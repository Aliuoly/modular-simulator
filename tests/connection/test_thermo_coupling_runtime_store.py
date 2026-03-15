from __future__ import annotations

# pyright: reportMissingImports=false

from dataclasses import replace
from typing import cast
from unittest.mock import patch

import numpy as np
import pytest

from modular_simulation.connection.connection_layer import TransportAndMixingUpdate
from modular_simulation.connection.process_binding import BindingError
from modular_simulation.connection.hydraulic_compile import HydraulicCompileLifecycle
from modular_simulation.connection.hydraulic_solver import (
    HydraulicSolveResult,
    HydraulicSystemDefinition,
    LinearResidualEquation,
)
from modular_simulation.connection import ProcessOutletConditionResolver
from modular_simulation.connection.network import ConnectionNetwork
from modular_simulation.connection.process_stream_io import (
    is_process_outlet_condition_resolver,
    resolve_process_outlet_condition,
)
from modular_simulation.connection.runtime import ConnectionRuntimeOrchestrator
from modular_simulation.connection.state import MaterialState, PortCondition
from modular_simulation.connection.transport import LagTransportState, LagTransportUpdateResult
from modular_simulation.flowsheet import Flowsheet
from modular_simulation.thermodynamics.runtime_context import SimulationRuntimeContext
from modular_simulation.thermodynamics.stream import StreamData
from modular_simulation.unit_processes import HeaterCooler


def _port_condition(*, pressure: float, temperature: float, flow_rate: float) -> PortCondition:
    return PortCondition(
        state=MaterialState(
            pressure=pressure,
            temperature=temperature,
            mole_fractions=(0.25, 0.75),
            species_ids=("7732-18-5", "64-17-5"),
            phase="liquid",
        ),
        species_ids=("7732-18-5", "64-17-5"),
        through_molar_flow_rate=flow_rate,
    )


class _ResolverPreferredUnit:
    def __init__(self, resolved_condition: PortCondition) -> None:
        self._resolved_condition = resolved_condition
        self.legacy_get_calls: list[str] = []
        self.resolver_calls: list[str] = []

    def apply_inlet(self, port_name: str, stream: StreamData) -> None:
        del port_name, stream

    def get_outlet_stream(self, port_name: str) -> StreamData:
        self.legacy_get_calls.append(port_name)
        raise AssertionError(
            "legacy get_outlet_stream fallback should not run when resolver exists"
        )

    def resolve_outlet_condition(self, port_name: str) -> PortCondition:
        self.resolver_calls.append(port_name)
        return self._resolved_condition


class _LegacyFallbackUnit:
    def __init__(self, outlet_stream: StreamData) -> None:
        self._outlet_stream = outlet_stream
        self.legacy_get_calls: list[str] = []

    def apply_inlet(self, port_name: str, stream: StreamData) -> None:
        del port_name, stream

    def get_outlet_stream(self, port_name: str) -> StreamData:
        self.legacy_get_calls.append(port_name)
        return self._outlet_stream


class _RuntimeSpeciesRegistry:
    cas_list = ("7732-18-5", "64-17-5")


class _RuntimeContextStub:
    species_registry = _RuntimeSpeciesRegistry()


class _ReactorRuntimePortBridge:
    def __init__(
        self,
        *,
        runtime: ConnectionRuntimeOrchestrator,
        resolved_condition: PortCondition,
        legacy_stream: StreamData,
    ) -> None:
        self._runtime = runtime
        self._resolved_condition = resolved_condition
        self._legacy_stream = legacy_stream
        self.legacy_get_calls: list[str] = []
        self.resolver_calls: list[str] = []
        self.inlet_snapshot_visible_before_apply: list[bool] = []

    def apply_inlet(self, port_name: str, stream: StreamData) -> None:
        snapshot = self._runtime.get_latest_inlet_condition(node_id="reactor", port_name=port_name)
        self.inlet_snapshot_visible_before_apply.append(snapshot is not None)
        if snapshot is not None:
            assert snapshot.through_molar_flow_rate == stream.molar_flow_rate

    def get_outlet_stream(self, port_name: str) -> StreamData:
        self.legacy_get_calls.append(port_name)
        return self._legacy_stream

    def resolve_outlet_condition(self, port_name: str) -> PortCondition:
        self.resolver_calls.append(port_name)
        return self._resolved_condition


def _linear_equation(
    residual_name: str,
    coefficients: dict[str, float],
    *,
    constant: float = 0.0,
) -> LinearResidualEquation:
    return LinearResidualEquation(
        residual_name=residual_name,
        coefficients=coefficients,
        constant=constant,
    )


def _valid_system() -> HydraulicSystemDefinition:
    return HydraulicSystemDefinition(
        equations=(),
        linear_residual_equations=(
            _linear_equation("ref", {"pressure": 1.0}, constant=-5.0),
            _linear_equation("balance", {"pressure": 1.0, "flow": -1.0}),
        ),
    )


def _hydraulic_result(*, edge_flow: float) -> HydraulicSolveResult:
    return HydraulicSolveResult(
        converged=True,
        iterations=2,
        residual_norm=1.0e-10,
        solution_vector=np.asarray([edge_flow, 5.0], dtype=np.float64),
        unknowns={"flow": edge_flow, "pressure": 5.0},
        unknown_index_map={"flow": 0, "pressure": 1},
        residual_index_map={"balance": 0, "ref": 1},
    )


def _transport_result() -> LagTransportUpdateResult:
    return LagTransportUpdateResult(
        state=LagTransportState(composition=(0.6, 0.4), temperature=315.0),
        update_fraction=0.5,
        flow_scale=1.0,
        flow_sign_changed=False,
        held_for_near_zero_flow=False,
    )


def test_resolver_preferred_outlet_resolution_uses_port_condition_resolver() -> None:
    resolved_condition = _port_condition(pressure=180000.0, temperature=345.0, flow_rate=4.5)
    unit = _ResolverPreferredUnit(resolved_condition)
    resolver: ProcessOutletConditionResolver = unit

    assert is_process_outlet_condition_resolver(resolver)
    assert resolve_process_outlet_condition(unit, "product") == resolved_condition
    assert unit.resolver_calls == ["product"]
    assert unit.legacy_get_calls == []


def test_legacy_fallback_outlet_resolution_without_resolver_returns_none() -> None:
    legacy_condition = _port_condition(pressure=155000.0, temperature=330.0, flow_rate=2.25)
    unit = _LegacyFallbackUnit(StreamData.from_port_condition(legacy_condition))

    resolved_condition = resolve_process_outlet_condition(unit, "product")

    assert resolved_condition is None
    assert unit.legacy_get_calls == []


def test_runtime_step_thermo_coupling_wires_runtime_owned_snapshot_store() -> None:
    def hydraulic_solve_step(
        *,
        network: ConnectionNetwork,
        macro_step_time_s: float,
    ) -> HydraulicSolveResult:
        del network, macro_step_time_s
        return _hydraulic_result(edge_flow=1.75)

    def transport_and_mixing_step(
        *,
        network: ConnectionNetwork,
        hydraulic_result: HydraulicSolveResult,
        macro_step_time_s: float,
    ) -> TransportAndMixingUpdate:
        del network, hydraulic_result, macro_step_time_s
        return TransportAndMixingUpdate(
            transport_results={
                "edge_0001": _transport_result(),
                "edge_0002": _transport_result(),
            }
        )

    runtime = ConnectionRuntimeOrchestrator(
        runtime_context=cast("SimulationRuntimeContext", _RuntimeContextStub()),
        hydraulic_solve_step=hydraulic_solve_step,
        transport_and_mixing_step=transport_and_mixing_step,
    )

    network = ConnectionNetwork(
        compile_lifecycle=HydraulicCompileLifecycle(),
        hydraulic_system_builder=lambda topology: _valid_system(),
        runtime_orchestrator=runtime,
    )
    network.add_process("reactor", inlet_ports=("feed",), outlet_ports=("product",))
    network.add_boundary_source("feed_boundary")
    network.add_boundary_sink("product_boundary")
    network.connect("feed_boundary", "reactor.feed")
    network.connect("reactor.product", "product_boundary")
    compiled = network.compile()

    resolved_condition = _port_condition(pressure=180000.0, temperature=345.0, flow_rate=4.5)
    legacy_condition = _port_condition(pressure=111000.0, temperature=301.0, flow_rate=0.33)
    reactor_bridge = _ReactorRuntimePortBridge(
        runtime=runtime,
        resolved_condition=resolved_condition,
        legacy_stream=StreamData.from_port_condition(legacy_condition),
    )
    runtime.bind_stream_port_io(node_id="reactor", stream_port_io=reactor_bridge)
    runtime.set_feed_stream(
        boundary_id="feed_boundary",
        stream=StreamData.from_port_condition(
            _port_condition(pressure=130000.0, temperature=320.0, flow_rate=3.2)
        ),
    )

    network._compiled = replace(
        compiled,
        process_bindings={
            **compiled.process_bindings,
            "reactor": reactor_bridge,
        },
    )

    _ = network.step(macro_step_time_s=1.0)

    assert reactor_bridge.resolver_calls == ["product"]
    assert reactor_bridge.legacy_get_calls == []
    assert reactor_bridge.inlet_snapshot_visible_before_apply == [True]

    latest_inlet = runtime.get_latest_inlet_condition(node_id="reactor", port_name="feed")
    assert latest_inlet is not None
    assert latest_inlet.state.pressure == 130000.0
    assert latest_inlet.state.temperature == 320.0
    assert latest_inlet.through_molar_flow_rate == 1.75

    latest_outlet = runtime.get_latest_outlet_condition(node_id="reactor", port_name="product")
    assert latest_outlet is not None
    assert latest_outlet.state.pressure == 180000.0
    assert latest_outlet.state.temperature == 345.0
    assert latest_outlet.through_molar_flow_rate == 1.75

    latest_outlet_stream = runtime.get_latest_outlet_stream(node_id="reactor", port_name="product")
    assert latest_outlet_stream is not None
    assert latest_outlet_stream.pressure == 180000.0
    assert latest_outlet_stream.temperature == 345.0
    assert latest_outlet_stream.molar_flow_rate == 1.75


def test_runtime_snapshot_preferred_flowsheet_uses_runtime_outlet_snapshot() -> None:
    context = SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    flowsheet = Flowsheet(context=context, dt=0.2)

    preferred_heater = HeaterCooler(n_species=2, mode="duty", external_heat_duty=0.0)
    flowsheet.add_unit("heater", preferred_heater)
    flowsheet.add_unit("cooler", HeaterCooler(n_species=2, mode="duty", external_heat_duty=0.0))
    flowsheet.add_feed_from_values("feed", T=320.0, P=140000.0, z=(0.5, 0.5), flow=2.0)
    flowsheet.chain("feed", "heater", "cooler")

    def _resolve_outlet_condition(self: HeaterCooler, port_name: str) -> PortCondition:
        return self.get_outlet_stream(port_name).to_port_condition()

    with patch.object(
        HeaterCooler,
        "resolve_outlet_condition",
        new=_resolve_outlet_condition,
        create=True,
    ):
        plant = flowsheet.compile()
        _ = plant.step(macro_step_time_s=0.2)

    legacy_get_calls: list[str] = []
    original_get_outlet_stream = HeaterCooler.get_outlet_stream

    def _tracked_get_outlet_stream(self: HeaterCooler, port_name: str) -> StreamData:
        if self is preferred_heater:
            legacy_get_calls.append(port_name)
            raise AssertionError(
                "flowsheet should use runtime-owned outlet snapshots before legacy get_outlet_stream"
            )
        return original_get_outlet_stream(self, port_name)

    heater_connection = flowsheet._connections[1]

    with patch.object(HeaterCooler, "get_outlet_stream", new=_tracked_get_outlet_stream):
        heater_to_cooler = flowsheet._stream_snapshot_for_connection(heater_connection)

    assert legacy_get_calls == []
    latest_outlet = plant.runtime_orchestrator.get_latest_outlet_condition(
        node_id="heater",
        port_name="outlet",
    )
    assert latest_outlet is not None
    assert heater_to_cooler == StreamData.from_port_condition(latest_outlet)


def test_legacy_fallback_thermo_coupling_process_source_without_resolver_raises_binding_error() -> (
    None
):
    def hydraulic_solve_step(
        *,
        network: ConnectionNetwork,
        macro_step_time_s: float,
    ) -> HydraulicSolveResult:
        del network, macro_step_time_s
        return _hydraulic_result(edge_flow=1.75)

    def transport_and_mixing_step(
        *,
        network: ConnectionNetwork,
        hydraulic_result: HydraulicSolveResult,
        macro_step_time_s: float,
    ) -> TransportAndMixingUpdate:
        del network, hydraulic_result, macro_step_time_s
        return TransportAndMixingUpdate(
            transport_results={
                "edge_0001": _transport_result(),
                "edge_0002": _transport_result(),
            }
        )

    runtime = ConnectionRuntimeOrchestrator(
        runtime_context=cast("SimulationRuntimeContext", _RuntimeContextStub()),
        hydraulic_solve_step=hydraulic_solve_step,
        transport_and_mixing_step=transport_and_mixing_step,
    )

    network = ConnectionNetwork(
        compile_lifecycle=HydraulicCompileLifecycle(),
        hydraulic_system_builder=lambda topology: _valid_system(),
        runtime_orchestrator=runtime,
    )
    network.add_process("reactor", inlet_ports=("feed",), outlet_ports=("product",))
    network.add_boundary_source("feed_boundary")
    network.add_boundary_sink("product_boundary")
    network.connect("feed_boundary", "reactor.feed")
    network.connect("reactor.product", "product_boundary")
    compiled = network.compile()

    reactor_bridge = _LegacyFallbackUnit(
        StreamData.from_port_condition(
            _port_condition(pressure=111000.0, temperature=301.0, flow_rate=0.33)
        )
    )
    runtime.bind_stream_port_io(node_id="reactor", stream_port_io=reactor_bridge)
    runtime.set_feed_stream(
        boundary_id="feed_boundary",
        stream=StreamData.from_port_condition(
            _port_condition(pressure=130000.0, temperature=320.0, flow_rate=3.2)
        ),
    )

    network._compiled = replace(
        compiled,
        process_bindings={
            **compiled.process_bindings,
            "reactor": reactor_bridge,
        },
    )

    with pytest.raises(BindingError, match="Missing canonical outlet condition"):
        _ = network.step(macro_step_time_s=1.0)

    assert reactor_bridge.legacy_get_calls == []


def test_legacy_fallback_flowsheet_stream_snapshot_without_runtime_snapshot_raises_runtime_error() -> (
    None
):
    context = SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    flowsheet = Flowsheet(context=context, dt=0.2)

    flowsheet.add_unit("heater", HeaterCooler(n_species=2, mode="duty", external_heat_duty=0.0))
    flowsheet.add_unit("cooler", HeaterCooler(n_species=2, mode="duty", external_heat_duty=0.0))
    flowsheet.add_feed_from_values("feed", T=320.0, P=140000.0, z=(0.5, 0.5), flow=2.0)
    flowsheet.chain("feed", "heater", "cooler")
    _ = flowsheet.compile()

    heater_connection = flowsheet._connections[1]
    with pytest.raises(RuntimeError, match="missing runtime-owned outlet snapshot"):
        _ = flowsheet._stream_snapshot_for_connection(heater_connection)


def test_legacy_fallback_flowsheet_unit_results_without_runtime_snapshot_raises_runtime_error() -> (
    None
):
    context = SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    flowsheet = Flowsheet(context=context, dt=0.2)

    heater = HeaterCooler(n_species=2, mode="duty", external_heat_duty=0.0)
    flowsheet.add_unit("heater", heater)
    flowsheet.add_unit("cooler", HeaterCooler(n_species=2, mode="duty", external_heat_duty=0.0))
    flowsheet.add_feed_from_values("feed", T=320.0, P=140000.0, z=(0.5, 0.5), flow=2.0)
    flowsheet.chain("feed", "heater", "cooler")
    _ = flowsheet.compile()

    state_trace_values = {
        "heater": {state_name: [] for state_name in heater.state_list},
        "cooler": {
            state_name: []
            for state_name in cast("HeaterCooler", flowsheet.get_unit("cooler")).state_list
        },
    }

    with pytest.raises(RuntimeError, match="missing runtime-owned outlet snapshot"):
        _ = flowsheet._build_unit_results(state_trace_values=state_trace_values)

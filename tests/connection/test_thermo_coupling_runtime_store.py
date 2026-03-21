from __future__ import annotations

# pyright: reportMissingImports=false

from dataclasses import replace
from typing import cast
from unittest.mock import patch

import numpy as np
import pytest

from modular_simulation.connection.runtime.connection_layer import TransportAndMixingUpdate
from modular_simulation.connection.topology.process_binding import BindingError
from modular_simulation.connection.hydraulics.hydraulic_compile import HydraulicCompileLifecycle
from modular_simulation.connection.hydraulics.hydraulic_solver import (
    HydraulicTopologyLookup,
    HydraulicSolveResult,
    HydraulicSystemDefinition,
    LinearResidualEquation,
)
from modular_simulation.connection.topology.junction import JunctionMixingResult
from modular_simulation.connection import ProcessOutletConditionResolver
from modular_simulation.connection.topology.network import ConnectionNetwork
from modular_simulation.connection.runtime.process_stream_io import (
    is_process_outlet_condition_resolver,
    resolve_process_outlet_condition,
)
from modular_simulation.connection.runtime.runtime import ConnectionRuntimeOrchestrator
from modular_simulation.connection.domain.state import MaterialState, PortCondition
from modular_simulation.connection.domain.transport import (
    LagTransportState,
    LagTransportUpdateResult,
)
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


class _SimpleRuntimeBridge:
    def __init__(self, resolved_condition: PortCondition) -> None:
        self._resolved_condition = resolved_condition
        self.inlets: dict[str, StreamData] = {}

    def apply_inlet(self, port_name: str, stream: StreamData) -> None:
        self.inlets[port_name] = stream

    def get_outlet_stream(self, port_name: str) -> StreamData:
        del port_name
        return StreamData.from_port_condition(self._resolved_condition)

    def resolve_outlet_condition(self, port_name: str) -> PortCondition:
        del port_name
        return self._resolved_condition


class _SyntheticSplitFixture:
    def __init__(
        self,
        *,
        split_fraction: float,
        branch_placeholder_flows: tuple[float, float],
    ) -> None:
        self.split_fraction = float(split_fraction)
        self.branch_placeholder_flows = branch_placeholder_flows
        self.inlet: StreamData | None = None

    def apply_inlet(self, port_name: str, stream: StreamData) -> None:
        del port_name
        self.inlet = stream

    def get_inlet(self, port_name: str):
        del port_name
        if self.inlet is None:
            return None
        return {
            "role": "inlet",
            "inlet_flow": float(self.inlet.molar_flow_rate),
            "temperature": float(self.inlet.temperature),
            "pressure": float(self.inlet.pressure),
            "composition": tuple(float(value) for value in self.inlet.mole_fractions),
        }

    def get_outlet_stream(self, port_name: str) -> StreamData:
        if self.inlet is None:
            raise RuntimeError("split fixture inlet not initialized")

        if port_name == "outlet_1":
            flow = self.branch_placeholder_flows[0]
        elif port_name == "outlet_2":
            flow = self.branch_placeholder_flows[1]
        else:
            raise ValueError(f"invalid outlet port '{port_name}'")

        return StreamData(
            temperature=self.inlet.temperature,
            pressure=self.inlet.pressure,
            mole_fractions=self.inlet.mole_fractions,
            molar_flow_rate=float(flow),
        )

    def resolve_outlet_condition(self, port_name: str) -> PortCondition:
        return self.get_outlet_stream(port_name).to_port_condition()


class _SyntheticMixFixture:
    def __init__(self) -> None:
        self._inlets: dict[str, StreamData] = {}

    def apply_inlet(self, port_name: str, stream: StreamData) -> None:
        self._inlets[port_name] = stream

    def get_outlet_stream(self, port_name: str) -> StreamData:
        if not self._inlets:
            raise RuntimeError("mix fixture inlet not initialized")
        total = sum(stream.molar_flow_rate for stream in self._inlets.values())
        reference = next(iter(self._inlets.values()))
        return StreamData(
            temperature=reference.temperature,
            pressure=reference.pressure,
            mole_fractions=reference.mole_fractions,
            molar_flow_rate=float(total),
        )

    def resolve_outlet_condition(self, port_name: str) -> PortCondition:
        return self.get_outlet_stream(port_name).to_port_condition()

    def seed_inlet(self, stream: StreamData) -> None:
        self._inlets["inlet"] = stream


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


def _lookup_system() -> HydraulicSystemDefinition:
    return HydraulicSystemDefinition(
        equations=(),
        linear_residual_equations=(
            _linear_equation("ref", {"pressure": 1.0}, constant=-5.0),
            _linear_equation("balance", {"pressure": 1.0, "flow": -1.0}),
        ),
        topology_lookup=HydraulicTopologyLookup(
            line_flow_unknown_by_line={"edge_0001": "edge_flow", "edge_0002": "edge_flow"},
            edge_source_pressure_unknown_by_line={
                "edge_0001": "source_pressure",
                "edge_0002": "source_pressure",
            },
            edge_target_pressure_unknown_by_line={
                "edge_0001": "target_pressure",
                "edge_0002": "target_pressure",
            },
            node_pressure_unknown_by_endpoint={
                "feed_boundary.outlet": "source_pressure",
                "reactor.feed": "target_pressure",
                "reactor.product": "source_pressure",
                "product_boundary.inlet": "target_pressure",
            },
            node_pressure_unknown_by_junction={},
            endpoint_role_by_endpoint={
                "reactor.feed": "pressure_state",
                "reactor.product": "pressure_state",
            },
            balancing_group_name_by_endpoint={
                "reactor.feed": "reactor_group",
                "reactor.product": "reactor_group",
            },
        ),
    )


def _lookup_system_with_passive_reactor_feed() -> HydraulicSystemDefinition:
    base_system = _lookup_system()
    return replace(
        base_system,
        topology_lookup=replace(
            base_system.topology_lookup,
            endpoint_role_by_endpoint={
                "reactor.feed": "passive",
                "reactor.product": "pressure_state",
            },
            balancing_group_name_by_endpoint={
                "reactor.product": "reactor_group",
            },
        ),
    )


def _hydraulic_result(*, edge_flow: float) -> HydraulicSolveResult:
    return HydraulicSolveResult(
        converged=True,
        iterations=2,
        residual_norm=1.0e-10,
        solution_vector=np.asarray([edge_flow, 7.0, 9.0], dtype=np.float64),
        unknowns={"edge_flow": edge_flow, "source_pressure": 7.0, "target_pressure": 9.0},
        unknown_index_map={"edge_flow": 0, "source_pressure": 1, "target_pressure": 2},
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
        hydraulic_system_builder=lambda topology: _lookup_system(),
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
    assert latest_inlet.state.pressure == 9.0  # From compiled hydraulic lookup (target_pressure)
    assert latest_inlet.state.temperature == 320.0  # From feed stream
    assert latest_inlet.through_molar_flow_rate == 1.75  # From compiled hydraulic lookup

    latest_outlet = runtime.get_latest_outlet_condition(node_id="reactor", port_name="product")
    assert latest_outlet is not None
    assert latest_outlet.state.pressure == 7.0
    assert latest_outlet.state.temperature == 345.0
    assert latest_outlet.through_molar_flow_rate == 1.75

    latest_outlet_stream = runtime.get_latest_outlet_stream(node_id="reactor", port_name="product")
    assert latest_outlet_stream is not None
    assert latest_outlet_stream.pressure == 7.0
    assert latest_outlet_stream.temperature == 345.0
    assert latest_outlet_stream.molar_flow_rate == 1.75


def test_runtime_snapshot_preferred_flowsheet_uses_runtime_outlet_snapshot() -> None:
    context = SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    flowsheet = Flowsheet(context=context, dt=0.2)

    preferred_heater = HeaterCooler(n_species=2, mode="duty", external_heat_duty=0.0)
    flowsheet.add_unit("heater", preferred_heater)
    cooler = HeaterCooler(n_species=2, mode="duty", external_heat_duty=0.0)
    flowsheet.add_unit("cooler", cooler)
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
        hydraulic_system_builder=lambda topology: _lookup_system(),
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

    heater = HeaterCooler(n_species=2, mode="duty", external_heat_duty=0.0)
    cooler = HeaterCooler(n_species=2, mode="duty", external_heat_duty=0.0)
    flowsheet.add_unit("heater", heater)
    flowsheet.add_unit("cooler", cooler)
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
    cooler = HeaterCooler(n_species=2, mode="duty", external_heat_duty=0.0)
    flowsheet.add_unit("cooler", cooler)
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


def test_thermo_coupling_prefers_compiled_hydraulic_lookup_over_payload_placeholders() -> None:
    def hydraulic_solve_step(
        *,
        network: ConnectionNetwork,
        macro_step_time_s: float,
    ) -> HydraulicSolveResult:
        del network, macro_step_time_s
        return _hydraulic_result(edge_flow=1.25)

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

    class _PayloadOnlyBridge(_ReactorRuntimePortBridge):
        def get_outlet(self, port_name: str):
            del port_name
            return {
                "role": "outlet",
                "outlet_flow": 99.0,
                "pressure": 222000.0,
                "composition": (0.25, 0.75),
            }

    runtime = ConnectionRuntimeOrchestrator(
        runtime_context=cast("SimulationRuntimeContext", _RuntimeContextStub()),
        hydraulic_solve_step=hydraulic_solve_step,
        transport_and_mixing_step=transport_and_mixing_step,
    )

    network = ConnectionNetwork(
        compile_lifecycle=HydraulicCompileLifecycle(),
        hydraulic_system_builder=lambda topology: _lookup_system(),
        runtime_orchestrator=runtime,
    )
    network.add_process("reactor", inlet_ports=("feed",), outlet_ports=("product",))
    network.add_boundary_source("feed_boundary")
    network.add_boundary_sink("product_boundary")
    network.connect("feed_boundary", "reactor.feed")
    network.connect("reactor.product", "product_boundary")
    compiled = network.compile()
    assert compiled.hydraulic is not None

    resolved_condition = _port_condition(pressure=180000.0, temperature=345.0, flow_rate=4.5)
    bridge = _PayloadOnlyBridge(
        runtime=runtime,
        resolved_condition=resolved_condition,
        legacy_stream=StreamData.from_port_condition(resolved_condition),
    )
    runtime.bind_stream_port_io(node_id="reactor", stream_port_io=bridge)
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
            "reactor": bridge,
        },
    )

    _ = network.step(macro_step_time_s=1.0)

    latest_inlet = runtime.get_latest_inlet_condition(node_id="reactor", port_name="feed")
    assert latest_inlet is not None
    assert latest_inlet.through_molar_flow_rate == pytest.approx(1.25)
    assert latest_inlet.state.pressure == pytest.approx(9.0)


def test_thermo_coupling_ignores_branch_fixture_placeholders_for_canonical_branch_flows() -> None:
    context = SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    runtime = ConnectionRuntimeOrchestrator(runtime_context=context)
    network = ConnectionNetwork(
        compile_lifecycle=HydraulicCompileLifecycle(),
        hydraulic_system_builder=lambda topology: _lookup_system(),
        runtime_orchestrator=runtime,
    )
    network.add_boundary_source("feed")
    network.add_process("junction", inlet_ports=("inlet",), outlet_ports=("outlet_1", "outlet_2"))
    network.add_process("unit_a", inlet_ports=("feed",), outlet_ports=("product",))
    network.add_process("unit_b", inlet_ports=("feed",), outlet_ports=("product",))
    network.connect("feed", "junction.inlet")
    network.connect("junction.outlet_1", "unit_a.feed")
    network.connect("junction.outlet_2", "unit_b.feed")
    compiled = network.compile()

    class _ManualSplitterCompiledHydraulic:
        topology_lookup = HydraulicTopologyLookup(
            line_flow_unknown_by_line={
                "edge_0001": "flow_in",
                "edge_0002": "flow_out_a",
                "edge_0003": "flow_out_b",
            },
            edge_source_pressure_unknown_by_line={
                "edge_0001": "p_feed",
                "edge_0002": "p_junction_out_a",
                "edge_0003": "p_junction_out_b",
            },
            edge_target_pressure_unknown_by_line={
                "edge_0001": "p_junction_in",
                "edge_0002": "p_unit_a",
                "edge_0003": "p_unit_b",
            },
            node_pressure_unknown_by_endpoint={
                "feed.outlet": "p_feed",
                "junction.inlet": "p_junction_in",
                "junction.outlet_1": "p_junction_out_a",
                "junction.outlet_2": "p_junction_out_b",
                "unit_a.feed": "p_unit_a",
                "unit_b.feed": "p_unit_b",
            },
            node_pressure_unknown_by_junction={},
        )

        def resolve_line_flow(
            self, *, line_id: str, hydraulic_result: HydraulicSolveResult
        ) -> float | None:
            key = self.topology_lookup.line_flow_unknown_by_line.get(line_id)
            return None if key is None else float(hydraulic_result.unknowns[key])

        def resolve_line_source_pressure(
            self, *, line_id: str, hydraulic_result: HydraulicSolveResult
        ) -> float | None:
            key = self.topology_lookup.edge_source_pressure_unknown_by_line.get(line_id)
            return None if key is None else float(hydraulic_result.unknowns[key])

        def resolve_line_target_pressure(
            self, *, line_id: str, hydraulic_result: HydraulicSolveResult
        ) -> float | None:
            key = self.topology_lookup.edge_target_pressure_unknown_by_line.get(line_id)
            return None if key is None else float(hydraulic_result.unknowns[key])

        def resolve_endpoint_pressure(
            self, *, endpoint_id: str, hydraulic_result: HydraulicSolveResult
        ) -> float | None:
            key = self.topology_lookup.node_pressure_unknown_by_endpoint.get(endpoint_id)
            return None if key is None else float(hydraulic_result.unknowns[key])

        def resolve_junction_pressure(
            self, *, junction_id: str, hydraulic_result: HydraulicSolveResult
        ) -> float | None:
            del junction_id, hydraulic_result
            return None

        def solve(self) -> HydraulicSolveResult:
            raise AssertionError("not used")

    split_fixture = _SyntheticMixFixture()
    split_fixture.seed_inlet(
        StreamData.from_port_condition(
            _port_condition(pressure=138000.0, temperature=320.0, flow_rate=2.0)
        )
    )
    unit_a_bridge = _SimpleRuntimeBridge(
        _port_condition(pressure=101000.0, temperature=300.0, flow_rate=1.0)
    )
    unit_b_bridge = _SimpleRuntimeBridge(
        _port_condition(pressure=101000.0, temperature=300.0, flow_rate=1.0)
    )
    runtime.bind_stream_port_io(node_id="junction", stream_port_io=split_fixture)
    runtime.bind_stream_port_io(node_id="unit_a", stream_port_io=unit_a_bridge)
    runtime.bind_stream_port_io(node_id="unit_b", stream_port_io=unit_b_bridge)
    runtime.set_feed_stream(
        boundary_id="feed",
        stream=StreamData.from_port_condition(
            PortCondition(
                state=MaterialState(
                    pressure=140000.0,
                    temperature=320.0,
                    mole_fractions=(0.5, 0.5),
                    species_ids=("water", "ethanol"),
                ),
                species_ids=("water", "ethanol"),
                through_molar_flow_rate=2.0,
            )
        ),
    )

    network._compiled = replace(
        compiled,
        hydraulic=cast(object, _ManualSplitterCompiledHydraulic()),
        process_bindings={
            **compiled.process_bindings,
            "junction": split_fixture,
            "unit_a": unit_a_bridge,
            "unit_b": unit_b_bridge,
        },
    )

    hydraulic_result = HydraulicSolveResult(
        converged=True,
        iterations=2,
        residual_norm=1.0e-10,
        solution_vector=np.asarray(
            [2.0, 1.25, 0.75, 140000.0, 138000.0, 130000.0, 129000.0, 120000.0, 118000.0],
            dtype=np.float64,
        ),
        unknowns={
            "flow_in": 2.0,
            "flow_out_a": 1.25,
            "flow_out_b": 0.75,
            "p_feed": 140000.0,
            "p_junction_in": 138000.0,
            "p_junction_out_a": 130000.0,
            "p_junction_out_b": 129000.0,
            "p_unit_a": 120000.0,
            "p_unit_b": 118000.0,
        },
        unknown_index_map={},
        residual_index_map={},
    )

    _ = runtime._boundary_propagation_step(
        network=network,
        hydraulic_result=hydraulic_result,
        transport_and_mixing_update=TransportAndMixingUpdate(
            transport_results={
                "edge_0001": _transport_result(),
                "edge_0002": _transport_result(),
                "edge_0003": _transport_result(),
            }
        ),
        macro_step_time_s=1.0,
    )

    splitter_outlet_1 = runtime.get_latest_outlet_condition(
        node_id="junction",
        port_name="outlet_1",
    )
    splitter_outlet_2 = runtime.get_latest_outlet_condition(
        node_id="junction",
        port_name="outlet_2",
    )
    unit_a_inlet = runtime.get_latest_inlet_condition(node_id="unit_a", port_name="feed")
    unit_b_inlet = runtime.get_latest_inlet_condition(node_id="unit_b", port_name="feed")

    assert splitter_outlet_1 is not None
    assert splitter_outlet_2 is not None
    assert unit_a_inlet is not None
    assert unit_b_inlet is not None
    assert splitter_outlet_1.through_molar_flow_rate == pytest.approx(1.25)
    assert splitter_outlet_2.through_molar_flow_rate == pytest.approx(0.75)
    assert unit_a_inlet.through_molar_flow_rate == pytest.approx(1.25)
    assert unit_b_inlet.through_molar_flow_rate == pytest.approx(0.75)
    assert splitter_outlet_1.through_molar_flow_rate != 99.0
    assert splitter_outlet_2.through_molar_flow_rate != 88.0
    assert unit_a_inlet.through_molar_flow_rate != pytest.approx(2.0 * 0.99)
    assert unit_b_inlet.through_molar_flow_rate != pytest.approx(2.0 * 0.01)


def test_hydraulic_pressure_resolution_requires_compiled_lookup_no_heuristic_discovery() -> None:
    """Verify that hydraulic pressure resolution does NOT use heuristic unknown-name discovery."""

    def hydraulic_solve_step(
        *,
        network: ConnectionNetwork,
        macro_step_time_s: float,
    ) -> HydraulicSolveResult:
        del network, macro_step_time_s
        # Return a hydraulic result with heuristic-like unknown names that should NOT be used
        return HydraulicSolveResult(
            converged=True,
            iterations=2,
            residual_norm=1.0e-10,
            solution_vector=np.asarray([1.75, 200000.0, 9.0], dtype=np.float64),
            unknowns={
                "edge_flow": 1.75,
                "edge_0001.pressure": 200000.0,  # Heuristic-like key
                "edge_0001_pressure": 210000.0,  # Another heuristic-like key
                "source_pressure": 7.0,
                "target_pressure": 9.0,  # This is the correct compiled lookup value
            },
            unknown_index_map={"edge_flow": 0, "source_pressure": 1, "target_pressure": 2},
            residual_index_map={"balance": 0, "ref": 1},
        )

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

    class _PayloadOnlyBridge(_ReactorRuntimePortBridge):
        def get_outlet(self, port_name: str):
            del port_name
            return {
                "role": "outlet",
                "outlet_flow": 99.0,
                "pressure": 222000.0,
                "composition": (0.25, 0.75),
            }

    runtime = ConnectionRuntimeOrchestrator(
        runtime_context=cast("SimulationRuntimeContext", _RuntimeContextStub()),
        hydraulic_solve_step=hydraulic_solve_step,
        transport_and_mixing_step=transport_and_mixing_step,
    )

    network = ConnectionNetwork(
        compile_lifecycle=HydraulicCompileLifecycle(),
        hydraulic_system_builder=lambda topology: _lookup_system(),
        runtime_orchestrator=runtime,
    )
    network.add_process("reactor", inlet_ports=("feed",), outlet_ports=("product",))
    network.add_boundary_source("feed_boundary")
    network.add_boundary_sink("product_boundary")
    network.connect("feed_boundary", "reactor.feed")
    network.connect("reactor.product", "product_boundary")
    compiled = network.compile()

    resolved_condition = _port_condition(pressure=180000.0, temperature=345.0, flow_rate=4.5)
    bridge = _PayloadOnlyBridge(
        runtime=runtime,
        resolved_condition=resolved_condition,
        legacy_stream=StreamData.from_port_condition(resolved_condition),
    )
    runtime.bind_stream_port_io(node_id="reactor", stream_port_io=bridge)
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
            "reactor": bridge,
        },
    )

    _ = network.step(macro_step_time_s=1.0)

    # Verify that the inlet receives pressure from compiled lookup (target_pressure=9.0),
    # NOT from heuristic unknown keys in the result (edge_0001.pressure=200000.0, etc)
    latest_inlet = runtime.get_latest_inlet_condition(node_id="reactor", port_name="feed")
    assert latest_inlet is not None
    assert latest_inlet.state.pressure == pytest.approx(9.0)
    assert latest_inlet.state.pressure != 200000.0
    assert latest_inlet.state.pressure != 210000.0


def test_hydraulic_flow_resolution_requires_compiled_lookup_no_heuristic_discovery() -> None:
    """Verify that hydraulic flow resolution does NOT use heuristic unknown-name discovery."""

    def hydraulic_solve_step(
        *,
        network: ConnectionNetwork,
        macro_step_time_s: float,
    ) -> HydraulicSolveResult:
        del network, macro_step_time_s
        # Return a hydraulic result with heuristic-like unknown names that should NOT be used
        # Include flow-like keys that the old heuristic would have discovered
        return HydraulicSolveResult(
            converged=True,
            iterations=2,
            residual_norm=1.0e-10,
            solution_vector=np.asarray([1.5, 7.0, 9.0], dtype=np.float64),
            unknowns={
                "edge_flow": 1.5,  # Compiled lookup value
                "edge_0001_flow": 99.5,  # Heuristic-like key that should NOT be used
                "flow_edge_0001": 88.5,  # Another heuristic-like key
                "source_pressure": 7.0,
                "target_pressure": 9.0,
            },
            unknown_index_map={"edge_flow": 0, "source_pressure": 1, "target_pressure": 2},
            residual_index_map={"balance": 0, "ref": 1},
        )

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

    class _PayloadOnlyBridge(_ReactorRuntimePortBridge):
        def get_outlet(self, port_name: str):
            del port_name
            return {
                "role": "outlet",
                "outlet_flow": 99.0,
                "pressure": 222000.0,
                "composition": (0.25, 0.75),
            }

    runtime = ConnectionRuntimeOrchestrator(
        runtime_context=cast("SimulationRuntimeContext", _RuntimeContextStub()),
        hydraulic_solve_step=hydraulic_solve_step,
        transport_and_mixing_step=transport_and_mixing_step,
    )

    network = ConnectionNetwork(
        compile_lifecycle=HydraulicCompileLifecycle(),
        hydraulic_system_builder=lambda topology: _lookup_system(),
        runtime_orchestrator=runtime,
    )
    network.add_process("reactor", inlet_ports=("feed",), outlet_ports=("product",))
    network.add_boundary_source("feed_boundary")
    network.add_boundary_sink("product_boundary")
    network.connect("feed_boundary", "reactor.feed")
    network.connect("reactor.product", "product_boundary")
    compiled = network.compile()

    resolved_condition = _port_condition(pressure=180000.0, temperature=345.0, flow_rate=4.5)
    bridge = _PayloadOnlyBridge(
        runtime=runtime,
        resolved_condition=resolved_condition,
        legacy_stream=StreamData.from_port_condition(resolved_condition),
    )
    runtime.bind_stream_port_io(node_id="reactor", stream_port_io=bridge)
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
            "reactor": bridge,
        },
    )

    _ = network.step(macro_step_time_s=1.0)

    # Verify that the inlet receives flow from compiled lookup (edge_flow=1.5),
    # NOT from heuristic unknown keys (edge_0001_flow=99.5, flow_edge_0001=88.5, etc)
    latest_inlet = runtime.get_latest_inlet_condition(node_id="reactor", port_name="feed")
    assert latest_inlet is not None
    assert latest_inlet.through_molar_flow_rate == pytest.approx(1.5)
    assert latest_inlet.through_molar_flow_rate != 99.5
    assert latest_inlet.through_molar_flow_rate != 88.5


def test_thermo_coupling_preserves_solved_zero_flow_instead_of_payload_placeholder() -> None:
    def hydraulic_solve_step(
        *,
        network: ConnectionNetwork,
        macro_step_time_s: float,
    ) -> HydraulicSolveResult:
        del network, macro_step_time_s
        return _hydraulic_result(edge_flow=0.0)

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

    class _PayloadOnlyBridge(_ReactorRuntimePortBridge):
        def get_outlet(self, port_name: str):
            del port_name
            return {
                "role": "outlet",
                "outlet_flow": 99.0,
                "pressure": 222000.0,
                "composition": (0.25, 0.75),
            }

    runtime = ConnectionRuntimeOrchestrator(
        runtime_context=cast("SimulationRuntimeContext", _RuntimeContextStub()),
        hydraulic_solve_step=hydraulic_solve_step,
        transport_and_mixing_step=transport_and_mixing_step,
    )

    network = ConnectionNetwork(
        compile_lifecycle=HydraulicCompileLifecycle(),
        hydraulic_system_builder=lambda topology: _lookup_system(),
        runtime_orchestrator=runtime,
    )
    network.add_process("reactor", inlet_ports=("feed",), outlet_ports=("product",))
    network.add_boundary_source("feed_boundary")
    network.add_boundary_sink("product_boundary")
    network.connect("feed_boundary", "reactor.feed")
    network.connect("reactor.product", "product_boundary")
    compiled = network.compile()

    resolved_condition = _port_condition(pressure=180000.0, temperature=345.0, flow_rate=4.5)
    bridge = _PayloadOnlyBridge(
        runtime=runtime,
        resolved_condition=resolved_condition,
        legacy_stream=StreamData.from_port_condition(resolved_condition),
    )
    runtime.bind_stream_port_io(node_id="reactor", stream_port_io=bridge)
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
            "reactor": bridge,
        },
    )

    _ = network.step(macro_step_time_s=1.0)

    latest_inlet = runtime.get_latest_inlet_condition(node_id="reactor", port_name="feed")
    assert latest_inlet is not None
    assert latest_inlet.through_molar_flow_rate == pytest.approx(0.0)


def test_pressure_coupled_endpoint_missing_compiled_pressure_raises_instead_of_falling_back() -> (
    None
):
    def hydraulic_solve_step(
        *,
        network: ConnectionNetwork,
        macro_step_time_s: float,
    ) -> HydraulicSolveResult:
        del network, macro_step_time_s
        return _hydraulic_result(edge_flow=1.25)

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

    class _PayloadOnlyBridge(_ReactorRuntimePortBridge):
        def get_outlet(self, port_name: str):
            del port_name
            return {
                "role": "outlet",
                "outlet_flow": 99.0,
                "pressure": 222000.0,
                "composition": (0.25, 0.75),
            }

    runtime = ConnectionRuntimeOrchestrator(
        runtime_context=cast("SimulationRuntimeContext", _RuntimeContextStub()),
        hydraulic_solve_step=hydraulic_solve_step,
        transport_and_mixing_step=transport_and_mixing_step,
    )

    network = ConnectionNetwork(
        compile_lifecycle=HydraulicCompileLifecycle(),
        hydraulic_system_builder=lambda topology: _lookup_system(),
        runtime_orchestrator=runtime,
    )
    network.add_process("reactor", inlet_ports=("feed",), outlet_ports=("product",))
    network.add_boundary_source("feed_boundary")
    network.add_boundary_sink("product_boundary")
    network.connect("feed_boundary", "reactor.feed")
    network.connect("reactor.product", "product_boundary")
    compiled = network.compile()

    resolved_condition = _port_condition(pressure=180000.0, temperature=345.0, flow_rate=4.5)
    bridge = _PayloadOnlyBridge(
        runtime=runtime,
        resolved_condition=resolved_condition,
        legacy_stream=StreamData.from_port_condition(resolved_condition),
    )
    runtime.bind_stream_port_io(node_id="reactor", stream_port_io=bridge)
    runtime.set_feed_stream(
        boundary_id="feed_boundary",
        stream=StreamData.from_port_condition(
            _port_condition(pressure=130000.0, temperature=320.0, flow_rate=3.2)
        ),
    )
    assert compiled.hydraulic is not None
    compiled_hydraulic = compiled.hydraulic
    network._compiled = replace(
        compiled,
        hydraulic=replace(
            compiled_hydraulic,
            system=replace(
                compiled_hydraulic.system,
                topology_lookup=replace(
                    compiled_hydraulic.topology_lookup,
                    node_pressure_unknown_by_endpoint={
                        "feed_boundary.outlet": "source_pressure",
                        "product_boundary.inlet": "target_pressure",
                    },
                    balancing_group_name_by_endpoint={},
                ),
            ),
        ),
        process_bindings={
            **compiled.process_bindings,
            "reactor": bridge,
        },
    )

    with pytest.raises(BindingError, match="Missing compiled hydraulic pressure mapping"):
        _ = network.step(macro_step_time_s=1.0)


def test_pressure_coupled_endpoint_does_not_reuse_balancing_group_pressure() -> None:
    def hydraulic_solve_step(
        *,
        network: ConnectionNetwork,
        macro_step_time_s: float,
    ) -> HydraulicSolveResult:
        del network, macro_step_time_s
        return _hydraulic_result(edge_flow=1.25)

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

    class _PayloadOnlyBridge(_ReactorRuntimePortBridge):
        def get_outlet(self, port_name: str):
            del port_name
            return {
                "role": "outlet",
                "outlet_flow": 99.0,
                "pressure": 222000.0,
                "composition": (0.25, 0.75),
            }

    runtime = ConnectionRuntimeOrchestrator(
        runtime_context=cast("SimulationRuntimeContext", _RuntimeContextStub()),
        hydraulic_solve_step=hydraulic_solve_step,
        transport_and_mixing_step=transport_and_mixing_step,
    )

    network = ConnectionNetwork(
        compile_lifecycle=HydraulicCompileLifecycle(),
        hydraulic_system_builder=lambda topology: _lookup_system(),
        runtime_orchestrator=runtime,
    )
    network.add_process("reactor", inlet_ports=("feed",), outlet_ports=("product",))
    network.add_boundary_source("feed_boundary")
    network.add_boundary_sink("product_boundary")
    network.connect("feed_boundary", "reactor.feed")
    network.connect("reactor.product", "product_boundary")
    compiled = network.compile()
    assert compiled.hydraulic is not None

    resolved_condition = _port_condition(pressure=180000.0, temperature=345.0, flow_rate=4.5)
    bridge = _PayloadOnlyBridge(
        runtime=runtime,
        resolved_condition=resolved_condition,
        legacy_stream=StreamData.from_port_condition(resolved_condition),
    )
    runtime.bind_stream_port_io(node_id="reactor", stream_port_io=bridge)
    runtime.set_feed_stream(
        boundary_id="feed_boundary",
        stream=StreamData.from_port_condition(
            _port_condition(pressure=130000.0, temperature=320.0, flow_rate=3.2)
        ),
    )
    network._compiled = replace(
        compiled,
        hydraulic=replace(
            compiled.hydraulic,
            system=replace(
                compiled.hydraulic.system,
                topology_lookup=replace(
                    compiled.hydraulic.topology_lookup,
                    node_pressure_unknown_by_endpoint={
                        "feed_boundary.outlet": "source_pressure",
                        "reactor.product": "source_pressure",
                        "product_boundary.inlet": "target_pressure",
                    },
                ),
            ),
        ),
        process_bindings={
            **compiled.process_bindings,
            "reactor": bridge,
        },
    )

    with pytest.raises(BindingError, match="Missing compiled hydraulic pressure mapping"):
        _ = network.step(macro_step_time_s=1.0)


def test_passive_endpoint_allows_payload_pressure_fallback_when_compiled_pressure_missing() -> None:
    def hydraulic_solve_step(
        *,
        network: ConnectionNetwork,
        macro_step_time_s: float,
    ) -> HydraulicSolveResult:
        del network, macro_step_time_s
        return _hydraulic_result(edge_flow=1.25)

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

    class _PayloadOnlyBridge(_ReactorRuntimePortBridge):
        def get_outlet(self, port_name: str):
            del port_name
            return {
                "role": "outlet",
                "outlet_flow": 99.0,
                "pressure": 222000.0,
                "composition": (0.25, 0.75),
            }

    runtime = ConnectionRuntimeOrchestrator(
        runtime_context=cast("SimulationRuntimeContext", _RuntimeContextStub()),
        hydraulic_solve_step=hydraulic_solve_step,
        transport_and_mixing_step=transport_and_mixing_step,
    )

    network = ConnectionNetwork(
        compile_lifecycle=HydraulicCompileLifecycle(),
        hydraulic_system_builder=lambda topology: _lookup_system_with_passive_reactor_feed(),
        runtime_orchestrator=runtime,
    )
    network.add_process("reactor", inlet_ports=("feed",), outlet_ports=("product",))
    network.add_boundary_source("feed_boundary")
    network.add_boundary_sink("product_boundary")
    network.connect("feed_boundary", "reactor.feed")
    network.connect("reactor.product", "product_boundary")
    compiled = network.compile()
    assert compiled.hydraulic is not None

    resolved_condition = _port_condition(pressure=180000.0, temperature=345.0, flow_rate=4.5)
    bridge = _PayloadOnlyBridge(
        runtime=runtime,
        resolved_condition=resolved_condition,
        legacy_stream=StreamData.from_port_condition(resolved_condition),
    )
    runtime.bind_stream_port_io(node_id="reactor", stream_port_io=bridge)
    runtime.set_feed_stream(
        boundary_id="feed_boundary",
        stream=StreamData.from_port_condition(
            _port_condition(pressure=130000.0, temperature=320.0, flow_rate=3.2)
        ),
    )
    network._compiled = replace(
        compiled,
        hydraulic=replace(
            compiled.hydraulic,
            system=replace(
                compiled.hydraulic.system,
                topology_lookup=replace(
                    compiled.hydraulic.topology_lookup,
                    node_pressure_unknown_by_endpoint={
                        "feed_boundary.outlet": "source_pressure",
                        "reactor.product": "source_pressure",
                        "product_boundary.inlet": "target_pressure",
                    },
                    balancing_group_name_by_endpoint={
                        "reactor.product": "reactor_group",
                    },
                ),
            ),
        ),
        process_bindings={
            **compiled.process_bindings,
            "reactor": bridge,
        },
    )

    _ = network.step(macro_step_time_s=1.0)

    latest_inlet = runtime.get_latest_inlet_condition(node_id="reactor", port_name="feed")
    assert latest_inlet is not None
    assert latest_inlet.state.pressure == pytest.approx(7.0)


def test_pressure_coupled_edge_missing_solved_flow_raises_instead_of_zero_flow() -> None:
    runtime = ConnectionRuntimeOrchestrator(
        runtime_context=cast("SimulationRuntimeContext", _RuntimeContextStub())
    )
    network = ConnectionNetwork(
        compile_lifecycle=HydraulicCompileLifecycle(),
        hydraulic_system_builder=lambda topology: _lookup_system(),
        runtime_orchestrator=runtime,
    )
    network.add_process("reactor", inlet_ports=("feed",), outlet_ports=("product",))
    network.add_boundary_source("feed_boundary")
    network.add_boundary_sink("product_boundary")
    network.connect("feed_boundary", "reactor.feed")
    network.connect("reactor.product", "product_boundary")
    compiled = network.compile()
    assert compiled.hydraulic is not None

    class _MissingFlowCompiledHydraulic:
        topology_lookup = compiled.hydraulic.topology_lookup

        def resolve_line_flow(
            self, *, line_id: str, hydraulic_result: HydraulicSolveResult
        ) -> float | None:
            del line_id, hydraulic_result
            return None

        def resolve_line_source_pressure(
            self, *, line_id: str, hydraulic_result: HydraulicSolveResult
        ) -> float | None:
            key = self.topology_lookup.edge_source_pressure_unknown_by_line.get(line_id)
            return None if key is None else float(hydraulic_result.unknowns[key])

        def resolve_line_target_pressure(
            self, *, line_id: str, hydraulic_result: HydraulicSolveResult
        ) -> float | None:
            key = self.topology_lookup.edge_target_pressure_unknown_by_line.get(line_id)
            return None if key is None else float(hydraulic_result.unknowns[key])

        def resolve_endpoint_pressure(
            self, *, endpoint_id: str, hydraulic_result: HydraulicSolveResult
        ) -> float | None:
            key = self.topology_lookup.node_pressure_unknown_by_endpoint.get(endpoint_id)
            return None if key is None else float(hydraulic_result.unknowns[key])

        def resolve_junction_pressure(
            self, *, junction_id: str, hydraulic_result: HydraulicSolveResult
        ) -> float | None:
            del junction_id, hydraulic_result
            return None

        def solve(self) -> HydraulicSolveResult:
            raise AssertionError("not used")

    runtime.set_feed_stream(
        boundary_id="feed_boundary",
        stream=StreamData.from_port_condition(
            _port_condition(pressure=130000.0, temperature=320.0, flow_rate=3.2)
        ),
    )
    network._compiled = replace(
        compiled,
        hydraulic=cast(object, _MissingFlowCompiledHydraulic()),
    )

    with pytest.raises(BindingError, match="Missing compiled hydraulic flow mapping"):
        _ = runtime._boundary_propagation_step(
            network=network,
            hydraulic_result=HydraulicSolveResult(
                converged=True,
                iterations=2,
                residual_norm=1.0e-10,
                solution_vector=np.asarray([7.0, 9.0], dtype=np.float64),
                unknowns={"source_pressure": 7.0, "target_pressure": 9.0},
                unknown_index_map={"source_pressure": 0, "target_pressure": 1},
                residual_index_map={"balance": 0, "ref": 1},
            ),
            transport_and_mixing_update=TransportAndMixingUpdate(transport_results={}),
            macro_step_time_s=1.0,
        )


def test_thermo_coupling_uses_single_junction_mix_for_multiple_outgoing_edges() -> None:
    context = SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    runtime = ConnectionRuntimeOrchestrator(runtime_context=context)
    network = ConnectionNetwork(
        compile_lifecycle=HydraulicCompileLifecycle(),
        hydraulic_system_builder=lambda topology: _lookup_system(),
        runtime_orchestrator=runtime,
    )
    network.add_boundary_source("feed_a")
    network.add_boundary_source("feed_b")
    network.add_junction(
        "mix", inlet_ports=("inlet_a", "inlet_b"), outlet_ports=("outlet_a", "outlet_b")
    )
    network.add_process("unit_a", inlet_ports=("feed",), outlet_ports=("product",))
    network.add_process("unit_b", inlet_ports=("feed",), outlet_ports=("product",))
    network.connect("feed_a", "mix.inlet_a")
    network.connect("feed_b", "mix.inlet_b")
    network.connect("mix.outlet_a", "unit_a.feed")
    network.connect("mix.outlet_b", "unit_b.feed")
    compiled = network.compile()

    class _ManualCompiledHydraulic:
        topology_lookup = HydraulicTopologyLookup(
            line_flow_unknown_by_line={
                "edge_0001": "flow_a",
                "edge_0002": "flow_b",
                "edge_0003": "flow_out_a",
                "edge_0004": "flow_out_b",
            },
            edge_source_pressure_unknown_by_line={
                "edge_0001": "p_feed_a",
                "edge_0002": "p_feed_b",
                "edge_0003": "p_mix",
                "edge_0004": "p_mix",
            },
            edge_target_pressure_unknown_by_line={
                "edge_0001": "p_mix",
                "edge_0002": "p_mix",
                "edge_0003": "p_unit_a",
                "edge_0004": "p_unit_b",
            },
            node_pressure_unknown_by_endpoint={
                "feed_a.outlet": "p_feed_a",
                "feed_b.outlet": "p_feed_b",
                "mix.inlet_a": "p_mix",
                "mix.inlet_b": "p_mix",
                "mix.outlet_a": "p_mix",
                "mix.outlet_b": "p_mix",
                "unit_a.feed": "p_unit_a",
                "unit_b.feed": "p_unit_b",
            },
            node_pressure_unknown_by_junction={"mix": "p_mix"},
        )

        def resolve_line_flow(
            self, *, line_id: str, hydraulic_result: HydraulicSolveResult
        ) -> float | None:
            key = self.topology_lookup.line_flow_unknown_by_line.get(line_id)
            return None if key is None else float(hydraulic_result.unknowns[key])

        def resolve_line_source_pressure(
            self, *, line_id: str, hydraulic_result: HydraulicSolveResult
        ) -> float | None:
            key = self.topology_lookup.edge_source_pressure_unknown_by_line.get(line_id)
            return None if key is None else float(hydraulic_result.unknowns[key])

        def resolve_line_target_pressure(
            self, *, line_id: str, hydraulic_result: HydraulicSolveResult
        ) -> float | None:
            key = self.topology_lookup.edge_target_pressure_unknown_by_line.get(line_id)
            return None if key is None else float(hydraulic_result.unknowns[key])

        def resolve_endpoint_pressure(
            self, *, endpoint_id: str, hydraulic_result: HydraulicSolveResult
        ) -> float | None:
            key = self.topology_lookup.node_pressure_unknown_by_endpoint.get(endpoint_id)
            return None if key is None else float(hydraulic_result.unknowns[key])

        def resolve_junction_pressure(
            self, *, junction_id: str, hydraulic_result: HydraulicSolveResult
        ) -> float | None:
            key = self.topology_lookup.node_pressure_unknown_by_junction.get(junction_id)
            return None if key is None else float(hydraulic_result.unknowns[key])

        def solve(self) -> HydraulicSolveResult:
            raise AssertionError("not used")

    unit_a_bridge = _SimpleRuntimeBridge(
        _port_condition(pressure=101000.0, temperature=300.0, flow_rate=1.0)
    )
    unit_b_bridge = _SimpleRuntimeBridge(
        _port_condition(pressure=101000.0, temperature=300.0, flow_rate=1.0)
    )
    runtime.bind_stream_port_io(node_id="unit_a", stream_port_io=unit_a_bridge)
    runtime.bind_stream_port_io(node_id="unit_b", stream_port_io=unit_b_bridge)
    runtime.set_feed_stream(
        boundary_id="feed_a",
        stream=StreamData.from_port_condition(
            PortCondition(
                state=MaterialState(
                    pressure=120000.0,
                    temperature=300.0,
                    mole_fractions=(1.0, 0.0),
                    species_ids=("water", "ethanol"),
                ),
                species_ids=("water", "ethanol"),
                through_molar_flow_rate=5.0,
            )
        ),
    )
    runtime.set_feed_stream(
        boundary_id="feed_b",
        stream=StreamData.from_port_condition(
            PortCondition(
                state=MaterialState(
                    pressure=130000.0,
                    temperature=330.0,
                    mole_fractions=(0.0, 1.0),
                    species_ids=("water", "ethanol"),
                ),
                species_ids=("water", "ethanol"),
                through_molar_flow_rate=3.0,
            )
        ),
    )

    network._compiled = replace(
        compiled,
        hydraulic=cast(object, _ManualCompiledHydraulic()),
        process_bindings={
            **compiled.process_bindings,
            "unit_a": unit_a_bridge,
            "unit_b": unit_b_bridge,
        },
    )

    hydraulic_result = HydraulicSolveResult(
        converged=True,
        iterations=2,
        residual_norm=1.0e-10,
        solution_vector=np.asarray(
            [5.0, 3.0, 4.0, 4.0, 120000.0, 130000.0, 125000.0, 110000.0, 111000.0], dtype=np.float64
        ),
        unknowns={
            "flow_a": 5.0,
            "flow_b": 3.0,
            "flow_out_a": 4.0,
            "flow_out_b": 4.0,
            "p_feed_a": 120000.0,
            "p_feed_b": 130000.0,
            "p_mix": 125000.0,
            "p_unit_a": 110000.0,
            "p_unit_b": 111000.0,
        },
        unknown_index_map={},
        residual_index_map={},
    )

    _ = runtime._boundary_propagation_step(
        network=network,
        hydraulic_result=hydraulic_result,
        transport_and_mixing_update=TransportAndMixingUpdate(
            transport_results={
                "edge_0001": _transport_result(),
                "edge_0002": _transport_result(),
                "edge_0003": _transport_result(),
                "edge_0004": _transport_result(),
            },
            junction_results={
                "mix": JunctionMixingResult(
                    state=MaterialState(
                        pressure=125000.0,
                        temperature=311.25,
                        mole_fractions=(0.625, 0.375),
                        species_ids=("water", "ethanol"),
                    ),
                    total_incoming_flow_rate=8.0,
                    used_fallback=False,
                )
            },
        ),
        macro_step_time_s=1.0,
    )

    inlet_a = runtime.get_latest_inlet_condition(node_id="unit_a", port_name="feed")
    inlet_b = runtime.get_latest_inlet_condition(node_id="unit_b", port_name="feed")
    assert inlet_a is not None
    assert inlet_b is not None
    assert inlet_a.state.temperature == pytest.approx(311.25)
    assert inlet_b.state.temperature == pytest.approx(311.25)
    assert inlet_a.state.mole_fractions == pytest.approx((0.625, 0.375))
    assert inlet_b.state.mole_fractions == pytest.approx((0.625, 0.375))
    assert inlet_a.through_molar_flow_rate == pytest.approx(4.0)
    assert inlet_b.through_molar_flow_rate == pytest.approx(4.0)


def test_participating_source_endpoint_missing_own_mapping_raises_even_if_line_target_pressure_exists() -> (
    None
):
    """
    Regression: _resolve_pressure() must check endpoint participation BEFORE calling
    _resolve_hydraulic_pressure() (which returns the line's target pressure).  A participating
    source endpoint whose OWN compiled endpoint mapping is absent must raise BindingError, not
    silently use the line-target pressure.

    Uses a purely payload-only bridge (no resolve_outlet_condition) so _build_material_state() /
    _resolve_pressure() is actually exercised instead of the resolver-based path.
    """

    class _PurePayloadBridge:
        """Payload-only bridge: has get_outlet() but NO resolve_outlet_condition().
        Forces _build_material_state() / _resolve_pressure() code path."""

        def apply_inlet(self, port_name: str, stream: StreamData) -> None:
            del port_name, stream

        def get_outlet(self, port_name: str) -> dict[str, object]:
            del port_name
            return {
                "role": "outlet",
                "outlet_flow": 2.0,
                "pressure": 888000.0,
                "composition": (0.25, 0.75),
            }

    class _ParticipatingSourceMissingOwnMapping:
        """Compiled hydraulic where source endpoint has a participating role but NO own
        endpoint mapping, yet resolve_line_target_pressure returns a value for the edge.

        Both edges map to the same 'target_pressure' unknown, so resolve_line_target_pressure
        returns 9.0 for the reactor.product→product_boundary edge.  The old code would silently
        use that value as the source pressure; the correct code must raise BindingError instead.
        """

        topology_lookup = HydraulicTopologyLookup(
            line_flow_unknown_by_line={"edge_0001": "edge_flow", "edge_0002": "edge_flow"},
            edge_source_pressure_unknown_by_line={
                "edge_0001": "source_pressure",
                "edge_0002": "source_pressure",
            },
            edge_target_pressure_unknown_by_line={
                "edge_0001": "target_pressure",
                "edge_0002": "target_pressure",
            },
            node_pressure_unknown_by_endpoint={
                # reactor.product is a participating source but has NO own mapping here
                "product_boundary.inlet": "target_pressure",
            },
            node_pressure_unknown_by_junction={},
            endpoint_role_by_endpoint={
                "reactor.product": "pressure_state",  # participating, but no mapping above
            },
            balancing_group_name_by_endpoint={},
        )

        def resolve_line_flow(
            self, *, line_id: str, hydraulic_result: HydraulicSolveResult
        ) -> float | None:
            key = self.topology_lookup.line_flow_unknown_by_line.get(line_id)
            return None if key is None else float(hydraulic_result.unknowns[key])

        def resolve_line_source_pressure(
            self, *, line_id: str, hydraulic_result: HydraulicSolveResult
        ) -> float | None:
            key = self.topology_lookup.edge_source_pressure_unknown_by_line.get(line_id)
            return None if key is None else float(hydraulic_result.unknowns[key])

        def resolve_line_target_pressure(
            self, *, line_id: str, hydraulic_result: HydraulicSolveResult
        ) -> float | None:
            # Both edges return a value — the bug would silently use this for the participating source
            key = self.topology_lookup.edge_target_pressure_unknown_by_line.get(line_id)
            return None if key is None else float(hydraulic_result.unknowns[key])

        def resolve_endpoint_pressure(
            self, *, endpoint_id: str, hydraulic_result: HydraulicSolveResult
        ) -> float | None:
            key = self.topology_lookup.node_pressure_unknown_by_endpoint.get(endpoint_id)
            return None if key is None else float(hydraulic_result.unknowns[key])

        def resolve_junction_pressure(
            self, *, junction_id: str, hydraulic_result: HydraulicSolveResult
        ) -> float | None:
            del junction_id, hydraulic_result
            return None

        def solve(self) -> HydraulicSolveResult:
            raise AssertionError("not used")

    runtime = ConnectionRuntimeOrchestrator(
        runtime_context=cast("SimulationRuntimeContext", _RuntimeContextStub())
    )
    network = ConnectionNetwork(
        compile_lifecycle=HydraulicCompileLifecycle(),
        hydraulic_system_builder=lambda topology: _lookup_system(),
        runtime_orchestrator=runtime,
    )
    network.add_process("reactor", inlet_ports=("feed",), outlet_ports=("product",))
    network.add_boundary_source("feed_boundary")
    network.add_boundary_sink("product_boundary")
    network.connect("feed_boundary", "reactor.feed")
    network.connect("reactor.product", "product_boundary")
    compiled = network.compile()

    bridge = _PurePayloadBridge()
    runtime.set_feed_stream(
        boundary_id="feed_boundary",
        stream=StreamData.from_port_condition(
            _port_condition(pressure=130000.0, temperature=320.0, flow_rate=3.2)
        ),
    )
    network._compiled = replace(
        compiled,
        hydraulic=cast(object, _ParticipatingSourceMissingOwnMapping()),
        process_bindings={
            **compiled.process_bindings,
            "reactor": bridge,
        },
    )

    with pytest.raises(BindingError, match="Missing compiled hydraulic pressure mapping"):
        _ = runtime._boundary_propagation_step(
            network=network,
            hydraulic_result=HydraulicSolveResult(
                converged=True,
                iterations=2,
                residual_norm=1.0e-10,
                solution_vector=np.asarray([1.5, 7.0, 9.0], dtype=np.float64),
                unknowns={"edge_flow": 1.5, "source_pressure": 7.0, "target_pressure": 9.0},
                unknown_index_map={"edge_flow": 0, "source_pressure": 1, "target_pressure": 2},
                residual_index_map={},
            ),
            transport_and_mixing_update=TransportAndMixingUpdate(
                # edge_0002 is reactor.product→product_boundary; providing its transport result
                # ensures _build_material_state() is reached for the participating source endpoint
                transport_results={
                    "edge_0001": _transport_result(),
                    "edge_0002": _transport_result(),
                },
            ),
            macro_step_time_s=1.0,
        )


def test_thermo_coupling_classifies_reverse_flow_from_local_node_sign() -> None:
    context = SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    runtime = ConnectionRuntimeOrchestrator(runtime_context=context)
    network = ConnectionNetwork(
        compile_lifecycle=HydraulicCompileLifecycle(),
        hydraulic_system_builder=lambda topology: _lookup_system(),
        runtime_orchestrator=runtime,
    )
    network.add_process("upstream", inlet_ports=("feed",), outlet_ports=("product",))
    network.add_process("downstream", inlet_ports=("feed",), outlet_ports=("product",))
    network.connect("upstream.product", "downstream.feed")
    compiled = network.compile()

    class _ReverseCompiledHydraulic:
        topology_lookup = HydraulicTopologyLookup(
            line_flow_unknown_by_line={"edge_0001": "edge_flow"},
            edge_source_pressure_unknown_by_line={"edge_0001": "p_upstream"},
            edge_target_pressure_unknown_by_line={"edge_0001": "p_downstream"},
            node_pressure_unknown_by_endpoint={
                "upstream.product": "p_upstream",
                "downstream.feed": "p_downstream",
            },
            node_pressure_unknown_by_junction={},
        )

        def resolve_line_flow(
            self, *, line_id: str, hydraulic_result: HydraulicSolveResult
        ) -> float | None:
            return float(hydraulic_result.unknowns["edge_flow"])

        def resolve_line_source_pressure(
            self, *, line_id: str, hydraulic_result: HydraulicSolveResult
        ) -> float | None:
            return float(hydraulic_result.unknowns["p_upstream"])

        def resolve_line_target_pressure(
            self, *, line_id: str, hydraulic_result: HydraulicSolveResult
        ) -> float | None:
            return float(hydraulic_result.unknowns["p_downstream"])

        def resolve_endpoint_pressure(
            self, *, endpoint_id: str, hydraulic_result: HydraulicSolveResult
        ) -> float | None:
            key = self.topology_lookup.node_pressure_unknown_by_endpoint.get(endpoint_id)
            return None if key is None else float(hydraulic_result.unknowns[key])

        def resolve_junction_pressure(
            self, *, junction_id: str, hydraulic_result: HydraulicSolveResult
        ) -> float | None:
            del junction_id, hydraulic_result
            return None

        def solve(self) -> HydraulicSolveResult:
            raise AssertionError("not used")

    class _Bridge(_SimpleRuntimeBridge):
        pass

    upstream_condition = PortCondition(
        state=MaterialState(
            pressure=150000.0,
            temperature=350.0,
            mole_fractions=(1.0, 0.0),
            species_ids=("water", "ethanol"),
        ),
        species_ids=("water", "ethanol"),
        through_molar_flow_rate=2.0,
    )
    downstream_condition = PortCondition(
        state=MaterialState(
            pressure=160000.0,
            temperature=290.0,
            mole_fractions=(0.0, 1.0),
            species_ids=("water", "ethanol"),
        ),
        species_ids=("water", "ethanol"),
        through_molar_flow_rate=2.0,
    )
    upstream_bridge = _Bridge(upstream_condition)
    downstream_bridge = _Bridge(downstream_condition)
    runtime.bind_stream_port_io(node_id="upstream", stream_port_io=upstream_bridge)
    runtime.bind_stream_port_io(node_id="downstream", stream_port_io=downstream_bridge)

    network._compiled = replace(
        compiled,
        hydraulic=cast(object, _ReverseCompiledHydraulic()),
        process_bindings={
            **compiled.process_bindings,
            "upstream": upstream_bridge,
            "downstream": downstream_bridge,
        },
    )

    hydraulic_result = HydraulicSolveResult(
        converged=True,
        iterations=2,
        residual_norm=1.0e-10,
        solution_vector=np.asarray([-2.0, 150000.0, 160000.0], dtype=np.float64),
        unknowns={"edge_flow": -2.0, "p_upstream": 150000.0, "p_downstream": 160000.0},
        unknown_index_map={},
        residual_index_map={},
    )

    _ = runtime._boundary_propagation_step(
        network=network,
        hydraulic_result=hydraulic_result,
        transport_and_mixing_update=TransportAndMixingUpdate(
            transport_results={"edge_0001": _transport_result()}
        ),
        macro_step_time_s=1.0,
    )

    latest_upstream_inlet = runtime.get_latest_inlet_condition(
        node_id="upstream", port_name="product"
    )
    assert latest_upstream_inlet is not None
    assert latest_upstream_inlet.state.temperature == pytest.approx(290.0)
    assert latest_upstream_inlet.state.mole_fractions == pytest.approx((0.0, 1.0))
    assert latest_upstream_inlet.state.pressure == pytest.approx(150000.0)
    assert latest_upstream_inlet.through_molar_flow_rate == pytest.approx(2.0)

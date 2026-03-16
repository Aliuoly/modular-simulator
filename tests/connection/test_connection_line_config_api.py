from __future__ import annotations

import importlib
from collections.abc import Mapping
from types import MappingProxyType
from typing import Protocol, cast

import pytest

from modular_simulation.connection.domain.domain_contracts import ValveConfig
from modular_simulation.connection.hydraulics.hydraulic_compile import (
    HydraulicCompileLifecycle,
    calculate_effective_valve_resistance,
)
from modular_simulation.connection.hydraulics.hydraulic_element import (
    HydraulicElement,
    ValveHydraulicElement,
)
from modular_simulation.connection.hydraulics.hydraulic_solver import (
    ElementEquation,
    HydraulicSystemDefinition,
)
from modular_simulation.connection.topology.network import ConnectionNetwork
from modular_simulation.connection.runtime.runtime import (
    ConnectionRuntimeOrchestrator,
    ConnectionRuntimeStepResult,
)


class _ConnectionLineApi(Protocol):
    def connect_line(
        self,
        *,
        source: str,
        target: str,
        line_id: str | None = None,
        idempotency_key: str | None = None,
        expected_revision: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> str: ...

    def configure_line_geometry(
        self,
        *,
        line_id: str,
        radius_m: float,
        length_m: float,
        equation_name: str | None = None,
        resistance_parameter_name: str | None = None,
        idempotency_key: str | None = None,
        expected_revision: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> str: ...

    def use_derived_resistance(
        self,
        *,
        line_id: str,
        idempotency_key: str | None = None,
        expected_revision: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> str: ...

    def attach_line_valve(
        self,
        *,
        line_id: str,
        valve: ValveConfig,
        equation_name: str | None = None,
        resistance_parameter_name: str | None = None,
        idempotency_key: str | None = None,
        expected_revision: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> str: ...


class _ConnectionLineApiFactory(Protocol):
    def __call__(self, *, network: ConnectionNetwork) -> _ConnectionLineApi: ...


def _api(network: ConnectionNetwork) -> _ConnectionLineApi:
    module = importlib.import_module("modular_simulation.connection.domain.reconfiguration_api")
    api_factory = cast(
        _ConnectionLineApiFactory,
        getattr(module, "DynamicConnectionLineReconfigurationApi"),
    )
    return api_factory(network=network)


def _valve_system() -> HydraulicSystemDefinition:
    return HydraulicSystemDefinition(
        equations=(
            ElementEquation(
                name="eq_line_feed",
                element=cast(
                    HydraulicElement,
                    cast(object, ValveHydraulicElement()),
                ),
                inputs=MappingProxyType(
                    {
                        "upstream_pressure": 120_000.0,
                        "downstream_pressure": 100_000.0,
                    }
                ),
                parameters=MappingProxyType(
                    {
                        "valve_resistance": 1.0,
                        "delta": 1.0e-3,
                    }
                ),
                unknown_name_map=MappingProxyType({"flow_rate": "flow_line_feed"}),
                residual_name_map=MappingProxyType({"head_balance": "head_balance_line_feed"}),
            ),
        ),
        linear_residual_equations=(),
    )


def _network(runtime: ConnectionRuntimeOrchestrator) -> ConnectionNetwork:
    network = ConnectionNetwork(
        compile_lifecycle=HydraulicCompileLifecycle(),
        hydraulic_system_builder=lambda topology: _valve_system(),
        runtime_orchestrator=runtime,
    )
    network.add_process("producer", inlet_ports=("feed",), outlet_ports=("product",))
    network.add_process("consumer", inlet_ports=("feed",), outlet_ports=("product",))
    _ = network.compile()
    return network


def test_connect_and_configure_line_resistance_through_transaction_api() -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)
    api = _api(network)

    connect_request = api.connect_line(
        source="producer.product",
        target="consumer.feed",
        line_id="line_feed",
    )
    geometry_request = api.configure_line_geometry(
        line_id="line_feed",
        radius_m=0.05,
        length_m=2.0,
        equation_name="eq_line_feed",
        resistance_parameter_name="valve_resistance",
    )
    resistance_mode_request = api.use_derived_resistance(line_id="line_feed")
    valve_request = api.attach_line_valve(
        line_id="line_feed",
        valve=ValveConfig(
            valve_id="valve_feed",
            minimum_open_fraction=0.1,
            maximum_open_fraction=1.0,
            initial_open_fraction=0.6,
        ),
    )
    assert (
        connect_request,
        geometry_request,
        resistance_mode_request,
        valve_request,
    ) == ("rq_0001", "rq_0002", "rq_0003", "rq_0004")

    result = cast(ConnectionRuntimeStepResult, network.step(macro_step_time_s=0.25))
    assert result.graph_revision == "graph_rev_0002"
    assert result.barrier_reconfiguration.applied_request_ids == (
        "rq_0001",
        "rq_0002",
        "rq_0003",
        "rq_0004",
    )
    assert result.barrier_reconfiguration.skipped_request_ids == ()

    compiled = network.compiled
    assert compiled is not None and compiled.hydraulic is not None
    assert tuple(edge.edge_id for edge in compiled.topology.edges) == ("line_feed",)
    line_state = compiled.hydraulic.valve_state_by_line["line_feed"]
    expected_open_resistance = 2.0 / (0.05**4)
    assert line_state.valve_id == "valve_feed"
    assert abs(line_state.resistance_when_open - expected_open_resistance) < 1.0e-9

    expected_effective_resistance = calculate_effective_valve_resistance(
        resistance_when_open=line_state.resistance_when_open,
        open_fraction=line_state.current_open_fraction,
        minimum_open_fraction=line_state.minimum_open_fraction,
        maximum_open_fraction=line_state.maximum_open_fraction,
    )
    equation = compiled.hydraulic.system.equations[0]
    assert abs(equation.parameters["valve_resistance"] - expected_effective_resistance) < 1.0e-9
    assert network.queued_reconfigurations == ()


def test_invalid_endpoint_direction_is_rejected_without_side_effects() -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)
    api = _api(network)

    request_id = api.connect_line(
        source="consumer.feed",
        target="producer.product",
        line_id="line_invalid_direction",
    )
    assert request_id == "rq_0001"
    before_snapshot = network.save_runtime_snapshot()

    with pytest.raises(
        RuntimeError,
        match=(
            r"reconfiguration transaction rollback: request 'rq_0001' mutation 1 failed: "
            + r"invalid endpoint direction for connection 'consumer.feed->producer.product'"
        ),
    ):
        _ = network.step(macro_step_time_s=0.25)

    after_snapshot = network.save_runtime_snapshot()
    assert after_snapshot == before_snapshot
    compiled = network.compiled
    assert compiled is not None
    assert compiled.graph_revision == "graph_rev_0001"
    assert tuple(edge.edge_id for edge in compiled.topology.edges) == ()
    assert tuple(item.request_id for item in network.queued_reconfigurations) == ("rq_0001",)

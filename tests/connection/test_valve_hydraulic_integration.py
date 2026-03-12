from __future__ import annotations

from types import MappingProxyType
from typing import cast

import pytest

from modular_simulation.connection.domain_contracts import ResistanceConfig, ValveConfig
from modular_simulation.connection.hydraulic_compile import (
    HydraulicCompileLifecycle,
    compile_valve_hydraulic_state,
    resolve_line_resistance,
)
from modular_simulation.connection.hydraulic_element import HydraulicElement, ValveHydraulicElement
from modular_simulation.connection.hydraulic_solver import (
    ElementEquation,
    HydraulicSystemDefinition,
)
from modular_simulation.connection.network import ConnectionNetwork
from modular_simulation.connection.runtime import (
    ConnectionRuntimeOrchestrator,
    ConnectionRuntimeStepResult,
)


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
    network.add_process("reactor", inlet_ports=("feed",), outlet_ports=("product",))
    network.add_boundary_source("feed_boundary")
    network.add_boundary_sink("product_boundary")
    _ = network.connect("feed_boundary", "reactor.feed")
    _ = network.connect("reactor.product", "product_boundary")
    _ = network.compile()
    return network


def _configure_compiled_valve_state(network: ConnectionNetwork) -> None:
    compiled = network.compiled
    if compiled is None:
        raise RuntimeError("compiled network is required")

    resolved_resistance = resolve_line_resistance(
        line_id="line_feed",
        resistance=ResistanceConfig(mode="derived", radius_m=0.05, length_m=2.0),
    )
    valve_state = compile_valve_hydraulic_state(
        line_id="line_feed",
        equation_name="eq_line_feed",
        resolved_resistance=resolved_resistance,
        valve=ValveConfig(
            valve_id="valve_feed",
            minimum_open_fraction=0.1,
            maximum_open_fraction=1.0,
            initial_open_fraction=0.2,
        ),
    )
    hydraulic = HydraulicCompileLifecycle().compile(
        system=_valve_system(),
        graph_revision=compiled.graph_revision,
        valve_state_by_line={"line_feed": valve_state},
    )
    network.replace_compiled_hydraulic(hydraulic=hydraulic)


def _active_valve_resistance(network: ConnectionNetwork) -> float:
    compiled = network.compiled
    if compiled is None or compiled.hydraulic is None:
        raise RuntimeError("compiled hydraulic graph is required")
    equation = compiled.hydraulic.system.equations[0]
    return float(equation.parameters["valve_resistance"])


def _solve_flow_rate(network: ConnectionNetwork) -> float:
    compiled = network.compiled
    if compiled is None or compiled.hydraulic is None:
        raise RuntimeError("compiled hydraulic graph is required")
    solved = compiled.hydraulic.solve(tolerance=1.0e-12, max_iterations=25)
    return solved.unknowns["flow_line_feed"]


def test_valve_actuation_affects_flow_and_effective_resistance() -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)
    _configure_compiled_valve_state(network)

    baseline_flow = _solve_flow_rate(network)
    baseline_resistance = _active_valve_resistance(network)

    _ = network.queue_reconfiguration(
        {
            "operation": "batch_update",
            "mutations": [
                {
                    "operation": "set_valve_open_fraction",
                    "line_id": "line_feed",
                    "open_fraction": 0.8,
                }
            ],
        }
    )
    _ = cast(ConnectionRuntimeStepResult, network.step(macro_step_time_s=1.0))

    updated_flow = _solve_flow_rate(network)
    updated_resistance = _active_valve_resistance(network)
    compiled = network.compiled
    assert compiled is not None and compiled.hydraulic is not None
    assert compiled.hydraulic.valve_state_by_line["line_feed"].current_open_fraction == 0.8
    assert updated_resistance < baseline_resistance
    assert updated_flow > baseline_flow


def test_invalid_valve_range_is_rejected_without_runtime_corruption() -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)
    _configure_compiled_valve_state(network)

    before_resistance = _active_valve_resistance(network)

    _ = network.queue_reconfiguration(
        {
            "operation": "batch_update",
            "mutations": [
                {
                    "operation": "set_valve_open_fraction",
                    "line_id": "line_feed",
                    "open_fraction": 1.5,
                }
            ],
        }
    )
    before_snapshot = network.save_runtime_snapshot()

    with pytest.raises(
        RuntimeError,
        match=(
            r"reconfiguration transaction rollback: request 'rq_0001' mutation 1 failed: "
            r"valve command for line 'line_feed' must be within \[0.1, 1.0\], got 1.5"
        ),
    ):
        _ = network.step(macro_step_time_s=1.0)

    after_snapshot = network.save_runtime_snapshot()
    after_resistance = _active_valve_resistance(network)
    assert after_snapshot == before_snapshot
    assert abs(after_resistance - before_resistance) < 1.0e-12


def test_apply_valve_command_updates_compiled_graph_deterministically() -> None:
    resolved_resistance = resolve_line_resistance(
        line_id="line_feed",
        resistance=ResistanceConfig(mode="derived", radius_m=0.05, length_m=2.0),
    )
    valve_state = compile_valve_hydraulic_state(
        line_id="line_feed",
        equation_name="eq_line_feed",
        resolved_resistance=resolved_resistance,
        valve=ValveConfig(
            valve_id="valve_feed",
            minimum_open_fraction=0.1,
            maximum_open_fraction=1.0,
            initial_open_fraction=0.2,
        ),
    )
    compiled = HydraulicCompileLifecycle().compile(
        system=_valve_system(),
        graph_revision="rev_valve",
        valve_state_by_line={"line_feed": valve_state},
    )

    updated_a = compiled.with_valve_commands({"line_feed": 0.65})
    updated_b = compiled.with_valve_commands({"line_feed": 0.65})

    assert updated_a == updated_b

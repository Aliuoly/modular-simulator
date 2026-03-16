from __future__ import annotations

from typing import cast

import pytest

from modular_simulation.connection.hydraulics.hydraulic_compile import HydraulicCompileLifecycle
from modular_simulation.connection.hydraulics.hydraulic_solver import (
    HydraulicSystemDefinition,
    LinearResidualEquation,
)
from modular_simulation.connection.topology.network import ConnectionNetwork
from modular_simulation.connection.runtime.runtime import (
    ConnectionRuntimeOrchestrator,
    ConnectionRuntimeStepResult,
)


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


def _network(runtime: ConnectionRuntimeOrchestrator) -> ConnectionNetwork:
    network = ConnectionNetwork(
        compile_lifecycle=HydraulicCompileLifecycle(),
        hydraulic_system_builder=lambda topology: _valid_system(),
        runtime_orchestrator=runtime,
    )
    network.add_process("reactor", inlet_ports=("feed",), outlet_ports=("product",))
    network.add_boundary_source("feed_boundary")
    network.add_boundary_sink("product_boundary")
    _ = network.connect("feed_boundary", "reactor.feed")
    _ = network.connect("reactor.product", "product_boundary")
    _ = network.compile()
    return network


def test_remove_unit_with_dependents_is_blocked_by_default() -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)

    _ = network.queue_reconfiguration(
        {
            "operation": "batch_update",
            "metadata": {
                "control_dependencies": {
                    "unit:reactor": ["controller:reactor_pid"],
                }
            },
            "mutations": [
                {
                    "operation": "remove_unit",
                    "process_id": "reactor",
                }
            ],
        }
    )
    before_step_snapshot = network.save_runtime_snapshot()

    with pytest.raises(RuntimeError) as error:
        _ = network.step(macro_step_time_s=1.0)

    message = str(error.value)
    assert "DESTRUCTIVE_EDIT_DEPENDENTS" in message
    assert '"operation":"remove_unit"' in message
    assert '"target":"unit:reactor"' in message
    assert (
        '"blocking_dependents":["control:controller:reactor_pid","edge:edge_0001","edge:edge_0002"]'
        in message
    )
    assert '"policy_mode":"hard_fail"' in message
    assert network.save_runtime_snapshot() == before_step_snapshot
    compiled = network.compiled
    assert compiled is not None
    assert tuple(node.process_id for node in compiled.topology.process_nodes) == ("reactor",)
    assert compiled.topology.edge_ids == ("edge_0001", "edge_0002")


def test_remove_unit_safe_detach_works_only_when_mode_is_set_in_metadata() -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)

    request_id = network.queue_reconfiguration(
        {
            "operation": "batch_update",
            "metadata": {
                "destructive_edit_mode": "safe_detach",
                "control_dependencies": {
                    "unit:reactor": ["controller:reactor_pid"],
                },
            },
            "mutations": [
                {
                    "operation": "remove_unit",
                    "process_id": "reactor",
                    "destructive_edit_mode": "safe_detach",
                }
            ],
        }
    )
    assert request_id == "rq_0001"

    result = cast(ConnectionRuntimeStepResult, network.step(macro_step_time_s=0.25))
    assert result.graph_revision == "graph_rev_0002"
    assert result.barrier_reconfiguration.applied_request_ids == ("rq_0001",)
    assert result.barrier_reconfiguration.skipped_request_ids == ()
    compiled = network.compiled
    assert compiled is not None
    assert tuple(node.process_id for node in compiled.topology.process_nodes) == ()
    assert tuple(edge.edge_id for edge in compiled.topology.edges) == ()


def test_remove_unit_safe_detach_flag_inside_mutation_is_ignored() -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)

    _ = network.queue_reconfiguration(
        {
            "operation": "batch_update",
            "metadata": {
                "control_dependencies": {
                    "unit:reactor": ["controller:reactor_pid"],
                }
            },
            "mutations": [
                {
                    "operation": "remove_unit",
                    "process_id": "reactor",
                    "destructive_edit_mode": "safe_detach",
                }
            ],
        }
    )

    with pytest.raises(RuntimeError) as error:
        _ = network.step(macro_step_time_s=1.0)

    message = str(error.value)
    assert "DESTRUCTIVE_EDIT_DEPENDENTS" in message
    assert '"policy_mode":"hard_fail"' in message
    compiled = network.compiled
    assert compiled is not None
    assert tuple(node.process_id for node in compiled.topology.process_nodes) == ("reactor",)
    assert compiled.topology.edge_ids == ("edge_0001", "edge_0002")

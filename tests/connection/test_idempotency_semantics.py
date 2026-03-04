from __future__ import annotations

import pytest
from typing import cast

from modular_simulation.connection.hydraulic_compile import HydraulicCompileLifecycle
from modular_simulation.connection.hydraulic_solver import (
    HydraulicSystemDefinition,
    LinearResidualEquation,
)
from modular_simulation.connection.network import ConnectionNetwork
from modular_simulation.connection.runtime import (
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


def _network(runtime: ConnectionRuntimeOrchestrator | None = None) -> ConnectionNetwork:
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


def _compiled_boundary_ids(network: ConnectionNetwork) -> tuple[str, ...]:
    compiled = network.compiled
    if compiled is None:
        return ()
    return tuple(node.boundary_id for node in compiled.topology.boundary_nodes)


def _compiled_edge_ids(network: ConnectionNetwork) -> tuple[str, ...]:
    compiled = network.compiled
    if compiled is None:
        return ()
    return tuple(edge.edge_id for edge in compiled.topology.edges)


def test_idempotent_single_operation_replay_is_skipped_without_state_change() -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)

    _ = network.queue_reconfiguration(
        {
            "operation": "add_boundary_sink",
            "boundary_id": "sink_a",
            "idempotency_key": "sink-a",
        }
    )
    first = cast(ConnectionRuntimeStepResult, network.step(macro_step_time_s=1.0))
    assert first.barrier_reconfiguration.applied_request_ids == ("rq_0001",)
    assert first.barrier_reconfiguration.skipped_request_ids == ()
    assert first.graph_revision == "graph_rev_0002"

    _ = network.queue_reconfiguration(
        {
            "operation": "add_boundary_sink",
            "boundary_id": "sink_a",
            "idempotency_key": "sink-a",
        }
    )
    replay = cast(ConnectionRuntimeStepResult, network.step(macro_step_time_s=1.0))

    assert replay.barrier_reconfiguration.applied_request_ids == ()
    assert replay.barrier_reconfiguration.skipped_request_ids == ("rq_0002",)
    assert replay.graph_revision == "graph_rev_0002"
    assert _compiled_edge_ids(network) == ("edge_0001", "edge_0002")


def test_idempotency_conflict_fails_deterministically_with_no_state_mutation() -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)

    _ = network.queue_reconfiguration(
        {
            "operation": "add_boundary_sink",
            "boundary_id": "sink_a",
            "idempotency_key": "sink-a",
        }
    )
    _ = network.step(macro_step_time_s=1.0)

    _ = network.queue_reconfiguration(
        {
            "operation": "add_boundary_sink",
            "boundary_id": "sink_b",
            "idempotency_key": "sink-a",
        }
    )
    pre_failure_snapshot = network.save_runtime_snapshot()

    with pytest.raises(
        RuntimeError,
        match=(
            "reconfiguration transaction rollback: request 'rq_0002' reuses "
            "idempotency_key 'sink-a' with different payload"
        ),
    ):
        _ = network.step(macro_step_time_s=1.0)

    assert "sink_b" not in _compiled_boundary_ids(network)
    assert tuple(item.request_id for item in network.queued_reconfigurations) == ("rq_0002",)
    assert network.save_runtime_snapshot() == pre_failure_snapshot


def test_idempotency_conflict_inside_explicit_batch_request_rolls_back() -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)

    _ = network.queue_reconfiguration(
        {
            "operation": "batch_update",
            "idempotency_key": "batch-key",
            "mutations": [
                {"operation": "add_boundary_sink", "boundary_id": "sink_a"},
            ],
        }
    )
    _ = network.step(macro_step_time_s=1.0)

    _ = network.queue_reconfiguration(
        {
            "operation": "batch_update",
            "idempotency_key": "batch-key",
            "mutations": [
                {"operation": "add_boundary_sink", "boundary_id": "sink_b"},
                {
                    "operation": "add_connection",
                    "source": "reactor.product",
                    "target": "sink_b",
                },
            ],
        }
    )
    pre_failure_snapshot = network.save_runtime_snapshot()

    with pytest.raises(
        RuntimeError,
        match=(
            "reconfiguration transaction rollback: request 'rq_0002' reuses "
            "idempotency_key 'batch-key' with different payload"
        ),
    ):
        _ = network.step(macro_step_time_s=1.0)

    assert "sink_b" not in _compiled_boundary_ids(network)
    assert _compiled_edge_ids(network) == ("edge_0001", "edge_0002")
    assert tuple(item.request_id for item in network.queued_reconfigurations) == ("rq_0002",)
    assert network.save_runtime_snapshot() == pre_failure_snapshot

from __future__ import annotations

# pyright: reportMissingImports=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportUnusedCallResult=false

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
    network.connect("feed_boundary", "reactor.feed")
    network.connect("reactor.product", "product_boundary")
    _ = network.compile()
    return network


def test_mutation_queued_during_macro_step_commits_only_at_next_barrier() -> None:
    def macro_step_hook(
        network: ConnectionNetwork, macro_step_index: int, simulation_time_s: float
    ) -> None:
        del simulation_time_s
        if macro_step_index != 1:
            return
        request_id = network.queue_reconfiguration(
            {
                "operation": "batch_update",
                "mutations": [
                    {
                        "operation": "add_boundary_sink",
                        "boundary_id": "purge_sink",
                    },
                    {
                        "operation": "add_connection",
                        "source": "reactor.product",
                        "target": "purge_sink",
                    },
                ],
            }
        )
        assert request_id == "rq_0001"

    runtime = ConnectionRuntimeOrchestrator(macro_step_hook=macro_step_hook)
    network = _network(runtime)

    first = cast(ConnectionRuntimeStepResult, network.step(macro_step_time_s=1.0))
    assert first.graph_revision == "graph_rev_0001"
    assert first.simulation_time_s == pytest.approx(1.0)
    assert first.barrier_reconfiguration.applied_request_ids == ()
    assert "purge_sink" not in network._boundary_specs

    second = cast(ConnectionRuntimeStepResult, network.step(macro_step_time_s=1.0))
    assert second.graph_revision == "graph_rev_0002"
    assert second.simulation_time_s == pytest.approx(2.0)
    assert second.barrier_reconfiguration.applied_request_ids == ("rq_0001",)
    assert second.barrier_reconfiguration.skipped_request_ids == ()
    assert "purge_sink" in network._boundary_specs
    assert tuple(edge.edge_id for edge in network._edges) == ("edge_0001", "edge_0002", "edge_0003")


def test_mutation_queued_before_and_during_macro_step_commits_at_separate_barriers() -> None:
    queued_during_hook: list[str] = []

    def macro_step_hook(
        network: ConnectionNetwork, macro_step_index: int, simulation_time_s: float
    ) -> None:
        del simulation_time_s
        if macro_step_index != 1:
            return
        queued_during_hook.append(
            network.queue_reconfiguration(
                {
                    "operation": "add_boundary_sink",
                    "boundary_id": "sink_during",
                }
            )
        )

    runtime = ConnectionRuntimeOrchestrator(macro_step_hook=macro_step_hook)
    network = _network(runtime)
    queued_before_step = network.queue_reconfiguration(
        {
            "operation": "add_boundary_sink",
            "boundary_id": "sink_before",
        }
    )
    assert queued_before_step == "rq_0001"

    first = cast(ConnectionRuntimeStepResult, network.step(macro_step_time_s=1.0))
    assert queued_during_hook == ["rq_0002"]
    assert first.graph_revision == "graph_rev_0002"
    assert first.barrier_reconfiguration.applied_request_ids == ("rq_0001",)
    assert first.barrier_reconfiguration.skipped_request_ids == ()
    assert "sink_before" in network._boundary_specs
    assert "sink_during" not in network._boundary_specs
    assert tuple(item.request_id for item in network.queued_reconfigurations) == ("rq_0002",)

    second = cast(ConnectionRuntimeStepResult, network.step(macro_step_time_s=1.0))
    assert second.graph_revision == "graph_rev_0003"
    assert second.barrier_reconfiguration.applied_request_ids == ("rq_0002",)
    assert second.barrier_reconfiguration.skipped_request_ids == ()
    assert "sink_during" in network._boundary_specs
    assert network.queued_reconfigurations == ()


def test_invalid_mutation_batch_rolls_back_graph_runtime_and_time() -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)

    _ = network.queue_reconfiguration(
        {
            "operation": "batch_update",
            "mutations": [
                {
                    "operation": "add_connection",
                    "source": "unknown_source",
                    "target": "reactor.feed",
                }
            ],
        }
    )
    before_failed_commit = network.save_runtime_snapshot()

    with pytest.raises(
        RuntimeError,
        match=(
            "reconfiguration transaction rollback: request 'rq_0001' mutation 1 failed: "
            "unknown endpoint node 'unknown_source'"
        ),
    ):
        _ = network.step(macro_step_time_s=1.0)

    after_failed_commit = network.save_runtime_snapshot()
    assert after_failed_commit == before_failed_commit
    assert network._compiled is not None
    assert network._compiled.graph_revision == "graph_rev_0001"
    assert network._next_revision_index == 2


def test_invalid_scope_operation_is_rejected_with_transaction_rollback() -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)

    _ = network.queue_reconfiguration(
        {
            "operation": "install_subsystem_sensor",
            "scope": "subsystem",
            "descriptor_id": "reactor_a",
        }
    )
    queued_snapshot = network.save_runtime_snapshot()

    with pytest.raises(
        RuntimeError,
        match=(
            "reconfiguration transaction rollback: request 'rq_0001' mutation 1 failed: "
            "unsupported reconfiguration operation 'install_subsystem_sensor'"
        ),
    ):
        _ = network.step(macro_step_time_s=1.0)

    assert network.save_runtime_snapshot() == queued_snapshot
    assert tuple(item.request_id for item in network.queued_reconfigurations) == ("rq_0001",)


def test_unresolved_cross_subsystem_reference_rolls_back_without_state_drift() -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)

    _ = network.queue_reconfiguration(
        {
            "operation": "add_connection",
            "source": "subsystem_a/reactor.product",
            "target": "reactor.feed",
        }
    )
    queued_snapshot = network.save_runtime_snapshot()

    with pytest.raises(
        RuntimeError,
        match=(
            "reconfiguration transaction rollback: request 'rq_0001' mutation 1 failed: "
            "unknown endpoint node 'subsystem_a/reactor'"
        ),
    ):
        _ = network.step(macro_step_time_s=1.0)

    assert network.save_runtime_snapshot() == queued_snapshot
    assert tuple(item.request_id for item in network.queued_reconfigurations) == ("rq_0001",)


def test_reconfiguration_batch_is_deterministic_and_idempotent_by_key() -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)

    rq1 = network.queue_reconfiguration(
        {
            "operation": "add_boundary_sink",
            "boundary_id": "sink_a",
            "idempotency_key": "sink-a-key",
        }
    )
    rq2 = network.queue_reconfiguration(
        {
            "operation": "add_boundary_sink",
            "boundary_id": "sink_a",
            "idempotency_key": "sink-a-key",
        }
    )
    rq3 = network.queue_reconfiguration(
        {
            "operation": "batch_update",
            "mutations": [
                {
                    "operation": "add_process_port",
                    "process_id": "reactor",
                    "direction": "inlet",
                    "port_name": "recycle",
                },
                {
                    "operation": "add_process_port",
                    "process_id": "reactor",
                    "direction": "outlet",
                    "port_name": "purge",
                },
                {
                    "operation": "add_connection",
                    "source": "reactor.purge",
                    "target": "sink_a",
                },
            ],
        }
    )

    assert (rq1, rq2, rq3) == ("rq_0001", "rq_0002", "rq_0003")

    result = cast(ConnectionRuntimeStepResult, network.step(macro_step_time_s=0.5))
    assert result.graph_revision == "graph_rev_0002"
    assert result.barrier_reconfiguration.applied_request_ids == ("rq_0001", "rq_0003")
    assert result.barrier_reconfiguration.skipped_request_ids == ("rq_0002",)
    assert network._process_specs["reactor"].inlet_ports == ("feed", "recycle")
    assert network._process_specs["reactor"].outlet_ports == ("product", "purge")
    assert tuple(edge.edge_id for edge in network._edges) == ("edge_0001", "edge_0002", "edge_0003")

    replay = network.queue_reconfiguration(
        {
            "operation": "add_boundary_sink",
            "boundary_id": "sink_b",
            "idempotency_key": "sink-a-key",
        }
    )
    assert replay == "rq_0004"

    with pytest.raises(
        RuntimeError,
        match=(
            "reconfiguration transaction rollback: request 'rq_0004' reuses "
            "idempotency_key 'sink-a-key' with different payload"
        ),
    ):
        _ = network.step(macro_step_time_s=0.5)

    assert "sink_b" not in network._boundary_specs


def test_poison_request_at_queue_head_strictly_blocks_following_requests() -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)

    _ = network.queue_reconfiguration(
        {
            "operation": "batch_update",
            "mutations": [
                {
                    "operation": "add_connection",
                    "source": "unknown_source",
                    "target": "reactor.feed",
                }
            ],
        }
    )
    _ = network.queue_reconfiguration(
        {
            "operation": "add_boundary_sink",
            "boundary_id": "sink_later",
        }
    )
    queued_snapshot = network.save_runtime_snapshot()

    with pytest.raises(
        RuntimeError,
        match=(
            "reconfiguration transaction rollback: request 'rq_0001' mutation 1 failed: "
            "unknown endpoint node 'unknown_source'"
        ),
    ):
        _ = network.step(macro_step_time_s=1.0)

    with pytest.raises(
        RuntimeError,
        match=(
            "reconfiguration transaction rollback: request 'rq_0001' mutation 1 failed: "
            "unknown endpoint node 'unknown_source'"
        ),
    ):
        _ = network.step(macro_step_time_s=1.0)

    assert "sink_later" not in network._boundary_specs
    assert tuple(item.request_id for item in network._queued_reconfigurations) == (
        "rq_0001",
        "rq_0002",
    )
    assert network.save_runtime_snapshot() == queued_snapshot

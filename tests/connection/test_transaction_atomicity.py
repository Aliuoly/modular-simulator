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


def test_expected_revision_mismatch_rejects_before_mutation_and_rolls_back() -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)

    _ = network.queue_reconfiguration(
        {
            "operation": "add_boundary_sink",
            "boundary_id": "purge_sink",
            "expected_revision": "graph_rev_0999",
        }
    )
    queued_snapshot = network.save_runtime_snapshot()

    with pytest.raises(
        RuntimeError,
        match=(
            "reconfiguration transaction rollback: request 'rq_0001' expected_revision "
            "'graph_rev_0999' does not match active graph revision 'graph_rev_0001'"
        ),
    ):
        _ = network.step(macro_step_time_s=1.0)

    assert "purge_sink" not in _compiled_boundary_ids(network)
    assert _compiled_edge_ids(network) == ("edge_0001", "edge_0002")
    assert tuple(item.request_id for item in network.queued_reconfigurations) == ("rq_0001",)
    assert network.save_runtime_snapshot() == queued_snapshot


def test_expected_revision_match_allows_atomic_batch_commit() -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)

    _ = network.queue_reconfiguration(
        {
            "operation": "batch_update",
            "expected_revision": "graph_rev_0001",
            "mutations": [
                {"operation": "add_boundary_sink", "boundary_id": "purge_sink"},
                {
                    "operation": "add_connection",
                    "source": "reactor.product",
                    "target": "purge_sink",
                },
            ],
        }
    )

    result = cast(ConnectionRuntimeStepResult, network.step(macro_step_time_s=1.0))
    assert result.barrier_reconfiguration.applied_request_ids == ("rq_0001",)
    assert result.barrier_reconfiguration.skipped_request_ids == ()
    assert result.graph_revision == "graph_rev_0002"
    assert "purge_sink" in _compiled_boundary_ids(network)
    assert _compiled_edge_ids(network) == ("edge_0001", "edge_0002", "edge_0003")


def test_mixed_topology_and_control_mutations_fail_atomically() -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)

    _ = network.queue_reconfiguration(
        {
            "operation": "batch_update",
            "mutations": [
                {"operation": "add_boundary_sink", "boundary_id": "purge_sink"},
                {
                    "operation": "add_connection",
                    "source": "reactor.product",
                    "target": "purge_sink",
                },
                {
                    "operation": "install_subsystem_sensor",
                    "scope": "subsystem",
                    "descriptor_id": "reactor_a",
                },
            ],
        }
    )
    queued_snapshot = network.save_runtime_snapshot()

    with pytest.raises(
        RuntimeError,
        match=(
            "reconfiguration transaction rollback: request 'rq_0001' mutation 3 failed: "
            "unsupported reconfiguration operation 'install_subsystem_sensor'"
        ),
    ):
        _ = network.step(macro_step_time_s=1.0)

    assert "purge_sink" not in _compiled_boundary_ids(network)
    assert _compiled_edge_ids(network) == ("edge_0001", "edge_0002")
    assert tuple(item.request_id for item in network.queued_reconfigurations) == ("rq_0001",)
    assert network.save_runtime_snapshot() == queued_snapshot

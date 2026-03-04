from __future__ import annotations

from copy import deepcopy
from typing import cast

import pytest

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
from modular_simulation.connection.runtime_persistence import (
    restore_runtime_snapshot_contract,
    save_runtime_snapshot_contract,
)
from modular_simulation.framework.system import (
    CHECKPOINT_VERSION_MISMATCH_ERROR_CODE,
    checkpoint_payload_checksum,
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
    network.connect("feed_boundary", "reactor.feed")
    network.connect("reactor.product", "product_boundary")
    _ = network.compile()
    return network


def test_same_version_checkpoint_resume_restores_pending_queue_state() -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)
    process_runtime_state: dict[str, object] = {"reactor": {"temperature": 345.0}}

    queued_request = network.queue_reconfiguration(
        {
            "operation": "add_boundary_sink",
            "boundary_id": "purge_sink",
            "idempotency_key": "purge-sink-key",
        }
    )
    assert queued_request == "rq_0001"

    snapshot = save_runtime_snapshot_contract(
        runtime=runtime,
        network=network,
        process_runtime_state=process_runtime_state,
    )
    assert snapshot["graph_revision"] == "graph_rev_0001"
    assert snapshot["integrity_checksum"]
    pending_journal = cast(list[dict[str, object]], snapshot["pending_command_journal"])
    assert [entry["request_id"] for entry in pending_journal] == ["rq_0001"]

    runtime._simulation_time_s = 7.0
    runtime._macro_step_index = 11
    _ = network.queue_reconfiguration(
        {
            "operation": "add_boundary_sink",
            "boundary_id": "temporary_sink",
        }
    )
    process_runtime_state["reactor"] = {"temperature": 300.0}

    restore_runtime_snapshot_contract(
        runtime=runtime,
        network=network,
        process_runtime_state_sink=process_runtime_state,
        snapshot=snapshot,
    )

    restored_queue = tuple(item.request_id for item in network.queued_reconfigurations)
    assert restored_queue == ("rq_0001",)
    result = cast(ConnectionRuntimeStepResult, network.step(macro_step_time_s=0.5))
    assert result.barrier_reconfiguration.applied_request_ids == ("rq_0001",)
    assert "purge_sink" in network._boundary_specs


def test_checkpoint_restore_rejects_mismatched_package_version() -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)
    process_runtime_state: dict[str, object] = {"reactor": {"temperature": 330.0}}
    _ = network.queue_reconfiguration(
        {
            "operation": "add_boundary_sink",
            "boundary_id": "purge_sink",
        }
    )

    snapshot = save_runtime_snapshot_contract(
        runtime=runtime,
        network=network,
        process_runtime_state=process_runtime_state,
    )
    before_restore = save_runtime_snapshot_contract(
        runtime=runtime,
        network=network,
        process_runtime_state=process_runtime_state,
    )

    mismatched_snapshot = cast(dict[str, object], deepcopy(snapshot))
    package_metadata = cast(dict[str, object], mismatched_snapshot["package_metadata"])
    package_metadata["package_version"] = "999.0.0-mismatch"
    checksum_payload = cast(dict[str, object], deepcopy(mismatched_snapshot))
    _ = checksum_payload.pop("integrity_checksum", None)
    mismatched_snapshot["integrity_checksum"] = checkpoint_payload_checksum(checksum_payload)

    with pytest.raises(
        ValueError,
        match=rf"\[{CHECKPOINT_VERSION_MISMATCH_ERROR_CODE}\] incompatible runtime snapshot payload",
    ):
        restore_runtime_snapshot_contract(
            runtime=runtime,
            network=network,
            process_runtime_state_sink=process_runtime_state,
            snapshot=mismatched_snapshot,
        )

    after_restore = save_runtime_snapshot_contract(
        runtime=runtime,
        network=network,
        process_runtime_state=process_runtime_state,
    )
    assert after_restore == before_restore

# pyright: reportMissingImports=false
from __future__ import annotations

from collections.abc import Mapping, Sequence

import pytest

from modular_simulation.connection.domain.error_catalog import (
    COMPATIBILITY_FAILURE_CODE,
    DiagnosticValueError,
)
from modular_simulation.connection.hydraulics.hydraulic_compile import HydraulicCompileLifecycle
from modular_simulation.connection.hydraulics.hydraulic_solver import (
    HydraulicSystemDefinition,
    LinearResidualEquation,
)
from modular_simulation.connection.topology.network import ConnectionNetwork
from modular_simulation.connection.runtime.runtime import ConnectionRuntimeOrchestrator
from modular_simulation.connection.runtime.runtime_persistence import (
    RUNTIME_SNAPSHOT_SCHEMA_VERSION,
    restore_runtime_snapshot_contract,
    runtime_replay_state_hash,
    save_runtime_snapshot_contract,
    validate_runtime_snapshot_contract,
    verify_runtime_replay_hashes,
)
from modular_simulation.framework.system import checkpoint_payload_checksum


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


def _tick_requests(
    *, swap_tick_three_order: bool = False
) -> dict[int, tuple[Mapping[str, object], ...]]:
    tick_one = (
        {
            "operation": "add_boundary_sink",
            "boundary_id": "sink_a",
            "idempotency_key": "sink-a",
        },
    )
    tick_two = (
        {
            "operation": "batch_update",
            "idempotency_key": "wire-sink-a",
            "mutations": [
                {
                    "operation": "add_boundary_sink",
                    "boundary_id": "sink_aux",
                },
                {
                    "operation": "add_connection",
                    "source": "reactor.product",
                    "target": "sink_aux",
                },
            ],
        },
    )
    tick_three_default = (
        {
            "operation": "add_boundary_sink",
            "boundary_id": "sink_b",
            "idempotency_key": "sink-b",
        },
        {
            "operation": "add_boundary_sink",
            "boundary_id": "sink_c",
            "idempotency_key": "sink-c",
        },
    )
    tick_three = (
        (tick_three_default[1], tick_three_default[0])
        if swap_tick_three_order
        else tick_three_default
    )
    return {
        1: tick_one,
        2: tick_two,
        3: tick_three,
    }


def _run_ticks(
    *,
    runtime: ConnectionRuntimeOrchestrator,
    network: ConnectionNetwork,
    process_runtime_state: dict[str, object],
    requests_by_tick: Mapping[int, Sequence[Mapping[str, object]]],
    selected_ticks: Sequence[int],
    start_tick: int,
    end_tick: int,
    hash_sink: dict[int, str],
) -> None:
    selected_tick_set = set(selected_ticks)
    for tick in range(start_tick, end_tick + 1):
        process_runtime_state["reactor"] = {
            "temperature": 340.0 + tick,
            "conversion": float(tick) / 10.0,
        }
        tick_requests = requests_by_tick.get(tick, ())
        for request in tick_requests:
            _ = network.queue_reconfiguration(request)
        if tick in selected_tick_set:
            hash_sink[tick] = runtime_replay_state_hash(
                tick=tick,
                runtime=runtime,
                network=network,
                process_runtime_state=process_runtime_state,
            )
        _ = network.step(macro_step_time_s=0.5)


def _run_baseline_hashes(selected_ticks: Sequence[int]) -> dict[int, str]:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)
    process_runtime_state: dict[str, object] = {
        "reactor": {"temperature": 340.0, "conversion": 0.0}
    }
    hashes: dict[int, str] = {}
    _run_ticks(
        runtime=runtime,
        network=network,
        process_runtime_state=process_runtime_state,
        requests_by_tick=_tick_requests(),
        selected_ticks=selected_ticks,
        start_tick=1,
        end_tick=4,
        hash_sink=hashes,
    )
    return hashes


def _run_checkpoint_resume_hashes(
    *,
    selected_ticks: Sequence[int],
    swap_tick_three_order: bool,
) -> dict[int, str]:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)
    process_runtime_state: dict[str, object] = {
        "reactor": {"temperature": 340.0, "conversion": 0.0}
    }
    hashes: dict[int, str] = {}

    baseline_schedule = _tick_requests()
    _run_ticks(
        runtime=runtime,
        network=network,
        process_runtime_state=process_runtime_state,
        requests_by_tick=baseline_schedule,
        selected_ticks=selected_ticks,
        start_tick=1,
        end_tick=2,
        hash_sink=hashes,
    )

    checkpoint = save_runtime_snapshot_contract(
        runtime=runtime,
        network=network,
        process_runtime_state=process_runtime_state,
    )

    runtime.set_runtime_state(
        simulation_time_s=99.0,
        macro_step_index=77,
        macro_step_active=False,
        committed_idempotency_keys=runtime.committed_idempotency_keys,
    )
    process_runtime_state["reactor"] = {"temperature": -1.0, "conversion": -1.0}
    _ = network.queue_reconfiguration(
        {
            "operation": "add_boundary_sink",
            "boundary_id": "temporary_sink",
        }
    )

    restore_runtime_snapshot_contract(
        runtime=runtime,
        network=network,
        process_runtime_state_sink=process_runtime_state,
        snapshot=checkpoint,
    )

    resumed_schedule = _tick_requests(swap_tick_three_order=swap_tick_three_order)
    _run_ticks(
        runtime=runtime,
        network=network,
        process_runtime_state=process_runtime_state,
        requests_by_tick=resumed_schedule,
        selected_ticks=selected_ticks,
        start_tick=3,
        end_tick=4,
        hash_sink=hashes,
    )
    return hashes


def test_checkpoint_resume_replay_hashes_match_selected_ticks() -> None:
    selected_ticks = (1, 2, 3, 4)
    baseline_hashes = _run_baseline_hashes(selected_ticks)
    resumed_hashes = _run_checkpoint_resume_hashes(
        selected_ticks=selected_ticks,
        swap_tick_three_order=False,
    )

    verify_runtime_replay_hashes(
        baseline_hashes=baseline_hashes,
        replay_hashes=resumed_hashes,
    )


def test_checkpoint_resume_replay_hashes_detect_perturbed_queue_order() -> None:
    selected_ticks = (1, 2, 3, 4)
    baseline_hashes = _run_baseline_hashes(selected_ticks)
    perturbed_hashes = _run_checkpoint_resume_hashes(
        selected_ticks=selected_ticks,
        swap_tick_three_order=True,
    )

    with pytest.raises(
        ValueError,
        match="deterministic replay hash mismatch detected at selected ticks: tick 3:",
    ):
        verify_runtime_replay_hashes(
            baseline_hashes=baseline_hashes,
            replay_hashes=perturbed_hashes,
        )


def test_runtime_snapshot_contract_schema_mismatch_is_rejected() -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)
    process_runtime_state: dict[str, object] = {
        "reactor": {"temperature": 345.0, "conversion": 0.34}
    }

    snapshot = save_runtime_snapshot_contract(
        runtime=runtime,
        network=network,
        process_runtime_state=process_runtime_state,
    )
    legacy_snapshot = dict(snapshot)
    legacy_snapshot["schema_version"] = RUNTIME_SNAPSHOT_SCHEMA_VERSION - 1
    payload_without_checksum = dict(legacy_snapshot)
    payload_without_checksum.pop("integrity_checksum", None)
    legacy_snapshot["integrity_checksum"] = checkpoint_payload_checksum(payload_without_checksum)

    with pytest.raises(DiagnosticValueError) as caught:
        validate_runtime_snapshot_contract(legacy_snapshot)
    assert caught.value.payload["code"] == COMPATIBILITY_FAILURE_CODE
    message = str(caught.value.payload.get("message", ""))
    assert "schema_version" in message

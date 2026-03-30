from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from modular_simulation.connection.kernel_adapter import (
    CandidateKernelAdapter,
    KernelWarmStartResult,
    KernelWarmStartRequest,
)
from modular_simulation.connection.runtime.runtime_snapshot_schema import (
    validate_runtime_checkpoint_envelope,
    validate_live_runtime_snapshot_payload,
)

KernelRestoreReason = Literal["resume", "save_load", "post_edit_recovery"]


class KernelWarmStartFailure(RuntimeError):
    def __init__(self, *, restore_reason: KernelRestoreReason, failure_reason: str) -> None:
        self.restore_reason = restore_reason
        self.failure_reason = failure_reason
        super().__init__(f"kernel warm start failed for {restore_reason}: {failure_reason}")


def restore_kernel_from_snapshot(
    *,
    adapter: CandidateKernelAdapter,
    snapshot: Mapping[str, object],
    restore_reason: KernelRestoreReason,
) -> KernelWarmStartResult:
    validated_snapshot = _validate_snapshot_or_raise(
        snapshot=snapshot,
        restore_reason=restore_reason,
    )
    try:
        result = adapter.warm_start(
            KernelWarmStartRequest(
                accepted_snapshot=validated_snapshot,
                metadata={"restore_reason": restore_reason},
            )
        )
    except KernelWarmStartFailure:
        raise
    except Exception as exc:
        raise KernelWarmStartFailure(
            restore_reason=restore_reason,
            failure_reason=str(exc) or exc.__class__.__name__,
        ) from exc
    if not result.restored:
        raise KernelWarmStartFailure(
            restore_reason=restore_reason,
            failure_reason=result.details or "adapter reported unsafe restore",
        )
    return result


def _validate_snapshot_or_raise(
    *,
    snapshot: Mapping[str, object],
    restore_reason: KernelRestoreReason,
) -> Mapping[str, object]:
    try:
        validated_snapshot = validate_live_runtime_snapshot_payload(snapshot=snapshot)
        return validated_snapshot.model_dump(mode="python", by_alias=True)
    except ValueError:
        pass
    try:
        checkpoint_envelope = validate_runtime_checkpoint_envelope(snapshot=snapshot)
    except ValueError as exc:
        failure_reason = str(exc)
        if "invalid runtime snapshot payload" not in failure_reason:
            failure_reason = f"invalid runtime snapshot payload: {failure_reason}"
        raise KernelWarmStartFailure(
            restore_reason=restore_reason,
            failure_reason=failure_reason,
        ) from exc

    checkpoint_snapshot = checkpoint_envelope.snapshot
    return {
        "schema": "connection_runtime_v1",
        "simulation_time_s": checkpoint_snapshot.runtime.simulation_time_s,
        "macro_step_index": checkpoint_snapshot.runtime.macro_step_index,
        "macro_step_active": checkpoint_snapshot.runtime.macro_step_active,
        "graph_revision": checkpoint_envelope.graph_revision,
        "queued_request_ids": tuple(
            request.request_id
            for request in checkpoint_snapshot.connection_runtime_state.queued_reconfigurations
        ),
        "queued_request_count": len(
            checkpoint_snapshot.connection_runtime_state.queued_reconfigurations
        ),
        "committed_idempotency_keys": checkpoint_snapshot.connection_runtime_state.committed_idempotency_keys,
        "process_runtime_state": dict(checkpoint_snapshot.process_runtime_state),
        "transport_runtime_state": dict(checkpoint_snapshot.transport_runtime_state),
    }


__all__ = [
    "KernelWarmStartFailure",
    "KernelRestoreReason",
    "restore_kernel_from_snapshot",
]

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from .runtime import ConnectionRuntimeOrchestrator
from .runtime_persistence import (
    restore_runtime_snapshot_contract,
    save_runtime_snapshot_contract,
)
from ..topology.network import ConnectionNetwork


class _ProcessRuntimeStateOwner(Protocol):
    def export_process_runtime_state(self) -> Mapping[str, object]: ...

    def restore_process_runtime_state(self, payload: Mapping[str, object]) -> None: ...

    def get_observability_observables(self) -> Mapping[str, Mapping[str, float]]: ...


@dataclass(frozen=True)
class MacroStepRollbackCapsule:
    snapshot: Mapping[str, object]
    accepted_observability: Mapping[str, Mapping[str, float]]


def capture_macro_step_rollback_capsule(
    *,
    runtime: ConnectionRuntimeOrchestrator,
    network: ConnectionNetwork,
    process_runtime_owner: _ProcessRuntimeStateOwner,
    accepted_observability: Mapping[str, Mapping[str, float]],
) -> MacroStepRollbackCapsule:
    return MacroStepRollbackCapsule(
        snapshot=save_runtime_snapshot_contract(
            runtime=runtime,
            network=network,
            process_runtime_state=process_runtime_owner.export_process_runtime_state(),
        ),
        accepted_observability={
            key: dict(values) for key, values in accepted_observability.items()
        },
    )


def restore_macro_step_rollback_capsule(
    *,
    runtime: ConnectionRuntimeOrchestrator,
    network: ConnectionNetwork,
    process_runtime_owner: _ProcessRuntimeStateOwner,
    capsule: MacroStepRollbackCapsule,
) -> Mapping[str, Mapping[str, float]]:
    process_runtime_state: dict[str, object] = {}
    restore_runtime_snapshot_contract(
        runtime=runtime,
        network=network,
        process_runtime_state_sink=process_runtime_state,
        snapshot=capsule.snapshot,
    )
    process_runtime_owner.restore_process_runtime_state(process_runtime_state)
    return {key: dict(values) for key, values in capsule.accepted_observability.items()}


def clone_observability_payload(
    observability: Mapping[str, Mapping[str, float]],
) -> Mapping[str, Mapping[str, float]]:
    return {section: dict(values) for section, values in observability.items()}


__all__ = [
    "MacroStepRollbackCapsule",
    "capture_macro_step_rollback_capsule",
    "clone_observability_payload",
    "restore_macro_step_rollback_capsule",
]

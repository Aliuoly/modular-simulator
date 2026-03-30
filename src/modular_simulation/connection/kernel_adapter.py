from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol, runtime_checkable


class KernelDelayStrategy(StrEnum):
    EXTERNAL_TRANSPORT_HISTORY = "external_transport_history"
    AUGMENTED_STATE = "augmented_state"
    HYBRID = "hybrid"


class KernelOptionalCapability(StrEnum):
    STATE_VECTOR = "state_vector"
    RESIDUAL = "residual"
    JACOBIAN = "jacobian"
    BOUNDS = "bounds"


@dataclass(frozen=True)
class KernelDelaySemantics:
    strategy: KernelDelayStrategy
    state_schema: str
    preserves_existing_transport_history: bool
    notes: str | None = None


@dataclass(frozen=True)
class KernelAdapterTelemetry:
    macro_step_index: int
    macro_step_time_s: float
    simulation_time_s: float
    graph_revision: str | None
    executed_sequence: tuple[str, ...]
    transport_fallback_keys: tuple[str, ...]
    junction_fallback_keys: tuple[str, ...]
    used_fallback: bool
    picard_iterations_used: int = 0
    picard_converged: bool = True
    picard_last_residual: float | None = None
    barrier_queue_size_before: int = 0
    barrier_queue_size_after: int = 0
    applied_request_ids: tuple[str, ...] = ()
    skipped_request_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class KernelInitializationRequest:
    accepted_snapshot: Mapping[str, object] | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class KernelInitializationResult:
    initialized: bool
    graph_revision: str | None
    details: str | None = None


@dataclass(frozen=True)
class KernelWarmStartRequest:
    accepted_snapshot: Mapping[str, object]
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class KernelWarmStartResult:
    restored: bool
    graph_revision: str | None
    details: str | None = None


@dataclass(frozen=True)
class KernelCandidateStepRequest:
    macro_step_time_s: float
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class KernelCandidateStepResult:
    accepted: bool
    graph_revision: str | None
    telemetry: KernelAdapterTelemetry
    details: str | None = None


@runtime_checkable
class SupportsStateVectorExport(Protocol):
    def export_state_vector(self) -> Sequence[float]: ...


@runtime_checkable
class SupportsResidualEvaluation(Protocol):
    def evaluate_residual(self, *, state_vector: Sequence[float]) -> Sequence[float]: ...


@runtime_checkable
class SupportsJacobianAccess(Protocol):
    def evaluate_jacobian(self, *, state_vector: Sequence[float]) -> object: ...


@runtime_checkable
class SupportsBoundsAccess(Protocol):
    def get_bounds(self) -> tuple[Sequence[float | None], Sequence[float | None]]: ...


@runtime_checkable
class CandidateKernelAdapter(Protocol):
    @property
    def delay_semantics(self) -> KernelDelaySemantics: ...

    @property
    def telemetry(self) -> KernelAdapterTelemetry: ...

    def initialize(self, request: KernelInitializationRequest) -> KernelInitializationResult: ...

    def warm_start(self, request: KernelWarmStartRequest) -> KernelWarmStartResult: ...

    def evaluate_candidate_step(
        self, request: KernelCandidateStepRequest
    ) -> KernelCandidateStepResult: ...

    def capture_delay_state(self) -> Mapping[str, object]: ...

    def restore_delay_state(self, payload: Mapping[str, object]) -> None: ...

    def supported_optional_capabilities(self) -> frozenset[KernelOptionalCapability]: ...


__all__ = [
    "CandidateKernelAdapter",
    "KernelAdapterTelemetry",
    "KernelCandidateStepRequest",
    "KernelCandidateStepResult",
    "KernelDelaySemantics",
    "KernelDelayStrategy",
    "KernelInitializationRequest",
    "KernelInitializationResult",
    "KernelOptionalCapability",
    "KernelWarmStartRequest",
    "KernelWarmStartResult",
    "SupportsBoundsAccess",
    "SupportsJacobianAccess",
    "SupportsResidualEvaluation",
    "SupportsStateVectorExport",
]

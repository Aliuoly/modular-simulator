from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

from modular_simulation.connection.kernel_adapter import (
    CandidateKernelAdapter,
    KernelAdapterTelemetry,
    KernelCandidateStepRequest,
    KernelCandidateStepResult,
    KernelDelaySemantics,
    KernelDelayStrategy,
    KernelInitializationRequest,
    KernelInitializationResult,
    KernelOptionalCapability,
    KernelWarmStartRequest,
    KernelWarmStartResult,
)
from modular_simulation.connection.runtime.runtime import (
    ConnectionRuntimeOrchestrator,
    ConnectionRuntimeStepResult,
)
from modular_simulation.connection.topology.network import ConnectionNetwork


class ProcessRuntimeStateOwner(Protocol):
    def export_process_runtime_state(self) -> Mapping[str, object]: ...

    def restore_process_runtime_state(self, payload: Mapping[str, object]) -> None: ...


def _default_delay_semantics() -> KernelDelaySemantics:
    return KernelDelaySemantics(
        strategy=KernelDelayStrategy("external_transport_history"),
        state_schema="transport_runtime_state",
        preserves_existing_transport_history=True,
        notes="Split runtime preserves delay state as external transport history.",
    )


def _bootstrap_telemetry() -> KernelAdapterTelemetry:
    return KernelAdapterTelemetry(
        macro_step_index=0,
        macro_step_time_s=0.0,
        simulation_time_s=0.0,
        graph_revision=None,
        executed_sequence=(),
        transport_fallback_keys=(),
        junction_fallback_keys=(),
        used_fallback=False,
        picard_iterations_used=0,
        picard_converged=True,
        picard_last_residual=None,
        barrier_queue_size_before=0,
        barrier_queue_size_after=0,
        applied_request_ids=(),
        skipped_request_ids=(),
    )


@dataclass
class SplitKernelAdapter:
    network: ConnectionNetwork
    runtime_orchestrator: ConnectionRuntimeOrchestrator
    process_runtime_owner: ProcessRuntimeStateOwner | None = None
    delay_semantics: KernelDelaySemantics = field(default_factory=_default_delay_semantics)
    telemetry: KernelAdapterTelemetry = field(default_factory=_bootstrap_telemetry)

    def __post_init__(self) -> None:
        if self.process_runtime_owner is not None:
            self.runtime_orchestrator.set_observability_provider(self.process_runtime_owner)

    def initialize(self, request: KernelInitializationRequest) -> KernelInitializationResult:
        if self.network.compiled is None:
            compiled = self.network.compile()
        else:
            compiled = self.network.compiled
        if request.accepted_snapshot is not None:
            self.network.restore_validated_runtime_snapshot(snapshot=request.accepted_snapshot)
        return KernelInitializationResult(
            initialized=True,
            graph_revision=None if compiled is None else compiled.graph_revision,
        )

    def warm_start(self, request: KernelWarmStartRequest) -> KernelWarmStartResult:
        self.network.restore_validated_runtime_snapshot(snapshot=request.accepted_snapshot)
        compiled = self.network.compiled
        return KernelWarmStartResult(
            restored=True,
            graph_revision=None if compiled is None else compiled.graph_revision,
        )

    def evaluate_candidate_step(
        self, request: KernelCandidateStepRequest
    ) -> KernelCandidateStepResult:
        runtime_result = self.runtime_orchestrator.step(
            network=self.network,
            macro_step_time_s=request.macro_step_time_s,
        )
        self.telemetry = self._build_telemetry(runtime_result)
        return KernelCandidateStepResult(
            accepted=True,
            graph_revision=runtime_result.graph_revision,
            telemetry=self.telemetry,
        )

    def capture_delay_state(self) -> Mapping[str, object]:
        return self.runtime_orchestrator.export_transport_runtime_state()

    def restore_delay_state(self, payload: Mapping[str, object]) -> None:
        self.runtime_orchestrator.restore_transport_runtime_state(payload)

    def supported_optional_capabilities(self) -> frozenset[KernelOptionalCapability]:
        return frozenset()

    def capture_process_runtime_state(self) -> Mapping[str, object]:
        if self.process_runtime_owner is None:
            return {}
        return self.process_runtime_owner.export_process_runtime_state()

    def restore_process_runtime_state(self, payload: Mapping[str, object]) -> None:
        if self.process_runtime_owner is None:
            return
        self.process_runtime_owner.restore_process_runtime_state(payload)

    def _build_telemetry(
        self, runtime_result: ConnectionRuntimeStepResult
    ) -> KernelAdapterTelemetry:
        bookkeeping = runtime_result.bookkeeping
        barrier = runtime_result.barrier_reconfiguration
        return KernelAdapterTelemetry(
            macro_step_index=runtime_result.macro_step_index,
            macro_step_time_s=runtime_result.macro_step_time_s,
            simulation_time_s=runtime_result.simulation_time_s,
            graph_revision=runtime_result.graph_revision,
            executed_sequence=bookkeeping.executed_sequence,
            transport_fallback_keys=bookkeeping.transport_fallback_keys,
            junction_fallback_keys=bookkeeping.junction_fallback_keys,
            used_fallback=bookkeeping.used_fallback,
            picard_iterations_used=bookkeeping.picard_iterations_used,
            picard_converged=bookkeeping.picard_converged,
            picard_last_residual=bookkeeping.picard_last_residual,
            barrier_queue_size_before=barrier.queue_size_before,
            barrier_queue_size_after=barrier.queue_size_after,
            applied_request_ids=barrier.applied_request_ids,
            skipped_request_ids=barrier.skipped_request_ids,
        )


__all__ = ["SplitKernelAdapter"]

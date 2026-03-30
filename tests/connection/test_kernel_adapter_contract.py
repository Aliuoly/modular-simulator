from __future__ import annotations

from dataclasses import dataclass

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
    SupportsBoundsAccess,
    SupportsJacobianAccess,
    SupportsResidualEvaluation,
    SupportsStateVectorExport,
)


@dataclass
class _CoreOnlyAdapter:
    delay_semantics: KernelDelaySemantics
    telemetry: KernelAdapterTelemetry

    def initialize(self, request: KernelInitializationRequest) -> KernelInitializationResult:
        del request
        return KernelInitializationResult(initialized=True, graph_revision="graph_rev_core")

    def warm_start(self, request: KernelWarmStartRequest) -> KernelWarmStartResult:
        del request
        return KernelWarmStartResult(restored=True, graph_revision="graph_rev_core")

    def evaluate_candidate_step(
        self, request: KernelCandidateStepRequest
    ) -> KernelCandidateStepResult:
        del request
        return KernelCandidateStepResult(
            accepted=True,
            graph_revision="graph_rev_core",
            telemetry=self.telemetry,
        )

    def capture_delay_state(self) -> dict[str, object]:
        return {"transport_runtime_state": {}}

    def restore_delay_state(self, payload: dict[str, object]) -> None:
        del payload

    def supported_optional_capabilities(self) -> frozenset[KernelOptionalCapability]:
        return frozenset()


@dataclass
class _ResidualCapableAdapter(_CoreOnlyAdapter):
    def evaluate_residual(self, *, state_vector: tuple[float, ...]) -> tuple[float, ...]:
        return state_vector


def _telemetry() -> KernelAdapterTelemetry:
    return KernelAdapterTelemetry(
        macro_step_index=1,
        macro_step_time_s=0.5,
        simulation_time_s=0.5,
        graph_revision="graph_rev_0001",
        executed_sequence=("hydraulics_solve", "transport_update", "boundary_state_propagation"),
        transport_fallback_keys=("edge_a",),
        junction_fallback_keys=(),
        used_fallback=True,
        picard_iterations_used=2,
        picard_converged=True,
        picard_last_residual=1.0e-6,
        barrier_queue_size_before=1,
        barrier_queue_size_after=0,
        applied_request_ids=("rq_0001",),
        skipped_request_ids=(),
    )


def _delay_semantics() -> KernelDelaySemantics:
    return KernelDelaySemantics(
        strategy=KernelDelayStrategy.EXTERNAL_TRANSPORT_HISTORY,
        state_schema="transport_runtime_state",
        preserves_existing_transport_history=True,
        notes="Split runtime keeps transport history outside the solver state vector.",
    )


def test_core_adapter_protocol_allows_candidate_without_solver_capabilities() -> None:
    adapter = _CoreOnlyAdapter(delay_semantics=_delay_semantics(), telemetry=_telemetry())

    assert isinstance(adapter, CandidateKernelAdapter)
    assert adapter.supported_optional_capabilities() == frozenset()
    assert not isinstance(adapter, SupportsStateVectorExport)
    assert not isinstance(adapter, SupportsResidualEvaluation)
    assert not isinstance(adapter, SupportsJacobianAccess)
    assert not isinstance(adapter, SupportsBoundsAccess)


def test_solver_capabilities_are_independent_optional_protocols() -> None:
    adapter = _ResidualCapableAdapter(delay_semantics=_delay_semantics(), telemetry=_telemetry())

    assert isinstance(adapter, CandidateKernelAdapter)
    assert isinstance(adapter, SupportsResidualEvaluation)
    assert not isinstance(adapter, SupportsStateVectorExport)
    assert not isinstance(adapter, SupportsJacobianAccess)
    assert not isinstance(adapter, SupportsBoundsAccess)
    assert KernelOptionalCapability.STATE_VECTOR.value == "state_vector"
    assert KernelOptionalCapability.RESIDUAL.value == "residual"
    assert KernelOptionalCapability.JACOBIAN.value == "jacobian"
    assert KernelOptionalCapability.BOUNDS.value == "bounds"


def test_core_adapter_contract_requires_delay_semantics_and_comparable_telemetry() -> None:
    adapter = _CoreOnlyAdapter(delay_semantics=_delay_semantics(), telemetry=_telemetry())

    assert adapter.delay_semantics.strategy.value == "external_transport_history"
    assert adapter.delay_semantics.preserves_existing_transport_history is True
    assert adapter.telemetry.executed_sequence == (
        "hydraulics_solve",
        "transport_update",
        "boundary_state_propagation",
    )
    assert adapter.telemetry.transport_fallback_keys == ("edge_a",)
    assert adapter.telemetry.applied_request_ids == ("rq_0001",)

"""Thin wrapper around the reusable Phase 3 benchmark harness."""

from __future__ import annotations

from types import SimpleNamespace

from modular_simulation.connection.benchmarking import (
    BenchmarkHarness,
    BenchmarkLatencyBudget,
    benchmark_attempt_records_to_dicts,
    build_phase3_workloads,
)
from modular_simulation.connection.kernel_adapter import (
    KernelAdapterTelemetry,
    KernelCandidateStepRequest,
    KernelCandidateStepResult,
)


def run_benchmark() -> dict[str, object]:
    workloads = build_phase3_workloads()
    attempt_records = []
    for workload in workloads:
        candidate_config = _candidate_config_for_workload(workload)
        attempt_records.extend(
            BenchmarkHarness(
                workload_definition=workload,
                candidate_config=candidate_config,
                candidate_adapter_factory=lambda seed: _DisciplinedSplitBaseline(
                    seed.session.network
                ),
                latency_budget=BenchmarkLatencyBudget(),
            ).run()
        )

    return {
        "candidate_id": "disciplined_split",
        "workload_count": len(workloads),
        "attempt_record_count": len(attempt_records),
        "attempt_records": benchmark_attempt_records_to_dicts(attempt_records),
    }


class _DisciplinedSplitBaseline:
    def __init__(self, network: object) -> None:
        self.network = network
        self.runtime_orchestrator = SimpleNamespace(macro_step_index=0)
        self.telemetry = KernelAdapterTelemetry(
            macro_step_index=0,
            macro_step_time_s=0.0,
            simulation_time_s=0.0,
            graph_revision="graph_0",
            executed_sequence=(),
            transport_fallback_keys=(),
            junction_fallback_keys=(),
            used_fallback=False,
        )

    def initialize(self, request):
        return SimpleNamespace(initialized=True, graph_revision="graph_0")

    def evaluate_candidate_step(
        self, request: KernelCandidateStepRequest
    ) -> KernelCandidateStepResult:
        next_index = self.telemetry.macro_step_index + 1
        self.runtime_orchestrator.macro_step_index = next_index
        self.telemetry = KernelAdapterTelemetry(
            macro_step_index=next_index,
            macro_step_time_s=request.macro_step_time_s,
            simulation_time_s=next_index * request.macro_step_time_s,
            graph_revision=f"graph_{next_index}",
            executed_sequence=("split_baseline_step",),
            transport_fallback_keys=(),
            junction_fallback_keys=(),
            used_fallback=False,
        )
        return KernelCandidateStepResult(
            accepted=True,
            graph_revision=self.telemetry.graph_revision,
            telemetry=self.telemetry,
            details="baseline accepted",
        )

    def capture_process_runtime_state(self) -> dict[str, object]:
        return {}


def _candidate_config_for_workload(workload):
    from modular_simulation.connection.benchmarking.contracts import BenchmarkCandidateConfig

    return BenchmarkCandidateConfig(
        candidate_id="disciplined_split",
        candidate_label="Disciplined split baseline",
        checkpoint_id=workload.checkpoint_id,
        tolerance_profile=workload.tolerance_profile,
        physical_acceptance_profile=workload.physical_acceptance_profile,
        telemetry_contract_version=workload.telemetry_contract_version,
        delay_semantics_label=workload.delay_semantics_label,
        candidate_family="split",
    )


__all__ = ["run_benchmark"]

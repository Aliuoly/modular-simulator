"""Thin wrapper around the reusable Phase 3 benchmark harness."""

from __future__ import annotations

from modular_simulation.connection.benchmarking import (
    BenchmarkHarness,
    BenchmarkLatencyBudget,
    benchmark_workload_coverage_matrix,
    build_phase3_report,
    build_phase3_workloads,
)


def run_benchmark() -> dict[str, object]:
    workloads = build_phase3_workloads()
    latency_budget = BenchmarkLatencyBudget()
    candidate_id = "disciplined_split"
    candidate_config = _candidate_config_for_workloads(workloads, candidate_id=candidate_id)
    attempt_records = []
    for workload in workloads:
        attempt_records.extend(
            BenchmarkHarness(
                workload_definition=workload,
                candidate_config=candidate_config[workload.workload_id],
                candidate_adapter_factory=lambda seed: seed.session.network._build_kernel_adapter(),
                latency_budget=latency_budget,
            ).run()
        )

    return build_phase3_report(
        candidate_attempt_records={candidate_id: tuple(attempt_records)},
        candidate_configs={candidate_id: candidate_config[workloads[0].workload_id]},
        coverage_matrix=benchmark_workload_coverage_matrix(),
        latency_budget=latency_budget,
    )


def _candidate_config_for_workloads(workloads, *, candidate_id: str):
    from modular_simulation.connection.benchmarking.contracts import BenchmarkCandidateConfig

    return {
        workload.workload_id: BenchmarkCandidateConfig(
            candidate_id=candidate_id,
            candidate_label="Disciplined split baseline",
            checkpoint_id=workload.checkpoint_id,
            tolerance_profile=workload.tolerance_profile,
            physical_acceptance_profile=workload.physical_acceptance_profile,
            telemetry_contract_version=workload.telemetry_contract_version,
            delay_semantics_label=workload.delay_semantics_label,
            candidate_family="split",
        )
        for workload in workloads
    }


__all__ = ["run_benchmark"]

"""Thin wrapper around the reusable Phase 3 benchmark harness."""

from __future__ import annotations

from modular_simulation.connection.benchmarking import (
    BenchmarkHarness,
    BenchmarkCandidateConfig,
    BenchmarkLatencyBudget,
    benchmark_workload_coverage_matrix,
    build_phase3_report,
    build_phase3_workloads,
    build_phase5_candidate_configs,
)


def run_benchmark() -> dict[str, object]:
    workloads = build_phase3_workloads()
    latency_budget = BenchmarkLatencyBudget()
    candidate_configs = _candidate_configs_by_candidate(workloads)
    candidate_factories = {
        "disciplined_split": lambda seed: seed.session.network._build_kernel_adapter(),
    }

    candidate_attempt_records: dict[str, tuple[object, ...]] = {}
    for candidate_id, workload_configs in candidate_configs.items():
        attempt_records = []
        for workload in workloads:
            attempt_records.extend(
                BenchmarkHarness(
                    workload_definition=workload,
                    candidate_config=workload_configs[workload.workload_id],
                    candidate_adapter_factory=candidate_factories[candidate_id],
                    latency_budget=latency_budget,
                ).run()
            )
        candidate_attempt_records[candidate_id] = tuple(attempt_records)

    return build_phase3_report(
        candidate_attempt_records=candidate_attempt_records,
        candidate_configs={
            candidate_id: next(iter(workload_configs.values()))
            for candidate_id, workload_configs in candidate_configs.items()
        },
        coverage_matrix=benchmark_workload_coverage_matrix(),
        latency_budget=latency_budget,
    )


def _candidate_configs_by_candidate(
    workloads,
) -> dict[str, dict[str, BenchmarkCandidateConfig]]:
    candidate_configs = build_phase5_candidate_configs(workloads)
    grouped: dict[str, dict[str, BenchmarkCandidateConfig]] = {}
    for config in candidate_configs:
        grouped.setdefault(config.candidate_id, {})[config.checkpoint_id] = config
    workload_id_lookup = {workload.checkpoint_id: workload.workload_id for workload in workloads}
    return {
        candidate_id: {
            workload_id_lookup[checkpoint_id]: config
            for checkpoint_id, config in checkpoint_configs.items()
        }
        for candidate_id, checkpoint_configs in grouped.items()
    }


__all__ = ["run_benchmark"]

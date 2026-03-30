from __future__ import annotations

from modular_simulation.connection.benchmarking.contracts import (
    BenchmarkAcceptedLatencySummary,
    BenchmarkAttemptRecord,
    BenchmarkCandidateConfig,
    BenchmarkDisqualificationReason,
    BenchmarkWorkloadDefinition,
)
from modular_simulation.connection.kernel_adapter import KernelCandidateStepResult


def build_benchmark_attempt_record(
    *,
    candidate_step_result: KernelCandidateStepResult,
    wall_clock_elapsed_s: float,
    replay_hash: str,
    workload_definition: BenchmarkWorkloadDefinition,
    candidate_config: BenchmarkCandidateConfig,
    disqualification_reasons: tuple[BenchmarkDisqualificationReason, ...] = (),
) -> BenchmarkAttemptRecord:
    telemetry = candidate_step_result.telemetry
    return BenchmarkAttemptRecord(
        workload_id=workload_definition.workload_id,
        candidate_id=candidate_config.candidate_id,
        checkpoint_id=workload_definition.checkpoint_id,
        tolerance_profile=workload_definition.tolerance_profile,
        physical_acceptance_profile=workload_definition.physical_acceptance_profile,
        telemetry_contract_version=workload_definition.telemetry_contract_version,
        delay_semantics_label=workload_definition.delay_semantics_label,
        attempt_outcome="accepted" if candidate_step_result.accepted else "rejected",
        macro_step_index=telemetry.macro_step_index,
        macro_step_time_s=telemetry.macro_step_time_s,
        simulation_time_s=telemetry.simulation_time_s,
        wall_clock_elapsed_s=wall_clock_elapsed_s,
        replay_hash=replay_hash,
        graph_revision=candidate_step_result.graph_revision,
        transport_fallback_keys=telemetry.transport_fallback_keys,
        junction_fallback_keys=telemetry.junction_fallback_keys,
        used_fallback=telemetry.used_fallback,
        picard_iterations_used=telemetry.picard_iterations_used,
        picard_converged=telemetry.picard_converged,
        picard_last_residual=telemetry.picard_last_residual,
        disqualification_reasons=disqualification_reasons,
        details=candidate_step_result.details,
    )


def summarize_accepted_step_latency(
    attempt_records: tuple[BenchmarkAttemptRecord, ...] | list[BenchmarkAttemptRecord],
) -> BenchmarkAcceptedLatencySummary:
    accepted_latencies = sorted(
        record.wall_clock_elapsed_s
        for record in attempt_records
        if record.attempt_outcome == "accepted"
    )
    rejected_attempt_count = sum(
        1 for record in attempt_records if record.attempt_outcome != "accepted"
    )
    if not accepted_latencies:
        return BenchmarkAcceptedLatencySummary(
            accepted_attempt_count=0,
            rejected_attempt_count=rejected_attempt_count,
            accepted_step_latency_median_s=None,
            accepted_step_latency_p95_s=None,
            accepted_step_latency_p99_s=None,
        )

    return BenchmarkAcceptedLatencySummary(
        accepted_attempt_count=len(accepted_latencies),
        rejected_attempt_count=rejected_attempt_count,
        accepted_step_latency_median_s=_quantile(accepted_latencies, 0.5),
        accepted_step_latency_p95_s=_quantile(accepted_latencies, 0.95),
        accepted_step_latency_p99_s=_quantile(accepted_latencies, 0.99),
    )


def _quantile(sorted_values: list[float], fraction: float) -> float:
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = (len(sorted_values) - 1) * fraction
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(sorted_values) - 1)
    lower_value = sorted_values[lower_index]
    upper_value = sorted_values[upper_index]
    return lower_value + ((upper_value - lower_value) * (position - lower_index))


__all__ = ["build_benchmark_attempt_record", "summarize_accepted_step_latency"]

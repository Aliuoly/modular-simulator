from __future__ import annotations

from modular_simulation.connection.benchmarking.contracts import (
    BenchmarkAttemptRecord,
    BenchmarkCandidateConfig,
    BenchmarkDisqualificationReason,
    BenchmarkLatencyBudget,
)
from modular_simulation.connection.benchmarking.telemetry import (
    summarize_accepted_step_latency,
)


_RANK_BLOCKING_REASONS = frozenset(
    {
        BenchmarkDisqualificationReason.FALLBACK_USED,
        BenchmarkDisqualificationReason.PHYSICAL_ACCEPTANCE_FAILURE,
        BenchmarkDisqualificationReason.HIDDEN_SOLVER_FAILURE,
        BenchmarkDisqualificationReason.CLIPPING_MASKED_APPARENT_STABILITY,
        BenchmarkDisqualificationReason.HIDDEN_RECOVERY,
        BenchmarkDisqualificationReason.TELEMETRY_CONTRACT_VIOLATION,
    }
)


def score_candidate_report(
    *,
    candidate_config: BenchmarkCandidateConfig,
    attempt_records: tuple[BenchmarkAttemptRecord, ...] | list[BenchmarkAttemptRecord],
    latency_budget: BenchmarkLatencyBudget,
) -> dict[str, object]:
    latency_summary = summarize_accepted_step_latency(attempt_records)
    accepted_records = [
        record for record in attempt_records if record.attempt_outcome == "accepted"
    ]
    disqualification_reasons = _collect_disqualification_reasons(attempt_records)
    accepted_step_p95_s = latency_summary.accepted_step_latency_p95_s
    step_size_s = accepted_records[0].macro_step_time_s if accepted_records else None
    accepted_step_p95_fraction_of_step_size = (
        accepted_step_p95_s / step_size_s
        if accepted_step_p95_s is not None and step_size_s not in (None, 0.0)
        else None
    )
    accepted_step_latency_median_s = latency_summary.accepted_step_latency_median_s
    realtime_factor = (
        (step_size_s / accepted_step_latency_median_s)
        if accepted_step_latency_median_s is not None
        and accepted_step_latency_median_s > 0.0
        and step_size_s
        else None
    )
    meets_latency_gate = (
        accepted_step_p95_fraction_of_step_size is not None
        and accepted_step_p95_fraction_of_step_size
        <= latency_budget.accepted_step_p95_fraction_of_step_size
    )
    meets_minimum_rtf_gate = (
        realtime_factor is not None and realtime_factor >= latency_budget.minimum_rtf_gate
    )
    meets_headline_rtf_target = (
        realtime_factor is not None and realtime_factor >= latency_budget.headline_rtf_target
    )
    is_disqualified = bool(disqualification_reasons)
    viable_for_ranking = bool(
        not is_disqualified
        and latency_summary.accepted_attempt_count > 0
        and meets_latency_gate
        and meets_minimum_rtf_gate
    )
    return {
        "candidate_id": candidate_config.candidate_id,
        "candidate_label": candidate_config.candidate_label,
        "candidate_family": candidate_config.candidate_family,
        "checkpoint_id": candidate_config.checkpoint_id,
        "tolerance_profile": candidate_config.tolerance_profile,
        "physical_acceptance_profile": candidate_config.physical_acceptance_profile,
        "telemetry_contract_version": candidate_config.telemetry_contract_version,
        "delay_semantics_label": candidate_config.delay_semantics_label,
        "accepted_attempt_count": latency_summary.accepted_attempt_count,
        "rejected_attempt_count": latency_summary.rejected_attempt_count,
        "accepted_step_latency_median_s": latency_summary.accepted_step_latency_median_s,
        "accepted_step_latency_p95_s": latency_summary.accepted_step_latency_p95_s,
        "accepted_step_latency_p99_s": latency_summary.accepted_step_latency_p99_s,
        "accepted_step_p95_fraction_of_step_size": accepted_step_p95_fraction_of_step_size,
        "latency_budget_fraction": latency_budget.accepted_step_p95_fraction_of_step_size,
        "realtime_factor": realtime_factor,
        "minimum_rtf_gate": latency_budget.minimum_rtf_gate,
        "headline_rtf_target": latency_budget.headline_rtf_target,
        "meets_latency_gate": meets_latency_gate,
        "meets_minimum_rtf_gate": meets_minimum_rtf_gate,
        "meets_headline_rtf_target": meets_headline_rtf_target,
        "is_disqualified": is_disqualified,
        "viable_for_ranking": viable_for_ranking,
        "disqualification_reasons": [reason.value for reason in disqualification_reasons],
    }


def build_phase3_report(
    *,
    candidate_attempt_records: dict[
        str, tuple[BenchmarkAttemptRecord, ...] | list[BenchmarkAttemptRecord]
    ],
    candidate_configs: dict[str, BenchmarkCandidateConfig],
    coverage_matrix: tuple[dict[str, object], ...] | list[dict[str, object]],
    latency_budget: BenchmarkLatencyBudget,
) -> dict[str, object]:
    scored_rows = [
        score_candidate_report(
            candidate_config=candidate_configs[candidate_id],
            attempt_records=attempt_records,
            latency_budget=latency_budget,
        )
        for candidate_id, attempt_records in candidate_attempt_records.items()
    ]
    candidate_rankings = sorted(
        [row for row in scored_rows if row["viable_for_ranking"]],
        key=lambda row: (
            float(row["realtime_factor"] or 0.0),
            -float(row["accepted_step_latency_p95_s"] or float("inf")),
        ),
        reverse=True,
    )
    disqualified_candidates = [row for row in scored_rows if row["is_disqualified"]]
    return {
        "candidate_rankings": candidate_rankings,
        "disqualified_candidates": disqualified_candidates,
        "coverage_matrix": list(coverage_matrix),
        "headline_rtf_target": latency_budget.headline_rtf_target,
        "minimum_rtf_gate": latency_budget.minimum_rtf_gate,
        "latency_budget_fraction": latency_budget.accepted_step_p95_fraction_of_step_size,
    }


def _collect_disqualification_reasons(
    attempt_records: tuple[BenchmarkAttemptRecord, ...] | list[BenchmarkAttemptRecord],
) -> tuple[BenchmarkDisqualificationReason, ...]:
    reasons: list[BenchmarkDisqualificationReason] = []
    for record in attempt_records:
        for reason in record.disqualification_reasons:
            if reason in _RANK_BLOCKING_REASONS and reason not in reasons:
                reasons.append(reason)
        if record.used_fallback and BenchmarkDisqualificationReason.FALLBACK_USED not in reasons:
            reasons.append(BenchmarkDisqualificationReason.FALLBACK_USED)
    return tuple(reasons)


__all__ = ["build_phase3_report", "score_candidate_report"]

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
    representative_record = attempt_records[0] if attempt_records else None
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
        "workload_id": representative_record.workload_id
        if representative_record is not None
        else None,
        "candidate_id": candidate_config.candidate_id,
        "candidate_label": candidate_config.candidate_label,
        "candidate_family": candidate_config.candidate_family,
        "checkpoint_id": (
            representative_record.checkpoint_id
            if representative_record is not None
            else candidate_config.checkpoint_id
        ),
        "tolerance_profile": (
            representative_record.tolerance_profile
            if representative_record is not None
            else candidate_config.tolerance_profile
        ),
        "physical_acceptance_profile": (
            representative_record.physical_acceptance_profile
            if representative_record is not None
            else candidate_config.physical_acceptance_profile
        ),
        "telemetry_contract_version": (
            representative_record.telemetry_contract_version
            if representative_record is not None
            else candidate_config.telemetry_contract_version
        ),
        "delay_semantics_label": (
            representative_record.delay_semantics_label
            if representative_record is not None
            else candidate_config.delay_semantics_label
        ),
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


def score_candidate_workloads(
    *,
    candidate_config: BenchmarkCandidateConfig,
    attempt_records: tuple[BenchmarkAttemptRecord, ...] | list[BenchmarkAttemptRecord],
    latency_budget: BenchmarkLatencyBudget,
) -> tuple[dict[str, object], ...]:
    grouped_records: dict[str, list[BenchmarkAttemptRecord]] = {}
    for record in attempt_records:
        grouped_records.setdefault(record.workload_id, []).append(record)
    return tuple(
        score_candidate_report(
            candidate_config=candidate_config,
            attempt_records=records,
            latency_budget=latency_budget,
        )
        for _, records in sorted(grouped_records.items())
    )


def build_phase3_report(
    *,
    candidate_attempt_records: dict[
        str, tuple[BenchmarkAttemptRecord, ...] | list[BenchmarkAttemptRecord]
    ],
    candidate_configs: dict[str, BenchmarkCandidateConfig],
    coverage_matrix: tuple[dict[str, object], ...] | list[dict[str, object]],
    latency_budget: BenchmarkLatencyBudget,
) -> dict[str, object]:
    scored_rows = []
    for candidate_id, attempt_records in candidate_attempt_records.items():
        workload_rows = score_candidate_workloads(
            candidate_config=candidate_configs[candidate_id],
            attempt_records=attempt_records,
            latency_budget=latency_budget,
        )
        scored_rows.append(
            _build_candidate_aggregate_row(
                candidate_config=candidate_configs[candidate_id],
                workload_rows=workload_rows,
                latency_budget=latency_budget,
            )
        )
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
        "candidate_workloads": {
            row["candidate_id"]: row["workload_reports"] for row in scored_rows
        },
        "coverage_matrix": list(coverage_matrix),
        "headline_rtf_target": latency_budget.headline_rtf_target,
        "minimum_rtf_gate": latency_budget.minimum_rtf_gate,
        "latency_budget_fraction": latency_budget.accepted_step_p95_fraction_of_step_size,
    }


def _build_candidate_aggregate_row(
    *,
    candidate_config: BenchmarkCandidateConfig,
    workload_rows: tuple[dict[str, object], ...],
    latency_budget: BenchmarkLatencyBudget,
) -> dict[str, object]:
    accepted_attempt_count = sum(int(row["accepted_attempt_count"]) for row in workload_rows)
    rejected_attempt_count = sum(int(row["rejected_attempt_count"]) for row in workload_rows)
    disqualification_reasons: list[str] = []
    for row in workload_rows:
        for reason in row["disqualification_reasons"]:
            if reason not in disqualification_reasons:
                disqualification_reasons.append(reason)
    viable_for_ranking = bool(workload_rows) and all(
        bool(row["viable_for_ranking"]) for row in workload_rows
    )
    is_disqualified = any(bool(row["is_disqualified"]) for row in workload_rows)
    realtime_values = [
        float(row["realtime_factor"]) for row in workload_rows if row["realtime_factor"] is not None
    ]
    p95_values = [
        float(row["accepted_step_latency_p95_s"])
        for row in workload_rows
        if row["accepted_step_latency_p95_s"] is not None
    ]
    fraction_values = [
        float(row["accepted_step_p95_fraction_of_step_size"])
        for row in workload_rows
        if row["accepted_step_p95_fraction_of_step_size"] is not None
    ]
    checkpoint_ids = [str(row["checkpoint_id"]) for row in workload_rows if row["checkpoint_id"]]
    workload_ids = [str(row["workload_id"]) for row in workload_rows if row["workload_id"]]
    median_values = [
        float(row["accepted_step_latency_median_s"])
        for row in workload_rows
        if row["accepted_step_latency_median_s"] is not None
    ]
    p99_values = [
        float(row["accepted_step_latency_p99_s"])
        for row in workload_rows
        if row["accepted_step_latency_p99_s"] is not None
    ]
    return {
        "candidate_id": candidate_config.candidate_id,
        "candidate_label": candidate_config.candidate_label,
        "candidate_family": candidate_config.candidate_family,
        "checkpoint_id": checkpoint_ids[0] if len(set(checkpoint_ids)) == 1 else None,
        "checkpoint_ids": checkpoint_ids,
        "workload_ids": workload_ids,
        "tolerance_profile": candidate_config.tolerance_profile,
        "physical_acceptance_profile": candidate_config.physical_acceptance_profile,
        "telemetry_contract_version": candidate_config.telemetry_contract_version,
        "delay_semantics_label": candidate_config.delay_semantics_label,
        "accepted_attempt_count": accepted_attempt_count,
        "rejected_attempt_count": rejected_attempt_count,
        "accepted_step_latency_median_s": max(median_values, default=None),
        "accepted_step_latency_p95_s": max(p95_values, default=None),
        "accepted_step_latency_p99_s": max(p99_values, default=None),
        "accepted_step_p95_fraction_of_step_size": max(fraction_values, default=None),
        "latency_budget_fraction": latency_budget.accepted_step_p95_fraction_of_step_size,
        "realtime_factor": min(realtime_values, default=None),
        "minimum_rtf_gate": latency_budget.minimum_rtf_gate,
        "headline_rtf_target": latency_budget.headline_rtf_target,
        "meets_latency_gate": bool(workload_rows)
        and all(bool(row["meets_latency_gate"]) for row in workload_rows),
        "meets_minimum_rtf_gate": bool(workload_rows)
        and all(bool(row["meets_minimum_rtf_gate"]) for row in workload_rows),
        "meets_headline_rtf_target": bool(workload_rows)
        and all(bool(row["meets_headline_rtf_target"]) for row in workload_rows),
        "is_disqualified": is_disqualified,
        "viable_for_ranking": viable_for_ranking,
        "disqualification_reasons": disqualification_reasons,
        "workload_reports": list(workload_rows),
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


__all__ = ["build_phase3_report", "score_candidate_report", "score_candidate_workloads"]

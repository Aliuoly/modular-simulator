from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ScipyStatus = Literal["sufficient", "solver_limited", "needs_more_evidence"]
RecommendedSolverStack = Literal["scipy"]


@dataclass(frozen=True)
class KernelProfilingSummary:
    solver_core_fraction: float | None


@dataclass(frozen=True)
class KernelDirectionDecision:
    default_kernel_direction: str
    scipy_status: ScipyStatus
    recommended_solver_stack: RecommendedSolverStack
    preserve_existing_facades: bool
    evidence_workload_ids: tuple[str, ...]
    blocking_reasons: tuple[str, ...] = ()
    missing_evidence: tuple[str, ...] = ()
    later_escalation_only: tuple[str, ...] = ()


def build_kernel_direction_decision(
    phase3_report: dict[str, object],
    profiling_summary: KernelProfilingSummary,
) -> KernelDirectionDecision:
    evidence_workload_ids = _extract_evidence_workload_ids(phase3_report)
    disciplined_split_is_viable = _disciplined_split_is_viable(phase3_report)

    if disciplined_split_is_viable:
        return KernelDirectionDecision(
            default_kernel_direction="hybrid_coupled",
            scipy_status="sufficient",
            recommended_solver_stack="scipy",
            preserve_existing_facades=True,
            evidence_workload_ids=evidence_workload_ids,
            blocking_reasons=(),
            missing_evidence=(),
            later_escalation_only=(),
        )

    solver_core_fraction = profiling_summary.solver_core_fraction
    if solver_core_fraction is None:
        return KernelDirectionDecision(
            default_kernel_direction="hybrid_coupled",
            scipy_status="needs_more_evidence",
            recommended_solver_stack="scipy",
            preserve_existing_facades=True,
            evidence_workload_ids=evidence_workload_ids,
            blocking_reasons=_gate_failure_reasons(phase3_report),
            missing_evidence=(
                "solver_core_fraction profiling is required before declaring SciPy solver-limited",
            ),
            later_escalation_only=(),
        )

    if solver_core_fraction >= 0.5:
        return KernelDirectionDecision(
            default_kernel_direction="hybrid_coupled",
            scipy_status="solver_limited",
            recommended_solver_stack="scipy",
            preserve_existing_facades=True,
            evidence_workload_ids=evidence_workload_ids,
            blocking_reasons=_gate_failure_reasons(phase3_report),
            missing_evidence=(
                "external benchmark solver candidates were removed; keep the SciPy path until a new migration target exists",
            ),
            later_escalation_only=(),
        )

    return KernelDirectionDecision(
        default_kernel_direction="hybrid_coupled",
        scipy_status="needs_more_evidence",
        recommended_solver_stack="scipy",
        preserve_existing_facades=True,
        evidence_workload_ids=evidence_workload_ids,
        blocking_reasons=_gate_failure_reasons(phase3_report),
        missing_evidence=(
            "solver_core_fraction remained below the 0.5 solver-dominance threshold",
        ),
        later_escalation_only=(),
    )


def _extract_evidence_workload_ids(phase3_report: dict[str, object]) -> tuple[str, ...]:
    candidate_rankings = phase3_report.get("candidate_rankings")
    if isinstance(candidate_rankings, list):
        for row in candidate_rankings:
            if not isinstance(row, dict):
                continue
            workload_ids = row.get("workload_ids")
            extracted = _coerce_string_tuple(workload_ids)
            if extracted:
                return extracted

    coverage_matrix = phase3_report.get("coverage_matrix")
    if isinstance(coverage_matrix, list):
        extracted = tuple(
            entry["workload_id"]
            for entry in coverage_matrix
            if isinstance(entry, dict) and isinstance(entry.get("workload_id"), str)
        )
        if extracted:
            return extracted

    return ()


def _disciplined_split_is_viable(phase3_report: dict[str, object]) -> bool:
    candidate_rankings = phase3_report.get("candidate_rankings")
    if not isinstance(candidate_rankings, list):
        return False

    for row in candidate_rankings:
        if isinstance(row, dict) and row.get("candidate_id") == "disciplined_split":
            return True
    return False


def _gate_failure_reasons(phase3_report: dict[str, object]) -> tuple[str, ...]:
    minimum_rtf_gate = phase3_report.get("minimum_rtf_gate")
    latency_budget_fraction = phase3_report.get("latency_budget_fraction")
    reasons = [
        f"Disciplined SciPy baseline did not clear minimum_rtf_gate={minimum_rtf_gate}",
        f"Disciplined SciPy baseline did not clear latency_budget_fraction={latency_budget_fraction}",
    ]
    return tuple(reason for reason in reasons if not reason.endswith("=None"))


def _coerce_string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str))


__all__ = [
    "KernelDirectionDecision",
    "KernelProfilingSummary",
    "RecommendedSolverStack",
    "ScipyStatus",
    "build_kernel_direction_decision",
]

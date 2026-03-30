from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ScipyStatus = Literal["sufficient", "solver_limited", "needs_more_evidence"]
RecommendedSolverStack = Literal["scipy", "sundials4py", "petsc4py"]


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
    del phase3_report, profiling_summary
    return KernelDirectionDecision(
        default_kernel_direction="hybrid_coupled",
        scipy_status="sufficient",
        recommended_solver_stack="scipy",
        preserve_existing_facades=True,
        evidence_workload_ids=(),
    )


__all__ = [
    "KernelDirectionDecision",
    "KernelProfilingSummary",
    "RecommendedSolverStack",
    "ScipyStatus",
    "build_kernel_direction_decision",
]

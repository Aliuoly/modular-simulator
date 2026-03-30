from __future__ import annotations

from modular_simulation.connection.benchmarking.decision_gate import (
    KernelProfilingSummary,
    build_kernel_direction_decision,
)


def test_build_kernel_direction_decision_keeps_hybrid_direction_for_viable_scipy() -> None:
    decision = build_kernel_direction_decision(
        _phase3_report(
            candidate_rankings=[
                {
                    "candidate_id": "disciplined_split",
                    "workload_ids": [
                        "ammonia_recycle_warm",
                        "staged_delay_control_disturbance",
                        "checkpoint_restart_reconfigure",
                    ],
                }
            ]
        ),
        KernelProfilingSummary(solver_core_fraction=0.3),
    )

    assert decision.default_kernel_direction == "hybrid_coupled"
    assert decision.scipy_status == "sufficient"
    assert decision.recommended_solver_stack == "scipy"
    assert decision.preserve_existing_facades is True
    assert decision.evidence_workload_ids == (
        "ammonia_recycle_warm",
        "staged_delay_control_disturbance",
        "checkpoint_restart_reconfigure",
    )


def test_build_kernel_direction_decision_marks_solver_limited_only_with_gate_miss_and_solver_dominance() -> (
    None
):
    decision = build_kernel_direction_decision(
        _phase3_report(candidate_rankings=[]),
        KernelProfilingSummary(solver_core_fraction=0.5),
    )

    assert decision.default_kernel_direction == "hybrid_coupled"
    assert decision.scipy_status == "solver_limited"
    assert decision.recommended_solver_stack == "sundials4py"
    assert any("minimum_rtf_gate" in reason for reason in decision.blocking_reasons)


def test_build_kernel_direction_decision_keeps_petsc_as_later_only_escalation() -> None:
    decision = build_kernel_direction_decision(
        _phase3_report(candidate_rankings=[], post_sundials_gap_unresolved=True),
        KernelProfilingSummary(solver_core_fraction=0.7),
    )

    assert decision.scipy_status == "solver_limited"
    assert decision.recommended_solver_stack == "sundials4py"
    assert decision.recommended_solver_stack != "petsc4py"
    assert decision.later_escalation_only == ("petsc4py",)


def test_build_kernel_direction_decision_never_recommends_petsc_as_first_escalation() -> None:
    decision = build_kernel_direction_decision(
        _phase3_report(candidate_rankings=[], direct_petsc_escalation=True),
        KernelProfilingSummary(solver_core_fraction=0.8),
    )

    assert decision.scipy_status == "solver_limited"
    assert decision.recommended_solver_stack == "sundials4py"
    assert decision.recommended_solver_stack != "petsc4py"


def test_build_kernel_direction_decision_needs_more_evidence_without_profiling_signal() -> None:
    decision = build_kernel_direction_decision(
        _phase3_report(candidate_rankings=[]),
        KernelProfilingSummary(solver_core_fraction=None),
    )

    assert decision.scipy_status == "needs_more_evidence"
    assert decision.recommended_solver_stack == "scipy"
    assert any("solver_core_fraction" in reason for reason in decision.missing_evidence)


def _phase3_report(
    *,
    candidate_rankings: list[dict[str, object]],
    post_sundials_gap_unresolved: bool = False,
    direct_petsc_escalation: bool = False,
) -> dict[str, object]:
    return {
        "candidate_rankings": candidate_rankings,
        "disqualified_candidates": [],
        "minimum_rtf_gate": 4.0,
        "latency_budget_fraction": 0.25,
        "coverage_matrix": [
            {"workload_id": "ammonia_recycle_warm"},
            {"workload_id": "staged_delay_control_disturbance"},
            {"workload_id": "checkpoint_restart_reconfigure"},
        ],
        "post_sundials_gap_unresolved": post_sundials_gap_unresolved,
        "direct_petsc_escalation": direct_petsc_escalation,
    }

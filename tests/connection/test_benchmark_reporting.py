from __future__ import annotations

from modular_simulation.connection.benchmarking.contracts import (
    BenchmarkCandidateConfig,
    BenchmarkDisqualificationReason,
    BenchmarkLatencyBudget,
)
from modular_simulation.connection.benchmarking.telemetry import build_benchmark_attempt_record
from modular_simulation.connection.benchmarking.workloads import build_phase3_workloads
from modular_simulation.connection.kernel_adapter import (
    KernelAdapterTelemetry,
    KernelCandidateStepResult,
)


def test_score_candidate_report_uses_accepted_step_latency_only() -> None:
    from modular_simulation.connection.benchmarking.reporting import score_candidate_report

    workload = build_phase3_workloads()[0]
    candidate = _candidate_config_for_workload(workload)
    accepted_fast = _attempt_record(
        workload_index=0,
        accepted=True,
        wall_clock_elapsed_s=0.02,
    )
    accepted_slow = _attempt_record(
        workload_index=0,
        accepted=True,
        wall_clock_elapsed_s=0.03,
    )
    rejected_very_slow = _attempt_record(
        workload_index=0,
        accepted=False,
        wall_clock_elapsed_s=5.0,
    )

    report = score_candidate_report(
        candidate_config=candidate,
        attempt_records=(accepted_fast, accepted_slow, rejected_very_slow),
        latency_budget=BenchmarkLatencyBudget(),
    )

    assert report["accepted_attempt_count"] == 2
    assert report["rejected_attempt_count"] == 1
    assert report["accepted_step_latency_median_s"] == 0.025
    assert report["accepted_step_latency_p95_s"] == 0.0295
    assert report["accepted_step_latency_p99_s"] == 0.0299
    assert report["realtime_factor"] == 10.0
    assert report["minimum_rtf_gate"] == 4.0
    assert report["headline_rtf_target"] == 100.0
    assert report["meets_minimum_rtf_gate"] is True
    assert report["meets_headline_rtf_target"] is False
    assert report["accepted_step_p95_fraction_of_step_size"] == 0.118
    assert report["meets_latency_gate"] is True


def test_score_candidate_report_disqualifies_fallback_usage() -> None:
    from modular_simulation.connection.benchmarking.reporting import score_candidate_report

    workload = build_phase3_workloads()[0]
    candidate = _candidate_config_for_workload(workload)
    fallback_attempt = _attempt_record(
        workload_index=0,
        accepted=True,
        wall_clock_elapsed_s=0.02,
        used_fallback=True,
    )

    report = score_candidate_report(
        candidate_config=candidate,
        attempt_records=(fallback_attempt,),
        latency_budget=BenchmarkLatencyBudget(),
    )

    assert report["is_disqualified"] is True
    assert report["viable_for_ranking"] is False
    assert report["disqualification_reasons"] == ["fallback_used"]


def test_disqualified_baseline_is_visible_but_unranked() -> None:
    from modular_simulation.connection.benchmarking.reporting import build_phase3_report

    workload = build_phase3_workloads()[0]
    disciplined_split = _candidate_config_for_workload(
        workload,
        candidate_id="disciplined_split",
        candidate_label="Disciplined split baseline",
    )
    hybrid_candidate = _candidate_config_for_workload(
        workload,
        candidate_id="hybrid_coupled",
        candidate_label="Hybrid coupled candidate",
    )

    report = build_phase3_report(
        candidate_attempt_records={
            disciplined_split.candidate_id: (
                _attempt_record(
                    workload_index=0,
                    candidate_config=disciplined_split,
                    accepted=True,
                    wall_clock_elapsed_s=0.02,
                    used_fallback=True,
                ),
            ),
            hybrid_candidate.candidate_id: (
                _attempt_record(
                    workload_index=0,
                    candidate_config=hybrid_candidate,
                    accepted=True,
                    wall_clock_elapsed_s=0.02,
                ),
            ),
        },
        candidate_configs={
            disciplined_split.candidate_id: disciplined_split,
            hybrid_candidate.candidate_id: hybrid_candidate,
        },
        coverage_matrix=(),
        latency_budget=BenchmarkLatencyBudget(),
    )

    assert [row["candidate_id"] for row in report["candidate_rankings"]] == ["hybrid_coupled"]
    assert [row["candidate_id"] for row in report["disqualified_candidates"]] == [
        "disciplined_split"
    ]
    assert report["disqualified_candidates"][0]["candidate_label"] == "Disciplined split baseline"
    assert report["disqualified_candidates"][0]["disqualification_reasons"] == ["fallback_used"]


def test_build_phase3_report_includes_coverage_matrix_and_disqualified_candidates() -> None:
    from modular_simulation.connection.benchmarking.reporting import build_phase3_report

    workloads = build_phase3_workloads()
    baseline = _candidate_config_for_workload(workloads[0])
    report = build_phase3_report(
        candidate_attempt_records={
            baseline.candidate_id: (
                _attempt_record(
                    workload_index=0,
                    candidate_config=baseline,
                    accepted=True,
                    wall_clock_elapsed_s=0.02,
                    disqualification_reasons=(
                        BenchmarkDisqualificationReason.HIDDEN_SOLVER_FAILURE,
                    ),
                ),
            )
        },
        candidate_configs={baseline.candidate_id: baseline},
        coverage_matrix=[
            {
                "workload_id": workloads[0].workload_id,
                "checkpoint_id": workloads[0].checkpoint_id,
                "scenario_tags": [tag.value for tag in workloads[0].scenario_tags],
            }
        ],
        latency_budget=BenchmarkLatencyBudget(),
    )

    assert report["coverage_matrix"][0]["workload_id"] == "ammonia_recycle_warm"
    assert report["disqualified_candidates"][0]["disqualification_reasons"] == [
        "hidden_solver_failure"
    ]


def _attempt_record(
    *,
    workload_index: int,
    candidate_config: BenchmarkCandidateConfig | None = None,
    accepted: bool,
    wall_clock_elapsed_s: float,
    used_fallback: bool = False,
    disqualification_reasons: tuple[BenchmarkDisqualificationReason, ...] = (),
):
    workload = build_phase3_workloads()[workload_index]
    candidate = candidate_config or _candidate_config_for_workload(workload)
    return build_benchmark_attempt_record(
        candidate_step_result=KernelCandidateStepResult(
            accepted=accepted,
            graph_revision="graph_1",
            telemetry=KernelAdapterTelemetry(
                macro_step_index=1,
                macro_step_time_s=0.25,
                simulation_time_s=0.25,
                graph_revision="graph_1",
                executed_sequence=("candidate_step",),
                transport_fallback_keys=("line_a",) if used_fallback else (),
                junction_fallback_keys=(),
                used_fallback=used_fallback,
            ),
            details="ok" if accepted else "rejected",
        ),
        wall_clock_elapsed_s=wall_clock_elapsed_s,
        replay_hash="replay-hash",
        workload_definition=workload,
        candidate_config=candidate,
        disqualification_reasons=disqualification_reasons,
    )


def _candidate_config_for_workload(
    workload,
    *,
    candidate_id: str = "disciplined_split",
    candidate_label: str = "Disciplined split baseline",
) -> BenchmarkCandidateConfig:
    return BenchmarkCandidateConfig(
        candidate_id=candidate_id,
        candidate_label=candidate_label,
        checkpoint_id=workload.checkpoint_id,
        tolerance_profile=workload.tolerance_profile,
        physical_acceptance_profile=workload.physical_acceptance_profile,
        telemetry_contract_version=workload.telemetry_contract_version,
        delay_semantics_label=workload.delay_semantics_label,
        candidate_family="split" if candidate_id == "disciplined_split" else "hybrid",
    )

from __future__ import annotations

from dataclasses import replace

from modular_simulation.connection.benchmarking import (
    BenchmarkCandidateConfig,
    BenchmarkDisqualificationReason,
    BenchmarkLatencyBudget,
    BenchmarkScenarioTag,
    BenchmarkWorkloadDefinition,
    build_benchmark_attempt_record,
    summarize_accepted_step_latency,
)
from modular_simulation.connection.kernel_adapter import (
    KernelAdapterTelemetry,
    KernelCandidateStepResult,
)


def test_benchmark_latency_budget_distinguishes_minimum_gate_from_headline_target() -> None:
    budget = BenchmarkLatencyBudget()

    assert budget.headline_rtf_target == 100.0
    assert budget.minimum_rtf_gate == 4.0
    assert budget.accepted_step_p95_fraction_of_step_size == 0.25
    assert budget.use_accepted_steps_only_for_latency_gate is True
    assert budget.minimum_rtf_gate < budget.headline_rtf_target


def test_workload_definition_requires_shared_fairness_fields() -> None:
    workload = BenchmarkWorkloadDefinition(
        workload_id="staged_delay_control_disturbance",
        checkpoint_id="checkpoint-delay-control-v1",
        tolerance_profile="phase3-default-tolerances",
        physical_acceptance_profile="phase3-physical-acceptance-v1",
        telemetry_contract_version="benchmark_attempt_v1",
        delay_semantics_label="external_transport_history",
        scenario_tags=(
            BenchmarkScenarioTag.DISTURBANCE,
            BenchmarkScenarioTag.CONTROLLER_NETWORK_COUPLING,
            BenchmarkScenarioTag.DELAY_HEAVY,
        ),
        latency_budget=BenchmarkLatencyBudget(),
    )

    assert workload.checkpoint_id == "checkpoint-delay-control-v1"
    assert workload.tolerance_profile == "phase3-default-tolerances"
    assert workload.physical_acceptance_profile == "phase3-physical-acceptance-v1"
    assert workload.telemetry_contract_version == "benchmark_attempt_v1"
    assert workload.delay_semantics_label == "external_transport_history"
    assert workload.scenario_tags == (
        BenchmarkScenarioTag.DISTURBANCE,
        BenchmarkScenarioTag.CONTROLLER_NETWORK_COUPLING,
        BenchmarkScenarioTag.DELAY_HEAVY,
    )
    assert BenchmarkScenarioTag.WARM_RUN.value == "warm_run"
    assert BenchmarkScenarioTag.RESTART_RECONFIGURATION.value == "restart_reconfiguration"


def test_disqualification_reasons_include_fallback_and_hidden_failure() -> None:
    reasons = {reason.value for reason in BenchmarkDisqualificationReason}

    assert reasons == {
        "fallback_used",
        "physical_acceptance_failure",
        "hidden_solver_failure",
        "clipping_masked_apparent_stability",
        "hidden_recovery",
        "telemetry_contract_violation",
    }


def _workload_definition() -> BenchmarkWorkloadDefinition:
    return BenchmarkWorkloadDefinition(
        workload_id="staged_delay_control_disturbance",
        checkpoint_id="checkpoint-delay-control-v1",
        tolerance_profile="phase3-default-tolerances",
        physical_acceptance_profile="phase3-physical-acceptance-v1",
        telemetry_contract_version="benchmark_attempt_v1",
        delay_semantics_label="external_transport_history",
        scenario_tags=(
            BenchmarkScenarioTag.DISTURBANCE,
            BenchmarkScenarioTag.CONTROLLER_NETWORK_COUPLING,
            BenchmarkScenarioTag.DELAY_HEAVY,
        ),
    )


def _candidate_config() -> BenchmarkCandidateConfig:
    return BenchmarkCandidateConfig(
        candidate_id="split_scipy",
        candidate_label="Split / SciPy baseline",
        checkpoint_id="checkpoint-delay-control-v1",
        tolerance_profile="phase3-default-tolerances",
        physical_acceptance_profile="phase3-physical-acceptance-v1",
        telemetry_contract_version="benchmark_attempt_v1",
        delay_semantics_label="external_transport_history",
        candidate_family="split",
    )


def _telemetry(*, used_fallback: bool = True) -> KernelAdapterTelemetry:
    return KernelAdapterTelemetry(
        macro_step_index=7,
        macro_step_time_s=0.5,
        simulation_time_s=3.5,
        graph_revision="graph_rev_0007",
        executed_sequence=("hydraulics_solve", "transport_update", "boundary_state_propagation"),
        transport_fallback_keys=("line_a",),
        junction_fallback_keys=("junction_b",),
        used_fallback=used_fallback,
        picard_iterations_used=3,
        picard_converged=False,
        picard_last_residual=1.25e-4,
        barrier_queue_size_before=2,
        barrier_queue_size_after=1,
        applied_request_ids=("rq_apply",),
        skipped_request_ids=("rq_skip",),
    )


def test_build_benchmark_attempt_record_preserves_fallback_and_replay_evidence() -> None:
    result = KernelCandidateStepResult(
        accepted=True,
        graph_revision="graph_rev_0007",
        telemetry=_telemetry(),
        details="accepted candidate step",
    )

    record = build_benchmark_attempt_record(
        candidate_step_result=result,
        wall_clock_elapsed_s=0.03125,
        replay_hash="replay-hash-007",
        workload_definition=_workload_definition(),
        candidate_config=_candidate_config(),
        disqualification_reasons=(BenchmarkDisqualificationReason.FALLBACK_USED,),
    )

    assert record.attempt_outcome == "accepted"
    assert record.wall_clock_elapsed_s == 0.03125
    assert record.replay_hash == "replay-hash-007"
    assert record.transport_fallback_keys == ("line_a",)
    assert record.junction_fallback_keys == ("junction_b",)
    assert record.used_fallback is True
    assert record.picard_iterations_used == 3
    assert record.picard_converged is False
    assert record.picard_last_residual == 1.25e-4
    assert record.disqualification_reasons == (BenchmarkDisqualificationReason.FALLBACK_USED,)


def test_summarize_accepted_step_latency_ignores_rejected_attempts() -> None:
    workload = _workload_definition()
    candidate = _candidate_config()
    base_result = KernelCandidateStepResult(
        accepted=True,
        graph_revision="graph_rev_0007",
        telemetry=_telemetry(used_fallback=False),
        details=None,
    )
    accepted_attempts = [
        build_benchmark_attempt_record(
            candidate_step_result=base_result,
            wall_clock_elapsed_s=elapsed,
            replay_hash=f"accepted-{index}",
            workload_definition=workload,
            candidate_config=candidate,
        )
        for index, elapsed in enumerate((0.10, 0.20, 0.30, 0.40), start=1)
    ]
    rejected_attempt = build_benchmark_attempt_record(
        candidate_step_result=replace(base_result, accepted=False, details="rejected"),
        wall_clock_elapsed_s=9.99,
        replay_hash="rejected-1",
        workload_definition=workload,
        candidate_config=candidate,
        disqualification_reasons=(BenchmarkDisqualificationReason.HIDDEN_SOLVER_FAILURE,),
    )

    summary = summarize_accepted_step_latency((*accepted_attempts, rejected_attempt))

    assert summary.accepted_attempt_count == 4
    assert summary.rejected_attempt_count == 1
    assert summary.accepted_step_latency_median_s == 0.25
    assert summary.accepted_step_latency_p95_s == 0.385
    assert summary.accepted_step_latency_p99_s == 0.397


def test_attempt_record_carries_delay_semantics_and_workload_contract_fields() -> None:
    workload = _workload_definition()
    candidate = _candidate_config()
    result = KernelCandidateStepResult(
        accepted=False,
        graph_revision="graph_rev_0008",
        telemetry=_telemetry(used_fallback=False),
        details="rejected after gate",
    )

    record = build_benchmark_attempt_record(
        candidate_step_result=result,
        wall_clock_elapsed_s=0.42,
        replay_hash="replay-hash-008",
        workload_definition=workload,
        candidate_config=candidate,
    )

    assert record.attempt_outcome == "rejected"
    assert record.workload_id == workload.workload_id
    assert record.candidate_id == candidate.candidate_id
    assert record.checkpoint_id == workload.checkpoint_id == candidate.checkpoint_id
    assert record.tolerance_profile == workload.tolerance_profile == candidate.tolerance_profile
    assert (
        record.physical_acceptance_profile
        == workload.physical_acceptance_profile
        == candidate.physical_acceptance_profile
    )
    assert (
        record.telemetry_contract_version
        == workload.telemetry_contract_version
        == candidate.telemetry_contract_version
    )
    assert (
        record.delay_semantics_label
        == workload.delay_semantics_label
        == candidate.delay_semantics_label
    )

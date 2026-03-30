from __future__ import annotations

from modular_simulation.connection.benchmarking import (
    BenchmarkDisqualificationReason,
    BenchmarkLatencyBudget,
    BenchmarkScenarioTag,
    BenchmarkWorkloadDefinition,
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

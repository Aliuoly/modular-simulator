from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from types import SimpleNamespace

import pytest

from modular_simulation.connection.benchmarking.contracts import (
    BenchmarkCandidateConfig,
    BenchmarkLatencyBudget,
)
from modular_simulation.connection.benchmarking.telemetry import BenchmarkAttemptRecord
from modular_simulation.connection.benchmarking.contracts import BenchmarkScenarioTag
from modular_simulation.connection.benchmarking.workloads import (
    benchmark_workload_coverage_matrix,
    build_phase3_workloads,
)
from modular_simulation.connection.kernel_adapter import (
    KernelAdapterTelemetry,
    KernelCandidateStepRequest,
    KernelCandidateStepResult,
)


def test_build_phase3_workloads_returns_exactly_three_canonical_workloads() -> None:
    workloads = build_phase3_workloads()

    assert tuple(workload.workload_id for workload in workloads) == (
        "ammonia_recycle_warm",
        "staged_delay_control_disturbance",
        "checkpoint_restart_reconfigure",
    )
    assert len(workloads) == 3
    assert workloads[0].scenario_tags == (
        BenchmarkScenarioTag.WARM_RUN,
        BenchmarkScenarioTag.RECYCLE_HEAVY,
    )
    assert workloads[1].scenario_tags == (
        BenchmarkScenarioTag.DISTURBANCE,
        BenchmarkScenarioTag.CONTROLLER_NETWORK_COUPLING,
        BenchmarkScenarioTag.DELAY_HEAVY,
    )
    assert workloads[2].scenario_tags == (
        BenchmarkScenarioTag.RESTART_RECONFIGURATION,
        BenchmarkScenarioTag.DELAY_HEAVY,
    )


def test_workload_coverage_matrix_explicitly_covers_all_phase3_scenario_classes() -> None:
    rows = benchmark_workload_coverage_matrix()

    assert tuple(row["workload_id"] for row in rows) == (
        "ammonia_recycle_warm",
        "staged_delay_control_disturbance",
        "checkpoint_restart_reconfigure",
    )

    coverage = {tag for row in rows for tag in row["scenario_tags"]}
    assert coverage == {tag.value for tag in BenchmarkScenarioTag}


def test_every_workload_definition_is_checkpoint_first() -> None:
    workloads = build_phase3_workloads()

    expected_checkpoint_ids = {
        "ammonia_recycle_warm": "phase3-ammonia-recycle-warm-checkpoint",
        "staged_delay_control_disturbance": "phase3-staged-delay-control-checkpoint",
        "checkpoint_restart_reconfigure": "phase3-restart-reconfigure-checkpoint",
    }

    for workload in workloads:
        assert workload.checkpoint_id == expected_checkpoint_ids[workload.workload_id]
        assert workload.tolerance_profile == "phase3-default-tolerances"
        assert workload.physical_acceptance_profile == "phase3-physical-acceptance-v1"
        assert workload.telemetry_contract_version == "benchmark_attempt_v1"
        assert callable(workload.checkpoint_builder)

        seed = workload.checkpoint_builder()
        assert seed.macro_step_time_s > 0.0
        assert isinstance(seed.checkpoint, Mapping)
        assert hasattr(seed.session, "save_checkpoint")
        assert hasattr(seed.session, "load_checkpoint")


def test_benchmark_harness_runs_candidate_against_checkpoint_first_workload() -> None:
    from modular_simulation.connection.benchmarking.harness import run_candidate_workload

    workload = build_phase3_workloads()[0]
    candidate = _candidate_config()

    attempt_records = run_candidate_workload(
        workload_definition=workload,
        candidate_config=candidate,
        candidate_adapter_factory=lambda seed: _FakeCandidateAdapter(seed.session.network),
        latency_budget=BenchmarkLatencyBudget(),
        macro_step_count=2,
    )

    assert len(attempt_records) == 2
    assert all(record.workload_id == workload.workload_id for record in attempt_records)
    assert all(record.candidate_id == candidate.candidate_id for record in attempt_records)
    assert all(record.attempt_outcome == "accepted" for record in attempt_records)


def test_harness_uses_shared_fairness_contract_for_each_candidate_run() -> None:
    from modular_simulation.connection.benchmarking.harness import run_candidate_workload

    workload = build_phase3_workloads()[1]
    mismatched_candidate = replace(
        _candidate_config(),
        checkpoint_id="different-checkpoint",
    )

    with pytest.raises(ValueError, match="shared fairness contract"):
        run_candidate_workload(
            workload_definition=workload,
            candidate_config=mismatched_candidate,
            candidate_adapter_factory=lambda seed: _FakeCandidateAdapter(seed.session.network),
            latency_budget=BenchmarkLatencyBudget(),
        )


def _candidate_config() -> BenchmarkCandidateConfig:
    workload = build_phase3_workloads()[0]
    return BenchmarkCandidateConfig(
        candidate_id="disciplined_split",
        candidate_label="Disciplined split baseline",
        checkpoint_id=workload.checkpoint_id,
        tolerance_profile=workload.tolerance_profile,
        physical_acceptance_profile=workload.physical_acceptance_profile,
        telemetry_contract_version=workload.telemetry_contract_version,
        delay_semantics_label=workload.delay_semantics_label,
        candidate_family="split",
    )


class _FakeCandidateAdapter:
    def __init__(self, network: object) -> None:
        self.network = network
        self.runtime_orchestrator = SimpleNamespace()
        self.telemetry = KernelAdapterTelemetry(
            macro_step_index=0,
            macro_step_time_s=0.0,
            simulation_time_s=0.0,
            graph_revision="graph_0",
            executed_sequence=(),
            transport_fallback_keys=(),
            junction_fallback_keys=(),
            used_fallback=False,
        )

    def initialize(self, request):
        return SimpleNamespace(initialized=True, graph_revision="graph_0")

    def warm_start(self, request):
        return SimpleNamespace(restored=True, graph_revision="graph_0")

    def evaluate_candidate_step(
        self, request: KernelCandidateStepRequest
    ) -> KernelCandidateStepResult:
        next_index = self.telemetry.macro_step_index + 1
        self.telemetry = replace(
            self.telemetry,
            macro_step_index=next_index,
            macro_step_time_s=request.macro_step_time_s,
            simulation_time_s=next_index * request.macro_step_time_s,
            graph_revision=f"graph_{next_index}",
            executed_sequence=("candidate_step",),
        )
        return KernelCandidateStepResult(
            accepted=True,
            graph_revision=self.telemetry.graph_revision,
            telemetry=self.telemetry,
            details="accepted",
        )

    def capture_delay_state(self) -> Mapping[str, object]:
        return {}

    def restore_delay_state(self, payload: Mapping[str, object]) -> None:
        return None

    def supported_optional_capabilities(self):
        return frozenset()

    def capture_process_runtime_state(self) -> Mapping[str, object]:
        return {}

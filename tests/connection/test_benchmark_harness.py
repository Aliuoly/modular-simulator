from __future__ import annotations

from collections.abc import Mapping

from modular_simulation.connection.benchmarking.contracts import BenchmarkScenarioTag
from modular_simulation.connection.benchmarking.workloads import (
    benchmark_workload_coverage_matrix,
    build_phase3_workloads,
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

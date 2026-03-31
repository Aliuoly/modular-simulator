from __future__ import annotations

import pytest

from modular_simulation.connection.domain.phase1_failure_semantics import (
    FailureFamily,
    ScenarioClass,
    StructuralPreStepRejection,
)


def test_kern_03_structural_rejection_uses_pre_step_structural_family_only(
    phase1_scenario_manifest,
) -> None:
    scenario = next(
        row
        for row in phase1_scenario_manifest
        if row.scenario_class is ScenarioClass.RUNTIME_EDIT_OR_RESTART
    )

    rejection = StructuralPreStepRejection(
        scenario=scenario,
        rejection_family=FailureFamily.STRUCTURAL_INCONSISTENCY,
        rejection_code="HYDRAULIC_STRUCTURE_REJECTED",
        rejection_message="compile barrier rejected an inconsistent hydraulic structure",
    )

    assert rejection.rejection_family is FailureFamily.STRUCTURAL_INCONSISTENCY
    assert rejection.process_phases_entered == ()


def test_kern_03_structural_rejection_blocks_process_phase_entry(
    phase1_scenario_manifest,
) -> None:
    scenario = next(
        row
        for row in phase1_scenario_manifest
        if row.scenario_class is ScenarioClass.RUNTIME_EDIT_OR_RESTART
    )

    with pytest.raises(
        ValueError,
        match="structural pre-step rejection cannot record subsystem process phase entry",
    ):
        StructuralPreStepRejection(
            scenario=scenario,
            rejection_family=FailureFamily.STRUCTURAL_INCONSISTENCY,
            rejection_code="COMPILE_FAILED",
            rejection_message="compile failed before stepping",
            process_phases_entered=("subsystem_process_step",),
        )

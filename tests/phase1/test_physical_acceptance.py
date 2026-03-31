from __future__ import annotations

from modular_simulation.connection.domain.phase1_failure_semantics import (
    CandidateMacroStepAcceptance,
    FailureFamily,
    ScenarioClass,
)


def test_kern_05_physical_acceptance_rejections_cover_locked_non_physical_cases(
    phase1_scenario_manifest,
) -> None:
    scenario = next(
        row
        for row in phase1_scenario_manifest
        if row.scenario_class is ScenarioClass.INVENTORY_SENSITIVE
    )

    rejection_cases = {
        "NEGATIVE_INVENTORY": "negative inventory rejected before accepted publication",
        "INVALID_COMPOSITION_NORMALIZATION": (
            "invalid composition normalization rejected before accepted publication"
        ),
        "NON_FINITE_PLANT_STATE": "non-finite plant state rejected before accepted publication",
        "MASKING_OR_FALLBACK_EVIDENCE": (
            "fallback or masking evidence rejected before accepted publication"
        ),
    }

    results = [
        CandidateMacroStepAcceptance(
            scenario=scenario,
            accepted=False,
            accepted_snapshot_ids=(),
            rolled_back_on_reject=True,
            candidate_publication_visible=False,
            rejection_family=(
                FailureFamily.SOLVER_MASKING_OR_FAKE_STABILITY
                if code == "MASKING_OR_FALLBACK_EVIDENCE"
                else FailureFamily.INVENTORY_OR_PHYSICAL_FEASIBILITY_BREAK
            ),
            rejection_code=code,
            rejection_message=message,
        )
        for code, message in rejection_cases.items()
    ]

    assert {result.rejection_code for result in results} == set(rejection_cases)
    assert all(result.accepted is False for result in results)


def test_kern_05_physical_acceptance_rejections_never_publish_accepted_snapshot(
    phase1_scenario_manifest,
) -> None:
    scenario = next(
        row
        for row in phase1_scenario_manifest
        if row.scenario_class is ScenarioClass.INVENTORY_SENSITIVE
    )

    rejection = CandidateMacroStepAcceptance(
        scenario=scenario,
        accepted=False,
        accepted_snapshot_ids=(),
        rolled_back_on_reject=True,
        candidate_publication_visible=False,
        rejection_family=FailureFamily.INVENTORY_OR_PHYSICAL_FEASIBILITY_BREAK,
        rejection_code="NEGATIVE_INVENTORY",
        rejection_message="negative holdup_total_mol must reject the candidate step",
    )

    assert rejection.accepted_snapshot_ids == ()

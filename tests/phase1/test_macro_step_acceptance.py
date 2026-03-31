from __future__ import annotations

import pytest

from modular_simulation.connection.domain.phase1_failure_semantics import (
    CandidateMacroStepAcceptance,
    FailureFamily,
    ScenarioClass,
)
from modular_simulation.connection.runtime.connection_layer import MacroStepBookkeeping


def test_kern_02_macro_step_acceptance_requires_one_accepted_coupled_snapshot(
    phase1_scenario_manifest,
    phase1_bookkeeping_expectation_builder,
) -> None:
    scenario = next(
        row
        for row in phase1_scenario_manifest
        if row.scenario_class is ScenarioClass.STRONGLY_COUPLED
    )
    bookkeeping = MacroStepBookkeeping(
        macro_step_time_s=0.5,
        macro_step_index=7,
        executed_sequence=(
            "hydraulics_solve",
            "transport_update",
            "boundary_state_propagation",
        ),
        updated_port_keys=("reactor.feed", "reactor.product"),
        transport_fallback_keys=(),
        junction_fallback_keys=(),
        used_fallback=False,
        picard_gate_enabled=True,
        picard_iterations_used=2,
        picard_converged=True,
        picard_last_residual=1.0e-6,
    )

    acceptance = CandidateMacroStepAcceptance(
        scenario=scenario,
        accepted=True,
        accepted_snapshot_ids=("accepted-step-0007",),
        rolled_back_on_reject=False,
        candidate_publication_visible=True,
        bookkeeping=bookkeeping,
    )

    phase1_bookkeeping_expectation_builder(
        macro_step_time_s=0.5,
        macro_step_index=7,
        updated_port_keys=("reactor.feed", "reactor.product"),
        picard_gate_enabled=True,
        picard_iterations_used=2,
        picard_converged=True,
        picard_last_residual=1.0e-6,
    ).assert_matches(bookkeeping)
    assert acceptance.accepted_snapshot_ids == ("accepted-step-0007",)


def test_kern_02_macro_step_rejection_requires_rollback_and_hides_partial_publication(
    phase1_scenario_manifest,
) -> None:
    scenario = next(
        row
        for row in phase1_scenario_manifest
        if row.scenario_class is ScenarioClass.STRONGLY_COUPLED
    )

    rejection = CandidateMacroStepAcceptance(
        scenario=scenario,
        accepted=False,
        accepted_snapshot_ids=(),
        rolled_back_on_reject=True,
        candidate_publication_visible=False,
        rejection_family=FailureFamily.SOLVER_MASKING_OR_FAKE_STABILITY,
        rejection_code="ROLLBACK_ON_REJECT",
        rejection_message="candidate macro-step exposed fake stability and was rolled back",
    )

    assert rejection.rolled_back_on_reject is True
    assert rejection.candidate_publication_visible is False

    with pytest.raises(
        ValueError,
        match="rejected macro-step results cannot expose candidate publication",
    ):
        CandidateMacroStepAcceptance(
            scenario=scenario,
            accepted=False,
            accepted_snapshot_ids=(),
            rolled_back_on_reject=True,
            candidate_publication_visible=True,
            rejection_family=FailureFamily.SOLVER_MASKING_OR_FAKE_STABILITY,
            rejection_code="VISIBLE_PARTIAL_STATE",
            rejection_message="candidate publication leaked before acceptance",
        )

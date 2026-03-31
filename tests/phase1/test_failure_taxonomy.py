from __future__ import annotations

from modular_simulation.connection.domain.phase1_failure_semantics import (
    CandidateMacroStepAcceptance,
    ClassifiedRuntimeEvidence,
    FailureFamily,
    ScenarioClass,
)
from modular_simulation.connection.runtime.connection_layer import MacroStepBookkeeping


def test_kern_01_failure_taxonomy_manifest_covers_all_locked_families_and_scenario_classes(
    phase1_scenario_manifest,
) -> None:
    assert {row.primary_failure_family for row in phase1_scenario_manifest} == {
        FailureFamily.STALE_HYDRAULIC_LAG,
        FailureFamily.INVENTORY_OR_PHYSICAL_FEASIBILITY_BREAK,
        FailureFamily.STRUCTURAL_INCONSISTENCY,
        FailureFamily.SOLVER_MASKING_OR_FAKE_STABILITY,
    }
    assert {row.scenario_class for row in phase1_scenario_manifest} == {
        ScenarioClass.INVENTORY_SENSITIVE,
        ScenarioClass.DELAY_HEAVY,
        ScenarioClass.STRONGLY_COUPLED,
        ScenarioClass.RUNTIME_EDIT_OR_RESTART,
    }


def test_kern_01_runtime_evidence_uses_replay_hashes_and_bookkeeping_contracts(
    phase1_scenario_manifest,
    phase1_replay_hash_capture,
) -> None:
    scenario = next(
        row for row in phase1_scenario_manifest if row.scenario_class is ScenarioClass.DELAY_HEAVY
    )
    replay_hashes = phase1_replay_hash_capture(scenario.replay_ticks)
    bookkeeping = MacroStepBookkeeping(
        macro_step_time_s=1.0,
        macro_step_index=2,
        executed_sequence=(
            "hydraulics_solve",
            "transport_update",
            "boundary_state_propagation",
        ),
        updated_port_keys=("reactor.feed",),
        transport_fallback_keys=("edge_0001",),
        junction_fallback_keys=(),
        used_fallback=True,
        picard_gate_enabled=False,
        picard_iterations_used=0,
        picard_converged=True,
        picard_last_residual=None,
    )

    evidence = ClassifiedRuntimeEvidence(
        scenario=scenario,
        failure_family=FailureFamily.STALE_HYDRAULIC_LAG,
        replay_hashes=replay_hashes,
        bookkeeping=bookkeeping,
        checkpoint_schema_marker="connection.runtime.snapshot",
        notes=("uv-phase1",),
    )

    assert evidence.replay_hashes == replay_hashes
    assert evidence.bookkeeping.transport_fallback_keys == ("edge_0001",)
    assert evidence.failure_family is FailureFamily.STALE_HYDRAULIC_LAG


def test_kern_01_candidate_acceptance_contract_keeps_single_snapshot_boundary_explicit(
    phase1_scenario_manifest,
) -> None:
    scenario = next(
        row
        for row in phase1_scenario_manifest
        if row.scenario_class is ScenarioClass.STRONGLY_COUPLED
    )

    acceptance = CandidateMacroStepAcceptance(
        scenario=scenario,
        accepted=True,
        accepted_snapshot_ids=("accepted-step-0001",),
        rolled_back_on_reject=False,
        candidate_publication_visible=True,
    )

    assert acceptance.accepted_snapshot_ids == ("accepted-step-0001",)
    assert acceptance.accepted is True

from __future__ import annotations

import numpy as np
import pytest

from modular_simulation.connection.domain.error_catalog import (
    VALIDATION_FAILURE_CODE,
    diagnostic_value_error,
    extract_diagnostic_payload,
)
from modular_simulation.connection.domain.phase1_failure_semantics import (
    CandidateMacroStepAcceptance,
    ClassifiedRuntimeEvidence,
    FailureFamily,
    ScenarioClass,
)
from modular_simulation.connection.hydraulics.hydraulic_solver import HydraulicSolveResult
from modular_simulation.connection.runtime.connection_layer import (
    MacroCoupler,
    MacroStepBookkeeping,
    TransportAndMixingUpdate,
)
from modular_simulation.connection.runtime.phase1_runtime_diagnostics import (
    classify_runtime_failure_family,
)


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


def test_kern_01_hydraulic_solve_failure_emits_structured_runtime_diagnostic_payload() -> None:
    def hydraulic_solve_step(*, macro_step_time_s: float) -> HydraulicSolveResult:
        del macro_step_time_s
        raise diagnostic_value_error(
            code=VALIDATION_FAILURE_CODE,
            message="hydraulic network is missing a fixed pressure reference",
            path="hydraulics.network.reference_node",
            hint="add a fixed-pressure anchor before runtime stepping",
        )

    coupler = MacroCoupler(
        hydraulic_solve_step=hydraulic_solve_step,
        transport_update_step=(
            lambda *, hydraulic_result, macro_step_time_s: TransportAndMixingUpdate(
                transport_results={}
            )
        ),
        boundary_propagation_step=(
            lambda *, hydraulic_result, transport_and_mixing_update, macro_step_time_s: {}
        ),
    )

    with pytest.raises(RuntimeError) as exc_info:
        coupler.run(macro_step_time_s=1.25, macro_step_index=7)

    payload = extract_diagnostic_payload(exc_info.value)
    assert payload is not None
    assert payload["failure_family"] == FailureFamily.STRUCTURAL_INCONSISTENCY.value
    assert payload["path"] == "hydraulics.network.reference_node"
    assert payload["hint"] == "add a fixed-pressure anchor before runtime stepping"
    assert payload["macro_step_index"] == 7
    assert payload["macro_step_time_s"] == pytest.approx(1.25)
    assert payload["executed_sequence"] == ["hydraulics_solve"]
    assert payload["transport_fallback_keys"] == []
    assert payload["junction_fallback_keys"] == []
    assert payload["picard_iterations_used"] == 0


@pytest.mark.parametrize(
    ("bookkeeping", "expected_family"),
    [
        pytest.param(
            MacroStepBookkeeping(
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
            ),
            FailureFamily.STALE_HYDRAULIC_LAG,
            id="fallback-heavy-stale-lag",
        ),
        pytest.param(
            MacroStepBookkeeping(
                macro_step_time_s=1.0,
                macro_step_index=3,
                executed_sequence=(
                    "hydraulics_solve",
                    "transport_update",
                    "boundary_state_propagation",
                ),
                updated_port_keys=("recycle.inlet",),
                transport_fallback_keys=("edge_recycle",),
                junction_fallback_keys=("junction_recycle",),
                used_fallback=True,
                picard_gate_enabled=True,
                picard_iterations_used=3,
                picard_converged=False,
                picard_last_residual=0.42,
            ),
            FailureFamily.SOLVER_MASKING_OR_FAKE_STABILITY,
            id="fallback-heavy-picard-mask",
        ),
    ],
)
def test_kern_01_runtime_classification_distinguishes_fallback_heavy_failure_modes_without_string_parsing(
    bookkeeping: MacroStepBookkeeping,
    expected_family: FailureFamily,
) -> None:
    assert classify_runtime_failure_family(bookkeeping=bookkeeping) is expected_family


def test_kern_01_runtime_classification_preserves_all_four_locked_failure_families() -> None:
    families = {
        classify_runtime_failure_family(
            bookkeeping=MacroStepBookkeeping(
                macro_step_time_s=1.0,
                macro_step_index=1,
                executed_sequence=(
                    "hydraulics_solve",
                    "transport_update",
                    "boundary_state_propagation",
                ),
                updated_port_keys=(),
                transport_fallback_keys=("edge_delay",),
                junction_fallback_keys=(),
                used_fallback=True,
            )
        ),
        classify_runtime_failure_family(
            cause=diagnostic_value_error(
                code="PHYSICAL_ACCEPTANCE_FAILURE",
                message="candidate macro-step produced negative holdup_total_mol",
                path="process_state_values.tank_a.holdup_total_mol",
                hint="restore the last accepted state and inspect pre-step inventory",
            )
        ),
        classify_runtime_failure_family(
            cause=diagnostic_value_error(
                code=VALIDATION_FAILURE_CODE,
                message="missing pressure reference",
                path="hydraulics.network.reference_node",
                hint="add a fixed-pressure anchor",
            )
        ),
        classify_runtime_failure_family(
            bookkeeping=MacroStepBookkeeping(
                macro_step_time_s=1.0,
                macro_step_index=4,
                executed_sequence=(
                    "hydraulics_solve",
                    "transport_update",
                    "boundary_state_propagation",
                ),
                updated_port_keys=("recycle.inlet",),
                transport_fallback_keys=("edge_recycle",),
                junction_fallback_keys=("junction_recycle",),
                used_fallback=True,
                picard_gate_enabled=True,
                picard_iterations_used=2,
                picard_converged=False,
                picard_last_residual=0.11,
            )
        ),
    }

    assert families == {
        FailureFamily.STALE_HYDRAULIC_LAG,
        FailureFamily.INVENTORY_OR_PHYSICAL_FEASIBILITY_BREAK,
        FailureFamily.STRUCTURAL_INCONSISTENCY,
        FailureFamily.SOLVER_MASKING_OR_FAKE_STABILITY,
    }

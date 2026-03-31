from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from modular_simulation.connection.domain.error_catalog import DiagnosticPayload
from modular_simulation.connection.runtime.connection_layer import MacroStepBookkeeping


class FailureFamily(StrEnum):
    STALE_HYDRAULIC_LAG = "stale_hydraulic_lag"
    INVENTORY_OR_PHYSICAL_FEASIBILITY_BREAK = "inventory_or_physical_feasibility_break"
    STRUCTURAL_INCONSISTENCY = "structural_inconsistency"
    SOLVER_MASKING_OR_FAKE_STABILITY = "solver_masking_or_fake_stability"


STALE_HYDRAULIC_LAG_FAMILY = FailureFamily.STALE_HYDRAULIC_LAG
INVENTORY_OR_PHYSICAL_FEASIBILITY_BREAK_FAMILY = (
    FailureFamily.INVENTORY_OR_PHYSICAL_FEASIBILITY_BREAK
)
STRUCTURAL_INCONSISTENCY_FAMILY = FailureFamily.STRUCTURAL_INCONSISTENCY
SOLVER_MASKING_OR_FAKE_STABILITY_FAMILY = FailureFamily.SOLVER_MASKING_OR_FAKE_STABILITY


class ScenarioClass(StrEnum):
    INVENTORY_SENSITIVE = "inventory_sensitive"
    DELAY_HEAVY = "delay_heavy"
    STRONGLY_COUPLED = "strongly_coupled"
    RUNTIME_EDIT_OR_RESTART = "runtime_edit_or_restart"


INVENTORY_SENSITIVE_SCENARIO = ScenarioClass.INVENTORY_SENSITIVE
DELAY_HEAVY_SCENARIO = ScenarioClass.DELAY_HEAVY
STRONGLY_COUPLED_SCENARIO = ScenarioClass.STRONGLY_COUPLED
RUNTIME_EDIT_OR_RESTART_SCENARIO = ScenarioClass.RUNTIME_EDIT_OR_RESTART


class AcceptanceGate(StrEnum):
    FAILURE_TAXONOMY_EVIDENCE = "failure_taxonomy_evidence"
    STRUCTURAL_PRE_STEP_REJECTION = "structural_pre_step_rejection"
    MACRO_STEP_ACCEPTANCE = "macro_step_acceptance"
    PHYSICAL_ACCEPTANCE = "physical_acceptance"


@dataclass(frozen=True)
class ScenarioManifestRow:
    scenario_id: str
    description: str
    scenario_class: ScenarioClass
    primary_failure_family: FailureFamily
    expected_gate: AcceptanceGate
    replay_ticks: tuple[int, ...] = ()
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.scenario_id.strip():
            raise ValueError("scenario_id must be non-empty")
        if not self.description.strip():
            raise ValueError("description must be non-empty")
        if any(tick < 0 for tick in self.replay_ticks):
            raise ValueError("replay_ticks must contain only non-negative integers")


@dataclass(frozen=True)
class ClassifiedRuntimeEvidence:
    scenario: ScenarioManifestRow
    failure_family: FailureFamily
    replay_hashes: Mapping[int, str]
    bookkeeping: MacroStepBookkeeping
    diagnostic_payload: DiagnosticPayload | None = None
    checkpoint_schema_marker: str | None = None
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        missing_ticks = [
            tick for tick in self.scenario.replay_ticks if tick not in self.replay_hashes
        ]
        if missing_ticks:
            raise ValueError(
                "replay_hashes must cover every tick declared in scenario.replay_ticks"
            )


@dataclass(frozen=True)
class StructuralPreStepRejection:
    scenario: ScenarioManifestRow
    rejection_family: FailureFamily
    rejection_code: str
    rejection_message: str
    process_phases_entered: tuple[str, ...] = ()
    diagnostic_payload: DiagnosticPayload | None = None

    def __post_init__(self) -> None:
        if self.rejection_family is not FailureFamily.STRUCTURAL_INCONSISTENCY:
            raise ValueError(
                "structural pre-step rejection must use the structural_inconsistency family"
            )
        if self.process_phases_entered:
            raise ValueError(
                "structural pre-step rejection cannot record subsystem process phase entry"
            )
        if not self.rejection_code.strip() or not self.rejection_message.strip():
            raise ValueError("structural pre-step rejection requires code and message")


@dataclass(frozen=True)
class CandidateMacroStepAcceptance:
    scenario: ScenarioManifestRow
    accepted: bool
    accepted_snapshot_ids: tuple[str, ...]
    rolled_back_on_reject: bool
    candidate_publication_visible: bool
    bookkeeping: MacroStepBookkeeping | None = None
    rejection_family: FailureFamily | None = None
    rejection_code: str | None = None
    rejection_message: str | None = None
    diagnostic_payload: DiagnosticPayload | None = None

    def __post_init__(self) -> None:
        if self.accepted:
            if len(self.accepted_snapshot_ids) != 1:
                raise ValueError(
                    "accepted macro-step results must publish exactly one accepted snapshot id"
                )
            if self.rolled_back_on_reject:
                raise ValueError("accepted macro-step results cannot report rollback-on-reject")
            if self.rejection_family is not None:
                raise ValueError("accepted macro-step results cannot include rejection family")
            if self.rejection_code is not None or self.rejection_message is not None:
                raise ValueError("accepted macro-step results cannot include rejection details")
            return

        if self.accepted_snapshot_ids:
            raise ValueError("rejected macro-step results cannot publish accepted snapshots")
        if not self.rolled_back_on_reject:
            raise ValueError("rejected macro-step results must report rollback-on-reject")
        if self.candidate_publication_visible:
            raise ValueError("rejected macro-step results cannot expose candidate publication")
        if self.rejection_family is None:
            raise ValueError("rejected macro-step results require a rejection family")
        if self.rejection_code is None or self.rejection_message is None:
            raise ValueError("rejected macro-step results require rejection details")


def build_default_phase1_scenario_manifest() -> tuple[ScenarioManifestRow, ...]:
    """Return the canonical Wave 0 Phase 1 scenario matrix.

    These rows are intentionally light-weight so later plans can extend them while
    keeping one importable contract surface for uv-driven pytest execution.
    """

    return (
        ScenarioManifestRow(
            scenario_id="inventory_holdup_floor",
            description=(
                "Inventory-sensitive replay where accepted publication must reject a "
                "negative or depleted holding-tank holdup state."
            ),
            scenario_class=ScenarioClass.INVENTORY_SENSITIVE,
            primary_failure_family=(FailureFamily.INVENTORY_OR_PHYSICAL_FEASIBILITY_BREAK),
            expected_gate=AcceptanceGate.PHYSICAL_ACCEPTANCE,
            replay_ticks=(0, 1),
            tags=("holding_tank", "inventory", "phase1"),
        ),
        ScenarioManifestRow(
            scenario_id="delay_transport_fallback",
            description=(
                "Delay-heavy replay where lag transport and near-zero-flow fallback "
                "must remain visible in bookkeeping-backed evidence."
            ),
            scenario_class=ScenarioClass.DELAY_HEAVY,
            primary_failure_family=FailureFamily.STALE_HYDRAULIC_LAG,
            expected_gate=AcceptanceGate.FAILURE_TAXONOMY_EVIDENCE,
            replay_ticks=(0, 2),
            tags=("transport_history", "delay", "fallback"),
        ),
        ScenarioManifestRow(
            scenario_id="recycle_picard_masking",
            description=(
                "Strongly coupled recycle replay where Picard activity and fallback "
                "evidence must remain classifiable instead of looking falsely stable."
            ),
            scenario_class=ScenarioClass.STRONGLY_COUPLED,
            primary_failure_family=FailureFamily.SOLVER_MASKING_OR_FAKE_STABILITY,
            expected_gate=AcceptanceGate.MACRO_STEP_ACCEPTANCE,
            replay_ticks=(0, 1, 3),
            tags=("recycle", "picard", "strong_coupling"),
        ),
        ScenarioManifestRow(
            scenario_id="restart_barrier_resume",
            description=(
                "Runtime-edit or restart replay where compile or barrier failures must "
                "reject before subsystem process stepping begins."
            ),
            scenario_class=ScenarioClass.RUNTIME_EDIT_OR_RESTART,
            primary_failure_family=FailureFamily.STRUCTURAL_INCONSISTENCY,
            expected_gate=AcceptanceGate.STRUCTURAL_PRE_STEP_REJECTION,
            replay_ticks=(0,),
            tags=("barrier", "restart", "reconfiguration"),
        ),
    )


def manifest_rows_by_scenario_class(
    rows: Sequence[ScenarioManifestRow],
) -> dict[ScenarioClass, tuple[ScenarioManifestRow, ...]]:
    grouped: dict[ScenarioClass, list[ScenarioManifestRow]] = {}
    for row in rows:
        grouped.setdefault(row.scenario_class, []).append(row)
    return {scenario_class: tuple(class_rows) for scenario_class, class_rows in grouped.items()}


__all__ = [
    "AcceptanceGate",
    "CandidateMacroStepAcceptance",
    "ClassifiedRuntimeEvidence",
    "DELAY_HEAVY_SCENARIO",
    "FailureFamily",
    "INVENTORY_OR_PHYSICAL_FEASIBILITY_BREAK_FAMILY",
    "INVENTORY_SENSITIVE_SCENARIO",
    "RUNTIME_EDIT_OR_RESTART_SCENARIO",
    "STALE_HYDRAULIC_LAG_FAMILY",
    "STRONGLY_COUPLED_SCENARIO",
    "STRUCTURAL_INCONSISTENCY_FAMILY",
    "SOLVER_MASKING_OR_FAKE_STABILITY_FAMILY",
    "ScenarioClass",
    "ScenarioManifestRow",
    "StructuralPreStepRejection",
    "build_default_phase1_scenario_manifest",
    "manifest_rows_by_scenario_class",
]

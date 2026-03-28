"""Main-sandbox progression catalog and snapshot helpers."""

from __future__ import annotations

from dataclasses import dataclass

from modular_simulation.gameplay.contracts import ProgressionSnapshot


@dataclass(frozen=True)
class StageDefinition:
    stage_id: str
    title: str
    available_item_ids: tuple[str, ...]


@dataclass(frozen=True)
class ResearchDefinition:
    research_id: str
    target_stage_ids: tuple[str, ...]
    required_product_quantities: dict[str, float]


STAGE_CATALOG: dict[str, StageDefinition] = {
    "gas_inlet_separation_v1": StageDefinition(
        stage_id="gas_inlet_separation_v1",
        title="Inlet gas separation",
        available_item_ids=("place_inlet_gas_separator", "build_process_line"),
    ),
    "teg_dehydration_v1": StageDefinition(
        stage_id="teg_dehydration_v1",
        title="TEG dehydration",
        available_item_ids=(
            "place_teg_contactor",
            "place_rich_glycol_flash_tank",
            "place_lean_rich_glycol_exchanger",
            "place_teg_regenerator",
            "install_glycol_circulation_pump",
        ),
    ),
    "jt_low_temperature_separation_v1": StageDefinition(
        stage_id="jt_low_temperature_separation_v1",
        title="JT / low-temperature separation",
        available_item_ids=(
            "place_gas_gas_exchanger",
            "install_jt_valve",
            "place_low_temperature_separator",
        ),
    ),
    "condensate_stabilization_v1": StageDefinition(
        stage_id="condensate_stabilization_v1",
        title="Condensate stabilization",
        available_item_ids=("place_condensate_stabilizer",),
    ),
}

STAGE_ORDER: tuple[str, ...] = tuple(STAGE_CATALOG)
STARTER_STAGE_IDS: tuple[str, ...] = ("gas_inlet_separation_v1", "teg_dehydration_v1")
UNLOCK_RESEARCH_ID = "unlock_cold_recovery_train_v1"
BUILD_PROCESS_LINE_ITEM_ID = "build_process_line"

RESEARCH_CATALOG: dict[str, ResearchDefinition] = {
    UNLOCK_RESEARCH_ID: ResearchDefinition(
        research_id=UNLOCK_RESEARCH_ID,
        target_stage_ids=(
            "jt_low_temperature_separation_v1",
            "condensate_stabilization_v1",
        ),
        required_product_quantities={
            "separator_gas": 20.0,
            "unstabilized_condensate": 10.0,
            "dry_gas": 20.0,
        },
    )
}


def build_progression_snapshot(unlocked_stage_ids: tuple[str, ...]) -> ProgressionSnapshot:
    unknown = tuple(stage_id for stage_id in unlocked_stage_ids if stage_id not in STAGE_CATALOG)
    if unknown:
        raise ValueError(f"Unknown stage ids: {unknown!r}")

    unlocked = tuple(stage_id for stage_id in STAGE_ORDER if stage_id in set(unlocked_stage_ids))
    active = unlocked[-1] if unlocked else None

    available_items: list[str] = []
    for stage_id in unlocked:
        for item_id in STAGE_CATALOG[stage_id].available_item_ids:
            if item_id == BUILD_PROCESS_LINE_ITEM_ID:
                continue
            if item_id not in available_items:
                available_items.append(item_id)
    available_items.append(BUILD_PROCESS_LINE_ITEM_ID)

    unlock_research = RESEARCH_CATALOG[UNLOCK_RESEARCH_ID]
    has_all_targets = all(
        stage_id in set(unlocked) for stage_id in unlock_research.target_stage_ids
    )
    available_research = () if has_all_targets else (UNLOCK_RESEARCH_ID,)

    return ProgressionSnapshot(
        active_stage_id=active,
        unlocked_stage_ids=unlocked,
        available_item_ids=tuple(available_items),
        available_research_ids=available_research,
    )

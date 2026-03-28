from __future__ import annotations

from modular_simulation.gameplay.contracts import ProgressionSnapshot
from modular_simulation.gameplay.progression import (
    RESEARCH_CATALOG,
    STAGE_CATALOG,
    STARTER_STAGE_IDS,
    build_progression_snapshot,
)


def test_stage_ladder_is_frozen_exactly() -> None:
    assert tuple(STAGE_CATALOG) == (
        "gas_inlet_separation_v1",
        "teg_dehydration_v1",
        "jt_low_temperature_separation_v1",
        "condensate_stabilization_v1",
    )
    assert STAGE_CATALOG["gas_inlet_separation_v1"].available_item_ids == (
        "place_inlet_gas_separator",
        "build_process_line",
    )
    assert STAGE_CATALOG["teg_dehydration_v1"].available_item_ids == (
        "place_teg_contactor",
        "place_rich_glycol_flash_tank",
        "place_lean_rich_glycol_exchanger",
        "place_teg_regenerator",
        "install_glycol_circulation_pump",
    )
    assert STAGE_CATALOG["jt_low_temperature_separation_v1"].available_item_ids == (
        "place_gas_gas_exchanger",
        "install_jt_valve",
        "place_low_temperature_separator",
    )
    assert STAGE_CATALOG["condensate_stabilization_v1"].available_item_ids == (
        "place_condensate_stabilizer",
    )


def test_research_recipe_is_frozen_exactly() -> None:
    recipe = RESEARCH_CATALOG["unlock_cold_recovery_train_v1"].required_product_quantities
    assert recipe == {
        "separator_gas": 20.0,
        "unstabilized_condensate": 10.0,
        "dry_gas": 20.0,
    }


def test_starter_progression_snapshot_tuple_is_frozen_exactly() -> None:
    assert STARTER_STAGE_IDS == ("gas_inlet_separation_v1", "teg_dehydration_v1")
    snapshot = build_progression_snapshot(STARTER_STAGE_IDS)
    assert isinstance(snapshot, ProgressionSnapshot)
    assert snapshot.active_stage_id == "teg_dehydration_v1"
    assert snapshot.unlocked_stage_ids == (
        "gas_inlet_separation_v1",
        "teg_dehydration_v1",
    )
    assert snapshot.available_item_ids == (
        "place_inlet_gas_separator",
        "place_teg_contactor",
        "place_rich_glycol_flash_tank",
        "place_lean_rich_glycol_exchanger",
        "place_teg_regenerator",
        "install_glycol_circulation_pump",
        "build_process_line",
    )
    assert snapshot.available_research_ids == ("unlock_cold_recovery_train_v1",)


def test_unlocked_progression_snapshot_tuple_is_frozen_exactly() -> None:
    snapshot = build_progression_snapshot(
        (
            "gas_inlet_separation_v1",
            "teg_dehydration_v1",
            "jt_low_temperature_separation_v1",
            "condensate_stabilization_v1",
        )
    )
    assert snapshot.active_stage_id == "condensate_stabilization_v1"
    assert snapshot.unlocked_stage_ids == (
        "gas_inlet_separation_v1",
        "teg_dehydration_v1",
        "jt_low_temperature_separation_v1",
        "condensate_stabilization_v1",
    )
    assert snapshot.available_item_ids == (
        "place_inlet_gas_separator",
        "place_teg_contactor",
        "place_rich_glycol_flash_tank",
        "place_lean_rich_glycol_exchanger",
        "place_teg_regenerator",
        "install_glycol_circulation_pump",
        "place_gas_gas_exchanger",
        "install_jt_valve",
        "place_low_temperature_separator",
        "place_condensate_stabilizer",
        "build_process_line",
    )
    assert snapshot.available_research_ids == ()

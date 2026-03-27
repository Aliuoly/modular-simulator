from __future__ import annotations

from modular_simulation.gameplay.sandbox_catalog import build_sandbox_catalog


def test_catalog_contains_gas_items_and_tutorial_items() -> None:
    catalog = build_sandbox_catalog()
    expected = {
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
        "place_heat_exchanger",
        "build_process_line",
        "place_heater_cooler",
        "place_flash_drum",
        "place_component_separator",
        "place_shortcut_distillation_column",
        "place_merge_junction_2x1",
        "place_split_junction_1x2",
        "install_line_pump",
        "install_line_valve",
        "install_sampled_delayed_sensor",
        "install_pid_controller",
        "place_holding_tank",
        "place_quality_control_lab",
    }
    assert set(catalog) == expected


def test_gas_main_items_support_main_sandbox_only() -> None:
    catalog = build_sandbox_catalog()
    for item_id in (
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
    ):
        assert catalog[item_id].supported_start_ids == ("phase1_process_sandbox_v1",)


def test_gas_distillation_items_use_stagewise_column_path() -> None:
    catalog = build_sandbox_catalog()
    for item_id in ("place_teg_regenerator", "place_condensate_stabilizer"):
        item = catalog[item_id]
        assert item.default_config["unit_type"] == "StagewiseDistillationColumn"


def test_place_heat_exchanger_is_tutorial_only_not_main_sandbox() -> None:
    catalog = build_sandbox_catalog()
    assert catalog["place_heat_exchanger"].supported_start_ids == (
        "heater_flash_tutorial_start_v1",
    )


def test_legacy_shortcut_distillation_item_id_remains_available() -> None:
    catalog = build_sandbox_catalog()
    assert "place_shortcut_distillation_column" in catalog

from __future__ import annotations

from modular_simulation.gameplay.start_catalog import build_start_catalog


def test_start_catalog_contains_exact_start_ids() -> None:
    catalog = build_start_catalog()
    assert set(catalog) == {
        "phase1_process_sandbox_v1",
        "heater_flash_tutorial_start_v1",
        "reactor_control_tutorial_start_v1",
        "recycle_purge_tutorial_start_v1",
    }


def test_sandbox_start_is_gas_first_and_tutorials_unchanged() -> None:
    catalog = build_start_catalog()

    sandbox = catalog["phase1_process_sandbox_v1"]
    assert sandbox.start_kind == "sandbox"
    assert sandbox.title == "Sweet wet gas main sandbox"
    assert sandbox.seed_source_paths == (
        "examples/unit_process_flowsheet/gas_1_inlet_separator.py",
        "examples/unit_process_flowsheet/gas_2_teg_dehydration.py",
        "examples/unit_process_flowsheet/gas_3_jt_low_temperature_separation.py",
        "examples/unit_process_flowsheet/gas_4_condensate_stabilizer.py",
    )
    assert sandbox.starting_topology_summary == (
        "One sweet wet gas feed and five named product sinks are present, "
        "but no gas-processing units, line overlays, or connecting lines are preinstalled."
    )
    assert sandbox.allowed_item_ids == (
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

    assert catalog["heater_flash_tutorial_start_v1"].allowed_item_ids == (
        "place_heater_cooler",
        "place_flash_drum",
        "build_process_line",
    )
    assert catalog["reactor_control_tutorial_start_v1"].allowed_item_ids == (
        "install_sampled_delayed_sensor",
        "install_pid_controller",
    )
    assert catalog["recycle_purge_tutorial_start_v1"].allowed_item_ids == (
        "install_line_valve",
        "install_line_pump",
    )

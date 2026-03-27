from __future__ import annotations

from importlib import import_module
from typing import Any


EXPECTED_STARTS = {
    "phase1_process_sandbox_v1": {
        "start_kind": "sandbox",
        "title": "Phase-1 process sandbox",
        "seed_source_paths": (
            "examples/unit_process_flowsheet/easy_2_heater_flash.py",
            "examples/unit_process_flowsheet/easy_3_dual_feed_heat_exchanger.py",
        ),
        "starting_topology_summary": (
            "Two named feeds and two named sinks with no units, junctions, or line overlays preinstalled."
        ),
        "published_signal_ids": (
            "feed_a_draw_mol_s",
            "feed_b_draw_mol_s",
            "product_a_flow_mol_s",
            "product_b_flow_mol_s",
            "heating_steam_duty_W",
            "total_normalized_pump_load",
        ),
        "allowed_item_ids": (
            "place_heater_cooler",
            "place_flash_drum",
            "place_heat_exchanger",
            "place_component_separator",
            "place_merge_junction_2x1",
            "place_split_junction_1x2",
            "build_process_line",
            "install_line_pump",
            "install_line_valve",
            "install_line_heat_actuator",
            "install_sampled_delayed_sensor",
            "install_pid_controller",
        ),
    },
    "heater_flash_tutorial_start_v1": {
        "start_kind": "tutorial_start",
        "title": "Heater/flash tutorial start",
        "seed_source_paths": ("examples/unit_process_flowsheet/easy_2_heater_flash.py",),
        "starting_topology_summary": (
            "One named feed and two named product sinks with no heater, flash drum, or connecting lines preinstalled."
        ),
        "published_signal_ids": (
            "feed_draw_mol_s",
            "vapor_product_flow_mol_s",
            "liquid_product_flow_mol_s",
            "heating_steam_duty_W",
        ),
        "allowed_item_ids": (
            "place_heater_cooler",
            "place_flash_drum",
            "build_process_line",
        ),
    },
    "reactor_control_tutorial_start_v1": {
        "start_kind": "tutorial_start",
        "title": "Reactor control tutorial start",
        "seed_source_paths": (
            "examples/van_de_vusse_cstr/process_definition.py",
            "examples/van_de_vusse_cstr/component_definition.py",
            "examples/van_de_vusse_cstr/run_simulation.py",
        ),
        "starting_topology_summary": (
            "Van de Vusse reactor scaffold is preloaded, but reference sensors and controllers are intentionally absent for learner-installed instrumentation."
        ),
        "published_signal_ids": (
            "reactor_temperature_K",
            "product_b_concentration_mol_l",
            "cooling_water_duty_W",
        ),
        "allowed_item_ids": (
            "install_sampled_delayed_sensor",
            "install_pid_controller",
        ),
    },
    "recycle_purge_tutorial_start_v1": {
        "start_kind": "tutorial_start",
        "title": "Recycle/purge tutorial start",
        "seed_source_paths": ("examples/unit_process_flowsheet/complex_6_ammonia_recycle_loop.py",),
        "starting_topology_summary": (
            "Recycle scaffold includes named recycle and purge lines, but leaves purge throttling and recycle pumping to the learner."
        ),
        "published_signal_ids": (
            "fresh_feed_draw_mol_s",
            "liquid_product_flow_mol_s",
            "purge_loss_flow_mol_s",
            "total_normalized_pump_load",
        ),
        "allowed_item_ids": (
            "install_line_valve",
            "install_line_pump",
        ),
    },
}


def _build_start_catalog() -> dict[str, Any]:
    """Load the start catalog via any callable that returns a dict keyed by start_id.

    The implementation may name its builder function however it likes; we locate
    it by looking for the first public callable in the module that accepts no
    positional arguments and returns a dict.
    """
    module = import_module("modular_simulation.gameplay.start_catalog")
    # Try the canonical name first; fall back to any public no-arg callable.
    for candidate_name in dir(module):
        if candidate_name.startswith("_"):
            continue
        candidate = getattr(module, candidate_name)
        if callable(candidate):
            try:
                result = candidate()
            except TypeError:
                continue
            if isinstance(result, dict):
                return result
    raise RuntimeError(
        "modular_simulation.gameplay.start_catalog exposes no public callable that returns a dict"
    )


def test_start_catalog_contains_exactly_the_frozen_start_ids() -> None:
    catalog = _build_start_catalog()
    assert set(catalog) == set(EXPECTED_STARTS)


def test_start_kind_is_one_sandbox_and_three_tutorial_starts() -> None:
    catalog = _build_start_catalog()
    sandbox_start_ids = [
        start_id
        for start_id, definition in catalog.items()
        if getattr(definition, "start_kind") == "sandbox"
    ]
    assert sandbox_start_ids == ["phase1_process_sandbox_v1"]
    for start_id, definition in catalog.items():
        if start_id != "phase1_process_sandbox_v1":
            assert getattr(definition, "start_kind") == "tutorial_start"


def test_each_start_record_matches_frozen_metadata_payloads() -> None:
    catalog = _build_start_catalog()
    for start_id, expected in EXPECTED_STARTS.items():
        definition = catalog[start_id]
        assert definition.start_kind == expected["start_kind"]
        assert definition.title == expected["title"]
        assert definition.seed_source_paths == expected["seed_source_paths"]
        assert definition.starting_topology_summary == expected["starting_topology_summary"]
        assert definition.published_signal_ids == expected["published_signal_ids"]
        assert definition.allowed_item_ids == expected["allowed_item_ids"]


def test_no_current_start_allowlist_gains_new_foundation_items() -> None:
    """This pack does not add place_holding_tank or place_quality_control_lab to any
    current start's allowed_item_ids.  Both items have supported_start_ids = ()."""
    catalog = _build_start_catalog()
    forbidden_new_items = (
        "place_holding_tank",
        "place_quality_control_lab",
        "place_shortcut_distillation_column",
    )
    for start_id, definition in catalog.items():
        for forbidden in forbidden_new_items:
            assert forbidden not in definition.allowed_item_ids, (
                f"Start '{start_id}' must not include '{forbidden}' in its "
                f"allowed_item_ids in this first pack"
            )


def test_phase1_process_sandbox_keeps_current_title_and_provenance() -> None:
    """phase1_process_sandbox_v1 title and seed_source_paths are frozen; this pack must not change them."""
    catalog = _build_start_catalog()
    sandbox = catalog["phase1_process_sandbox_v1"]
    assert sandbox.title == "Phase-1 process sandbox"
    assert sandbox.seed_source_paths == (
        "examples/unit_process_flowsheet/easy_2_heater_flash.py",
        "examples/unit_process_flowsheet/easy_3_dual_feed_heat_exchanger.py",
    )


def test_phase1_process_sandbox_keeps_current_published_signals() -> None:
    """phase1_process_sandbox_v1 published_signal_ids are frozen; this pack must not change them."""
    catalog = _build_start_catalog()
    sandbox = catalog["phase1_process_sandbox_v1"]
    assert sandbox.published_signal_ids == (
        "feed_a_draw_mol_s",
        "feed_b_draw_mol_s",
        "product_a_flow_mol_s",
        "product_b_flow_mol_s",
        "heating_steam_duty_W",
        "total_normalized_pump_load",
    )


def test_phase1_process_sandbox_keeps_current_allowed_item_ids() -> None:
    """phase1_process_sandbox_v1 allowed_item_ids are frozen at exactly 12 entries; this pack must not change them."""
    catalog = _build_start_catalog()
    sandbox = catalog["phase1_process_sandbox_v1"]
    assert sandbox.allowed_item_ids == (
        "place_heater_cooler",
        "place_flash_drum",
        "place_heat_exchanger",
        "place_component_separator",
        "place_merge_junction_2x1",
        "place_split_junction_1x2",
        "build_process_line",
        "install_line_pump",
        "install_line_valve",
        "install_line_heat_actuator",
        "install_sampled_delayed_sensor",
        "install_pid_controller",
    )

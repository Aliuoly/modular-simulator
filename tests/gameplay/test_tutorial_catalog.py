from __future__ import annotations

from importlib import import_module
from typing import Any


EXPECTED_TUTORIALS = {
    "heater_flash_guided_build_v1": {
        "title": "Heater/flash guided build",
        "teaching_track": "topology_separation",
        "start_id": "heater_flash_tutorial_start_v1",
        "goal_mode": "sequential",
        "goals": (
            {
                "goal_id": "goal_place_heater",
                "title": "Place heater/cooler",
                "goal_kind": "install_item_count",
                "item_id": "place_heater_cooler",
                "required_count": 1,
                "prerequisite_goal_ids": (),
            },
            {
                "goal_id": "goal_place_flash",
                "title": "Place flash drum",
                "goal_kind": "install_item_count",
                "item_id": "place_flash_drum",
                "required_count": 1,
                "prerequisite_goal_ids": ("goal_place_heater",),
            },
            {
                "goal_id": "goal_wire_flowsheet",
                "title": "Wire the flowsheet",
                "goal_kind": "install_item_count",
                "item_id": "build_process_line",
                "required_count": 4,
                "prerequisite_goal_ids": ("goal_place_flash",),
            },
        ),
        "guidance_steps": (
            {
                "step_id": "step_place_heater",
                "title": "Place the heater",
                "related_goal_ids": ("goal_place_heater",),
                "hint_text": "Warm the incoming stream before attempting any vapor/liquid split.",
            },
            {
                "step_id": "step_place_flash",
                "title": "Place the flash drum",
                "related_goal_ids": ("goal_place_flash",),
                "hint_text": "Add one flash drum to create explicit vapor and liquid product branches.",
            },
            {
                "step_id": "step_wire_flowsheet",
                "title": "Wire the flowsheet",
                "related_goal_ids": ("goal_wire_flowsheet",),
                "hint_text": "Connect feed to heater, heater to flash, and both flash products to sinks.",
            },
        ),
    },
    "reactor_control_fixup_v1": {
        "title": "Reactor control fix-up",
        "teaching_track": "reactor_control",
        "start_id": "reactor_control_tutorial_start_v1",
        "goal_mode": "mixed",
        "goals": (
            {
                "goal_id": "goal_add_temperature_sensor",
                "title": "Add temperature sensor",
                "goal_kind": "install_item_count",
                "item_id": "install_sampled_delayed_sensor",
                "required_count": 1,
                "prerequisite_goal_ids": (),
            },
            {
                "goal_id": "goal_add_quality_sensor",
                "title": "Add quality sensor",
                "goal_kind": "install_item_count",
                "item_id": "install_sampled_delayed_sensor",
                "required_count": 1,
                "prerequisite_goal_ids": (),
            },
            {
                "goal_id": "goal_add_pid",
                "title": "Add PID controller",
                "goal_kind": "install_item_count",
                "item_id": "install_pid_controller",
                "required_count": 1,
                "prerequisite_goal_ids": (
                    "goal_add_temperature_sensor",
                    "goal_add_quality_sensor",
                ),
            },
        ),
        "guidance_steps": (
            {
                "step_id": "step_instrument_temperature",
                "title": "Instrument temperature",
                "related_goal_ids": ("goal_add_temperature_sensor",),
                "hint_text": "Instrument reactor temperature before attempting any automatic jacket manipulation.",
            },
            {
                "step_id": "step_instrument_quality",
                "title": "Instrument quality",
                "related_goal_ids": ("goal_add_quality_sensor",),
                "hint_text": "Add a product-quality measurement so tuning discussions connect to selectivity.",
            },
            {
                "step_id": "step_close_loop",
                "title": "Close the loop",
                "related_goal_ids": ("goal_add_pid",),
                "hint_text": "Bind one PID controller to the available actuator tag after both measurements exist.",
            },
        ),
    },
    "recycle_purge_tradeoff_v1": {
        "title": "Recycle/purge tradeoff",
        "teaching_track": "recycle_process_design",
        "start_id": "recycle_purge_tutorial_start_v1",
        "goal_mode": "sequential",
        "goals": (
            {
                "goal_id": "goal_add_purge_valve",
                "title": "Add purge valve",
                "goal_kind": "install_item_count",
                "item_id": "install_line_valve",
                "required_count": 1,
                "prerequisite_goal_ids": (),
            },
            {
                "goal_id": "goal_add_recycle_pump",
                "title": "Add recycle pump",
                "goal_kind": "install_item_count",
                "item_id": "install_line_pump",
                "required_count": 1,
                "prerequisite_goal_ids": ("goal_add_purge_valve",),
            },
        ),
        "guidance_steps": (
            {
                "step_id": "step_throttle_purge",
                "title": "Throttle purge",
                "related_goal_ids": ("goal_add_purge_valve",),
                "hint_text": "Install a purge-line valve so purge becomes an explicit operating decision.",
            },
            {
                "step_id": "step_restore_recycle_drive",
                "title": "Restore recycle drive",
                "related_goal_ids": ("goal_add_recycle_pump",),
                "hint_text": "Install recycle pumping explicitly rather than relying on hidden hydraulic gain.",
            },
        ),
    },
}


def _build_tutorial_catalog() -> dict[str, Any]:
    """Load the tutorial catalog via any callable that returns a dict keyed by tutorial_id.

    The implementation may name its builder function however it likes; we locate
    it by looking for the first public callable in the module that accepts no
    positional arguments and returns a dict.
    """
    module = import_module("modular_simulation.gameplay.tutorial_catalog")
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
        "modular_simulation.gameplay.tutorial_catalog exposes no public callable "
        "that returns a dict"
    )


def test_tutorial_catalog_contains_exactly_the_frozen_tutorial_ids() -> None:
    catalog = _build_tutorial_catalog()
    assert set(catalog) == set(EXPECTED_TUTORIALS)


def test_tutorial_records_match_exact_titles_tracks_starts_and_goal_modes() -> None:
    catalog = _build_tutorial_catalog()
    for tutorial_id, expected in EXPECTED_TUTORIALS.items():
        tutorial = catalog[tutorial_id]
        assert tutorial.title == expected["title"]
        assert tutorial.teaching_track == expected["teaching_track"]
        assert tutorial.start_id == expected["start_id"]
        assert tutorial.goal_mode == expected["goal_mode"]


def test_tutorial_goal_payloads_match_exact_frozen_contracts() -> None:
    catalog = _build_tutorial_catalog()
    for tutorial_id, expected in EXPECTED_TUTORIALS.items():
        tutorial = catalog[tutorial_id]
        actual_goals = tuple(
            {
                "goal_id": goal.goal_id,
                "title": goal.title,
                "goal_kind": goal.goal_kind,
                "item_id": goal.item_id,
                "required_count": goal.required_count,
                "prerequisite_goal_ids": goal.prerequisite_goal_ids,
            }
            for goal in tutorial.goals
        )
        assert actual_goals == expected["goals"]


def test_tutorial_guidance_steps_match_exact_frozen_contracts() -> None:
    catalog = _build_tutorial_catalog()
    for tutorial_id, expected in EXPECTED_TUTORIALS.items():
        tutorial = catalog[tutorial_id]
        actual_steps = tuple(
            {
                "step_id": step.step_id,
                "title": step.title,
                "related_goal_ids": step.related_goal_ids,
                "hint_text": step.hint_text,
            }
            for step in tutorial.guidance_steps
        )
        assert actual_steps == expected["guidance_steps"]

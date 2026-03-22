"""Phase-1 tutorial catalog.

Returns a dict keyed by tutorial_id containing TutorialDefinition records.
"""

from __future__ import annotations

from modular_simulation.gameplay.contracts import (
    GuidanceStepDefinition,
    TutorialDefinition,
    TutorialGoalDefinition,
)


def build_tutorial_catalog() -> dict[str, TutorialDefinition]:
    """Return the frozen phase-1 tutorial catalog."""
    entries = [
        TutorialDefinition(
            tutorial_id="heater_flash_guided_build_v1",
            title="Heater/flash guided build",
            teaching_track="topology_separation",
            start_id="heater_flash_tutorial_start_v1",
            goal_mode="sequential",
            goals=(
                TutorialGoalDefinition(
                    goal_id="goal_place_heater",
                    title="Place heater/cooler",
                    goal_kind="install_item_count",
                    item_id="place_heater_cooler",
                    required_count=1,
                    prerequisite_goal_ids=(),
                ),
                TutorialGoalDefinition(
                    goal_id="goal_place_flash",
                    title="Place flash drum",
                    goal_kind="install_item_count",
                    item_id="place_flash_drum",
                    required_count=1,
                    prerequisite_goal_ids=("goal_place_heater",),
                ),
                TutorialGoalDefinition(
                    goal_id="goal_wire_flowsheet",
                    title="Wire the flowsheet",
                    goal_kind="install_item_count",
                    item_id="build_process_line",
                    required_count=4,
                    prerequisite_goal_ids=("goal_place_flash",),
                ),
            ),
            guidance_steps=(
                GuidanceStepDefinition(
                    step_id="step_place_heater",
                    title="Place the heater",
                    related_goal_ids=("goal_place_heater",),
                    hint_text="Warm the incoming stream before attempting any vapor/liquid split.",
                ),
                GuidanceStepDefinition(
                    step_id="step_place_flash",
                    title="Place the flash drum",
                    related_goal_ids=("goal_place_flash",),
                    hint_text="Add one flash drum to create explicit vapor and liquid product branches.",
                ),
                GuidanceStepDefinition(
                    step_id="step_wire_flowsheet",
                    title="Wire the flowsheet",
                    related_goal_ids=("goal_wire_flowsheet",),
                    hint_text="Connect feed to heater, heater to flash, and both flash products to sinks.",
                ),
            ),
        ),
        TutorialDefinition(
            tutorial_id="reactor_control_fixup_v1",
            title="Reactor control fix-up",
            teaching_track="reactor_control",
            start_id="reactor_control_tutorial_start_v1",
            goal_mode="mixed",
            goals=(
                TutorialGoalDefinition(
                    goal_id="goal_add_temperature_sensor",
                    title="Add temperature sensor",
                    goal_kind="install_item_count",
                    item_id="install_sampled_delayed_sensor",
                    required_count=1,
                    prerequisite_goal_ids=(),
                ),
                TutorialGoalDefinition(
                    goal_id="goal_add_quality_sensor",
                    title="Add quality sensor",
                    goal_kind="install_item_count",
                    item_id="install_sampled_delayed_sensor",
                    required_count=1,
                    prerequisite_goal_ids=(),
                ),
                TutorialGoalDefinition(
                    goal_id="goal_add_pid",
                    title="Add PID controller",
                    goal_kind="install_item_count",
                    item_id="install_pid_controller",
                    required_count=1,
                    prerequisite_goal_ids=(
                        "goal_add_temperature_sensor",
                        "goal_add_quality_sensor",
                    ),
                ),
            ),
            guidance_steps=(
                GuidanceStepDefinition(
                    step_id="step_instrument_temperature",
                    title="Instrument temperature",
                    related_goal_ids=("goal_add_temperature_sensor",),
                    hint_text="Instrument reactor temperature before attempting any automatic jacket manipulation.",
                ),
                GuidanceStepDefinition(
                    step_id="step_instrument_quality",
                    title="Instrument quality",
                    related_goal_ids=("goal_add_quality_sensor",),
                    hint_text="Add a product-quality measurement so tuning discussions connect to selectivity.",
                ),
                GuidanceStepDefinition(
                    step_id="step_close_loop",
                    title="Close the loop",
                    related_goal_ids=("goal_add_pid",),
                    hint_text="Bind one PID controller to the available actuator tag after both measurements exist.",
                ),
            ),
        ),
        TutorialDefinition(
            tutorial_id="recycle_purge_tradeoff_v1",
            title="Recycle/purge tradeoff",
            teaching_track="recycle_process_design",
            start_id="recycle_purge_tutorial_start_v1",
            goal_mode="sequential",
            goals=(
                TutorialGoalDefinition(
                    goal_id="goal_add_purge_valve",
                    title="Add purge valve",
                    goal_kind="install_item_count",
                    item_id="install_line_valve",
                    required_count=1,
                    prerequisite_goal_ids=(),
                ),
                TutorialGoalDefinition(
                    goal_id="goal_add_recycle_pump",
                    title="Add recycle pump",
                    goal_kind="install_item_count",
                    item_id="install_line_pump",
                    required_count=1,
                    prerequisite_goal_ids=("goal_add_purge_valve",),
                ),
            ),
            guidance_steps=(
                GuidanceStepDefinition(
                    step_id="step_throttle_purge",
                    title="Throttle purge",
                    related_goal_ids=("goal_add_purge_valve",),
                    hint_text="Install a purge-line valve so purge becomes an explicit operating decision.",
                ),
                GuidanceStepDefinition(
                    step_id="step_restore_recycle_drive",
                    title="Restore recycle drive",
                    related_goal_ids=("goal_add_recycle_pump",),
                    hint_text="Install recycle pumping explicitly rather than relying on hidden hydraulic gain.",
                ),
            ),
        ),
    ]
    return {entry.tutorial_id: entry for entry in entries}

# Tutorials

## Purpose

This capability defines tutorial mode boundaries, tutorial goal contracts, and frozen phase-1 tutorial records.

## Requirements

### Requirement: Phase-1 Gameplay Uses One Sandbox And Separate Tutorials
Phase-1 gameplay SHALL expose exactly one free-play sandbox and SHALL keep tutorial challenge starts separate from that sandbox.

#### Scenario: Exactly one sandbox start exists
- **WHEN** the phase-1 start catalog is inspected
- **THEN** exactly one start record has `start_kind = "sandbox"` and any remaining start records are `tutorial_start`

### Requirement: Tutorial Contracts Use Explicit Goal Records
Tutorials SHALL use explicit goal records rather than vague learning-objective text.

#### Scenario: Tutorial goal contract shape is fixed
- **WHEN** a contributor inspects tutorial contracts
- **THEN** `TutorialDefinition` exposes `tutorial_id`, `title`, `teaching_track`, `start_id`, `goal_mode`, `goals`, and `guidance_steps`, `TutorialGoalDefinition` exposes `goal_id`, `title`, `goal_kind`, `item_id`, `required_count`, and `prerequisite_goal_ids`, and `GuidanceStepDefinition` exposes `step_id`, `title`, `related_goal_ids`, and `hint_text`

### Requirement: The Exact Phase-1 Tutorial Records Are Frozen
The tutorial catalog SHALL contain exactly `heater_flash_guided_build_v1`, `reactor_control_fixup_v1`, and `recycle_purge_tradeoff_v1` with these exact records:

- `heater_flash_guided_build_v1`: `title = "Heater/flash guided build"`, `teaching_track = "topology_separation"`, `start_id = "heater_flash_tutorial_start_v1"`, `goal_mode = "sequential"`, goals `goal_place_heater` (`title = "Place heater/cooler"`, `goal_kind = "install_item_count"`, `place_heater_cooler`, `1`, no prerequisites), `goal_place_flash` (`title = "Place flash drum"`, `goal_kind = "install_item_count"`, `place_flash_drum`, `1`, prerequisite `goal_place_heater`), `goal_wire_flowsheet` (`title = "Wire the flowsheet"`, `goal_kind = "install_item_count"`, `build_process_line`, `4`, prerequisite `goal_place_flash`), and steps `step_place_heater` (`title = "Place the heater"`, `related_goal_ids = ("goal_place_heater",)`, hint `Warm the incoming stream before attempting any vapor/liquid split.`), `step_place_flash` (`title = "Place the flash drum"`, `related_goal_ids = ("goal_place_flash",)`, hint `Add one flash drum to create explicit vapor and liquid product branches.`), `step_wire_flowsheet` (`title = "Wire the flowsheet"`, `related_goal_ids = ("goal_wire_flowsheet",)`, hint `Connect feed to heater, heater to flash, and both flash products to sinks.`)
- `reactor_control_fixup_v1`: `title = "Reactor control fix-up"`, `teaching_track = "reactor_control"`, `start_id = "reactor_control_tutorial_start_v1"`, `goal_mode = "mixed"`, goals `goal_add_temperature_sensor` (`title = "Add temperature sensor"`, `goal_kind = "install_item_count"`, `install_sampled_delayed_sensor`, `1`, no prerequisites), `goal_add_quality_sensor` (`title = "Add quality sensor"`, `goal_kind = "install_item_count"`, `install_sampled_delayed_sensor`, `1`, no prerequisites), `goal_add_pid` (`title = "Add PID controller"`, `goal_kind = "install_item_count"`, `install_pid_controller`, `1`, prerequisites `goal_add_temperature_sensor` and `goal_add_quality_sensor`), and steps `step_instrument_temperature` (`title = "Instrument temperature"`, `related_goal_ids = ("goal_add_temperature_sensor",)`, hint `Instrument reactor temperature before attempting any automatic jacket manipulation.`), `step_instrument_quality` (`title = "Instrument quality"`, `related_goal_ids = ("goal_add_quality_sensor",)`, hint `Add a product-quality measurement so tuning discussions connect to selectivity.`), `step_close_loop` (`title = "Close the loop"`, `related_goal_ids = ("goal_add_pid",)`, hint `Bind one PID controller to the available actuator tag after both measurements exist.`)
- `recycle_purge_tradeoff_v1`: `title = "Recycle/purge tradeoff"`, `teaching_track = "recycle_process_design"`, `start_id = "recycle_purge_tutorial_start_v1"`, `goal_mode = "sequential"`, goals `goal_add_purge_valve` (`title = "Add purge valve"`, `goal_kind = "install_item_count"`, `install_line_valve`, `1`, no prerequisites), `goal_add_recycle_pump` (`title = "Add recycle pump"`, `goal_kind = "install_item_count"`, `install_line_pump`, `1`, prerequisite `goal_add_purge_valve`), and steps `step_throttle_purge` (`title = "Throttle purge"`, `related_goal_ids = ("goal_add_purge_valve",)`, hint `Install a purge-line valve so purge becomes an explicit operating decision.`), `step_restore_recycle_drive` (`title = "Restore recycle drive"`, `related_goal_ids = ("goal_add_recycle_pump",)`, hint `Install recycle pumping explicitly rather than relying on hidden hydraulic gain.`)

#### Scenario: Tutorial goals are frozen exactly
- **WHEN** a contributor inspects tutorial records
- **THEN** each tutorial’s title, teaching track, start id, goal mode, goal ids, goal titles, goal kinds, goal counts, prerequisite chain, step ids, step titles, step `related_goal_ids`, and step hint text match the exact frozen record above

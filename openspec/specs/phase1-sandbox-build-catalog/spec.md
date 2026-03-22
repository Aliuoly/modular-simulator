# Phase-1 Sandbox Build Catalog

## Purpose

This capability defines the exact phase-1 gameplay start catalog, sandbox build/apply catalog, tutorial challenge records, and the limited generic backend-session helper surface required to support the sandbox-first educational gameplay layer.

## Requirements

### Requirement: Phase-1 Gameplay Uses One Sandbox And Separate Tutorials
Phase-1 gameplay SHALL expose exactly one free-play sandbox and SHALL keep tutorial challenge starts separate from that sandbox.

#### Scenario: Exactly one sandbox start exists
- **WHEN** the phase-1 start catalog is inspected
- **THEN** exactly one start record has `start_kind = "sandbox"` and any remaining start records are `tutorial_start`

### Requirement: Start-State Contract Fields Are Stable
`PlayStartDefinition` SHALL expose `start_id`, `start_kind`, `title`, `seed_source_paths`, `starting_topology_summary`, `published_signal_ids`, and `allowed_item_ids`.

#### Scenario: Start-state contract shape is fixed before implementation
- **WHEN** a contributor inspects the gameplay contracts for phase-1 starts
- **THEN** those exact fields are present and no separate builder-only structure is needed to discover start metadata

### Requirement: The Exact Phase-1 Start Records Are Frozen
The phase-1 start catalog SHALL contain exactly `phase1_process_sandbox_v1`, `heater_flash_tutorial_start_v1`, `reactor_control_tutorial_start_v1`, and `recycle_purge_tutorial_start_v1` with these exact records:

- `phase1_process_sandbox_v1`
  - `start_kind = "sandbox"`
  - `title = "Phase-1 process sandbox"`
  - `seed_source_paths = ("examples/unit_process_flowsheet/easy_2_heater_flash.py", "examples/unit_process_flowsheet/easy_3_dual_feed_heat_exchanger.py")`
  - `starting_topology_summary = "Two named feeds and two named sinks with no units, junctions, or line overlays preinstalled."`
  - `published_signal_ids = ("feed_a_draw_mol_s", "feed_b_draw_mol_s", "product_a_flow_mol_s", "product_b_flow_mol_s", "heating_steam_duty_W", "total_normalized_pump_load")`
  - `allowed_item_ids = ("place_heater_cooler", "place_flash_drum", "place_heat_exchanger", "place_component_separator", "place_merge_junction_2x1", "place_split_junction_1x2", "build_process_line", "install_line_pump", "install_line_valve", "install_line_heat_actuator", "install_sampled_delayed_sensor", "install_pid_controller")`
- `heater_flash_tutorial_start_v1`
  - `start_kind = "tutorial_start"`
  - `title = "Heater/flash tutorial start"`
  - `seed_source_paths = ("examples/unit_process_flowsheet/easy_2_heater_flash.py",)`
  - `starting_topology_summary = "One named feed and two named product sinks with no heater, flash drum, or connecting lines preinstalled."`
  - `published_signal_ids = ("feed_draw_mol_s", "vapor_product_flow_mol_s", "liquid_product_flow_mol_s", "heating_steam_duty_W")`
  - `allowed_item_ids = ("place_heater_cooler", "place_flash_drum", "build_process_line")`
- `reactor_control_tutorial_start_v1`
  - `start_kind = "tutorial_start"`
  - `title = "Reactor control tutorial start"`
  - `seed_source_paths = ("examples/van_de_vusse_cstr/process_definition.py", "examples/van_de_vusse_cstr/component_definition.py", "examples/van_de_vusse_cstr/run_simulation.py")`
  - `starting_topology_summary = "Van de Vusse reactor scaffold is preloaded, but reference sensors and controllers are intentionally absent for learner-installed instrumentation."`
  - `published_signal_ids = ("reactor_temperature_K", "product_b_concentration_mol_l", "cooling_water_duty_W")`
  - `allowed_item_ids = ("install_sampled_delayed_sensor", "install_pid_controller")`
- `recycle_purge_tutorial_start_v1`
  - `start_kind = "tutorial_start"`
  - `title = "Recycle/purge tutorial start"`
  - `seed_source_paths = ("examples/unit_process_flowsheet/complex_6_ammonia_recycle_loop.py",)`
  - `starting_topology_summary = "Recycle scaffold includes named recycle and purge lines, but leaves purge throttling and recycle pumping to the learner."`
  - `published_signal_ids = ("fresh_feed_draw_mol_s", "liquid_product_flow_mol_s", "purge_loss_flow_mol_s", "total_normalized_pump_load")`
  - `allowed_item_ids = ("install_line_valve", "install_line_pump")`

#### Scenario: Start records are frozen exactly
- **WHEN** the phase-1 start catalog is inspected
- **THEN** each start record matches those exact kinds, titles, source paths, topology summaries, published signal ids, and allowed item ids

### Requirement: The Exact Phase-1 Sandbox Catalog Item Ids Are Frozen
The phase-1 sandbox catalog SHALL contain exactly `place_heater_cooler`, `place_flash_drum`, `place_heat_exchanger`, `place_component_separator`, `place_merge_junction_2x1`, `place_split_junction_1x2`, `build_process_line`, `install_line_pump`, `install_line_valve`, `install_line_heat_actuator`, `install_sampled_delayed_sensor`, and `install_pid_controller`.

#### Scenario: No hidden or deferred build items leak into phase 1
- **WHEN** the catalog is inspected
- **THEN** it contains exactly those 12 item ids and no arbitrary process-factory, stand-alone pump/valve-unit, or tutorial-only mechanics

### Requirement: Sandbox Catalog Items Use Typed Apply Kinds Grounded In Repo APIs
Each catalog item SHALL declare one typed `apply_kind` grounded in current repo surfaces: `add_process`, `add_junction`, `connect_configure_line`, `attach_line_pump`, `attach_line_valve`, `attach_line_heat_actuator`, `create_bind_sensor`, or `create_bind_activate_controller`.

#### Scenario: Catalog items trace back to supported substrate operations
- **WHEN** a contributor inspects a catalog item definition
- **THEN** the item’s apply kind maps to an existing repo operation or to a thin generic backend-session helper explicitly required by this change

### Requirement: Sandbox Catalog Item Contract Fields Are Stable
`SandboxCatalogItemDefinition` SHALL expose `item_id`, `title`, `item_kind`, `apply_kind`, `default_config`, `required_user_inputs`, `supported_start_ids`, and `educational_summary`.

#### Scenario: Catalog item contract shape is fixed before implementation
- **WHEN** a contributor inspects the gameplay contracts for phase-1 catalog items
- **THEN** those exact fields are present and the frozen item records use `default_config` rather than an alternate payload-only schema

### Requirement: The Exact Phase-1 Catalog Records Are Frozen
The phase-1 sandbox catalog SHALL encode these exact records:

- `place_heater_cooler`: `title = "Heater/cooler unit"`, `item_kind = "unit_blueprint"`, `apply_kind = "add_process"`, `default_config = {"unit_type": "HeaterCooler", "unit_module": "modular_simulation.unit_processes.thermal.heater_cooler", "constructor_payload": {"mode": "temperature", "external_outlet_temperature": 325.0, "pressure_drop": 0.0}}`, `required_user_inputs = ("process_id",)`, `supported_start_ids = ("phase1_process_sandbox_v1", "heater_flash_tutorial_start_v1")`, summary `single-inlet single-outlet heater/cooler with explicit outlet-temperature boundary`
- `place_flash_drum`: `title = "Flash drum unit"`, `item_kind = "unit_blueprint"`, `apply_kind = "add_process"`, `default_config = {"unit_type": "FlashDrum", "unit_module": "modular_simulation.unit_processes.separation.flash_drum", "constructor_payload": {"thermal_mode": "isothermal", "imposed_pressure": 101325.0, "imposed_temperature": 320.0}}`, `required_user_inputs = ("process_id",)`, `supported_start_ids = ("phase1_process_sandbox_v1", "heater_flash_tutorial_start_v1")`, summary `two-product flash separator with explicit imposed pressure and temperature boundaries`
- `place_heat_exchanger`: `title = "Heat exchanger unit"`, `item_kind = "unit_blueprint"`, `apply_kind = "add_process"`, `default_config = {"unit_type": "HeatExchanger", "unit_module": "modular_simulation.unit_processes.thermal.heat_exchanger", "constructor_payload": {"flow_arrangement": "counter", "ua": 7500.0}}`, `required_user_inputs = ("process_id",)`, `supported_start_ids = ("phase1_process_sandbox_v1",)`, summary `counter-current dual-stream heat exchanger with explicit UA parameter`
- `place_component_separator`: `title = "Component separator unit"`, `item_kind = "unit_blueprint"`, `apply_kind = "add_process"`, `default_config = {"unit_type": "ComponentSeparator", "unit_module": "modular_simulation.unit_processes.separation.component_separator", "constructor_payload": {"configured_split_fraction_targets": {"mode": "equal_split"}}}`, `required_user_inputs = ("process_id",)`, `supported_start_ids = ("phase1_process_sandbox_v1",)`, summary `abstract split-fraction separator for material-balance and recovery tradeoff teaching`
- `place_merge_junction_2x1`: `title = "Merge junction (2x1)"`, `item_kind = "junction_blueprint"`, `apply_kind = "add_junction"`, `default_config = {"inlet_ports": ("feed_a", "feed_b"), "outlet_ports": ("out",)}`, `required_user_inputs = ("junction_id",)`, `supported_start_ids = ("phase1_process_sandbox_v1",)`, summary `explicit two-inlet merge junction using the canonical junction topology model`
- `place_split_junction_1x2`: `title = "Split junction (1x2)"`, `item_kind = "junction_blueprint"`, `apply_kind = "add_junction"`, `default_config = {"inlet_ports": ("in",), "outlet_ports": ("product", "recycle")}`, `required_user_inputs = ("junction_id",)`, `supported_start_ids = ("phase1_process_sandbox_v1",)`, summary `explicit one-inlet split junction with named product and recycle branches`
- `build_process_line`: `title = "Process line"`, `item_kind = "line"`, `apply_kind = "connect_configure_line"`, `default_config = {"radius_m": 0.05, "length_m": 1.0}`, `required_user_inputs = ("source", "target")`, `supported_start_ids = ("phase1_process_sandbox_v1", "heater_flash_tutorial_start_v1")`, summary `explicit process line with geometry-owned pressure-loss implications`
- `install_line_pump`: `title = "Line pump overlay"`, `item_kind = "line_overlay"`, `apply_kind = "attach_line_pump"`, `default_config = {"initial_pump_speed": 80000.0}`, `required_user_inputs = ("line_id", "pump_id")`, `supported_start_ids = ("phase1_process_sandbox_v1", "recycle_purge_tutorial_start_v1")`, summary `line-owned hydraulic boost overlay, not a stand-alone unit family`
- `install_line_valve`: `title = "Line valve overlay"`, `item_kind = "line_overlay"`, `apply_kind = "attach_line_valve"`, `default_config = {"minimum_open_fraction": 0.0, "maximum_open_fraction": 1.0, "initial_open_fraction": 1.0}`, `required_user_inputs = ("line_id", "valve_id")`, `supported_start_ids = ("phase1_process_sandbox_v1", "recycle_purge_tutorial_start_v1")`, summary `line-owned throttling valve using the existing runtime/control surface`
- `install_line_heat_actuator`: `title = "Line heat-actuator overlay"`, `item_kind = "line_overlay"`, `apply_kind = "attach_line_heat_actuator"`, `default_config = {"initial_heat_rate": 0.0}`, `required_user_inputs = ("line_id", "heat_actuator_id")`, `supported_start_ids = ("phase1_process_sandbox_v1",)`, summary `line-owned heat actuator overlay using the explicit heat-actuator substrate`
- `install_sampled_delayed_sensor`: `title = "Sampled delayed sensor"`, `item_kind = "sensor"`, `apply_kind = "create_bind_sensor"`, `default_config = {"sensor_type": "SampledDelayedSensor", "sensor_module": "modular_simulation.components.sensors.sampled_delayed_sensor", "sensor_config": {"sampling_period": 0.2, "deadtime": 0.0}}`, `required_user_inputs = ("sensor_id", "signal_key")`, `supported_start_ids = ("phase1_process_sandbox_v1", "reactor_control_tutorial_start_v1")`, summary `sampled and delayed measurement point for instrumentation tutorials and controller feedback`
- `install_pid_controller`: `title = "PID controller"`, `item_kind = "controller"`, `apply_kind = "create_bind_activate_controller"`, `default_config = {"controller_type": "PIDController", "controller_module": "modular_simulation.components.control_system.controllers", "controller_config": {"Kp": 1.0, "Ti": 5.0, "Td": 0.0}}`, `required_user_inputs = ("controller_id", "signal_key", "actuator_tag")`, `supported_start_ids = ("phase1_process_sandbox_v1", "reactor_control_tutorial_start_v1")`, summary `standard PID controller bound through the existing runtime wiring APIs`

#### Scenario: Catalog records are frozen exactly
- **WHEN** a contributor inspects any phase-1 catalog item
- **THEN** its title, kind, apply kind, payload, required inputs, supported start ids, and educational summary match the exact frozen record above

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

### Requirement: Generic Backend-Session Helper Scope Is Explicit
Phase 1 SHALL add only the generic `TxHandle` helper surface required by the frozen catalog: `add_junction`, `attach_line_pump`, and `attach_line_heat_actuator`, all reachable through `PlantBackendSession.begin_tx()`.

#### Scenario: Missing helper work stays substrate-level and policy-free
- **WHEN** a contributor inspects the gameplay pack and backend-session facade changes
- **THEN** any new helper methods are generic transaction helpers and no gameplay pricing, inventory, tutorial timing, or economics policy is added to `PlantBackendSession`

#### Scenario: New helper methods follow the existing transaction lifecycle
- **WHEN** a caller uses one of the new helper methods on a transaction handle
- **THEN** the helper enqueues a mutation, appears in transaction preview output, and applies through `commit()` without requiring new top-level `PlantBackendSession` convenience methods

### Requirement: Phase-1 Sandbox Boundaries Exclude Open-Ended Chemistry Authoring
The phase-1 sandbox SHALL exclude arbitrary process factories, stand-alone pump/valve unit families, freeform feed-chemistry authoring beyond the frozen starts, and general purchasable CSTR/PFR/Van-de-Vusse placement.

#### Scenario: Scope review keeps later-phase sandbox ambitions deferred
- **WHEN** a contributor reviews the phase-1 sandbox contract
- **THEN** those larger systems remain explicit follow-on work rather than implicit implementation freedom

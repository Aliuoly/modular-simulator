# Units and components

## Purpose

This capability defines the player-buildable units and components catalog and related start metadata for phase-1 gameplay.

## Requirements

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
The phase-1 sandbox catalog SHALL contain exactly `place_heater_cooler`, `place_flash_drum`, `place_heat_exchanger`, `place_component_separator`, `place_merge_junction_2x1`, `place_split_junction_1x2`, `build_process_line`, `install_line_pump`, `install_line_valve`, `install_line_heat_actuator`, `install_sampled_delayed_sensor`, `install_pid_controller`, `place_holding_tank`, and `place_quality_control_lab`.

#### Scenario: No hidden or deferred build items leak into phase 1
- **WHEN** the catalog is inspected
- **THEN** it contains exactly those 14 item ids and no arbitrary process-factory, stand-alone pump/valve-unit, or tutorial-only mechanics

### Requirement: Sandbox Catalog Items Use Typed Apply Kinds Grounded In Repo APIs
Each catalog item SHALL declare one typed `apply_kind` grounded in current repo surfaces: `add_process`, `add_junction`, `connect_configure_line`, `attach_line_pump`, `attach_line_valve`, `attach_line_heat_actuator`, `create_bind_sensor`, or `create_bind_activate_controller`.

#### Scenario: Catalog items trace back to supported substrate operations
- **WHEN** a contributor inspects a catalog item definition
- **THEN** the item’s apply kind maps to an existing repo operation or to a thin generic backend-session helper

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
- `place_holding_tank`: `title = "Holding tank"`, `item_kind = "unit_blueprint"`, `apply_kind = "add_process"`, `default_config = {"unit_type": "HoldingTank", "unit_module": "modular_simulation.unit_processes.storage.holding_tank", "constructor_payload": {}}`, `required_user_inputs = ("process_id",)`, `supported_start_ids = ()`, summary `single-inlet single-outlet buffer vessel for future tank-mediated material holdup and transfer`
- `place_quality_control_lab`: `title = "Quality control lab"`, `item_kind = "unit_blueprint"`, `apply_kind = "add_process"`, `default_config = {"unit_type": "QualityControlLab", "unit_module": "modular_simulation.unit_processes.analysis.quality_control_lab", "constructor_payload": {"minimum_purity_mol_fraction": 0.95}}`, `required_user_inputs = ("process_id", "tracked_component_id")`, `supported_start_ids = ()`, summary `process-stream quality gate that counts accepted moles toward later research progress and rejects off-spec material to disposal`

#### Scenario: Catalog records are frozen exactly
- **WHEN** a contributor inspects any phase-1 catalog item
- **THEN** its title, kind, apply kind, payload, required inputs, supported start ids, and educational summary match the exact frozen record above

### Requirement: Add-Process Unit Blueprints Remain Runtime-Authoritative
Phase-1 gameplay SHALL interpret `unit_blueprint` catalog records with `apply_kind = "add_process"` from their frozen runtime metadata rather than a slice-hardcoded default port schema, and SHALL remain general to each unit's declared inlet/outlet shape instead of imposing a broader single-inlet/single-outlet rule.

#### Scenario: Holding tank staging uses its real declared ports
- **WHEN** the module-private helper in `src/modular_simulation/gameplay/realtime_service.py` stages `place_holding_tank` from the shared sandbox catalog for `_install_unit()`
- **THEN** it resolves `unit_module = "modular_simulation.unit_processes.storage.holding_tank"`, `unit_type = "HoldingTank"`, and `constructor_payload = {}` from the catalog record
- **AND** it uses the unit's real ports `("inlet",)` and `("outlet",)` instead of forcing generic `("in",)` and `("out",)`

#### Scenario: Constructor payload remains part of runtime-authoritative unit metadata
- **WHEN** the same module-private realtime-service helper resolves `place_quality_control_lab` from the shared sandbox catalog for a non-public staging proof
- **THEN** it preserves `constructor_payload = {"minimum_purity_mol_fraction": 0.95}` exactly from the catalog record alongside `unit_module` and `unit_type`
- **AND** that constructor metadata remains runtime-authoritative even though no current start exposes the quality-control lab yet

#### Scenario: Runtime-authoritative unit metadata does not widen the live slice by itself
- **WHEN** contributors inspect the staged `add_process` runtime seam for cataloged units
- **THEN** catalog metadata remains valid even for items that no current start exposes yet
- **AND** the current live start allowlists and playable build-item lists remain unchanged until a later change explicitly widens them

#### Scenario: Runtime-authoritative placement does not freeze single-port topology as a general rule
- **WHEN** contributors inspect the staged `add_process` runtime seam beyond the current HoldingTank proof case
- **THEN** the seam derives whatever ports a cataloged unit implementation declares
- **AND** the current single-inlet/single-outlet HoldingTank proof case does not imply that future tank or unit-blueprint variants may only expose one inlet and one outlet

### Requirement: Catalog-Only Foundation Items Do Not Change Current Starts
The additive foundation items introduced by this change SHALL remain unavailable on every current sandbox and tutorial start.

#### Scenario: Current start allowlists remain unchanged
- **WHEN** a contributor inspects `phase1_process_sandbox_v1`, `heater_flash_tutorial_start_v1`, `reactor_control_tutorial_start_v1`, and `recycle_purge_tutorial_start_v1`
- **THEN** none of those start records include `place_holding_tank` or `place_quality_control_lab` in `allowed_item_ids`

### Requirement: Foundation Units Participate As Ordinary Connected Process Nodes
`HoldingTank` and `QualityControlLab` SHALL expose explicit `hydraulic_participation` declarations so they can compile as ordinary connected process nodes under the current connection contract.

#### Scenario: Holding tank declares explicit connected-unit participation
- **WHEN** a contributor inspects `HoldingTank`
- **THEN** it declares explicit hydraulic participation for `inlet` and `outlet`
- **AND** it declares exactly one balancing group over `("inlet", "outlet")`
- **AND** compile does not depend on undeclared passive-port inference or a topology exception

#### Scenario: Quality control lab declares explicit connected-unit participation
- **WHEN** a contributor inspects `QualityControlLab`
- **THEN** it declares explicit hydraulic participation for `inlet` and `reject_outlet`
- **AND** it declares exactly one balancing group over `("inlet", "reject_outlet")`
- **AND** compile does not depend on undeclared passive-port inference or a topology exception

### Requirement: Holding Tank Freezes Minimum Holdup Behavior
`HoldingTank` SHALL behave as a minimal physically transferable single-inlet single-outlet holdup unit owned by the simulation layer and advanced through the repo-standard differential process-model lifecycle.

#### Scenario: Stored inventory is conserved amount state
- **WHEN** the holding tank advances over a macro step
- **THEN** stored inventory advances as conserved differential amount state through the unit’s `ProcessModel.step()` / adaptive internal ODE solver path
- **AND** stored inventory updates from material-balance dynamics rather than from sampled instantaneous `molar_flow_rate` values
- **AND** the unit stores conserved holdup amount state rather than gameplay-owned placeholder inventory.

#### Scenario: Requested outlet demand is clipped by a near-empty depletion guard
- **WHEN** connection runtime applies requested outlet through-flow demand to the tank for its next process step
- **THEN** the tank clips depletion so conserved holdup never steps negative under that requested demand
- **AND** the depletion guard may retain a small positive numerical floor rather than exact zero to stay consistent with repo near-zero conventions
- **AND** downstream transferable outlet flow over a step never exceeds the moles withdrawable above the configured near-empty floor
- **AND** any positive near-zero outlet flow retained at that floor is observability regularization only unless backed by withdrawable holdup above the floor
- **AND** downstream propagation uses the realized outlet state produced by the tank model rather than the raw requested demand.

#### Scenario: Outlet state reflects the well-mixed bulk holdup
- **WHEN** stored holdup contains mixed material from one or more incoming transfers or has been clipped to the near-empty floor
- **THEN** the outlet stream state for the step reflects the current well-mixed bulk tank composition and temperature produced by the unit model
- **AND** realized component withdrawal follows that current mixed-bulk composition on the published species basis
- **AND** near-empty clipping may retain the previous bulk temperature/composition for continuity at the numerical floor
- **AND** that outlet state is a lumped single-bulk approximation for this slice rather than a geometry-, stratification-, or EOS-resolved vessel model
- **AND** the unit does not maintain parallel per-source inventory buckets in the live model.

### Requirement: Quality Control Lab Freezes Pass-Fail Progress Accounting
`QualityControlLab` SHALL use one pass/fail purity rule based on `tracked_component_id` and `minimum_purity_mol_fraction`.

#### Scenario: Threshold-met stream grants whole-stream credit
- **WHEN** the incoming stream purity for `tracked_component_id` is greater than or equal to the configured minimum threshold
- **THEN** the lab increases `accepted_progress_mol` by the entire incoming stream molar amount
- **AND** higher purity above the threshold does not grant additional credit

#### Scenario: Off-spec stream grants no credit
- **WHEN** the incoming stream purity for `tracked_component_id` is below the configured minimum threshold
- **THEN** the lab increases `accepted_progress_mol` by `0.0`

#### Scenario: Lab stays topology-compatible with one outlet
- **WHEN** the quality control lab participates in the current topology model
- **THEN** it exposes exactly one outlet named `reject_outlet`
- **AND** accepted and rejected stream slices both leave through that one outlet boundary in this first pack
- **AND** the unit does not rely on a second accepted-material outlet or a sink-only topology exception

### Requirement: Generic Backend-Session Helper Scope Is Explicit
Phase 1 SHALL add only the generic `TxHandle` helper surface required by the frozen catalog: `add_junction`, `attach_line_pump`, and `attach_line_heat_actuator`, all reachable through `PlantBackendSession.begin_tx()`.

#### Scenario: Missing helper work stays substrate-level and policy-free
- **WHEN** a contributor inspects the gameplay layer and backend-session facade changes
- **THEN** any new helper methods are generic transaction helpers and no gameplay pricing, inventory, tutorial timing, or economics policy is added to `PlantBackendSession`

#### Scenario: New helper methods follow the existing transaction lifecycle
- **WHEN** a caller uses one of the new helper methods on a transaction handle
- **THEN** the helper enqueues a mutation, appears in transaction preview output, and applies through `commit()` without requiring new top-level `PlantBackendSession` convenience methods

### Requirement: Phase-1 Sandbox Boundaries Exclude Open-Ended Chemistry Authoring
The phase-1 sandbox SHALL exclude arbitrary process factories, stand-alone pump/valve unit families, freeform feed-chemistry authoring beyond the frozen starts, and general purchasable CSTR/PFR/Van-de-Vusse placement.

#### Scenario: Scope review keeps later-phase sandbox ambitions deferred
- **WHEN** a contributor reviews the phase-1 sandbox contract
- **THEN** those larger systems remain explicit follow-on work rather than implicit implementation freedom

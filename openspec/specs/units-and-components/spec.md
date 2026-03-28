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
  - `title = "Sweet wet gas main sandbox"`
  - `seed_source_paths = ("examples/unit_process_flowsheet/gas_1_inlet_separator.py", "examples/unit_process_flowsheet/gas_2_teg_dehydration.py", "examples/unit_process_flowsheet/gas_3_jt_low_temperature_separation.py", "examples/unit_process_flowsheet/gas_4_condensate_stabilizer.py")`
  - `starting_topology_summary = "One sweet wet gas feed and five named product sinks are present, but no gas-processing units, line overlays, or connecting lines are preinstalled."`
  - `published_signal_ids = ("sweet_wet_gas_draw_mol_s", "separator_gas_flow_mol_s", "unstabilized_condensate_flow_mol_s", "dry_gas_flow_mol_s", "ngl_liquids_flow_mol_s", "stabilized_condensate_flow_mol_s", "heating_steam_duty_W", "total_normalized_pump_load")`
  - `allowed_item_ids = ("place_inlet_gas_separator", "place_teg_contactor", "place_rich_glycol_flash_tank", "place_lean_rich_glycol_exchanger", "place_teg_regenerator", "install_glycol_circulation_pump", "place_gas_gas_exchanger", "install_jt_valve", "place_low_temperature_separator", "place_condensate_stabilizer", "build_process_line")`
- `heater_flash_tutorial_start_v1`
  - unchanged from the current live tutorial contract
- `reactor_control_tutorial_start_v1`
  - unchanged from the current live tutorial contract
- `recycle_purge_tutorial_start_v1`
  - unchanged from the current live tutorial contract

#### Scenario: Default sandbox metadata is gas-first and tutorials remain separate
- **WHEN** the phase-1 start catalog is inspected
- **THEN** `phase1_process_sandbox_v1` matches the exact gas-first record above and the three tutorial start records remain tutorial-only starts rather than new main-world sandbox variants

### Requirement: The Exact Phase-1 Sandbox Catalog Item Ids Are Frozen
The phase-1 sandbox catalog SHALL contain exactly these live item ids:

- main-world gas ladder items:
  - `place_inlet_gas_separator`
  - `place_teg_contactor`
  - `place_rich_glycol_flash_tank`
  - `place_lean_rich_glycol_exchanger`
  - `place_teg_regenerator`
  - `install_glycol_circulation_pump`
  - `place_gas_gas_exchanger`
  - `install_jt_valve`
  - `place_low_temperature_separator`
  - `place_condensate_stabilizer`
  - `build_process_line`
- retained tutorial-facing legacy items:
  - `place_heater_cooler`
  - `place_flash_drum`
  - `place_heat_exchanger`
  - `place_component_separator`
  - `place_merge_junction_2x1`
  - `place_split_junction_1x2`
  - `install_line_pump`
  - `install_line_valve`
  - `install_line_heat_actuator`
  - `install_sampled_delayed_sensor`
  - `install_pid_controller`

#### Scenario: Main-world gas items coexist with tutorial-only legacy items
- **WHEN** the catalog is inspected
- **THEN** it contains the exact gas ladder item ids required by the main sandbox and still retains the legacy tutorial-facing items needed by the current tutorial starts

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

### Requirement: The Exact Gas-First Main-World Catalog Records Are Frozen
The main-world gas ladder item records SHALL encode these exact records:

- `place_inlet_gas_separator`: `title = "Inlet gas separator"`, `item_kind = "unit_blueprint"`, `apply_kind = "add_process"`, `default_config = {"unit_type": "FlashDrum", "unit_module": "modular_simulation.unit_processes.separation.flash_drum", "constructor_payload": {"thermal_mode": "isothermal", "imposed_pressure": 600000.0, "imposed_temperature": 305.0}}`, `required_user_inputs = ("process_id",)`, `supported_start_ids = ("phase1_process_sandbox_v1",)`, summary `educational proxy for inlet three-phase style separation`
- `place_teg_contactor`: `title = "TEG contactor"`, `item_kind = "unit_blueprint"`, `apply_kind = "add_process"`, `default_config = {"unit_type": "ComponentSeparator", "unit_module": "modular_simulation.unit_processes.separation.component_separator", "constructor_payload": {}}`, `required_user_inputs = ("process_id",)`, `supported_start_ids = ("phase1_process_sandbox_v1",)`, summary `educational proxy for TEG dehydration contactor behavior`
- `place_rich_glycol_flash_tank`: `title = "Rich glycol flash tank"`, `item_kind = "unit_blueprint"`, `apply_kind = "add_process"`, `default_config = {"unit_type": "FlashDrum", "unit_module": "modular_simulation.unit_processes.separation.flash_drum", "constructor_payload": {"thermal_mode": "isothermal", "imposed_pressure": 250000.0, "imposed_temperature": 320.0}}`, `required_user_inputs = ("process_id",)`, `supported_start_ids = ("phase1_process_sandbox_v1",)`, summary `educational proxy for rich glycol degassing support`
- `place_lean_rich_glycol_exchanger`: `title = "Lean/rich glycol exchanger"`, `item_kind = "unit_blueprint"`, `apply_kind = "add_process"`, `default_config = {"unit_type": "HeatExchanger", "unit_module": "modular_simulation.unit_processes.thermal.heat_exchanger", "constructor_payload": {"flow_arrangement": "counter", "ua": 7500.0}}`, `required_user_inputs = ("process_id",)`, `supported_start_ids = ("phase1_process_sandbox_v1",)`, summary `educational proxy for glycol thermal integration`
- `place_teg_regenerator`: `title = "TEG regenerator"`, `item_kind = "unit_blueprint"`, `apply_kind = "add_process"`, `default_config = {"unit_type": "StagewiseDistillationColumn", "unit_module": "modular_simulation.unit_processes.separation.stagewise_distillation", "constructor_payload": {"n_species": 2, "active_contact_height_m": 4.0, "shell_diameter_m": 1.0, "feed_stage_indices": (1,)}}`, `required_user_inputs = ("process_id",)`, `supported_start_ids = ("phase1_process_sandbox_v1",)`, summary `educational proxy for TEG regeneration`
- `install_glycol_circulation_pump`: `title = "Glycol circulation pump"`, `item_kind = "line_overlay"`, `apply_kind = "attach_line_pump"`, `default_config = {"initial_pump_speed": 80000.0}`, `required_user_inputs = ("line_id", "pump_id")`, `supported_start_ids = ("phase1_process_sandbox_v1",)`, summary `line-owned educational proxy for glycol circulation`
- `place_gas_gas_exchanger`: `title = "Gas-gas exchanger"`, `item_kind = "unit_blueprint"`, `apply_kind = "add_process"`, `default_config = {"unit_type": "HeatExchanger", "unit_module": "modular_simulation.unit_processes.thermal.heat_exchanger", "constructor_payload": {"flow_arrangement": "counter", "ua": 9000.0}}`, `required_user_inputs = ("process_id",)`, `supported_start_ids = ("phase1_process_sandbox_v1",)`, summary `educational proxy for pre-JT cold recovery`
- `install_jt_valve`: `title = "JT valve"`, `item_kind = "line_overlay"`, `apply_kind = "attach_line_valve"`, `default_config = {"minimum_open_fraction": 0.0, "maximum_open_fraction": 1.0, "initial_open_fraction": 1.0}`, `required_user_inputs = ("line_id", "valve_id")`, `supported_start_ids = ("phase1_process_sandbox_v1",)`, summary `line-owned educational proxy for JT throttling`
- `place_low_temperature_separator`: `title = "Low-temperature separator"`, `item_kind = "unit_blueprint"`, `apply_kind = "add_process"`, `default_config = {"unit_type": "FlashDrum", "unit_module": "modular_simulation.unit_processes.separation.flash_drum", "constructor_payload": {"thermal_mode": "isothermal", "imposed_pressure": 250000.0, "imposed_temperature": 250.0}}`, `required_user_inputs = ("process_id",)`, `supported_start_ids = ("phase1_process_sandbox_v1",)`, summary `educational proxy for JT low-temperature separation`
- `place_condensate_stabilizer`: `title = "Condensate stabilizer"`, `item_kind = "unit_blueprint"`, `apply_kind = "add_process"`, `default_config = {"unit_type": "StagewiseDistillationColumn", "unit_module": "modular_simulation.unit_processes.separation.stagewise_distillation", "constructor_payload": {"n_species": 2, "active_contact_height_m": 4.0, "shell_diameter_m": 1.0, "feed_stage_indices": (1,)}}`, `required_user_inputs = ("process_id",)`, `supported_start_ids = ("phase1_process_sandbox_v1",)`, summary `educational proxy for condensate stabilization`
- `build_process_line`: unchanged line contract, but `supported_start_ids` SHALL include `phase1_process_sandbox_v1`

#### Scenario: Gas item records are frozen exactly
- **WHEN** a contributor inspects any phase-1 catalog item
- **THEN** its title, kind, apply kind, payload, required inputs, supported start ids, and educational summary match the exact frozen record above

### Requirement: Main-World Gas Starts Stay Seed-Backed
The gas-first main sandbox SHALL remain backed by explicit example provenance rather than synthetic empty metadata.

#### Scenario: Main sandbox provenance points to gas examples
- **WHEN** the default sandbox start builder is inspected
- **THEN** it uses the exact gas example files named in the frozen `seed_source_paths` record and does not reuse unrelated heater/flash or dual-feed example provenance for the main gas ladder

### Requirement: Gas Example Provenance Maps One-To-One To Stage Reachability
Each named gas example SHALL back the stage/product pair or starter-batch research contribution it exists to teach:

- `gas_1_inlet_separator.py` → starter-batch reachability for `separator_gas` and `unstabilized_condensate`
- `gas_2_teg_dehydration.py` → starter-batch reachability for `dry_gas`
- `gas_3_jt_low_temperature_separation.py` → post-unlock reachability for `ngl_liquids`
- `gas_4_condensate_stabilizer.py` → post-unlock reachability for `stabilized_condensate`

#### Scenario: Gas example provenance and progression reachability stay aligned
- **WHEN** a contributor inspects the gas examples, start builders, and progression artifacts together
- **THEN** each example corresponds to the exact stage/product pair above and no gas example is left unassigned to the stage ladder it is meant to prove

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
- **AND** the runtime-authoritative metadata seam does not by itself widen the live playable build-item lists; any playable-slice widening remains an explicit later change.

#### Scenario: Runtime-authoritative placement does not freeze single-port topology as a general rule
- **WHEN** contributors inspect the staged `add_process` runtime seam beyond the current HoldingTank proof case
- **THEN** the seam derives whatever ports a cataloged unit implementation declares
- **AND** the current single-inlet/single-outlet HoldingTank proof case does not imply that future tank or unit-blueprint variants may only expose one inlet and one outlet

### Requirement: Runtime-Authoritative Add-Process Metadata Fails Through Stable Gameplay Errors
Phase-1 gameplay SHALL translate invalid runtime-authoritative metadata resolution for `unit_blueprint` records with `apply_kind = "add_process"` into stable gameplay request errors instead of leaking raw Python import, lookup, or constructor exceptions.

#### Scenario: Runtime-authoritative metadata resolution stays on the stable gameplay error surface
- **WHEN** the gameplay build path uses the module-private helper in `src/modular_simulation/gameplay/realtime_service.py` to resolve cataloged `add_process` unit metadata and encounters missing configured module-target resolution, missing configured exported unit type, or constructor-payload validation failure
- **THEN** the gameplay layer fails the request with `SandboxRequestError(error_code="invalid_config", ...)`
- **AND** the helper remains module-private and runtime-authoritative rather than introducing a second public metadata surface

#### Scenario: Stable metadata failure translation does not widen the live slice
- **WHEN** contributors inspect the invalid-metadata hardening for `add_process` unit blueprints
- **THEN** no new public build items, start allowlists, session methods, or error-code families are introduced by that hardening

### Requirement: Public Add-Process Exposure Follows Cataloged Family Support
The playable gameplay layer SHALL expose current public `unit_blueprint/add_process` items from the bound start's `allowed_item_ids`, filtered by the approved public add-process family, through one family-driven placement path instead of a heater/flash-only public whitelist.

#### Scenario: Sandbox public unit builds widen to the current approved add-process set
- **WHEN** contributors inspect the current playable sandbox build list after 6ei
- **THEN** it includes exactly `place_heater_cooler`, `place_flash_drum`, and `place_heat_exchanger` from the cataloged `add_process` family
- **AND** it does not implicitly expose unsupported-start items such as `place_holding_tank` or `place_quality_control_lab`.

### Requirement: Public Line Wiring Uses Real Named Ports For Exposed Units
The 6ei playable slice SHALL wire publicly exposed units against their runtime-declared named ports rather than an implicit gameplay-only `.in` / `.out` alias.

#### Scenario: Public unit families expose real endpoint names for wiring
- **WHEN** contributors inspect the public 6ei line contract for exposed units
- **THEN** heater/cooler wiring uses `inlet` and `outlet`
- **AND** flash-drum wiring uses `inlet`, `vapor_outlet`, and `liquid_outlet`
- **AND** heat-exchanger wiring uses `hot_inlet`, `cold_inlet`, `hot_outlet`, and `cold_outlet`
- **AND** bare process ids are not treated as a valid public alias for any non-boundary unit endpoint.

#### Scenario: Unknown endpoints fail as invalid wiring requests
- **WHEN** contributors inspect the public 6ei wiring error contract
- **THEN** malformed endpoint strings, unknown process ids, unknown boundaries, and unknown process-port combinations fail on the stable gameplay `invalid_config` path rather than inventing a new public error family.

### Requirement: Deferred Separator And Non-Add-Process Families Remain Deferred
The 6ei playable widening SHALL not implicitly pull deferred separator or non-add-process families into the public slice.

#### Scenario: Deferred separator, sensor, controller, junction, and overlay families remain deferred
- **WHEN** contributors inspect the 6ei public build widening
- **THEN** `place_component_separator`, `install_sampled_delayed_sensor`, `install_pid_controller`, `install_line_pump`, `install_line_valve`, `install_line_heat_actuator`, `place_merge_junction_2x1`, and `place_split_junction_1x2` are not implicitly pulled into the current playable build surface by the add-process refactor.

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
`HoldingTank` SHALL behave as a real single-inlet single-outlet holdup unit foundation.

#### Scenario: Outlet flow is bounded by stored holdup
- **WHEN** the holding tank advances with finite stored inventory
- **THEN** any outlet flow comes only from stored holdup
- **AND** outlet flow for the simulated step never exceeds available holdup

#### Scenario: Empty tank does not invent discharge
- **WHEN** the holding tank has zero stored holdup and no incoming material for the step
- **THEN** the outlet flow is zero

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

### Requirement: Distillation-Column Foundation Work Targets Dynamic Stagewise Behavior
This change SHALL target one monolithic `StagewiseDistillationColumn` with multicomponent, stage-by-stage dynamic behavior and SHALL NOT define a lumped main model as the completion contract.

#### Scenario: Dynamic model boundary is stage-by-stage and multicomponent
- **WHEN** contributors inspect the distillation-column contract for this change
- **THEN** the live dynamic RHS is defined by stage-by-stage component balances with a named stagewise VLE closure
- **AND** the contract remains monolithic (single column unit boundary) rather than split into separately placeable tower/condenser/reboiler units in this pack
- **AND** non-key species remain explicit in feeds, stage inventories, and both products
- **AND** Fenske/Underwood/Gilliland/Hengstebeck-Geddes are not specified as the live dynamic closure.

### Requirement: Multi-Feed Assignment Is First-Class Column Behavior
The dynamic distillation-column contract SHALL support multiple feed inputs and configurable feed-stage assignment (feed height/stage).

#### Scenario: Multi-feed stage assignment is part of runtime behavior
- **WHEN** a runtime configures more than one feed on the distillation column
- **THEN** each feed has an explicit assigned stage (or equivalent feed-height mapping)
- **AND** feed assignment participates in the live dynamic material-balance behavior rather than metadata-only bookkeeping.

### Requirement: Realism Boundary Is Frozen For This Slice
This change SHALL freeze a material-balance-first dynamic column boundary with two products, duty-limited condenser surrogate + reflux drum, partial-equilibrium kettle reboiler + bottoms sump, and constant-molar-overflow first closure.

#### Scenario: Initial closure is near-ideal unless stronger VLE is explicitly frozen
- **WHEN** contributors inspect the model closure assumptions in this change
- **THEN** near-ideal/constant-relative-volatility-first closure is acceptable as the initial slice
- **AND** the contract does not require rigorous full MESH energy fidelity in this change.

### Requirement: Reflux And Product Topology Seams Are Explicit Runtime Contract
The monolithic `StagewiseDistillationColumn` SHALL provide explicit reflux and product withdrawal seams as part of runtime behavior.

#### Scenario: Reflux and withdrawal topology is not implicit bookkeeping
- **WHEN** contributors inspect runtime seam requirements
- **THEN** reflux liquid has explicit unit-local boundary seam fields for outlet and reflux-return requests
- **AND** distillate withdrawal is modeled as external withdrawal from reflux-drum holdup
- **AND** bottoms withdrawal is modeled as external withdrawal from bottoms-sump holdup
- **AND** reflux return, distillate withdrawal, and bottoms withdrawal remain liquid-phase and holdup-bounded rather than bypassing their owning inventories.

### Requirement: Condenser/Reboiler Actuation Is Direct-Duty Service Coupled Into RHS
Condenser and reboiler actuation in this change SHALL be modeled as unit-local duty-request boundary fields coupled into the dynamic RHS.

#### Scenario: Utility actuation contract is explicit and runtime-owned
- **WHEN** condenser or reboiler actuation is configured
- **THEN** runtime behavior applies unit-local duty-request boundary fields into the monolithic stagewise RHS under the constant-molar-overflow slice
- **AND** surrogate condensation/boilup rates remain bounded by available vapor/liquid inventory
- **AND** duty service semantics do not create or destroy component moles
- **AND** the contract does not require controller-proof acceptance in this change.

### Requirement: Ratio Fields Are Reference/Derived Only
`reflux_ratio` and `boilup_ratio` SHALL be initialization/reference/derived-observable fields and SHALL NOT be treated as live runtime actuation knobs.

#### Scenario: Runtime actuation authority uses explicit seams instead of ratio knobs
- **WHEN** live runtime actuation is evaluated for the dynamic column
- **THEN** explicit unit-local boundary request fields plus external material-routing seams provide runtime actuation authority
- **AND** any exposed `reflux_ratio` and `boilup_ratio` values are derived from actual runtime flows
- **AND** `reflux_ratio` and `boilup_ratio` remain non-actuating in runtime.

### Requirement: Geometry Semantics Are Explicit And Non-Misleading
`active_contact_height_m` SHALL control tray-equivalent stage count under fixed tray spacing, and `shell_diameter_m` SHALL control area/holdup/capacity effects.

#### Scenario: Geometry wording avoids false selectivity claims
- **WHEN** geometry fields are interpreted in this change contract
- **THEN** `active_contact_height_m` maps to effective contacting stages
- **AND** `shell_diameter_m` uses an area-scaled capacity proxy heuristic for throughput/holdup limits
- **AND** shell width is not framed as directly changing thermodynamic selectivity.

### Requirement: Pressure Contract Guarantees Dynamic Column Pressure Minimum
The minimum guaranteed pressure contract SHALL expose one shared dynamic `column_pressure_pa` used across stages and ports.

#### Scenario: Stagewise pressure implementations remain allowed
- **WHEN** a future implementation provides stagewise dynamic pressure treatment
- **THEN** it remains compliant if it preserves the minimum shared dynamic pressure contract at interfaces
- **AND** this change text does not forbid the more natural stagewise treatment.

### Requirement: Distillation Runtime Semantics Are Stagewise-Only With No Shortcut Shim
This capability SHALL treat `StagewiseDistillationColumn` as the only runtime distillation behavior path and SHALL NOT reintroduce a `ShortcutDistillation` class, alias, or compatibility shim.

#### Scenario: Completion cannot rely on a shortcut compatibility path
- **WHEN** implementation or tests evaluate dynamic distillation behavior
- **THEN** completion requires stagewise runtime behavior from `StagewiseDistillationColumn`
- **AND** no `ShortcutDistillation` runtime/shim pathway is required or preserved.

### Requirement: Current Gameplay Gating Stays Unchanged In This Change
`place_shortcut_distillation_column` SHALL keep its current hide/reject gating on topology-only starts in this change.

#### Scenario: Foundation identity is preserved without premature exposure
- **WHEN** contributors inspect current supported build lists and start-allowlist behavior
- **THEN** `place_shortcut_distillation_column` remains a foundation identity with existing hide/reject behavior
- **AND** current topology-only starts do not gain public distillation-column exposure in this change.

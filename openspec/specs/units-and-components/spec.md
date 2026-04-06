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

### Requirement: Howard 1970 Comparison Model Preserves Published Plate-Balance Family
`Howard1970DistillationColumn` SHALL implement the Howard (1970) single-column dynamic plate-balance family with its published equilibrium, tray-efficiency, bubble-point, feed-plate, and constant-volume-holdup forms rather than collapsing the model into the repo's reduced-order stagewise closure.

#### Governing Equations
- `GE-H70-1` General component balance (Howard Eq. 5):

  `R_j * dx_{j,i}/dt = V_{j+1} * (y_{j+1,i} - x_{j,i}) + L_{j-1} * (x_{j-1,i} - x_{j,i}) - V_j * (y_{j,i} - x_{j,i})`

- `GE-H70-2` Equilibrium relation (Howard Eq. 6):

  `y^*_{j,i} = K_i(T_j, P_j) * x_{j,i}`

- `GE-H70-3` Vaporization efficiency (Howard Eq. 7):

  `E^o_{j,i} = y_{j,i} / y^*_{j,i}`

- `GE-H70-4` Murphree efficiency (Howard Eq. 8):

  `E^M_{j,i} = (y_{j,i} - y_{j-1,i}) / (y^*_{j,i} - y_{j-1,i})`

- `GE-H70-5` Liquid enthalpy and algebraic energy-balance family (Howard Eqs. 9 and 14):

  `h_j = sum_i x_{j,i} * f_i(T_j) + phi_M(x_{j,1} ... x_{j,NC})`

  `0 = V_{j+1} * ((H_{j+1} - h_j) - A_j) + L_{j-1} * ((h_{j-1} - h_j) - B_j) - V_j * ((H_j - h_j) - C_j) - Q_{Lj}`

- `GE-H70-6` Bubble-point closure and implicit temperature-derivative family (Howard Eqs. 15–21):

  `sum_i K_i(T_j) * x_{j,i} = 1`

  `dT_j/dx_{j,i} = -(dZ/dx_{j,i}) / (dZ/dT_j)`

  with

  `Z(T_j, x_j) = sum_{m=1}^{NC-1} [K_m(T_j) - K_c(T_j)] * x_{j,m} + K_c(T_j)`

  and the paper's Eq. (21) working expression used over the `NC - 1` independent components.

- `GE-H70-7` Feed-plate extension (Howard Eqs. 22–25):

  `R_j * dx_{j,i}/dt = V_{j+1} * (y_{j+1,i} - x_{j,i}) + L_{j-1} * (x_{j-1,i} - x_{j,i}) + F * (x_{F,i} - x_{j,i}) - V_j * (y_{j,i} - x_{j,i})`

  `dR_j/dt = V_{j+1} + L_{j-1} + F - V_j - L_j`

  `d(R_j * h_j)/dt = V_{j+1} * H_{j+1} + L_{j-1} * h_{j-1} + F * h_F - V_j * H_j - L_j * h_j + Q_{Lj}`

  `+ F * ((h_F - h_j) - D_j)`

- `GE-H70-8` Constant-volume-holdup closure (Howard Eqs. 26–29, with Eq. 30 optional only as a source-exact or deterministically derived shorthand):

  `R_j = V_bar * v(x_j, T_j)`

  `v(x_j, T_j) = sum_i x_{j,i} * v_i(T_j)`

  `-V_bar * d(v(x_j, T_j)) / dt = V_{j+1} + L_{j-1} - V_j - L_j`

  `0 = V_{j+1} * (1 - F_j) + L_{j-1} * (1 - G_j) - V_j * (1 - K_j) - L_j`

  with the first executable slice required to satisfy the direct Eq. (28) derivative balance and the Eq. (29) rearranged closure without inventing surrogate coefficient families.

  If the Eq. (30) shorthand is used, `F_j`, `G_j`, and `K_j` SHALL come from the source-exact or deterministically derived coefficient family implied by the Eq. (28) expansion; heuristic surrogate coefficients do **not** satisfy this requirement.

- Symbols and assumptions:
  - `j` = plate index, `i` = component index
  - `R_j` = plate liquid holdup
  - `x_{j,i}`, `y_{j,i}`, `y^*_{j,i}` = liquid, actual vapor, and equilibrium vapor compositions
  - `V_j`, `L_j` = vapor and liquid flow rates
  - `h_j`, `H_j` = liquid and vapor enthalpies
  - `Q_{Lj}` = plate heat-loss term
  - vapor holdup is neglected, liquid on each plate is well mixed, and vapor-liquid relation is established instantaneously as in the paper
  - this change freezes Howard's constant-volume-holdup executable slice around direct Eq. (28) and Eq. (29); it does not require every alternative Howard specification family in the first implementation.

#### Scenario: Howard runtime behavior follows the published balance family
- **WHEN** implementation or tests evaluate `Howard1970DistillationColumn`
- **THEN** its dynamic plate behavior follows `GE-H70-1` through `GE-H70-8`
- **AND** the model does not replace those equations with the repo's existing reduced-order stagewise hydraulic and thermal closure family
- **AND** Howard's feed-plate and constant-volume-holdup forms remain explicit rather than implied by prose
- **AND** the constant-volume-holdup runtime closure satisfies Howard Eq. (28) and Eq. (29) directly unless a source-exact or deterministically derived Eq. (30) shorthand is used.

### Requirement: Gani 1986 Comparison Model Preserves Published Generalized Column Family
`Gani1986DistillationColumn` SHALL implement the Gani, Ruiz, Cameroni (1986) single-column open-loop generalized column family with explicit plate balances, algebraic thermodynamic/property closures, generic hydraulic dependencies, reflux-drum/reboiler balances, and bubble-cap appendix hydraulics rather than collapsing the model into the repo's reduced-order stagewise closure.

#### Governing Equations
- `GE-G86-1` Component mass balance (Gani Eq. 1):

  `dC^c_{p,i}/dt = F^c_{V,p} * Y^c_{F,p,i} + F^c_{L,p} * x^c_{F,p,i} + V^c_{p-1} * y^c_{p-1,i} + E^c_{L,p-1} * x^c_{p-1,i} + L^c_{p+1} * x^c_{p+1,i} + E^c_{V,p+1} * y^c_{p+1,i} - (P^c_{V,p} + V^c_p + E^c_{V,p}) * y^c_{p,i} - (P^c_{L,p} + L^c_p + E^c_{L,p}) * x^c_{p,i}`

- `GE-G86-2` Total energy balance (Gani Eq. 2):

  `dC^c_{E,p}/dt = F^c_{V,p} * H^c_{F,p} + F^c_{L,p} * h^c_{F,p} + V^c_{p-1} * H^c_{p-1} + E^c_{L,p-1} * h^c_{p-1} + L^c_{p+1} * h^c_{p+1} + E^c_{V,p+1} * H^c_{p+1} - (P^c_{V,p} + V^c_p + E^c_{V,p}) * H^c_p - (P^c_{L,p} + L^c_p + E^c_{L,p}) * h^c_p`

- `GE-G86-3` Total mass balance (Gani Eq. 3):

  `dC^c_{T,p}/dt = F^c_{V,p} + F^c_{L,p} + V^c_{p-1} + E^c_{L,p-1} + L^c_{p+1} + E^c_{V,p+1} - V^c_p - E^c_{L,p} - L^c_p - E^c_{V,p} - P^c_{V,p} - P^c_{L,p}`

- `GE-G86-4` Definitions and Murphree efficiency (Gani Eqs. 4–8):

  `C^c_{T,p} = sum_i C^c_{p,i}`

  `C^c_{E,p} = h^c_p * C^c_{T,p}`

  `sum_i x^c_{p,i} = sum_i y^c_{p,i} = 1`

  `x^c_{p,i} = C^c_{p,i} / C^c_{T,p}`

  `h^c_p = C^c_{E,p} / C^c_{T,p}`

  `y^{*c}_{p,i} = (y^c_{p,i} - y^c_{p-1,i}) / ME^c_p + y^c_{p-1,i}`

- `GE-G86-5` Equilibrium, enthalpy, density, and molecular-weight closures (Gani Eqs. 9–18):

  `y^{*c}_{p,i} = K^c_{p,i} * x^c_{p,i}`

  `K^c_{p,i} = f(x^c_p, y^c_p, Theta^c_p, Pi^c_p)`

  `H^c_p = f(y^c_p, Theta^c_p, Pi^c_p)`

  `h^c_p = f(x^c_p, Theta^c_p, Pi^c_p)`

  `rho_bar^c_{L,p} = sum_i rho^c_{L,p,i} * x^c_{p,i}`

  `rho_bar^c_{V,p} = sum_i rho^c_{V,p,i} * y^c_{p,i}`

  `rho^c_{L,p,i} = f(Pi^c_p, R, Theta^c_p, Z^c_{L,p,i})`

  `rho^c_{V,p,i} = f(Pi^c_p, R, Theta^c_p, Z^c_{V,p,i})`

  `M_bar^c_{L,p} = sum_i M^c_{L,p,i} * x^c_{p,i}`

  `M_bar^c_{V,p} = sum_i M^c_{V,p,i} * y^c_{p,i}`

- `GE-G86-6` Generic hydraulic dependency family (Gani Eq. 19):

  `DeltaPi^c_p = Pi^c_{p-1} - Pi^c_p`

  `V^c_p = f(DeltaPi^c_p, C^c_{T,p}, plate geometry)`

  `L^c_p = f(C^c_{T,p}, plate geometry)`

  `L^c_{w,p} = f(C^c_{T,p}, V^c_p, plate geometry)`

  `V^c_{f,p} = f(V^c_p, L^c_p, plate geometry)`

  `E^c_{L,p} = f(C^c_{T,p}, DeltaPi^c_p, plate geometry)`

  `E^c_{V,p} = f(C^c_{T,p}, DeltaPi^c_p, plate geometry)`

- `GE-G86-7` Reflux-drum and reboiler balances (Gani Eqs. 20–21):

  `dM^c_{RD,i}/dt = V^c_{N_p} * y^c_{N_p,i} - (L^c_0 + D^c) * x^c_{D,i}`

  `dM^c_{RB,i}/dt = L^c_1 * x^c_{1,i} - B^c * x^c_{B,i} - V^c_B * y^c_{B,i}`

- `GE-G86-8` Bubble-cap hydraulic subset (Gani Appendix A.1–A.8):

  `h_ow = ((L^D_p) / (W * rho_{L,p} * 999.0))^(2/3)`

  `h^da_p = (0.003 / 12.0) * (g^L / (100.0 * A_D1))^2`

  `C_{T,p} = beta_p * (h_w + h_ow) * (A_p * rho_{L,p} / M_{L,p}) + (h^T_p + h^da_p + h^L_p - l) * (rho_{L,p} * A_D2 / M_{L,p})`

  If `h^L_{p-1} < h_bc`, the downcomer is not sealed and

  `h^T_p = (6.0 / (g * rho_{L,p} * rho_{V,p})) * (V^D_p * M_{V,p} / (3600.0 * A_D2))^2 * [0.7 * (A_D2 / A_D1)^2 + 1.2 + f_0 * (l_D / d_be)]`

  `U_f = F_1 * F_2 * (sigma_{L,p} / rho_{L,p})^(1/2)`

  `h^L_p = h^{bc}_p + h^{op}_p + h^{hu}_p`

  `h^{aL}_p = beta_p * (h_w + h_ow + Delta p / 2.0)`

  `Q'_p = 2.36 * (A_h / h_dc) * ((rho_{L,p} - rho_{V,p}) / rho_{V,p})^(1/2) * [(2 / (31 + R_s)) * (h^{os}_p)^(3/2) + (4 / (151 + R_s)) * (1 - R_s * h^{os}_p / h_sh)^(5/2)]`

  with `R_s = d_st / d_tb`.

- Symbols and assumptions:
  - `c` = column index, `p` = plate index, `i` = component index
  - `C^c_{p,i}`, `C^c_{T,p}`, `C^c_{E,p}` = component, total-holdup, and total-energy plate states
  - `x^c_{p,i}`, `y^c_{p,i}`, `y^{*c}_{p,i}` = liquid, actual vapor, and equilibrium vapor compositions
  - `Theta^c_p`, `Pi^c_p` = plate temperature and pressure
  - `V^c_p`, `L^c_p` = vapor and liquid plate flows
  - `ME^c_p` = Murphree efficiency in the paper notation
  - the paper assumptions of negligible vapor holdup, thermal equilibrium, and perfect mixing apply
  - this change freezes a single-column open-loop bubble-cap slice; controllers, multiple columns, start-up procedures, external wall heat-transfer procedures, and alternate plate families remain deferred.

#### Scenario: Gani runtime behavior follows the published generalized family
- **WHEN** implementation or tests evaluate `Gani1986DistillationColumn`
- **THEN** its dynamic plate and hydraulic behavior follows `GE-G86-1` through `GE-G86-8`
- **AND** the model does not replace those equations with the repo's existing reduced-order stagewise closure
- **AND** the first implementation slice stays within the explicit single-column open-loop bubble-cap boundary instead of silently claiming the paper's deferred controller, start-up, or multi-column modes.

### Requirement: Paper-Faithful Comparison Models Reuse The Existing Monolithic Runtime Boundary
`Howard1970DistillationColumn` and `Gani1986DistillationColumn` SHALL remain backend-only monolithic runtime units with explicit feed and product ownership, and SHALL NOT widen gameplay/start/build exposure in this change.

#### Scenario: Paper-faithful models coexist with the stagewise baseline without widening gameplay
- **WHEN** contributors inspect the runtime distillation surfaces after this change
- **THEN** `Howard1970DistillationColumn` and `Gani1986DistillationColumn` exist as explicit sibling runtime model classes alongside `StagewiseDistillationColumn`
- **AND** no gameplay/start/build contract is widened merely because the new classes exist
- **AND** the change does not introduce a shortcut compatibility model under a different name.

### Requirement: Distillation-Column Foundation Work Targets Dynamic Stagewise Behavior
This change SHALL keep one monolithic `StagewiseDistillationColumn` as the repo's existing reduced-order dynamic distillation baseline, SHALL additionally allow monolithic `Howard1970DistillationColumn` and `Gani1986DistillationColumn` comparison models in this slice, and SHALL NOT define a lumped main model as the completion contract.

#### Scenario: Dynamic model boundary is monolithic and comparison-ready
- **WHEN** contributors inspect the runtime distillation-model contract for this change
- **THEN** `StagewiseDistillationColumn`, `Howard1970DistillationColumn`, and `Gani1986DistillationColumn` are explicit monolithic runtime model classes
- **AND** no lumped main model is the completion contract
- **AND** the paper-faithful models do not replace the existing stagewise baseline.

### Requirement: Multi-Feed Assignment Is First-Class Column Behavior
The dynamic distillation-column contract SHALL support multiple feed inputs and configurable feed-stage assignment (feed height/stage).

#### Scenario: Multi-feed stage assignment is part of runtime behavior
- **WHEN** a runtime configures more than one feed on the distillation column
- **THEN** each feed has an explicit assigned stage (or equivalent feed-height mapping)
- **AND** feed assignment participates in the live dynamic material-balance behavior rather than metadata-only bookkeeping.

### Requirement: Internal Hydraulic States Drive Dynamic Stage Traffic
`StagewiseDistillationColumn` SHALL drive internal liquid and vapor traffic from runtime-owned hydraulic and holdup state rather than fixed global constant-molar-overflow traffic.

#### Governing Equations
- `GE-HYD-1` Stage liquid holdup:

  `M_liq,i = sum_k M_stage[i,k]`  `[mol]`

- `GE-HYD-2` Liquid volume and head:

  `V_liq,i = M_liq,i * MW_mix,i / rho_liq,i`  `[m^3]`

  `h_i = V_liq,i / A_active,i`  `[m]`

- `GE-HYD-3` Liquid downflow law:

  `L_i = C_L,i * max(h_i - h_weir,i, 0)^(3/2)`  `[mol/s]`

- `GE-HYD-4` Available vapor driving pressure:

  `DeltaP_i = P_{i+1} - P_i`  `[Pa]`

  `DeltaP_head,i = rho_liq,i * g * h_i`  `[Pa]`

  `DeltaP_avail,i = max(DeltaP_i - DeltaP_dry,i - DeltaP_head,i, 0)`  `[Pa]`

- `GE-HYD-5` Vapor upflow law:

  `V_i = C_V,i * sqrt(DeltaP_avail,i / max(rho_vap,i, eps))`  `[mol/s]`

- Symbols and assumptions:
  - `M_stage[i,k]` = stage `i` component holdup of species `k` `[mol]`
  - `MW_mix,i` = stage-liquid mixture molecular weight `[kg/mol]`
  - `rho_liq,i`, `rho_vap,i` = reduced-order liquid and vapor densities `[kg/m^3]`
  - `A_active,i` = active cross-sectional area implied by geometry `[m^2]`
  - `C_L,i`, `C_V,i`, `h_weir,i`, `DeltaP_dry,i` = named hydraulic closure parameters
  - `g` = gravitational acceleration `[m/s^2]`
  - flooding, weeping, entrainment, and other regime switching are explicitly out of scope for this slice.

#### Scenario: Internal stage traffic responds to runtime state
- **WHEN** feed, condenser duty, reboiler duty, reflux routing, or product withdrawal disturbs the column over multiple runtime steps
- **THEN** internal liquid and vapor traffic evolves according to `GE-HYD-1` through `GE-HYD-5`
- **AND** stage-to-stage coupling is not represented as a pair of fixed global liquid/vapor flow constants
- **AND** the current slice does not yet require flooding, weeping, or entrainment regime switching.

### Requirement: Reduced-Order Thermal State Evolution Is Thermodynamic Rather Than Proxy-Based
`StagewiseDistillationColumn` SHALL expose reduced-order thermal behavior derived from runtime thermal state and explicit thermodynamic closure rather than mixed-feed proxy temperatures.

#### Governing Equations
- `GE-TH-1` Stage liquid-region energy balance for stage `i`:

  `dU_i/dt = F_i * hF_i + L_{i-1} * hL_{i-1} + V_{i+1} * hV_{i+1} - L_i * hL_i - V_i * hV_i`  `[W]`

- `GE-TH-2` Reflux-drum energy balance:

  `dU_drum/dt = V_top * hV_top - Q_condenser + R_ext * hR_ext - D * hD - L_reflux * hL_drum`  `[W]`

- `GE-TH-3` Bottoms-sump energy balance:

  `dU_sump/dt = L_bottom * hL_bottom + Q_reboiler - V_boilup * hV_boilup - B * hB`  `[W]`

- `GE-TH-4` Temperature recovery from reduced-order thermodynamic state:

  `U_region = M_region * h_liq(T_region, x_region, P_region)`

  `T_region = h_liq^(-1)(U_region / M_region, x_region, P_region)`

- Symbols and assumptions:
  - `U_i`, `U_drum`, `U_sump` = internal energy states `[J]`
  - `h*` = reduced-order phase enthalpies `[J/mol]`
  - `Q_condenser`, `Q_reboiler` = applied duty terms `[W]`
  - `T_region` is recovered from thermodynamic state, not copied from feed temperature
  - the slice still does not require full rigorous MESH, superheat modeling, or pressure-swing distillation.

#### Scenario: Duty response changes reported thermal state
- **WHEN** condenser or reboiler duty changes over multiple runtime steps
- **THEN** reported top and bottom thermal state evolves according to `GE-TH-1` through `GE-TH-4`
- **AND** the thermal response is derived from runtime thermodynamic state rather than a feed-temperature passthrough.

### Requirement: Realism Boundary Is Frozen For This Slice
This change SHALL freeze a reduced-order but physically grounded dynamic column boundary with multicomponent stagewise inventories, dynamic internal hydraulic states, a dynamic condenser plus reflux-drum region, a dynamic sump plus thermosyphon-inspired reboiler region, stronger internal pressure treatment, and explicit reduced-order thermal-state evolution, while still deferring flooding/weeping and full rigorous MESH in this slice.

#### Governing Equations
- `GE-RB-1` Stage component balance family:

  `dM[i,k]/dt = F[i,k] + L_{i-1} * x[i-1,k] + V_{i+1} * y[i+1,k] - L_i * x[i,k] - V_i * y[i,k]`  `[mol/s]`

- `GE-RB-2` Internal hydraulic traffic is defined by `GE-HYD-1` through `GE-HYD-5`.
- `GE-RB-3` Thermal-state evolution is defined by `GE-TH-1` through `GE-TH-4`.
- `GE-RB-4` Top and bottom dynamic regions are defined by `GE-CR-1` through `GE-CR-4` and `GE-BR-1` through `GE-BR-4`.
- Symbols and assumptions:
  - `x[i,k]`, `y[i,k]` = liquid and vapor compositions on stage `i`
  - the slice remains multicomponent and reduced-order
  - flooding/weeping, full rigorous MESH, and rate-based mass transfer remain explicitly deferred.

#### Scenario: Initial closure is still reduced-order and multicomponent
- **WHEN** contributors inspect the model closure assumptions in this change
- **THEN** the frozen realism boundary is the reduced-order multicomponent balance family defined by `GE-RB-1` through `GE-RB-4`
- **AND** the contract does not require full rigorous MESH or rate-based mass-transfer fidelity in this change.

#### Scenario: Initial thermodynamic and hydraulic basis is explicit
- **WHEN** contributors inspect the stagewise-column closure assumptions in this slice
- **THEN** stage separation, hydraulic traffic, and thermal behavior are anchored by `GE-HYD-1` through `GE-HYD-5`, `GE-TH-1` through `GE-TH-4`, and `GE-K-1` through `GE-K-2`
- **AND** the contract no longer relies on fixed global internal liquid/vapor traffic, bare fixed-latent-heat `Q/λ` as the whole primary closure, or proxy temperatures.

### Requirement: Reflux And Product Topology Seams Are Explicit Runtime Contract
The monolithic `StagewiseDistillationColumn` SHALL provide explicit reflux and product withdrawal seams as part of runtime behavior.

#### Scenario: Reflux and withdrawal topology is not implicit bookkeeping
- **WHEN** contributors inspect runtime seam requirements
- **THEN** reflux liquid has explicit unit-local boundary seam fields for outlet and reflux-return requests
- **AND** distillate withdrawal is modeled as external withdrawal from reflux-drum holdup
- **AND** bottoms withdrawal is modeled as external withdrawal from bottoms-sump holdup
- **AND** reflux return, distillate withdrawal, and bottoms withdrawal remain liquid-phase and holdup-bounded rather than bypassing their owning inventories.

### Requirement: Condenser/Reboiler Actuation Is Direct-Duty Service Coupled Into RHS
Condenser and reboiler actuation in this change SHALL be modeled as unit-local duty-request boundary fields coupled into dynamic top and bottom thermal-hydraulic regions of the monolithic column rather than as direct fixed-latent-heat shortcuts alone.

#### Governing Equations
- `GE-CR-1` Reflux-drum and condenser energy balance:

  `dU_drum/dt = V_top * hV_top - Q_condenser + R_ext * hR_ext - D * hD - L_reflux * hL_drum`  `[W]`

- `GE-CR-2` Top-region flash closure:

  `(beta_top, x_drum, y_top) = Flash_top(P_top, H_top, z_top)`

- `GE-CR-3` Bottoms-sump energy balance:

  `dU_sump/dt = L_bottom * hL_bottom + Q_reboiler - V_boilup * hV_boilup - B * hB`  `[W]`

- `GE-CR-4` Bottom-region vapor generation is derived from the bottom thermodynamic and circulation closure rather than a bare fixed-latent-heat `Q/λ` mapping.

- Symbols and assumptions:
  - `Flash_top(...)` = explicit top-region thermodynamic flash closure, preferably property-package-backed
  - `H_top`, `z_top` = top-region molar enthalpy and composition inputs to the flash closure
  - `Q_condenser`, `Q_reboiler` remain unit-local duty-request inputs `[W]`
  - the slice does not require separate placeable condenser/reboiler equipment.

#### Scenario: Utility actuation contract is explicit and runtime-owned
- **WHEN** condenser or reboiler actuation is configured
- **THEN** runtime behavior applies unit-local duty-request boundary fields into the monolithic stagewise RHS according to `GE-CR-1` through `GE-CR-4`
- **AND** realized duty response remains mass-conservative and inventory-aware
- **AND** the contract does not require controller-proof acceptance or separate placeable condenser/reboiler units in this change.

### Requirement: Bottoms-Side Reboiler Closure Remains Internal-Only And Monolithic
The monolithic `StagewiseDistillationColumn` SHALL keep stronger reboiler-circulation and boiling closure unit-internal while allowing a dynamic sump plus thermosyphon-inspired reboiler region in this slice.

#### Governing Equations
- `GE-BR-1` Natural-circulation driving pressure:

  `DeltaP_drive = max((rho_downcomer - rho_riser) * g * H_loop, 0)`  `[Pa]`

- `GE-BR-2` Internal circulation law:

  `L_circ = C_circ * sqrt(DeltaP_drive / max(rho_liq,sump, eps))`  `[mol/s]`

- `GE-BR-3` Reboiler outlet flash closure:

  `(beta_boilup, x_return, y_boilup) = Flash_bottom(P_bottom, h_circ,out, x_sump)`

- `GE-BR-4` Boilup from internal circulation:

  `V_boilup = beta_boilup * L_circ`  `[mol/s]`

- Symbols and assumptions:
  - `rho_downcomer`, `rho_riser` = effective liquid-rich and vaporizing-leg densities `[kg/m^3]`
  - `H_loop` = effective thermosyphon static-head height `[m]`
  - `C_circ` = named internal circulation coefficient
  - `Flash_bottom(...)` = explicit bottom-region thermodynamic flash closure, preferably property-package-backed
  - this is an internal-only thermosyphon-inspired heuristic; it does not create a public circulation port or line-level circulation edge.

#### Scenario: Hidden circulation custody does not widen the public surface
- **WHEN** contributors inspect the bottoms-side closure used by `StagewiseDistillationColumn`
- **THEN** the bottoms-side circulation and boilup behavior follows `GE-BR-1` through `GE-BR-4`
- **AND** the bottoms sump remains the owner of liquid holdup
- **AND** the change does not add a public circulation port, public circulation actuator, connection-layer circulation edge, or separate placeable reboiler unit.

#### Scenario: Stronger bottoms-side closure does not widen public model contracts
- **WHEN** contributors inspect the public/runtime-facing contract of `StagewiseDistillationColumn` after this slice
- **THEN** runtime actuation authority still stays on the existing duty-request and liquid-routing seams
- **AND** no public circulation-related boundary field, session-visible circulation contract, or new public circulation observability promise is required by `GE-BR-1` through `GE-BR-4`.

### Requirement: Ratio Fields Are Reference/Derived Only
`reflux_ratio` and `boilup_ratio` SHALL be initialization/reference/derived-observable fields and SHALL NOT be treated as live runtime actuation knobs.

#### Scenario: Runtime actuation authority uses explicit seams instead of ratio knobs
- **WHEN** live runtime actuation is evaluated for the dynamic column
- **THEN** explicit unit-local boundary request fields plus external material-routing seams provide runtime actuation authority
- **AND** any exposed `reflux_ratio` and `boilup_ratio` values are derived from actual runtime flows
- **AND** `reflux_ratio` and `boilup_ratio` remain non-actuating in runtime.

### Requirement: Geometry Semantics Are Explicit And Non-Misleading
`active_contact_height_m` SHALL control tray-equivalent stage count under fixed tray spacing, and `shell_diameter_m` SHALL control area, liquid holdup, hydraulic capacity, and pressure-response semantics.

#### Governing Equations
- `GE-GEO-1` Effective stage count:

  `N_stage = max(1, round(active_contact_height_m / tray_spacing_m))`

- `GE-GEO-2` Active column area:

  `A_active = pi * shell_diameter_m^2 / 4`  `[m^2]`

- `GE-GEO-3` Geometry enters the hydraulic and pressure closures through `A_active`, vapor-space volumes, and the holdup/head terms used in `GE-HYD-1` through `GE-HYD-5` and `GE-PR-1` through `GE-PR-3`.

- Symbols and assumptions:
  - `tray_spacing_m` = fixed tray-equivalent spacing used to map contact height to stage count
  - `shell_diameter_m` influences residence, holdup, hydraulic capacity, and pressure response, not thermodynamic selectivity directly.

#### Scenario: Geometry wording avoids false selectivity claims
- **WHEN** geometry fields are interpreted in this change contract
- **THEN** stage count and area semantics follow `GE-GEO-1` through `GE-GEO-3`
- **AND** shell width is not framed as directly changing thermodynamic selectivity.

### Requirement: Pressure Contract Guarantees Dynamic Column Pressure Minimum
The minimum guaranteed pressure contract SHALL keep one shared `column_pressure_pa` interface for existing runtime and connection surfaces while requiring that interface to be derived from a stronger internal dynamic pressure solution rather than a dead placeholder.

#### Governing Equations
- `GE-PR-1` Top vapor-space pressure:

  `P_top = Z_top * R * T_top * n_top_vap / V_top_vap`  `[Pa]`

- `GE-PR-2` Bottom vapor-space pressure:

  `P_bottom = Z_bottom * R * T_bottom * n_bottom_vap / V_bottom_vap`  `[Pa]`

- `GE-PR-3` Shared compatibility pressure for existing external interfaces:

  `column_pressure_pa = 0.5 * (P_top + P_bottom)`  `[Pa]`

- Symbols and assumptions:
  - `Z_top`, `Z_bottom` = reduced-order compressibility factors
  - `n_top_vap`, `n_bottom_vap` = top and bottom vapor holdup states `[mol]`
  - `V_top_vap`, `V_bottom_vap` = effective top and bottom vapor-space volumes `[m^3]`
  - `column_pressure_pa` is the shared compatibility interface for existing runtime/connection surfaces, not the full internal pressure field.

#### Scenario: Stagewise pressure implementations remain allowed and stronger pressure behavior stays interface-compatible
- **WHEN** a stronger implementation provides sectionwise or otherwise richer internal dynamic pressure treatment
- **THEN** the exposed shared compatibility pressure follows `GE-PR-1` through `GE-PR-3`
- **AND** the exposed shared pressure is derived from the internal dynamic pressure solution rather than a constant or dead placeholder
- **AND** this change text does not require a wider public pressure-actuation surface.

### Requirement: Reduced-Order Multicomponent Equilibrium Is Explicit
The live stagewise equilibrium closure in this slice SHALL remain multicomponent and explicit rather than relying on binary-only constant-alpha reasoning.

#### Governing Equations
- `GE-K-1` Reduced-order multicomponent `K`-value model for species `k` on region `i`:

  `ln(K[i,k]) = ln(K_ref[k]) + a[k] * (1/T_i - 1/T_ref) - b[k] * ln(P_i / P_ref)`

- `GE-K-2` Vapor composition from `K`-values:

  `y[i,k] = K[i,k] * x[i,k] / sum_j(K[i,j] * x[i,j])`

- Symbols and assumptions:
  - `K_ref[k]`, `a[k]`, `b[k]` = named reduced-order equilibrium parameters for species `k`
  - `x[i,k]`, `y[i,k]` = liquid and vapor mole fractions
  - this slice allows stronger property-package-backed flash closure in the top and bottom regions, but does not require tray-by-tray rigorous flash on every RHS evaluation.

#### Scenario: Multicomponent equilibrium stays explicit and reduced-order
- **WHEN** contributors inspect the live stagewise equilibrium story in this slice
- **THEN** the multicomponent equilibrium closure follows `GE-K-1` and `GE-K-2`
- **AND** the contract does not collapse the model back to binary-only constant-alpha reasoning.

### Requirement: Distillation Runtime Semantics Are Stagewise-Only With No Shortcut Shim
This capability SHALL treat `StagewiseDistillationColumn` as the existing reduced-order runtime distillation baseline, SHALL additionally allow `Howard1970DistillationColumn` and `Gani1986DistillationColumn` as approved paper-faithful runtime comparison-model paths in this slice, and SHALL NOT reintroduce a `ShortcutDistillation` class, alias, or compatibility shim.

#### Scenario: Completion cannot rely on a shortcut compatibility path
- **WHEN** implementation or tests evaluate dynamic distillation behavior
- **THEN** completion may use runtime behavior from `StagewiseDistillationColumn`, `Howard1970DistillationColumn`, or `Gani1986DistillationColumn`
- **AND** no `ShortcutDistillation` runtime/shim pathway is required or preserved.

### Requirement: Current Gameplay Gating Stays Unchanged In This Change
`place_shortcut_distillation_column` SHALL keep its current hide/reject gating on topology-only starts in this change.

#### Scenario: Foundation identity is preserved without premature exposure
- **WHEN** contributors inspect current supported build lists and start-allowlist behavior
- **THEN** `place_shortcut_distillation_column` remains a foundation identity with existing hide/reject behavior
- **AND** current topology-only starts do not gain public distillation-column exposure in this change.

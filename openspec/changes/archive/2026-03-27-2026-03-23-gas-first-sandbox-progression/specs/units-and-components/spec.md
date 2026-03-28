## MODIFIED Requirements

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

### Requirement: The Exact Gas-First Main-World Catalog Records Are Frozen
The main-world gas ladder item records SHALL encode these exact records:

- `place_inlet_gas_separator`: `title = "Inlet gas separator"`, `item_kind = "unit_blueprint"`, `apply_kind = "add_process"`, `default_config = {"unit_type": "FlashDrum", "unit_module": "modular_simulation.unit_processes.separation.flash_drum", "constructor_payload": {"thermal_mode": "isothermal", "imposed_pressure": 4500000.0, "imposed_temperature": 305.0}}`, `required_user_inputs = ("process_id",)`, `supported_start_ids = ("phase1_process_sandbox_v1",)`, summary `field inlet separator that removes free liquids ahead of downstream gas treating`
- `place_teg_contactor`: `title = "TEG contactor"`, `item_kind = "unit_blueprint"`, `apply_kind = "add_process"`, `default_config = {"unit_type": "ComponentSeparator", "unit_module": "modular_simulation.unit_processes.separation.component_separator", "constructor_payload": {"n_species": 2, "species_order": ("water", "hydrocarbon"), "configured_split_fraction_targets": {"water": 0.98, "hydrocarbon": 0.05}}}`, `required_user_inputs = ("process_id",)`, `supported_start_ids = ("phase1_process_sandbox_v1",)`, summary `dehydration-package proxy that preferentially removes water from sweet wet gas without claiming a rigorous closed glycol contactor model`
- `place_rich_glycol_flash_tank`: `title = "Rich glycol flash tank"`, `item_kind = "unit_blueprint"`, `apply_kind = "add_process"`, `default_config = {"unit_type": "FlashDrum", "unit_module": "modular_simulation.unit_processes.separation.flash_drum", "constructor_payload": {"thermal_mode": "isothermal", "imposed_pressure": 350000.0, "imposed_temperature": 315.0}}`, `required_user_inputs = ("process_id",)`, `supported_start_ids = ("phase1_process_sandbox_v1",)`, summary `rich-glycol flash vessel for separating flashed gas before regeneration`
- `place_lean_rich_glycol_exchanger`: `title = "Lean/rich glycol exchanger"`, `item_kind = "unit_blueprint"`, `apply_kind = "add_process"`, `default_config = {"unit_type": "HeatExchanger", "unit_module": "modular_simulation.unit_processes.thermal.heat_exchanger", "constructor_payload": {"flow_arrangement": "counter", "ua": 6000.0}}`, `required_user_inputs = ("process_id",)`, `supported_start_ids = ("phase1_process_sandbox_v1",)`, summary `heat recovery exchanger between rich and regenerated glycol streams`
- `place_teg_regenerator`: `title = "TEG regenerator"`, `item_kind = "unit_blueprint"`, `apply_kind = "add_process"`, `default_config = {"unit_type": "StagewiseDistillationColumn", "unit_module": "modular_simulation.unit_processes.separation.stagewise_distillation", "constructor_payload": {"n_species": 2, "active_contact_height_m": 4.0, "shell_diameter_m": 1.0, "feed_stage_indices": (1,)}}`, `required_user_inputs = ("process_id",)`, `supported_start_ids = ("phase1_process_sandbox_v1",)`, summary `regeneration proxy representing the still column and reboiler section of a TEG package`
- `install_glycol_circulation_pump`: `title = "Glycol circulation pump"`, `item_kind = "line_overlay"`, `apply_kind = "attach_line_pump"`, `default_config = {"initial_pump_speed": 90000.0}`, `required_user_inputs = ("line_id", "pump_id")`, `supported_start_ids = ("phase1_process_sandbox_v1",)`, summary `line-owned circulation pump used to move regenerated glycol through the dehydration loop`
- `place_gas_gas_exchanger`: `title = "Gas-gas exchanger"`, `item_kind = "unit_blueprint"`, `apply_kind = "add_process"`, `default_config = {"unit_type": "HeatExchanger", "unit_module": "modular_simulation.unit_processes.thermal.heat_exchanger", "constructor_payload": {"flow_arrangement": "counter", "ua": 8000.0}}`, `required_user_inputs = ("process_id",)`, `supported_start_ids = ("phase1_process_sandbox_v1",)`, summary `named pre-cooling proxy on the main gas path ahead of the educational JT/LTS recovery step, not a fully connected exchanger-service model`
- `install_jt_valve`: `title = "JT valve"`, `item_kind = "line_overlay"`, `apply_kind = "attach_line_valve"`, `default_config = {"minimum_open_fraction": 0.05, "maximum_open_fraction": 1.0, "initial_open_fraction": 0.35}`, `required_user_inputs = ("line_id", "valve_id")`, `supported_start_ids = ("phase1_process_sandbox_v1",)`, summary `named Joule-Thomson throttling proxy that qualifies the imposed downstream cold-condition path for the low-temperature separator`
- `place_low_temperature_separator`: `title = "Low-temperature separator"`, `item_kind = "unit_blueprint"`, `apply_kind = "add_process"`, `default_config = {"unit_type": "FlashDrum", "unit_module": "modular_simulation.unit_processes.separation.flash_drum", "constructor_payload": {"thermal_mode": "isothermal", "imposed_pressure": 2000000.0, "imposed_temperature": 265.0}}`, `required_user_inputs = ("process_id",)`, `supported_start_ids = ("phase1_process_sandbox_v1",)`, summary `imposed-cold low-temperature-separation proxy that represents heavier-hydrocarbon dropout after the named JT/LTS path is installed in order`
- `place_condensate_stabilizer`: `title = "Condensate stabilizer"`, `item_kind = "unit_blueprint"`, `apply_kind = "add_process"`, `default_config = {"unit_type": "StagewiseDistillationColumn", "unit_module": "modular_simulation.unit_processes.separation.stagewise_distillation", "constructor_payload": {"n_species": 2, "active_contact_height_m": 4.0, "shell_diameter_m": 1.0, "feed_stage_indices": (1,)}}`, `required_user_inputs = ("process_id",)`, `supported_start_ids = ("phase1_process_sandbox_v1",)`, summary `stabilization proxy on the inlet-separator liquid path that avoids public product-inventory or tank-mediated refeed semantics`
- `build_process_line`: unchanged line contract, but `supported_start_ids` SHALL include `phase1_process_sandbox_v1`

#### Scenario: Gas item records are frozen exactly
- **WHEN** a contributor inspects a main-world gas catalog item
- **THEN** its title, kind, apply kind, payload, required inputs, supported start ids, and educational summary match the exact frozen record above

#### Scenario: JT/LTS wording stays educational and imposed-cold
- **WHEN** a contributor inspects `place_gas_gas_exchanger`, `install_jt_valve`, or `place_low_temperature_separator`
- **THEN** the artifact states that the pack uses a named JT/LTS teaching proxy with an imposed downstream cold condition rather than a rigorous Joule-Thomson or cryogenic thermodynamics model

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

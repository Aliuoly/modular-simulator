## MODIFIED Requirements

### Requirement: The Exact Phase-1 Sandbox Catalog Item Ids Are Frozen
The phase-1 sandbox catalog SHALL contain exactly `place_heater_cooler`, `place_flash_drum`, `place_heat_exchanger`, `place_component_separator`, `place_merge_junction_2x1`, `place_split_junction_1x2`, `build_process_line`, `install_line_pump`, `install_line_valve`, `install_line_heat_actuator`, `install_sampled_delayed_sensor`, `install_pid_controller`, `place_holding_tank`, and `place_quality_control_lab`.

#### Scenario: No hidden or deferred build items leak into phase 1
- **WHEN** the catalog is inspected
- **THEN** it contains exactly those 14 item ids and no arbitrary process-factory, stand-alone pump/valve-unit, or tutorial-only mechanics

## ADDED Requirements

### Requirement: Additive Foundation Catalog Records Are Frozen
The phase-1 sandbox catalog SHALL additionally encode these exact records:

- `place_holding_tank`: `title = "Holding tank"`, `item_kind = "unit_blueprint"`, `apply_kind = "add_process"`, `default_config = {"unit_type": "HoldingTank", "unit_module": "modular_simulation.unit_processes.storage.holding_tank", "constructor_payload": {}}`, `required_user_inputs = ("process_id",)`, `supported_start_ids = ()`, summary `single-inlet single-outlet buffer vessel for future tank-mediated material holdup and transfer`
- `place_quality_control_lab`: `title = "Quality control lab"`, `item_kind = "unit_blueprint"`, `apply_kind = "add_process"`, `default_config = {"unit_type": "QualityControlLab", "unit_module": "modular_simulation.unit_processes.analysis.quality_control_lab", "constructor_payload": {"minimum_purity_mol_fraction": 0.95}}`, `required_user_inputs = ("process_id", "tracked_component_id")`, `supported_start_ids = ()`, summary `process-stream quality gate that counts accepted moles toward later research progress and rejects off-spec material to disposal`

#### Scenario: New foundation catalog records are frozen exactly
- **WHEN** a contributor inspects either new catalog item
- **THEN** its title, kind, apply kind, payload, required inputs, supported start ids, and educational summary match the exact frozen record above

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

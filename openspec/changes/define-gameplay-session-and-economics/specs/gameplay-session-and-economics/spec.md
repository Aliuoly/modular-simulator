## ADDED Requirements

### Requirement: Gameplay Session API Composes The Simulation Substrate
The gameplay layer SHALL expose a dedicated scenario-session API that composes `PlantBackendSession` or equivalent simulation substrate surfaces instead of embedding progression policy inside the substrate itself.

#### Scenario: Session startup uses a dedicated gameplay layer
- **WHEN** a caller starts a gameplay scenario
- **THEN** the caller interacts with a gameplay-session API above the simulation core rather than directly with progression policy embedded in `PlantBackendSession`

### Requirement: Upgrade Quotations And Purchases Are Explicit
The gameplay session SHALL provide quotation and purchase flows that name cost, prerequisites, and the explicit plant mutation or documented parameter change associated with an upgrade.

#### Scenario: Unsupported or out-of-scope upgrades are rejected
- **WHEN** a caller requests an upgrade that is unsupported, violates prerequisites, or falls outside phase-1 scope
- **THEN** the gameplay session rejects the request instead of silently applying a hidden gameplay-only effect

### Requirement: Gameplay Session API Has Stable Inputs, Outputs, And Reason Codes
The gameplay session SHALL expose fixed method signatures and stable result payloads for scenario startup, upgrade quotation, upgrade purchase, stepping, and progression-state reads.

#### Scenario: Session methods return the documented contract shapes
- **WHEN** a caller uses the gameplay-session API
- **THEN** `start_scenario`, `quote_upgrade`, `purchase_upgrade`, `step_and_score`, and `get_progression_state` return the documented contract objects and rejected purchases use stable reason codes including `unknown_upgrade`, `already_owned`, `unmet_prerequisite`, `insufficient_cash`, and `out_of_scope`

#### Scenario: Objective status uses the fixed hold-timer payload
- **WHEN** a caller inspects `objective_status_by_id`
- **THEN** each entry exposes `condition_id`, `currently_satisfied`, `accumulated_hold_time_s`, and `completed`, and `completed` latches once the condition has remained satisfied for at least its `hold_duration_s`

### Requirement: Economics Are Deterministic And Simulation-Derived
Phase-1 economics SHALL be deterministic for a fixed scenario state and SHALL derive from simulation outputs plus installed-asset information rather than from manual click-income counters.

#### Scenario: Economics expose the required breakdown fields
- **WHEN** a caller asks for a step or score summary
- **THEN** the result includes `revenue`, `utility_cost`, `equipment_capex`, `instrumentation_capex`, and `operating_profit`

#### Scenario: Economics fields use one phase-1 interpretation
- **WHEN** a caller inspects a phase-1 economics breakdown
- **THEN** `revenue` and `utility_cost` are step-interval values over the just-completed `dt_s`, `equipment_capex` and `instrumentation_capex` are cumulative spent-to-date totals, and `operating_profit` equals `revenue - utility_cost` without subtracting CAPEX again

### Requirement: Progression State Stays Scenario-Local
The gameplay session SHALL keep progression state local to the active starter scenario.

#### Scenario: Later-phase campaign systems stay deferred
- **WHEN** progression state is inspected during phase-1 gameplay
- **THEN** it includes scenario-local cash, unlocks, owned upgrades, and objective status, and does not include multi-plant supply-chain or staffing systems

### Requirement: Gameplay Session Consumes Scenario-Authored Upgrade And Objective Data
The gameplay-session layer SHALL consume upgrade definitions, success metrics, and victory conditions from the starter-scenario catalog rather than inventing separate pricing or objective logic.

#### Scenario: Upgrade and objective ownership does not split across layers inconsistently
- **WHEN** a contributor inspects the starter-scenario catalog and gameplay-session implementation
- **THEN** upgrade ids, prices, prerequisites, plant changes, success metrics, and victory conditions originate in scenario definitions and the gameplay-session layer evaluates or applies them without redefining them

### Requirement: Gameplay Session Consumes Scenario-Authored Economics Bindings
The gameplay-session layer SHALL compute `revenue` and `utility_cost` from the scenario-authored `EconomicsFieldDefinition` bindings rather than inventing separate scenario formulas.

#### Scenario: Revenue and utility calculations come from scenario data
- **WHEN** a contributor inspects the starter-scenario catalog and gameplay economics implementation
- **THEN** the implementation reads the scenario’s declared base amounts and metric coefficients for `revenue` and `utility_cost` and applies the shared phase-1 formula shape without redefining per-scenario logic elsewhere

### Requirement: PlantBackendSession Remains Free Of Gameplay Policy
Any changes to `PlantBackendSession` made to support gameplay composition SHALL remain generic substrate hooks and SHALL not own pricing, scenario, or progression policy.

#### Scenario: Gameplay integration preserves substrate ownership boundaries
- **WHEN** the gameplay session implementation requires backend-session support
- **THEN** any added substrate helpers remain generic and gameplay policy continues to live under `src/modular_simulation/gameplay/`

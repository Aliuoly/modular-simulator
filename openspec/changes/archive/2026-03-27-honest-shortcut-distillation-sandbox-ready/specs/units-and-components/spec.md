## MODIFIED Requirements

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

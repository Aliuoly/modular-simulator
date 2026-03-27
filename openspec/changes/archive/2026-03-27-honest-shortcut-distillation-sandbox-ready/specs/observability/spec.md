## MODIFIED Requirements

### Requirement: Dynamic Distillation Process State Is Exposed Through Substrate Observability
`observables.process_state_values` SHALL expose runtime-owned dynamic distillation-column state as normalized numeric keys.

#### Scenario: Stagewise and product composition observability includes active species
- **WHEN** a runtime includes the dynamic distillation-column unit
- **THEN** `observables.process_state_values` includes selected stage-composition values and product compositions for all active species
- **AND** composition values are runtime-owned process-state projections, not gameplay metadata reconstruction.

#### Scenario: Core dynamic readouts are visible for runtime analysis
- **WHEN** the dynamic distillation-column unit is stepped
- **THEN** `observables.process_state_values` includes reflux-drum holdup, bottoms-sump holdup, and actual flows
- **AND** each configured feed exposes actual flow/composition plus assigned stage/feed-height association
- **AND** reflux-return and external product-withdrawal related runtime flow readouts are exposed when those seams are configured.

### Requirement: Shared Pressure And Geometry Readouts Are Part Of Public Runtime Contract
The dynamic observability contract SHALL include shared dynamic pressure and any runtime/public geometry values exposed by the runtime.

#### Scenario: Pressure minimum contract appears in process-state values
- **WHEN** a dynamic distillation column participates in runtime observability
- **THEN** published values include at least the shared dynamic `column_pressure_pa` contract
- **AND** wording allows richer stagewise dynamic pressure readouts without breaking minimum compatibility.

#### Scenario: Geometry readouts align with frozen semantics
- **WHEN** geometry values are published to runtime observability
- **THEN** `active_contact_height_m` and `shell_diameter_m` readouts align with their frozen stage-count and area/holdup/capacity semantics
- **AND** runtime observability does not imply that diameter directly changes thermodynamic selectivity.

#### Scenario: Capacity wording matches implemented heuristic naming
- **WHEN** observability/spec text describes diameter-linked capacity behavior
- **THEN** wording uses area-scaled capacity proxy/heuristic language
- **AND** observability text does not label the behavior as a specific named correlation unless that correlation is explicitly implemented.

### Requirement: Duty Request And Realized Duty Readouts Are Runtime-Owned
Condenser/reboiler duty request and realized-duty readouts (when exposed) SHALL appear under runtime-owned process-state projection without requiring external utility-service objects.

#### Scenario: Duty-aware process-state projection remains substrate-owned
- **WHEN** condenser or reboiler behavior is stepped in runtime
- **THEN** runtime snapshots include corresponding duty request/realized-duty numeric values where available
- **AND** gameplay/session layers do not synthesize duty observability from non-runtime bookkeeping.

### Requirement: Ratio Fields Remain Reference/Derived Observables
If `reflux_ratio` or `boilup_ratio` are exposed under `observables.process_state_values`, they SHALL be treated as derived/reference values and not runtime actuator states.

#### Scenario: Ratio readouts do not imply ratio-knob actuation contract
- **WHEN** runtime snapshots expose `reflux_ratio` or `boilup_ratio`
- **THEN** those values are documented/used as initialization-reference or derived telemetry computed from actual runtime flows
- **AND** observability output does not redefine ratio fields as authoritative live actuation knobs.

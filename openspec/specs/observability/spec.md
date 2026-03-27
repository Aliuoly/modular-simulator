# Observability

## Purpose

This capability defines the stable observability snapshot owned by `ConnectionNetwork` and forwarded by `PlantBackendSession`, covering runtime state and physical simulation outputs without gameplay or economics fields.

## Requirements

### Requirement: Substrate Owns The Public Observability Snapshot API
The simulation substrate SHALL expose a stable public observability snapshot owned by `ConnectionNetwork` and consumable through `PlantBackendSession` as a thin forwarding facade.

#### Scenario: Public observability reads stay on owner surfaces
- **WHEN** a contributor inspects the public runtime read APIs
- **THEN** the observability snapshot is owned by `ConnectionNetwork` and any `PlantBackendSession` entry point only forwards that snapshot without adding gameplay or economics policy

### Requirement: Observability Snapshot Contract Is Stable And Distinct From Persistence
The substrate SHALL expose a consumer-facing observability snapshot contract that is distinct from checkpoint or replay persistence payloads.

#### Scenario: Consumer-facing snapshot does not reuse checkpoint payloads
- **WHEN** a caller compares the observability snapshot with `save_runtime_snapshot()` output
- **THEN** the observability snapshot is a separate read model rather than the persistence payload with replay/checksum fields exposed directly

### Requirement: First-Slice Snapshot Shape Is Frozen
The public observability snapshot SHALL expose exactly these top-level fields and sections:
- `schema: str`
- `graph_revision: str | None`
- `runtime: Mapping[str, object]` with `simulation_time_s: float`, `macro_step_index: int`, and `macro_step_active: bool`
- `queue: Mapping[str, object]` with `queued_request_ids: tuple[str, ...] | list[str]`, `queued_request_count: int`, and `committed_idempotency_keys: tuple[str, ...] | list[str]`
- `observables: Mapping[str, object]` with `published_measurements: Mapping[str, float]`, `process_state_values: Mapping[str, float]`, and `plant_calculation_outputs: Mapping[str, float]`

#### Scenario: Runtime and queue state are readable without runtime scraping
- **WHEN** a caller requests the public observability snapshot after queueing or stepping runtime work
- **THEN** the snapshot includes the current graph revision, simulation time, macro-step state, queued request ids, queued request count, and committed idempotency keys through the frozen sections above

### Requirement: Published Measurements Are Exposed As Normalized Numeric Maps
The public observability snapshot SHALL expose subsystem published measurements as normalized numeric mappings using the existing subsystem publication namespace rules.

#### Scenario: Published subsystem tags remain normalized
- **WHEN** a subsystem publishes measurements through its `publication_map` or publication snapshot adapter
- **THEN** the public observability snapshot exposes those values under normalized `<subsystem>/<published_tag>` keys as numeric values

### Requirement: Plant Calculation Outputs Are Exposed In The Same Snapshot
The public observability snapshot SHALL expose plant-calculation outputs alongside published subsystem measurements.

#### Scenario: Plant calculations appear in observables
- **WHEN** plant calculations have produced outputs during runtime execution
- **THEN** the public observability snapshot includes those outputs in `observables.plant_calculation_outputs` as a stable numeric mapping

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

### Requirement: The Snapshot Exposes Only Substrate State And Stays Additive
The first-slice observability snapshot SHALL remain limited to substrate-owned physical/runtime state and SHALL not introduce gameplay or economics policy fields.

#### Scenario: Economics and gameplay semantics stay out of the substrate snapshot
- **WHEN** a contributor inspects the observability snapshot contract
- **THEN** it does not include pricing, scoring, tutorial progression, cash-ledger state, or other higher-layer policy fields

### Requirement: Snapshot Results Do Not Leak Live Mutable Runtime Structures
The public observability snapshot SHALL return serializable copies of runtime-owned state rather than direct references to mutable registries or runtime containers.

#### Scenario: Callers cannot mutate live substrate state through the snapshot payload
- **WHEN** a caller reads the public observability snapshot
- **THEN** the returned mappings and sequences are safe read copies and not direct mutable handles into runtime internals

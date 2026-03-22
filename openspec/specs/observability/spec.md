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
- `observables: Mapping[str, object]` with `published_measurements: Mapping[str, float]` and `plant_calculation_outputs: Mapping[str, float]`

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

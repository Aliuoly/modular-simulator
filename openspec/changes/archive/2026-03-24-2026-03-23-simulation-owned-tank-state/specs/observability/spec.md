## MODIFIED Requirements

### Requirement: First-Slice Snapshot Shape Is Frozen
The public observability snapshot SHALL expose exactly these top-level fields and sections:
- `schema: str`
- `graph_revision: str | None`
- `runtime: Mapping[str, object]` with `simulation_time_s: float`, `macro_step_index: int`, and `macro_step_active: bool`
- `queue: Mapping[str, object]` with `queued_request_ids: tuple[str, ...] | list[str]`, `queued_request_count: int`, and `committed_idempotency_keys: tuple[str, ...] | list[str]`
- `observables: Mapping[str, object]` with `published_measurements: Mapping[str, float]`, `plant_calculation_outputs: Mapping[str, float]`, and `process_state_values: Mapping[str, float]`

#### Scenario: Additive process-state observability keeps the top-level envelope unchanged
- **WHEN** a caller requests the public observability snapshot from a runtime that includes holding tanks
- **THEN** the top-level snapshot keys remain exactly `schema`, `graph_revision`, `runtime`, `queue`, and `observables`
- **AND** tank/process physical reads appear only under `observables.process_state_values`.

### Requirement: Process-State Observability Uses Normalized Numeric Keys
The public observability snapshot SHALL expose substrate-owned conserved process state through `observables.process_state_values` as a normalized numeric mapping.

#### Scenario: Holding tank publishes stable process-state reads through near-empty regularization
- **WHEN** a holding tank participates in runtime with ordinary or near-empty holdup
- **THEN** `observables.process_state_values` always includes `<process_id>/holdup_total_mol` and `<process_id>/outlet_flow_mol_s`
- **AND** `observables.process_state_values` includes `<process_id>/bulk_temperature_K` plus one numeric `<process_id>/mole_fraction/<species_id>` key per published species in the mixed bulk state
- **AND** when the tank is clipped to its small positive near-empty floor, `outlet_flow_mol_s` may report a clipped near-zero positive observable rather than exact zero for continuity
- **AND** that clipped near-zero observable SHALL NOT by itself authorize additional material transfer once withdrawable holdup above the configured floor is exhausted
- **AND** when the tank is clipped to that near-empty floor, `bulk_temperature_K` and mole-fraction keys retain the previous bulk-state values for observability continuity
- **AND** `bulk_temperature_K` is a lumped bulk-state read rather than a claim of full energy-balance, stratification, or EOS closure
- **AND** those values are derived from substrate-owned tank state rather than gameplay-owned mirrors or direct persistence-payload dumping.

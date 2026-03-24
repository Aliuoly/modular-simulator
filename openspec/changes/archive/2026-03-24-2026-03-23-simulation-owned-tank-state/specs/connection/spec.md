## ADDED Requirements

### Requirement: Connection Runtime Advances Conserved Process State After Canonical Flow Resolution
For units with substrate-owned conserved holdup, the connection runtime SHALL own canonical boundary-condition application during runtime coupling without delegating that ownership to gameplay code, while the unit process model remains the owner of differential state advance.

#### Scenario: Canonical hydraulic flow drives requested outlet demand
- **WHEN** canonical hydraulic solve and boundary propagation resolve per-inlet transferred conditions and per-outlet requested withdrawal demand for a conserved-holdup unit
- **THEN** the runtime coupling path applies the transferred inlet state plus requested outlet through-flow demand during `connection_runtime_coupling` for consumption on the next `subsystem_process_step` under the existing process-then-runtime phase order
- **AND** gameplay/session code does not inject, overwrite, or mirror those physical boundary conditions.

#### Scenario: Unit process model owns realized outlet state
- **WHEN** a holding tank updates holdup for a macro step
- **THEN** the authoritative holdup advance occurs through the unit’s `ProcessModel.step()` lifecycle rather than a gameplay helper or macrostep-only runtime integrator
- **AND** downstream propagated transfer, runtime inlet/outlet snapshots, and public observability use the tank model’s realized outlet condition rather than the raw requested outlet demand
- **AND** transferable outlet flow over a step never exceeds the withdrawable holdup above the configured near-empty floor.

#### Scenario: Connected plants keep the existing process-then-runtime lifecycle
- **WHEN** a compiled connected plant contains `HoldingTank` or another conserved-holdup unit
- **THEN** the connected plant keeps the existing repo phase order with `subsystem_process_step` advancing the unit model through `process_model.step(duration)` and `connection_runtime_coupling` applying canonical runtime boundary conditions
- **AND** implementation does not add a second post-hydraulic tank-state integrator that would double-advance the same conserved-holdup state in one macro step.

### Requirement: Runtime-Coupled Process State Remains Distinct From The Public Read Model
The runtime SHALL keep conserved process runtime state separate from the public observability snapshot while allowing the public snapshot to project additive read values from that state.

#### Scenario: Persistence and observability stay distinct
- **WHEN** checkpoint persistence captures `process_runtime_state` and public observability exposes `process_state_values`
- **THEN** the observability payload remains a separate consumer-facing read model rather than a direct dump of persistence structures.

### Requirement: Conserved Process Runtime State Round-Trips Through Persistence
Authoritative conserved process runtime state for holding tanks SHALL round-trip through checkpoint/export/restore without rebuilding that state from gameplay mirrors or lossy observability payloads.

#### Scenario: Holding-tank runtime state restores authoritatively
- **WHEN** checkpoint/export captures a runtime that includes holding-tank conserved holdup state and that runtime is later restored
- **THEN** the restored runtime reproduces the authoritative holding-tank process state from `process_runtime_state`
- **AND** later observability reads project from that restored runtime state rather than rebuilding tank state from gameplay-owned mirrors or `observables.process_state_values`.

## ADDED Requirements

### Requirement: Internal Tank-Custody Primitives Remain Session-Owned And Non-Public
Phase-1 gameplay SHALL keep staged tank-custody bookkeeping and purge-by-tank support under the gameplay/session layer as internal primitives, without widening the public simulation-session API or snapshot contracts in this change.

#### Scenario: Tank custody is keyed by process id and boundary id
- **WHEN** contributors inspect the staged tank-custody helper used by the simulation session and realtime-service runtime
- **THEN** stored custody state is keyed by holding-tank `process_id`
- **AND** boundary-route assignment is keyed by named boundary id for external bought/sold routes
- **AND** each boundary id has at most one active assigned tank at a time for those external routes

#### Scenario: Mixed tank contents are stored as one aggregate inventory state
- **WHEN** multiple incoming stream contributions are applied to the same staged tank-custody record
- **THEN** the helper combines them into one aggregate stored inventory state suitable for later outlet-pressure and volume calculation
- **AND** that state preserves repo-consistent thermodynamic fields such as temperature, pressure, species ids/composition, and repo-defined optional phase, enthalpy, entropy, or equivalent fields
- **AND** that state is represented as one mixed inventory record rather than separate per-source purity buckets

#### Scenario: Internal purge clears one tank custody record without widening live contracts
- **WHEN** the staged purge primitive clears custody for one holding-tank `process_id`
- **THEN** it removes only that tank's stored custody state
- **AND** it does not delete the tank record, alter ledger state, or require a new public session method, snapshot field, HTTP route, or Godot command

#### Scenario: Internal staging proof does not widen supported build items or start allowlists
- **WHEN** tests exercise the module-private helper in `src/modular_simulation/gameplay/realtime_service.py` that `_install_unit()` uses to stage `place_holding_tank`
- **THEN** that non-public proof stages the tank from catalog metadata without requiring a public build-item change or a current-start allowlist change
- **AND** `SUPPORTED_BUILD_ITEM_IDS` and all current start allowlists remain unchanged in the live playable slice

#### Scenario: Boundary-route uniqueness does not limit general tank connectivity
- **WHEN** contributors inspect the staged one-route-per-boundary bookkeeping rule
- **THEN** that rule applies only to external bought/sold boundary-route assignment
- **AND** it does not by itself forbid future non-boundary multi-stream fan-in or fan-out connections on tanks

## Why

Landed `4fm` solved infrastructure staging, but repo reality now shows that its tank ownership boundary is wrong for live use. `src/modular_simulation/gameplay/tank_custody.py` mirrors physical tank inventory in gameplay and adds `molar_flow_rate` directly into stored `total_mol`, while `src/modular_simulation/unit_processes/storage/holding_tank.py` drains full starting holdup every step and replaces stored holdup with `inlet_flow * dt`. The live `session` spec now also contradicts itself by requiring both substrate-owned observability reads and gameplay-owned internal tank custody.

`ModularSimulator-ej7` owns the later live gas-starter rewrite, real feed/product naming, live tank-mediated gameplay contracts, sale-spec policy, and progression. That work should not freeze against the current nonphysical tank model or gameplay-owned inventory mirror. `ModularSimulator-9tr.2` remains valid follow-up hardening for metadata-resolution failures, but it does not unblock the physical ownership dependency.

`ej7.1` therefore needs a corrective OpenSpec pack first: freeze simulation-owned minimal tank semantics, the substrate/runtime seam that applies canonical tank boundary conditions, and the observability read model that higher layers must consume before direct ej7 planning or implementation continues.

## What Changes

- Replace gameplay-owned tank inventory ownership with **simulation-owned conserved tank holdup**.
- Freeze the minimum physically transferable holding-tank semantics for this slice:
  - stored inventory is conserved amount state, not a flow-rate sample,
  - tank holdup advances through the repo-standard differential process-model / ODE-solver path rather than a macrostep-only bookkeeping update,
  - runtime/hydraulic logic supplies requested outlet demand as a boundary condition and the tank model clips depletion with a small positive numerical floor,
  - outlet composition and temperature follow a lumped well-mixed bulk state, retaining the previous bulk state at the near-empty floor.
- Extend the substrate-owned observability contract with additive **process/tank state values** under `observables`, while keeping the frozen top-level snapshot envelope unchanged.
- Freeze a substrate/runtime-owned boundary-application seam so connection runtime can supply canonical inlet conditions and requested outlet demand to conserved-state units without gameplay bookkeeping.
- Require authoritative conserved tank state to round-trip through checkpoint/export/restore via runtime-owned process state rather than gameplay mirrors or observability payloads.
- Remove or supersede the gameplay-owned `tank_custody` physical-inventory direction introduced by `4fm`.

## Capabilities

### Modified Capabilities
- `session`
- `observability`
- `units-and-components`
- `connection`

## Impact

- Affected code:
  - `src/modular_simulation/unit_processes/storage/holding_tank.py`
  - `src/modular_simulation/connection/runtime/process_stream_io.py`
  - `src/modular_simulation/connection/runtime/runtime.py`
  - `src/modular_simulation/connection/runtime/thermo_coupling.py`
  - `src/modular_simulation/connection/runtime/runtime_persistence.py`
  - `src/modular_simulation/connection/topology/network.py`
  - `src/modular_simulation/cli/backend_session.py`
  - `src/modular_simulation/gameplay/tank_custody.py` (remove or sharply narrow; no longer physical-state owner)
- Affected tests:
  - `tests/unit_process/test_layer4_holding_tank.py`
  - `tests/connection/test_connected_plant_orchestrator.py`
  - `tests/connection/test_connection_runtime_sequence.py`
  - `tests/connection/test_network_api.py`
  - `tests/cli/test_backend_session.py`
  - `tests/connection/test_thermo_coupling_runtime_store.py`
  - `tests/connection/test_runtime_persistence_contract.py`
  - `tests/gameplay/test_tank_custody.py` (remove/replace with ownership-boundary regression)
  - `tests/gameplay/test_realtime_game_service.py`
  - `tests/gameplay/test_sandbox_catalog.py`
  - `tests/gameplay/test_start_catalog.py`
  - `tests/gameplay/test_sandbox_session.py`
- Explicitly deferred to existing Beads follow-ons:
  - `ModularSimulator-ej7` — live gas-starter rewrite, public tank-mediated gameplay, real feed/product naming, sale-spec policy, progression
  - `ModularSimulator-9tr.2` — metadata-resolution error hardening for `_resolve_unit_metadata()` failures
  - `ModularSimulator-9tr.1` — later player-managed transport/logistics

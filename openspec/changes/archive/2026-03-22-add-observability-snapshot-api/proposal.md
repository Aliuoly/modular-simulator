## Why

The simulation substrate already exposes topology, stepping, and persistence, but higher layers still lack a stable, policy-free read model for runtime observability. This change adds that missing substrate-owned snapshot surface now so economics and gameplay layers can read physical-state rollups without scraping low-level runtime internals or pulling pricing logic downward.

## What Changes

- Add a new substrate capability for stable observability snapshots that package runtime state, queued reconfiguration state, published measurements, and plant-calculation outputs into a consumer-facing read model.
- Freeze `ConnectionNetwork` as the owner of the snapshot contract and keep `PlantBackendSession` as a thin forwarding facade rather than a gameplay/economics policy owner.
- Define the first slice of additive observability rollups for simulation time, topology revision, queue state, published subsystem measurements, and plant calculation outputs.
- Keep pricing, tutorial progression, ledger rules, and other economics or gameplay policy out of scope for this substrate change.

## Capabilities

### New Capabilities
- `observability-snapshot-api`: stable substrate-owned observability snapshot contract for higher-layer consumers.

### Modified Capabilities
- `sandbox-session-and-heuristic-economics`: clarify that higher-layer economics and gameplay observability reads consume the substrate snapshot surface rather than reconstructing physical-state signals from runtime internals.

## Impact

- Affected code: `src/modular_simulation/connection/topology/network.py`, `src/modular_simulation/connection/runtime/connected_plant_orchestrator.py`, and `src/modular_simulation/cli/backend_session.py`.
- Affected tests: add substrate-facing contract coverage under `tests/cli/`, `tests/connection/`, and integration coverage for runtime workflows.
- Affected docs/artifacts: new OpenSpec capability plus a delta on the sandbox/economics spec to keep ownership boundaries explicit.
- Dependency: this work must preserve the existing educational-backend positioning requirement that `PlantBackendSession` remains substrate and not a gameplay/economics policy owner.

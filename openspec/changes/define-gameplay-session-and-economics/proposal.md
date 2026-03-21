## Why

The user vision includes upgrades, money, profitability, observability, and stepwise plant improvement. The repo already has runtime plant-editing APIs and physically grounded simulation outputs, but it does not yet define how a gameplay session should start a scenario, quote an upgrade, apply an upgrade, advance the plant, or compute profit from plant behavior.

If those concerns are not isolated in a dedicated pack, implementers would likely push progression rules into `PlantBackendSession`, invent clicker-style income detached from simulation outputs, or mix scenario policy with the hydraulic/runtime substrate.

## What Changes

- Add a new `gameplay-session-and-economics` capability that defines the minimal gameplay orchestration layer above the simulation core.
- Specify a dedicated gameplay package, its public contracts, the handoff from scenario-authored upgrades/objectives, and the boundary between substrate hooks and gameplay policy.
- Require economics to be deterministic, scenario-local, step-based, and derived from simulation outputs plus installed assets with explicit field semantics.

## Capabilities

### New Capabilities
- `gameplay-session-and-economics`: gameplay session orchestration, upgrade quotation/purchase flow, progression snapshotting, and simulation-derived economics.

## Impact

- Affected code: new modules under `src/modular_simulation/gameplay/`, with only thin helper hooks allowed in `src/modular_simulation/cli/backend_session.py` when strictly needed.
- Affected tests: `tests/gameplay/test_contracts.py`, `tests/gameplay/test_economics.py`, `tests/gameplay/test_game_backend_session.py`, and `tests/integration/test_gameplay_smoke.py`.
- Dependency: this pack depends on both `clarify-educational-backend-positioning` and `define-phase1-starter-scenarios`.

## Why

Current repo framing is split between a generic closed-loop simulation framework (`docs/README.md`) and a game-like interactive plant backend (`docs/plant_backend_session_user_guide.md`, `src/modular_simulation/cli/backend_session.py`). That mismatch makes it hard to tell whether this repository is supposed to be a general simulation sandbox, a classroom backend, or a game substrate.

The requested product vision adds educational intent, progression constraints, and realism boundaries. Before scenario catalogs or gameplay APIs are added, the repo needs one narrow change that freezes the product position, target audience, first-phase teaching scope, and what is intentionally deferred.

## What Changes

- Add a new `educational-backend-positioning` capability that defines the repository as a simulation-first backend for educational chemical-process gameplay and classroom exercises.
- Freeze phase 1 as a narrow continuous-process starter curriculum with three teaching tracks: topology/separation, reactor/control, and recycle/process-design.
- Clarify that `Flowsheet`, hydraulic solving, and `PlantBackendSession` remain the simulation/runtime-editing substrate; progression and economics belong to later gameplay-layer packs.
- Make non-goals explicit: batch-first gameplay, open-ended chemistry sandboxing, staffing/fouling systems, and multi-plant vertical integration.

## Capabilities

### New Capabilities
- `educational-backend-positioning`: repo identity, target audience, phase-1 scope, fidelity boundaries, and substrate ownership.

## Impact

- Affected docs: `docs/README.md`, `docs/plant_backend_session_user_guide.md`, and a new `docs/game_backend_overview.md`.
- Affected tests: add a docs-contract regression such as `tests/test_game_backend_positioning.py` and keep existing doc alignment checks green.
- No simulation-core or gameplay-runtime code is required by this pack; it is the prerequisite framing pack for the starter-scenario and gameplay-session follow-on packs.

## Why

The repo now has phase-1 gameplay primitives (`sandbox_session`, `economics`, frozen starts, and the build catalog), but it still does not provide an actual playable game loop. There is no transport boundary for a client, no always-running session owner, no topology-plus-layout snapshot for rendering, and no Godot client.

The user explicitly wants a continuous realtime-like experience with **no pause feature**, a **Godot** client, **60 FPS rendering decoupled from simulation updates**, and the ability to run finer simulation `dt` values when small systems can afford it. The current gameplay modules are still module-scoped and step-driven, which is enough for backend tests but not enough for a long-running playable slice.

Without this pack, implementation would have to guess:
- where the authoritative realtime loop lives,
- how Godot talks to the backend,
- how plant topology and board layout are exposed together,
- and whether the client must manually orchestrate backend receipt handoffs.

## What Changes

- Add a new `phase1-realtime-godot-vertical-slice` capability for the first playable local game slice.
- Define a thin Python game-service layer above `sandbox_session`, `economics`, and `PlantBackendSession` that owns continuous session ticking, player-intent command orchestration, and JSON-friendly snapshots for a client.
- Define the first Godot 4 client scope: fixed-camera 2.5D presentation, 60 FPS rendering, no pause affordance, and a narrow playable feature set grounded in the existing sandbox plus the heater/flash tutorial.
- Explicitly keep this slice local, single-player, and ephemeral rather than silently promising multiplayer or cross-process save/resume.

## Capabilities

### New Capabilities
- `phase1-realtime-godot-vertical-slice`: always-running local session service, Godot client bridge, combined gameplay/topology snapshot, and first playable heater/flash-oriented vertical slice.

## Impact

- Affected code:
  - `src/modular_simulation/gameplay/sandbox_session.py`
  - `src/modular_simulation/gameplay/economics.py`
  - new game-service modules under `src/modular_simulation/gameplay/`
  - new API entrypoint under `src/modular_simulation/app/`
  - `pyproject.toml` for explicit service/runtime dependencies if needed
  - a new Godot project under `clients/godot_phase1_vertical_slice/`
- Affected tests:
  - extend existing gameplay tests to preserve current contracts while enabling instance-backed runtimes
  - add service/API/integration coverage under `tests/gameplay/`, `tests/app/`, and `tests/integration/`
  - add a Godot headless smoke inside the new client project
- Affected docs:
  - `docs/game_backend_overview.md`
  - `docs/plant_backend_session_user_guide.md`
  - new runbook doc for the Godot vertical slice
- Dependencies:
  - builds on the already-landed `phase1-sandbox-build-catalog` and `sandbox-session-and-heuristic-economics` capabilities
  - keeps `PlantBackendSession` as substrate rather than moving gameplay policy into it

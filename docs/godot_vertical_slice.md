# Godot Phase-1 Vertical Slice Runbook

This runbook covers local startup and smoke checks for the first playable Godot vertical slice that consumes the realtime game service.

## Scope (Supported Modes)

The current slice supports exactly these mode ids:

- `phase1_process_sandbox_v1`
- `heater_flash_guided_build_v1`

No additional modes are in scope for this playable slice.

## Architecture Positioning

- `PlantBackendSession` remains the low-level simulation/topology substrate.
- `RealtimeGameService` + `game_api.py` are the client transport seam.
- The Godot project under `clients/godot_phase1_vertical_slice/` is a consumer of that API.

## Required Environment Variables

- `MODSIM_GAME_API_BASE_URL`
  - Used by `BackendClient` in the Godot project.
  - Example: `http://127.0.0.1:8000`
- `MODSIM_GODOT_SMOKE_MODE`
  - Used by `clients/godot_phase1_vertical_slice/tests/smoke_test.gd`.
  - Allowed values: `phase1_process_sandbox_v1` or `heater_flash_guided_build_v1`.
  - If omitted, smoke defaults to `phase1_process_sandbox_v1`.

## Start the Backend API

From repo root:

```bash
uv run uvicorn modular_simulation.app.game_api:app --host 127.0.0.1 --port 8000
```

The Godot client expects `/game/bootstrap` and the phase-1 game routes exposed by this API.

## Start the Godot Client (Interactive)

From repo root:

```bash
MODSIM_GAME_API_BASE_URL=http://127.0.0.1:8000 \
godot4 --path clients/godot_phase1_vertical_slice
```

Client behavior for this slice:

- fixed camera, no free rotation,
- 2.5D board presentation,
- no pause button and no pause hotkey.

## Run Godot Headless Smoke

Sandbox smoke:

```bash
MODSIM_GAME_API_BASE_URL=http://127.0.0.1:8000 \
MODSIM_GODOT_SMOKE_MODE=phase1_process_sandbox_v1 \
godot4 --headless --path clients/godot_phase1_vertical_slice --script res://tests/smoke_test.gd
```

Tutorial smoke:

```bash
MODSIM_GAME_API_BASE_URL=http://127.0.0.1:8000 \
MODSIM_GODOT_SMOKE_MODE=heater_flash_guided_build_v1 \
godot4 --headless --path clients/godot_phase1_vertical_slice --script res://tests/smoke_test.gd
```

## Persistence Limitation (Current)

Session persistence for this slice is restart-only:

- supported: in-process `restart` of the active session,
- out of scope: cross-process save/resume for player sessions.

`PlantBackendSession` checkpoint functions exist at substrate level, but this slice does not surface them as a player-facing save system.

## Known Headless Note

In some headless/dummy-renderer runs, Godot may print non-fatal `mesh_get_surface_count` noise.

- Treat this as non-blocking unless the smoke exits non-zero or assertions fail.
- Use smoke exit code and explicit assertion failures as the pass/fail source of truth.

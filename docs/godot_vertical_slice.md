# Godot Phase-1 Vertical Slice Runbook

This runbook covers local startup and smoke checks for the first playable Godot vertical slice that consumes the realtime game service.

## Scope (Supported Modes)

The current slice supports exactly these mode ids:

- `phase1_process_sandbox_v1`
- `heater_flash_guided_build_v1`

No additional modes are in scope for this playable slice.

## Gas-First Progression Notes

- `phase1_process_sandbox_v1` starts on the gas-first starter batch (`place_inlet_gas_separator`, `place_teg_contactor`, `place_rich_glycol_flash_tank`, `place_lean_rich_glycol_exchanger`, `place_teg_regenerator`, `install_glycol_circulation_pump`, `build_process_line`).
- The sandbox HUD/snapshot exposes progression state (`active_stage_id`, unlocked stages, currently unlocked build items, available research ids).
- The research command is part of the slice: `POST /game/sessions/{session_id}/commands/submit-research` with payload `{research_id, submitted_quantities_by_product_id}`.
- `buy-feed` and `sell-product` remain direct id+quantity commands in this slice (no public `tank_id` payload).

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
- snapshot-driven world rendering of authoritative boundaries, units, and process lines,
- panel-first process-line authoring using explicit source/target endpoint selection,
- active background snapshot polling after session start,
- serialized HTTP request use on the shared Godot `HTTPRequest` node so polling and commands do not overlap,
- no pause button and no pause hotkey.

## Current Client Interaction Notes

- `build_process_line` is now authored from the existing build panel rather than hard-stopping with an endpoint error.
- Source choices come from public source boundaries plus process outlet endpoints in the authoritative snapshot.
- Target choices come from public sink boundaries plus process inlet endpoints in the authoritative snapshot.
- The client generates orthogonal `layout.path_xy` polylines with 90-degree elbows from authoritative process anchors plus fixed boundary anchors for the current slice.
- The first pass uses simple keep-out rectangles around placed unit anchors to avoid routing lines directly through occupied unit positions.
- Richer in-world line drawing and direct click/drag authoring remain deferred.

## Current World Rendering Notes

- `WorldRenderer` rebuilds the visible board state from each authoritative snapshot instead of maintaining a separate client-side simulation.
- Units render from `board_layout.unit_entities_by_process_id[*].anchor_xy`.
- Process lines render from `board_layout.line_entities_by_line_id[*].path_xy`.
- Public boundaries render only when they are present in the authoritative topology payload, but keep their current slice-local fixed anchor positions.
- Rendering remains intentionally minimal: deterministic primitive meshes, fixed heights per layer, and no animated flow or richer overlay claims in this pack.

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

Smoke expectations for this pack:

- sandbox mode proves panel-driven line building from explicit endpoint selections,
- sandbox mode observes at least one post-mount polling-only snapshot update,
- the world renderer exposes authoritative boundary, unit, and line ids that match the current snapshot,
- tutorial mode proves the same polling startup/teardown lifecycle without widening tutorial scope,
- restart re-renders the authoritative world state after reset,
- teardown returns through the real title-screen path and stops polling cleanly.

## Persistence Limitation (Current)

Session persistence for this slice is restart-only:

- supported: in-process `restart` of the active session,
- out of scope: cross-process save/resume for player sessions.

`PlantBackendSession` checkpoint functions exist at substrate level, but this slice does not surface them as a player-facing save system.

## Known Headless Note

In some headless/dummy-renderer runs, Godot may print non-fatal `mesh_get_surface_count` noise.

- Treat this as non-blocking unless the smoke exits non-zero or assertions fail.
- Use smoke exit code and explicit assertion failures as the pass/fail source of truth.

## Known Local Blocker

If `godot4` is not installed in the local environment, the headless smoke command cannot run and will fail with command-not-found. Treat this as an environment blocker, not a gameplay contract failure.

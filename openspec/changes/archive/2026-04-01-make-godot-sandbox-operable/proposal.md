## Why

The current Godot slice has the backend contracts and UI scaffolding for the gas-first sandbox, but it is still not operable from the client. Repo evidence shows three concrete blockers:

- `clients/godot_phase1_vertical_slice/scripts/build_command_panel.gd` hard-stops `build_process_line` with `"Line build requires explicit endpoints"`, so the client cannot assemble the required sandbox topology.
- `clients/godot_phase1_vertical_slice/scripts/session_store.gd` has no background snapshot polling and leaves `stop_polling()` as a stub, even though the live client spec already assumes an always-running session with lower-frequency client polling.
- `clients/godot_phase1_vertical_slice/tests/smoke_test.gd` currently calls `store.refresh_snapshot()` manually after `MainGame` appears because the initial snapshot signal fires before the HUD exists, proving the current client is still relying on one-shot refreshes instead of sustained authoritative sync.

Without this pack, the repo still has a “slice-shaped demo” rather than an actually operable local sandbox loop in Godot.

## What Changes

- Add a panel-only process-line authoring flow to the Godot build panel so the player can choose explicit source and target endpoints from the authoritative snapshot and submit `build_process_line` without in-world click/drag interaction.
- Use smart panel-generated orthogonal line routing for this first pass: the client should generate 90-degree-elbow `path_xy` polylines that avoid occupied unit anchors well enough for the current sparse board instead of sending naive straight segments through equipment.
- Add continuous active-session snapshot polling in the Godot client, using a lower-frequency sync loop than the render loop and a safe request lifecycle that does not overlap `HTTPRequest` use across polls and commands.
- Update the Godot smoke harness and runbook so completion is proven by the real client path: title flow → sandbox session → panel-driven line build → automatic snapshot refresh → visible sandbox-loop state changes.
- Keep scope deliberately narrow: no richer in-world renderer, no websocket transport, no new backend routes, and no expansion of the playable mode list.

## Capabilities

### Modified Capabilities
- `client-godot`

## Impact

- Affected code:
  - `clients/godot_phase1_vertical_slice/scenes/MainGame.tscn`
  - `clients/godot_phase1_vertical_slice/scripts/build_command_panel.gd`
  - `clients/godot_phase1_vertical_slice/scripts/session_store.gd`
  - `clients/godot_phase1_vertical_slice/scripts/bootstrap_controller.gd`
  - `clients/godot_phase1_vertical_slice/scripts/backend_client.gd` if request lifecycle coordination must move down to the transport helper
  - `clients/godot_phase1_vertical_slice/tests/smoke_test.gd`
- Affected tests:
  - `clients/godot_phase1_vertical_slice/tests/smoke_test.gd`
  - `tests/integration/test_game_vertical_slice_smoke.py` as backend sanity coverage while the client path is hardened
- Affected docs:
  - `docs/godot_vertical_slice.md`
- Affected OpenSpec sync surfaces after implementation:
  - `openspec/changes/make-godot-sandbox-operable/specs/client-godot/spec.md`
  - `openspec/specs/client-godot/spec.md`

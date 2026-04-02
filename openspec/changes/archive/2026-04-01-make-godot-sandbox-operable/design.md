## Context

- `clients/godot_phase1_vertical_slice/scripts/build_command_panel.gd` currently supports unit placement, feed purchase, sell-product, research, and restart, but it immediately rejects `build_process_line` instead of collecting endpoints.
- `src/modular_simulation/gameplay/realtime_service.py` and `src/modular_simulation/gameplay/service_contracts.py` already expose the authoritative data needed for line authoring and sync: `GameSnapshot.topology`, `GameSnapshot.board_layout`, `supported_build_item_ids`, and `lag_backlog_s`.
- `src/modular_simulation/gameplay/board_layout.py` already serializes unit anchors and line paths, so the client does not need new backend routes to derive panel choices.
- `clients/godot_phase1_vertical_slice/scripts/session_store.gd` currently refreshes only on explicit calls or successful commands, while `clients/godot_phase1_vertical_slice/tests/smoke_test.gd` proves that this misses the intended always-running sync model.
- `clients/godot_phase1_vertical_slice/scripts/backend_client.gd` uses one `HTTPRequest` node for all calls. Godot’s `HTTPRequest` guidance warns against simultaneous requests on a single node, so polling and commands must be coordinated deliberately rather than left to race.

## Goals / Non-Goals

**Goals**
- Make the sandbox operable from the existing Godot client by enabling explicit panel-driven line creation.
- Make active sessions feel alive from the client by continuously syncing authoritative snapshots at a lower frequency than rendering.
- Prove the operable path with headless Godot smoke that no longer depends on manual `refresh_snapshot()` as the primary synchronization mechanism after scene load.

**Non-Goals**
- Add direct in-world line drawing, drag-to-connect interaction, or richer 3D rendering.
- Change the backend HTTP route surface, command payloads, supported modes, or session semantics.
- Add websockets, pause/resume, save/load, or broader UI polish work.
- Redesign the build panel into a generalized late-game topology editor.

## Decisions

1. **Line authoring is panel-first, not scene-first.**
   - The first operability pass extends `BuildCommandPanel` with explicit source/target endpoint selection controls.
   - The client sends the exact endpoint strings already frozen by the session/build contract (`boundary_id` for public boundaries and `<process_id>.<port_name>` for process ports).
   - This pack intentionally prefers reliable operability over immersive interaction.

2. **Endpoint choices come from the authoritative snapshot, with direction-aware filtering.**
   - Source choices must include source boundaries and process outlet endpoints.
   - Target choices must include sink boundaries and process inlet endpoints.
   - The panel must not preselect hidden defaults; the user should make an explicit choice before line submission.
   - When the topology changes, the endpoint lists refresh from the newest snapshot rather than maintaining a client-invented topology cache.

3. **Panel-authored lines use deterministic orthogonal routing in this pack.**
   - `build_process_line` still requires `layout.path_xy` with at least two points, so the client must generate that payload even in panel-only mode.
   - For this pack, `BuildCommandPanel` derives `path_xy` as a Manhattan-style polyline with 90-degree elbows, not a naive straight segment.
   - Process endpoint anchors come from `board_layout.unit_entities_by_process_id[process_id].anchor_xy`.
   - Public boundary anchors are fixed client-side constants chosen to match the existing minimal board framing for current slice ids (`sweet_wet_gas`, `separator_gas`, `unstabilized_condensate`, `dry_gas`, `ngl_liquids`, `stabilized_condensate`, and the tutorial feed/vapor/liquid boundaries).
   - The client should route around placed units using simple keep-out rectangles centered on authoritative unit anchors, with a fixed slice-local footprint/padding heuristic suitable for the current sparse board.
   - A valid route may use the smallest number of elbows that avoids occupied keep-out boxes; if no valid orthogonal route is found, the panel rejects the line build locally with a visible status rather than inventing a malformed `path_xy` payload.

4. **Polling is active-session sync, not a render-loop responsibility.**
   - `SessionStore` owns background polling for the active session.
   - Poll cadence should remain visibly lower than render cadence and suitable for local HTTP request/response play (for this pack, a simple fixed interval in the 500–1000 ms range is sufficient).
   - The polling lifecycle starts after successful session creation.
   - Because `SessionStore` outlives `MainGame` under `Bootstrap.tscn`, `BootstrapController` must own scene-transition teardown and call `SessionStore.stop_polling()` before clearing `ScreenRoot` or switching away from the active game scene.

5. **One `HTTPRequest` node means one in-flight request at a time.**
   - Because `backend_client.gd` uses a single `HTTPRequest`, the implementation must prevent polling and command requests from overlapping on that node.
   - A simple serialized request gate is acceptable for this pack: polling skips or waits while a command is in flight, and command-triggered authoritative snapshots remain the source of truth after success.
   - If implementation moves coordination into `backend_client.gd`, it should still preserve the same external request methods and avoid widening transport surface area.

6. **Smoke verification must prove the playable loop through the real UI path.**
   - The smoke should no longer rely on manual refresh as the only way to demonstrate HUD wiring after `MainGame` mounts.
   - Sandbox smoke must drive the real panel controls far enough to build at least the minimal separator loop and observe an idle post-mount snapshot change delivered by polling alone rather than by command success or `_ready()` hydration.
   - Tutorial smoke remains in scope for this pack and must prove polling startup plus teardown under `heater_flash_guided_build_v1`, even if it does not build the full sandbox loop.

## Risks / Trade-offs

- **Panel endpoint lists may become unwieldy as topology grows.**
  - Mitigation: keep scope narrow to current slice scale and structure the controls so filtering/search can be added later without changing the line-build contract.
- **Polling can race with command requests and produce transport errors on the single `HTTPRequest` node.**
  - Mitigation: require explicit request serialization in `SessionStore`/`BackendClient` and verify stop/cleanup behavior in smoke.
- **The client may remain visually sparse even after it becomes operable.**
  - Mitigation: declare richer rendering out of scope in this pack so operability is not blocked on polish.

## Verification Strategy

- TDD should lead the Godot smoke and any targeted Python sanity updates before client-side implementation changes.
- Required verification for implementation:
  - `uv run pytest tests/integration/test_game_vertical_slice_smoke.py`
  - `godot4 --headless --path clients/godot_phase1_vertical_slice --script res://tests/smoke_test.gd`
  - `MODSIM_GODOT_SMOKE_MODE=heater_flash_guided_build_v1 godot4 --headless --path clients/godot_phase1_vertical_slice --script res://tests/smoke_test.gd`
- Expected evidence:
  - the Godot build panel can submit `build_process_line` through explicit endpoint choices instead of hard-rejecting the action,
  - panel-authored line commands generate deterministic orthogonal `path_xy` payloads with 90-degree elbows from authoritative process anchors and fixed boundary anchors,
  - the generated path avoids occupied unit keep-out boxes for the current slice layouts instead of drawing straight through placed equipment,
  - active sessions poll authoritative snapshots without manual refresh driving the normal HUD update path,
  - the smoke observes at least one post-mount snapshot change that arrives from polling alone rather than from command success or `_ready()` hydration,
  - polling and commands do not collide on the shared HTTP transport lifecycle,
  - sandbox smoke can build enough topology through the real UI to observe feed/product or other authoritative state change,
  - tutorial smoke proves polling starts and stops cleanly for the tutorial mode as well,
  - `stop_polling()` becomes real cleanup rather than a stub,
  - richer in-world rendering remains deferred and is not silently expanded in this pack.

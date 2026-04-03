## Dependency gate

- [x] D0 Do not start implementation until this change pack is approved and the implementation packet is created in Beads from these tasks.
  - Implementation proceeded after change approval under explicit user override because local Beads/Dolt execution tracking was unavailable in this environment.

## Wave 1 — Lock the operability target with failing verification first

- [x] 1.1 Extend `clients/godot_phase1_vertical_slice/tests/smoke_test.gd` so sandbox mode proves the real UI path can select explicit line endpoints and no longer treats `store.refresh_snapshot()` as the normal post-load synchronization path.
  - Drive the existing `BuildPanel` controls rather than bypassing them.
  - Add assertions that fail while `build_process_line` still returns `"Line build requires explicit endpoints"`.
- [x] 1.2 Update smoke expectations for background sync and cleanup:
  - assert that authoritative snapshot updates arrive after `MainGame` mounts without relying on a manual refresh call,
  - assert that at least one observed post-mount snapshot change comes from polling alone rather than from command success or `_ready()` hydration,
  - assert that `store.stop_polling()` performs real shutdown behavior.
- [x] 1.3 Extend `clients/godot_phase1_vertical_slice/tests/smoke_test.gd` so tutorial mode (`MODSIM_GODOT_SMOKE_MODE=heater_flash_guided_build_v1`) proves polling startup and teardown for the non-sandbox path without widening tutorial scope beyond the current slice.
- [x] 1.4 Run the failing/known-baseline verification boundary before client edits so the pack starts from a known state:
  - `godot4 --headless --path clients/godot_phase1_vertical_slice --script res://tests/smoke_test.gd`
  - `MODSIM_GODOT_SMOKE_MODE=heater_flash_guided_build_v1 godot4 --headless --path clients/godot_phase1_vertical_slice --script res://tests/smoke_test.gd`
  - `uv run pytest tests/integration/test_game_vertical_slice_smoke.py`
  - Expected evidence: backend route smoke is green, while the Godot smoke still fails or proves the current client cannot yet satisfy the new operability assertions until implementation lands.

## Wave 2 — Make panel-first line building real

- [x] 2.1 Update `clients/godot_phase1_vertical_slice/scenes/MainGame.tscn` and `clients/godot_phase1_vertical_slice/scripts/build_command_panel.gd` to add the minimum controls needed for explicit process-line authoring inside the existing panel.
  - Keep the UX panel-only.
  - Do not add in-world click/drag interaction in this pack.
- [x] 2.2 Populate source and target choices from `SessionStore.latest_snapshot` using the authoritative topology/build-contract shape already exposed by the backend.
  - Sources must represent source boundaries plus process outlet endpoints.
  - Targets must represent sink boundaries plus process inlet endpoints.
  - Use exact build-contract endpoint strings when submitting the command.
- [x] 2.3 In `clients/godot_phase1_vertical_slice/scripts/build_command_panel.gd`, generate the required `layout.path_xy` for panel-authored lines as a deterministic two-point path from source anchor to target anchor.
  - Read process anchors from `latest_snapshot.board_layout.unit_entities_by_process_id`.
  - Use fixed client-side anchor constants for current public boundary ids.
  - Generate an orthogonal Manhattan-style polyline with 90-degree elbows that avoids simple keep-out rectangles around placed unit anchors.
  - Reject line submission locally with a visible status if either anchor is unavailable or no valid orthogonal route can be found.
- [x] 2.4 Preserve the narrow current-slice panel scope while adding line authoring.
  - Keep unit placement, buy-feed, sell-product, submit-research, and restart behavior intact.
  - Do not widen the playable mode list or invent a second client-side topology model.

## Wave 3 — Add continuous authoritative polling with safe request sequencing

- [x] 3.1 Update `clients/godot_phase1_vertical_slice/scripts/session_store.gd` so active sessions start background polling automatically after session creation and stop it cleanly on teardown/reset.
- [x] 3.2 Coordinate polling with the existing single-`HTTPRequest` transport in `clients/godot_phase1_vertical_slice/scripts/backend_client.gd`.
  - Prevent overlapping poll/command requests on the shared node.
  - Keep successful command responses authoritative and compatible with the polling loop.
- [x] 3.3 Update `clients/godot_phase1_vertical_slice/scripts/bootstrap_controller.gd` so screen transitions/teardown call `SessionStore.stop_polling()` before `ScreenRoot` is cleared or the active game scene is replaced.
- [x] 3.4 Replace the current `stop_polling()` stub with real cleanup semantics and ensure the smoke harness can observe them.

## Wave 4 — Verify the operable loop and sync docs/specs

- [x] 4.1 Make the updated Godot smoke pass:
  - `godot4 --headless --path clients/godot_phase1_vertical_slice --script res://tests/smoke_test.gd`
  - `MODSIM_GODOT_SMOKE_MODE=heater_flash_guided_build_v1 godot4 --headless --path clients/godot_phase1_vertical_slice --script res://tests/smoke_test.gd`
  - Expected evidence: title flow works, sandbox panel can build lines from explicit endpoints with orthogonal 90-degree-elbow `path_xy` that avoids occupied unit keep-out boxes, automatic polling updates the HUD after scene load, polling-only snapshot changes are observable after mount, tutorial mode also starts/stops polling correctly, and polling stops cleanly at shutdown.
- [x] 4.2 Re-run backend sanity coverage after the client changes:
  - `uv run pytest tests/integration/test_game_vertical_slice_smoke.py`
  - Expected evidence: the existing HTTP slice remains stable while the client becomes operable.
- [x] 4.3 Update `docs/godot_vertical_slice.md` to describe the actual client behavior after this pack.
  - Document panel-first line building.
  - Document active snapshot polling and any local caveat about shared-request serialization.
  - Keep richer in-world rendering explicitly deferred.
- [x] 4.4 Sync the implemented delta into `openspec/specs/client-godot/spec.md` and archive this change only after implementation plus verification are complete.
  - Spec sync is complete. Archive remains a separate workflow step after final review/closure.

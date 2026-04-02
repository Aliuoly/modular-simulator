## Context

- `world_renderer.gd` is currently a stub even though `MainGame.tscn` already mounts it under `World/WorldRenderer`.
- `board_layout.py` already exposes all render metadata needed for a first readable slice:
  - `unit_entities_by_process_id[*].anchor_xy`
  - `line_entities_by_line_id[*].path_xy`
- The fixed camera, HUD, build panel, and polling loop are already in place from the operability pack.

## Goals / Non-Goals

**Goals**
- Make the Godot world readable enough to understand placed equipment, boundaries, and lines at a glance.
- Keep rendering synchronized with the authoritative snapshot rather than inventing a second client state model.
- Prove render refresh and restart clearing through the headless Godot smoke.

**Non-Goals**
- Add in-world editing, drag-to-connect, or click-to-place interaction.
- Add flow animation, throughput visualization, or richer simulation-state overlays.
- Add new backend routes, websocket transport, or art-heavy polish.

## Decisions

1. **Rendering stays snapshot-driven and rebuild-oriented.**
   - `WorldRenderer` rebuilds its minimal render nodes from `SessionStore.latest_snapshot` whenever `snapshot_updated` fires.
   - This pack prefers simple correctness over incremental scene diffing.

2. **The world uses minimal primitive meshes with deterministic roots.**
   - Units render as box markers.
   - Public boundaries render as narrow upright markers.
   - Process lines render as thin box segments derived from stored `path_xy` points.
   - Render nodes live under deterministic child roots such as units, lines, and boundaries so the smoke can inspect them directly.

3. **Board coordinates map directly into the fixed-camera world plane.**
   - Board-layout `x` maps to world `x`.
   - Board-layout `y` maps to world `z`.
   - Small fixed heights keep units, boundaries, and lines visually separated without changing gameplay semantics.

4. **Boundary placement remains fixed client-side for the current slice ids.**
   - Use the same boundary framing constants as the operability pack for current public ids.
   - The renderer reads boundary presence from authoritative topology state, but uses fixed local anchors for this narrow slice.

5. **Smoke proves readability through counts and ids, not screenshots.**
   - The smoke asserts that `WorldRenderer` exists and exposes rendered ids/counts matching the authoritative snapshot.
   - Sandbox mode proves unit and line nodes appear after build actions.
   - Restart proves rendered units/lines clear back to the restarted authoritative state.
   - Tutorial mode proves boundary/world rendering is still wired even without widening tutorial interactions.

## Risks / Trade-offs

- Rebuilding nodes on each snapshot is not the most efficient approach, but it is simple and safe for the current slice scale.
- Primitive markers will remain visually plain; that is intentional so readability is improved without creating a second design project.

## Verification Strategy

- Required verification for implementation:
  - `godot4 --headless --path clients/godot_phase1_vertical_slice --script res://tests/smoke_test.gd`
  - `MODSIM_GODOT_SMOKE_MODE=heater_flash_guided_build_v1 godot4 --headless --path clients/godot_phase1_vertical_slice --script res://tests/smoke_test.gd`
  - `uv run pytest tests/integration/test_game_vertical_slice_smoke.py`
- Expected evidence:
  - `WorldRenderer` mounts in `MainGame` and renders boundary markers from authoritative topology state.
  - Sandbox builds cause rendered unit and line ids/counts to match the authoritative snapshot.
  - Restart returns rendered unit/line ids/counts to the restarted snapshot state.
  - Tutorial mode still renders its authoritative world state and clears correctly on teardown.

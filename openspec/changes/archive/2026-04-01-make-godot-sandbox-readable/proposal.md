## Why

The Godot slice is now operable, but it is still hard to read at a glance because the world view does not render the authoritative board state.

- `clients/godot_phase1_vertical_slice/scripts/world_renderer.gd` still does nothing on `snapshot_updated`.
- `GameSnapshot.board_layout` already exposes `unit_entities_by_process_id[*].anchor_xy` and `line_entities_by_line_id[*].path_xy`, so the missing piece is client-side consumption rather than new backend capability.
- The HUD and build panel are functional, but the fixed-camera world remains visually empty enough that the gas-first slice still feels like a panel-driven debug surface instead of a readable board.

Without this pack, the player can operate the sandbox, but cannot quickly understand what has been placed or wired from the main view.

## What Changes

- Render authoritative unit placements from `board_layout.unit_entities_by_process_id` using minimal Godot primitives.
- Render authoritative process lines from `board_layout.line_entities_by_line_id` using minimal orthogonal segment primitives.
- Render current public boundary markers from the authoritative topology snapshot using fixed client-side boundary anchors that already frame the slice.
- Keep the renderer snapshot-driven so polling, build commands, and restart all refresh the same world state.
- Extend the Godot smoke harness so it proves world-render nodes appear, refresh after builds, and clear back to restart state.

## Capabilities

### Modified Capabilities
- `client-godot`

## Impact

- Affected code:
  - `clients/godot_phase1_vertical_slice/scripts/world_renderer.gd`
  - `clients/godot_phase1_vertical_slice/tests/smoke_test.gd`
  - `clients/godot_phase1_vertical_slice/scenes/MainGame.tscn` only if small scene support nodes become necessary
- Affected docs:
  - `docs/godot_vertical_slice.md`
- Affected OpenSpec sync surfaces after implementation:
  - `openspec/changes/make-godot-sandbox-readable/specs/client-godot/spec.md`
  - `openspec/specs/client-godot/spec.md`

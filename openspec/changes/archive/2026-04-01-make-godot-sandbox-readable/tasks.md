## Dependency gate

- [x] D0 Do not start implementation until this change pack is approved and the implementation packet is created in Beads from these tasks.
  - Beads execution packet created as `ModularSimulator-ej7.8` before implementation.

## Wave 1 — Lock the readability target with verification first

- [x] 1.1 Extend `clients/godot_phase1_vertical_slice/tests/smoke_test.gd` so it asserts `WorldRenderer` exists, renders authoritative boundary markers after session start, and can report rendered ids/counts for units, lines, and boundaries.
- [x] 1.2 Extend sandbox smoke so build actions prove rendered unit and line nodes appear and stay synchronized with `latest_snapshot.board_layout`.
- [x] 1.3 Extend restart assertions so rendered unit/line ids clear back to the restarted authoritative snapshot state.
- [x] 1.4 Keep tutorial smoke in scope by asserting world rendering remains wired for `heater_flash_guided_build_v1` without widening tutorial interaction scope.

## Wave 2 — Implement snapshot-driven readable world rendering

- [x] 2.1 Replace the `pass` implementation in `clients/godot_phase1_vertical_slice/scripts/world_renderer.gd` with minimal authoritative rendering.
  - Render units from `board_layout.unit_entities_by_process_id`.
  - Render lines from `board_layout.line_entities_by_line_id`.
  - Render current boundaries from authoritative topology nodes using fixed slice-local boundary anchors.
- [x] 2.2 Keep world rendering deterministic and inspection-friendly.
  - Maintain separate child roots for rendered units, lines, and boundaries.
  - Expose small helper methods the smoke can use to inspect rendered ids/counts.
- [x] 2.3 Keep scope narrow.
  - No in-world editing.
  - No animation or throughput overlays.
  - No new backend routes.

## Wave 3 — Sync docs/specs and verify

- [x] 3.1 Update `docs/godot_vertical_slice.md` to describe the current readable world behavior and keep richer visual polish deferred.
- [x] 3.2 Sync the new readability requirement into `openspec/specs/client-godot/spec.md`.
- [x] 3.3 Run verification:
  - `godot4 --headless --path clients/godot_phase1_vertical_slice --script res://tests/smoke_test.gd`
  - `MODSIM_GODOT_SMOKE_MODE=heater_flash_guided_build_v1 godot4 --headless --path clients/godot_phase1_vertical_slice --script res://tests/smoke_test.gd`
  - `uv run pytest tests/integration/test_game_vertical_slice_smoke.py`

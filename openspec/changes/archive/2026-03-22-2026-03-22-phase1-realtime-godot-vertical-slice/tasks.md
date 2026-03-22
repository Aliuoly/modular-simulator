## Dependency gate

- [x] D0 Treat `openspec/specs/phase1-sandbox-build-catalog/spec.md` and `openspec/specs/sandbox-session-and-heuristic-economics/spec.md` as read-only prerequisites for this pack; do not redefine start ids, tutorial ids, catalog items, or simulation/economics ownership boundaries here.

## Wave 1 — Freeze runtime/service/client contracts with red tests first

- [x] 1.1 Extend `tests/gameplay/test_sandbox_session.py` with red tests proving the new public instance-backed session runtime preserves the existing module-level API behavior and still exposes the frozen simulation contract from `openspec/specs/sandbox-session-and-heuristic-economics/spec.md`.
- [x] 1.2 Extend `tests/gameplay/test_economics_ledger.py` with red tests proving the new public instance-backed ledger runtime preserves the existing module-level API behavior and still exposes the frozen economics contract and handoff semantics.
- [x] 1.3 Add `tests/gameplay/test_realtime_game_service.py` with red tests covering these exact slice boundaries before implementation:
  - the service can create exactly `phase1_process_sandbox_v1` and `heater_flash_guided_build_v1` sessions for this slice,
  - `simulation_dt_s` accepts the advertised presets `1/60`, `1/30`, and `1/20`, defaults to `1/60` when omitted, and rejects unsupported values with `error_code="unsupported_simulation_dt_s"`,
  - the service enforces exactly one active local session at a time and rejects concurrent creation with `error_code="session_already_active"`,
  - sessions are always-running once created,
  - there is no pause/resume operation,
  - restart keeps the same `session_id` while resetting slice state,
  - the combined snapshot includes session metadata, `mode_id`, `SimulationSessionSnapshot`, `CashLedgerSnapshot`, latest published signals, topology payload, board-layout payload, and `lag_backlog_s`,
  - player-intent build/feed/sell commands orchestrate receipts internally and never require client-supplied receipt ids,
  - restart resets the active slice state without promising cross-process resume.
- [x] 1.4 Add `tests/gameplay/test_board_layout.py` with red tests covering the exact service-owned render metadata required for the supported slice commands:
  - heater and flash placements store fixed board positions,
  - process-line placements store source/target anchors plus renderable path metadata,
  - board-layout state stays separate from raw `PlantBackendSession` topology payload.
- [x] 1.5 Add `tests/app/test_game_api.py` with red tests covering these exact route and rejection boundaries before implementation:
  - `GET /game/bootstrap`
  - `POST /game/sessions`
  - `GET /game/sessions/{session_id}/snapshot`
  - `POST /game/sessions/{session_id}/commands/build`
  - `POST /game/sessions/{session_id}/commands/buy-feed`
  - `POST /game/sessions/{session_id}/commands/sell-product`
  - `POST /game/sessions/{session_id}/restart`
  - `GET /game/bootstrap` returns the supported mode ids, supported build item ids, advertised `simulation_dt_s` presets, `default_simulation_dt_s = 1/60`, and `pause_supported = false`,
  - `POST /game/sessions` accepts `mode_id` plus optional `simulation_dt_s`, returns HTTP `201` plus `{session_id, snapshot}` on success, and rejects unsupported `mode_id`, unsupported `simulation_dt_s`, and second-session creation while one local session is active,
  - `GET /game/sessions/{session_id}/snapshot` returns HTTP `200` plus `GameSnapshot` on success,
  - build-command requests enforce the frozen item/config/layout contract from `design.md` and return HTTP `200` plus exact success payload `{accepted: true, message, snapshot}`,
  - buy-feed, sell-product, and restart return HTTP `200` plus exact success payload `{accepted: true, message, snapshot}`,
  - rejected requests assert the frozen HTTP status semantics from `design.md` alongside JSON `{error_code, message}` bodies,
  - snapshot and restart reject unknown session ids with HTTP `404` and `error_code="unknown_session"`,
  - explicit rejection/evidence that no `pause` or `resume` route exists.
- [x] 1.6 Add `tests/integration/test_game_vertical_slice_smoke.py` with red integration coverage for these fixed end-to-end flows before implementation:
  - sandbox flow: create a sandbox session, buy feed, place heater + flash + process lines, let the always-running loop advance, then sell product,
  - tutorial flow: create `heater_flash_guided_build_v1`, place the required items/lines through the service, and verify goal completion plus elapsed-time reporting through the combined snapshot,
  - restart flow: verify restart returns the slice to its initial state without surfacing a pause or resume affordance.
- [x] 1.7 Add a red Godot smoke harness at `clients/godot_phase1_vertical_slice/tests/smoke_test.gd` asserting that, once the client project exists, the headless smoke proves all of the following before implementation is considered complete:
  - bootstrap/title flow exists,
  - the fixed camera exists,
  - no pause UI node/action exists,
  - `backend_client.gd` can create a sandbox or heater/flash tutorial session through the HTTP API,
  - `session_store.gd` can consume a backend snapshot,
  - HUD nodes can reflect authoritative snapshot-backed state.
- [x] 1.8 Verify the red boundary with:
  - `uv run pytest tests/gameplay/test_sandbox_session.py tests/gameplay/test_economics_ledger.py tests/gameplay/test_realtime_game_service.py tests/gameplay/test_board_layout.py tests/app/test_game_api.py tests/integration/test_game_vertical_slice_smoke.py`
  - Expected evidence: service/API/client-smoke tests fail before the new runtime/service/client implementation exists.

## Wave 2 — Refactor backend runtimes for service ownership

- [x] 2.1 Extend `src/modular_simulation/gameplay/sandbox_session.py` with a public instance-backed runtime class used by the service, while preserving the existing module-level `start_sandbox`, `start_tutorial`, `install_catalog_item`, `load_feed_inventory`, `advance`, `withdraw_product_inventory`, and `get_simulation_state` entrypoints.
- [x] 2.2 Extend `src/modular_simulation/gameplay/economics.py` with a public instance-backed ledger runtime class used by the service, while preserving the existing module-level `open_cash_ledger`, quote/record methods, and handoff semantics.
- [x] 2.3 Add `src/modular_simulation/gameplay/board_layout.py` for service-owned board entity placement/path records that do not leak into `PlantBackendSession`.
- [x] 2.4 Add `src/modular_simulation/gameplay/start_runtime.py` to compose the supported slice starts into active backend/runtime state without redefining the frozen start catalog.
- [x] 2.5 Keep `src/modular_simulation/cli/backend_session.py` substrate-only: it may be consumed by the new service, but this pack must not move gameplay policy, tutorial timing, or economics logic into it.

## Wave 3 — Implement the realtime game service and HTTP bridge

- [x] 3.1 Add `src/modular_simulation/gameplay/service_contracts.py` with the frozen transport DTOs for bootstrap, combined snapshots, board entities, and command responses used by both the service and the API layer.
- [x] 3.2 Add `src/modular_simulation/gameplay/realtime_service.py` with the authoritative per-session loop manager for:
  - wall-clock accumulation,
  - fixed-step `simulation_dt_s` advancement,
  - no-pause lifecycle,
  - single-active-session enforcement,
  - lag diagnostics,
  - player-intent command orchestration across economics + simulation + substrate + board layout.
- [x] 3.3 Add `src/modular_simulation/app/game_api.py` exposing the exact route surface frozen in `design.md`; use request/response JSON contracts and do not expose receipt ids to the client.
- [x] 3.4 Update `pyproject.toml` to declare any new API runtime dependencies explicitly (for example `fastapi` / `uvicorn`) instead of relying on NiceGUI’s transitive install footprint.
- [x] 3.5 Do not repurpose `src/modular_simulation/app/main.py` into the authoritative game transport seam; keep the Godot-facing API isolated in `game_api.py`.

## Wave 4 — Build the Godot client vertical slice

- [x] 4.1 Create the Godot project scaffold under `clients/godot_phase1_vertical_slice/` with these exact initial files:
  - `project.godot`
  - `scenes/Bootstrap.tscn`
  - `scenes/TitleScreen.tscn`
  - `scenes/MainGame.tscn`
  - `scripts/backend_client.gd`
  - `scripts/session_store.gd`
  - `scripts/world_renderer.gd`
  - `scripts/hud_controller.gd`
  - `scripts/build_command_panel.gd`
  - `tests/smoke_test.gd`
- [x] 4.2 Implement the title/start flow so the player can launch exactly the sandbox or heater/flash tutorial slice modes from the client.
- [x] 4.3 Implement the fixed-camera 2.5D main scene so the player can see placed heaters, flash drums, and process lines on a non-rotatable board.
- [x] 4.4 Implement backend polling and authoritative state updates through `backend_client.gd` / `session_store.gd`, with 60 FPS rendering decoupled from backend snapshot polling.
- [x] 4.5 Implement HUD and command-panel support for the slice-visible state only:
  - cash balance
  - feed inventory
  - product inventory
  - published signals
  - heater/flash tutorial goals when the tutorial mode is active
  - build/feed/sell/restart commands
- [x] 4.6 Explicitly omit pause UI, pause hotkeys, and free camera rotation from the client.

## Wave 5 — Verify the playable slice and sync docs

- [x] 5.1 Make the new targeted Python matrix pass:
  - `uv run pytest tests/gameplay/test_sandbox_session.py`
  - `uv run pytest tests/gameplay/test_economics_ledger.py`
  - `uv run pytest tests/gameplay/test_realtime_game_service.py`
  - `uv run pytest tests/gameplay/test_board_layout.py`
  - `uv run pytest tests/app/test_game_api.py`
  - `uv run pytest tests/integration/test_game_vertical_slice_smoke.py`
- [x] 5.2 Make the Godot headless smoke pass on a machine with Godot 4 available on `PATH`:
  - `godot4 --headless --path clients/godot_phase1_vertical_slice --script res://tests/smoke_test.gd`
  - Expected evidence: bootstrap loads, title flow exists, fixed camera exists, no pause UI/action is registered, a session can be created through `backend_client.gd`, a backend snapshot is consumed into `session_store.gd`, and HUD state updates from authoritative backend data.
- [x] 5.3 Update `docs/game_backend_overview.md` so the repo framing names the new service/client layer as a consumer of the educational backend rather than a replacement for it.
- [x] 5.4 Update `docs/plant_backend_session_user_guide.md` to point game-client implementers at the higher-level realtime service while keeping `PlantBackendSession` documented as substrate.
- [x] 5.5 Add `docs/godot_vertical_slice.md` with a concrete local runbook covering backend startup, Godot startup, supported slice scope, the no-pause rule, and the current persistence limitation.
- [x] 5.6 Re-run `uv run pytest tests/test_game_backend_positioning.py` after the doc updates so repo identity and ownership boundaries remain aligned.
- [x] 5.7 When implementation begins, track execution in Beads from the project root with `bd --json`; keep OpenSpec as the only durable planning artifact and do not create a second markdown plan outside the change pack.

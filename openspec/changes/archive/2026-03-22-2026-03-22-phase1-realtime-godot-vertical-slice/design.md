## Context

- `src/modular_simulation/gameplay/sandbox_session.py` currently exposes a step-driven module API, but its runtime state is scope-keyed and only returns simulation/inventory state; it does not expose a renderable topology or board layout.
- `src/modular_simulation/gameplay/economics.py` already owns quotes, receipts, and sale handoffs, but it is also module-scoped and not shaped as a long-running per-session service object.
- `src/modular_simulation/cli/backend_session.py` already exposes the substrate topology/runtime façade, including `get_topology()`, `save_checkpoint()`, and `load_checkpoint()`, but it is still a direct Python object boundary rather than a client transport seam.
- `src/modular_simulation/gameplay/contracts.py` and `PlantBackendSession.get_topology()` are already close to JSON-friendly, which makes an HTTP polling bridge practical for a first slice.
- `src/modular_simulation/gameplay/start_catalog.py`, `sandbox_catalog.py`, `tutorial_catalog.py`, and `starts/builders.py` already freeze the phase-1 starts and item metadata that the game layer should consume rather than redefining.
- `src/modular_simulation/app/main.py` is only a small NiceGUI stub and is not a current gameplay transport layer.
- The user wants an always-running realtime-like loop, Godot, a fixed non-rotatable camera, 60 FPS rendering, and no pause feature. They are willing to defer deeper performance work until after small systems are playable.

## Goals / Non-Goals

**Goals**
- Deliver an implementation-ready plan for a first playable local Godot slice above the existing backend/gameplay primitives.
- Keep the backend authoritative while hiding receipt choreography from the client.
- Support continuous no-pause sessions with decoupled render and simulation rates.
- Make plant topology, gameplay state, and board-layout state available in one client-consumable snapshot.
- Keep the first slice narrow enough to ship: sandbox + heater/flash tutorial, heater/flash build loop, feed purchase, product sale, HUD, and fixed-camera world rendering.

**Non-Goals**
- Multiplayer, matchmaking, remote authoritative hosting, or account systems.
- Cross-process save/resume for gameplay sessions in this slice.
- Websocket streaming, rollback networking, or per-frame transport synchronization.
- Client support for the full phase-1 catalog on day one; reactor-control and recycle/purge client flows stay deferred.
- Final art production matching Satisfactory-quality assets; the first slice may use clean placeholder/greybox assets while preserving the intended fixed-camera 2.5D presentation.
- Moving gameplay policy into `PlantBackendSession`.

## Decisions

1. **The first playable slice is local, single-player, and deliberately narrow.**
   - Supported session entry points for the slice:
     - `phase1_process_sandbox_v1`
     - `heater_flash_guided_build_v1`
   - Supported build/apply items surfaced to the Godot client in this pack:
     - `place_heater_cooler`
     - `place_flash_drum`
     - `build_process_line`
   - Supported economy actions surfaced to the client in this pack:
     - buy feed for materials exposed by the active start
     - sell product inventory exposed by the active start
   - Reactor-control and recycle/purge remain backend capabilities but are out of scope for the first playable client.

2. **A thin game-service layer owns player-intent orchestration.**
   - Add new service-oriented modules under `src/modular_simulation/gameplay/`:
     - `service_contracts.py` — JSON/transport DTOs for bootstrap, snapshot, and command responses
     - `board_layout.py` — service-owned layout state for rendered entity positions and line paths
     - `start_runtime.py` — start-specific runtime composition helpers for supported slice starts
     - `realtime_service.py` — authoritative per-session realtime loop and command orchestration
   - The service composes:
     - a sandbox session runtime,
     - an economics ledger runtime,
     - a `PlantBackendSession` for topology/runtime edits,
     - and a board-layout store for client rendering.
   - The Godot client sends player intents such as “place item”, “buy feed”, and “sell product”; it does **not** send receipt ids or directly choreograph economics handoffs.

3. **`sandbox_session.py` and `economics.py` must gain public instance-backed runtimes while preserving today’s module-level APIs.**
   - `sandbox_session.py` should expose a public runtime class (for example `SandboxSessionRuntime`) that carries session state explicitly.
   - `economics.py` should expose a public runtime class (for example `CashLedgerRuntime`) that carries ledger state explicitly.
   - Existing module-level functions (`start_sandbox()`, `advance()`, `record_feed_purchase()`, etc.) remain as compatibility façades for current tests and examples.
   - The service layer must instantiate its own runtime objects rather than depending on the current module-global scope keys.

4. **The game-service transport is HTTP request/response with polling for the first slice.**
   - Add a new API entrypoint: `src/modular_simulation/app/game_api.py`.
   - The first slice uses ordinary JSON over HTTP rather than websockets.
   - Exact route surface:
     - `GET /game/bootstrap`
     - `POST /game/sessions`
     - `GET /game/sessions/{session_id}/snapshot`
     - `POST /game/sessions/{session_id}/commands/build`
     - `POST /game/sessions/{session_id}/commands/buy-feed`
     - `POST /game/sessions/{session_id}/commands/sell-product`
     - `POST /game/sessions/{session_id}/restart`
   - There is intentionally **no** `pause`, `resume`, or `step-on-demand` route.
   - Frozen request/response surface for implementation:
     - `GET /game/bootstrap -> GameBootstrapResponse`
       - fields:
         - `supported_mode_ids: tuple[str, ...] = ("phase1_process_sandbox_v1", "heater_flash_guided_build_v1")`
         - `supported_build_item_ids_by_mode_id: Mapping[str, tuple[str, ...]]`
         - `supported_simulation_dt_s_presets: tuple[float, ...] = (1/60, 1/30, 1/20)`
         - `default_simulation_dt_s: float = 1/60`
         - `pause_supported: bool = False`
     - `POST /game/sessions` request:
       - `mode_id: Literal["phase1_process_sandbox_v1", "heater_flash_guided_build_v1"]`
       - `simulation_dt_s: float | None`
       - omission of `simulation_dt_s` means the service uses `default_simulation_dt_s = 1/60`
       - unsupported values reject with `error_code="unsupported_simulation_dt_s"`
       - if an active local session already exists, reject with `error_code="session_already_active"`
     - `POST /game/sessions` response:
       - HTTP `201 Created`
       - `session_id: str`
       - `snapshot: GameSnapshot`
      - `GET /game/sessions/{session_id}/snapshot -> GameSnapshot`
       - HTTP `200 OK`
       - unknown ids reject with `error_code="unknown_session"`
      - `POST /game/sessions/{session_id}/commands/build` request:
       - `item_id: Literal["place_heater_cooler", "place_flash_drum", "build_process_line"]`
       - `config: Mapping[str, object]`
       - `layout: Mapping[str, object]`
       - config requirements by item:
         - `place_heater_cooler`: requires `process_id: str`
         - `place_flash_drum`: requires `process_id: str`
         - `build_process_line`: requires `source: str`, `target: str`; `length_m` and `radius_m` may be omitted to use the frozen catalog defaults
        - layout requirements by item:
          - unit items require `anchor_xy: tuple[float, float]`
          - `build_process_line` requires `path_xy: tuple[tuple[float, float], ...]` with at least two points
        - rejections use `error_code in {"unknown_session", "unknown_item", "unsupported_item_for_mode", "invalid_config", "invalid_layout"}`
       - success response:
         - HTTP `200 OK`
         - `accepted: bool = True`
         - `message: str`
         - `snapshot: GameSnapshot`
      - `POST /game/sessions/{session_id}/commands/buy-feed` request:
        - `material_id: str`
        - `quantity_mol: float`
        - rejections use `error_code in {"unknown_session", "unknown_material", "invalid_quantity", "insufficient_cash"}`
       - success response:
         - HTTP `200 OK`
         - `accepted: bool = True`
         - `message: str`
         - `snapshot: GameSnapshot`
      - `POST /game/sessions/{session_id}/commands/sell-product` request:
        - `product_id: str`
        - `quantity_mol: float`
        - rejections use `error_code in {"unknown_session", "unknown_product", "invalid_quantity", "insufficient_product_inventory"}`
       - success response:
         - HTTP `200 OK`
         - `accepted: bool = True`
         - `message: str`
         - `snapshot: GameSnapshot`
      - `POST /game/sessions/{session_id}/restart` response:
       - HTTP `200 OK`
       - success body:
         - `accepted: bool = True`
         - `message: str`
         - `snapshot: GameSnapshot`
        - resets the session to the initial state for its existing `mode_id`
        - preserves the existing `session_id`
        - unknown ids reject with `error_code="unknown_session"`
      - All rejected API requests return JSON `{error_code: str, message: str}` rather than raw Python exceptions.
      - HTTP status semantics for rejected requests:
        - `400 Bad Request` for `unsupported_simulation_dt_s`, `unknown_item`, `unsupported_item_for_mode`, `invalid_config`, `invalid_layout`, `unknown_material`, `unknown_product`, `invalid_quantity`
        - `404 Not Found` for `unknown_session`
        - `409 Conflict` for `session_already_active` and `insufficient_cash`
        - `409 Conflict` for `insufficient_product_inventory`

5. **The service owns a continuous fixed-step simulation loop with configurable `simulation_dt_s`.**
   - Every active session is always running once created.
   - The service advances simulation from wall-clock time accumulation rather than waiting for explicit client `advance()` calls.
   - `simulation_dt_s` is configurable when the session starts, but it is optional on session creation because omission uses the bootstrap default.
   - The bootstrap payload must advertise the slice presets `1/60`, `1/30`, and `1/20` seconds, with `1/60` as the default slice preset.
   - The Godot client renders independently at 60 FPS and polls snapshots at a lower rate; visual smoothness must not require a 60 Hz backend transport loop.
   - If the backend falls behind, the service records lag in diagnostics/state; it does not solve this by introducing a pause feature.

6. **The first slice is single-player and supports exactly one active local session at a time.**
   - The service may expose `session_id` in routes and snapshots, but only one active session may exist per local backend process in this pack.
   - `POST /game/sessions` rejects creation while another session is active instead of silently replacing it.
   - `POST /game/sessions/{session_id}/restart` resets that one active session in place and keeps its `session_id` stable.
   - No session-expiration or multi-profile behavior is in scope for this pack.

7. **The client consumes one combined snapshot, not scattered backend surfaces.**
   - `GameSnapshot` in `service_contracts.py` should include at minimum:
      - session identity and run state
      - `mode_id`
      - `session_kind`, `active_start_id`, `active_tutorial_id`
      - `elapsed_time_s` and `simulation_dt_s`
      - `lag_backlog_s`
      - the current `SimulationSessionSnapshot`
      - the current `CashLedgerSnapshot`
      - latest `published_signal_values_by_id`
      - `PlantBackendSession.get_topology()` payload
      - board-layout entities/positions/line paths for Godot rendering
      - the client-supported catalog subset for the active slice
    - Successful command responses always return exactly `accepted: bool`, `message: str`, and `snapshot: GameSnapshot` so the client can update from authoritative state after each action.
    - `lag_backlog_s` is the explicit diagnostics field proving whether wall-clock accumulation is outpacing simulation advancement.

8. **Topology and board layout are separate but synchronized concerns.**
   - `PlantBackendSession` remains the authoritative source for graph/topology edits.
   - The new `board_layout.py` owns render placement metadata that does not belong in the substrate.
   - Supported build commands in this slice must update both the substrate topology and the board layout in one service operation.
   - The service must consume the frozen apply kinds and required user inputs from `sandbox_catalog.py`; it must not invent a second gameplay catalog.

9. **The Godot client is a first-class deliverable of this change.**
   - Add a new project at `clients/godot_phase1_vertical_slice/`.
   - Required client structure:
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
   - The presentation contract for the slice:
     - fixed camera with no free rotation
     - 2.5D board/world rendering
     - HUD for cash, feed inventory, product inventory, published signals, and tutorial goals
     - title/start flow for sandbox vs heater/flash tutorial
     - no pause button or pause hotkey

10. **Gameplay persistence stays explicit and narrow.**
   - The slice supports `restart` of the active session.
   - The slice does **not** promise save/resume across process restarts.
   - Existing substrate checkpoint functions (`save_checkpoint()` / `load_checkpoint()`) remain available at lower layers, but this pack does not elevate them into a player-facing save system.

11. **The service/API stack must use explicit dependencies instead of relying on transitive NiceGUI internals.**
    - If `FastAPI` / `uvicorn` are used for `game_api.py`, they must be declared explicitly in `pyproject.toml` rather than depending on NiceGUI’s transitive install footprint.
    - `src/modular_simulation/app/main.py` is not the transport contract for this slice and should not be treated as such.

## Risks / Trade-offs

- **Current gameplay state is not yet session-instance-oriented.**
  - Mitigation: make instance-backed runtimes an explicit prerequisite inside this pack, while preserving existing public functions.
- **Current gameplay snapshots are insufficient for world rendering.**
  - Mitigation: define a combined service snapshot that merges simulation, ledger, topology, and board-layout state.
- **Adding a Godot client without a transport seam could tempt implementers to embed gameplay logic in the client.**
  - Mitigation: keep the backend authoritative and route only player-intent commands through the API.
- **Godot tooling is not currently present in the repo environment.**
  - Mitigation: add the project/runbook and headless smoke task explicitly, and document the local Godot 4 prerequisite rather than pretending it already exists in CI.
- **The no-pause requirement removes a convenient debugging escape hatch.**
  - Mitigation: expose restart and lag diagnostics, but do not add pause/resume as a hidden backdoor.

## Verification Strategy

- TDD should lead the service contracts, runtime refactor, and API surface before Godot implementation.
- Required verification for implementation:
  - `uv run pytest tests/gameplay/test_sandbox_session.py`
  - `uv run pytest tests/gameplay/test_economics_ledger.py`
  - `uv run pytest tests/gameplay/test_realtime_game_service.py`
  - `uv run pytest tests/gameplay/test_board_layout.py`
  - `uv run pytest tests/app/test_game_api.py`
  - `uv run pytest tests/integration/test_game_vertical_slice_smoke.py`
  - `uv run pytest tests/test_game_backend_positioning.py`
  - `godot4 --headless --path clients/godot_phase1_vertical_slice --script res://tests/smoke_test.gd`
- Expected evidence:
  - current gameplay tests still pass after the runtime refactor,
  - the service runs an always-running session with no pause route or pause UI,
  - session creation defaults omitted `simulation_dt_s` to `1/60` and rejects unsupported values,
  - the one-active-session rule is enforced with a stable `session_already_active` rejection,
  - build/feed/sell commands return authoritative combined snapshots without exposing receipt ids to the client,
  - the Godot client boots, creates a sandbox or heater/flash tutorial session through `backend_client.gd`, consumes snapshots into `session_store.gd`, renders a fixed-camera board, and updates HUD state from backend snapshots,
  - restart works, while cross-process save/resume is still documented as deferred.

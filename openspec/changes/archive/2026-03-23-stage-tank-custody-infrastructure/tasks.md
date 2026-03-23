## Dependency gate

- [x] D0 Do not start implementation until this change pack is approved and the implementation packet is created in Beads from these tasks.

## Wave 1 — Write red tests for the internal staging seams and unchanged live surfaces

- [x] 1.1 Add `tests/gameplay/test_tank_custody.py` with red tests for the new internal helper/module before implementation:
  - tank custody state is keyed by tank `process_id`, not by a hard-coded feed/product role,
  - mixed incoming custody updates are aggregated into one stored tank inventory state using repo-consistent thermodynamic fields (for example total amount, temperature, pressure, species ids/composition, and repo-defined optional phase/enthalpy/entropy or equivalent fields) instead of parallel per-source buckets,
  - one named boundary id maps to at most one active tank id at a time for bought/sold boundary routes,
  - reassigning a boundary route still leaves only one active mapping for that boundary,
  - purge-by-tank clears the aggregate stored custody state for one tank id without deleting the tank record or requiring a public command surface.
- [x] 1.2 Extend `tests/gameplay/test_realtime_game_service.py` with a red guard for the item-aware placement seam:
  - a module-private helper in `src/modular_simulation/gameplay/realtime_service.py`, invoked by `_install_unit()`, can resolve `place_holding_tank` from its catalog metadata and derive real ports `("inlet",)` / `("outlet",)` instead of forcing generic `("in",)` / `("out",)`,
  - that same helper preserves `constructor_payload` exactly from the catalog record when present, using `place_quality_control_lab` as the non-public metadata proof case,
  - that helper derives whatever ports the unit declares and does not freeze a broader single-inlet/single-outlet rule beyond the current HoldingTank proof case,
  - `SUPPORTED_BUILD_ITEM_IDS` remains exactly `("place_heater_cooler", "place_flash_drum", "build_process_line")`,
  - the public realtime-service method set remains unchanged.
- [x] 1.3 Extend `tests/app/test_game_api.py` with red guards proving the live HTTP slice stays frozen:
  - bootstrap still advertises the current build-item lists for each mode,
  - current buy-feed and sell-product success paths still work with the existing payload shapes,
  - no `/commands/purge-tank` route exists in this pack.
- [x] 1.4 Re-run or tighten unchanged-surface guards in these existing files without broadening their frozen contracts:
  - `tests/gameplay/test_sandbox_session.py`
  - `tests/gameplay/test_sandbox_contracts.py`
  - `tests/gameplay/test_sandbox_catalog.py`
  - `tests/gameplay/test_start_catalog.py`
  - Required proof: `place_holding_tank` remains `unsupported_on_start` on all current starts, session/economics contract fields stay exact, no current start allowlist changes, and no public session method/snapshot widening occurs while the internal tank-custody helper is added.
- [x] 1.5 Run the red boundary:
  - `uv run pytest tests/gameplay/test_tank_custody.py`
  - `uv run pytest tests/gameplay/test_realtime_game_service.py`
  - `uv run pytest tests/app/test_game_api.py`
  - `uv run pytest tests/gameplay/test_sandbox_session.py`
  - `uv run pytest tests/gameplay/test_sandbox_contracts.py`
  - `uv run pytest tests/gameplay/test_sandbox_catalog.py tests/gameplay/test_start_catalog.py`
  - Expected evidence: the new internal helper and item-aware placement tests fail before implementation exists, while unchanged-surface guards continue to describe the frozen live slice.

## Wave 2 — Implement the infrastructure-only seams without widening the live slice

- [x] 2.1 Create `src/modular_simulation/gameplay/tank_custody.py` with the internal primitives frozen in `design.md`:
  - per-tank custody state keyed by `process_id`,
  - aggregate mixed-inventory representation per tank using repo-consistent thermodynamic fields suitable for later outlet-pressure and volume calculation,
  - one-active-route-per-boundary assignment keyed by boundary id for external bought/sold routes only,
  - internal purge-by-tank support.
- [x] 2.2 Update `src/modular_simulation/gameplay/realtime_service.py` so the `add_process` application path can respect cataloged unit metadata for unit-blueprint items instead of forcing generic `in/out` ports.
  - Implement the seam as a module-private helper inside `src/modular_simulation/gameplay/realtime_service.py` that `_install_unit()` calls before `network.add_process(...)`.
  - Required proof case: `place_holding_tank` stages with ports `("inlet",)` / `("outlet",)`.
  - The proof path must stay non-public: tests should exercise that module-private helper directly rather than widening supported build items or current starts.
  - Respect `constructor_payload` when present so runtime-authoritative metadata remains aligned with the catalog record, even though the `HoldingTank` proof case uses `{}` today.
  - Keep the public `build(...)` / `buy_feed(...)` / `sell_product(...)` signatures unchanged.
- [x] 2.3 Update `src/modular_simulation/gameplay/sandbox_session.py` only as needed to host or consume the staged internal tank-custody primitives.
  - Do **not** add a new public simulation-session method.
  - Do **not** add new snapshot fields.
- [x] 2.4 Prefer existing generic substrate seams over new backend-session policy.
  - Reuse `PlantBackendSession.begin_tx()` / `TxHandle.add_process(...)` if possible.
  - If implementation truly needs changes under `src/modular_simulation/cli/backend_session.py`, keep them generic and add/adjust `tests/cli/test_backend_session.py` in the same wave.
- [x] 2.5 Do **not** modify these live-surface files unless a verified blocker proves this changepack is incomplete and the pack is updated first:
  - `src/modular_simulation/app/game_api.py`
  - `src/modular_simulation/gameplay/contracts.py`
  - `src/modular_simulation/gameplay/service_contracts.py`
  - `src/modular_simulation/gameplay/economics.py`
  - `src/modular_simulation/gameplay/start_runtime.py`
  - `src/modular_simulation/gameplay/starts/builders.py`

## Wave 3 — Prove the staged seams work and the current live slice still does not change

- [x] 3.1 Make `tests/gameplay/test_tank_custody.py` pass with the exact internal route/purge semantics frozen in `design.md`.
- [x] 3.2 Make the new realtime-service placement guard pass while keeping the current public slice frozen:
  - `SUPPORTED_BUILD_ITEM_IDS` still exact,
  - `place_holding_tank` still unavailable on all current starts,
  - the helper remains general to declared unit ports rather than hard-coding a broader single-inlet/single-outlet assumption,
  - no public tank or purge command appears.
- [x] 3.3 Re-run the unchanged public-contract guards until they pass without widening session, economics, or client behavior:
  - `uv run pytest tests/gameplay/test_sandbox_session.py`
  - `uv run pytest tests/gameplay/test_sandbox_contracts.py`
  - `uv run pytest tests/gameplay/test_sandbox_catalog.py tests/gameplay/test_start_catalog.py`
  - `uv run pytest tests/gameplay/test_realtime_game_service.py`
  - `uv run pytest tests/app/test_game_api.py`
- [x] 3.4 If `src/modular_simulation/cli/backend_session.py` changed, run:
  - `uv run pytest tests/cli/test_backend_session.py`
  - Expected evidence: backend-session helpers remain generic and policy-free.

## Wave 4 — Sync only the live capability text that actually changed

- [x] 4.1 Sync the implemented catalog/runtime-seam delta into `openspec/specs/units-and-components/spec.md`:
  - add the requirement that `unit_blueprint` catalog records with `apply_kind = "add_process"` remain runtime-authoritative for unit metadata,
  - freeze the `HoldingTank` proof case using real `("inlet",)` / `("outlet",)` ports,
  - keep all current start allowlists unchanged.
- [x] 4.2 Do **not** edit the public session API contract text in `openspec/specs/session/spec.md`, and do **not** edit `openspec/specs/economics/spec.md` or `openspec/specs/client-godot/spec.md`, unless implementation evidence proves a live public contract actually changed. If that happens, stop and revise this changepack boundary before continuing.
- [x] 4.3 Sync the implemented internal tank-custody contract into `openspec/specs/session/spec.md` without widening the public API contract text:
  - add the internal session-owned custody primitive requirement keyed by tank `process_id` and boundary id,
  - freeze aggregate mixed-inventory semantics using repo-consistent thermodynamic state suitable for later outlet-pressure and volume calculation,
  - freeze internal purge-by-tank clearing semantics,
  - freeze that the HoldingTank staging proof uses the module-private realtime-service helper called by `_install_unit()` and does not change supported build items, start allowlists, or public session methods.
- [x] 4.4 Do **not** edit `openspec/specs/economics/spec.md` or `openspec/specs/client-godot/spec.md` unless implementation evidence proves a live public contract actually changed. If that happens, stop and revise this changepack boundary before continuing.
- [x] 4.5 Run final verification:
  - `uv run pytest tests/gameplay/test_tank_custody.py`
  - `uv run pytest tests/gameplay/test_realtime_game_service.py`
  - `uv run pytest tests/gameplay/test_sandbox_session.py`
  - `uv run pytest tests/gameplay/test_sandbox_contracts.py`
  - `uv run pytest tests/gameplay/test_sandbox_catalog.py tests/gameplay/test_start_catalog.py`
  - `uv run pytest tests/app/test_game_api.py`
  - `uv run pytest tests/cli/test_backend_session.py` (only if touched)
- [x] 4.6 Expected final evidence:
  - `HoldingTank` can be staged through the gameplay `add_process` seam using its real ports,
  - that HoldingTank proof uses the module-private realtime-service helper called by `_install_unit()` rather than widening the live build/start surface,
  - tank-custody helper state supports aggregate mixed inventory with repo-consistent thermodynamic state plus one-route-per-boundary bookkeeping for external boundary routes only,
  - `place_holding_tank` remains unsupported on all current starts,
  - `SUPPORTED_BUILD_ITEM_IDS`, bootstrap payloads, session methods, contract fields, and current buy/sell routes remain unchanged,
  - archive only after implementation and verification are complete.

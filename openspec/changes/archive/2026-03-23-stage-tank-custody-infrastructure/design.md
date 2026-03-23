## Context

- `HoldingTank` is now implemented in `src/modular_simulation/unit_processes/storage/holding_tank.py`, but the current gameplay placement path still ignores item-specific unit metadata.
- `src/modular_simulation/gameplay/realtime_service.py` currently installs every placed process with `inlet_ports=("in",)` and `outlet_ports=("out",)`, which is incompatible with `HoldingTank` and any future unit whose real ports differ.
- `src/modular_simulation/gameplay/sandbox_session.py`, `src/modular_simulation/gameplay/contracts.py`, `src/modular_simulation/gameplay/service_contracts.py`, `src/modular_simulation/app/game_api.py`, and the live `session` / `economics` / `client-godot` specs still freeze the current direct-inventory, withdrawal-token, and thin-route playable slice.
- `openspec/specs/units-and-components/spec.md` already includes `place_holding_tank`, but it also freezes `supported_start_ids = ()`, so the holding tank remains unavailable on every current start.
- The user moved the future live gas-starter rewrite out of `4fm` and into `ModularSimulator-ej7`. `4fm` now stages reusable infrastructure only.
- The user also chose that `purge-by-tank` should remain an internal primitive here, not a public player-facing session/API command.

## Goals / Non-Goals

**Goals**
- Stage the minimum internal seams later tank-mediated gameplay can consume without rewriting the current live slice.
- Make gameplay `add_process` placement respect the runtime metadata already frozen in unit-blueprint catalog records.
- Stage generic internal tank-custody state, boundary-route bookkeeping, and purge-by-tank support for later starter migration work.
- Freeze an aggregate mixed-inventory model that is suitable for later outlet-pressure calculations instead of per-source inventory buckets.

**Non-Goals**
- Retarget the live sandbox away from `phase1_process_sandbox_v1`.
- Add real gas-process feed/product naming or sale-spec rules.
- Change current public buy-feed / sell-product routes, payloads, or session method names.
- Change current economics receipts, withdrawal-token handoff, or live price tables.
- Add `place_holding_tank` to any current start allowlist or widen `SUPPORTED_BUILD_ITEM_IDS`.
- Expose purge-by-tank as a public gameplay/session/API command.
- Add player-managed transport or logistics.

## Decisions

1. **`4fm` stages infrastructure only; `ej7` owns the later live rewrite.**
   - `4fm` may add internal helpers and tests that future work can reuse.
   - `4fm` must not rewrite the playable sandbox/client/economics/session contract surface.
   - If implementation pressure requires public `tank_id` buy/sell commands, start allowlist changes, real product naming, or client HUD changes, stop and move that work to `ModularSimulator-ej7` instead of weakening this pack.

2. **Item-aware `add_process` placement becomes the first staged seam.**
   - For `SandboxCatalogItemDefinition` records with `item_kind = "unit_blueprint"` and `apply_kind = "add_process"`, gameplay should stop assuming generic `("in",)` / `("out",)` ports.
   - The gameplay layer should resolve the cataloged unit implementation from the frozen record:
     - `unit_module`
     - `unit_type`
     - `constructor_payload` when present, so staging honors the same runtime metadata the catalog already freezes
   - The placement seam should derive actual process ports from the real unit implementation, with `HoldingTank` as the required proof case:
     - inlet ports `("inlet",)`
     - outlet ports `("outlet",)`
   - The seam must stay general to the unit's declared ports. The current `HoldingTank` proof case happens to be single-inlet/single-outlet, but this pack must not freeze a broader rule that future tanks or other unit blueprints may only have one inlet and one outlet.
   - Prefer a module-private helper in `src/modular_simulation/gameplay/realtime_service.py`, invoked by `_install_unit()`, that instantiates or inspects the cataloged unit implementation and reads its declared ports over adding a second hard-coded port registry.
   - The required proof seam is **that module-private realtime-service helper**. Tests should exercise that helper directly in `tests/gameplay/test_realtime_game_service.py` instead of widening `SUPPORTED_BUILD_ITEM_IDS`, start allowlists, session methods, or HTTP routes just to prove HoldingTank staging.
   - Reuse the existing generic substrate transaction seam (`PlantBackendSession.begin_tx()` / `TxHandle.add_process(...)`) when possible; do not move gameplay policy into `PlantBackendSession`.

3. **The current live build/start surface stays frozen.**
   - `SUPPORTED_BUILD_ITEM_IDS` remains exactly `("place_heater_cooler", "place_flash_drum", "build_process_line")` in this pack.
   - `phase1_process_sandbox_v1` and all tutorial starts keep their current `allowed_item_ids`.
   - `place_holding_tank` and `place_quality_control_lab` remain unsupported on every current start.
   - Bootstrap payloads, session snapshots, and HTTP command shapes remain unchanged.

4. **Internal tank-custody infrastructure is generic, keyed by tank `process_id`, and boundary-routed.**
   - Add a small internal gameplay helper/module to hold staged tank-custody state for future work.
   - Minimum behavior frozen here:
     - tank custody is keyed by tank `process_id`, not by fixed product role,
     - each tank's stored inventory is represented as one aggregate mixed state that preserves enough thermodynamic information for later outlet-pressure and volume calculations, following repo stream/state conventions such as temperature, pressure, species ids and composition plus repo-defined optional phase/enthalpy/entropy or equivalent fields,
     - route assignment is keyed by named boundary id for external bought/sold boundary routes,
     - each boundary id has at most one active assigned tank at a time for those external boundary routes,
     - the helper must not assume real gas naming or purity/sale-spec logic.
   - Mixing is in scope for this staged custody state: adding multiple incoming streams to the same tank must combine them into one stored inventory state suitable for later outlet-pressure and volume calculation, not leave them as parallel tagged sub-inventories.
   - The one-active-route-per-boundary rule applies only to those external boundary-route assignments. It must not be interpreted as a general restriction on how many non-boundary streams may connect to a tank, and it must not freeze tanks as permanently single-inlet/single-outlet in future live topology work.
   - Current boundary ids may still be the placeholder scaffold ids (`feed_a`, `feed_b`, `product_a`, `product_b`) because live starter retarget is deferred.
   - This pack does not yet expose those routes in public snapshots or live commands.
   - Because this behavior is in scope for `4fm`, it must be frozen in the change-local `session` delta spec even though the public session API remains unchanged.

5. **Purge-by-tank is internal only in `4fm`.**
   - The staged purge primitive clears the aggregate stored custody state for one tank `process_id`.
   - Purge does not delete the tank, does not create a demolition/resale mechanic, and does not touch ledger state.
   - Purge does not require a new public session method, realtime-service method, HTTP endpoint, or Godot affordance in this pack.

6. **Session, economics, and client contracts stay unchanged.**
   - `start_sandbox`, `install_catalog_item`, `load_feed_inventory`, `advance`, `withdraw_product_inventory`, and `get_simulation_state` remain the exact simulation API.
   - `record_product_sale(withdrawal_id)` and `SaleReceipt.withdrawal_id` remain the exact economics handoff.
   - `POST /commands/buy-feed` and `POST /commands/sell-product` remain the exact live routes and keep their current payloads without `tank_id`.
   - `GameSnapshot`, `SimulationSessionSnapshot`, `InventoryLoadResult`, `InventoryWithdrawalResult`, and `SimulationAdvanceResult` remain unchanged.

## Risks / Trade-offs

- **This pack can feel abstract because it deliberately stops before visible live gameplay.**
  - Mitigation: keep the acceptance proof concrete around the real `HoldingTank` port mismatch and explicit internal helper tests.
- **Internal routing keyed by current placeholder boundary ids can accidentally harden the old starter vocabulary.**
  - Mitigation: keep those ids internal only and explicitly defer real naming and live ownership to `ModularSimulator-ej7`.
- **Implementation may be tempted to widen the live build/API surface "just enough" to exercise the infrastructure.**
  - Mitigation: treat any start allowlist, route, payload, or HUD widening as out-of-scope and block on spec revision instead.

## Verification Strategy

- TDD should lead both the new internal tank-custody helper and the item-aware placement seam.
- Required verification for implementation:
  - `uv run pytest tests/gameplay/test_tank_custody.py`
  - `uv run pytest tests/gameplay/test_realtime_game_service.py`
  - `uv run pytest tests/gameplay/test_sandbox_session.py`
  - `uv run pytest tests/gameplay/test_sandbox_contracts.py`
  - `uv run pytest tests/gameplay/test_sandbox_catalog.py`
  - `uv run pytest tests/gameplay/test_start_catalog.py`
  - `uv run pytest tests/app/test_game_api.py`
  - `uv run pytest tests/cli/test_backend_session.py` (only if `src/modular_simulation/cli/backend_session.py` is touched)
- Expected evidence:
  - the gameplay placement seam can stage `HoldingTank` using its real `("inlet",)` / `("outlet",)` ports,
  - the placement seam remains general to declared unit ports and does not hard-code a single-inlet/single-outlet assumption beyond the current HoldingTank proof case,
  - that proof uses the module-private realtime-service helper called by `_install_unit()` and does not widen supported build items or start allowlists,
  - internal tank-custody helpers support aggregate mixed-inventory state with repo-consistent thermodynamic fields, one-route-per-boundary assignment for external boundary routes only, and purge-by-tank clearing keyed by `process_id`,
  - no current start gains `place_holding_tank`,
  - no current realtime-service build set expands,
  - no session/economics/client contract fields or public command payloads change in this pack.

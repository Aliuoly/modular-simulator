## Context

- The user originally chose a **sweet-wet-gas first** main world, not a tutorial rewrite, with an abstract research submission action rather than a placeable R&D building; the refreshed pack now groups that ladder into a starter batch plus one batched unlock milestone.
- Current repo reality is still the old generic slice:
  - `phase1_process_sandbox_v1` remains a heater/flash sandbox with `feed_a`, `feed_b`, `product_a`, and `product_b`
  - `SandboxSessionRuntime` has no progression state or research action
  - `RealtimeGameService` still hard-codes `("place_heater_cooler", "place_flash_drum", "build_process_line")`
  - `game_api.py` has no `submit-research` route
  - economics tables still only know generic items/materials/products
  - the Godot scene references controller scripts that are currently missing from the repo tree
- `ej7.1` has already corrected tank ownership and observability boundaries, so `ej7` no longer needs to solve physical tank state ownership first.
- The Beads wording for `ModularSimulator-ej7` is now broader than the implementation-ready slice because it still implies public tank-mediated sell contracts and purity-policy work that are not yet required for the first live gas-world step.

## Goals / Non-Goals

**Goals**
- Replace the generic default sandbox content with a narrow sweet-wet-gas ladder while keeping stable public mode/start ids.
- Add a minimal but explicit progression contract: current stage, unlocked stages, available items, and available research actions.
- Keep the first live gas-world slice playable through the existing service/API/Godot seam with the minimum client changes needed to expose stage progress and research submission.
- Use real gas-processing names while being explicit about proxy-unit educational abstractions.

**Non-Goals**
- Public tank-mediated buy/sell commands, public `tank_id` payloads, or purity-policy/sale-spec workflows.
- Player-managed transport/logistics (`ModularSimulator-9tr.1`).
- Generic placement-command refactor (`ModularSimulator-6ei`) beyond the minimal changes needed to support this pack’s exact item set.
- Sour-gas treatment, acid-gas removal, sulfur recovery, or fractionation beyond the frozen stabilizer stage.
- A placeable research building, second progression tree, or broader factory-management meta-system.

## Decisions

1. **Keep the public sandbox id stable, but replace its content.**
   - `phase1_process_sandbox_v1` remains the default sandbox mode/start id.
   - Its title, seed provenance, feed/product ids, published signals, and allowed items change to the gas-first ladder.
   - Tutorial starts remain separate and unchanged in meaning.

2. **The narrow ej7 slice keeps the already chosen four-stage sweet-wet-gas ladder, but progression unlocks happen in batches.**
   - Initial available stages at sandbox start:
     - `gas_inlet_separation_v1`
       - items: `place_inlet_gas_separator`, `build_process_line`
     - `teg_dehydration_v1`
       - items: `place_teg_contactor`, `place_rich_glycol_flash_tank`, `place_lean_rich_glycol_exchanger`, `place_teg_regenerator`, `install_glycol_circulation_pump`
   - Batched research unlock: `unlock_cold_recovery_train_v1`
     - unlocks both `jt_low_temperature_separation_v1` and `condensate_stabilization_v1`
     - exact recipe `{"separator_gas": 20.0, "unstabilized_condensate": 10.0, "dry_gas": 20.0}`
   - Post-research available stages:
     - `jt_low_temperature_separation_v1`
       - items: `place_gas_gas_exchanger`, `install_jt_valve`, `place_low_temperature_separator`
     - `condensate_stabilization_v1`
       - items: `place_condensate_stabilizer`

3. **Progression is explicit, sandbox-only, and inventory-backed.**
   - Add `ProgressionSnapshot` with exactly:
     - `active_stage_id: str | None`
     - `unlocked_stage_ids: tuple[str, ...]`
     - `available_item_ids: tuple[str, ...]`
     - `available_research_ids: tuple[str, ...]`
    - `SimulationSessionSnapshot` adds `progression_snapshot: ProgressionSnapshot | None`.
    - `submit_research_unlock(research_id, *, submitted_quantities_by_product_id)` lives in the gameplay/session layer, not in `PlantBackendSession`.
    - Research submission follows the existing sandbox-session error style: invalid or unavailable submissions raise `SandboxRequestError`, consume no inventory on rejection, and return `ResearchSubmissionResult` only on success.
    - `active_stage_id` means the highest unlocked stage in the ladder, not the last unit placed or the currently producing path.
    - `available_item_ids` is the cumulative unlocked subset of `phase1_process_sandbox_v1.allowed_item_ids`, preserving ladder order and keeping `build_process_line` at the tail.
    - `available_research_ids` contains at most one id: the next batched unlock milestone for the current sandbox state, or `()` after the final unlock batch.
    - For this pack, the batched unlock milestone is visible from sandbox start so the player can plan toward the mixed-product target without hidden threshold discovery.

   Canonical main-sandbox progression snapshots are frozen exactly as:

   - starter snapshot
     - `active_stage_id = "teg_dehydration_v1"`
     - `unlocked_stage_ids = ("gas_inlet_separation_v1", "teg_dehydration_v1")`
     - `available_item_ids = ("place_inlet_gas_separator", "place_teg_contactor", "place_rich_glycol_flash_tank", "place_lean_rich_glycol_exchanger", "place_teg_regenerator", "install_glycol_circulation_pump", "build_process_line")`
     - `available_research_ids = ("unlock_cold_recovery_train_v1",)`
   - after successful `unlock_cold_recovery_train_v1`
     - `active_stage_id = "condensate_stabilization_v1"`
     - `unlocked_stage_ids = ("gas_inlet_separation_v1", "teg_dehydration_v1", "jt_low_temperature_separation_v1", "condensate_stabilization_v1")`
     - `available_item_ids = ("place_inlet_gas_separator", "place_teg_contactor", "place_rich_glycol_flash_tank", "place_lean_rich_glycol_exchanger", "place_teg_regenerator", "install_glycol_circulation_pump", "place_gas_gas_exchanger", "install_jt_valve", "place_low_temperature_separator", "place_condensate_stabilizer", "build_process_line")`
     - `available_research_ids = ()`

4. **Public commerce stays direct and tank-free in this pack.**
   - `buy-feed` remains `{material_id, quantity_mol}`.
   - `sell-product` remains `{product_id, quantity_mol}`.
   - No public `tank_id`, no purity-spec payloads, and no public tank inventory contract are introduced here.
   - Public tank-mediated sale policy remains deferred follow-on work even though Beads text still references it.

5. **Gas gameplay units use explicit educational proxy mappings.**
   - `place_inlet_gas_separator` → `FlashDrum`
   - `place_teg_contactor` → `ComponentSeparator` proxy
   - `place_rich_glycol_flash_tank` → `FlashDrum`
   - `place_lean_rich_glycol_exchanger` → `HeatExchanger`
   - `place_teg_regenerator` → `StagewiseDistillationColumn` proxy
   - `install_glycol_circulation_pump` → line-owned pump overlay
   - `place_gas_gas_exchanger` → `HeatExchanger`
   - `install_jt_valve` → line-owned valve overlay
   - `place_low_temperature_separator` → `FlashDrum`
   - `place_condensate_stabilizer` → `StagewiseDistillationColumn` proxy
    - The pack must explicitly say these are **educational abstractions** of process intent, not plant-accurate TEG design, molecular sieve drying, turboexpansion, or rigorous cryogenic/NGL fractionation.
    - `install_jt_valve` plus `place_low_temperature_separator` teaches the Joule-Thomson / low-temperature-separation concept only as a named gameplay proxy. This pack does **not** calculate rigorous Joule-Thomson cooling, auto-refrigeration, or cryogenic equilibrium from fluid properties; instead, the low-temperature separator applies an imposed downstream cold condition when the required upstream proxy path exists.

6. **Gas product generation is path-qualified and remains tank-free.**
   - Main-sandbox purchased feed ids are exactly `("sweet_wet_gas",)`.
   - Main-sandbox public product ids are exactly `("separator_gas", "unstabilized_condensate", "dry_gas", "ngl_liquids", "stabilized_condensate")`.
   - Unlock alone never creates product inventory. Product generation requires at least one qualifying connected path from the `sweet_wet_gas` feed boundary to the named product sink through the required proxy units in the intended order.
   - `separator_gas` requires an installed `place_inlet_gas_separator` on a connected path from `sweet_wet_gas` to the `separator_gas` sink.
   - `unstabilized_condensate` requires an installed `place_inlet_gas_separator` on a connected path from `sweet_wet_gas` to the `unstabilized_condensate` sink.
    - `dry_gas` requires:
      - a connected gas path from the inlet separator through `place_teg_contactor` to the `dry_gas` sink, and
      - support-package proxies `place_rich_glycol_flash_tank`, `place_lean_rich_glycol_exchanger`, `place_teg_regenerator`, and `install_glycol_circulation_pump` connected within the same dehydration-package topology / connected component as that qualifying contactor path, not merely installed elsewhere in the sandbox.
   - `ngl_liquids` requires a connected path in this order: inlet-separator gas path → `place_teg_contactor` → `place_gas_gas_exchanger` → a line carrying `install_jt_valve` immediately upstream of `place_low_temperature_separator` → `ngl_liquids` sink.
   - `stabilized_condensate` requires a connected path from the inlet-separator liquid side through `place_condensate_stabilizer` to the `stabilized_condensate` sink; it does not consume public product inventory and does not introduce tank-mediated refeed semantics.
   - Earlier products remain producible after later unlocks if their own qualifying path still exists.
   - Duplicate parallel qualifying paths for the same product id do not stack output credit in this pack.

7. **Research reachability is frozen by batch-ready product mixes and seed-backed examples.**
    - The starter+dehydration batch and the first two gas examples must together make `separator_gas`, `unstabilized_condensate`, and `dry_gas` reachable for `unlock_cold_recovery_train_v1`.
   - `gas_1_inlet_separator.py` proves starter-batch reachability for `separator_gas` and `unstabilized_condensate`.
   - `gas_2_teg_dehydration.py` proves starter-batch reachability for `dry_gas` without needing later-stage items.
   - After `unlock_cold_recovery_train_v1`, `gas_3_jt_low_temperature_separation.py` and `gas_4_condensate_stabilizer.py` prove the newly unlocked cold-recovery/stabilization content remains reachable and playable via `ngl_liquids` and `stabilized_condensate`.
   - Reachability means the player can stay in the core build/run/sell loop long enough to satisfy a mixed-product research recipe before reopening the research surface.

8. **Economics and start scaffolds switch to gas-first ids while tutorials retain legacy coverage.**
   - Main sandbox uses `sweet_wet_gas`, `separator_gas`, `unstabilized_condensate`, `dry_gas`, `ngl_liquids`, `stabilized_condensate`.
   - Legacy tutorial-facing `feed_a`, `feed_b`, `product_a`, `product_b`, and the old generic equipment anchors remain in the price tables so tutorial and existing smoke coverage stay valid.
   - Default starting cash remains `900.0`.
   - Gas-world equipment/feed/product prices are delivered through a default fixed-price policy for this slice, but the pack must preserve an additive seam for future dynamic pricing policies instead of baking fixed-price assumptions into unrelated gameplay/client contracts.
   - In concrete repo terms, `src/modular_simulation/gameplay/economics.py` must stop treating module-level price tables as the domain model and instead route `quote_equipment_purchase(...)`, `quote_feed_purchase(...)`, `quote_product_sale(...)`, and their `CashLedgerRuntime` twins through one internal default pricing-policy seam whose current implementation returns the exact frozen values in this pack.

9. **The service/API/client slice must expose progression explicitly and reject locked items atomically.**
   - `GameBootstrapResponse.supported_build_item_ids_by_mode_id` advertises the initial starter-batch items for `phase1_process_sandbox_v1` and the existing guided-tutorial mode items for `heater_flash_guided_build_v1`.
   - Guided tutorial mode ids remain distinct from start ids, following the current runtime mapping pattern in `start_runtime.py` (`heater_flash_guided_build_v1` → `heater_flash_tutorial_start_v1`).
   - `GameSnapshot.supported_build_item_ids` becomes the current unlocked item list rather than a module-level constant.
   - Add `POST /game/sessions/{session_id}/commands/submit-research` with exact payload `{research_id, submitted_quantities_by_product_id}` and stable 400/404/409 semantics.
   - Build preflight must reject `item_locked` and other invalid requests before mutating topology, board layout, or cash state.

10. **Godot scope is minimum viable, not a new UI framework rewrite.**
    - `MainGame.tscn` remains the authoritative scene file.
    - If `res://scripts/world_renderer.gd`, `hud_controller.gd`, or `build_command_panel.gd` are missing, implementation must restore/create those exact paths rather than change scene references ad hoc.
    - HUD requirements for this pack are limited to current stage, available research, current unlocked build items, plus the existing cash/feed/product/signal display.

11. **Generic placement refactor is explicitly deferred to `6ei`.**
    - `realtime_service.py` may continue to use item-specific branches where needed for this exact item set.
    - `ModularSimulator-6ei` is the real follow-on for turning those branches into a generic placement abstraction once ej7 freezes the live gas-world command surface.

## Risks / Trade-offs

- **The current repo is far from the target pack across every gameplay surface.**
  - Mitigation: keep the pack narrow; explicitly defer tank-mediated sales, transport/logistics, and generic placement refactor.
- **Proxy gas units could be mistaken for full-fidelity process models.**
  - Mitigation: encode educational-abstraction wording directly in specs/design/tasks and keep the ladder sweet-gas only.
- **Downstream gas products could be misread as unlock-only magic without topology gates.**
  - Mitigation: freeze connected-path product rules, stage-to-product reachability pairs, and no-unlock-only-generation expectations directly in specs and tests.
- **The Godot scene references missing scripts today.**
  - Mitigation: make those exact script paths explicit implementation targets instead of silently changing the scene contract.
- **Current tests freeze the generic heater/flash world very tightly.**
  - Mitigation: lead with red tests that rewrite the default sandbox expectations while preserving tutorial expectations.

## Verification Strategy

- TDD should lead all contract, catalog, progression, service/API, and client changes.
- Required verification for implementation:
  - `uv run pytest tests/gameplay/test_sandbox_contracts.py`
  - `uv run pytest tests/gameplay/test_start_catalog.py`
  - `uv run pytest tests/gameplay/test_sandbox_catalog.py`
  - `uv run pytest tests/gameplay/test_progression.py`
  - `uv run pytest tests/gameplay/test_sandbox_session.py`
  - `uv run pytest tests/gameplay/test_economics_ledger.py`
  - `uv run pytest tests/gameplay/test_realtime_game_service.py`
  - `uv run pytest tests/gameplay/test_board_layout.py`
  - `uv run pytest tests/gameplay/test_sandbox_starts.py`
  - `uv run pytest tests/app/test_game_api.py`
  - `uv run pytest tests/integration/test_sandbox_start_smoke.py`
  - `uv run pytest tests/integration/test_sandbox_session_smoke.py`
  - `uv run pytest tests/integration/test_game_vertical_slice_smoke.py`
  - `uv run pytest tests/integration/test_examples_smoke.py -k "gas_1 or gas_2 or gas_3 or gas_4 or heater_flash or van_de_vusse or ammonia_recycle"`
  - `godot4 --headless --path clients/godot_phase1_vertical_slice --script res://tests/smoke_test.gd`
- Expected evidence:
  - the main sandbox still starts under `phase1_process_sandbox_v1` but now presents gas-first content,
  - tutorials remain separate and unchanged,
  - progression state is explicit in authoritative gameplay and service snapshots,
  - the canonical starter-batch and post-unlock-batch progression snapshots match the exact frozen tuples above,
  - locked items reject with `item_locked` before topology/layout/cash mutation,
  - `submit-research` consumes the exact mixed-product batch recipe and unlocks the next batch exactly once,
  - unlock alone never creates downstream gas products and qualifying connected paths are required for `separator_gas`, `unstabilized_condensate`, `dry_gas`, `ngl_liquids`, and `stabilized_condensate`,
  - `buy-feed` / `sell-product` remain direct material/product routes without `tank_id`,
  - the current fixed prices still quote the exact frozen values while the economics implementation now has a narrow default pricing-policy seam for later dynamic pricing,
  - gas example assets back the start catalog, the stage ladder, and the next-recipe reachability smokes,
  - client HUD/bootstrap state reflects the current stage and current unlocked build items.

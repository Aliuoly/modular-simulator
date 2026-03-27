## Dependency gate

- [x] D0 Do not start implementation until this refreshed ej7 pack is approved and implementation Beads tasks are created from these waves.

## Wave 1 — Freeze the narrowed gas-first contracts with red tests first

- [x] 1.1 Extend `tests/gameplay/test_sandbox_contracts.py` with red contract tests for:
  - `ProgressionSnapshot` exact fields
  - `ResearchSubmissionResult` exact fields
  - `SimulationSessionSnapshot.progression_snapshot`
  - new stable error codes `item_locked`, `unknown_research_unlock`, `research_not_available`, and `research_unavailable_for_session`
  - success-only `ResearchSubmissionResult` semantics while rejected research requests still raise `SandboxRequestError`
- [x] 1.2 Add a new red file `tests/gameplay/test_progression.py` freezing the exact stage order, batched research id, stage-to-item mapping, mixed-product research recipe, and the exact starter-batch / post-unlock-batch `ProgressionSnapshot` tuples from `design.md`, including:
  - `active_stage_id` as the highest unlocked stage,
  - cumulative `available_item_ids`,
  - single-entry batched `available_research_ids`,
  - roadmap-visible availability of `unlock_cold_recovery_train_v1` from sandbox start,
  - and the exact tuple ordering for both canonical progression states.
- [x] 1.3 Rewrite `tests/gameplay/test_start_catalog.py`, `tests/gameplay/test_sandbox_catalog.py`, and `tests/gameplay/test_sandbox_starts.py` so the default sandbox record becomes gas-first while the three tutorial starts remain unchanged.
- [x] 1.4 Extend `tests/gameplay/test_sandbox_session.py` with red tests proving:
  - `start_sandbox()` initializes the starter batch items and roadmap-visible research state
  - main-sandbox startup inventory keys are exactly `sweet_wet_gas` plus `separator_gas`, `unstabilized_condensate`, `dry_gas`, `ngl_liquids`, and `stabilized_condensate`
  - tutorials keep `progression_snapshot=None`
  - `submit_research_unlock(...)` is sandbox-only, exact-recipe, inventory-backed, and side-effect-free on rejection
  - successful unlock moves the snapshot to the exact post-unlock canonical tuple
  - unlock alone does not create downstream product inventory
  - earlier gas products remain producible when their qualifying path still exists
  - locked gas items reject with `item_locked`
- [x] 1.5 Extend `tests/gameplay/test_realtime_game_service.py`, `tests/app/test_game_api.py`, and `tests/gameplay/test_board_layout.py` with red tests proving:
  - main-sandbox bootstrap starter-batch items are exactly `place_inlet_gas_separator`, `place_teg_contactor`, `place_rich_glycol_flash_tank`, `place_lean_rich_glycol_exchanger`, `place_teg_regenerator`, `install_glycol_circulation_pump`, and `build_process_line`
  - `supported_build_item_ids` becomes progression-driven rather than a process-wide constant
  - `submit-research` route exists with exact payload keys and stable 400/404/409 semantics
  - `heater_flash_guided_build_v1` remains the guided-tutorial mode id while runtime start mapping still resolves to `heater_flash_tutorial_start_v1`
  - `buy-feed` and `sell-product` stay direct `material_id` / `product_id` payloads with no public `tank_id`
  - locked/invalid build requests do not mutate topology, board layout, or cash
- [x] 1.6 Extend `tests/gameplay/test_economics_ledger.py`, `tests/integration/test_sandbox_start_smoke.py`, `tests/integration/test_sandbox_session_smoke.py`, and `tests/integration/test_game_vertical_slice_smoke.py` with red checks for the gas-first item/material/product tables, gas example provenance, and unchanged tutorial smokes.
- [x] 1.7 Extend stage/example reachability coverage so red tests freeze these exact pairs and the mixed batch recipe:
  - in `tests/gameplay/test_sandbox_session.py`, starter stage / `gas_1_inlet_separator.py` → `separator_gas` and `unstabilized_condensate` contribute to `unlock_cold_recovery_train_v1`
  - in `tests/gameplay/test_sandbox_session.py`, `teg_dehydration_v1` / `gas_2_teg_dehydration.py` → `dry_gas` contributes to `unlock_cold_recovery_train_v1`
  - in `tests/gameplay/test_sandbox_session.py`, disconnected dehydration-package support items do **not** qualify `dry_gas`
  - in `tests/integration/test_examples_smoke.py`, post-unlock `gas_3_jt_low_temperature_separation.py` → `ngl_liquids` remains reachable as the cold-recovery product
  - in `tests/integration/test_examples_smoke.py`, post-unlock `gas_4_condensate_stabilizer.py` → `stabilized_condensate` remains reachable as the stabilization product
- [x] 1.8 Run the red boundary:
  - `uv run pytest tests/gameplay/test_sandbox_contracts.py tests/gameplay/test_start_catalog.py tests/gameplay/test_sandbox_catalog.py tests/gameplay/test_progression.py`
  - `uv run pytest tests/gameplay/test_sandbox_session.py tests/gameplay/test_realtime_game_service.py tests/gameplay/test_board_layout.py tests/app/test_game_api.py`
  - `uv run pytest tests/gameplay/test_sandbox_starts.py tests/gameplay/test_economics_ledger.py tests/integration/test_sandbox_start_smoke.py tests/integration/test_sandbox_session_smoke.py tests/integration/test_game_vertical_slice_smoke.py`
  - Expected evidence: the current generic heater/flash slice fails against the narrowed gas-first contract.

## Wave 2 — Implement progression contracts, gas starts/catalog, and gas example provenance

- [x] 2.1 Update `src/modular_simulation/gameplay/contracts.py` with `ProgressionSnapshot`, `ResearchSubmissionResult`, and `SimulationSessionSnapshot.progression_snapshot` only.
- [x] 2.2 Add `src/modular_simulation/gameplay/progression.py` with the exact stage catalog, research catalog, stage unlock mapping, and helper lookups frozen in `design.md`.
- [x] 2.3 Update `src/modular_simulation/gameplay/start_catalog.py`, `src/modular_simulation/gameplay/sandbox_catalog.py`, and `src/modular_simulation/gameplay/starts/builders.py` so `phase1_process_sandbox_v1` becomes the gas-first world while tutorial records remain unchanged.
- [x] 2.3a Keep mode/start id boundaries explicit while updating starts: `start_catalog.py` continues to own `*_tutorial_start_*` ids, and `start_runtime.py` / service surfaces continue to expose guided tutorial mode ids like `heater_flash_guided_build_v1`.
- [x] 2.4 Add seed-backed gas examples under `examples/unit_process_flowsheet/`:
  - `gas_1_inlet_separator.py`
  - `gas_2_teg_dehydration.py`
  - `gas_3_jt_low_temperature_separation.py`
  - `gas_4_condensate_stabilizer.py`
- [x] 2.5 Make each gas example the canonical proof artifact for its stage/product pair or starter-batch research contribution and keep names aligned across builders, start metadata, and smoke tests.
- [x] 2.6 Keep proxy boundaries explicit in code comments/test naming: dehydration, JT/LTS, and stabilizer are educational proxies, not rigorous absorber/cryogenic/column models.

## Wave 3 — Implement gameplay/session/economics behavior for the narrow live gas world

- [x] 3.1 Update `src/modular_simulation/gameplay/sandbox_session.py` so sandbox startup initializes the gas-first progression snapshot and tutorials remain progression-free.
- [x] 3.2 Add `submit_research_unlock(...)` to `sandbox_session.py` with exact mixed-recipe validation, batched unlock behavior, and no inventory consumption on rejection.
- [x] 3.2a Keep research submission on the existing sandbox-session error pattern: invalid/unavailable submissions raise `SandboxRequestError`, while successful submissions return `ResearchSubmissionResult(success=True, reason_code=None, snapshot=...)`.
- [x] 3.3 Replace generic `feed_a/feed_b/product_a/product_b` sandbox handling in `sandbox_session.py` with the gas-first feed/product ids and the frozen path-qualified production rules from `design.md`, including:
  - no unlock-only product generation,
  - connected-path gating for each named gas product,
  - dehydration-package support items qualifying `dry_gas` only when they are in the same connected component/package as the qualifying contactor path,
  - cumulative earlier-product producibility when qualifying paths remain,
  - and non-stacking duplicate-path behavior per product id.
- [x] 3.4 Update `src/modular_simulation/gameplay/economics.py` with the exact gas-item anchors and gas feed/product price tables while retaining legacy tutorial-facing tables, and introduce one narrow internal default pricing-policy seam used by both the module-level quote functions and `CashLedgerRuntime` methods.
- [x] 3.4a Preserve existing gameplay/session/API/client quote contracts while adding the pricing seam; this wave must not widen command payloads or snapshot shapes for pricing concerns.
- [x] 3.5 Keep public commerce narrow: do not add public `tank_id` or purity-spec logic in this wave.
- [x] 3.6 Run targeted gameplay verification:
  - `uv run pytest tests/gameplay/test_progression.py`
  - `uv run pytest tests/gameplay/test_sandbox_session.py`
  - `uv run pytest tests/gameplay/test_economics_ledger.py`
  - Expected evidence: the mixed-product batched research unlock is inventory-backed and roadmap-visible from sandbox start; stage-qualified paths, not unlocks alone, generate downstream gas products; the starter batch can satisfy the frozen mixed-product recipe before the cold-recovery batch unlocks; gas-first economics still returns the exact frozen values through the new pricing seam; no public tank-mediated sales surface is introduced.

## Wave 4 — Remove stale heater/flash assumptions from service/API/client minimums

- [x] 4.1 Update `src/modular_simulation/gameplay/start_runtime.py` to keep stable mode ids while composing the gas-first sandbox start/runtime bundle.
- [x] 4.2 Update `src/modular_simulation/gameplay/realtime_service.py` to:
  - derive main-sandbox build affordances from progression state,
  - add a service method for research submission,
  - stop hard-coding old generic sandbox published-signal sets,
  - keep `buy-feed` / `sell-product` direct and tank-free,
  - preflight locked/invalid build commands before topology/layout/ledger mutation.
- [x] 4.3 Update `src/modular_simulation/gameplay/service_contracts.py` and `src/modular_simulation/app/game_api.py` so authoritative snapshots carry progression state and the HTTP bridge adds only the frozen `submit-research` route.
- [x] 4.4 Update `clients/godot_phase1_vertical_slice/scenes/MainGame.tscn` and restore/create these exact script paths if absent:
  - `clients/godot_phase1_vertical_slice/scripts/world_renderer.gd`
  - `clients/godot_phase1_vertical_slice/scripts/hud_controller.gd`
  - `clients/godot_phase1_vertical_slice/scripts/build_command_panel.gd`
  so the client can render current stage, available research, and currently unlocked build items.
- [x] 4.5 Keep `ModularSimulator-6ei` out of implementation scope for this wave; do not refactor gameplay placement into a generic abstraction beyond what is strictly needed for this exact item set.
- [x] 4.6 Run service/API/client verification for this wave:
  - `uv run pytest tests/gameplay/test_realtime_game_service.py`
  - `uv run pytest tests/app/test_game_api.py`
  - `uv run pytest tests/integration/test_game_vertical_slice_smoke.py`
  - `godot4 --headless --path clients/godot_phase1_vertical_slice --script res://tests/smoke_test.gd`
  - Expected evidence:
    - bootstrap starter items are gas-first,
    - snapshots carry progression state and progression-driven `supported_build_item_ids`,
    - `submit-research` honors the frozen payload/status semantics,
    - locked build requests remain atomic,
    - the HUD exposes current stage, available research, and unlocked build items.

## Wave 5 — Docs/spec sync, full verification, and review gate

- [x] 5.1 Update `docs/game_backend_overview.md` and `docs/godot_vertical_slice.md` for the gas-first default sandbox and research-aware client/API surface.
- [x] 5.2 Sync the implemented deltas into live specs:
  - `openspec/specs/progression/spec.md` (new)
  - `openspec/specs/units-and-components/spec.md`
  - `openspec/specs/session/spec.md`
  - `openspec/specs/economics/spec.md`
  - `openspec/specs/client-godot/spec.md`
- [x] 5.3 Run the final verification matrix:
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
- [x] 5.4 Required final evidence:
  - `phase1_process_sandbox_v1` is now the gas-first world under the stable id,
  - tutorials remain separate and unchanged,
  - starter and post-unlock progression snapshots match the frozen canonical tuples,
  - starter and unlocked build items come from authoritative progression state,
  - `submit-research` unlocks the cold-recovery/stabilization batch and consumes the exact mixed-product inventory recipe,
  - qualifying connected paths, not unlock-only state changes, govern gas product generation and research reachability,
  - `buy-feed` / `sell-product` remain direct non-tank routes,
  - the default fixed-price policy seam preserves the exact frozen prices without hard-wiring pricing into unrelated contracts,
  - locked/invalid build commands do not mutate topology, board layout, or cash,
  - gas example assets and start builders stay aligned.
- [x] 5.5 Before closing implementation, run `hybrid-code-reviewer` and `simulation-advisor` in parallel because this pack uses named gas-processing proxy semantics plus gameplay/economics contracts that teach process-engineering concepts.

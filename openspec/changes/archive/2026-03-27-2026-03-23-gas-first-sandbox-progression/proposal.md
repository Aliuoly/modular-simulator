## Why

`ej7.1` removed the tank-ownership/runtime blocker, but the current live gameplay slice is still the old generic heater/flash sandbox: no progression state, no research submission action, no gas-first start/catalog/economics tables, and no client/API support for staged unlocks.

Repo reality also shows the broad original `ej7` framing is too wide for an implementation-ready pack right now. The active codebase still has hard-coded heater/flash build items, generic `feed_a` / `product_a` inventory ids, and a Godot scene that references missing controller scripts. Beads text for `ModularSimulator-ej7` is additionally stale because it still implies public tank-mediated sales and purity-policy work that are not yet encoded in the active OpenSpec pack and are not required for the first live gas-world slice.

This change refreshes `ej7` to a **narrow first live gas-world pack**: replace the default sandbox content with a sweet-wet-gas ladder, add explicit progression/research state with batched milestones rather than one-product/one-unlock churn, wire the minimum API/client surfaces needed to play that ladder, and defer public tank gameplay, tank-mediated sale policy, logistics, and generic placement refactors.

## What Changes

- Replace the **content** of `phase1_process_sandbox_v1` with a sweet-wet-gas main sandbox while keeping tutorial starts separate and unchanged.
- Add a new `progression` capability for explicit unlock state plus inventory-backed `submit_research_unlock(...)` behavior.
- Freeze the exact narrow gas-first ladder already chosen for this world, but group it into two progression batches:
  1. starter batch: inlet gas separation + TEG dehydration,
  2. unlock batch: JT / low-temperature separation + condensate stabilization.
- Freeze one batched research milestone that consumes differing quantities of starter-batch products and unlocks the full cold-recovery/stabilization batch.
- Add the minimum gameplay/session/economics/API/client changes needed to surface current stage, current buildable items, research submission, and a default fixed-price policy seam that can later host dynamic pricing.
- Keep public commerce narrow in this pack: `buy-feed` stays material-id based, `sell-product` stays product-id based, and no public `tank_id` / purity-spec sales surface is introduced yet.
- Defer the generic gameplay placement refactor to `ModularSimulator-6ei` instead of bundling it into this pack.

## Capabilities

### New Capabilities
- `progression`

### Modified Capabilities
- `units-and-components`
- `session`
- `economics`
- `client-godot`

## Impact

- Affected code:
  - `src/modular_simulation/gameplay/contracts.py`
  - `src/modular_simulation/gameplay/progression.py` (new)
  - `src/modular_simulation/gameplay/sandbox_catalog.py`
  - `src/modular_simulation/gameplay/start_catalog.py`
  - `src/modular_simulation/gameplay/starts/builders.py`
  - `src/modular_simulation/gameplay/sandbox_session.py`
  - `src/modular_simulation/gameplay/economics.py`
  - `src/modular_simulation/gameplay/service_contracts.py`
  - `src/modular_simulation/gameplay/start_runtime.py`
  - `src/modular_simulation/gameplay/realtime_service.py`
  - `src/modular_simulation/app/game_api.py`
  - `examples/unit_process_flowsheet/gas_1_inlet_separator.py` (new)
  - `examples/unit_process_flowsheet/gas_2_teg_dehydration.py` (new)
  - `examples/unit_process_flowsheet/gas_3_jt_low_temperature_separation.py` (new)
  - `examples/unit_process_flowsheet/gas_4_condensate_stabilizer.py` (new)
  - `clients/godot_phase1_vertical_slice/scenes/MainGame.tscn`
  - `clients/godot_phase1_vertical_slice/scripts/world_renderer.gd` (restore/create if absent)
  - `clients/godot_phase1_vertical_slice/scripts/hud_controller.gd` (restore/create if absent)
  - `clients/godot_phase1_vertical_slice/scripts/build_command_panel.gd` (restore/create if absent)
- Affected tests:
  - `tests/gameplay/test_sandbox_contracts.py`
  - `tests/gameplay/test_start_catalog.py`
  - `tests/gameplay/test_sandbox_catalog.py`
  - `tests/gameplay/test_progression.py` (new)
  - `tests/gameplay/test_sandbox_session.py`
  - `tests/gameplay/test_economics_ledger.py`
  - `tests/gameplay/test_realtime_game_service.py`
  - `tests/gameplay/test_board_layout.py`
  - `tests/gameplay/test_sandbox_starts.py`
  - `tests/app/test_game_api.py`
  - `tests/integration/test_sandbox_start_smoke.py`
  - `tests/integration/test_sandbox_session_smoke.py`
  - `tests/integration/test_game_vertical_slice_smoke.py`
  - `tests/integration/test_examples_smoke.py`
  - `clients/godot_phase1_vertical_slice/tests/smoke_test.gd`
- Affected docs:
  - `docs/game_backend_overview.md`
  - `docs/godot_vertical_slice.md`
- Follow-on work explicitly deferred from this pack:
  - public tank-mediated sales / purity policy under `ModularSimulator-ej7`
  - player-managed transport/logistics under `ModularSimulator-9tr.1`
  - generic placement-command refactor under `ModularSimulator-6ei`
- Affected OpenSpec sync surfaces after implementation:
  - `openspec/specs/progression/spec.md` (new)
  - `openspec/specs/units-and-components/spec.md`
  - `openspec/specs/session/spec.md`
  - `openspec/specs/economics/spec.md`
  - `openspec/specs/client-godot/spec.md`

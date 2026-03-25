## Context

- `src/modular_simulation/gameplay/realtime_service.py` currently freezes `SUPPORTED_BUILD_ITEM_IDS = ("place_heater_cooler", "place_flash_drum", "build_process_line")` and routes `build(...)` through item-id branches for those exact three items.
- `src/modular_simulation/gameplay/sandbox_catalog.py` already provides typed catalog records with `item_kind`, `apply_kind`, `default_config`, `required_user_inputs`, and `supported_start_ids`.
- `src/modular_simulation/gameplay/start_catalog.py` already allows more build items on `phase1_process_sandbox_v1` than the realtime slice currently exposes, including `place_heat_exchanger`, `place_component_separator`, `install_sampled_delayed_sensor`, and `install_pid_controller`.
- The current supported realtime modes remain only `phase1_process_sandbox_v1` and `heater_flash_guided_build_v1` in `src/modular_simulation/gameplay/start_runtime.py`.
- `src/modular_simulation/app/game_api.py` duplicates the stale process-wide realtime build-item tuple into `SUPPORTED_BUILD_ITEM_IDS_BY_MODE_ID`.
- Closed follow-on `openspec/changes/2026-03-24-harden-unit-metadata-error-translation/` already freezes caller-boundary `invalid_config` handling around `_resolve_unit_metadata()`. The 6ei pack must preserve that merged behavior and regression coverage while refactoring add-process dispatch.
- Current runtime sensor binding remains broader than a semantically clear public port-mounted contract: `signal_key` is bound as the underlying measurement tag, so public sensor exposure is deferred to Beads follow-up `ModularSimulator-9tr.3`.
- Current realtime gameplay remains topology-only: build placement installs topology shells and tick advances `sandbox_runtime` inventory/economics without stepping live process models, so public multicomponent shortcut distillation is deferred to Beads follow-up `ModularSimulator-9tr.4`.

## Goals / Non-Goals

**Goals**
- Replace item-id-specific public gameplay build routing with generic family dispatch for public `add_process` work.
- Widen the sandbox playable slice only to the public `add_process` units that remain honest under the current topology-only gameplay architecture.
- Keep the public route/method set stable while making bootstrap and snapshot build lists mode-specific and exact.

**Non-Goals**
- Do not create a full `apply_kind` dispatcher across every catalog family.
- Do not expose sensors, controllers, junctions, or line overlays through the current playable build route in this pack.
- Do not expose `place_component_separator` or any runtime-backed multicomponent separator through the current playable build route in this pack.
- Do not add a new playable mode for `reactor_control_tutorial_start_v1`.
- Do not change economics formulas, price tables, or receipt semantics.
- Do not introduce progression-driven unlock logic here; exact mode-specific lists remain static for this slice.

## Decisions

1. **6ei becomes a public-family dispatch refactor, not a full catalog executor.**
   - Internal gameplay dispatch should stop branching on exact unit ids for currently public units.
    - This pack only freezes two public families:
      - `unit_blueprint` + `add_process`
      - `line` + `connect_configure_line` (retained on the same route, but with explicit endpoint semantics)
   - Sensors, controllers, junctions, and overlays remain explicit follow-on work rather than being smuggled into an `add_component` umbrella.

2. **Public build-item advertisement is derived from the bound start's `allowed_item_ids`, filtered by the approved public-family matrix.**
   - The durable authority for mode-specific advertisement in this pack is `start.allowed_item_ids` for the mode's bound start, not `catalog.supported_start_ids`.
   - The implementation may still use catalog metadata to classify items, but the exact advertised list comes from `start.allowed_item_ids ∩ {public add_process items, build_process_line}`.
    - Freeze exact results for this pack:
      - `phase1_process_sandbox_v1`: `place_heater_cooler`, `place_flash_drum`, `place_heat_exchanger`, `build_process_line`
      - `heater_flash_guided_build_v1`: `place_heater_cooler`, `place_flash_drum`, `build_process_line`
    - `place_component_separator`, `install_sampled_delayed_sensor`, `install_pid_controller`, junctions, and overlays stay hidden from the public playable slice even though underlying catalog/start metadata exists.

3. **Generic add-process routing uses runtime-authoritative unit metadata and preserves the hardening boundary.**
   - The add-process family should route every currently public `unit_blueprint/add_process` item through the same placement path.
   - That path should continue using `_resolve_unit_metadata(...)` and real declared unit ports rather than a second registry.
   - The 6ei refactor must preserve the `invalid_config` caller-boundary translation frozen by `2026-03-24-harden-unit-metadata-error-translation`.
   - Because both packs touch `src/modular_simulation/gameplay/realtime_service.py` and `tests/gameplay/test_realtime_game_service.py`, this pack must carry forward the closed hardening regression scenarios inside its touched test boundary instead of treating the overlap as advisory.

4. **Public line building becomes endpoint-aware on the existing `build_process_line` surface.**
   - The route stays `build(item_id="build_process_line", config, layout)`; no new route or top-level payload field is added.
   - `config.source` and `config.target` become exact endpoint strings:
     - bare boundary ids remain valid for feed/product boundaries
     - all non-boundary nodes must use explicit `<process_id>.<port_name>` endpoint strings
   - Gameplay must stop inferring process endpoints as `.out` / `.in`.
   - Bare process ids are invalid for all non-boundary nodes and must fail with stable `invalid_config` plus actionable endpoint guidance.
   - Endpoint direction remains substrate-aligned: source endpoints must be outlets and target endpoints must be inlets.
   - Syntactically valid but unknown endpoint ids (unknown boundaries, unknown process ids, or unknown process-port combinations) also fail with stable `invalid_config`.

5. **Generic add-process refactor preserves existing build orchestration semantics.**
   - Successful widened add-process builds continue to use the existing `build(...)` command surface, record equipment purchases through `cash_ledger_runtime.record_equipment_purchase(...)`, and call `sandbox_runtime.install_catalog_item(...)` so install counts and tutorial semantics stay stable.
   - Rejected widened add-process builds must fail before board-layout/install-count/cash changes are committed for the rejected command.
   - This pack does not introduce a parallel install-count path or a special case that bypasses `install_catalog_item(...)` for newly public units.

6. **The widened unit-and-line slice remains topology-validating, not runtime-behavioral.**
   - A successful public build in this pack means the unit can be placed and lines can be wired against real named ports using topology-valid endpoint strings.
   - This pack still does **not** claim runtime heater duty, flash split behavior, heat-exchanger heat transfer, hydraulic consequences from line geometry, or topology-coupled production.
   - Verification and spec wording must say explicitly that the gameplay slice remains topology-only even after port-aware line validation is added.

7. **Public sensor exposure is deferred rather than partially widened.**
   - `install_sampled_delayed_sensor` remains in the frozen catalog and start metadata, but it is not part of the 6ei playable build widening.
   - The reason for deferral is semantic, not missing plumbing: current runtime sensor binding uses `signal_key` as the measurement tag, so a public process-port placement contract would be misleading without a stricter signal-to-target rule.
    - Follow-on Beads task `ModularSimulator-9tr.3` owns the public sensor target model and measurement-semantics contract.

8. **Public multicomponent separator exposure is deferred rather than papered over.**
   - `place_component_separator` remains a catalog/start artifact, but it is not part of the 6ei playable build widening.
   - Repo evidence showed its frozen metadata is not a valid runtime-authoritative public contract, and user direction rejected fake equal-split or metadata-override workarounds.
   - A real public multicomponent separator must be runtime-backed and explicitly name the real shortcut methods/correlations rather than pretending topology-only placement gives separation behavior.
   - Follow-on Beads task `ModularSimulator-9tr.4` owns discovery/spec work for runtime-backed public multicomponent shortcut distillation.

9. **Public method/route shapes remain unchanged while values widen.**
   - `RealtimeGameService` method set stays exactly `get_bootstrap`, `create_session`, `get_snapshot`, `build`, `buy_feed`, `sell_product`, `restart_session`, `tick`.
   - HTTP routes stay exactly the current set.
   - `GameBootstrapResponse` and `GameSnapshot` field sets stay unchanged; only `supported_build_item_ids_by_mode_id` and `supported_build_item_ids` values widen.

## Risks / Trade-offs

- **Overlap with the recently closed metadata-hardening change is the main implementation risk.**
  - Mitigation: preserve the `_resolve_unit_metadata()` caller-boundary error translation tests while refactoring dispatch.

- **The widened sandbox build list increases public smoke coverage.**
  - Mitigation: freeze exact per-mode build lists and add integration coverage that exercises named-port wiring through the current public unit slice without widening deferred sensor/controller/overlay scope.

- **Start metadata is broader than the honest current public slice.**
  - Mitigation: keep advertisement derived from `start.allowed_item_ids`, but filter it through the approved public-family matrix and explicit deferred-item fences so `place_component_separator` stays out of the current client-facing list.

- **The old `.in` / `.out` gameplay endpoint shortcut is incompatible with real named ports on the widened unit slice.**
  - Mitigation: revise the public line contract to exact endpoint strings and add stable rejection coverage for malformed, ambiguous, unknown-port, and wrong-direction endpoints.

## Verification Strategy

- TDD should lead this pack because it replaces frozen public build-surface assumptions and widens the playable slice.
- Required implementation evidence:
  - sandbox bootstrap/snapshot build lists widen exactly to the approved mode-specific values
  - `place_heat_exchanger` builds through the generic add-process path without new item-specific branches
  - public `build_process_line` accepts exact endpoint strings for the widened unit slice and rejects ambiguous bare process ids
  - `place_component_separator`, sensors, controllers, junctions, and line overlays remain outside the current public playable build slice
  - `GameBootstrapResponse` / `GameSnapshot` / route sets stay shape-stable
  - `_resolve_unit_metadata()` failure handling is not weakened by the add-process refactor
  - widened add-process builds preserve receipt/install-count orchestration and rejected build attempts leave authoritative state unchanged
  - topology payloads and board-layout line entities preserve the exact endpoint strings the player built
  - the widened slice remains explicitly topology-only and does not claim runtime unit behavior from successful placement/wiring
- Required verification commands for implementation:
  - `uv run pytest tests/gameplay/test_realtime_game_service.py`
  - `uv run pytest tests/app/test_game_api.py`
  - `uv run pytest tests/integration/test_game_vertical_slice_smoke.py`
  - `uv run pytest tests/gameplay/test_sandbox_session.py` (if gameplay-layer validation is shared there)
- Because this pack widens the public slice for additional unit operations without changing their underlying models, independent `hybrid-plan-reviewer` and `simulation-advisor` review are both required.

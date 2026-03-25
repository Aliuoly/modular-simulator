## Dependency gate

- [x] D0 Do not start implementation until this change pack is approved and the implementation packet is created in Beads from these tasks.
- [x] D1 Preserve the merged `_resolve_unit_metadata()` hardening boundary from `openspec/changes/2026-03-24-harden-unit-metadata-error-translation/`; if `src/modular_simulation/gameplay/realtime_service.py` or its API tests are touched, carry forward that pack's exact `invalid_config` regression scenarios inside this implementation boundary instead of re-deciding sequencing ad hoc.

## Wave 1 — Write red tests for the widened public build slice, generic family routing, and port-aware line semantics

- [x] 1.1 Extend `tests/gameplay/test_realtime_game_service.py` with red public-surface guards for mode-specific build-item exposure:
  - `phase1_process_sandbox_v1` now advertises exactly `place_heater_cooler`, `place_flash_drum`, `place_heat_exchanger`, and `build_process_line`
  - `heater_flash_guided_build_v1` remains exactly `place_heater_cooler`, `place_flash_drum`, and `build_process_line`
  - `place_component_separator`, `install_sampled_delayed_sensor`, `install_pid_controller`, `install_line_pump`, `install_line_valve`, `install_line_heat_actuator`, `place_merge_junction_2x1`, and `place_split_junction_1x2` remain outside the current public playable build slice.
- [x] 1.2 Extend `tests/gameplay/test_realtime_game_service.py` with red behavior-matrix tests for generic add-process routing:
  - sandbox `build(...)` accepts `place_heat_exchanger` with the same `process_id` + `anchor_xy` contract as the existing heater/flash path
  - `place_component_separator` remains rejected on the stable `unknown_item` path for the current playable slice
  - the widened add-process family preserves stable `unknown_item` / `invalid_config` behavior, rejected builds stay state-atomic, and no new public methods are introduced
  - `build_process_line` succeeds for explicit endpoint strings such as `feed_a -> heater_1.inlet`, `heater_1.outlet -> product_a`, `feed_a -> flash_1.inlet`, `flash_1.vapor_outlet -> product_a`, and explicit heat-exchanger side wiring.
- [x] 1.2a Extend `tests/gameplay/test_realtime_game_service.py` with red endpoint-validation guards for the revised line contract:
  - bare non-boundary process ids such as `heater_1`, `flash_1`, and `heat_exchanger_1` are rejected on the stable `invalid_config` path
  - unknown port names and wrong-direction endpoint usage fail with stable `invalid_config`
  - syntactically valid but unknown endpoint ids such as `ghost_1.outlet` or unknown boundaries also fail with stable `invalid_config`
  - topology and board-layout line payloads preserve the exact endpoint strings used in the accepted build request.
- [x] 1.3 Extend `tests/gameplay/test_realtime_game_service.py` with red regression guards copied forward from the closed metadata-hardening pack:
  - invalid configured `unit_module` resolution still fails as `SandboxRequestError(error_code="invalid_config", ...)`
  - missing configured exported `unit_type` still fails as `SandboxRequestError(error_code="invalid_config", ...)`
  - invalid constructor payload during `_resolve_unit_metadata(...)` still fails as `SandboxRequestError(error_code="invalid_config", ...)`.
- [x] 1.4 Extend `tests/app/test_game_api.py` with red HTTP guards:
  - bootstrap returns the widened sandbox build list and unchanged tutorial list
  - sandbox build requests can place `place_heat_exchanger`
  - sandbox build requests can wire newly public units only through explicit endpoint strings on the existing `build_process_line` route, including `hot_inlet`, `cold_inlet`, `hot_outlet`, and `cold_outlet` for heat exchangers
  - bare process endpoints, unknown port names, wrong-direction endpoints, and syntactically valid but unknown endpoint ids fail with stable JSON `{error_code, message}` and HTTP `400`
  - `place_component_separator` and deferred public sensor/controller/overlay items still fail with stable `unknown_item` behavior for the current playable slice
  - metadata-resolution failures still produce stable JSON `{error_code, message}` with HTTP `400`.
- [x] 1.5 Extend `tests/integration/test_game_vertical_slice_smoke.py` with one red sandbox smoke proving the widened public slice can place units and wire them through explicit named ports on the existing command surface while still returning the standard command/snapshot envelopes.
- [x] 1.6 Run the red boundary:
  - `uv run pytest tests/gameplay/test_realtime_game_service.py`
  - `uv run pytest tests/app/test_game_api.py`
  - `uv run pytest tests/integration/test_game_vertical_slice_smoke.py`
  - Expected evidence: widened build-list and generic add-process routing tests fail before implementation exists.

## Wave 2 — Implement generic public-family dispatch and port-aware line semantics without widening beyond approved scope

- [x] 2.1 Refactor `src/modular_simulation/gameplay/realtime_service.py` so public build dispatch is driven by the approved catalog-family matrix rather than exact heater/flash item-id branches:
  - generic public `add_process` family over supported `unit_blueprint/add_process` items
  - existing line build family retained.
- [x] 2.2 Replace the process-wide supported-build tuple with mode/start-derived helpers in `src/modular_simulation/gameplay/realtime_service.py`:
  - compute exact public build items per supported mode from the bound start's `allowed_item_ids`, filtered by the approved public family matrix
  - make `get_bootstrap()` and `GameSnapshot.supported_build_item_ids` use those exact per-mode values.
- [x] 2.3 Preserve runtime-authoritative add-process metadata resolution while refactoring:
  - keep `_resolve_unit_metadata(...)` as the authoritative add-process metadata seam
  - preserve the merged `invalid_config` error-translation boundary when metadata resolution fails.
- [x] 2.4 Preserve existing build orchestration semantics for widened add-process items:
  - successful widened add-process builds still record an equipment purchase and call `sandbox_runtime.install_catalog_item(...)`
  - rejected widened add-process builds leave topology, board layout, install counts, and cash unchanged for the rejected command.
- [x] 2.5 Update `src/modular_simulation/app/game_api.py` so bootstrap/build behavior reflects the new per-mode supported-build lists without freezing a duplicate process-wide constant.
- [x] 2.6 Refactor `src/modular_simulation/gameplay/realtime_service.py` line endpoint resolution to support the revised contract:
  - retain bare ids only for feed/product boundaries
  - require exact `<process_id>.<port_name>` strings for non-boundary endpoints
  - translate malformed, ambiguous, unknown-port, and wrong-direction endpoint requests into stable `invalid_config` gameplay errors.
- [x] 2.7 Preserve payload stability while storing exact endpoint strings:
  - no new top-level snapshot or route fields
  - topology and board-layout line entities keep the exact endpoint strings used by accepted builds.
- [x] 2.8 Do **not** widen beyond the approved 6ei boundary in this wave:
  - no `place_component_separator` public-build support
  - no sensor public-build support
  - no controller public-build support
  - no junction public-build support
  - no line-overlay public-build support
  - no new routes, modes, or top-level snapshot fields.

## Wave 3 — Prove the widened slice and unchanged public shapes

- [x] 3.1 Make the widened-mode build-list tests pass in `tests/gameplay/test_realtime_game_service.py` and `tests/app/test_game_api.py`.
- [x] 3.2 Make the generic add-process behavior matrix pass for heater, flash, and heat exchanger in sandbox mode while `place_component_separator` remains rejected on the stable current-slice unsupported path.
- [x] 3.2a Prove `build_process_line` passes through the revised explicit-endpoint contract after the refactor, including real named ports for heater, flash, and heat exchanger.
- [x] 3.2b Prove malformed, bare-process, unknown-endpoint, unknown-port, and wrong-direction endpoint requests fail on stable `invalid_config` behavior.
- [x] 3.3 Make the copied-forward metadata-hardening regression tests pass alongside the widened add-process routing.
- [x] 3.4 Prove rejected widened add-process builds remain state-atomic and deferred public sensor/controller/overlay items remain outside the playable slice.
- [x] 3.5 Make the widened sandbox smoke pass with explicit named-port wiring instead of direct feed-to-product bypass lines.
- [x] 3.5a Add an honesty guard proving the slice remains topology-only even after port-aware line validation, so the pack does not over-claim runtime unit behavior.
- [x] 3.6 Re-run the affected verification set:
  - `uv run pytest tests/gameplay/test_realtime_game_service.py`
  - `uv run pytest tests/app/test_game_api.py`
  - `uv run pytest tests/integration/test_game_vertical_slice_smoke.py`
  - `uv run pytest tests/gameplay/test_sandbox_session.py` (if gameplay-layer validation is shared there)

## Wave 4 — Sync live specs and lock the public contract

- [x] 4.1 Sync the implemented gameplay-dispatch delta into `openspec/specs/units-and-components/spec.md`:
  - public add-process routing becomes family-driven instead of heater/flash-specific
  - `place_component_separator`, sensor, controller, junction, and overlay families remain explicitly deferred from the playable slice.
- [x] 4.2 Sync the implemented gameplay/session error and routing delta into `openspec/specs/session/spec.md`:
  - widened public build families preserve stable request errors and existing equipment/install orchestration
  - public line semantics use exact endpoint strings on the existing build surface
  - metadata-resolution failures remain on the stable `invalid_config` path.
- [x] 4.3 Sync the implemented playable-slice delta into `openspec/specs/client-godot/spec.md`:
  - exact per-mode supported build-item lists
  - explicit endpoint-string contract for public `build_process_line`, including named heat-exchanger ports
  - stable HTTP `400` handling for invalid metadata-driven build failures
  - deferred `place_component_separator`, sensor, controller, junction, and overlay items remain outside the current playable slice.
- [x] 4.4 Run the final verification matrix:
  - `uv run pytest tests/gameplay/test_realtime_game_service.py`
  - `uv run pytest tests/app/test_game_api.py`
  - `uv run pytest tests/integration/test_game_vertical_slice_smoke.py`
  - `uv run pytest tests/gameplay/test_sandbox_session.py` (if touched)
- [x] 4.5 Expected final evidence:
  - the sandbox playable slice exposes the exact widened four-item build list and heater/flash tutorial remains on the three-item list
  - add-process unit placement no longer depends on heater/flash-only branches
  - public lines target exact named endpoints for exposed units instead of implicit `.in` / `.out` shortcuts
  - `place_component_separator`, sensors, controllers, junctions, and overlays remain deferred
  - route/method/top-level payload shapes stay unchanged.

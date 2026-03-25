## Why

`src/modular_simulation/gameplay/realtime_service.py` still freezes the public build surface as a process-wide tuple `("place_heater_cooler", "place_flash_drum", "build_process_line")` and routes `build(...)` through item-id branches for heater, flash, and line only. Repo evidence now shows that this is narrower than the already-frozen catalog/start contract for public add-process units:

- `phase1_process_sandbox_v1` already allows `place_heat_exchanger` and `place_component_separator` in `src/modular_simulation/gameplay/start_catalog.py`, but repo evidence now shows `place_component_separator` is not an honest public slice candidate under the current topology-only gameplay runtime
- `src/modular_simulation/gameplay/sandbox_catalog.py` already carries typed metadata for `unit_blueprint/add_process`
- the runtime-authoritative `_resolve_unit_metadata(...)` seam already exists for generic unit placement and the metadata-hardening follow-on is now closed separately

Without this pack, every newly exposed public add-process unit still requires bespoke gameplay branches, stale bootstrap constants, and duplicated per-mode build lists. That is the exact long-term blocker tracked by `ModularSimulator-6ei`.

## What Changes

- Replace item-specific realtime build routing with generic public-family dispatch for `unit_blueprint` + `add_process`.
- Keep the existing `build_process_line` route shape, but revise its public config contract from implicit process ids to explicit endpoint strings so newly public units can be wired against their real named ports.
- Freeze exact public playable build-item lists for this slice:
  - `phase1_process_sandbox_v1` exposes `place_heater_cooler`, `place_flash_drum`, `place_heat_exchanger`, and `build_process_line`
  - `heater_flash_guided_build_v1` remains `place_heater_cooler`, `place_flash_drum`, and `build_process_line`
- Keep sensors, controllers, junctions, line overlays, and a full `apply_kind` dispatcher deferred to follow-on work.
- Track public sensor semantics separately under Beads task `ModularSimulator-9tr.3` because current runtime `signal_key` behavior is broader than a semantically clear port-mounted public contract.
- Track runtime-backed public multicomponent shortcut distillation separately under Beads task `ModularSimulator-9tr.4` because current realtime gameplay remains topology-only and does not step live unit models.
- Preserve the current public route/method set and stable error-code family while widening only the exact supported build values.
- Preserve the current public route/method set and top-level payload shapes while allowing `build_process_line` to carry exact endpoint strings such as boundary ids and `<process_id>.<port_name>`.

## Capabilities

### Modified Capabilities
- `session`
- `units-and-components`
- `client-godot`

## Impact

- Affected code:
  - `src/modular_simulation/gameplay/realtime_service.py`
  - `src/modular_simulation/app/game_api.py`
  - `src/modular_simulation/gameplay/service_contracts.py` only if implementation needs a typed supported-build-list helper
- Affected tests:
  - `tests/gameplay/test_realtime_game_service.py`
  - `tests/app/test_game_api.py`
  - `tests/integration/test_game_vertical_slice_smoke.py`
  - tutorial-facing wiring checks inside `tests/gameplay/test_realtime_game_service.py` and/or `tests/app/test_game_api.py` if explicit flash outlet naming now becomes part of the public contract
  - `tests/gameplay/test_sandbox_session.py` only if gameplay-layer validation is shared there
- Affected OpenSpec sync surfaces after implementation:
  - `openspec/changes/2026-03-24-generalize-build-dispatch-units-sensors/specs/session/spec.md`
  - `openspec/changes/2026-03-24-generalize-build-dispatch-units-sensors/specs/units-and-components/spec.md`
  - `openspec/changes/2026-03-24-generalize-build-dispatch-units-sensors/specs/client-godot/spec.md`
  - `openspec/specs/session/spec.md`
  - `openspec/specs/units-and-components/spec.md`
  - `openspec/specs/client-godot/spec.md`
- Explicitly deferred:
  - public sensor-build generalization
  - controller public-build generalization
  - junction public-build generalization
  - line-overlay public-build generalization
  - progression-driven unlock lists from `2026-03-23-gas-first-sandbox-progression`

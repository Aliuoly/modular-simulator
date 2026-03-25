## Dependency gate

- [x] D0 Do not start implementation until this change pack is approved and the implementation packet is created in Beads from these tasks.

## Wave 1 — Add red regression coverage for the metadata-failure boundary

- [x] 1.1 Extend `tests/gameplay/test_realtime_game_service.py` with build-path red tests that patch `_resolve_unit_metadata()` dependency points and prove `RealtimeGameService.build(...)` / `_install_unit()` returns `SandboxRequestError(error_code="invalid_config", ...)` rather than leaking raw exceptions when metadata resolution fails because of:
  - missing configured `unit_module` target resolution,
  - missing configured exported `unit_type`,
  - constructor-payload signature/validation failure during `unit_cls(**constructor_payload)`.
  - Use targeted patching/spies; do not widen `SUPPORTED_BUILD_ITEM_IDS` or current start allowlists to manufacture a new public proof path.
- [x] 1.2 Extend `tests/app/test_game_api.py` with a red HTTP regression test that patches the build path to simulate an invalid metadata-resolution failure and proves the route returns stable JSON `{error_code, message}` with HTTP `400` and `error_code="invalid_config"`.
- [x] 1.3 Run the red boundary:
  - `uv run pytest tests/gameplay/test_realtime_game_service.py -k "resolve_unit_metadata or invalid_config"`
  - `uv run pytest tests/app/test_game_api.py -k "invalid_config or stable_error or build"`
  - Expected evidence: new metadata-failure guards fail before implementation hardening exists.

## Wave 2 — Harden the realtime metadata seam without widening public contracts

- [x] 2.1 Update `src/modular_simulation/gameplay/realtime_service.py` so `_install_unit()` is the explicit translation boundary for invalid runtime-authoritative metadata-resolution failures, returning `SandboxRequestError(error_code="invalid_config", ...)` while preserving exception chaining.
- [x] 2.2 Keep the translation seam narrow:
  - handle missing configured module-target resolution, missing configured unit-type lookup, and constructor-payload signature/validation failure during metadata resolution,
  - do not introduce new public error codes,
  - do not broaden exception masking beyond this metadata-resolution path unless a test-backed repo constraint forces it and the spec is updated first,
  - do not treat this as a blanket requirement to mask arbitrary import-time side-effect failures inside otherwise valid modules.
- [x] 2.3 Do **not** widen any public surface while implementing this hardening:
  - no new realtime-service public methods,
  - no new HTTP routes,
  - no build-item allowlist or start allowlist changes,
  - no snapshot or contract-shape changes.

## Wave 3 — Verify gameplay/API behavior stays stable and sync the OpenSpec deltas

- [x] 3.1 Make the new gameplay regression tests pass in `tests/gameplay/test_realtime_game_service.py` and confirm build-path metadata failures now surface as stable `invalid_config` errors.
- [x] 3.2 Make the new HTTP regression test pass in `tests/app/test_game_api.py` and confirm metadata failures still map to stable JSON `{error_code, message}` with HTTP `400`.
- [x] 3.3 Re-run the full affected verification set:
  - `uv run pytest tests/gameplay/test_realtime_game_service.py`
  - `uv run pytest tests/app/test_game_api.py`
- [x] 3.4 Sync the implemented deltas into the live specs:
  - update `openspec/specs/session/spec.md` to include runtime-authoritative metadata-resolution failures under invalid install requests,
  - update `openspec/specs/units-and-components/spec.md` to require stable gameplay error translation for invalid `add_process` metadata resolution,
  - update `openspec/specs/client-godot/spec.md` to require HTTP `400` + stable JSON for invalid metadata-driven build requests,
  - archive the change only after implementation and verification are complete.
- [x] 3.5 Expected final evidence:
  - build-path metadata-resolution failures no longer leak raw exceptions to callers,
  - gameplay build requests reject those failures with `SandboxRequestError(error_code="invalid_config", ...)`,
  - HTTP build requests preserve stable `{error_code, message}` payloads with status `400`,
  - no public surface widens beyond the existing slice.

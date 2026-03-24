## Why

`ModularSimulator-4fm` landed the module-private `_resolve_unit_metadata()` seam in `src/modular_simulation/gameplay/realtime_service.py` so gameplay can derive runtime-authoritative unit ports from `unit_blueprint` catalog metadata. Repo evidence shows that helper currently calls `_import_module(...)`, `getattr(...)`, and `unit_cls(**constructor_payload)` before `_install_unit()` enters its existing `try/except SandboxRequestError` translation block.

That means invalid `unit_blueprint` metadata can currently leak raw `ModuleNotFoundError`, `AttributeError`, `TypeError`, or other constructor-time exceptions through the gameplay layer instead of failing with the stable `SandboxRequestError` surface already frozen for invalid build configuration. The Beads item `ModularSimulator-9tr.2` explicitly narrows scope to hardening this metadata-resolution boundary without widening public contracts.

Without this pack, future catalog or staging mistakes in runtime-authoritative unit metadata can escape as unstable internal exceptions, undermining the stable gameplay/API error surface.

## What Changes

- Harden the gameplay build path around the module-private runtime-authoritative unit metadata seam so invalid `unit_blueprint` metadata resolution failures are translated into stable gameplay request errors.
- Freeze the failure classes in scope for translation at this boundary:
  - missing configured `unit_module` target resolution,
  - missing configured exported `unit_type` on the resolved module,
  - constructor-payload signature/validation failures while instantiating the unit for port derivation.
- Keep the translated public error surface narrow:
  - use the existing `SandboxRequestError(error_code="invalid_config", ...)` family for invalid metadata-driven build failures,
  - preserve stable JSON `{error_code, message}` and existing HTTP `400` semantics,
  - do not add new public error codes, routes, snapshot fields, or service methods.
- Add focused regression coverage for dependency-point failures exercised through the realtime build path and HTTP bridge.

## Capabilities

### Modified Capabilities
- `session`
- `units-and-components`
- `client-godot`

## Impact

- Affected code:
  - `src/modular_simulation/gameplay/realtime_service.py`
  - `src/modular_simulation/app/game_api.py` only if implementation needs a minimal assertion/update to preserve existing HTTP 400 mapping; otherwise no code change required there
- Affected tests:
  - `tests/gameplay/test_realtime_game_service.py`
  - `tests/app/test_game_api.py`
- Affected OpenSpec sync surfaces after implementation:
  - `openspec/changes/harden-unit-metadata-error-translation/specs/session/spec.md`
  - `openspec/changes/harden-unit-metadata-error-translation/specs/units-and-components/spec.md`
  - `openspec/changes/harden-unit-metadata-error-translation/specs/client-godot/spec.md`
  - `openspec/specs/session/spec.md`
  - `openspec/specs/units-and-components/spec.md`
  - `openspec/specs/client-godot/spec.md`

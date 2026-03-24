## Context

- `src/modular_simulation/gameplay/realtime_service.py` defines module-private `_resolve_unit_metadata(item)` that extracts `unit_module`, `unit_type`, and `constructor_payload` from a `SandboxCatalogItemDefinition`, then imports the unit class and instantiates it to read `.ports`.
- `_install_unit()` currently calls `_resolve_unit_metadata(item)` before entering the `try/except` block that translates downstream `network.add_process(...)` and `compile()` failures into `SandboxRequestError(error_code="invalid_config", ...)`.
- Live session spec already freezes `invalid_config` as the stable gameplay error family for invalid install requests.
- Live client-godot spec already freezes stable JSON `{error_code, message}` payloads and HTTP `400` semantics for invalid request/item/config failures.
- The existing units-and-components spec freezes `_resolve_unit_metadata()` as the runtime-authoritative proof seam for `unit_blueprint` metadata, but it does not yet freeze how invalid metadata-resolution failures are translated.

## Goals / Non-Goals

**Goals**
- Ensure invalid runtime-authoritative unit metadata fails through the stable gameplay error surface rather than leaking raw Python exceptions from the build path.
- Freeze the translation boundary tightly around metadata resolution used by `_install_unit()`.
- Add verification that covers build/API-level regression cases at the exact caller boundary.

**Non-Goals**
- Widen the public buildable item set, start allowlists, or session/API method set.
- Add new public error codes for module-not-found vs type-not-found vs bad-constructor distinctions.
- Change the runtime-authoritative metadata ownership model introduced in `4fm`.
- Change tank semantics, observability ownership, or any `ej7.1` work.
- Introduce broad catch-all masking of unrelated runtime failures beyond the metadata-resolution seam.

## Decisions

1. **`_install_unit()` is the explicit translation boundary.**
   - `_resolve_unit_metadata()` remains a module-private runtime-authoritative helper.
   - This pack does **not** freeze direct helper-call behavior as a public or semi-public contract.
   - The required behavior is that build-path callers, led by `_install_unit()`, translate qualifying metadata-resolution failures into the stable gameplay error surface.

2. **Metadata-resolution failures translate to the existing `invalid_config` surface.**
   - Failures while resolving runtime-authoritative metadata for a `unit_blueprint` build request are treated as invalid build configuration.
   - The public failure stays `SandboxRequestError(error_code="invalid_config", message=...)`.
   - HTTP behavior stays on the existing invalid-request path: JSON `{error_code, message}` with status `400`.

3. **Translation scope is narrow and seam-local.**
   - The implementation should translate failures arising from:
     - missing configured `unit_module` target resolution,
     - missing configured `unit_type` lookup on the resolved module,
     - constructor-payload signature or validation failures attributable to `unit_cls(**constructor_payload)` during port derivation.
   - The pack should not require blanket swallowing of every possible exception in unrelated topology compile, ledger, or session flows.
   - The pack also should not be read as requiring blanket masking of arbitrary import-time side-effect failures inside otherwise valid modules.
   - Exception chaining should be preserved (`raise ... from exc`) so internal debugging fidelity remains available without leaking raw exceptions to the public API.

4. **The helper seam remains module-private and runtime-authoritative.**
   - `_resolve_unit_metadata()` stays the exact proof seam already frozen in repo tests/specs.
   - This pack hardens failure translation around the caller boundary for that seam; it does not replace it with a separate registry or new public helper.

5. **Regression coverage must prove two layers.**
   - **Realtime build-path coverage** in `tests/gameplay/test_realtime_game_service.py`:
     - when dependency-point failures are induced under `_resolve_unit_metadata()`, `RealtimeGameService.build(...)` / `_install_unit()` returns stable gameplay errors instead of raw exceptions.
   - **HTTP bridge coverage** in `tests/app/test_game_api.py`:
     - the same invalid metadata build rejection still produces stable JSON `{error_code, message}` with HTTP `400`.

6. **Public contract text changes should stay minimal and explicit.**
   - `session` delta spec should add the missing scenario that invalid install requests include runtime-authoritative metadata-resolution failures.
   - `units-and-components` delta spec should add the requirement that invalid runtime-authoritative metadata resolution fails through stable gameplay error translation.
   - `client-godot` delta spec should add the matching HTTP scenario that invalid metadata-driven build requests stay on the stable error JSON / HTTP `400` path.

## Risks / Trade-offs

- **Over-catching could mask unrelated defects.**
  - Mitigation: scope translation explicitly to metadata resolution used by `_install_unit()` and keep tests focused on import/lookup/constructor failure classes.
- **There is no currently exposed live build item that naturally triggers metadata-resolution failure through HTTP.**
  - Mitigation: use targeted patch/spies in gameplay/API tests so the regression remains narrow and does not require widening the playable slice.

## Verification Strategy

- TDD should lead the new regression cases before implementation changes.
- Required verification for implementation:
  - `uv run pytest tests/gameplay/test_realtime_game_service.py -k "resolve_unit_metadata or invalid_config"`
  - `uv run pytest tests/app/test_game_api.py -k "stable_error or invalid_config or build"`
  - `uv run pytest tests/gameplay/test_realtime_game_service.py`
  - `uv run pytest tests/app/test_game_api.py`
- Expected evidence:
  - invalid import/lookup/constructor failures during `_resolve_unit_metadata()` no longer leak raw Python exceptions,
  - gameplay build requests reject those failures with `SandboxRequestError(error_code="invalid_config", ...)`,
  - HTTP build requests surface the same failures as stable JSON `{error_code, message}` with status `400`,
  - no public routes, build-item allowlists, snapshots, or error-code families widen.

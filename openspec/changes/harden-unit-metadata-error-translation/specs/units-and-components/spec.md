## ADDED Requirements

### Requirement: Runtime-Authoritative Add-Process Metadata Fails Through Stable Gameplay Errors
Phase-1 gameplay SHALL translate invalid runtime-authoritative metadata resolution for `unit_blueprint` records with `apply_kind = "add_process"` into stable gameplay request errors instead of leaking raw Python import, lookup, or constructor exceptions.

#### Scenario: Runtime-authoritative metadata resolution stays on the stable gameplay error surface
- **WHEN** the gameplay build path uses the module-private helper in `src/modular_simulation/gameplay/realtime_service.py` to resolve cataloged `add_process` unit metadata and encounters missing configured module-target resolution, missing configured exported unit type, or constructor-payload validation failure
- **THEN** the gameplay layer fails the request with `SandboxRequestError(error_code="invalid_config", ...)`
- **AND** the helper remains module-private and runtime-authoritative rather than introducing a second public metadata surface

#### Scenario: Stable metadata failure translation does not widen the live slice
- **WHEN** contributors inspect the invalid-metadata hardening for `add_process` unit blueprints
- **THEN** no new public build items, start allowlists, session methods, or error-code families are introduced by that hardening

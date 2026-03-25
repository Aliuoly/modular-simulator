## ADDED Requirements

### Requirement: Invalid Install Requests Include Metadata-Resolution Failures
Phase-1 gameplay SHALL treat invalid runtime-authoritative unit metadata resolution during realtime build placement as an `invalid_config` request failure rather than leaking raw internal exceptions.

#### Scenario: Invalid unit metadata import fails as invalid_config
- **WHEN** a build request targets a `unit_blueprint` record whose configured `unit_module` target cannot be resolved during runtime-authoritative metadata resolution
- **THEN** the session/gameplay layer raises `SandboxRequestError(error_code="invalid_config", ...)`
- **AND** the failure does not escape as a raw module-target resolution exception to callers

#### Scenario: Invalid unit metadata type lookup fails as invalid_config
- **WHEN** a build request targets a `unit_blueprint` record whose configured `unit_type` is missing from the imported module during runtime-authoritative metadata resolution
- **THEN** the session/gameplay layer raises `SandboxRequestError(error_code="invalid_config", ...)`
- **AND** the failure does not escape as a raw attribute lookup exception to callers

#### Scenario: Invalid constructor payload fails as invalid_config
- **WHEN** a build request targets a `unit_blueprint` record whose `constructor_payload` causes constructor-time validation failure while deriving declared ports
- **THEN** the session/gameplay layer raises `SandboxRequestError(error_code="invalid_config", ...)`
- **AND** the failure does not escape as a raw constructor exception to callers

## ADDED Requirements

### Requirement: Invalid Metadata-Driven Build Requests Preserve Stable HTTP Errors
The playable-slice HTTP bridge SHALL translate invalid runtime-authoritative unit metadata failures for build requests into the existing stable JSON error payload and invalid-request status path.

#### Scenario: Invalid metadata-driven build request returns stable JSON and HTTP 400
- **WHEN** a build request reaches the gameplay layer and runtime-authoritative unit metadata resolution fails because the configured module, unit type, or constructor payload is invalid
- **THEN** the HTTP bridge responds with JSON `{error_code: "invalid_config", message: ...}`
- **AND** the response status is HTTP `400`

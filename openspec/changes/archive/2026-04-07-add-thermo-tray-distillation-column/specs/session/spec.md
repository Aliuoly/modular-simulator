## MODIFIED Requirements

### Requirement: Dynamic Distillation Session Semantics Allow Approved Backend Runtime Paths
Session-level expectations SHALL treat `StagewiseDistillationColumn` and backend-only `ThermoTrayDistillationColumn` as supported dynamic distillation runtime behavior paths and SHALL NOT depend on a `ShortcutDistillation` compatibility route.

#### Scenario: Dynamic behavior contract may be satisfied by the thermo-backed tray path without widening public exposure
- **WHEN** a contributor evaluates whether backend dynamic-distillation runtime behavior is available after this change
- **THEN** completion may use `StagewiseDistillationColumn` or `ThermoTrayDistillationColumn` runtime behavior on the existing generic substrate/session/runtime surfaces
- **AND** no `ShortcutDistillation` runtime/shim pathway is part of completion criteria
- **AND** current topology-only starts and public build surfaces remain gated exactly as before.

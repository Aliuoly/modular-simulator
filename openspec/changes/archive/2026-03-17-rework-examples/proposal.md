## Why

The current examples catalog is too large and inconsistent, which makes it hard for users to identify canonical usage patterns for this simulator. We need a smaller, intentional set of examples that highlight recognized process patterns and consistently demonstrate flowsheet-first modeling.

## What Changes

- Reduce the examples catalog to a curated subset of high-signal examples that represent core repository capabilities.
- Standardize retained examples on the flowsheet style: boundary feed streams attach to process ports, unit processes are connected through explicit connections, terminal product handoff is documented consistently with the current high-level flowsheet API, and control elements are placed on required edges.
- Enforce architectural consistency in examples by eliminating unit-level actuators and keeping unit process state internal-only.
- Update example-facing documentation and run entrypoints so the curated set is easy to discover and execute.
- Correct review-discovered faults in shared calculation semantics, curated example wording, and automated verification/CI coverage.

## Capabilities

### New Capabilities
- `curated-flowsheet-examples`: Define and maintain a canonical, compact set of examples that follow strict flowsheet and control-placement conventions.

### Modified Capabilities
- None.

## Impact

- Affected code: `examples/` subtree (example definitions, helper scripts, and related assets).
- Affected docs: README or example index references that enumerate supported demos.
- Runtime/API impact: no engine API changes expected; this is primarily an example-library quality and consistency change, so the canonical examples must align with the current high-level flowsheet helpers instead of assuming new boundary-sink helpers.

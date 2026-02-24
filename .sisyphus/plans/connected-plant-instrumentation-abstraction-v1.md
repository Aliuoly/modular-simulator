# Connected Plant Instrumentation Abstraction (V1)

## TL;DR
> **Summary**: Introduce a connected-plant orchestration abstraction that supports subsystem-scoped sensor/controller installation, plant-scoped calculations, and deferred hot-install while the plant is running via queue-at-runtime and barrier-commit semantics.
> **Deliverables**:
> - New scoped installation API (subsystem + plant scopes)
> - Thin connected-plant orchestrator integrating subsystem runtime with connection runtime
> - Break-and-replace migration path and updated two-tank connection example
> - Regression and new-feature tests proving sequencing, hot-install determinism, collision handling, and failure behavior
> **Effort**: Large
> **Parallel**: YES - 3 waves
> **Critical Path**: Task 1 -> Task 2 -> Task 4 -> Task 8 -> Task 9 -> Task 12

## Context
### Original Request
Abstract controller and sensor installation to either the entire connected system or subsystem level, and support calculations at whole-system scope.

### Interview Summary
- V1 scope is subsystem-first for sensor/controller installation.
- Backward compatibility is break-and-replace for this release.
- Calculations are included in this wave but remain plant-scoped (cross-subsystem inputs allowed through published measurements).
- Test strategy is tests-after.

### Metis Review (gaps addressed)
- Added explicit deterministic phase-order contract so control behavior does not drift.
- Added strict tag namespace/collision guardrails.
- Limited v1 scope to installer abstraction + thin orchestrator (no plugin-framework rewrite).
- Replaced install-time-only guardrail with deferred hot-install contract: enqueue allowed while running, apply only at next barrier.
- Added explicit compatibility boundary assumptions for runtime behavior vs serialization.

## Work Objectives
### Core Objective
Deliver a single abstraction layer that allows subsystem-level sensor/controller installation and plant-level calculation installation for connected process systems, without requiring manual per-step wiring in example-level code.

### Deliverables
- Connected plant orchestration API and runtime sequencing contract.
- Subsystem abstraction object exposing local installation methods.
- Plant abstraction object exposing cross-subsystem calculation installation.
- Namespacing and collision policy for cross-subsystem measurement tags.
- Upgraded two-tank connection example using the new abstraction.
- Automated tests for behavior parity, edge cases, and failure modes.

### Definition of Done (verifiable conditions with commands)
- `pytest -q tests/test_system.py tests/test_components.py`
- `pytest -q tests/connection/test_connection_runtime_sequence.py tests/connection/test_process_binding.py`
- `pytest -q tests/connection/test_two_tank_reaction_comparison.py`
- `pytest -q tests/connection/test_runtime_mutation_contract.py tests/connection/test_runtime_persistence_contract.py`
- `pytest -q tests -k "connected plant or subsystem installer or tag collision"`
- `python examples/connection_layer/two_tank_reaction_comparison.py --no-show`

### Must Have
- Deterministic macro-step sequencing with explicit phase order contract.
- Subsystem-scoped sensor/controller install API.
- Plant-scoped calculation install API using published subsystem measurements.
- Hot-install contract: enqueue while running is allowed, visibility is next-barrier only.
- Idempotency conflict policy: same `idempotency_key` with different payload is rejected with no state change.
- Poison-request policy: strict block at queue head until fixed/removed via explicit maintenance path.
- Fail-fast tag collision behavior across subsystem namespaces.
- Break-and-replace migration notes and clear error messaging for deprecated pathways.

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- No immediate same-step apply for newly queued installs.
- No asynchronous out-of-barrier apply path.
- No implicit last-writer-wins tag policy.
- No hidden behavioral drift in connection runtime sequencing.
- No broad rewrite of existing sensor/controller/calculation internals beyond required adapters.
- No scope expansion into generic plugin/DI framework.

## Verification Strategy
> ZERO HUMAN INTERVENTION - all verification is agent-executed.
- Test decision: tests-after with pytest.
- QA policy: Every task includes happy-path and failure/edge QA scenarios.
- Evidence: `.sisyphus/evidence/task-{N}-{slug}.txt` and `.sisyphus/evidence/task-{N}-{slug}-error.txt`.

## Execution Strategy
### Parallel Execution Waves
> Target: 5-8 tasks per wave. Shared dependencies are extracted to Wave 1.

Wave 1: API and architecture foundation (Tasks 1-5)
Wave 2: installer/orchestrator integration and migration (Tasks 6-10)
Wave 3: validation hardening and docs completion (Tasks 11-14)

### Dependency Matrix (full, all tasks)
- Task 1 -> Blocks Tasks 4, 5, 6, 8
- Task 2 -> Blocks Tasks 6, 7, 11, 13
- Task 3 -> Blocks Tasks 4, 6, 8
- Task 4 -> Blocks Tasks 8, 9, 12
- Task 5 -> Blocks Tasks 9, 12
- Task 6 -> Blocks Tasks 7, 8, 10, 11
- Task 7 -> Blocks Tasks 8, 11, 13
- Task 8 -> Blocks Tasks 9, 12, 13
- Task 9 -> Blocks Task 14
- Task 10 -> Blocks Task 14
- Task 11 -> Blocks Final Verification
- Task 12 -> Blocks Final Verification
- Task 13 -> Blocks Final Verification
- Task 14 -> Blocks Final Verification

### Agent Dispatch Summary (wave -> task count -> categories)
- Wave 1 -> 5 tasks -> deep, unspecified-high, quick
- Wave 2 -> 5 tasks -> deep, unspecified-high, quick
- Wave 3 -> 4 tasks -> unspecified-high, writing, quick

## TODOs
> Implementation + Test = ONE task. Never separate.
> EVERY task includes Agent Profile, Parallelization, References, Acceptance Criteria, and QA Scenarios.
> Tasks are grouped by validation-first execution readability; follow task numbers and dependency matrix for actual execution order.


- [x] 13. Add Failure-Mode and Runtime-Barrier Regression Tests

  **What to do**: Add explicit tests for invalid scope usage, unresolved cross-subsystem references, deferred hot-install semantics (enqueue during run, next-barrier visibility), idempotency key payload mismatch rejection, strict-block poison-request behavior, and invalid connection binding interactions under the new abstraction.
  **Must NOT do**: Do not depend on flaky timing assertions; do not weaken existing strict-binding validations.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: high-value negative-path regression suite.
  - Skills: `[]` - no special skill required.
  - Omitted: [`playwright`] - backend simulation/runtime coverage.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: [Final Verification] | Blocked By: [2, 7, 8]

  **References** (executor has NO interview context - be exhaustive):
  - Test: `tests/connection/test_runtime_mutation_contract.py` - barrier and runtime mutation edge patterns.
  - Pattern: `src/modular_simulation/connection/runtime_persistence.py` - queue/idempotency persistence behavior.
  - Test: `tests/connection/test_runtime_persistence_contract.py` - snapshot queue-order and idempotency continuity expectations.
  - Test: `tests/connection/test_process_binding.py` - strict binding failure expectations.
  - Test: `tests/test_system.py` - grouped configuration error handling style.

  **Acceptance Criteria** (agent-executable only):
  - [ ] New failure-mode tests cover invalid scope, deferred hot-install visibility, idempotency mismatch rejection, and strict-block queue behavior.
  - [ ] Existing strict binding and barrier tests remain green.
  - [ ] `pytest -q tests/connection/test_runtime_mutation_contract.py tests/connection/test_runtime_persistence_contract.py` passes.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```text
  Scenario: Hot-install is deferred deterministically
    Tool: Bash
    Steps: Run `pytest -q tests/connection/test_runtime_mutation_contract.py -k "queued during macro step commits only at next barrier"`
    Expected: Command exits 0; tests confirm enqueue is accepted during run and effects are visible only at next barrier.
    Evidence: .sisyphus/evidence/task-13-failure-modes.txt

  Scenario: Idempotency mismatch and poison request are handled predictably
    Tool: Bash
    Steps: Run `pytest -q tests/connection/test_runtime_mutation_contract.py tests/connection/test_runtime_persistence_contract.py -k "idempotency or poison or unresolved reference"`
    Expected: Command exits 0; tests verify reject-on-mismatch, strict-block behavior, and deterministic failure handling.
    Evidence: .sisyphus/evidence/task-13-failure-modes-error.txt
  ```

  **Commit**: YES | Message: `test(connection): add failure-mode regressions for scoped abstraction` | Files: [`tests/connection/`, `tests/test_system.py`]

- [x] 14. Update Documentation and Example Guidance for New API

  **What to do**: Update user/developer docs and example guidance to reflect subsystem installers, plant calculations, naming policy, and break-and-replace migration path.
  **Must NOT do**: Do not leave legacy examples as implied recommended flow.

  **Recommended Agent Profile**:
  - Category: `writing` - Reason: documentation clarity and migration guidance.
  - Skills: `[]` - no special skill required.
  - Omitted: [`frontend-ui-ux`] - docs-only content.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: [Final Verification] | Blocked By: [9, 10]

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `readme.md` - architecture and workflow overview.
  - Pattern: `LLM_CONTEXT.md` - internal architecture mapping.
  - Example: `examples/connection_layer/two_tank_reaction_comparison.py` - migrated usage.
  - Test: `tests/connection/test_migration_hygiene_gate.py` - migration messaging expectations.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Docs describe subsystem install API, plant calculation API, and namespacing rules with runnable snippets.
  - [ ] Migration section explicitly lists replaced APIs and the new equivalents.
  - [ ] `pytest -q tests/connection/test_migration_hygiene_gate.py tests/connection/test_process_interface_adapter.py` passes after doc-linked examples are updated.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```text
  Scenario: New docs flow aligns with executable example
    Tool: Bash
    Steps: Run `python examples/connection_layer/two_tank_reaction_comparison.py --no-show`
    Expected: Command exits 0; doc-referenced command works.
    Evidence: .sisyphus/evidence/task-14-docs-migration.txt

  Scenario: Migration guidance matches enforced behavior
    Tool: Bash
    Steps: Run `pytest -q tests/connection/test_migration_hygiene_gate.py tests/connection/test_process_interface_adapter.py`
    Expected: Command exits 0; tests confirm migration guidance and break behavior align.
    Evidence: .sisyphus/evidence/task-14-docs-migration-error.txt
  ```

  **Commit**: YES | Message: `docs(connection): document scoped installers and migration path` | Files: [`readme.md`, `LLM_CONTEXT.md`, `examples/connection_layer/two_tank_reaction_comparison.py`, `tests/connection/`]

- [x] 9. Migrate Two-Tank Connection Example to New Abstraction

  **What to do**: Refactor `two_tank_reaction_comparison` example to use subsystem installation APIs and plant calculation APIs via connected-plant orchestrator instead of manual installer/binding wiring in script logic.
  **Must NOT do**: Do not change benchmark physics equations or comparison metrics.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: example migration on top of completed APIs.
  - Skills: `[]` - no special skill required.
  - Omitted: [`playwright`] - CLI/data output example.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: [14] | Blocked By: [4, 5, 8]

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `examples/connection_layer/two_tank_reaction_comparison.py` - current manual connection-loop logic and metrics.
  - Pattern: `src/modular_simulation/connection/network.py` - compile/binding interfaces.
  - Pattern: `src/modular_simulation/connection/process_binding.py` - strict port contracts.
  - Test: `tests/connection/test_two_tank_reaction_comparison.py` - expected benchmark behavior.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Example runs through new API and preserves comparison output structure.
  - [ ] Two-tank comparison tolerances remain within test thresholds.
  - [ ] `pytest -q tests/connection/test_two_tank_reaction_comparison.py` passes.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```text
  Scenario: Refactored example produces expected benchmark metrics
    Tool: Bash
    Steps: Run `python examples/connection_layer/two_tank_reaction_comparison.py --no-show`
    Expected: Command exits 0; metrics table and error outputs are printed.
    Evidence: .sisyphus/evidence/task-9-two-tank-migration.txt

  Scenario: Regression guard catches metric drift
    Tool: Bash
    Steps: Run `pytest -q tests/connection/test_two_tank_reaction_comparison.py`
    Expected: Command exits 0; tolerance/behavior assertions pass.
    Evidence: .sisyphus/evidence/task-9-two-tank-migration-error.txt
  ```

  **Commit**: YES | Message: `refactor(examples): migrate two-tank comparison to connected plant API` | Files: [`examples/connection_layer/two_tank_reaction_comparison.py`, `tests/connection/test_two_tank_reaction_comparison.py`]

- [x] 10. Add Break-and-Replace Migration Guardrails

  **What to do**: Add explicit migration guardrails for replaced APIs (clear exceptions/messages, migration notes, and controlled deprecation shims only where needed for diagnosability).
  **Must NOT do**: Do not preserve full backward-compatible behavior; do not leave silent behavior changes.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: compatibility boundary clarity and failure UX.
  - Skills: `[]` - no special skill required.
  - Omitted: [`frontend-ui-ux`] - non-UI path.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: [14] | Blocked By: [6]

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `src/modular_simulation/framework/system.py` - current constructor/validation error style.
  - Pattern: `src/modular_simulation/connection/process_interface.py` - prior hard-switch compatibility messaging style.
  - Test: `tests/connection/test_migration_hygiene_gate.py` - migration hygiene patterns.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Replaced API paths fail with actionable migration messages.
  - [ ] No ambiguous silent fallback paths remain.
  - [ ] `pytest -q tests/connection/test_migration_hygiene_gate.py tests/connection/test_process_interface_adapter.py` passes.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```text
  Scenario: Deprecated entrypoint emits migration guidance
    Tool: Bash
    Steps: Run `pytest -q tests/connection -k "migration guidance"`
    Expected: Command exits 0; tests assert explicit replacement instructions.
    Evidence: .sisyphus/evidence/task-10-migration-guardrails.txt

  Scenario: Legacy behavior is not silently accepted
    Tool: Bash
    Steps: Run `pytest -q tests/connection/test_migration_hygiene_gate.py tests/connection/test_process_interface_adapter.py`
    Expected: Command exits 0; tests confirm deterministic failure for unsupported legacy path.
    Evidence: .sisyphus/evidence/task-10-migration-guardrails-error.txt
  ```

  **Commit**: YES | Message: `refactor(connection): add break-and-replace migration guardrails` | Files: [`src/modular_simulation/connection/process_interface.py`, `src/modular_simulation/connection/`, `tests/connection/`]

- [x] 11. Add Unit Tests for Scoped Installers and Collision Rules

  **What to do**: Add focused unit tests covering subsystem installer contract, plant calculation registration rules, namespace resolution, and collision failures.
  **Must NOT do**: Do not rely only on broad integration tests; do not skip negative path coverage.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: concentrated test additions with clear scope.
  - Skills: `[]` - no special skill required.
  - Omitted: [`playwright`] - backend test work.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: [Final Verification] | Blocked By: [2, 6, 7]

  **References** (executor has NO interview context - be exhaustive):
  - Test: `tests/test_system.py` - component install validation patterns.
  - Test: `tests/test_components.py` - component behavior test style.
  - Test: `tests/connection/test_process_binding.py` - strict contract assertions.
  - Test: `tests/connection/test_connection_layer_sequence.py` - fixture and assertion style.

  **Acceptance Criteria** (agent-executable only):
  - [ ] New unit tests exist for each scope rule and collision edge case.
  - [ ] Test names and failure messages are explicit about scope and namespace policy.
  - [ ] `pytest -q tests -k "subsystem scoped installer or plant scoped calculation or tag collision"` passes.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```text
  Scenario: Scope rules validated at unit level
    Tool: Bash
    Steps: Run `pytest -q tests -k "subsystem scoped installer or plant scoped calculation"`
    Expected: Command exits 0; targeted unit tests pass.
    Evidence: .sisyphus/evidence/task-11-scoped-unit-tests.txt

  Scenario: Collision policy validated at unit level
    Tool: Bash
    Steps: Run `pytest -q tests -k "tag collision"`
    Expected: Command exits 0; collision negative tests pass.
    Evidence: .sisyphus/evidence/task-11-scoped-unit-tests-error.txt
  ```

  **Commit**: YES | Message: `test(connection): cover scoped installers and namespace collisions` | Files: [`tests/test_system.py`, `tests/test_components.py`, `tests/connection/`]

- [x] 12. Add Integration Tests for Sequencing and Behavior Parity

  **What to do**: Add/extend integration tests proving connected-plant sequencing and parity with expected two-tank behavior under new abstraction.
  **Must NOT do**: Do not reduce existing tolerance checks; do not remove deterministic bookkeeping assertions.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: integration correctness and regression risk.
  - Skills: `[]` - no special skill required.
  - Omitted: [`frontend-ui-ux`] - backend simulation tests.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: [Final Verification] | Blocked By: [4, 5, 8]

  **References** (executor has NO interview context - be exhaustive):
  - Test: `tests/connection/test_connection_runtime_sequence.py` - deterministic runtime order assertions.
  - Test: `tests/connection/test_connection_integration_physics.py` - integration physics patterns.
  - Test: `tests/connection/test_two_tank_reaction_comparison.py` - benchmark parity expectations.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Integration tests assert exact phase order under new connected-plant orchestration.
  - [ ] Two-tank comparison still meets existing max error and monotonicity expectations.
  - [ ] `pytest -q tests/connection/test_connection_runtime_sequence.py tests/connection/test_two_tank_reaction_comparison.py` passes.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```text
  Scenario: Sequencing parity validated
    Tool: Bash
    Steps: Run `pytest -q tests/connection/test_connection_runtime_sequence.py`
    Expected: Command exits 0; deterministic sequence and metadata checks pass.
    Evidence: .sisyphus/evidence/task-12-integration-sequencing.txt

  Scenario: Behavioral parity validated on benchmark
    Tool: Bash
    Steps: Run `pytest -q tests/connection/test_two_tank_reaction_comparison.py`
    Expected: Command exits 0; benchmark errors remain within expected bounds.
    Evidence: .sisyphus/evidence/task-12-integration-sequencing-error.txt
  ```

  **Commit**: YES | Message: `test(connection): add connected plant sequencing and parity integration tests` | Files: [`tests/connection/test_connection_runtime_sequence.py`, `tests/connection/test_two_tank_reaction_comparison.py`, `tests/connection/`]


- [x] 5. Implement Subsystem-Scoped Sensor and Controller Installation API

  **What to do**: Add subsystem methods for local installation (for example `subsystem.add_sensor(...)` and `subsystem.add_control_element(...)`) that validate tags against local published process view and wire to local registry context.
  **Must NOT do**: Do not permit plant-level side effects from subsystem installer calls; do not auto-create plant calculations here.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: touches controller/sensor installation wiring and validation semantics.
  - Skills: `[]` - no special skill required.
  - Omitted: [`playwright`] - backend-only behavior.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: [9, 12] | Blocked By: [1]

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `src/modular_simulation/components/sensors/abstract_sensor.py` - sensor install and measurement tag resolution.
  - Pattern: `src/modular_simulation/components/control_system/abstract_controller.py` - controller install and CV resolution.
  - Pattern: `src/modular_simulation/framework/system.py` - current resolver/error semantics.
  - Test: `tests/test_system.py` - sensor/controller configuration failure expectations.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Subsystem sensor/controller install validates local tags and emits deterministic configuration errors.
  - [ ] Installed local components update during subsystem phase without manual script wiring.
  - [ ] `pytest -q tests -k "subsystem scoped installer and sensor or controller"` passes.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```text
  Scenario: Subsystem installs sensor/controller and updates values
    Tool: Bash
    Steps: Run `pytest -q tests -k "subsystem scoped installer and happy path"`
    Expected: Command exits 0; local install and update order tests pass.
    Evidence: .sisyphus/evidence/task-5-subsystem-installers.txt

  Scenario: Invalid local tag rejected
    Tool: Bash
    Steps: Run `pytest -q tests -k "subsystem scoped installer and invalid tag"`
    Expected: Command exits 0; tests assert explicit configuration error and message.
    Evidence: .sisyphus/evidence/task-5-subsystem-installers-error.txt
  ```

  **Commit**: YES | Message: `feat(connection): add subsystem-scoped sensor controller installers` | Files: [`src/modular_simulation/components/sensors/`, `src/modular_simulation/components/control_system/`, `tests/test_system.py`, `tests/connection/`]

- [x] 6. Implement Plant-Scoped Calculation Installation API

  **What to do**: Add plant-level calculation installer (for example `connected_plant.add_calculation(...)`) that resolves inputs only from published subsystem measurements and existing plant calculations.
  **Must NOT do**: Do not allow direct raw process-state reads bypassing publication map in v1; do not attach plant calculations to a single subsystem scope.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: defines cross-subsystem calculation semantics and dependency resolution.
  - Skills: `[]` - no special skill required.
  - Omitted: [`frontend-ui-ux`] - no UI.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: [7, 8, 10, 11] | Blocked By: [1, 2, 3]

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `src/modular_simulation/components/calculations/abstract_calculation.py` - install flow and iterative dependency behavior.
  - Pattern: `src/modular_simulation/framework/system.py` - calculation install order and unresolved calculation handling.
  - Pattern: `examples/simplified_gas_phase_system/component_definition.py` - controller use of calculation outputs.
  - Test: `tests/test_system.py` - calculation commissioning expectations.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Plant-scoped calculations install and resolve dependencies across published subsystem tags.
  - [ ] Unresolvable plant calculation dependencies fail with deterministic grouped errors.
  - [ ] `pytest -q tests -k "plant scoped calculation"` passes.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```text
  Scenario: Cross-subsystem plant calculation resolves
    Tool: Bash
    Steps: Run `pytest -q tests -k "plant scoped calculation and cross subsystem"`
    Expected: Command exits 0; output tag values are produced and available to controllers.
    Evidence: .sisyphus/evidence/task-6-plant-calculations.txt

  Scenario: Missing published input fails commissioning
    Tool: Bash
    Steps: Run `pytest -q tests -k "plant scoped calculation and missing input"`
    Expected: Command exits 0; tests assert calculation configuration failure.
    Evidence: .sisyphus/evidence/task-6-plant-calculations-error.txt
  ```

  **Commit**: YES | Message: `feat(connection): add plant-scoped calculation installer` | Files: [`src/modular_simulation/components/calculations/`, `src/modular_simulation/connection/`, `tests/test_system.py`, `tests/connection/`]

- [x] 7. Build Publication Adapter Between Subsystems and Plant Registry

  **What to do**: Implement adapter logic that publishes selected subsystem points into plant scope using namespace policy and unit-safe value retrieval for plant calculations.
  **Must NOT do**: Do not duplicate full point registries per tick; do not silently coerce incompatible units.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: data-contract bridge with validation and conversion semantics.
  - Skills: `[]` - no special skill required.
  - Omitted: [`playwright`] - non-browser work.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: [8, 11, 13] | Blocked By: [2, 6]

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `src/modular_simulation/components/point/point_registry.py` - conversion getter behavior and point lookup semantics.
  - Pattern: `src/modular_simulation/components/point/point.py` - point data model.
  - Pattern: `src/modular_simulation/components/point/point.py` - `DataValue` value/time/ok semantics.
  - Test: `tests/test_components.py` - conversion and component-output expectations.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Plant publication adapter exposes namespaced measurement points from all configured subsystems.
  - [ ] Unit mismatch raises explicit error unless conversion path exists.
  - [ ] `pytest -q tests -k "publication adapter"` passes.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```text
  Scenario: Published measurements available for plant calculations
    Tool: Bash
    Steps: Run `pytest -q tests -k "publication adapter and happy path"`
    Expected: Command exits 0; plant getter retrieves converted values from subsystem outputs.
    Evidence: .sisyphus/evidence/task-7-publication-adapter.txt

  Scenario: Unit incompatibility rejected
    Tool: Bash
    Steps: Run `pytest -q tests -k "publication adapter and unit mismatch"`
    Expected: Command exits 0; tests verify explicit conversion/configuration error.
    Evidence: .sisyphus/evidence/task-7-publication-adapter-error.txt
  ```

  **Commit**: YES | Message: `feat(connection): add subsystem publication adapter for plant scope` | Files: [`src/modular_simulation/components/point/`, `src/modular_simulation/connection/`, `tests/connection/`]

- [x] 8. Integrate Full Connected-Plant Step Sequencing

  **What to do**: Implement the final per-step orchestration sequence combining subsystem updates, plant calculations, controller actions, process stepping, and connection runtime coupling exactly per Task 1 contract.
  **Must NOT do**: Do not reorder phases opportunistically; do not skip barrier checks; do not make queued changes visible in the same macro-step they were queued.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: highest risk behavior integration.
  - Skills: `[]` - no special skill required.
  - Omitted: [`frontend-ui-ux`] - backend control/runtime concern.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: [9, 12, 13] | Blocked By: [1, 3, 4, 6, 7]

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `src/modular_simulation/framework/system.py` - existing update/step ordering semantics.
  - Pattern: `src/modular_simulation/connection/runtime.py` - macro-step and reconfiguration barrier.
  - Test: `tests/connection/test_connection_runtime_sequence.py` - deterministic sequence expectations.
  - Test: `tests/connection/test_transport_runtime.py` - runtime coupling side effects.

  **Acceptance Criteria** (agent-executable only):
  - [ ] End-to-end connected-plant step follows documented phase order exactly.
  - [ ] Existing connection runtime sequencing tests remain green.
  - [ ] `pytest -q tests/connection/test_connection_runtime_sequence.py tests/connection/test_transport_runtime.py` passes.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```text
  Scenario: Deterministic phase order preserved
    Tool: Bash
    Steps: Run `pytest -q tests/connection/test_connection_runtime_sequence.py`
    Expected: Command exits 0; no sequencing regressions.
    Evidence: .sisyphus/evidence/task-8-step-sequencing.txt

  Scenario: Deferred hot-install visibility is enforced
    Tool: Bash
    Steps: Run `pytest -q tests/connection/test_runtime_mutation_contract.py -k "queued during macro step commits only at next barrier"`
    Expected: Command exits 0; mutation queue accepts runtime requests but apply happens only at barrier.
    Evidence: .sisyphus/evidence/task-8-step-sequencing-error.txt
  ```

  **Commit**: YES | Message: `feat(connection): integrate connected plant macro-step sequencing` | Files: [`src/modular_simulation/connection/runtime.py`, `src/modular_simulation/framework/system.py`, `tests/connection/`]


- [x] 1. Freeze V1 Scope and Phase-Order Contract

  **What to do**: Define the authoritative sequencing contract for connected-plant execution (subsystem sensor update -> subsystem calculations -> plant calculations -> subsystem controllers -> process stepping -> connection runtime coupling), codify compatibility boundary (break-and-replace API, runtime behavior preserved, legacy serialization compatibility not guaranteed in v1), and formalize hot-install state machine (`Queued` -> `Staged` -> `Applied` | `Skipped` | `RolledBack`) with deterministic FIFO ordering.
  **Must NOT do**: Do not implement new runtime behavior in this task; do not leave ordering implicit.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: architecture contract decisions affect all downstream tasks.
  - Skills: `[]` - no special skill required.
  - Omitted: [`frontend-ui-ux`] - no UI work.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: [2, 4, 5, 6, 8] | Blocked By: []

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `src/modular_simulation/framework/system.py` - current component install/update order.
  - Pattern: `src/modular_simulation/connection/runtime.py` - macro-step orchestration and mutation barrier behavior.
  - API/Type: `src/modular_simulation/components/abstract_component.py` - install lifecycle contract.
  - Test: `tests/connection/test_connection_runtime_sequence.py` - deterministic sequencing baseline.

  **Acceptance Criteria** (agent-executable only):
  - [ ] New architecture contract doc and inline developer notes exist and are referenced by implementation modules.
  - [ ] Contract explicitly defines: next-barrier visibility, idempotency mismatch rejection, and strict-block poison-request policy.
  - [ ] `pytest -q tests/connection/test_connection_runtime_sequence.py` passes.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```text
  Scenario: Contract baseline preserved
    Tool: Bash
    Steps: Run `pytest -q tests/connection/test_connection_runtime_sequence.py`
    Expected: Command exits 0; deterministic sequence tests pass.
    Evidence: .sisyphus/evidence/task-1-phase-order-contract.txt

  Scenario: Contract policy enforcement exists
    Tool: Bash
    Steps: Run `pytest -q tests/connection/test_runtime_mutation_contract.py -k "deterministic and idempotent by key"`
    Expected: Command exits 0; contract policies for ordering/idempotency are enforced.
    Evidence: .sisyphus/evidence/task-1-phase-order-contract-error.txt
  ```

  **Commit**: YES | Message: `feat(connection): define connected-plant phase order contract` | Files: [`src/modular_simulation/connection/runtime.py`, `src/modular_simulation/framework/system.py`, `tests/connection/test_connection_runtime_sequence.py`]

- [x] 2. Add Subsystem Namespace and Tag Collision Policy

  **What to do**: Introduce deterministic subsystem namespacing for published measurement tags and enforce hard-error collision checks at registration time.
  **Must NOT do**: Do not use last-writer-wins behavior; do not silently rewrite conflicting tags.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: cross-cutting registry and validation logic.
  - Skills: `[]` - no special skill required.
  - Omitted: [`playwright`] - non-browser backend task.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: [6, 7, 11, 13] | Blocked By: [1]

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `src/modular_simulation/components/point/point_registry.py` - point/tag registration constraints.
  - Pattern: `src/modular_simulation/framework/system.py` - how points are currently registered for components.
  - Test: `tests/test_system.py` - existing configuration error patterns.
  - Test: `tests/connection/test_process_binding.py` - strict validation style.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Duplicate published tags across subsystems raise explicit configuration errors.
  - [ ] Namespaced tags resolve consistently in plant-scoped calculations.
  - [ ] `pytest -q tests -k "tag collision or namespace"` passes.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```text
  Scenario: Unique namespaces register cleanly
    Tool: Bash
    Steps: Run `pytest -q tests -k "namespace registration"`
    Expected: Command exits 0; namespace registration tests pass.
    Evidence: .sisyphus/evidence/task-2-namespace-collision.txt

  Scenario: Duplicate tag fails fast
    Tool: Bash
    Steps: Run `pytest -q tests -k "tag collision"`
    Expected: Command exits 0; collision tests assert explicit error type/message.
    Evidence: .sisyphus/evidence/task-2-namespace-collision-error.txt
  ```

  **Commit**: YES | Message: `feat(connection): enforce subsystem tag namespace collisions` | Files: [`src/modular_simulation/components/point/point_registry.py`, `tests/test_system.py`, `tests/connection/test_process_binding.py`]

- [x] 3. Introduce Subsystem Runtime Descriptor

  **What to do**: Create a lightweight subsystem descriptor object that binds process identity, local process model/runtime context, declared ports, and published measurement map for installer use.
  **Must NOT do**: Do not duplicate full `System` internals; do not alter process physics.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: focused new abstraction object and validations.
  - Skills: `[]` - no special skill required.
  - Omitted: [`git-master`] - no git-history operation needed.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: [4, 6, 8] | Blocked By: [1]

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `src/modular_simulation/connection/network.py` - process identity and port declarations.
  - Pattern: `src/modular_simulation/connection/process_binding.py` - inlet/outlet strictness model.
  - Pattern: `examples/connection_layer/two_tank_reaction_comparison.py` - current manual per-process wiring data needed by descriptor.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Subsystem descriptor validates required ids/ports/publication fields.
  - [ ] Descriptor integrates with process binding lookup for connected examples.
  - [ ] `pytest -q tests/connection -k "subsystem descriptor"` passes.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```text
  Scenario: Valid subsystem descriptor accepted
    Tool: Bash
    Steps: Run `pytest -q tests/connection -k "subsystem descriptor and valid"`
    Expected: Command exits 0; valid descriptor tests pass.
    Evidence: .sisyphus/evidence/task-3-subsystem-descriptor.txt

  Scenario: Missing port metadata rejected
    Tool: Bash
    Steps: Run `pytest -q tests/connection -k "subsystem descriptor and missing port"`
    Expected: Command exits 0; tests confirm deterministic configuration failure.
    Evidence: .sisyphus/evidence/task-3-subsystem-descriptor-error.txt
  ```

  **Commit**: YES | Message: `feat(connection): add subsystem runtime descriptor` | Files: [`src/modular_simulation/connection/network.py`, `src/modular_simulation/connection/process_binding.py`, `tests/connection/`]

- [x] 4. Create Connected Plant Orchestrator Skeleton

  **What to do**: Add a thin connected-plant orchestration class that composes subsystem descriptors and `ConnectionRuntimeOrchestrator`, with explicit phase hooks but no advanced business logic yet.
  **Must NOT do**: Do not bypass runtime mutation barriers; do not apply newly queued installs inside active macro-step.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: central integration seam across orchestration domains.
  - Skills: `[]` - no special skill required.
  - Omitted: [`frontend-ui-ux`] - non-UI architecture task.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: [8, 9, 12] | Blocked By: [1, 3]

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `src/modular_simulation/connection/runtime.py` - runtime step, snapshot, and barrier semantics.
  - Pattern: `src/modular_simulation/framework/system.py` - component lifecycle and update sequencing.
  - Test: `tests/connection/test_connection_runtime_sequence.py` - sequencing assertions to preserve.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Connected plant orchestrator can initialize with multiple subsystems and compiled connection network.
  - [ ] Runtime can enqueue install requests while running, with apply deferred to barrier commit points.
  - [ ] `pytest -q tests/connection -k "connected plant orchestrator and init"` passes.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```text
  Scenario: Orchestrator initializes and performs one macro step
    Tool: Bash
    Steps: Run `pytest -q tests/connection -k "connected plant orchestrator and macro step"`
    Expected: Command exits 0; step bookkeeping and graph revision checks pass.
    Evidence: .sisyphus/evidence/task-4-plant-orchestrator.txt

  Scenario: Runtime install enqueue allowed but deferred
    Tool: Bash
    Steps: Run `pytest -q tests/connection -k "connected plant orchestrator and runtime enqueue"`
    Expected: Command exits 0; tests confirm enqueue accepted during run and committed at barrier.
    Evidence: .sisyphus/evidence/task-4-plant-orchestrator-error.txt
  ```

  **Commit**: YES | Message: `feat(connection): introduce connected plant orchestrator skeleton` | Files: [`src/modular_simulation/connection/runtime.py`, `src/modular_simulation/connection/`, `tests/connection/`]


## Final Verification Wave (4 parallel agents, ALL must APPROVE)
- [x] F1. Plan Compliance Audit - oracle
- [x] F2. Code Quality Review - unspecified-high
- [x] F3. Real Manual QA - unspecified-high (+ playwright if UI)
- [x] F4. Scope Fidelity Check - deep

## Commit Strategy
- Use atomic commits per task cluster (foundation, integration, tests/docs).
- Enforce Conventional Commit style: `feat(connection): ...`, `refactor(system): ...`, `test(connection): ...`, `docs(connection): ...`.
- Do not amend previous commits; create follow-up commits for hook-driven changes.

## Success Criteria
- New abstraction removes manual installer boilerplate from connected examples.
- Subsystem sensors/controllers and plant calculations can be installed declaratively, including runtime hot-install through deferred barrier-commit workflow.
- Deterministic sequencing and runtime contracts remain stable under existing and new tests.
- Failure modes (tag collisions, unresolved references, invalid scope use) fail fast with actionable errors.

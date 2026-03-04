# Dynamic Simulation API and CLI Foundation

## TL;DR
> **Summary**: Build a deterministic command-driven backend and hybrid CLI for runtime topology/control edits, with same-version checkpoint resume and strict atomicity guarantees for game-loop reliability.
> **Deliverables**:
> - Transactional dynamic-reconfiguration API with invariant validation and deterministic tick-boundary apply
> - Resistance/valve/sensor/controller configuration model aligned with existing connection runtime
> - Same-version snapshot+journal persistence with replay determinism checks
> - Hybrid CLI (`commands` + `spec diff/apply`) mapped 1:1 to backend command contracts
> - Pytest+ruff+mypy+CI baseline and contract/integration coverage for failure paths
> **Effort**: XL
> **Parallel**: YES - 3 waves
> **Critical Path**: Task 1 -> Task 2 -> Task 4 -> Task 7 -> Task 11 -> Task 13 -> Task 17

## Context
### Original Request
Create a clean, efficient, reliable backend API for dynamic process-network editing (inlets/outlets, unit processes, junctions, line resistance, control valves, sensors, controllers/calculations), plus save/load continuation and an intuitive low-boilerplate CLI for game-backend usage.

### Interview Summary
- User confirmed dynamic topology/control/persistence scope and emphasized KISS design.
- User selected test baseline: `pytest + ruff + mypy + CI`.
- User selected resistance behavior: geometry-derived default with manual override.
- User selected CLI style: hybrid commands and spec-file workflow.
- User selected persistence compatibility: same-version guarantees for now; cross-version migration deferred.

### Metis Review (gaps addressed)
- Preserved existing deterministic runtime semantics: queued mutations, FIFO, tick-boundary apply, idempotency conflict handling.
- Added explicit destructive-edit policy matrix and strict atomic rollback expectations.
- Locked non-goals to prevent scope creep: no cross-version migration tooling, no solver redesign, no UI work.
- Added deterministic replay hash verification and checkpoint envelope contract to avoid snapshot/journal split-brain.
- Added CLI-to-API contract tests to prevent behavior drift between interfaces.

## Work Objectives
### Core Objective
Deliver a decision-complete runtime mutation and control-configuration platform that lets agents or game systems safely edit and resume simulations without non-deterministic behavior or high-boilerplate setup.

### Deliverables
- Canonical domain contracts for graph entities, ports, hydraulic metadata, sensor/controller bindings, and runtime command envelopes.
- Transaction engine with parse/validate/compile/commit lifecycle and strict rollback on failure.
- Dynamic API surface for unit/junction/port/line/valve/sensor/controller operations.
- Checkpoint envelope (`snapshot + journal + revision + version`) with same-version guard and replay verification utilities.
- Hybrid CLI with terse commands and declarative spec diff/apply, both using the same backend contracts.
- Automated quality baseline (tests, lint, type checks, CI) and regression suite covering happy/failure paths.

### Definition of Done (verifiable conditions with commands)
- `python -m ruff check src tests`
- `python -m mypy src`
- `python -m pytest -q tests/connection/test_transaction_atomicity.py tests/connection/test_tick_boundary_reconfiguration.py`
- `python -m pytest -q tests/connection/test_idempotency_semantics.py tests/persistence/test_checkpoint_same_version_guard.py`
- `python -m pytest -q tests/persistence/test_checkpoint_journal_replay_determinism.py tests/cli/test_cli_api_contract_mapping.py`
- `python -m pytest -q tests/integration/test_dynamic_process_network_workflow.py`

### Must Have
- Single authoritative mutation contract with `idempotency_key` + `expected_revision`.
- Atomic commit/rollback for command and batch transaction execution.
- Junctions configurable as unit-process variants with explicit inlet/outlet management.
- Resistance precedence contract: geometry-derived baseline, manual override allowed and traceable.
- Control valves implemented as resistance modifiers integrated with hydraulic compile/runtime.
- Sensors and controllers configurable at runtime; sensors contribute no extra hydraulic resistance.
- Same-version checkpoint save/load with deterministic continuation expectations.
- Same-version means exact package version string equality (from runtime metadata), not semver-major compatibility.
- CLI path requiring minimal boilerplate for common topology wiring while remaining explicit.

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- No immediate same-tick apply of runtime edits outside barrier/tick boundary.
- No partial commits on validator or compile failures.
- No hidden multi-step CLI side effects; batched behavior must be explicit transaction semantics.
- No mixing manual and derived resistance without deterministic precedence/validation errors.
- No cross-version migration guarantees in this scope.
- No human-only acceptance criteria.
- No broad refactor of unrelated process models/solver internals.

## Verification Strategy
> ZERO HUMAN INTERVENTION - all verification is agent-executed.
- Test decision: tests-after with `pytest` plus `ruff` and `mypy` quality gates.
- QA policy: every task includes one happy path and one failure/edge scenario with concrete commands/selectors/data.
- Evidence: `.sisyphus/evidence/task-{N}-{slug}.txt` and `.sisyphus/evidence/task-{N}-{slug}-error.txt`.

## Execution Strategy
### Parallel Execution Waves
> Target: 5-8 tasks per wave. Shared dependencies are front-loaded in Wave 1.

Wave 1: foundational contracts and deterministic mutation pipeline (Tasks 1-6)
Wave 2: feature APIs and persistence/CLI core flows (Tasks 7-12)
Wave 3: CLI hardening, quality baseline, integration proof, and docs/examples (Tasks 13-18)

### Dependency Matrix (full, all tasks)
- Task 1 -> Blocks Tasks 2, 3, 5, 7, 8, 9, 10
- Task 2 -> Blocks Tasks 4, 7, 8, 9, 10, 11, 13, 14
- Task 3 -> Blocks Tasks 7, 8, 15, 17
- Task 4 -> Blocks Tasks 7, 8, 9, 10, 11, 12, 17
- Task 5 -> Blocks Tasks 6, 8, 17
- Task 6 -> Blocks Tasks 8, 10, 17
- Task 7 -> Blocks Tasks 13, 14, 17, 18
- Task 8 -> Blocks Tasks 13, 14, 17
- Task 9 -> Blocks Tasks 10, 13, 17
- Task 10 -> Blocks Tasks 13, 14, 17
- Task 11 -> Blocks Tasks 12, 14, 17
- Task 12 -> Blocks Tasks 17
- Task 13 -> Blocks Tasks 17, 18
- Task 14 -> Blocks Tasks 17, 18
- Task 15 -> Blocks Tasks 17
- Task 16 -> Blocks Task 17
- Task 17 -> Blocks Task 18 and Final Verification Wave
- Task 18 -> Blocks Final Verification Wave

### Agent Dispatch Summary (wave -> task count -> categories)
- Wave 1 -> 6 tasks -> deep, unspecified-high
- Wave 2 -> 6 tasks -> deep, unspecified-high, quick
- Wave 3 -> 6 tasks -> unspecified-high, writing, quick

## TODOs
> Implementation + Test = ONE task. Never separate.
> EVERY task MUST have: Agent Profile + Parallelization + QA Scenarios.

- [x] 1. Define Canonical Runtime Mutation Domain Contracts

  **What to do**: Introduce canonical typed contracts for `UnitProcess`, `JunctionProcess`, `Port`, `ConnectionLine`, `ResistanceConfig`, `ValveConfig`, `SensorBinding`, `ControllerBinding`, and command envelopes (`idempotency_key`, `expected_revision`, metadata). Encode junctions as unit-process variants and define stable ID conventions.
  **Must NOT do**: Do not create parallel topology models; do not bypass existing topology/process-binding contracts.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: foundational architecture contracts affect all downstream tasks.
  - Skills: `[]` - no additional skill required.
  - Omitted: [`playwright`] - backend/domain work only.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: [2, 3, 5, 7, 8, 9, 10] | Blocked By: []

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `src/modular_simulation/connection/topology.py` - existing graph node/edge semantics.
  - Pattern: `src/modular_simulation/connection/process_binding.py` - inlet/outlet binding contracts.
  - Pattern: `src/modular_simulation/connection/state.py` - state validation patterns.
  - Pattern: `src/modular_simulation/connection/junction.py` - junction runtime semantics.
  - Pattern: `src/modular_simulation/framework/system.py` - system-level registration conventions.

  **Acceptance Criteria** (agent-executable only):
  - [ ] New domain contract module(s) compile with no circular imports and are imported by mutation entry points.
  - [ ] Junction entities are representable through the same unit-process configuration path as other units.
  - [ ] `python -m mypy src` passes for new/updated contract modules.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```text
  Scenario: Contract objects serialize and validate correctly
    Tool: Bash
    Steps: Run `python -m pytest -q tests/connection/test_domain_contracts.py -k "serialize or validate"`
    Expected: Exit code 0; tests confirm typed IDs, direction checks, and junction-as-unit compatibility.
    Evidence: .sisyphus/evidence/task-1-domain-contracts.txt

  Scenario: Invalid port direction and duplicate IDs are rejected
    Tool: Bash
    Steps: Run `python -m pytest -q tests/connection/test_domain_contracts.py -k "invalid direction or duplicate id"`
    Expected: Exit code 0; tests assert deterministic validation errors and no partial object creation.
    Evidence: .sisyphus/evidence/task-1-domain-contracts-error.txt
  ```

  **Commit**: YES | Message: `feat(connection): add canonical mutation domain contracts` | Files: [`src/modular_simulation/connection/`, `tests/connection/test_domain_contracts.py`]

- [x] 2. Build Transaction Command Engine and Validation Lifecycle

  **What to do**: Implement typed command processing lifecycle (`parse -> semantic validate -> invariant validate -> compile preview -> atomic commit/rollback`) with support for single commands and batch transactions. Enforce `expected_revision` and `idempotency_key` semantics.
  **Must NOT do**: Do not allow partial commit after any failed validation/compile step; do not introduce non-deterministic command ordering.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: core runtime mutation pipeline and invariants.
  - Skills: `[]` - no additional skill required.
  - Omitted: [`frontend-ui-ux`] - non-UI backend runtime logic.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: [4, 7, 8, 9, 10, 11, 13, 14] | Blocked By: [1]

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `src/modular_simulation/connection/network.py` - queued mutation/idempotency behavior.
  - Pattern: `src/modular_simulation/connection/runtime.py` - runtime apply/barrier sequencing.
  - Pattern: `src/modular_simulation/connection/connection_layer.py` - macro-step orchestration.
  - Pattern: `src/modular_simulation/connection/topology.py` - invariant checks.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Command handler supports both single-operation and explicit transaction batch envelopes.
  - [ ] One transaction may include mixed topology + instrumentation/control commands and commits atomically.
  - [ ] Revision mismatch or idempotency conflict returns structured error with no state mutation.
  - [ ] Idempotency keys persist across checkpoint save/load for pending/applied command replay safety.
  - [ ] `python -m pytest -q tests/connection/test_transaction_atomicity.py tests/connection/test_idempotency_semantics.py` passes.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```text
  Scenario: Multi-command transaction commits atomically
    Tool: Bash
    Steps: Run `python -m pytest -q tests/connection/test_transaction_atomicity.py -k "atomic commit"`
    Expected: Exit code 0; entire batch applies only when all commands pass.
    Evidence: .sisyphus/evidence/task-2-transaction-engine.txt

  Scenario: Mid-batch invariant failure triggers rollback
    Tool: Bash
    Steps: Run `python -m pytest -q tests/connection/test_transaction_atomicity.py -k "rollback"`
    Expected: Exit code 0; revision/state remain unchanged and structured error is emitted.
    Evidence: .sisyphus/evidence/task-2-transaction-engine-error.txt
  ```

  **Commit**: YES | Message: `feat(connection): add transactional command execution pipeline` | Files: [`src/modular_simulation/connection/`, `tests/connection/test_transaction_atomicity.py`, `tests/connection/test_idempotency_semantics.py`]

- [x] 3. Implement Invariant Validator and Destructive-Edit Policy Matrix

  **What to do**: Add centralized invariant validator for topology/control dependencies and define destructive-edit behavior matrix (remove unit/port/edge/junction with dependents -> hard fail with actionable error unless explicit safe-detach mode in transaction metadata).
  **Must NOT do**: Do not auto-detach silently; do not allow dangling sensor/controller references.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: safety policy and failure semantics.
  - Skills: `[]` - no additional skill required.
  - Omitted: [`playwright`] - no browser scope.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: [7, 8, 15, 17] | Blocked By: [1]

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `src/modular_simulation/connection/topology.py` - graph integrity checks.
  - Pattern: `src/modular_simulation/connection/process_binding.py` - port binding restrictions.
  - Pattern: `src/modular_simulation/components/control_system/abstract_controller.py` - controller dependency contracts.
  - Pattern: `src/modular_simulation/components/sensors/abstract_sensor.py` - sensor linkage expectations.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Validator rejects destructive edits with live dependents by default.
  - [ ] Error payload includes blocking dependents and remediation hint.
  - [ ] `python -m pytest -q tests/connection/test_destructive_edit_policies.py` passes.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```text
  Scenario: Removing unit with attached controller is blocked
    Tool: Bash
    Steps: Run `python -m pytest -q tests/connection/test_destructive_edit_policies.py -k "remove unit with dependents"`
    Expected: Exit code 0; operation rejected with dependency list and no state mutation.
    Evidence: .sisyphus/evidence/task-3-destructive-policy.txt

  Scenario: Explicit detach mode removes dependencies safely
    Tool: Bash
    Steps: Run `python -m pytest -q tests/connection/test_destructive_edit_policies.py -k "safe detach"`
    Expected: Exit code 0; detach behavior is explicit, deterministic, and fully reflected in revision delta.
    Evidence: .sisyphus/evidence/task-3-destructive-policy-error.txt
  ```

  **Commit**: YES | Message: `feat(connection): enforce destructive edit policy matrix` | Files: [`src/modular_simulation/connection/`, `tests/connection/test_destructive_edit_policies.py`]

- [x] 4. Enforce Tick-Boundary Reconfiguration Queue Integration

  **What to do**: Wire transaction engine into existing runtime queue so accepted reconfiguration commands apply only at deterministic barrier/tick boundaries. Ensure compile and apply ordering remains FIFO and deterministic.
  **Must NOT do**: Do not apply accepted mutations immediately mid-step; do not reorder queued transactions.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: runtime sequencing correctness and determinism.
  - Skills: `[]` - no additional skill required.
  - Omitted: [`frontend-ui-ux`] - backend runtime sequencing.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: [7, 8, 9, 10, 11, 12, 17] | Blocked By: [2]

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `src/modular_simulation/connection/runtime.py` - barrier sequencing and apply timing.
  - Pattern: `src/modular_simulation/connection/network.py` - queue and mutation dispatch behavior.
  - Pattern: `src/modular_simulation/connection/connection_layer.py` - macro-step orchestration boundaries.
  - Example: `examples/connection_layer/split_reversal_demo.py` - connection runtime behavior pattern.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Reconfiguration command accepted during run is visible only after next boundary.
  - [ ] FIFO queue ordering preserved across mixed command types.
  - [ ] `python -m pytest -q tests/connection/test_tick_boundary_reconfiguration.py` passes.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```text
  Scenario: Queued reconfiguration applies at next tick boundary
    Tool: Bash
    Steps: Run `python -m pytest -q tests/connection/test_tick_boundary_reconfiguration.py -k "next boundary"`
    Expected: Exit code 0; state changes appear only after barrier.
    Evidence: .sisyphus/evidence/task-4-tick-boundary-queue.txt

  Scenario: FIFO ordering is preserved across multiple queued edits
    Tool: Bash
    Steps: Run `python -m pytest -q tests/connection/test_tick_boundary_reconfiguration.py -k "fifo"`
    Expected: Exit code 0; resulting topology/revision reflects original queue order exactly.
    Evidence: .sisyphus/evidence/task-4-tick-boundary-queue-error.txt
  ```

  **Commit**: YES | Message: `feat(connection): enforce tick-boundary reconfiguration apply` | Files: [`src/modular_simulation/connection/runtime.py`, `src/modular_simulation/connection/network.py`, `tests/connection/test_tick_boundary_reconfiguration.py`]

- [x] 5. Add Geometry-Derived Resistance Model with Manual Override Precedence

  **What to do**: Implement line resistance computation contract using geometry inputs (`radius`, `length`, optional fluid factors), store derived value with provenance, and allow explicit manual override that takes precedence and is auditable.
  **Must NOT do**: Do not silently blend manual and derived values; do not accept non-physical geometry values.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: physics/validation contract with clear precedence rules.
  - Skills: `[]` - no additional skill required.
  - Omitted: [`playwright`] - backend numerical configuration.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: [6, 8, 17] | Blocked By: [1]

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `src/modular_simulation/connection/hydraulic_element.py` - hydraulic parameter integration pattern.
  - Pattern: `src/modular_simulation/connection/hydraulic_compile.py` - compile-time parameter ingestion.
  - Pattern: `src/modular_simulation/connection/material_models.py` - numerical model conventions.
  - Pattern: `src/modular_simulation/connection/state.py` - validation style for constrained numeric data.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Resistance config supports `derived` and `manual_override` modes with explicit precedence.
  - [ ] Invalid geometry (`radius <= 0`, `length <= 0`) is rejected with structured error.
  - [ ] `python -m pytest -q tests/connection/test_line_resistance_models.py` passes.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```text
  Scenario: Derived resistance is computed from geometry
    Tool: Bash
    Steps: Run `python -m pytest -q tests/connection/test_line_resistance_models.py -k "derived from geometry"`
    Expected: Exit code 0; computed resistance is stored with `source=derived`.
    Evidence: .sisyphus/evidence/task-5-resistance-model.txt

  Scenario: Manual override supersedes derived value deterministically
    Tool: Bash
    Steps: Run `python -m pytest -q tests/connection/test_line_resistance_models.py -k "manual override precedence"`
    Expected: Exit code 0; manual value is active and provenance marks override source.
    Evidence: .sisyphus/evidence/task-5-resistance-model-error.txt
  ```

  **Commit**: YES | Message: `feat(connection): add geometry resistance with manual override` | Files: [`src/modular_simulation/connection/`, `tests/connection/test_line_resistance_models.py`]

- [x] 6. Integrate Control Valve Resistance Modulation into Hydraulic Runtime

  **What to do**: Extend hydraulic compile/runtime so valve configuration maps to effective line resistance (or equivalent hydraulic parameter) and can be updated through controller outputs without breaking solver contracts.
  **Must NOT do**: Do not bypass hydraulic element interfaces; do not let valve state updates skip revision/accounting rules.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: runtime hydraulics + control coupling.
  - Skills: `[]` - no additional skill required.
  - Omitted: [`frontend-ui-ux`] - backend numerical runtime.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: [8, 10, 17] | Blocked By: [5]

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `src/modular_simulation/connection/hydraulic_element.py` - valve/pipe element contracts.
  - Pattern: `src/modular_simulation/connection/hydraulic_solver.py` - solver coupling points.
  - Pattern: `src/modular_simulation/connection/hydraulic_compile.py` - compile graph to solver structures.
  - Pattern: `src/modular_simulation/components/control_system/control_element.py` - control element abstraction.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Valve actuation updates effective hydraulic resistance in runtime step pipeline.
  - [ ] Solver remains stable and deterministic under valve movement test cases.
  - [ ] `python -m pytest -q tests/connection/test_valve_hydraulic_integration.py` passes.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```text
  Scenario: Valve opening change updates line flow as expected
    Tool: Bash
    Steps: Run `python -m pytest -q tests/connection/test_valve_hydraulic_integration.py -k "actuation affects flow"`
    Expected: Exit code 0; monotonic valve-position/flow relationship holds for configured case.
    Evidence: .sisyphus/evidence/task-6-valve-runtime.txt

  Scenario: Out-of-range valve command is rejected safely
    Tool: Bash
    Steps: Run `python -m pytest -q tests/connection/test_valve_hydraulic_integration.py -k "invalid valve range"`
    Expected: Exit code 0; invalid command yields structured error and no runtime corruption.
    Evidence: .sisyphus/evidence/task-6-valve-runtime-error.txt
  ```

  **Commit**: YES | Message: `feat(connection): integrate valve resistance modulation` | Files: [`src/modular_simulation/connection/`, `src/modular_simulation/components/control_system/`, `tests/connection/test_valve_hydraulic_integration.py`]

- [x] 7. Add Dynamic Unit/Junction/Port Reconfiguration API Endpoints

  **What to do**: Implement API operations for adding/removing unit processes, adding/removing inlets/outlets, and configuring junctions through the same unit-process interface. Route all operations through transaction command engine.
  **Must NOT do**: Do not expose direct mutable object editing APIs that bypass transaction/invariant checks.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: primary user-facing backend API with strict invariants.
  - Skills: `[]` - no additional skill required.
  - Omitted: [`playwright`] - backend API.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: [13, 14, 17, 18] | Blocked By: [1, 2, 3, 4]

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `src/modular_simulation/connection/network.py` - public mutation entrypoint style.
  - Pattern: `src/modular_simulation/connection/process_binding.py` - dynamic inlet/outlet mapping contracts.
  - Pattern: `src/modular_simulation/connection/topology.py` - graph mutation constraints.
  - Pattern: `src/modular_simulation/framework/system.py` - system orchestration API conventions.

  **Acceptance Criteria** (agent-executable only):
  - [ ] API supports add/remove for unit processes and junctions via one shared contract family.
  - [ ] API supports add/remove inlet/outlet with validation against existing connections.
  - [ ] `python -m pytest -q tests/connection/test_dynamic_unit_port_api.py` passes.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```text
  Scenario: Add unit process and attach inlet/outlet via API
    Tool: Bash
    Steps: Run `python -m pytest -q tests/connection/test_dynamic_unit_port_api.py -k "add unit and ports"`
    Expected: Exit code 0; API returns committed revision and stable IDs.
    Evidence: .sisyphus/evidence/task-7-dynamic-unit-port-api.txt

  Scenario: Remove port with active connection fails cleanly
    Tool: Bash
    Steps: Run `python -m pytest -q tests/connection/test_dynamic_unit_port_api.py -k "remove connected port"`
    Expected: Exit code 0; operation rejected with dependency details and no mutation.
    Evidence: .sisyphus/evidence/task-7-dynamic-unit-port-api-error.txt
  ```

  **Commit**: YES | Message: `feat(api): add dynamic unit, junction, and port reconfiguration` | Files: [`src/modular_simulation/connection/`, `src/modular_simulation/framework/system.py`, `tests/connection/test_dynamic_unit_port_api.py`]

- [x] 8. Add Connection Line API with Resistance Configuration

  **What to do**: Implement connect/disconnect line operations and line-configuration commands (geometry, derived resistance, manual override, valve attachment) through transaction contracts. Ensure per-line validation and compile integration.
  **Must NOT do**: Do not permit connection creation between incompatible port directions or invalid medium constraints.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: cross-cutting API + hydraulic compile integration.
  - Skills: `[]` - no additional skill required.
  - Omitted: [`frontend-ui-ux`] - backend.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: [13, 14, 17] | Blocked By: [1, 2, 3, 4, 5, 6]

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `src/modular_simulation/connection/topology.py` - edge mutation validation.
  - Pattern: `src/modular_simulation/connection/hydraulic_compile.py` - line parameter compile path.
  - Pattern: `src/modular_simulation/connection/hydraulic_element.py` - line/valve parameter mapping.
  - Pattern: `src/modular_simulation/connection/network.py` - mutation API surface.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Connect/disconnect operations are revisioned, validated, and atomic.
  - [ ] Resistance/geometry/valve config updates are reflected in compiled runtime state.
  - [ ] `python -m pytest -q tests/connection/test_connection_line_config_api.py` passes.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```text
  Scenario: Connect two processes and configure line resistance
    Tool: Bash
    Steps: Run `python -m pytest -q tests/connection/test_connection_line_config_api.py -k "connect and configure resistance"`
    Expected: Exit code 0; line is created and compiled resistance matches active config mode.
    Evidence: .sisyphus/evidence/task-8-line-config-api.txt

  Scenario: Invalid endpoint direction fails without side effects
    Tool: Bash
    Steps: Run `python -m pytest -q tests/connection/test_connection_line_config_api.py -k "invalid endpoint"`
    Expected: Exit code 0; operation rejected and graph revision unchanged.
    Evidence: .sisyphus/evidence/task-8-line-config-api-error.txt
  ```

  **Commit**: YES | Message: `feat(api): add connection line configuration operations` | Files: [`src/modular_simulation/connection/`, `tests/connection/test_connection_line_config_api.py`]

- [x] 9. Add Sensor Runtime Binding API with Zero-Resistance Guard

  **What to do**: Implement dynamic sensor add/remove/bind operations against nodes/ports/signals, explicitly enforcing that sensor installation has no hydraulic resistance impact and no topology mutation side effects.
  **Must NOT do**: Do not let sensor operations mutate hydraulic graph parameters.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: integration between connection and instrumentation layers.
  - Skills: `[]` - no additional skill required.
  - Omitted: [`playwright`] - non-UI instrumentation backend.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: [10, 13, 17] | Blocked By: [1, 2, 4]

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `src/modular_simulation/components/sensors/abstract_sensor.py` - sensor lifecycle and contract.
  - Pattern: `src/modular_simulation/components/sensors/sampled_delayed_sensor.py` - sampled sensor runtime behavior.
  - Pattern: `src/modular_simulation/framework/system.py` - sensor installation orchestration.
  - Pattern: `src/modular_simulation/components/point/point.py` - measured value transport/history.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Sensor API supports create/bind/unbind/remove with revisioned command semantics.
  - [ ] Hydraulic compile/runtime results are unchanged by sensor-only operations.
  - [ ] `python -m pytest -q tests/components/test_sensor_binding_api.py` passes.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```text
  Scenario: Sensor binds to flow variable and returns sampled measurement
    Tool: Bash
    Steps: Run `python -m pytest -q tests/components/test_sensor_binding_api.py -k "bind sensor"`
    Expected: Exit code 0; measurement stream is produced and metadata reflects binding target.
    Evidence: .sisyphus/evidence/task-9-sensor-binding-api.txt

  Scenario: Sensor install does not alter hydraulic solve result
    Tool: Bash
    Steps: Run `python -m pytest -q tests/components/test_sensor_binding_api.py -k "no hydraulic effect"`
    Expected: Exit code 0; baseline and sensor-enabled solve outputs remain equivalent under test tolerance.
    Evidence: .sisyphus/evidence/task-9-sensor-binding-api-error.txt
  ```

  **Commit**: YES | Message: `feat(components): add dynamic sensor binding api` | Files: [`src/modular_simulation/components/sensors/`, `src/modular_simulation/framework/system.py`, `tests/components/test_sensor_binding_api.py`]

- [x] 10. Add Controller and Calculation Wiring API

  **What to do**: Implement API for creating controllers, binding sensor/calculation inputs, and binding control outputs to control elements (valves). Support runtime mode configuration and validation for missing/broken signal paths.
  **Must NOT do**: Do not allow controller activation with unresolved measurement or actuator bindings.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: control-loop integrity and runtime safety.
  - Skills: `[]` - no additional skill required.
  - Omitted: [`playwright`] - backend control logic.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: [13, 14, 17] | Blocked By: [1, 2, 4, 6, 9]

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `src/modular_simulation/components/control_system/abstract_controller.py` - controller contract and update lifecycle.
  - Pattern: `src/modular_simulation/components/control_system/controller_mode.py` - mode semantics.
  - Pattern: `src/modular_simulation/components/control_system/control_element.py` - actuator abstraction.
  - Pattern: `src/modular_simulation/components/control_system/controllers/PID_controller.py` - existing controller behavior.
  - Pattern: `src/modular_simulation/framework/system.py` - installation/wiring orchestration.

  **Acceptance Criteria** (agent-executable only):
  - [ ] API supports sensor/calculation-to-controller and controller-to-valve binding commands.
  - [ ] Invalid wiring (missing tags, incompatible units, missing actuator) is rejected before activation.
  - [ ] `python -m pytest -q tests/components/test_controller_wiring_api.py` passes.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```text
  Scenario: PID controller drives valve through bound sensor signal
    Tool: Bash
    Steps: Run `python -m pytest -q tests/components/test_controller_wiring_api.py -k "pid valve loop"`
    Expected: Exit code 0; controller output updates valve command and loop converges in test fixture.
    Evidence: .sisyphus/evidence/task-10-controller-wiring-api.txt

  Scenario: Controller activation fails on unresolved sensor tag
    Tool: Bash
    Steps: Run `python -m pytest -q tests/components/test_controller_wiring_api.py -k "unresolved sensor"`
    Expected: Exit code 0; activation blocked with structured binding error.
    Evidence: .sisyphus/evidence/task-10-controller-wiring-api-error.txt
  ```

  **Commit**: YES | Message: `feat(control): add controller and calculation wiring api` | Files: [`src/modular_simulation/components/control_system/`, `src/modular_simulation/framework/system.py`, `tests/components/test_controller_wiring_api.py`]

- [x] 11. Implement Checkpoint Envelope Persistence with Same-Version Guard

  **What to do**: Extend save/load to persist a unified envelope containing topology/runtime snapshot, pending command journal, graph revision, schema marker, package/version metadata, and integrity checksum. Enforce same-version restore guard.
  **Must NOT do**: Do not silently load mismatched versions; do not write non-atomic checkpoint files.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: persistence correctness and compatibility contract.
  - Skills: `[]` - no additional skill required.
  - Omitted: [`frontend-ui-ux`] - persistence backend.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: [12, 14, 17] | Blocked By: [2, 4]

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `src/modular_simulation/connection/runtime_persistence.py` - existing snapshot schema and restore guards.
  - Pattern: `src/modular_simulation/framework/system.py` - system save/load orchestration.
  - Example: `examples/simple_irreversible_system/checkpoint_irreversible.json` - checkpoint artifact style.
  - Example: `examples/simple_irreversible_system/continue_simulation.py` - resume workflow expectation.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Checkpoint envelope writes include version/revision/checksum and pending-queue state.
  - [ ] Restore rejects mismatched version with explicit error code/message.
  - [ ] `python -m pytest -q tests/persistence/test_checkpoint_same_version_guard.py` passes.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```text
  Scenario: Save and load same-version checkpoint resumes simulation
    Tool: Bash
    Steps: Run `python -m pytest -q tests/persistence/test_checkpoint_same_version_guard.py -k "same version resume"`
    Expected: Exit code 0; loaded runtime continues from saved revision/tick.
    Evidence: .sisyphus/evidence/task-11-checkpoint-envelope.txt

  Scenario: Version mismatch checkpoint load is rejected
    Tool: Bash
    Steps: Run `python -m pytest -q tests/persistence/test_checkpoint_same_version_guard.py -k "version mismatch"`
    Expected: Exit code 0; load fails with deterministic compatibility error.
    Evidence: .sisyphus/evidence/task-11-checkpoint-envelope-error.txt
  ```

  **Commit**: YES | Message: `feat(persistence): add same-version checkpoint envelope contract` | Files: [`src/modular_simulation/connection/runtime_persistence.py`, `src/modular_simulation/framework/system.py`, `tests/persistence/test_checkpoint_same_version_guard.py`]

- [x] 12. Add Deterministic Replay Hash Verification Utilities

  **What to do**: Add deterministic replay utility to compare state hashes at selected ticks between original run and checkpoint-resume run. Integrate into persistence regression tests.
  **Must NOT do**: Do not use nondeterministic hash inputs (unordered dicts without canonicalization).

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: determinism and numerical reproducibility safeguards.
  - Skills: `[]` - no additional skill required.
  - Omitted: [`playwright`] - backend verification.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: [17] | Blocked By: [4, 11]

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `src/modular_simulation/connection/runtime_persistence.py` - snapshot/load state materialization.
  - Pattern: `src/modular_simulation/connection/runtime.py` - runtime step boundaries for consistent sampling.
  - Pattern: `src/modular_simulation/framework/system.py` - top-level run lifecycle.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Deterministic hash helper uses canonical ordering/serialization.
  - [ ] Replay test verifies hash equality for configured checkpoints/ticks.
  - [ ] `python -m pytest -q tests/persistence/test_checkpoint_journal_replay_determinism.py` passes.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```text
  Scenario: Replay from checkpoint matches original state hashes
    Tool: Bash
    Steps: Run `python -m pytest -q tests/persistence/test_checkpoint_journal_replay_determinism.py -k "hash match"`
    Expected: Exit code 0; per-tick hash vectors are identical.
    Evidence: .sisyphus/evidence/task-12-replay-determinism.txt

  Scenario: Perturbed command order fails determinism assertion
    Tool: Bash
    Steps: Run `python -m pytest -q tests/persistence/test_checkpoint_journal_replay_determinism.py -k "order perturbation"`
    Expected: Exit code 0; test detects mismatch and reports the first diverging tick.
    Evidence: .sisyphus/evidence/task-12-replay-determinism-error.txt
  ```

  **Commit**: YES | Message: `test(persistence): add deterministic replay hash verification` | Files: [`src/modular_simulation/connection/`, `tests/persistence/test_checkpoint_journal_replay_determinism.py`]

- [x] 13. Build Hybrid CLI Command Surface (1:1 API Mapping)

  **What to do**: Implement terse CLI commands for graph/control/persistence operations (`add-unit`, `add-port`, `connect`, `configure-line`, `add-sensor`, `bind-controller`, `save`, `load`, `tx begin/commit/rollback`) mapped directly to transaction API envelopes.
  **Must NOT do**: Do not implement CLI-only hidden behavior that has no API equivalent.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: interface layer mapped to existing backend contracts.
  - Skills: `[]` - no additional skill required.
  - Omitted: [`playwright`] - CLI/non-browser.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: [17, 18] | Blocked By: [2, 7, 8, 9, 10]

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `examples/connection_layer/two_tank_reaction_comparison.py` - currently verbose wiring to simplify.
  - Pattern: `src/modular_simulation/framework/system.py` - orchestration calls behind CLI handlers.
  - Pattern: `src/modular_simulation/connection/network.py` - mutation command entrypoint.
  - Example: `examples/simple_irreversible_system/continue_simulation.py` - save/load continuation flow.

  **Acceptance Criteria** (agent-executable only):
  - [ ] CLI supports end-to-end topology setup and save/load with fewer commands than current examples.
  - [ ] Each CLI command serializes to one expected backend command envelope.
  - [ ] `python -m pytest -q tests/cli/test_cli_api_contract_mapping.py` passes.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```text
  Scenario: Build two-unit connection via terse CLI commands
    Tool: Bash
    Steps: Run `python -m pytest -q tests/cli/test_cli_api_contract_mapping.py -k "basic topology flow"`
    Expected: Exit code 0; command sequence creates graph and commits expected revisions.
    Evidence: .sisyphus/evidence/task-13-cli-command-surface.txt

  Scenario: Invalid CLI command payload is rejected with actionable error
    Tool: Bash
    Steps: Run `python -m pytest -q tests/cli/test_cli_api_contract_mapping.py -k "invalid payload"`
    Expected: Exit code 0; CLI returns structured error code/message and no state mutation.
    Evidence: .sisyphus/evidence/task-13-cli-command-surface-error.txt
  ```

  **Commit**: YES | Message: `feat(cli): add command surface mapped to mutation api` | Files: [`src/modular_simulation/cli/`, `tests/cli/test_cli_api_contract_mapping.py`]

- [x] 14. Add Declarative Spec Diff/Apply CLI Workflow

  **What to do**: Add spec-file workflow (`spec diff`, `spec apply`) that compiles desired state into explicit transaction batches, previews delta, and then applies atomically via backend command engine.
  **Must NOT do**: Do not apply spec changes without explicit diff preview and transaction boundaries.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: state reconciliation and transaction safety.
  - Skills: `[]` - no additional skill required.
  - Omitted: [`frontend-ui-ux`] - CLI/backend.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: [17, 18] | Blocked By: [2, 7, 8, 10, 11]

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `src/modular_simulation/connection/network.py` - command application semantics.
  - Pattern: `src/modular_simulation/connection/runtime_persistence.py` - serialized graph/runtime representation.
  - Pattern: `examples/simple_irreversible_system/checkpoint_irreversible.json` - JSON artifact pattern.
  - Pattern: `src/modular_simulation/framework/system.py` - lifecycle orchestration hooks.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Spec diff output lists add/remove/update mutations deterministically.
  - [ ] Spec apply executes as one or more explicit transactions with rollback on failure.
  - [ ] `python -m pytest -q tests/cli/test_cli_spec_diff_apply.py` passes.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```text
  Scenario: Spec diff then apply builds target network deterministically
    Tool: Bash
    Steps: Run `python -m pytest -q tests/cli/test_cli_spec_diff_apply.py -k "diff apply happy"`
    Expected: Exit code 0; diff preview and post-apply state match expected revision delta.
    Evidence: .sisyphus/evidence/task-14-cli-spec-workflow.txt

  Scenario: Spec with invariant violation aborts entire apply
    Tool: Bash
    Steps: Run `python -m pytest -q tests/cli/test_cli_spec_diff_apply.py -k "rollback on invalid spec"`
    Expected: Exit code 0; apply fails atomically and state remains unchanged.
    Evidence: .sisyphus/evidence/task-14-cli-spec-workflow-error.txt
  ```

  **Commit**: YES | Message: `feat(cli): add declarative spec diff and apply workflow` | Files: [`src/modular_simulation/cli/`, `tests/cli/test_cli_spec_diff_apply.py`]

- [x] 15. Standardize Error Codes and Diagnostics Payloads

  **What to do**: Define and enforce structured error catalog for validation, invariants, revision mismatch, idempotency conflicts, compatibility failures, and CLI argument issues. Ensure API and CLI share the same diagnostics schema.
  **Must NOT do**: Do not return unstructured ad hoc exception strings from command handlers.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: reliability and debuggability contract.
  - Skills: `[]` - no additional skill required.
  - Omitted: [`playwright`] - backend/CLI diagnostics.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: [17] | Blocked By: [3]

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `src/modular_simulation/connection/topology.py` - current validation failure style.
  - Pattern: `src/modular_simulation/connection/runtime_persistence.py` - compatibility error paths.
  - Pattern: `src/modular_simulation/framework/system.py` - public API error propagation patterns.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Error catalog defines stable codes and payload fields (`code`, `message`, `path`, `hint`, `revision`).
  - [ ] API and CLI tests assert same code for equivalent failures.
  - [ ] `python -m pytest -q tests/connection/test_error_catalog.py tests/cli/test_cli_error_mapping.py` passes.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```text
  Scenario: API and CLI emit consistent error codes for invalid port direction
    Tool: Bash
    Steps: Run `python -m pytest -q tests/connection/test_error_catalog.py tests/cli/test_cli_error_mapping.py -k "invalid port direction"`
    Expected: Exit code 0; shared error code/payload contract is identical.
    Evidence: .sisyphus/evidence/task-15-error-catalog.txt

  Scenario: Revision mismatch reports expected vs actual revision details
    Tool: Bash
    Steps: Run `python -m pytest -q tests/connection/test_error_catalog.py -k "revision mismatch"`
    Expected: Exit code 0; payload includes expected/actual revision and retry hint.
    Evidence: .sisyphus/evidence/task-15-error-catalog-error.txt
  ```

  **Commit**: YES | Message: `feat(api): standardize mutation and cli error diagnostics` | Files: [`src/modular_simulation/connection/`, `src/modular_simulation/cli/`, `tests/connection/test_error_catalog.py`, `tests/cli/test_cli_error_mapping.py`]

- [x] 16. Bootstrap Quality Infrastructure (Pytest, Ruff, Mypy, CI)

  **What to do**: Add and configure baseline quality infrastructure for tests, linting, static typing, and CI execution. Include minimal test discovery scaffolding for new suites.
  **Must NOT do**: Do not add heavyweight tooling beyond selected baseline; do not block local development on nonessential checks.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: straightforward infra setup with clear user-selected stack.
  - Skills: `[]` - no additional skill required.
  - Omitted: [`playwright`] - infrastructure/backend only.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: [17] | Blocked By: []

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `pyproject.toml` - Python tooling central configuration (create/update as needed).
  - Pattern: `opencode.json` - repository command/config conventions to mirror in CI command choices.
  - Pattern: `.opencode/package.json` - existing script/tooling conventions for command ergonomics.
  - Pattern: `src/modular_simulation/` - typed package roots for mypy/ruff scope.
  - Pattern: `tests/conftest.py` - baseline pytest shared fixture conventions.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `pytest`, `ruff`, and `mypy` config committed and runnable in repo root.
  - [ ] CI workflow runs lint, type-check, and targeted tests.
  - [ ] `python -m ruff check src tests && python -m mypy src` executes successfully.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```text
  Scenario: Quality commands execute locally with expected scope
    Tool: Bash
    Steps: Run `python -m ruff check src tests && python -m mypy src`
    Expected: Exit code 0; configured rule/type baselines pass.
    Evidence: .sisyphus/evidence/task-16-quality-baseline.txt

  Scenario: CI config validates against workflow lint and dry execution
    Tool: Bash
    Steps: Run `python -m pytest -q tests -k "smoke"`
    Expected: Exit code 0; baseline smoke tests run under the same command family as CI.
    Evidence: .sisyphus/evidence/task-16-quality-baseline-error.txt
  ```

  **Commit**: YES | Message: `chore(repo): bootstrap pytest ruff mypy and ci` | Files: [`pyproject.toml`, `.github/workflows/`, `tests/`]

- [x] 17. Deliver Contract and Integration Test Wave for Dynamic Workflow

  **What to do**: Add full contract/integration tests spanning transaction atomicity, barrier-apply timing, idempotency/revision semantics, dynamic topology edits, line/valve config, sensor/controller wiring, checkpoint guard, replay determinism, and CLI mapping.
  **Must NOT do**: Do not use vague assertions; every test must assert binary pass/fail outcomes with explicit expected state/error codes.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: broad multi-module verification and regression coverage.
  - Skills: `[]` - no additional skill required.
  - Omitted: [`frontend-ui-ux`] - test-only backend scope.

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocks: [18, Final Verification Wave] | Blocked By: [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]

  **References** (executor has NO interview context - be exhaustive):
  - Test: `tests/connection/` - mutation/runtime/hydraulic suite patterns.
  - Test: `tests/test_components.py` - existing component-level test style to extend.
  - Test: `tests/test_save_load_minimal.py` - existing persistence baseline for continuation behavior.
  - Test: `tests/test_system.py` - end-to-end system integration assertions.
  - Example: `examples/simple_irreversible_system/continue_simulation.py` - end-to-end resume behavior expectation.

  **Acceptance Criteria** (agent-executable only):
  - [ ] All newly introduced suites execute and pass with deterministic outcomes.
  - [ ] Integration scenario validates end-to-end flow: create network -> configure controls -> run -> save -> load -> continue.
  - [ ] `python -m pytest -q tests/connection tests/components tests/persistence tests/cli tests/integration/test_dynamic_process_network_workflow.py` passes.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```text
  Scenario: Full dynamic workflow passes end-to-end integration
    Tool: Bash
    Steps: Run `python -m pytest -q tests/integration/test_dynamic_process_network_workflow.py`
    Expected: Exit code 0; scenario passes from network creation through checkpoint resume.
    Evidence: .sisyphus/evidence/task-17-integration-wave.txt

  Scenario: Failure-path matrix asserts rollback and diagnostics consistency
    Tool: Bash
    Steps: Run `python -m pytest -q tests/connection tests/cli -k "rollback or mismatch or invalid"`
    Expected: Exit code 0; failure-path tests confirm atomic rollback and stable error contracts.
    Evidence: .sisyphus/evidence/task-17-integration-wave-error.txt
  ```

  **Commit**: YES | Message: `test(integration): add dynamic simulation workflow regression suite` | Files: [`tests/connection/`, `tests/components/`, `tests/persistence/`, `tests/cli/`, `tests/integration/test_dynamic_process_network_workflow.py`]

- [x] 18. Add Minimal-Boilerplate Examples and Operator Docs

  **What to do**: Add/update examples and docs to show concise wiring of two processes through inlet/outlet, junction-as-unit setup, valve+sensor+controller loop, and save/load continuation using new API and CLI workflows.
  **Must NOT do**: Do not keep old verbose setup as recommended path; do not document undeclared behavior.

  **Recommended Agent Profile**:
  - Category: `writing` - Reason: user-facing clarity and adoption.
  - Skills: `[]` - no additional skill required.
  - Omitted: [`frontend-ui-ux`] - docs/examples, no UI build.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: [Final Verification Wave] | Blocked By: [7, 13, 14, 17]

  **References** (executor has NO interview context - be exhaustive):
  - Example: `examples/connection_layer/two_tank_reaction_comparison.py` - existing wiring baseline to simplify.
  - Example: `examples/simple_irreversible_system/run_simulation.py` - runnable simulation pattern.
  - Example: `examples/simple_irreversible_system/continue_simulation.py` - continuation pattern.
  - Pattern: `readme.md` - top-level user guidance and command snippets.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Docs include both command-based and spec-based quickstart flows.
  - [ ] Example commands run as documented and produce expected checkpoint continuation behavior.
  - [ ] `python -m pytest -q tests/integration/test_examples_smoke.py` passes.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```text
  Scenario: Quickstart command sequence creates and runs simple two-process setup
    Tool: Bash
    Steps: Run `python -m pytest -q tests/integration/test_examples_smoke.py -k "quickstart two process"`
    Expected: Exit code 0; smoke test confirms concise workflow is executable.
    Evidence: .sisyphus/evidence/task-18-docs-examples.txt

  Scenario: Documented save/load continuation command sequence succeeds
    Tool: Bash
    Steps: Run `python -m pytest -q tests/integration/test_examples_smoke.py -k "save load continue"`
    Expected: Exit code 0; resumed run continues from checkpoint and matches expected outputs.
    Evidence: .sisyphus/evidence/task-18-docs-examples-error.txt
  ```

  **Commit**: YES | Message: `docs(examples): add concise dynamic network quickstarts` | Files: [`readme.md`, `examples/`, `tests/integration/test_examples_smoke.py`]

## Final Verification Wave (4 parallel agents, ALL must APPROVE)
- [x] F1. Plan Compliance Audit - oracle
- [x] F2. Code Quality Review - unspecified-high
- [x] F3. Real Runtime QA - unspecified-high (+ playwright if UI)
- [x] F4. Scope Fidelity Check - deep

## Commit Strategy
- Use small atomic commits aligned to task boundaries (one logical feature contract per commit).
- Require green task-level acceptance commands before each commit.
- Commit format: `type(scope): desc` (e.g., `feat(connection): add transactional reconfiguration command pipeline`).
- Avoid mixing infrastructure bootstrap with runtime behavior changes in the same commit.

## Success Criteria
- Dynamic topology/control edits run through one deterministic mutation contract with no partial state commits.
- Checkpoint save/load resumes the same simulation run under same-version guard with deterministic replay evidence.
- CLI supports concise, intuitive setup for common network wiring while matching API semantics exactly.
- Automated quality gates and contract/integration tests reliably catch regression and failure-path drift.

# Connection UX Hard Switch Plan

## TL;DR

> **Quick Summary**: Replace the current manual connection-layer authoring flow with a graph-first backend API that makes process/port extension and connection creation intuitive, while preserving existing solver physics, runtime continuity, and resume coherence.
>
> **Deliverables**:
> - New single-path connection authoring API (backend/domain)
> - Runtime snapshot/resume support for full system + connection runtime
> - Hard-switch migration of all connection-layer tests/examples
> - Removal of legacy private/manual wiring patterns
>
> **Estimated Effort**: Large
> **Parallel Execution**: YES - 4 waves + final verification
> **Critical Path**: Task 1 -> Task 4 -> Task 9A -> Task 9B -> Task 9 -> Task 10 -> Task 13 -> F1-F4

---

## Context

### Original Request
User wants the connection system to be far less unwieldy, with abstraction that lets users quickly and intuitively establish connections and efficiently extend systems (add processes/inlets/outlets) with minimal manual setup and ideally single APIs.

### Interview Summary
**Key Discussions**:
- Future UX target is drag-to-connect, but this plan is backend/domain API first.
- Hard switch required: no backward compatibility layer; migrate all connection tests/examples now.
- Keep split behavior solver-driven via pressure-drop/resistance physics.
- Support ad-hoc runtime network changes (add/remove ports and connections) without resetting timeline.
- Continuous-to-batch mode transitions (e.g., CSTR inlet/outlet removal) must preserve time and state coherence.
- Add full runtime save/resume capability for the entire system (configuration + runtime internals), including pending reconfiguration queue continuity.
- Test strategy is TDD with pytest.
- Ignore prior NiceGUI direction for this effort.

**Research Findings**:
- Current connection layer is physically robust and already well covered by tests.
- Ergonomics pain comes from manual adapter wiring, direct private stream mutation, and per-step plumbing in examples.
- Existing kernels (`hydraulic_solver`, `transport`, `junction`, macro sequence) should be reused rather than rewritten.

### Metis Review
**Identified Gaps (addressed)**:
- Added explicit lifecycle guardrail: author graph -> compile/validate -> run.
- Added deterministic error and ordering guardrails.
- Added scope lock: no kernel math/tolerance rewrites, no UI implementation, no split-policy knobs.
- Added migration hygiene gate to ban legacy private/manual wiring APIs after cutover.
- Added runtime mutation guardrail: queue updates anytime, apply atomically at macro-step barriers only.
- Added runtime persistence guardrail: capture/restore only at macro barriers with staged validation and atomic activate/rollback.

---

## Work Objectives

### Core Objective
Ship a new connection domain API that allows intuitive, low-setup connection authoring and extension, including safe ad-hoc runtime reconfiguration and full runtime save/resume, while preserving existing numerical/physical behavior and determinism.

### Concrete Deliverables
- `src/modular_simulation/connection/network.py` public authoring facade.
- Supporting topology/binding/runtime compiler modules under `src/modular_simulation/connection/`.
- Runtime snapshot schema + resume validator modules for system + connection runtime continuity.
- Migrated tests in `tests/connection/` using new API.
- Migrated examples in `examples/connection_layer/` using new API.
- Hard-switch cleanup removing legacy adapter/manual wiring entry points.

### Definition of Done
- [x] `pytest tests/connection -q` passes with new API only.
- [x] `python examples/connection_layer/two_tank_reaction_comparison.py` runs successfully with new API.
- [x] No usage remains of `_input_streams`, `_output_streams`, `write_port_conditions`, or `map_port_conditions_to_balance_terms` in active connection tests/examples.
- [x] Runtime mutation contract tests pass, including CSTR continuous-to-batch transition without time reset.
- [x] Runtime persistence contract tests pass, including save/resume with queued reconfiguration and monotonic time continuity.

### Must Have
- Preserve macro sequence and determinism.
- Preserve flow-sign/balance semantics and solver-driven split behavior.
- Preserve junction fallback and transport near-zero-flow behavior.
- Provide a single, coherent authoring path for adding processes/boundaries/connections.
- Support transactional runtime topology mutation with atomic apply/rollback semantics.
- Guarantee monotonic simulation time and unaffected-state continuity across accepted mutations.
- Support full runtime snapshot/resume preserving process state, connection runtime caches, graph revision, and queued reconfiguration transactions.

### Must NOT Have (Guardrails)
- No UI drag editor implementation in this plan.
- No explicit split-ratio/priority policy API in v1.
- No hidden private-attribute mutation required by public API usage.
- No rewrites of established hydraulic/transport/junction math unless strictly required for API integration.
- No structural mutation while a macro step or Picard iteration is actively executing.
- No snapshot/restore operation during active macro-step or Picard execution windows.
- No partial restore activation when validation fails (fail closed).

---

## Verification Strategy (MANDATORY)

> **ZERO HUMAN INTERVENTION** - ALL verification is agent-executed.

### Test Decision
- **Infrastructure exists**: YES
- **Automated tests**: TDD
- **Framework**: pytest
- **TDD mode**: RED -> GREEN -> REFACTOR for each task

### QA Policy
Every task includes agent-executed QA scenarios and evidence files under `.sisyphus/evidence/`.

- **Frontend/UI**: N/A in this plan scope.
- **CLI/Examples**: use Bash to run Python examples and assert output invariants.
- **API/Domain Runtime**: use Bash + pytest targeted tests.
- **Library/Module**: use pytest unit/integration tests and explicit assertions.

---

## Execution Strategy

### Parallel Execution Waves

Wave 1 (Foundation, start immediately):
- Task 1: Topology domain primitives and validation rules
- Task 2: Process-port binding model
- Task 3: Public authoring facade skeleton (`ConnectionNetwork`)
- Task 4: Graph compile lifecycle and diagnostics scaffolding
- Task 5: Migration hygiene gate tests (legacy API usage ban)

Wave 2 (Core runtimes, after Wave 1):
- Task 6: Hydraulic compile bridge from graph to existing solver inputs
- Task 7: Junction runtime integration via existing mixer
- Task 8: Transport runtime integration via existing lag model
- Task 9A: Runtime mutation transaction contract + barrier scheduler
- Task 9B: Runtime snapshot/resume contract + restore validator
- Task 9: Macro-step runtime orchestration with deterministic bookkeeping

Wave 3 (Behavior parity + migration, after Wave 2):
- Task 10: Migrate process/balance mapping tests to new API path
- Task 11: Migrate connection integration physics tests to new API path
- Task 12: Migrate sequence/picard/fallback-focused tests to new API path

Wave 4 (Examples + hard switch, after Wave 3):
- Task 13: Migrate `two_tank_reaction_comparison` example and parity checks
- Task 14: Migrate `pump_causality_demo` and related checks
- Task 15: Remove legacy adapter/manual wiring path and finalize exports

Wave FINAL (Independent parallel review):
- F1: Plan compliance audit (`oracle`)
- F2: Code quality review (`unspecified-high`)
- F3: Real QA execution of all task scenarios (`unspecified-high`)
- F4: Scope fidelity check (`deep`)

Critical Path: 1 -> 4 -> 9A -> 9B -> 9 -> 10 -> 13 -> F1-F4
Parallel Speedup: approx 65-70% vs sequential
Max Concurrent: 6 (Wave 2)

### Dependency Matrix (Full)

- **1** blocked by: none | blocks: 3, 4, 6, 10
- **2** blocked by: none | blocks: 3, 7, 10
- **3** blocked by: 1, 2 | blocks: 9, 10, 11, 12
- **4** blocked by: 1 | blocks: 6, 9, 11, 12
- **5** blocked by: 1 | blocks: 15
- **6** blocked by: 1, 4 | blocks: 9, 11
- **7** blocked by: 2, 3 | blocks: 9, 11, 12
- **8** blocked by: 2, 3 | blocks: 9, 11, 12
- **9A** blocked by: 3, 4 | blocks: 9B, 9, 10, 11, 12, 13, 14, 15
- **9B** blocked by: 4, 9A | blocks: 9, 10, 11, 12, 13, 14, 15
- **9** blocked by: 3, 4, 6, 7, 8, 9A, 9B | blocks: 10, 11, 12, 13, 14
- **10** blocked by: 1, 2, 3, 9, 9A, 9B | blocks: 15
- **11** blocked by: 3, 4, 6, 7, 8, 9, 9A, 9B | blocks: 13, 14, 15
- **12** blocked by: 3, 4, 7, 8, 9, 9A, 9B | blocks: 15
- **13** blocked by: 9, 9A, 9B, 11 | blocks: 15
- **14** blocked by: 9, 9A, 9B, 11 | blocks: 15
- **15** blocked by: 5, 9B, 10, 11, 12, 13, 14, 9A | blocks: F1, F2, F3, F4
- **F1** blocked by: 15 | blocks: none
- **F2** blocked by: 15 | blocks: none
- **F3** blocked by: 15 | blocks: none
- **F4** blocked by: 15 | blocks: none

### Agent Dispatch Summary

- **Wave 1 (5 tasks)**: T1 `deep`, T2 `quick`, T3 `quick`, T4 `unspecified-high`, T5 `quick`
- **Wave 2 (6 tasks)**: T6 `deep`, T7 `unspecified-high`, T8 `unspecified-high`, T9A `deep`, T9B `deep`, T9 `deep`
- **Wave 3 (3 tasks)**: T10 `quick`, T11 `deep`, T12 `deep`
- **Wave 4 (3 tasks)**: T13 `quick`, T14 `quick`, T15 `unspecified-high`
- **Final (4 tasks)**: F1 `oracle`, F2 `unspecified-high`, F3 `unspecified-high`, F4 `deep`

---

## TODOs

- [x] 1. Build topology primitives and validation contract

  **What to do**:
  - Add graph domain primitives for process nodes, boundary nodes, junction nodes, port references, and connection edges.
  - Add deterministic validation rules for unknown endpoints, duplicate IDs, duplicate edges, and invalid self-links.
  - Write RED tests first for invalid graph and deterministic error messaging, then implement minimal GREEN behavior.

  **Must NOT do**:
  - Do not call hydraulic/transport solvers here.
  - Do not implement UI behaviors.

  **Recommended Agent Profile**:
  - **Category**: `deep` (data model + invariants)
  - **Skills**: `playwright` (omitted in impl), `frontend-ui-ux` (omitted)
  - **Skills Evaluated but Omitted**: `git-master` (not needed for planning scope)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3, 4, 5)
  - **Blocks**: 3, 4, 6, 10
  - **Blocked By**: None

  **References**:
  - `src/modular_simulation/connection/hydraulic_solver.py` - solver compile inputs need stable node/edge identity.
  - `tests/connection/test_hydraulic_solver_solvability.py` - expected diagnostics shape for invalid systems.
  - `tests/connection/test_connection_integration_physics.py` - topologies that must remain representable.

  **Acceptance Criteria**:
  - [ ] `tests/connection/test_topology_domain.py` exists and fails first, then passes.
  - [ ] Duplicate edge/id and invalid endpoint cases raise deterministic, assertable errors.

  **QA Scenarios**:
  ```text
  Scenario: Happy path topology compile prerequisites
    Tool: Bash (pytest)
    Preconditions: New topology module and tests added
    Steps:
      1. Run: pytest tests/connection/test_topology_domain.py -q
      2. Assert all cases pass including deterministic ordering checks
    Expected Result: Exit code 0, stable pass count
    Failure Indicators: flaky order assertions or non-deterministic messages
    Evidence: .sisyphus/evidence/task-1-topology-happy.txt

  Scenario: Failure path duplicate edge
    Tool: Bash (pytest)
    Preconditions: Duplicate edge test present
    Steps:
      1. Run: pytest tests/connection/test_topology_domain.py -k duplicate -q
      2. Assert raised error class and exact message fragment for duplicate edge
    Expected Result: Target test passes by rejecting duplicate edge
    Evidence: .sisyphus/evidence/task-1-duplicate-edge-error.txt
  ```

  **Evidence to Capture**:
  - [ ] task-1-topology-happy.txt
  - [ ] task-1-duplicate-edge-error.txt

  **Commit**: YES (group 1)
  - Message: `feat(connection): add topology primitives and deterministic validation`
  - Files: `src/modular_simulation/connection/topology.py`, `tests/connection/test_topology_domain.py`
  - Pre-commit: `pytest tests/connection/test_topology_domain.py -q`

- [x] 2. Add explicit process port binding model

  **What to do**:
  - Introduce explicit inlet binding setters and outlet state getters to replace private stream mutation.
  - Provide validation for missing binding fields and incompatible composition lengths.
  - Implement with TDD and keep behavior compatible with current `ProcessBalanceTerm` semantics.

  **Must NOT do**:
  - Do not infer bindings from private attributes.
  - Do not auto-mutate process-model internals.

  **Recommended Agent Profile**:
  - **Category**: `quick` (focused module + tests)
  - **Skills**: `playwright` (omitted), `frontend-ui-ux` (omitted)
  - **Skills Evaluated but Omitted**: `git-master` (not needed)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3, 4, 5)
  - **Blocks**: 3, 7, 8, 10
  - **Blocked By**: None

  **References**:
  - `src/modular_simulation/connection/process_interface.py` - current inlet/outlet normalization to preserve.
  - `src/modular_simulation/measurables/process_model.py` - state getter/setter and stream APIs.
  - `tests/connection/test_process_balance_mapping.py` - behavior to preserve under new binding path.

  **Acceptance Criteria**:
  - [ ] `tests/connection/test_process_binding.py` covers happy path and binding validation errors.
  - [ ] Bound inlet/outlet mapping reproduces old sign-normalization expectations.

  **QA Scenarios**:
  ```text
  Scenario: Happy path binding projection
    Tool: Bash (pytest)
    Preconditions: Binding module and tests implemented
    Steps:
      1. Run: pytest tests/connection/test_process_binding.py -q
      2. Assert outlet extraction and inlet setter application tests pass
    Expected Result: Exit code 0 with all binding tests green
    Failure Indicators: mismatched mapped inlet/outlet flow signs
    Evidence: .sisyphus/evidence/task-2-binding-happy.txt

  Scenario: Failure path missing binding
    Tool: Bash (pytest)
    Preconditions: Validation tests for missing required binding
    Steps:
      1. Run: pytest tests/connection/test_process_binding.py -k missing -q
      2. Assert deterministic ValueError/KeyError message fragment
    Expected Result: Test passes by catching expected error
    Evidence: .sisyphus/evidence/task-2-binding-error.txt
  ```

  **Evidence to Capture**:
  - [ ] task-2-binding-happy.txt
  - [ ] task-2-binding-error.txt

  **Commit**: YES (group 1)
  - Message: `feat(connection): add explicit process port bindings`
  - Files: `src/modular_simulation/connection/process_binding.py`, `tests/connection/test_process_binding.py`
  - Pre-commit: `pytest tests/connection/test_process_binding.py -q`

- [x] 3. Create `ConnectionNetwork` authoring facade skeleton

  **What to do**:
  - Add public API entry points: `add_process`, `add_boundary_source`, `add_boundary_sink`, `connect`, `compile`, `step`, `queue_reconfiguration`, `save_runtime_snapshot`, and `resume_from_snapshot`.
  - Enforce idempotency/duplicate policy and explicit endpoint grammar (`process_id.port_name` or named boundary/junction IDs).
  - Add ergonomic error messages that are deterministic and testable.

  **Must NOT do**:
  - Do not embed kernel math in facade.
  - Do not bypass topology/binding validation.

  **Recommended Agent Profile**:
  - **Category**: `quick` (public API scaffolding)
  - **Skills**: `playwright` (omitted), `frontend-ui-ux` (omitted)
  - **Skills Evaluated but Omitted**: `git-master` (not needed)

  **Parallelization**:
  - **Can Run In Parallel**: YES (after Tasks 1 and 2 land interfaces)
  - **Parallel Group**: Wave 1
  - **Blocks**: 9, 10, 11, 12
  - **Blocked By**: 1, 2

  **References**:
  - `examples/connection_layer/two_tank_reaction_comparison.py` - current user journey to simplify.
  - `src/modular_simulation/connection/connection_layer.py` - output/result shape to mirror.
  - `tests/connection/test_process_interface_adapter.py` - error messaging expectations to keep actionable.

  **Acceptance Criteria**:
  - [ ] `tests/connection/test_network_api.py` defines and passes facade contract tests.
  - [ ] Duplicate connect behavior is deterministic and asserted.
  - [ ] Reconfiguration requests can be queued with deterministic validation errors for malformed operations.
  - [ ] Snapshot/resume API entry points expose deterministic errors when runtime contract is unavailable/invalid.

  **QA Scenarios**:
  ```text
  Scenario: Happy path facade authoring
    Tool: Bash (pytest)
    Preconditions: network facade tests written
    Steps:
      1. Run: pytest tests/connection/test_network_api.py -q
      2. Assert add/connect/compile API path passes
    Expected Result: Exit code 0 with deterministic ordering checks passing
    Failure Indicators: nondeterministic endpoint parsing or duplicate behavior
    Evidence: .sisyphus/evidence/task-3-network-happy.txt

  Scenario: Failure path invalid endpoint grammar
    Tool: Bash (pytest)
    Preconditions: invalid endpoint tests included
    Steps:
      1. Run: pytest tests/connection/test_network_api.py -k endpoint -q
      2. Assert specific parse/validation error message fragment
    Expected Result: Test passes by rejecting malformed endpoint
    Evidence: .sisyphus/evidence/task-3-network-error.txt
  ```

  **Evidence to Capture**:
  - [ ] task-3-network-happy.txt
  - [ ] task-3-network-error.txt

  **Commit**: YES (group 1)
  - Message: `feat(connection): scaffold connection network facade`
  - Files: `src/modular_simulation/connection/network.py`, `tests/connection/test_network_api.py`
  - Pre-commit: `pytest tests/connection/test_network_api.py -q`

- [x] 4. Implement compile lifecycle and deterministic diagnostics

  **What to do**:
  - Implement explicit `compile()` stage that validates graph consistency before `step()`.
  - Add deterministic diagnostic payloads for missing pressure references, disconnected structures, and invalid cardinality.
  - Add staged compile support for candidate graph revisions used by queued runtime mutations.
  - Ensure error class/message stability for assertion-based tests.

  **Must NOT do**:
  - Do not run runtime kernel execution inside compile.
  - Do not loosen existing solvability requirements.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` (cross-module validation contract)
  - **Skills**: `playwright` (omitted), `frontend-ui-ux` (omitted)
  - **Skills Evaluated but Omitted**: `git-master` (not needed)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1
  - **Blocks**: 6, 9, 11, 12
  - **Blocked By**: 1

  **References**:
  - `src/modular_simulation/connection/hydraulic_solver.py` - existing solvability checks to preserve.
  - `tests/connection/test_hydraulic_solver_solvability.py` - expected failure modes and diagnostics.
  - `src/modular_simulation/connection/connection_layer.py` - sequence assumptions that compile stage must feed.

  **Acceptance Criteria**:
  - [ ] `tests/connection/test_graph_compile_validation.py` exists and passes.
  - [ ] Same invalid graph produces same error type/message across runs.
  - [ ] Candidate reconfiguration compile can be validated without mutating active runtime state.

  **QA Scenarios**:
  ```text
  Scenario: Happy path compile validation
    Tool: Bash (pytest)
    Preconditions: compile tests implemented
    Steps:
      1. Run: pytest tests/connection/test_graph_compile_validation.py -q
      2. Assert valid topologies compile without runtime execution
    Expected Result: Exit code 0, deterministic diagnostics snapshots pass
    Failure Indicators: diagnostics include nondeterministic ordering/content
    Evidence: .sisyphus/evidence/task-4-compile-happy.txt

  Scenario: Failure path missing pressure reference
    Tool: Bash (pytest)
    Preconditions: invalid pressure reference case added
    Steps:
      1. Run: pytest tests/connection/test_graph_compile_validation.py -k pressure -q
      2. Assert explicit compile-time error with stable message
    Expected Result: test passes by catching expected compile error
    Evidence: .sisyphus/evidence/task-4-compile-error.txt
  ```

  **Evidence to Capture**:
  - [ ] task-4-compile-happy.txt
  - [ ] task-4-compile-error.txt

  **Commit**: YES (group 1)
  - Message: `feat(connection): add compile lifecycle and diagnostics`
  - Files: `src/modular_simulation/connection/hydraulic_compile.py`, `tests/connection/test_graph_compile_validation.py`
  - Pre-commit: `pytest tests/connection/test_graph_compile_validation.py -q`

- [x] 5. Add migration hygiene gate against legacy wiring APIs

  **What to do**:
  - Add tests that fail if active connection tests/examples use `_input_streams`, `_output_streams`, `write_port_conditions`, or `map_port_conditions_to_balance_terms`.
  - Scope the gate to connection-layer migrated targets to enforce hard switch.
  - Add clear failure messaging with offending file path and token.

  **Must NOT do**:
  - Do not ban legitimate internals outside migration scope.
  - Do not rely on manual review only.

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: `playwright` (omitted), `frontend-ui-ux` (omitted)
  - **Skills Evaluated but Omitted**: `git-master` (not needed)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1
  - **Blocks**: 15
  - **Blocked By**: 1

  **References**:
  - `examples/connection_layer/two_tank_reaction_comparison.py` - currently contains manual wiring patterns to eliminate.
  - `tests/connection/test_connection_integration_physics.py` - current private-field setup pattern to migrate away from.
  - `tests/connection/test_process_interface_adapter.py` - legacy adapter API usage to sunset.

  **Acceptance Criteria**:
  - [ ] `tests/connection/test_migration_hygiene_gate.py` enforces banned token checks.
  - [ ] Gate fails with actionable error when any banned usage is reintroduced.

  **QA Scenarios**:
  ```text
  Scenario: Happy path hygiene gate
    Tool: Bash (pytest)
    Preconditions: migrated files no longer contain banned tokens
    Steps:
      1. Run: pytest tests/connection/test_migration_hygiene_gate.py -q
      2. Assert no banned token findings
    Expected Result: Exit code 0
    Failure Indicators: false positives on allowed files
    Evidence: .sisyphus/evidence/task-5-gate-happy.txt

  Scenario: Failure path banned token detection
    Tool: Bash (pytest)
    Preconditions: test fixture includes synthetic banned token sample
    Steps:
      1. Run: pytest tests/connection/test_migration_hygiene_gate.py -k banned -q
      2. Assert failure output includes file path + token
    Expected Result: detection test passes by proving gate catches violations
    Evidence: .sisyphus/evidence/task-5-gate-error.txt
  ```

  **Evidence to Capture**:
  - [ ] task-5-gate-happy.txt
  - [ ] task-5-gate-error.txt

  **Commit**: YES (group 1)
  - Message: `test(connection): add migration hygiene gate for legacy wiring`
  - Files: `tests/connection/test_migration_hygiene_gate.py`
  - Pre-commit: `pytest tests/connection/test_migration_hygiene_gate.py -q`

- [x] 6. Bridge compiled graph to existing hydraulic solver interface

  **What to do**:
  - Convert compiled topology into hydraulic unknowns/residuals and boundary constraints consumed by existing solver.
  - Preserve deterministic unknown ordering and component-based pressure reference checks.
  - Add parity tests comparing compile output expectations for representative topologies.

  **Must NOT do**:
  - Do not change `solve_hydraulic_system` math or tolerance behavior.
  - Do not introduce split-ratio policy controls.

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: `playwright` (omitted), `frontend-ui-ux` (omitted)
  - **Skills Evaluated but Omitted**: `git-master` (not needed)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 7, 8, 9)
  - **Blocks**: 9, 11
  - **Blocked By**: 1, 4

  **References**:
  - `src/modular_simulation/connection/hydraulic_solver.py` - target solver contract.
  - `tests/connection/test_hydraulic_solver_solvability.py` - solvability and pressure reference behavior.
  - `tests/connection/test_connection_integration_physics.py` - flow reversal and closure expectations.

  **Acceptance Criteria**:
  - [ ] `tests/connection/test_hydraulic_compile.py` passes for linear, branch/split, and recycle topologies.
  - [ ] Unknown/residual ordering is deterministic and asserted.

  **QA Scenarios**:
  ```text
  Scenario: Happy path hydraulic compile parity
    Tool: Bash (pytest)
    Preconditions: compile bridge module and tests implemented
    Steps:
      1. Run: pytest tests/connection/test_hydraulic_compile.py -q
      2. Assert expected unknown/residual counts and deterministic key order
    Expected Result: Exit code 0 with parity tests green
    Failure Indicators: ordering mismatch or missing pressure-reference diagnostics
    Evidence: .sisyphus/evidence/task-6-hydraulic-compile-happy.txt

  Scenario: Failure path unsolvable component diagnostics
    Tool: Bash (pytest)
    Preconditions: unsolvable topology test included
    Steps:
      1. Run: pytest tests/connection/test_hydraulic_compile.py -k unsolvable -q
      2. Assert compile/solve bridge reports component-specific diagnostic
    Expected Result: test passes by catching expected failure
    Evidence: .sisyphus/evidence/task-6-hydraulic-compile-error.txt
  ```

  **Evidence to Capture**:
  - [ ] task-6-hydraulic-compile-happy.txt
  - [ ] task-6-hydraulic-compile-error.txt

  **Commit**: YES (group 2)
  - Message: `feat(connection): bridge graph compile output to hydraulic solver`
  - Files: `src/modular_simulation/connection/hydraulic_compile.py`, `tests/connection/test_hydraulic_compile.py`
  - Pre-commit: `pytest tests/connection/test_hydraulic_compile.py -q`

- [x] 7. Integrate junction runtime through existing mixer semantics

  **What to do**:
  - Implement runtime mapping from graph fan-in/fan-out node state to `mix_junction_state` inputs.
  - Preserve near-zero-flow fallback behavior and deterministic key traversal.
  - Add tests that prove no behavior drift from current junction semantics.

  **Must NOT do**:
  - Do not reimplement mixing math.
  - Do not add custom split policy paths.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: `playwright` (omitted), `frontend-ui-ux` (omitted)
  - **Skills Evaluated but Omitted**: `git-master` (not needed)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 6, 8, 9)
  - **Blocks**: 9, 11, 12
  - **Blocked By**: 2, 3

  **References**:
  - `src/modular_simulation/connection/junction.py` - authoritative mixing and fallback logic.
  - `tests/connection/test_junction_mixing.py` - exact expected behavior.
  - `tests/connection/test_connection_integration_physics.py` - integration usage of mixing.

  **Acceptance Criteria**:
  - [ ] `tests/connection/test_junction_runtime.py` passes and matches prior weighted/fallback semantics.
  - [ ] Fan-in/fan-out graph cases pass without introducing policy knobs.

  **QA Scenarios**:
  ```text
  Scenario: Happy path fan-in mixing parity
    Tool: Bash (pytest)
    Preconditions: junction runtime adapter implemented
    Steps:
      1. Run: pytest tests/connection/test_junction_runtime.py -q
      2. Assert weighted mixing outputs match expected pressure/temperature/composition
    Expected Result: Exit code 0
    Failure Indicators: output diverges from expected weighted state or fallback flag
    Evidence: .sisyphus/evidence/task-7-junction-happy.txt

  Scenario: Failure path near-zero fallback regression
    Tool: Bash (pytest)
    Preconditions: near-zero flow test case present
    Steps:
      1. Run: pytest tests/connection/test_junction_runtime.py -k near_zero -q
      2. Assert fallback state is previous_state with used_fallback=True
    Expected Result: test passes with deterministic fallback behavior
    Evidence: .sisyphus/evidence/task-7-junction-error.txt
  ```

  **Evidence to Capture**:
  - [ ] task-7-junction-happy.txt
  - [ ] task-7-junction-error.txt

  **Commit**: YES (group 2)
  - Message: `feat(connection): integrate junction runtime with existing mixer`
  - Files: `src/modular_simulation/connection/junction_runtime.py`, `tests/connection/test_junction_runtime.py`
  - Pre-commit: `pytest tests/connection/test_junction_runtime.py -q`

- [x] 8. Integrate transport runtime through existing lag model

  **What to do**:
  - Add edge-level transport runtime state manager using `update_lag_transport_state`.
  - Preserve sign-change and near-zero-flow hold behavior.
  - Add tests for finite-state guarantees and composition normalization.

  **Must NOT do**:
  - Do not alter transport equations.
  - Do not skip previous-flow-state tracking.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: `playwright` (omitted), `frontend-ui-ux` (omitted)
  - **Skills Evaluated but Omitted**: `git-master` (not needed)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 6, 7, 9)
  - **Blocks**: 9, 11, 12
  - **Blocked By**: 2, 3

  **References**:
  - `src/modular_simulation/connection/transport.py` - canonical lag transport behavior.
  - `tests/connection/test_transport_lag.py` - expected bounds, hold behavior, and invariants.
  - `tests/connection/test_connection_integration_physics.py` - runtime coupling expectations.

  **Acceptance Criteria**:
  - [ ] `tests/connection/test_transport_runtime.py` passes for happy path, reversal, and near-zero hold.
  - [ ] Composition sum and finite output invariants are asserted.

  **QA Scenarios**:
  ```text
  Scenario: Happy path lag transport update
    Tool: Bash (pytest)
    Preconditions: transport runtime module and tests implemented
    Steps:
      1. Run: pytest tests/connection/test_transport_runtime.py -q
      2. Assert finite state, normalized composition, expected update fraction bounds
    Expected Result: Exit code 0
    Failure Indicators: NaN values, composition sum drift, out-of-bounds update fraction
    Evidence: .sisyphus/evidence/task-8-transport-happy.txt

  Scenario: Failure path sign reversal/near-zero hold
    Tool: Bash (pytest)
    Preconditions: reversal and near-zero cases included
    Steps:
      1. Run: pytest tests/connection/test_transport_runtime.py -k "reversal or near_zero" -q
      2. Assert held-for-near-zero flag and deterministic transitions
    Expected Result: targeted tests pass with expected hold/reversal behavior
    Evidence: .sisyphus/evidence/task-8-transport-error.txt
  ```

  **Evidence to Capture**:
  - [ ] task-8-transport-happy.txt
  - [ ] task-8-transport-error.txt

  **Commit**: YES (group 2)
  - Message: `feat(connection): integrate transport runtime with lag model`
  - Files: `src/modular_simulation/connection/transport_runtime.py`, `tests/connection/test_transport_runtime.py`
  - Pre-commit: `pytest tests/connection/test_transport_runtime.py -q`

- [x] 9A. Define runtime reconfiguration transaction contract and barrier scheduler

  **What to do**:
  - Add a transactional reconfiguration model (`queue -> validate -> apply at barrier -> commit/rollback`) for topology updates during a run.
  - Support mutation operations for add/remove/rewire ports and connections, with deterministic ordering and idempotency key handling.
  - Enforce barrier-only apply semantics: requests can be queued anytime but must only commit between macro steps.
  - Add rollback behavior so failed reconfiguration leaves graph, runtime state, and simulation time unchanged.

  **Must NOT do**:
  - Do not apply structural mutation while a macro step or Picard iteration is executing.
  - Do not partially apply multi-op transactions.

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: `playwright` (omitted), `frontend-ui-ux` (omitted)
  - **Skills Evaluated but Omitted**: `git-master` (not needed)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 6, 7, 8, 9)
  - **Blocks**: 9, 10, 11, 12, 13, 14, 15
  - **Blocked By**: 3, 4

  **References**:
  - `src/modular_simulation/connection/connection_layer.py` - macro boundary and Picard execution windows to protect.
  - `src/modular_simulation/framework/system.py` - simulation step/time progression boundaries.
  - `tests/connection/test_connection_layer_sequence.py` - deterministic sequencing constraints.

  **Acceptance Criteria**:
  - [ ] `tests/connection/test_runtime_mutation_contract.py` exists and passes for boundary-only apply, rollback, and deterministic ordering.
  - [ ] Failed reconfiguration transaction does not advance simulation time or mutate active graph revision.
  - [ ] CSTR continuous-to-batch mutation scenario is covered as a runtime transition contract test.

  **QA Scenarios**:
  ```text
  Scenario: Happy path queued mutation applies at next macro boundary
    Tool: Bash (pytest)
    Preconditions: runtime mutation contract tests implemented
    Steps:
      1. Run: pytest tests/connection/test_runtime_mutation_contract.py -k boundary -q
      2. Assert mutation is queued during step N and committed only at step N+1 boundary
    Expected Result: Exit code 0 with deterministic revision/time assertions
    Failure Indicators: mutation visible before boundary or non-deterministic apply order
    Evidence: .sisyphus/evidence/task-9a-mutation-happy.txt

  Scenario: Failure path invalid mutation rolls back fully
    Tool: Bash (pytest)
    Preconditions: invalid multi-op transaction case present
    Steps:
      1. Run: pytest tests/connection/test_runtime_mutation_contract.py -k rollback -q
      2. Assert graph revision, runtime state snapshot, and sim time remain unchanged
    Expected Result: targeted tests pass by proving atomic rollback
    Evidence: .sisyphus/evidence/task-9a-mutation-error.txt
  ```

  **Evidence to Capture**:
  - [ ] task-9a-mutation-happy.txt
  - [ ] task-9a-mutation-error.txt

  **Commit**: YES (group 2)
  - Message: `feat(connection): add runtime mutation transaction contract`
  - Files: `src/modular_simulation/connection/network.py`, `src/modular_simulation/connection/runtime.py`, `tests/connection/test_runtime_mutation_contract.py`
  - Pre-commit: `pytest tests/connection/test_runtime_mutation_contract.py -q`

- [x] 9B. Define runtime snapshot/resume contract and restore validator

  **What to do**:
  - Add a versioned runtime snapshot schema capturing full run state: simulation time/indexes, process runtime state, connection runtime caches, active graph revision, and pending reconfiguration queue.
  - Implement barrier-only snapshot capture and barrier-safe restore (staged validate-then-activate).
  - Add integrity/version checks and fail-closed behavior so invalid snapshots cannot partially mutate active runtime.
  - Ensure queued reconfiguration transactions restore in deterministic order with idempotency keys preserved.

  **Must NOT do**:
  - Do not capture or apply snapshot mid macro-step/Picard iteration.
  - Do not partially restore when validation fails.

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: `playwright` (omitted), `frontend-ui-ux` (omitted)
  - **Skills Evaluated but Omitted**: `git-master` (not needed)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 6, 7, 8, 9A, 9)
  - **Blocks**: 9, 10, 11, 12, 13, 14, 15
  - **Blocked By**: 4, 9A

  **References**:
  - `src/modular_simulation/framework/system.py:420` - existing minimal save/load baseline to extend with runtime contract.
  - `src/modular_simulation/measurables/process_model.py:210` - process state/time serialization anchor.
  - `src/modular_simulation/connection/connection_layer.py` - macro boundary semantics needed for barrier-only capture/restore.

  **Acceptance Criteria**:
  - [ ] `tests/connection/test_runtime_persistence_contract.py` exists and passes for round-trip continuity.
  - [ ] Save/resume preserves `simulation_time`, graph revision id, and queued transaction ordering.
  - [ ] Failed restore leaves active runtime unchanged (time, revision, queue, and state snapshot).

  **QA Scenarios**:
  ```text
  Scenario: Happy path snapshot/resume continuity
    Tool: Bash (pytest)
    Preconditions: runtime persistence contract tests implemented
    Steps:
      1. Run: pytest tests/connection/test_runtime_persistence_contract.py -k "round_trip or monotonic" -q
      2. Assert resumed run continues from saved time and preserves revision/queue ordering
    Expected Result: Exit code 0 with deterministic continuity assertions
    Failure Indicators: time reset, queue reorder, or revision mismatch after resume
    Evidence: .sisyphus/evidence/task-9b-persistence-happy.txt

  Scenario: Failure path invalid snapshot restore
    Tool: Bash (pytest)
    Preconditions: corrupted/invalid snapshot fixture included
    Steps:
      1. Run: pytest tests/connection/test_runtime_persistence_contract.py -k "invalid or rollback" -q
      2. Assert restore rejection keeps active runtime unchanged
    Expected Result: targeted tests pass by proving atomic no-op on failed restore
    Evidence: .sisyphus/evidence/task-9b-persistence-error.txt
  ```

  **Evidence to Capture**:
  - [ ] task-9b-persistence-happy.txt
  - [ ] task-9b-persistence-error.txt

  **Commit**: YES (group 2)
  - Message: `feat(connection): add runtime snapshot and restore contract`
  - Files: `src/modular_simulation/connection/runtime_persistence.py`, `tests/connection/test_runtime_persistence_contract.py`
  - Pre-commit: `pytest tests/connection/test_runtime_persistence_contract.py -q`

- [x] 9. Build macro-step runtime orchestrator for network API

  **What to do**:
  - Wire compile output + hydraulic bridge + junction runtime + transport runtime into macro sequence.
  - Integrate queued reconfiguration commit barrier so accepted mutations apply atomically between macro steps.
  - Keep sequencing contract and bookkeeping parity with current `run_macro_coupling_step` behavior.
  - Preserve Picard gate controls and residual handling semantics.

  **Must NOT do**:
  - Do not change macro sequence ordering.
  - Do not remove bookkeeping fields used by tests.
  - Do not advance simulation time when reconfiguration commit fails validation/compile.

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: `playwright` (omitted), `frontend-ui-ux` (omitted)
  - **Skills Evaluated but Omitted**: `git-master` (not needed)

  **Parallelization**:
  - **Can Run In Parallel**: YES (once dependencies complete)
  - **Parallel Group**: Wave 2
  - **Blocks**: 10, 11, 12, 13, 14
  - **Blocked By**: 3, 4, 6, 7, 8, 9A, 9B

  **References**:
  - `src/modular_simulation/connection/connection_layer.py` - exact macro sequencing and bookkeeping model.
  - `tests/connection/test_connection_layer_sequence.py` - sequence invariants.
  - `tests/connection/test_connection_layer_picard_gate.py` - Picard gate convergence/iteration expectations.

  **Acceptance Criteria**:
  - [ ] `tests/connection/test_connection_runtime_sequence.py` passes with sequence parity assertions.
  - [ ] Picard gate behavior remains deterministic and test-covered.
  - [ ] Runtime mutation apply/rollback events are surfaced in deterministic bookkeeping fields.

  **QA Scenarios**:
  ```text
  Scenario: Happy path macro sequence parity
    Tool: Bash (pytest)
    Preconditions: network runtime orchestrator implemented
    Steps:
      1. Run: pytest tests/connection/test_connection_runtime_sequence.py -q
      2. Assert executed sequence equals expected fixed order
    Expected Result: Exit code 0 and bookkeeping assertions pass
    Failure Indicators: sequence order mismatch or missing updated keys
    Evidence: .sisyphus/evidence/task-9-runtime-happy.txt

  Scenario: Failure path Picard gate non-convergence handling
    Tool: Bash (pytest)
    Preconditions: non-convergent scenario fixture added
    Steps:
      1. Run: pytest tests/connection/test_connection_runtime_sequence.py -k picard -q
      2. Assert residual/iteration fields are populated and deterministic
    Expected Result: tests pass by validating robust handling
    Evidence: .sisyphus/evidence/task-9-runtime-error.txt

  Scenario: Failure path reconfiguration commit rejection
    Tool: Bash (pytest)
    Preconditions: invalid queued mutation fixture included
    Steps:
      1. Run: pytest tests/connection/test_connection_runtime_sequence.py -k reconfiguration -q
      2. Assert commit rejection leaves time unchanged and active revision intact
    Expected Result: targeted tests pass with deterministic rollback bookkeeping
    Evidence: .sisyphus/evidence/task-9-runtime-reconfig-error.txt
  ```

  **Evidence to Capture**:
  - [ ] task-9-runtime-happy.txt
  - [ ] task-9-runtime-error.txt
  - [ ] task-9-runtime-reconfig-error.txt

  **Commit**: YES (group 2)
  - Message: `feat(connection): add network macro-step orchestrator`
  - Files: `src/modular_simulation/connection/runtime.py`, `tests/connection/test_connection_runtime_sequence.py`
  - Pre-commit: `pytest tests/connection/test_connection_runtime_sequence.py -q`

- [x] 10. Migrate process/balance mapping tests to network API

  **What to do**:
  - Rewrite adapter-centric tests to use `ConnectionNetwork` and explicit bindings.
  - Preserve existing role-normalization and bidirectional flow assertions.
  - Remove reliance on private stream mutation in migrated tests.

  **Must NOT do**:
  - Do not weaken assertion strictness.
  - Do not keep dual-path test logic.

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: `playwright` (omitted), `frontend-ui-ux` (omitted)
  - **Skills Evaluated but Omitted**: `git-master` (not needed)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 11, 12)
  - **Blocks**: 15
  - **Blocked By**: 1, 2, 3, 9, 9A, 9B

  **References**:
  - `tests/connection/test_process_interface_adapter.py` - behavior baseline and errors to preserve.
  - `tests/connection/test_process_balance_mapping.py` - normalization assertions to keep.
  - `src/modular_simulation/connection/process_interface.py` - legacy mapping semantics to match.

  **Acceptance Criteria**:
  - [ ] Migrated tests pass using network API only.
  - [ ] No `_input_streams`/`_output_streams` mutation remains in these test files.

  **QA Scenarios**:
  ```text
  Scenario: Happy path migrated process mapping tests
    Tool: Bash (pytest)
    Preconditions: migrated tests committed in branch
    Steps:
      1. Run: pytest tests/connection/test_process_interface_adapter.py tests/connection/test_process_balance_mapping.py -q
      2. Assert pass with no legacy adapter setup helpers
    Expected Result: Exit code 0
    Failure Indicators: hidden adapter/private-stream usage or changed normalization semantics
    Evidence: .sisyphus/evidence/task-10-mapping-happy.txt

  Scenario: Failure path regression in sign normalization
    Tool: Bash (pytest)
    Preconditions: targeted reversal tests exist
    Steps:
      1. Run: pytest tests/connection/test_process_balance_mapping.py -k reversal -q
      2. Assert inlet/outlet role behavior still matches prior contract
    Expected Result: tests pass with unchanged sign expectations
    Evidence: .sisyphus/evidence/task-10-mapping-error.txt
  ```

  **Evidence to Capture**:
  - [ ] task-10-mapping-happy.txt
  - [ ] task-10-mapping-error.txt

  **Commit**: YES (group 3)
  - Message: `test(connection): migrate process mapping tests to network api`
  - Files: `tests/connection/test_process_interface_adapter.py`, `tests/connection/test_process_balance_mapping.py`
  - Pre-commit: `pytest tests/connection/test_process_interface_adapter.py tests/connection/test_process_balance_mapping.py -q`

- [x] 11. Migrate integration physics tests to network API

  **What to do**:
  - Migrate integration physics suites to construct networks with new authoring APIs.
  - Preserve causality reversal, mass-balance closure, and deterministic trace expectations.
  - Keep numeric tolerances unchanged unless a test proves tolerance bug independent of migration.

  **Must NOT do**:
  - Do not loosen physics assertions to pass migration.
  - Do not add manual fallback hacks outside runtime contract.

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: `playwright` (omitted), `frontend-ui-ux` (omitted)
  - **Skills Evaluated but Omitted**: `git-master` (not needed)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 10, 12)
  - **Blocks**: 13, 14, 15
  - **Blocked By**: 3, 4, 6, 7, 8, 9, 9A, 9B

  **References**:
  - `tests/connection/test_connection_integration_physics.py` - core parity criteria.
  - `tests/connection/test_hydraulic_solver_solvability.py` - solvability diagnostics and references.
  - `src/modular_simulation/connection/connection_layer.py` - sequence and result bookkeeping model.

  **Acceptance Criteria**:
  - [ ] Migrated integration physics suite passes with unchanged tolerances.
  - [ ] Branch/split and reversal scenarios are represented through network API calls.

  **QA Scenarios**:
  ```text
  Scenario: Happy path integration parity
    Tool: Bash (pytest)
    Preconditions: migrated integration tests updated
    Steps:
      1. Run: pytest tests/connection/test_connection_integration_physics.py -q
      2. Assert causality and closure checks pass
    Expected Result: Exit code 0 with parity assertions green
    Failure Indicators: residual closure fails or deterministic traces diverge
    Evidence: .sisyphus/evidence/task-11-integration-happy.txt

  Scenario: Failure path pressure-reference diagnostic stability
    Tool: Bash (pytest)
    Preconditions: invalid topology diagnostics tests included
    Steps:
      1. Run: pytest tests/connection/test_hydraulic_solver_solvability.py -k pressure_reference -q
      2. Assert diagnostics still include component-specific context
    Expected Result: targeted tests pass with stable diagnostics
    Evidence: .sisyphus/evidence/task-11-integration-error.txt
  ```

  **Evidence to Capture**:
  - [ ] task-11-integration-happy.txt
  - [ ] task-11-integration-error.txt

  **Commit**: YES (group 3)
  - Message: `test(connection): migrate integration physics suites to network api`
  - Files: `tests/connection/test_connection_integration_physics.py`, `tests/connection/test_hydraulic_solver_solvability.py`
  - Pre-commit: `pytest tests/connection/test_connection_integration_physics.py -q`

- [x] 12. Migrate sequence and Picard/fallback behavior tests

  **What to do**:
  - Port sequence-focused and Picard-gate tests to network runtime path.
  - Ensure transport fallback and junction fallback keys are still surfaced.
  - Preserve deterministic bookkeeping key order and residual reporting.

  **Must NOT do**:
  - Do not hide regressions by removing bookkeeping assertions.
  - Do not change gate convergence semantics.

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: `playwright` (omitted), `frontend-ui-ux` (omitted)
  - **Skills Evaluated but Omitted**: `git-master` (not needed)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 10, 11)
  - **Blocks**: 15
  - **Blocked By**: 3, 4, 7, 8, 9, 9A, 9B

  **References**:
  - `tests/connection/test_connection_layer_sequence.py` - sequence contract.
  - `tests/connection/test_connection_layer_picard_gate.py` - gate behavior contract.
  - `src/modular_simulation/connection/connection_layer.py` - bookkeeping fields and residual extraction.

  **Acceptance Criteria**:
  - [ ] Migrated sequence and gate suites pass under network runtime.
  - [ ] Bookkeeping fields `updated_port_keys`, fallback keys, and picard metadata remain asserted.

  **QA Scenarios**:
  ```text
  Scenario: Happy path sequence and gate parity
    Tool: Bash (pytest)
    Preconditions: sequence/picard tests migrated
    Steps:
      1. Run: pytest tests/connection/test_connection_layer_sequence.py tests/connection/test_connection_layer_picard_gate.py -q
      2. Assert sequence order and gate metadata checks pass
    Expected Result: Exit code 0
    Failure Indicators: missing fallback keys or changed gate iteration behavior
    Evidence: .sisyphus/evidence/task-12-sequence-happy.txt

  Scenario: Failure path forced non-convergence
    Tool: Bash (pytest)
    Preconditions: non-convergent fixture preserved
    Steps:
      1. Run: pytest tests/connection/test_connection_layer_picard_gate.py -k non_converge -q
      2. Assert deterministic max-iteration behavior and residual reporting
    Expected Result: targeted tests pass by validating expected failure handling
    Evidence: .sisyphus/evidence/task-12-sequence-error.txt
  ```

  **Evidence to Capture**:
  - [ ] task-12-sequence-happy.txt
  - [ ] task-12-sequence-error.txt

  **Commit**: YES (group 3)
  - Message: `test(connection): migrate sequence and picard behavior tests`
  - Files: `tests/connection/test_connection_layer_sequence.py`, `tests/connection/test_connection_layer_picard_gate.py`
  - Pre-commit: `pytest tests/connection/test_connection_layer_sequence.py tests/connection/test_connection_layer_picard_gate.py -q`

- [x] 13. Migrate `two_tank_reaction_comparison` example to network API

  **What to do**:
  - Replace manual adapter setup and per-step condition mapping with `ConnectionNetwork` authoring calls.
  - Preserve scenario behavior and key output trends used by existing tests.
  - Keep example readable as canonical user entry point for fast connection setup.

  **Must NOT do**:
  - Do not rely on private process-model stream mutation.
  - Do not silently change example scenario semantics.

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: `playwright` (omitted), `frontend-ui-ux` (omitted)
  - **Skills Evaluated but Omitted**: `git-master` (not needed)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4 (with Tasks 14, 15)
  - **Blocks**: 15
  - **Blocked By**: 9, 9A, 9B, 11

  **References**:
  - `examples/connection_layer/two_tank_reaction_comparison.py` - current verbose baseline to simplify.
  - `tests/connection/test_two_tank_reaction_comparison.py` - parity checks to keep passing.
  - `src/modular_simulation/connection/network.py` - new canonical authoring API.

  **Acceptance Criteria**:
  - [ ] Example runs via network API without manual adapter/private stream setup.
  - [ ] Existing two-tank test checks still pass or are migrated with equivalent assertions.

  **QA Scenarios**:
  ```text
  Scenario: Happy path two-tank example run
    Tool: Bash
    Preconditions: migrated example and test updated
    Steps:
      1. Run: python examples/connection_layer/two_tank_reaction_comparison.py
      2. Run: pytest tests/connection/test_two_tank_reaction_comparison.py -q
      3. Assert script exits successfully and tests pass
    Expected Result: Exit code 0 for both commands
    Failure Indicators: runtime wiring errors or parity assertion failures
    Evidence: .sisyphus/evidence/task-13-two-tank-happy.txt

  Scenario: Failure path invalid endpoint wiring in example helper
    Tool: Bash (pytest)
    Preconditions: negative helper test included
    Steps:
      1. Run: pytest tests/connection/test_two_tank_reaction_comparison.py -k invalid_endpoint -q
      2. Assert example wiring helper raises deterministic message
    Expected Result: targeted negative test passes
    Evidence: .sisyphus/evidence/task-13-two-tank-error.txt
  ```

  **Evidence to Capture**:
  - [ ] task-13-two-tank-happy.txt
  - [ ] task-13-two-tank-error.txt

  **Commit**: YES (group 4)
  - Message: `refactor(example): migrate two tank comparison to network api`
  - Files: `examples/connection_layer/two_tank_reaction_comparison.py`, `tests/connection/test_two_tank_reaction_comparison.py`
  - Pre-commit: `pytest tests/connection/test_two_tank_reaction_comparison.py -q`

- [x] 14. Migrate `pump_causality_demo` to network API

  **What to do**:
  - Rework pump causality example to use the same network authoring flow.
  - Preserve bidirectional causality demonstrations and flow-direction checks.
  - Keep example as a second canonical pattern (boundary + pump + process linkage).

  **Must NOT do**:
  - Do not alter expected causality demonstration behavior.
  - Do not retain dual old/new setup code paths.

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: `playwright` (omitted), `frontend-ui-ux` (omitted)
  - **Skills Evaluated but Omitted**: `git-master` (not needed)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4 (with Tasks 13, 15)
  - **Blocks**: 15
  - **Blocked By**: 9, 9A, 9B, 11

  **References**:
  - `examples/connection_layer/pump_causality_demo.py` - baseline behavior.
  - `tests/connection/test_connection_integration_physics.py` - causality assertions to preserve.
  - `src/modular_simulation/connection/network.py` - authoring API to use.

  **Acceptance Criteria**:
  - [ ] Pump causality example runs through network API.
  - [ ] Causality direction checks remain deterministic.

  **QA Scenarios**:
  ```text
  Scenario: Happy path pump causality run
    Tool: Bash
    Preconditions: migrated pump example complete
    Steps:
      1. Run: python examples/connection_layer/pump_causality_demo.py
      2. Run: pytest tests/connection/test_connection_integration_physics.py -k causality -q
      3. Assert expected causality checks pass
    Expected Result: Exit code 0 and deterministic causality outcomes
    Failure Indicators: flow direction mismatches or unstable outputs
    Evidence: .sisyphus/evidence/task-14-pump-happy.txt

  Scenario: Failure path reversed boundary conditions
    Tool: Bash (pytest)
    Preconditions: reversal test case present
    Steps:
      1. Run: pytest tests/connection/test_connection_integration_physics.py -k reversal -q
      2. Assert signs/pressures swap consistently and deterministically
    Expected Result: targeted tests pass
    Evidence: .sisyphus/evidence/task-14-pump-error.txt
  ```

  **Evidence to Capture**:
  - [ ] task-14-pump-happy.txt
  - [ ] task-14-pump-error.txt

  **Commit**: YES (group 4)
  - Message: `refactor(example): migrate pump causality demo to network api`
  - Files: `examples/connection_layer/pump_causality_demo.py`
  - Pre-commit: `python examples/connection_layer/pump_causality_demo.py`

- [x] 15. Execute hard-switch cleanup and finalize public exports

  **What to do**:
  - Remove legacy adapter/manual wiring usage from active connection path and update exports/docs references.
  - Ensure network API is the single supported path for connection authoring.
  - Verify migration hygiene gate and full suite are green before final merge.

  **Must NOT do**:
  - Do not leave shadow fallback path to old API.
  - Do not remove legacy code before migrated tests/examples are green.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: `playwright` (omitted), `frontend-ui-ux` (omitted)
  - **Skills Evaluated but Omitted**: `git-master` (not needed)

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential finalization in Wave 4
  - **Blocks**: F1, F2, F3, F4
  - **Blocked By**: 5, 9A, 9B, 10, 11, 12, 13, 14

  **References**:
  - `src/modular_simulation/connection/process_interface.py` - legacy adapter surface to sunset.
  - `src/modular_simulation/connection/__init__.py` - public export curation.
  - `tests/connection/test_migration_hygiene_gate.py` - enforced hard-switch policy.

  **Acceptance Criteria**:
  - [ ] Full `pytest tests/connection -q` passes with network API as sole path.
  - [ ] Migration hygiene gate passes and finds zero banned usages.
  - [ ] Public exports/documented examples reference only new API.

  **QA Scenarios**:
  ```text
  Scenario: Happy path full hard-switch verification
    Tool: Bash
    Preconditions: all migration tasks complete
    Steps:
      1. Run: pytest tests/connection -q
      2. Run: pytest tests/connection/test_migration_hygiene_gate.py -q
      3. Assert both commands pass with no legacy token findings
    Expected Result: Exit code 0 for both commands
    Failure Indicators: residual legacy references or failing migrated suites
    Evidence: .sisyphus/evidence/task-15-hard-switch-happy.txt

  Scenario: Failure path reintroduced legacy token
    Tool: Bash (pytest)
    Preconditions: synthetic fixture test for banned token remains in hygiene suite
    Steps:
      1. Run: pytest tests/connection/test_migration_hygiene_gate.py -k banned -q
      2. Assert violation output includes offending token and path
    Expected Result: targeted detection test passes
    Evidence: .sisyphus/evidence/task-15-hard-switch-error.txt
  ```

  **Evidence to Capture**:
  - [ ] task-15-hard-switch-happy.txt
  - [ ] task-15-hard-switch-error.txt

  **Commit**: YES (group 4)
  - Message: `refactor(connection): hard switch to network api`
  - Files: `src/modular_simulation/connection/process_interface.py`, `src/modular_simulation/connection/__init__.py`, `tests/connection/*`, `examples/connection_layer/*`
  - Pre-commit: `pytest tests/connection -q`

---

## Final Verification Wave (MANDATORY)

- [x] F1. **Plan Compliance Audit** - `oracle`
  - Verify every Must Have and Must NOT Have against code and evidence.
  - Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT`.

- [x] F2. **Code Quality Review** - `unspecified-high`
  - Run type/lint/tests; scan for anti-patterns and slop.
  - Output: `Build [PASS/FAIL] | Lint [PASS/FAIL] | Tests [N/N] | VERDICT`.

- [x] F3. **Real QA Scenario Execution** - `unspecified-high`
  - Execute all task QA scenarios exactly (including snapshot/resume continuity and failed-restore rollback); capture evidence files.
  - Output: `Scenarios [N/N pass] | Integration [N/N] | Edge Cases [N] | VERDICT`.

- [x] F4. **Scope Fidelity Check** - `deep`
  - Compare final diff against task specs; detect missing/scope-creep work.
  - Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | VERDICT`.

---

## Commit Strategy

- **1**: `feat(connection): add graph-first topology and network facade`
- **2**: `feat(connection): bridge graph runtime and add snapshot/restore persistence contract`
- **3**: `test(connection): migrate parity and integration suites to network API`
- **4**: `refactor(connection): remove legacy adapter/manual wiring path`

---

## Success Criteria

### Verification Commands
```bash
pytest tests/connection -q
pytest tests/connection/test_runtime_mutation_contract.py -q
pytest tests/connection/test_runtime_persistence_contract.py -q
python examples/connection_layer/two_tank_reaction_comparison.py
python examples/connection_layer/pump_causality_demo.py
```

### Final Checklist
- [x] All Must Have items satisfied.
- [x] All Must NOT Have items absent.
- [x] All migrated tests/examples pass with new API only.
- [x] Runtime reconfiguration tests pass (including continuous-to-batch transition continuity).
- [x] Runtime persistence tests pass (including queue continuity and failed-restore atomicity).
- [x] Final verification wave returns APPROVE on all four tracks.

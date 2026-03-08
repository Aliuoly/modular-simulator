# HeaterCooler Controller-Driven Migration

## TL;DR
> **Summary**: Remove HeaterCooler's internal target-temperature setpoint contract and make temperature regulation exclusively external through `ControlElement` + controller wiring.
> **Deliverables**:
> - HeaterCooler becomes duty-driven only (breaking API update)
> - Controller wiring path updated to drive HeaterCooler via MV tag
> - Tests/examples migrated to new contract and quality gates passing
> **Effort**: Medium
> **Parallel**: YES - 2 waves
> **Critical Path**: Task 1 -> Task 2 -> Task 5 -> Task 9

## Context
### Original Request
User wants to remove HeaterCooler's "arbitrary setpoint as an attribute" and use control element -> controller setup instead.

### Interview Summary
- Migration strategy selected: **breaking change now**.
- Scope focus: HeaterCooler + required wiring/tests for controller-driven behavior.
- Default applied: tests-after strategy with pytest-based verification.
- Default applied: update direct repo callsites (tests/examples) that use `target_temperature_setpoint` to avoid stale API usage.

### Metis Review (gaps addressed)
- Guardrail adopted: no broad refactor of other unit-process setpoint conventions (`flash_drum`, `cstr`, etc.).
- Guardrail adopted: preserve physical edge-case semantics (`zero-flow + nonzero duty` error, pressure floor, composition validation).
- Guardrail adopted: keep runtime controller activation/binding semantics unchanged.
- Added verification focus on subsystem-local tag validation and runtime rollback paths.

## Work Objectives
### Core Objective
Eliminate HeaterCooler internal temperature setpoint control and standardize closed-loop temperature regulation through existing control-system architecture.

### Deliverables
- Updated HeaterCooler public/state contract without `target_temperature_setpoint` and internal temperature-mode branch.
- Controller-driven integration path using HeaterCooler MV tag (`duty_setpoint`) for temperature control.
- Updated unit/integration tests and flowsheet examples.
- Passing lint/typecheck/targeted-test/smoke checks.

### Definition of Done (verifiable conditions with commands)
- `uv run python -m pytest -q tests/unit_process/test_layer4_heater_cooler.py`
- `uv run python -m pytest -q tests/unit_process/test_flowsheet_integration.py`
- `uv run python -m pytest -q tests/connection/test_subsystem_scoped_installers.py`
- `uv run python -m pytest -q tests/components/test_controller_wiring_api.py`
- `uv run python -m ruff check src tests`
- `uv run --with mypy python -m mypy src`
- `uv run python -m pytest -q tests -k "smoke or minimal"`
- `uv run python - <<'PY'\nfrom modular_simulation.unit_processes import HeaterCooler\nh=HeaterCooler()\nassert hasattr(h, "duty_setpoint")\nassert not hasattr(h, "target_temperature_setpoint")\nprint("heatercooler contract ok")\nPY`

### Must Have
- Breaking change is explicit and complete: no hidden fallback/deprecation branch for `target_temperature_setpoint`.
- HeaterCooler remains physically valid for duty-driven simulation and preserves current non-control guardrails.
- Controller path uses existing `ControlElement`/`AbstractController` abstractions (no parallel control subsystem).
- Updated tests prove happy-path and failure/edge behavior under controller-driven setup.

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- Do not refactor other unit process setpoint APIs.
- Do not add implicit compatibility shims for removed HeaterCooler fields.
- Do not weaken subsystem/local tag validation or runtime rollback behavior.
- Do not rely on manual QA; every claim must be command-verifiable.

## Verification Strategy
> ZERO HUMAN INTERVENTION - all verification is agent-executed.
- Test decision: tests-after + pytest.
- QA policy: every task includes happy path and failure/edge scenario with evidence artifacts.
- Evidence: `.sisyphus/evidence/task-{N}-{slug}.{ext}`

## Execution Strategy
### Parallel Execution Waves
> Target: 5-8 tasks per wave. Shared contracts first, then migrations.

Wave 1: contract + core behavior + direct test migrations (Tasks 1-5)
Wave 2: example migrations + regression guardrails + quality sweep (Tasks 6-9)

### Dependency Matrix (full, all tasks)
- Task 1 blocks Tasks 2, 4, 5, 6, 7.
- Task 2 blocks Tasks 4, 5.
- Task 3 can run after Task 1; blocks Task 5.
- Task 4 depends on Tasks 1-2.
- Task 5 depends on Tasks 1-3.
- Task 6 depends on Task 1.
- Task 7 depends on Task 1.
- Task 8 depends on Tasks 5 and 7.
- Task 9 depends on Tasks 4, 5, 6, 7, 8.

### Agent Dispatch Summary (wave -> task count -> categories)
- Wave 1 -> 5 tasks -> unspecified-high x3, quick x2
- Wave 2 -> 4 tasks -> quick x2, unspecified-high x1, deep x1

## TODOs
> Implementation + Test = ONE task. Never separate.
> Every task includes Agent Profile + Parallelization + QA Scenarios.

- [ ] 1. Remove HeaterCooler temperature-setpoint API surface

  **What to do**: Delete `target_temperature_setpoint` and temperature-mode contract from `HeaterCooler` state definitions and constructor-facing schema. Remove related mode helpers/constants only if they are HeaterCooler-local and unused after refactor. Keep `duty_setpoint`, pressure-drop handling, composition validation, and stream adapter APIs intact.
  **Must NOT do**: Do not add compatibility aliases, deprecated shadow fields, or hidden fallback parsing for `target_temperature_setpoint`.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: cross-cutting API contract surgery in a core unit process class.
  - Skills: `[]` - no special skill required.
  - Omitted: `["playwright"]` - backend-only change, no browser workflow.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 2, 4, 5, 6, 7 | Blocked By: none

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `src/modular_simulation/unit_processes/heater_cooler.py:90` - current state model fields include mode + setpoint contract.
  - Pattern: `src/modular_simulation/unit_processes/heater_cooler.py:121` - `target_temperature_setpoint` declaration to remove.
  - Pattern: `src/modular_simulation/unit_processes/heater_cooler.py:29` - mode constants/helpers currently tied to dual-mode design.
  - API/Type: `src/modular_simulation/thermodynamics/algebraic_process_model.py:1` - maintain base model contract compatibility.
  - Test: `tests/unit_process/test_layer4_heater_cooler.py:91` - old temperature-mode constructor usage to migrate.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `uv run python - <<'PY'\nfrom modular_simulation.unit_processes import HeaterCooler\nh=HeaterCooler()\nassert hasattr(h, "duty_setpoint")\nassert not hasattr(h, "target_temperature_setpoint")\nprint("task1-contract-ok")\nPY`
  - [ ] `uv run python - <<'PY'\nfrom modular_simulation.unit_processes import HeaterCooler\ntry:\n    HeaterCooler(target_temperature_setpoint=320.0)\nexcept TypeError:\n    print("task1-removed-arg-ok")\nelse:\n    raise SystemExit("target_temperature_setpoint still accepted")\nPY`

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Contract happy path
    Tool: Bash
    Steps: Run the task1-contract-ok inline Python command and capture stdout.
    Expected: Output contains "task1-contract-ok" and command exits 0.
    Evidence: .sisyphus/evidence/task-1-heatercooler-contract.log

  Scenario: Removed-argument failure path
    Tool: Bash
    Steps: Run the task1-removed-arg-ok inline Python command.
    Expected: Constructor with removed kwarg raises TypeError; output contains "task1-removed-arg-ok".
    Evidence: .sisyphus/evidence/task-1-heatercooler-contract-error.log
  ```

  **Commit**: YES | Message: `refactor(heatercooler): remove internal temperature setpoint contract` | Files: `src/modular_simulation/unit_processes/heater_cooler.py`, `tests/unit_process/test_layer4_heater_cooler.py`

- [ ] 2. Refactor HeaterCooler execution paths to duty-driven behavior only

  **What to do**: Update `calculate_algebraic_values` and `step` so HeaterCooler behavior is driven solely by `duty_setpoint` (plus existing inlet state and pressure drop). Remove temperature-mode branches while preserving no-flow guard (`near-zero flow + nonzero duty`), pressure floor, composition checks, and property-package flash usage semantics.
  **Must NOT do**: Do not change physical sign conventions for duty or remove existing error conditions around invalid finite values and flow edge cases.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: sensitive process-model behavior change with thermodynamic implications.
  - Skills: `[]` - no additional skills required.
  - Omitted: `["frontend-ui-ux"]` - no UI or frontend surface.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 4, 5 | Blocked By: 1

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `src/modular_simulation/unit_processes/heater_cooler.py:249` - algebraic value computation currently branches by mode.
  - Pattern: `src/modular_simulation/unit_processes/heater_cooler.py:296` - no-flow + nonzero-duty guard to preserve.
  - Pattern: `src/modular_simulation/unit_processes/heater_cooler.py:313` - thermodynamic `step` branch logic to simplify.
  - Pattern: `src/modular_simulation/unit_processes/heater_cooler.py:371` - duty finalization from enthalpy delta must remain coherent.
  - Test: `tests/unit_process/test_layer4_heater_cooler.py:63` - duty-mode baseline expectations.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `uv run python -m pytest -q tests/unit_process/test_layer4_heater_cooler.py -k "duty or pressure or zero_duty"`
  - [ ] `uv run python -m pytest -q tests/unit_process/test_layer4_heater_cooler.py -k "no_flow or negative_flow or validation"`

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path energy and pressure behavior
    Tool: Bash
    Steps: Run pytest selection `-k "duty or pressure or zero_duty"` for heater_cooler unit tests.
    Expected: Exit code 0 with all selected tests passing.
    Evidence: .sisyphus/evidence/task-2-heatercooler-duty-only.log

  Scenario: Failure/edge path validation
    Tool: Bash
    Steps: Run pytest selection `-k "no_flow or negative_flow or validation"`.
    Expected: Tests assert graceful failures for invalid inputs and still pass.
    Evidence: .sisyphus/evidence/task-2-heatercooler-duty-only-error.log
  ```

  **Commit**: YES | Message: `refactor(heatercooler): make model duty-driven only` | Files: `src/modular_simulation/unit_processes/heater_cooler.py`, `tests/unit_process/test_layer4_heater_cooler.py`

- [ ] 3. Rebind control topology to HeaterCooler duty MV in integration path

  **What to do**: In flowsheet integration tests, replace controller->MV wiring from `target_temperature_setpoint` to `duty_setpoint` and keep CV measured via sensor alias. Update trajectory/bounds to physically reasonable duty units and preserve comparative assertions that controller-enabled run alters downstream thermal behavior.
  **Must NOT do**: Do not bypass control system by writing HeaterCooler fields directly in test loops; retain `ControlElement` + `PIDController` path.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: integration-level control-loop behavior rewrite.
  - Skills: `[]` - built-in project patterns are sufficient.
  - Omitted: `["playwright"]` - non-UI simulation test.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 8, 9 | Blocked By: 1

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `tests/unit_process/test_flowsheet_integration.py:30` - current HeaterCooler temperature-mode construction.
  - Pattern: `tests/unit_process/test_flowsheet_integration.py:70` - current `ControlElement(mv_tag="target_temperature_setpoint")` wiring to replace.
  - Pattern: `tests/unit_process/test_flowsheet_integration.py:52` - sensor alias pattern for CV tag.
  - Pattern: `src/modular_simulation/components/control_system/control_element.py:32` - MV tag contract used by control element.
  - Pattern: `src/modular_simulation/components/control_system/abstract_controller.py:31` - CV tag contract.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `uv run python -m pytest -q tests/unit_process/test_flowsheet_integration.py`
  - [ ] `uv run python - <<'PY'\nfrom pathlib import Path\ntext=Path("tests/unit_process/test_flowsheet_integration.py").read_text()\nassert 'mv_tag="duty_setpoint"' in text\nassert 'mv_tag="target_temperature_setpoint"' not in text\nprint("task3-integration-control-ok")\nPY`

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path controller influences process
    Tool: Bash
    Steps: Run full `test_flowsheet_integration.py` and then the inline comparative script.
    Expected: Pytest passes; script prints "task3-integration-control-ok".
    Evidence: .sisyphus/evidence/task-3-flowsheet-control.log

  Scenario: Failure/edge path invalid local MV tag
    Tool: Bash
    Steps: Run `uv run python -m pytest -q tests/connection/test_subsystem_scoped_installers.py -k "invalid_controller_cv_tag"`.
    Expected: Test passes by asserting `ControllerConfigurationError` when tag resolution is invalid.
    Evidence: .sisyphus/evidence/task-3-flowsheet-control-error.log
  ```

  **Commit**: YES | Message: `test(integration): drive heatercooler via duty mv control loop` | Files: `tests/unit_process/test_flowsheet_integration.py`

- [ ] 4. Migrate HeaterCooler unit tests to post-setpoint contract

  **What to do**: Replace/remove tests that rely on `mode="temperature"` and `target_temperature_setpoint`. Add focused coverage for duty-driven operation, no-flow guard, and constructor contract removal behavior. Keep deterministic fake property package usage.
  **Must NOT do**: Do not drop negative-path tests; replace them with equivalent contract/validation assertions rather than deleting coverage.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: single-file test migration with explicit expected behavior.
  - Skills: `[]` - no special skill required.
  - Omitted: `["git-master"]` - no git investigation needed for execution.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 9 | Blocked By: 1, 2

  **References** (executor has NO interview context - be exhaustive):
  - Test: `tests/unit_process/test_layer4_heater_cooler.py:91` - old temperature-mode test to replace.
  - Test: `tests/unit_process/test_layer4_heater_cooler.py:63` - duty-mode baseline test structure.
  - Pattern: `src/modular_simulation/unit_processes/heater_cooler.py:196` - finite validation fields to keep aligned with tests.
  - Pattern: `src/modular_simulation/unit_processes/heater_cooler.py:296` - no-flow duty error semantics.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `uv run python -m pytest -q tests/unit_process/test_layer4_heater_cooler.py`
  - [ ] `uv run python - <<'PY'\nfrom modular_simulation.unit_processes import HeaterCooler\ntry:\n    HeaterCooler(target_temperature_setpoint=320.0)\nexcept TypeError:\n    print("task4-removed-arg-ok")\nelse:\n    raise SystemExit("removed arg still accepted")\nPY`

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path unit behavior
    Tool: Bash
    Steps: Run full heater_cooler unit test file.
    Expected: Exit code 0 and all tests pass.
    Evidence: .sisyphus/evidence/task-4-heatercooler-tests.log

  Scenario: Failure/edge path contract and validation checks
    Tool: Bash
    Steps: Run targeted `-k "removed_arg or no_flow or validation"` selection.
    Expected: Tests pass and explicitly assert failure behavior where expected.
    Evidence: .sisyphus/evidence/task-4-heatercooler-tests-error.log
  ```

  **Commit**: YES | Message: `test(unit): update heatercooler tests for duty-only api` | Files: `tests/unit_process/test_layer4_heater_cooler.py`

- [ ] 5. Preserve runtime/subsystem controller wiring guarantees after MV contract shift

  **What to do**: Validate and, if needed, minimally update tests that assert controller activation rules, subsystem-local tag checks, and rollback behavior so they remain aligned when HeaterCooler is actuated via `duty_setpoint`. Add a focused regression test if no existing test explicitly covers HeaterCooler MV-tag activation path.
  **Must NOT do**: Do not relax validation expectations or change error classes/messages beyond what is required by the HeaterCooler MV contract update.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: targeted test/contract alignment using existing wiring framework.
  - Skills: `[]` - project-local patterns are sufficient.
  - Omitted: `["playwright"]` - no browser-related behavior.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 8, 9 | Blocked By: 1, 2

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `src/modular_simulation/framework/system.py:780` - activation validation sequence (input, actuator, type checks).
  - Pattern: `src/modular_simulation/framework/system.py:805` - actuator tag must map to existing control element MV tag.
  - Pattern: `src/modular_simulation/connection/subsystem_descriptor.py:134` - controller CV local-tag validation.
  - Pattern: `src/modular_simulation/connection/subsystem_descriptor.py:143` - control element MV local-tag validation.
  - Test: `tests/components/test_controller_wiring_api.py:141` - runtime API happy path and rollback semantics.
  - Test: `tests/connection/test_subsystem_scoped_installers.py:42` - subsystem-scoped sensor/controller/element setup.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `uv run python -m pytest -q tests/components/test_controller_wiring_api.py`
  - [ ] `uv run python -m pytest -q tests/connection/test_subsystem_scoped_installers.py`

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path runtime controller activation
    Tool: Bash
    Steps: Run `tests/components/test_controller_wiring_api.py`.
    Expected: Runtime request ordering and actuator response assertions pass.
    Evidence: .sisyphus/evidence/task-5-runtime-wiring.log

  Scenario: Failure/edge path rollback and invalid tag checks
    Tool: Bash
    Steps: Run `tests/components/test_controller_wiring_api.py -k "rollback"` and `tests/connection/test_subsystem_scoped_installers.py -k "invalid"`.
    Expected: Tests pass while asserting expected configuration errors and rollback behavior.
    Evidence: .sisyphus/evidence/task-5-runtime-wiring-error.log
  ```

  **Commit**: YES | Message: `test(control): keep wiring validation guarantees with heater mv changes` | Files: `tests/components/test_controller_wiring_api.py`, `tests/connection/test_subsystem_scoped_installers.py`

- [ ] 6. Migrate easy/entrypoint examples to controller-driven HeaterCooler usage

  **What to do**: Update easy examples and demo flows to stop passing `target_temperature_setpoint` and to use either duty-only open-loop setup or explicit controller wiring (preferred when example intent is temperature control). Cover: `easy_2_heater_flash.py`, `easy_3_dual_feed_heat_exchanger.py`, and `flowsheet_demo.py`.
  **Must NOT do**: Do not silently change scenario intent; if an example previously demonstrated temperature regulation, keep that behavior via controller architecture.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: deterministic callsite migration in a limited file set.
  - Skills: `[]` - no extra skills required.
  - Omitted: `["frontend-ui-ux"]` - example scripts are backend simulations.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 9 | Blocked By: 1

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `examples/unit_process_flowsheet/easy_2_heater_flash.py:12` - direct temperature-setpoint constructor use.
  - Pattern: `tests/unit_process/test_flowsheet_integration.py:52` - sensor + controller wiring pattern to mirror where needed.
  - Pattern: `tests/unit_process/test_flowsheet_integration.py:70` - control-element MV wiring shape.
  - API/Type: `src/modular_simulation/components/control_system/control_element.py:32` - `mv_tag` contract.
  - API/Type: `src/modular_simulation/components/control_system/abstract_controller.py:31` - `cv_tag` contract.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `uv run python -m pytest -q tests/unit_process/test_flowsheet_integration.py`
  - [ ] `uv run python -m compileall examples/unit_process_flowsheet/easy_2_heater_flash.py examples/unit_process_flowsheet/easy_3_dual_feed_heat_exchanger.py examples/unit_process_flowsheet/flowsheet_demo.py`

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path example syntax and integration intent
    Tool: Bash
    Steps: Run compileall command for the three easy/demo examples; run full flowsheet integration test file.
    Expected: compileall returns 0 and flowsheet integration tests pass.
    Evidence: .sisyphus/evidence/task-6-easy-examples.log

  Scenario: Failure/edge path stale-API guard
    Tool: Bash
    Steps: Run `uv run python - <<'PY'\nfrom pathlib import Path\nfiles=[\n"examples/unit_process_flowsheet/easy_2_heater_flash.py",\n"examples/unit_process_flowsheet/easy_3_dual_feed_heat_exchanger.py",\n"examples/unit_process_flowsheet/flowsheet_demo.py",\n]\nfor f in files:\n    assert "target_temperature_setpoint" not in Path(f).read_text(), f\nprint("task6-easy-examples-ok")\nPY`.
    Expected: Output contains "task6-easy-examples-ok" and exits 0.
    Evidence: .sisyphus/evidence/task-6-easy-examples-error.log
  ```

  **Commit**: YES | Message: `chore(examples): migrate easy heater flows to controller-driven api` | Files: `examples/unit_process_flowsheet/easy_2_heater_flash.py`, `examples/unit_process_flowsheet/easy_3_dual_feed_heat_exchanger.py`, `examples/unit_process_flowsheet/flowsheet_demo.py`

- [ ] 7. Migrate complex flowsheet examples that still reference target temperature setpoint

  **What to do**: Update complex examples that reference `target_temperature_setpoint` (`complex_5`, `complex_6`, `complex_7`, `complex_8`) to the new HeaterCooler contract. Where closed-loop temperature behavior is intended, use sensor/controller/control-element wiring with MV=`duty_setpoint`; otherwise convert to explicit duty-driven setup.
  **Must NOT do**: Do not remove process steps or simplify chemical/process topology just to avoid control migration.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: multi-file migration with behavior-preservation risk.
  - Skills: `[]` - existing examples and tests provide sufficient patterns.
  - Omitted: `["playwright"]` - script-only examples.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 9 | Blocked By: 1

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `examples/unit_process_flowsheet/complex_5_dual_feed_blend_reaction.py:1` - contains HeaterCooler setpoint callsite.
  - Pattern: `examples/unit_process_flowsheet/complex_6_ammonia_recycle_loop.py:1` - contains setpoint usage (possibly indirect config).
  - Pattern: `examples/unit_process_flowsheet/complex_7_unipol_simplified_purge_bin.py:1` - contains setpoint usage (possibly indirect config).
  - Pattern: `examples/unit_process_flowsheet/complex_8_pressure_flash_recovery.py:1` - explicit temperature-mode constructor pattern.
  - Pattern: `tests/unit_process/test_flowsheet_integration.py:62` - controller construction values for reference.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `uv run python -m compileall examples/unit_process_flowsheet/complex_5_dual_feed_blend_reaction.py examples/unit_process_flowsheet/complex_6_ammonia_recycle_loop.py examples/unit_process_flowsheet/complex_7_unipol_simplified_purge_bin.py examples/unit_process_flowsheet/complex_8_pressure_flash_recovery.py`
  - [ ] `uv run python - <<'PY'\nimport pathlib\npaths=[\n"examples/unit_process_flowsheet/complex_5_dual_feed_blend_reaction.py",\n"examples/unit_process_flowsheet/complex_6_ammonia_recycle_loop.py",\n"examples/unit_process_flowsheet/complex_7_unipol_simplified_purge_bin.py",\n"examples/unit_process_flowsheet/complex_8_pressure_flash_recovery.py",\n]\nfor p in paths:\n    text=pathlib.Path(p).read_text()\n    assert "target_temperature_setpoint" not in text, p\nprint("task7-complex-examples-ok")\nPY`

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path compile checks
    Tool: Bash
    Steps: Run compileall command over complex example files.
    Expected: Exit code 0 for all files.
    Evidence: .sisyphus/evidence/task-7-complex-examples.log

  Scenario: Failure/edge path stale-token detection
    Tool: Bash
    Steps: Run inline Python assertion script that fails if any complex example still contains removed token.
    Expected: Output contains "task7-complex-examples-ok" and exits 0.
    Evidence: .sisyphus/evidence/task-7-complex-examples-error.log
  ```

  **Commit**: YES | Message: `chore(examples): migrate complex heater usages off removed setpoint` | Files: `examples/unit_process_flowsheet/complex_5_dual_feed_blend_reaction.py`, `examples/unit_process_flowsheet/complex_6_ammonia_recycle_loop.py`, `examples/unit_process_flowsheet/complex_7_unipol_simplified_purge_bin.py`, `examples/unit_process_flowsheet/complex_8_pressure_flash_recovery.py`

- [ ] 8. Enforce repository-level removal and control-path consistency checks

  **What to do**: Add/adjust regression assertions so the repo no longer depends on `target_temperature_setpoint` for HeaterCooler workflows and control-path tests continue to assert proper activation order, rollback, and subsystem-local tag validation. Use focused grep/script checks plus existing runtime test suites.
  **Must NOT do**: Do not make this a global ban for unrelated unit processes (`flash_temperature_setpoint`, `volume_setpoint`, etc.). Scope check to HeaterCooler token and callsites.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: cross-repo consistency verification with strict scope boundaries.
  - Skills: `[]` - no additional skills required.
  - Omitted: `["playwright"]` - backend-only validation.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 9 | Blocked By: 3, 5

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `src/modular_simulation/unit_processes/heater_cooler.py` - removed field anchor for consistency checks.
  - Pattern: `tests/unit_process/test_flowsheet_integration.py:70` - MV tag mapping expected to be `duty_setpoint` post-migration.
  - Pattern: `src/modular_simulation/framework/system.py:789` - activation preconditions that must still hold.
  - Pattern: `src/modular_simulation/connection/subsystem_descriptor.py:143` - local MV tag validation path.
  - Test: `tests/components/test_controller_wiring_api.py:188` - rollback failure scenario reference.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `uv run python - <<'PY'\nimport pathlib\nroot=pathlib.Path('.')\nviolations=[]\nfor p in root.rglob('*.py'):\n    txt=p.read_text(errors='ignore')\n    if 'target_temperature_setpoint' in txt and 'flash_temperature_setpoint' not in txt:\n        if 'heater_cooler' in p.as_posix() or 'unit_process_flowsheet' in p.as_posix() or 'test_' in p.name:\n            violations.append(p.as_posix())\nassert not violations, violations\nprint('task8-repo-consistency-ok')\nPY`
  - [ ] `uv run python -m pytest -q tests/components/test_controller_wiring_api.py tests/connection/test_subsystem_scoped_installers.py`

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path consistency sweep
    Tool: Bash
    Steps: Run inline repository consistency script.
    Expected: Prints "task8-repo-consistency-ok" and exits 0.
    Evidence: .sisyphus/evidence/task-8-consistency.log

  Scenario: Failure/edge path wiring regressions
    Tool: Bash
    Steps: Run targeted wiring test pair.
    Expected: Both test files pass, including rollback and invalid-tag assertions.
    Evidence: .sisyphus/evidence/task-8-consistency-error.log
  ```

  **Commit**: YES | Message: `test(regression): enforce heater setpoint removal and wiring integrity` | Files: `tests/components/test_controller_wiring_api.py`, `tests/connection/test_subsystem_scoped_installers.py`, `tests/unit_process/test_flowsheet_integration.py`

- [ ] 9. Run full quality wave and collect evidence bundle

  **What to do**: Execute final repo checks in CI-equivalent order (ruff, mypy, targeted suites, smoke/minimal). Capture outputs as evidence artifacts and resolve all failures without expanding scope beyond HeaterCooler migration.
  **Must NOT do**: Do not skip failing checks; do not broaden refactors to unrelated modules in order to silence pre-existing warnings unless directly blocking this scope.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: multi-command verification and final stabilization.
  - Skills: `[]` - standard CLI testing workflow.
  - Omitted: `["git-master"]` - no history surgery required.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: none | Blocked By: 4, 5, 6, 7, 8

  **References** (executor has NO interview context - be exhaustive):
  - CI Pattern: `.github/workflows/ci.yml` - quality job order and commands.
  - Tooling: `pyproject.toml` - pytest config (`tests` path).
  - Tooling: `pyproject.toml` - mypy section.
  - Tooling: `pyproject.toml` - ruff config anchor.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `uv run python -m ruff check src tests`
  - [ ] `uv run --with mypy python -m mypy src`
  - [ ] `uv run python -m pytest -q tests/unit_process/test_layer4_heater_cooler.py tests/unit_process/test_flowsheet_integration.py tests/connection/test_subsystem_scoped_installers.py tests/components/test_controller_wiring_api.py`
  - [ ] `uv run python -m pytest -q tests -k "smoke or minimal"`

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path quality gate completion
    Tool: Bash
    Steps: Run ruff, mypy, targeted pytest bundle, then smoke/minimal suite.
    Expected: Every command exits 0.
    Evidence: .sisyphus/evidence/task-9-quality-wave.log

  Scenario: Failure/edge path immediate fail-fast behavior
    Tool: Bash
    Steps: Intentionally run one targeted command first (e.g., mypy) and verify nonzero exits are surfaced, then fix and rerun full sequence.
    Expected: Initial failure (if any) is explicit; final rerun exits 0 across all commands.
    Evidence: .sisyphus/evidence/task-9-quality-wave-error.log
  ```

  **Commit**: NO | Message: `n/a` | Files: `n/a`

## Final Verification Wave (4 parallel agents, ALL must APPROVE)
- [ ] F1. Plan Compliance Audit - oracle
- [ ] F2. Code Quality Review - unspecified-high
- [ ] F3. Real Manual QA - unspecified-high (+ playwright if UI)
- [ ] F4. Scope Fidelity Check - deep

## Commit Strategy
- Commit in 4 logical groups:
- Group A: HeaterCooler contract/behavior refactor.
- Group B: Unit/integration test migrations.
- Group C: Example updates.
- Group D: Final quality/cleanup if needed.
- Use conventional commits with explicit breaking marker in first commit body.

## Success Criteria
- No code path or test depends on `target_temperature_setpoint`.
- HeaterCooler control is performed through controller->control-element->MV wiring.
- All listed verification commands pass in CI-equivalent environment.
- Scope remains HeaterCooler-focused with no collateral setpoint API rewrites elsewhere.

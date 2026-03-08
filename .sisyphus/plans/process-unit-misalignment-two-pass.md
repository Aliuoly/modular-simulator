# Process Unit Misalignment Two-Pass Audit

## TL;DR
> **Summary**: Execute a decision-complete two-pass audit of all process units: Pass 1 for control-contract alignment, Pass 2 for broader model-consistency mismatches.
> **Deliverables**:
> - Full unit-by-unit misalignment matrix with evidence
> - Severity-ranked findings split by pass assignment
> - Remediation-ready backlog and guardrail checklist
> **Effort**: Large
> **Parallel**: YES - 3 waves
> **Critical Path**: Task 1 -> Task 2 -> Task 5 -> Task 9 -> Task 11

## Context
### Original Request
User asked to identify all other misalignments in the process unit library after HeaterCooler setpoint architecture mismatch.

### Interview Summary
- User selected **Two-pass approach**.
- Pass 1 scope: control-contract consistency (setpoint embedding, mode selectors, controller-readiness).
- Pass 2 scope: broader process-model consistency (naming, validation, edge-case semantics).
- This plan is audit/remediation-planning focused (inventory-first), not immediate full code refactor.

### Metis Review (gaps addressed)
- Added `ConversionReactor` and `ShortcutDistillation` to explicit pass-assignment review.
- Added pass-boundary guardrails to prevent control-contract work from drifting into physics changes.
- Added runtime mutation/rollback parity checks (controller path, not sensor-only parity).

## Work Objectives
### Core Objective
Produce a complete, reproducible, severity-ranked misalignment inventory for all process units, with explicit pass ownership and execution-ready remediation sequencing.

### Deliverables
- `pass1-control-contract-matrix` (all units + classification + evidence paths).
- `pass2-consistency-matrix` (naming/validation/edge-case mismatches + evidence).
- Prioritized remediation backlog with guardrails and dependency order.
- Verification evidence bundle proving reproducibility.

### Definition of Done (verifiable conditions with commands)
- `uv run python -m pytest -q tests/unit_process/test_layer4_heater_cooler.py tests/unit_process/test_layer4_flash_drum.py tests/unit_process/test_layer4_conversion_reactor.py`
- `uv run python -m pytest -q tests/components/test_controller_wiring_api.py tests/connection/test_subsystem_scoped_installers.py`
- `uv run python -m pytest -q tests/unit_process/test_layer4_cstr.py tests/unit_process/test_layer4_pfr.py tests/unit_process/test_layer4_distillation.py`
- `uv run python -m pytest -q tests/connection/test_runtime_mutation_contract.py tests/connection/test_transaction_atomicity.py`
- `uv run python -m ruff check src tests`
- `uv run --with mypy python -m mypy src`

### Must Have
- Every unit in `src/modular_simulation/unit_processes` is classified in both passes.
- Every finding includes exact file evidence and severity rationale.
- Pass 1 and Pass 2 boundaries are explicit and enforced.
- Runtime control/wiring invariants are verified against existing controller runtime tests.

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- Do not skip low-risk units; absence of issue must still be explicitly recorded.
- Do not mix pass findings into one unstructured list.
- Do not propose physics-law changes in Pass 1.
- Do not create findings without direct source/test evidence.

## Verification Strategy
> ZERO HUMAN INTERVENTION - all verification is agent-executed.
- Test decision: tests-after (audit-first + targeted regression checks).
- QA policy: each task includes happy + failure/edge scenario with evidence artifacts.
- Evidence: `.sisyphus/evidence/task-{N}-{slug}.{ext}`

## Execution Strategy
### Parallel Execution Waves
> Target: 5-8 tasks per wave with strict pass boundaries.

Wave 1 (Pass 1 discovery): Tasks 1-5
Wave 2 (Pass 2 discovery): Tasks 6-9
Wave 3 (synthesis + verification): Tasks 10-11

### Dependency Matrix (full, all tasks)
- Task 1 blocks Tasks 2, 3, 4.
- Task 2 blocks Task 5.
- Task 3 blocks Task 5.
- Task 4 blocks Task 5.
- Task 5 blocks Tasks 6, 10.
- Task 6 blocks Tasks 7, 8.
- Task 7 blocks Task 9.
- Task 8 blocks Task 9.
- Task 9 blocks Task 10.
- Task 10 blocks Task 11.
- Task 11 blocks final verification wave.

### Agent Dispatch Summary (wave -> task count -> categories)
- Wave 1 -> 5 tasks -> deep x2, unspecified-high x2, quick x1
- Wave 2 -> 4 tasks -> deep x1, unspecified-high x2, quick x1
- Wave 3 -> 2 tasks -> writing x1, unspecified-high x1

## TODOs
> Implementation + Test = ONE task. Never separate.
> Every task includes Agent Profile + Parallelization + QA Scenarios.

- [x] 1. Build canonical process-unit inventory and pass rubric

  **What to do**: Enumerate every unit in `src/modular_simulation/unit_processes` and create a canonical inventory table with columns: `unit`, `class`, `ports`, `control-surface candidates`, `pass1 inclusion`, `pass2 inclusion`, `justification`. Define pass-assignment rules explicitly: Pass 1 includes units with mode selectors, setpoint fields, or controller-binding dependency; Pass 2 includes naming/validation/semantic consistency checks for all units.
  **Must NOT do**: Do not infer pass assignment without concrete source evidence.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: deterministic inventory and rubric setup.
  - Skills: `[]` - no additional skills required.
  - Omitted: `["playwright"]` - non-UI task.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 2, 3, 4 | Blocked By: none

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `src/modular_simulation/unit_processes` - authoritative unit process directory.
  - Pattern: `src/modular_simulation/unit_processes/heater_cooler.py` - pass1 archetype (mode + setpoint coupling).
  - Pattern: `src/modular_simulation/unit_processes/flash_drum.py` - pass1 archetype (thermal mode + setpoint).
  - Pattern: `src/modular_simulation/unit_processes/cstr.py` - pass1 candidate (internal setpoint-style level loop).
  - Pattern: `src/modular_simulation/unit_processes/conversion_reactor.py` - must be explicitly classified (Metis hotspot add).

  **Acceptance Criteria** (agent-executable only):
  - [ ] `uv run python - <<'PY'\nfrom pathlib import Path\nbase=Path('src/modular_simulation/unit_processes')\nunits=sorted([p.name for p in base.glob('*.py') if p.name!='__init__.py'])\nassert units, 'no units found'\nprint('\n'.join(units))\nprint('task1-inventory-ok')\nPY`
  - [ ] `uv run python - <<'PY'\nfrom pathlib import Path\nrequired={'heater_cooler.py','flash_drum.py','cstr.py','conversion_reactor.py','pfr.py','pump.py','valve.py','splitter.py','heat_exchanger.py','shortcut_distillation.py','component_separator.py','mixer.py'}\nunits={p.name for p in Path('src/modular_simulation/unit_processes').glob('*.py')}\nmissing=required-units\nassert not missing, missing\nprint('task1-rubric-base-ok')\nPY`

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path full inventory generation
    Tool: Bash
    Steps: Run task1 inventory script and persist output table artifact.
    Expected: Output includes all unit files and prints "task1-inventory-ok".
    Evidence: .sisyphus/evidence/task-1-unit-inventory.log

  Scenario: Failure/edge path missing-unit detection
    Tool: Bash
    Steps: Run required-set assertion script.
    Expected: Script exits 0 and prints "task1-rubric-base-ok"; if any required unit missing it fails with filename list.
    Evidence: .sisyphus/evidence/task-1-unit-inventory-error.log
  ```

  **Commit**: YES | Message: `docs(audit): add canonical process-unit inventory rubric` | Files: `.sisyphus/evidence/task-1-unit-inventory.log`, `.sisyphus/evidence/task-1-unit-inventory-error.log`

- [x] 2. Extract Pass 1 control-contract surfaces per unit

  **What to do**: For each unit file, extract fields and metadata markers (`T.CONTROLLED`, `T.CONSTANT`, mode selectors, `*setpoint*` tokens) and map to candidate MV/CV/control-mode surfaces. Build a structured matrix artifact with evidence snippets and line anchors.
  **Must NOT do**: Do not label a unit as pass1-misaligned without linking to exact source snippets.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: cross-file metadata analysis with strict evidence requirements.
  - Skills: `[]` - analysis can be completed with AST/grep/read tools.
  - Omitted: `["frontend-ui-ux"]` - backend contract analysis only.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 5 | Blocked By: 1

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `src/modular_simulation/unit_processes/heater_cooler.py` - `mode`, `duty_setpoint`, `target_temperature_setpoint` pattern.
  - Pattern: `src/modular_simulation/unit_processes/flash_drum.py` - `thermal_mode`, `flash_temperature_setpoint` pattern.
  - Pattern: `src/modular_simulation/unit_processes/cstr.py` - `reactor_volume` + `level_control_gain` internal control law.
  - Pattern: `src/modular_simulation/unit_processes/pump.py` - `pressure_rise` constant-tag contract.
  - Pattern: `src/modular_simulation/unit_processes/pfr.py` - `jacket_temperature` constant-tag thermal actuation candidate.
  - Pattern: `src/modular_simulation/unit_processes/component_separator.py` - constant split-fraction contract.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `uv run python - <<'PY'\nfrom pathlib import Path\nimport re\nbase=Path('src/modular_simulation/unit_processes')\nhits={}\nfor p in sorted(base.glob('*.py')):\n    if p.name=='__init__.py':\n        continue\n    t=p.read_text()\n    hits[p.name]={\n        'controlled': len(re.findall(r'T\\.CONTROLLED', t)),\n        'constant': len(re.findall(r'T\\.CONSTANT', t)),\n        'setpoint': len(re.findall(r'setpoint', t)),\n        'mode': len(re.findall(r'_mode|thermal_mode|mode\\s*:', t)),\n    }\nprint(hits)\nassert 'heater_cooler.py' in hits and hits['heater_cooler.py']['setpoint']>0\nprint('task2-control-surface-ok')\nPY`
  - [ ] `uv run python - <<'PY'\nfrom pathlib import Path\ntext=Path('src/modular_simulation/unit_processes/conversion_reactor.py').read_text()\nassert 'thermal_mode' in text\nprint('task2-conversion-reactor-covered')\nPY`

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path control-surface matrix extraction
    Tool: Bash
    Steps: Run task2 extraction script and save JSON-like output.
    Expected: Script prints "task2-control-surface-ok" and includes all units.
    Evidence: .sisyphus/evidence/task-2-control-surface.log

  Scenario: Failure/edge path hotspot omission guard
    Tool: Bash
    Steps: Run conversion reactor inclusion check script.
    Expected: Script prints "task2-conversion-reactor-covered"; fails if hotspot omitted.
    Evidence: .sisyphus/evidence/task-2-control-surface-error.log
  ```

  **Commit**: YES | Message: `docs(audit): extract pass1 control-contract surfaces` | Files: `.sisyphus/evidence/task-2-control-surface.log`, `.sisyphus/evidence/task-2-control-surface-error.log`

- [x] 3. Map controller-readiness against runtime/subsystem contracts

  **What to do**: Cross-check unit control surfaces against runtime controller requirements (`System` activation, subsystem tag validation, control element MV binding). For each unit, mark `controller-ready`, `ready-with-adapter`, or `not-ready` with exact reason.
  **Must NOT do**: Do not assume readiness from unit metadata alone; include runtime contract checks.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: cross-module contract mapping with runtime rules.
  - Skills: `[]` - native tools sufficient.
  - Omitted: `["playwright"]` - non-browser backend validation.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 5 | Blocked By: 1

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `src/modular_simulation/components/control_system/control_element.py` - MV tag binding behavior.
  - Pattern: `src/modular_simulation/components/control_system/abstract_controller.py` - CV/SP/MV lifecycle.
  - Pattern: `src/modular_simulation/framework/system.py:780` - controller activation preconditions and actuator resolution.
  - Pattern: `src/modular_simulation/connection/subsystem_descriptor.py:134` - local CV validation.
  - Pattern: `src/modular_simulation/connection/subsystem_descriptor.py:143` - local MV validation.
  - Test: `tests/components/test_controller_wiring_api.py` - runtime binding and rollback pattern.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `uv run python -m pytest -q tests/components/test_controller_wiring_api.py tests/connection/test_subsystem_scoped_installers.py`
  - [ ] `uv run python - <<'PY'\nfrom pathlib import Path\nrequired=['src/modular_simulation/framework/system.py','src/modular_simulation/connection/subsystem_descriptor.py','src/modular_simulation/components/control_system/control_element.py']\nfor p in required:\n    assert Path(p).exists(), p\nprint('task3-runtime-contract-ok')\nPY`

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path runtime contract verification
    Tool: Bash
    Steps: Run targeted controller/subsystem test command.
    Expected: Tests pass with exit code 0.
    Evidence: .sisyphus/evidence/task-3-runtime-readiness.log

  Scenario: Failure/edge path missing-contract guard
    Tool: Bash
    Steps: Run required-file assertion script.
    Expected: Prints "task3-runtime-contract-ok"; fails if required runtime contracts are missing.
    Evidence: .sisyphus/evidence/task-3-runtime-readiness-error.log
  ```

  **Commit**: YES | Message: `docs(audit): map controller-readiness to runtime contracts` | Files: `.sisyphus/evidence/task-3-runtime-readiness.log`, `.sisyphus/evidence/task-3-runtime-readiness-error.log`

- [x] 4. Build unit-specific Pass 1 test coverage matrix

  **What to do**: Map every unit to available tests for control-contract evidence: unit tests, flowsheet integration, controller runtime, subsystem validation, and example usage drift. Mark coverage levels `strong`, `partial`, or `missing` for each pass1 criterion.
  **Must NOT do**: Do not treat generic controller tests as unit-specific coverage unless unit is explicitly involved.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: evidence synthesis across tests/examples with false-positive risk.
  - Skills: `[]` - no extra skills required.
  - Omitted: `["playwright"]` - no UI coverage dimension.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 5 | Blocked By: 1

  **References** (executor has NO interview context - be exhaustive):
  - Test: `tests/unit_process/test_flowsheet_integration.py` - current HeaterCooler controller coupling path.
  - Test: `tests/unit_process/test_layer4_heater_cooler.py` - direct mode/setpoint unit coverage.
  - Test: `tests/unit_process/test_layer4_flash_drum.py` - flash mode/setpoint coverage.
  - Test: `tests/components/test_controller_wiring_api.py` - generic runtime controller wiring checks.
  - Test: `tests/connection/test_subsystem_scoped_installers.py` - subsystem local tag validation behavior.
  - Pattern: `examples/unit_process_flowsheet` - example drift detection source.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `uv run python - <<'PY'\nfrom pathlib import Path\nchecks=[\n'tests/unit_process/test_flowsheet_integration.py',\n'tests/unit_process/test_layer4_heater_cooler.py',\n'tests/unit_process/test_layer4_flash_drum.py',\n'tests/components/test_controller_wiring_api.py',\n'tests/connection/test_subsystem_scoped_installers.py',\n]\nfor c in checks:\n    assert Path(c).exists(), c\nprint('task4-coverage-inputs-ok')\nPY`
  - [ ] `uv run python -m pytest -q tests/unit_process/test_flowsheet_integration.py tests/unit_process/test_layer4_heater_cooler.py tests/unit_process/test_layer4_flash_drum.py`

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path coverage-input validity
    Tool: Bash
    Steps: Run task4 file-existence script and targeted pass1 unit tests.
    Expected: Script prints "task4-coverage-inputs-ok" and tests exit 0.
    Evidence: .sisyphus/evidence/task-4-pass1-coverage.log

  Scenario: Failure/edge path coverage-gap exposure
    Tool: Bash
    Steps: Run `uv run python - <<'PY'\nfrom pathlib import Path\ntext=Path('tests/unit_process/test_flowsheet_integration.py').read_text()\nassert 'mv_tag="target_temperature_setpoint"' in text or 'mv_tag="duty_setpoint"' in text\nprint('task4-coupling-probe-ok')\nPY`.
    Expected: Script verifies there is explicit integration-level coupling signal; fails if absent.
    Evidence: .sisyphus/evidence/task-4-pass1-coverage-error.log
  ```

  **Commit**: YES | Message: `docs(audit): map pass1 control-contract test coverage` | Files: `.sisyphus/evidence/task-4-pass1-coverage.log`, `.sisyphus/evidence/task-4-pass1-coverage-error.log`

- [x] 5. Produce Pass 1 severity-ranked misalignment register

  **What to do**: Merge outputs from Tasks 2-4 into one Pass 1 register artifact with fields: `unit`, `misalignment_type`, `severity`, `runtime_risk`, `test_gap`, `evidence_paths`, `recommended_remediation_pattern`. Include explicit include/exclude rationale for `ConversionReactor` and `ShortcutDistillation`.
  **Must NOT do**: Do not assign severity without runtime/test rationale.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: high-judgment synthesis requiring strict evidence traceability.
  - Skills: `[]` - no extra skills required.
  - Omitted: `["playwright"]` - non-UI analysis.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 6, 10 | Blocked By: 2, 3, 4

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `src/modular_simulation/unit_processes/heater_cooler.py` - high severity benchmark.
  - Pattern: `src/modular_simulation/unit_processes/flash_drum.py` - mode/setpoint embedding comparator.
  - Pattern: `src/modular_simulation/unit_processes/cstr.py` - internal level-loop comparator.
  - Pattern: `src/modular_simulation/unit_processes/conversion_reactor.py` - explicit include/exclude decision required.
  - Pattern: `src/modular_simulation/unit_processes/shortcut_distillation.py` - pass-boundary decision point.
  - Pattern: `src/modular_simulation/framework/system.py:780` - runtime activation risk anchor.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `uv run python - <<'PY'\nfrom pathlib import Path\nreport=Path('.sisyphus/evidence/task-5-pass1-register.md')\nassert report.exists(), report\ntext=report.read_text()\nfor token in ['heater_cooler','flash_drum','cstr','conversion_reactor','shortcut_distillation','severity']:\n    assert token in text, token\nprint('task5-pass1-register-ok')\nPY`
  - [ ] `uv run python - <<'PY'\nfrom pathlib import Path\ntext=Path('.sisyphus/evidence/task-5-pass1-register.md').read_text()\nassert 'evidence_paths' in text and 'recommended_remediation_pattern' in text\nprint('task5-structure-ok')\nPY`

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path pass1 register completeness
    Tool: Bash
    Steps: Generate the pass1 register markdown and run completeness assertion script.
    Expected: Prints "task5-pass1-register-ok" and exits 0.
    Evidence: .sisyphus/evidence/task-5-pass1-register.log

  Scenario: Failure/edge path schema guard
    Tool: Bash
    Steps: Run structure assertion script for required columns/tokens.
    Expected: Prints "task5-structure-ok"; fails if schema or key units are missing.
    Evidence: .sisyphus/evidence/task-5-pass1-register-error.log
  ```

  **Commit**: YES | Message: `docs(audit): publish pass1 severity misalignment register` | Files: `.sisyphus/evidence/task-5-pass1-register.md`, `.sisyphus/evidence/task-5-pass1-register.log`, `.sisyphus/evidence/task-5-pass1-register-error.log`

- [x] 6. Define Pass 2 consistency taxonomy and audit rules

  **What to do**: Create a formal Pass 2 taxonomy with categories: naming consistency, validation consistency, edge-case semantic consistency, and cross-unit contract coherence. Define deterministic detection rules and severity rubric before scanning.
  **Must NOT do**: Do not start Pass 2 findings collection before taxonomy is frozen.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: framework definition task with explicit outputs.
  - Skills: `[]` - no additional skills required.
  - Omitted: `["frontend-ui-ux"]` - backend taxonomy only.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: 7, 8 | Blocked By: 5

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `src/modular_simulation/unit_processes` - pass2 audit target set.
  - Pattern: `src/modular_simulation/validation/exceptions.py` - validation semantics baseline.
  - Test: `tests/unit_process` - observed behavior baseline for semantic consistency.
  - Test: `tests/connection/test_runtime_mutation_contract.py` - mutation consistency expectations.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `uv run python - <<'PY'\nfrom pathlib import Path\np=Path('.sisyphus/evidence/task-6-pass2-taxonomy.md')\nassert p.exists(), p\ntext=p.read_text()\nfor token in ['naming consistency','validation consistency','edge-case semantic consistency','severity rubric']:\n    assert token in text, token\nprint('task6-taxonomy-ok')\nPY`
  - [ ] `uv run python - <<'PY'\nfrom pathlib import Path\ntext=Path('.sisyphus/evidence/task-6-pass2-taxonomy.md').read_text()\nassert 'detection rule' in text.lower()\nprint('task6-rules-ok')\nPY`

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path taxonomy publication
    Tool: Bash
    Steps: Write taxonomy artifact and run token checks.
    Expected: Prints "task6-taxonomy-ok" and exits 0.
    Evidence: .sisyphus/evidence/task-6-pass2-taxonomy.log

  Scenario: Failure/edge path missing-rule guard
    Tool: Bash
    Steps: Run detection-rule assertion script.
    Expected: Prints "task6-rules-ok"; fails if rules are vague or absent.
    Evidence: .sisyphus/evidence/task-6-pass2-taxonomy-error.log
  ```

  **Commit**: YES | Message: `docs(audit): define pass2 consistency taxonomy` | Files: `.sisyphus/evidence/task-6-pass2-taxonomy.md`, `.sisyphus/evidence/task-6-pass2-taxonomy.log`, `.sisyphus/evidence/task-6-pass2-taxonomy-error.log`

- [x] 7. Execute Pass 2 naming and contract-semantics scan

  **What to do**: Audit naming and contract-semantics consistency across all units: mode naming, setpoint naming, parameter intent naming, and controlled-vs-constant labeling coherence. Produce mismatch list with side-by-side evidence snippets.
  **Must NOT do**: Do not conflate naming style differences with semantic mismatches unless behavior/contracts diverge.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: broad cross-file semantic comparison.
  - Skills: `[]` - standard code search/analysis tools suffice.
  - Omitted: `["playwright"]` - no UI surface.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 9 | Blocked By: 6

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `src/modular_simulation/unit_processes/heater_cooler.py` - naming baseline for control terms.
  - Pattern: `src/modular_simulation/unit_processes/flash_drum.py` - thermal-mode naming and setpoint semantics.
  - Pattern: `src/modular_simulation/unit_processes/shortcut_distillation.py` - reflux setpoint terminology.
  - Pattern: `src/modular_simulation/unit_processes/conversion_reactor.py` - mode selector terminology.
  - Pattern: `src/modular_simulation/unit_processes/pump.py` - actuation-like constants (`pressure_rise`) nomenclature.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `uv run python - <<'PY'\nfrom pathlib import Path\np=Path('.sisyphus/evidence/task-7-pass2-naming.md')\nassert p.exists(), p\ntext=p.read_text()\nfor token in ['heater_cooler','flash_drum','shortcut_distillation','conversion_reactor','pump']:\n    assert token in text, token\nprint('task7-naming-scan-ok')\nPY`
  - [ ] `uv run python - <<'PY'\nfrom pathlib import Path\ntext=Path('.sisyphus/evidence/task-7-pass2-naming.md').read_text()\nassert 'mismatch_type' in text and 'evidence' in text\nprint('task7-schema-ok')\nPY`

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path naming-scan artifact generation
    Tool: Bash
    Steps: Generate naming mismatch report and run token checks.
    Expected: Prints "task7-naming-scan-ok" and exits 0.
    Evidence: .sisyphus/evidence/task-7-pass2-naming.log

  Scenario: Failure/edge path schema validation
    Tool: Bash
    Steps: Run schema assertion script for mismatch/evidence columns.
    Expected: Prints "task7-schema-ok"; fails if report structure is incomplete.
    Evidence: .sisyphus/evidence/task-7-pass2-naming-error.log
  ```

  **Commit**: YES | Message: `docs(audit): publish pass2 naming and contract mismatch scan` | Files: `.sisyphus/evidence/task-7-pass2-naming.md`, `.sisyphus/evidence/task-7-pass2-naming.log`, `.sisyphus/evidence/task-7-pass2-naming-error.log`

- [x] 8. Execute Pass 2 validation and edge-case semantics scan

  **What to do**: Compare unit validation and edge-case semantics (no-flow behavior, pressure floors, composition normalization, mode parsing strictness, finite checks). Record inconsistencies and classify as benign divergence vs actionable misalignment.
  **Must NOT do**: Do not classify intentional physics differences as misalignment without contradictory contract behavior.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: nuanced behavioral consistency analysis.
  - Skills: `[]` - no extra skills needed.
  - Omitted: `["frontend-ui-ux"]` - backend behavior audit.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 9 | Blocked By: 6

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `src/modular_simulation/unit_processes/heater_cooler.py` - no-flow + duty guard semantics.
  - Pattern: `src/modular_simulation/unit_processes/flash_drum.py` - mode parsing and flash setpoint validation.
  - Pattern: `src/modular_simulation/unit_processes/cstr.py` - internal level-control validation semantics.
  - Pattern: `src/modular_simulation/unit_processes/pfr.py` - distributed reactor validation semantics.
  - Pattern: `src/modular_simulation/unit_processes/component_separator.py` - split-fraction validation behavior.
  - Test: `tests/unit_process/test_layer4_cstr.py`, `tests/unit_process/test_layer4_pfr.py`, `tests/unit_process/test_layer4_distillation.py` - baseline behavior checks.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `uv run python -m pytest -q tests/unit_process/test_layer4_cstr.py tests/unit_process/test_layer4_pfr.py tests/unit_process/test_layer4_distillation.py`
  - [ ] `uv run python - <<'PY'\nfrom pathlib import Path\np=Path('.sisyphus/evidence/task-8-pass2-edgecases.md')\nassert p.exists(), p\ntext=p.read_text()\nfor token in ['no-flow','pressure','composition','finite','classification']:\n    assert token in text.lower(), token\nprint('task8-edgecase-scan-ok')\nPY`

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path edge-case baseline verification
    Tool: Bash
    Steps: Run targeted pass2 unit tests and generate edge-case scan report.
    Expected: Tests pass; script prints "task8-edgecase-scan-ok".
    Evidence: .sisyphus/evidence/task-8-pass2-edgecases.log

  Scenario: Failure/edge path missing-classification guard
    Tool: Bash
    Steps: Validate report contains required classification dimensions.
    Expected: Assertion fails if any required dimension is missing.
    Evidence: .sisyphus/evidence/task-8-pass2-edgecases-error.log
  ```

  **Commit**: YES | Message: `docs(audit): publish pass2 validation and edge-case scan` | Files: `.sisyphus/evidence/task-8-pass2-edgecases.md`, `.sisyphus/evidence/task-8-pass2-edgecases.log`, `.sisyphus/evidence/task-8-pass2-edgecases-error.log`

- [x] 9. Produce Pass 2 severity-ranked consistency register

  **What to do**: Merge Tasks 7-8 findings into a pass2 register with fields: `unit`, `consistency_dimension`, `misalignment`, `severity`, `impact`, `evidence`, `recommended_next_step`. Cross-link to Pass 1 register for overlaps.
  **Must NOT do**: Do not duplicate pass1 issues without cross-linking; avoid double counting.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: consolidated severity modeling across semantic dimensions.
  - Skills: `[]` - no extra skills required.
  - Omitted: `["playwright"]` - non-UI synthesis.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: 10 | Blocked By: 7, 8

  **References** (executor has NO interview context - be exhaustive):
  - Artifact: `.sisyphus/evidence/task-7-pass2-naming.md` - naming mismatch source.
  - Artifact: `.sisyphus/evidence/task-8-pass2-edgecases.md` - edge-case mismatch source.
  - Artifact: `.sisyphus/evidence/task-5-pass1-register.md` - overlap and de-dup anchor.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `uv run python - <<'PY'\nfrom pathlib import Path\np=Path('.sisyphus/evidence/task-9-pass2-register.md')\nassert p.exists(), p\ntext=p.read_text()\nfor token in ['consistency_dimension','severity','impact','recommended_next_step']:\n    assert token in text, token\nprint('task9-pass2-register-ok')\nPY`
  - [ ] `uv run python - <<'PY'\nfrom pathlib import Path\ntext=Path('.sisyphus/evidence/task-9-pass2-register.md').read_text()\nassert 'task-5-pass1-register' in text\nprint('task9-crosslink-ok')\nPY`

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path pass2 register generation
    Tool: Bash
    Steps: Generate pass2 register and run schema checks.
    Expected: Prints "task9-pass2-register-ok" and exits 0.
    Evidence: .sisyphus/evidence/task-9-pass2-register.log

  Scenario: Failure/edge path pass overlap guard
    Tool: Bash
    Steps: Run cross-link assertion script.
    Expected: Prints "task9-crosslink-ok"; fails if pass1 overlap handling is missing.
    Evidence: .sisyphus/evidence/task-9-pass2-register-error.log
  ```

  **Commit**: YES | Message: `docs(audit): publish pass2 severity consistency register` | Files: `.sisyphus/evidence/task-9-pass2-register.md`, `.sisyphus/evidence/task-9-pass2-register.log`, `.sisyphus/evidence/task-9-pass2-register-error.log`

- [x] 10. Consolidate two-pass remediation backlog and sequencing

  **What to do**: Produce one backlog artifact that merges Pass 1 and Pass 2 registers into execution-ready remediation groups with dependency order, stop conditions, rollback guardrails, and per-unit priority. Include Oracle severity order baseline and any justified deviations.
  **Must NOT do**: Do not output a flat list; backlog must preserve dependency and risk sequencing.

  **Recommended Agent Profile**:
  - Category: `writing` - Reason: structured synthesis artifact requiring precision and traceability.
  - Skills: `[]` - no special skills required.
  - Omitted: `["playwright"]` - documentation/synthesis task.

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocks: 11 | Blocked By: 5, 9

  **References** (executor has NO interview context - be exhaustive):
  - Artifact: `.sisyphus/evidence/task-5-pass1-register.md`
  - Artifact: `.sisyphus/evidence/task-9-pass2-register.md`
  - Pattern: `src/modular_simulation/framework/system.py:780` - runtime risk anchor for sequencing.
  - Pattern: `src/modular_simulation/connection/subsystem_descriptor.py` - local tag guardrail constraints.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `uv run python - <<'PY'\nfrom pathlib import Path\np=Path('.sisyphus/evidence/task-10-two-pass-backlog.md')\nassert p.exists(), p\ntext=p.read_text()\nfor token in ['dependency','rollback guardrail','stop condition','priority order']:\n    assert token.lower() in text.lower(), token\nprint('task10-backlog-ok')\nPY`
  - [ ] `uv run python - <<'PY'\nfrom pathlib import Path\ntext=Path('.sisyphus/evidence/task-10-two-pass-backlog.md').read_text()\nassert 'HeaterCooler' in text and 'FlashDrum' in text and 'CSTR' in text\nprint('task10-priority-units-ok')\nPY`

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path consolidated backlog generation
    Tool: Bash
    Steps: Generate consolidated backlog artifact and run schema assertion.
    Expected: Prints "task10-backlog-ok" and exits 0.
    Evidence: .sisyphus/evidence/task-10-two-pass-backlog.log

  Scenario: Failure/edge path missing-priority-unit guard
    Tool: Bash
    Steps: Run priority-unit assertion script.
    Expected: Prints "task10-priority-units-ok"; fails if top-risk units are omitted.
    Evidence: .sisyphus/evidence/task-10-two-pass-backlog-error.log
  ```

  **Commit**: YES | Message: `docs(audit): consolidate two-pass remediation backlog` | Files: `.sisyphus/evidence/task-10-two-pass-backlog.md`, `.sisyphus/evidence/task-10-two-pass-backlog.log`, `.sisyphus/evidence/task-10-two-pass-backlog-error.log`

- [x] 11. Run reproducibility and quality verification wave

  **What to do**: Run final reproducibility checks for artifacts plus targeted quality/test commands to ensure supporting contracts are still valid. Bundle outputs into an index artifact linking every evidence file.
  **Must NOT do**: Do not mark complete if any required artifact or command output is missing.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: multi-command verification and artifact integrity checks.
  - Skills: `[]` - standard CLI/test execution.
  - Omitted: `["git-master"]` - no history manipulation needed.

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocks: none | Blocked By: 10

  **References** (executor has NO interview context - be exhaustive):
  - Artifact family: `.sisyphus/evidence/task-*.md`
  - CI Pattern: `.github/workflows/ci.yml`
  - Tooling: `pyproject.toml`

  **Acceptance Criteria** (agent-executable only):
  - [ ] `uv run python -m ruff check src tests`
  - [ ] `uv run --with mypy python -m mypy src`
  - [ ] `uv run python -m pytest -q tests/components/test_controller_wiring_api.py tests/connection/test_subsystem_scoped_installers.py tests/unit_process/test_layer4_heater_cooler.py tests/unit_process/test_layer4_flash_drum.py tests/unit_process/test_layer4_conversion_reactor.py tests/unit_process/test_layer4_cstr.py tests/unit_process/test_layer4_pfr.py tests/unit_process/test_layer4_distillation.py`
  - [ ] `uv run python - <<'PY'\nfrom pathlib import Path\nrequired=[\n'.sisyphus/evidence/task-5-pass1-register.md',\n'.sisyphus/evidence/task-6-pass2-taxonomy.md',\n'.sisyphus/evidence/task-7-pass2-naming.md',\n'.sisyphus/evidence/task-8-pass2-edgecases.md',\n'.sisyphus/evidence/task-9-pass2-register.md',\n'.sisyphus/evidence/task-10-two-pass-backlog.md',\n]\nfor p in required:\n    assert Path(p).exists(), p\nprint('task11-evidence-index-ok')\nPY`

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path final verification wave
    Tool: Bash
    Steps: Run ruff, mypy, targeted pytest bundle, then artifact-index script.
    Expected: All commands exit 0; script prints "task11-evidence-index-ok".
    Evidence: .sisyphus/evidence/task-11-final-verification.log

  Scenario: Failure/edge path missing-artifact guard
    Tool: Bash
    Steps: Run artifact-index script before generating one required file to verify fail-fast behavior, then regenerate and rerun.
    Expected: Initial run fails on missing path; final run succeeds with expected marker.
    Evidence: .sisyphus/evidence/task-11-final-verification-error.log
  ```

  **Commit**: NO | Message: `n/a` | Files: `n/a`

## Final Verification Wave (4 parallel agents, ALL must APPROVE)
- [x] F1. Plan Compliance Audit - oracle
- [x] F2. Code Quality Review - unspecified-high
- [x] F3. Real Manual QA - unspecified-high (+ playwright if UI)
- [x] F4. Scope Fidelity Check - deep

## Commit Strategy
- Commit Group A: Pass 1 evidence and matrix artifacts.
- Commit Group B: Pass 2 evidence and matrix artifacts.
- Commit Group C: consolidated remediation backlog and verification outputs.
- Keep commits evidence-focused; no incidental source refactors in this audit plan.

## Success Criteria
- Misalignment matrix covers all unit process files with explicit pass assignment.
- Severity-ranked backlog includes guardrails, dependencies, and risk rationale.
- Reproducibility checks pass with no manual steps.
- Outputs are execution-ready for `/start-work` without additional clarifications.

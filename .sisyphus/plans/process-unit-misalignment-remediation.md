# Process Unit Misalignment Remediation

## TL;DR
> **Summary**: Implement the completed two-pass audit backlog as one dependency-ordered remediation program that stabilizes controller contracts first, then fixes runtime-safety inconsistencies, then lands naming/compatibility cleanup without breaking persistence or controller bindings.
> **Deliverables**:
> - Shared controller-contract harness and per-unit direct/proxy/reject decision table
> - Pass 1 remediation for all units in backlog Groups 1-3
> - Pass 2 runtime-safety consistency fixes, alias/shim compatibility, and benign-divergence documentation
> - Expanded regression suite and evidence bundle for `/start-work`
> **Effort**: XL
> **Parallel**: YES - 3 waves
> **Critical Path**: Task 1 -> Tasks 2-6 -> Tasks 7-10 -> Tasks 11-12 -> Task 13 -> Task 14 -> Task 15

## Context
### Original Request
- Review the artifacts of the completed two-pass plan and identify action items.
- Turn the whole six-group backlog into one implementation plan for `/start-work`.

### Interview Summary
- The canonical audit plan is `.sisyphus/plans/process-unit-misalignment-two-pass.md`; it is complete and verified by `.sisyphus/evidence/task-11-evidence-index.md`.
- Remaining work is remediation only. The fixed execution order comes from `.sisyphus/evidence/task-10-two-pass-backlog.md`: Group 1 (`PFR`, `ConversionReactor`, `HeatExchanger`), Group 2 (`ShortcutDistillation`, `CSTR`, `Pump`, `ComponentSeparator`), Group 3 (`Splitter`, `FlashDrum`, `Valve`, `HeaterCooler`), Group 4 (runtime-safety consistency), Group 5 (naming/coherence with aliases before renames), Group 6 (benign-divergence docs/monitoring only).
- Default architectural policy for this plan: prefer unit-local `T.CONTROLLED` surfaces or controlled proxies; if no physically safe actuator exists, add explicit rejection coverage rather than exposing a faux actuator.
- Default compatibility policy for this plan: preserve constructor kwargs, raw tags, controller `mv_tag` bindings, and save/load state keys with warning-emitting aliases or shims; permanent removal is out of scope.
- Warning policy for this plan: legacy compatibility paths emit `DeprecationWarning` with `stacklevel=2`; canonical paths stay warning-free.

### Metis Review (gaps addressed)
- Added a mandatory Group 0 foundation slice before Group 1 to standardize controller-contract, rollback, and dimensionality verification.
- Locked a per-unit target outcome so implementers do not decide direct vs proxy vs reject during execution.
- Added tag-impact, persistence-impact, and vector-MV guardrails to prevent accidental framework breakage.
- Expanded final verification beyond the original Task 11 commands so Group 1-3 unit families and alias compatibility are explicitly covered.

## Work Objectives
### Core Objective
- Convert the verified two-pass audit backlog into implemented, regression-protected code changes that preserve current physics/model semantics while making controller exposure, runtime validation, and naming compatibility consistent across the unit-process portfolio.

### Deliverables
- Shared controller-contract harness covering happy-path scalar control, unresolved-signal rollback, unsupported-actuator rejection, and vector dimensionality rejection.
- Per-unit remediation for all 12 targeted units with exact direct/proxy/reject outcomes.
- Runtime-safety consistency fixes for reactor-family validation/clamping, passive pressure handling, pump zero-flow parity, and the `pressure_drop` semantic split.
- Alias/shim layer for naming cleanup that preserves kwargs, raw tags, controller bindings, and persisted state payloads.
- Updated benign-divergence documentation and a refreshed evidence bundle under `.sisyphus/evidence/`.

### Definition of Done (verifiable conditions with commands)
- `uv run python -m pytest -q tests/components/test_controller_wiring_api.py tests/connection/test_runtime_mutation_contract.py tests/connection/test_subsystem_scoped_installers.py`
- `uv run python -m pytest -q tests/unit_process/test_layer4_pfr.py tests/unit_process/test_layer4_conversion_reactor.py tests/unit_process/test_layer4_heat_exchanger.py tests/unit_process/test_layer4_distillation.py tests/unit_process/test_layer4_cstr.py tests/unit_process/test_layer4_pump_valve.py tests/unit_process/test_layer4_component_separator.py tests/unit_process/test_layer4_mixer_splitter.py tests/unit_process/test_layer4_flash_drum.py tests/unit_process/test_layer4_heater_cooler.py`
- `uv run python -m pytest -q tests/unit_process/test_flowsheet_integration.py tests/components/test_controller_wiring_api.py tests/connection/test_runtime_mutation_contract.py tests/connection/test_transaction_atomicity.py`
- `uv run python -m pytest -q tests/test_save_load_minimal.py tests/integration/test_dynamic_process_network_workflow.py`
- `uv run python -m ruff check src tests`
- `uv run --with mypy python -m mypy src`

### Must Have
- Preserve the six backlog groups and execute them in order, with Group 0 foundation added before Group 1.
- Use the following per-unit outcomes:
  - `PFR`: add controlled proxy `jacket_temperature_setpoint`; keep `heat_transfer_coeff` and `jacket_area` design-time only.
  - `ConversionReactor`: reject runtime control of `thermal_mode` and `conversion_fractions`; do not add a faux actuator.
  - `HeatExchanger`: reject runtime control of `ua` and `flow_arrangement`; do not expose runtime control for either in this plan.
  - `ShortcutDistillation`: keep direct `reflux_ratio_setpoint`; add missing coverage only.
  - `Pump`: add controlled proxy `pressure_rise_setpoint`; keep `pressure_rise` as the construction-time/default alias until Group 5 compatibility work lands.
  - `CSTR`: add controlled proxy `reactor_volume_setpoint`; keep `jacket_temperature` design-time only in this plan.
  - `ComponentSeparator`: add controlled vector proxy `split_fraction_targets`; initialize from current `split_fractions` semantics and preserve shape validation.
  - `Splitter`: keep direct `split_ratios`; harden dimensionality and error reporting only.
  - `FlashDrum`: keep direct `flash_pressure` and `flash_temperature_setpoint`; reject runtime control of `thermal_mode`.
  - `Valve`: keep direct `open_fraction`; add runtime algebraic bound revalidation.
  - `HeaterCooler`: keep direct `pressure_drop`, `duty_setpoint`, and `target_temperature_setpoint`; use as the unchanged gold baseline.
  - `Mixer`: keep passive/no-MV behavior; only address passive pressure consistency and documentation.
- Enforce algebraic/`step()` parity checks for every runtime-safety fix touching `CSTR`, `PFR`, `ConversionReactor`, or `Pump`.
- Preserve constructor kwargs, raw tags, controller `mv_tag` bindings, and save/load payload keys throughout Group 5.

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- Must NOT introduce a generic constant-mutation framework unless an earlier task proves the current `System` and `ControlElement` contracts cannot support the chosen per-unit outcomes.
- Must NOT reinterpret design/model-definition knobs (`thermal_mode`, `flow_arrangement`, `ua`, `conversion_fractions`, `heat_transfer_coeff`, `jacket_area`) as runtime actuators.
- Must NOT rename or remove public fields/tags before alias/shim compatibility tests exist and pass.
- Must NOT change stoichiometry, thermodynamics, hydraulic equations, or other governing physics as part of control-contract remediation.
- Must NOT use manual inspection as verification; every acceptance criterion must run through agent-executable commands.

## Verification Strategy
> ZERO HUMAN INTERVENTION - all verification is agent-executed.
- Test decision: tests-after with `pytest`, `ruff`, and `mypy`
- QA policy: every task includes one happy-path and one failure/edge-case scenario with explicit commands and evidence paths.
- Evidence: `.sisyphus/evidence/task-{N}-{slug}.log` and `.sisyphus/evidence/task-{N}-{slug}-error.log`

## Execution Strategy
### Parallel Execution Waves
> Target: 5-8 tasks per wave. Extract shared dependencies first, then execute unit slices in parallel inside each ordered group.

Wave 1: Task 1 (foundation), then Tasks 2-6 (Group 1 plus low-risk Group 2 setup-compatible slices)
Wave 2: Tasks 7-10 (remaining Group 2 plus Group 3 hardening)
Wave 3: Tasks 11-15 (Group 4 through Group 6 consolidation, ordered as 11/12 -> 13 -> 14 -> 15)

### Dependency Matrix (full, all tasks)
- Task 1 blocks Tasks 2-15.
- Tasks 2-4 must complete before Tasks 7-15.
- Tasks 5-6 must complete before Tasks 7-15.
- Tasks 7-10 must complete before Tasks 11-15.
- Tasks 11 and 12 must complete before Task 13.
- Task 13 must complete before Task 14.
- Task 14 must complete before Task 15.
- Task 15 must complete before the Final Verification Wave.

### Agent Dispatch Summary (wave -> task count -> categories)
- Wave 1 -> 6 tasks -> `deep` for Task 1, `unspecified-high` for Tasks 2-6
- Wave 2 -> 4 tasks -> `unspecified-high` for Tasks 7-10
- Wave 3 -> 5 tasks -> `deep` for Tasks 11-15

## TODOs
> Implementation + Test = ONE task. Never separate.
> EVERY task MUST have: Agent Profile + Parallelization + QA Scenarios.

- [x] 1. Build the shared controller-contract harness and per-unit decision table

  **What to do**: Add the reusable regression harness that every later task must use for controller happy-path, unresolved-tag rollback, unsupported-actuator rejection, and vector dimensionality rejection. Capture the final direct/proxy/reject table for all 12 units inside the implementation evidence so later tasks only execute predetermined outcomes.
  **Must NOT do**: Do not change any unit-process state types or rename any public fields in this task. Do not add a generic constant-mutation framework.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: this task locks the shared control-contract policy and failure semantics for the whole program.
  - Skills: `[]` - No extra skill is required beyond repo-grounded implementation and test work.
  - Omitted: `playwright`, `frontend-ui-ux` - No browser or UI work is involved.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12 | Blocked By: none

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `src/modular_simulation/framework/system.py:265` - Controller MV validation only accepts tags present in `process_model.controlled_view.state_list`.
  - Pattern: `src/modular_simulation/components/control_system/control_element.py:70` - Raw tag lookup and setter binding depend on process-model metadata and `mv_tag` resolution.
  - Pattern: `src/modular_simulation/components/control_system/control_element.py:118` - Direct process-model MV writes coerce with `float(...)`; vector success needs an explicit non-scalar path.
  - API/Type: `src/modular_simulation/measurables/process_model.py:62` - `StateType` membership drives controlled vs constant view behavior.
  - API/Type: `src/modular_simulation/measurables/process_model.py:206` - `save()` serializes current state names; renames/type changes affect persisted payload keys.
  - API/Type: `src/modular_simulation/measurables/process_model.py:224` - `load()` reconstructs models from the serialized `states` mapping.
  - Test: `tests/components/test_controller_wiring_api.py:133` - Canonical scalar controller happy-path and rollback-failure structure.
  - Test: `tests/connection/test_runtime_mutation_contract.py:150` - Canonical rollback/idempotency assertions for failed runtime reconfiguration.
  - Test: `tests/unit_process/test_flowsheet_integration.py:61` - Gold-standard subsystem/flowsheet controller coupling with a unit-local controlled surface.
  - External: `.sisyphus/evidence/task-10-two-pass-backlog.md` - Fixed remediation ordering and pass boundaries.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Add a reusable controller-contract test module or helper set that proves scalar success, unresolved-tag rollback, unsupported-actuator rejection, and vector dimensionality rejection with `uv run python -m pytest -q tests/components/test_controller_wiring_api.py tests/connection/test_runtime_mutation_contract.py tests/connection/test_subsystem_scoped_installers.py`.
  - [ ] Record a per-unit decision table in `.sisyphus/evidence/task-1-controller-contract-decision-table.md` with columns `unit`, `current field`, `target outcome`, `compatibility impact`, and `tests`.
  - [ ] No source file outside tests/evidence changes unit `StateType` or public field names in this task.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Shared scalar harness works
    Tool: Bash
    Steps: Run `uv run python -m pytest -q tests/components/test_controller_wiring_api.py tests/connection/test_runtime_mutation_contract.py tests/connection/test_subsystem_scoped_installers.py` and save stdout/stderr to `.sisyphus/evidence/task-1-controller-contract-harness.log`.
    Expected: All targeted controller wiring and rollback tests pass; evidence file exists.
    Evidence: .sisyphus/evidence/task-1-controller-contract-harness.log

  Scenario: Shared vector rejection path is enforced
    Tool: Bash
    Steps: Run the new vector dimensionality rejection test(s) from the harness and save output to `.sisyphus/evidence/task-1-controller-contract-harness-error.log`.
    Expected: The test passes by asserting rejection plus rollback; no vector MV is silently accepted through the scalar setter path.
    Evidence: .sisyphus/evidence/task-1-controller-contract-harness-error.log
  ```

  **Commit**: YES | Message: `test(control): add controller contract harness` | Files: `tests/components/test_controller_wiring_api.py`, `tests/connection/test_runtime_mutation_contract.py`, `tests/connection/test_subsystem_scoped_installers.py`, `.sisyphus/evidence/task-1-controller-contract-decision-table.md`

- [x] 2. Expose `PFR` jacket-temperature control through a controlled proxy

  **What to do**: Add a unit-local controlled proxy named `jacket_temperature_setpoint` to `PFR`, initialize it from the existing `jacket_temperature` value, and route the existing thermal calculation through that proxy without changing `heat_transfer_coeff`, `jacket_area`, kinetics, or reactor geometry semantics. Add direct unit tests plus controller/subsystem wiring tests that prove the new proxy is controller-visible and preserves the current default behavior when left unchanged.
  **Must NOT do**: Do not convert `heat_transfer_coeff` or `jacket_area` into runtime-controlled fields. Do not change reaction kinetics, mass-balance equations, or the meaning of `total_volume`.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: the task is unit-local but affects controller visibility, thermal logic, and regression coverage.
  - Skills: `[]` - Existing repo patterns are sufficient.
  - Omitted: `playwright`, `frontend-ui-ux` - No browser or UI work is involved.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 7, 11, 12 | Blocked By: 1

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `src/modular_simulation/unit_processes/pfr.py:57` - `PFR` class entry point.
  - Pattern: `src/modular_simulation/unit_processes/pfr.py:86` - Existing inlet-side `T.CONTROLLED` declarations show the correct state declaration style.
  - Pattern: `src/modular_simulation/unit_processes/pfr.py:121` - `heat_transfer_coeff` is explicitly design-time `T.CONSTANT` and must remain so.
  - Pattern: `src/modular_simulation/unit_processes/pfr.py:125` - `jacket_area` is explicitly design-time `T.CONSTANT` and must remain so.
  - Pattern: `src/modular_simulation/unit_processes/pfr.py:129` - Current `jacket_temperature` constant is the source value for the new proxy.
  - Test: `tests/unit_process/test_layer4_pfr.py` - Existing unit semantics and reactor regression coverage.
  - Test: `tests/unit_process/test_flowsheet_integration.py:61` - Reference pattern for proving a unit-local controlled setpoint changes flowsheet behavior.
  - Test: `tests/components/test_controller_wiring_api.py:133` - Controller activation and rollback template.
  - External: `.sisyphus/evidence/task-5-pass1-register.md` - `PFR` is the critical Pass 1 row and requires adapter/proxy-backed runtime exposure plus direct tests.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `PFR` exposes `jacket_temperature_setpoint` through `controlled_view.state_list`, while `heat_transfer_coeff` and `jacket_area` remain absent from that list.
  - [ ] `uv run python -m pytest -q tests/unit_process/test_layer4_pfr.py tests/unit_process/test_flowsheet_integration.py tests/components/test_controller_wiring_api.py` passes with new `PFR` happy-path coverage.
  - [ ] A negative test proves controller binding or runtime mutation rejects `heat_transfer_coeff` as an actuator and leaves runtime state unchanged.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: PFR controller drives jacket temperature setpoint
    Tool: Bash
    Steps: Run `uv run python -m pytest -q tests/unit_process/test_layer4_pfr.py tests/unit_process/test_flowsheet_integration.py -k pfr` and save output to `.sisyphus/evidence/task-2-pfr-control-surface.log`.
    Expected: The new proxy is controller-visible, default behavior is preserved, and all targeted PFR tests pass.
    Evidence: .sisyphus/evidence/task-2-pfr-control-surface.log

  Scenario: PFR rejects design-time thermal constants as actuators
    Tool: Bash
    Steps: Run the new negative controller/runtime-mutation tests for `heat_transfer_coeff` and/or `jacket_area` and save output to `.sisyphus/evidence/task-2-pfr-control-surface-error.log`.
    Expected: Rejection occurs with rollback-safe behavior; no test silently writes to design-time constants.
    Evidence: .sisyphus/evidence/task-2-pfr-control-surface-error.log
  ```

  **Commit**: YES | Message: `feat(pfr): expose jacket temperature control surface` | Files: `src/modular_simulation/unit_processes/pfr.py`, `tests/unit_process/test_layer4_pfr.py`, `tests/unit_process/test_flowsheet_integration.py`, `tests/components/test_controller_wiring_api.py`

- [x] 3. Lock `ConversionReactor` to explicit runtime-control rejection

  **What to do**: Preserve `ConversionReactor` as a design-time configured unit for `thermal_mode` and `conversion_fractions`, and make the unsupported-runtime-control policy explicit through targeted controller and runtime-mutation tests. If repo-level diagnostics need a clearer message for rejected non-controlled fields, limit that change to error clarity without exposing any new actuator.
  **Must NOT do**: Do not change `thermal_mode`, `pressure_drop`, `conversion_fractions`, or stoichiometric parameters to `T.CONTROLLED`. Do not add a synthetic setpoint that changes reaction semantics.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: this task is a policy-hardening slice with high risk of faux-actuator scope creep.
  - Skills: `[]` - Existing system/controller tests provide the pattern.
  - Omitted: `playwright`, `frontend-ui-ux` - No browser or UI work is involved.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 11, 12 | Blocked By: 1

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `src/modular_simulation/unit_processes/conversion_reactor.py:247` - `ConversionReactor` class entry point.
  - Pattern: `src/modular_simulation/unit_processes/conversion_reactor.py:267` - `thermal_mode` is design-time constant and must stay non-actuated.
  - Pattern: `src/modular_simulation/unit_processes/conversion_reactor.py:272` - `pressure_drop` stays design-time in this slice; semantic cleanup belongs to Task 11/12.
  - Pattern: `src/modular_simulation/unit_processes/conversion_reactor.py:276` - `conversion_fractions` is design-time configuration and must stay non-actuated.
  - Test: `tests/unit_process/test_layer4_conversion_reactor.py` - Existing thermal-mode/unit semantics coverage.
  - Test: `tests/components/test_controller_wiring_api.py:180` - Rollback-safe unresolved/rejected activation pattern.
  - Test: `tests/connection/test_runtime_mutation_contract.py:180` - Runtime reconfiguration rollback pattern for unsupported operations.
  - External: `.sisyphus/evidence/task-5-pass1-register.md` - Group 1 decision is to treat reactor runtime-control rejection as valid remediation if no safe physical MV exists.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `ConversionReactor` leaves `thermal_mode` and `conversion_fractions` out of `controlled_view.state_list`.
  - [ ] `uv run python -m pytest -q tests/unit_process/test_layer4_conversion_reactor.py tests/components/test_controller_wiring_api.py tests/connection/test_runtime_mutation_contract.py -k conversion` passes with explicit rejection coverage.
  - [ ] Negative tests prove controller install/activation and runtime mutation reject `thermal_mode` and `conversion_fractions` with rollback-safe behavior.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: ConversionReactor retains existing unit behavior
    Tool: Bash
    Steps: Run `uv run python -m pytest -q tests/unit_process/test_layer4_conversion_reactor.py` and save output to `.sisyphus/evidence/task-3-conversion-reactor-rejection.log`.
    Expected: Existing reactor-mode tests still pass with no semantic drift.
    Evidence: .sisyphus/evidence/task-3-conversion-reactor-rejection.log

  Scenario: Unsupported ConversionReactor actuators fail cleanly
    Tool: Bash
    Steps: Run the new negative controller/runtime-mutation tests for `thermal_mode` and `conversion_fractions` and save output to `.sisyphus/evidence/task-3-conversion-reactor-rejection-error.log`.
    Expected: Rejection occurs before or at activation/runtime mutation, and runtime state rolls back unchanged.
    Evidence: .sisyphus/evidence/task-3-conversion-reactor-rejection-error.log
  ```

  **Commit**: YES | Message: `test(conversion-reactor): lock unsupported control surfaces` | Files: `tests/unit_process/test_layer4_conversion_reactor.py`, `tests/components/test_controller_wiring_api.py`, `tests/connection/test_runtime_mutation_contract.py`

- [x] 4. Lock `HeatExchanger` to explicit runtime-control rejection

  **What to do**: Preserve `HeatExchanger` as a design-time configured unit for `ua` and `flow_arrangement`, and make unsupported-runtime-control behavior explicit with targeted controller and runtime-mutation tests. Keep existing thermal-exchange semantics intact while documenting that runtime control of exchanger configuration is out of scope for this plan.
  **Must NOT do**: Do not convert `ua` or `flow_arrangement` to `T.CONTROLLED`. Do not repurpose hot-side or cold-side inlet states as faux exchanger actuators.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: this task is a high-risk contract decision with medium implementation scope.
  - Skills: `[]` - Existing patterns are sufficient.
  - Omitted: `playwright`, `frontend-ui-ux` - No browser or UI work is involved.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 11, 12 | Blocked By: 1

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `src/modular_simulation/unit_processes/heat_exchanger.py:271` - `HeatExchanger` class entry point.
  - Pattern: `src/modular_simulation/unit_processes/heat_exchanger.py:303` - `flow_arrangement` is a design-time selector and stays non-actuated.
  - Pattern: `src/modular_simulation/unit_processes/heat_exchanger.py:308` - `ua` is a design-time conductance constant and stays non-actuated.
  - Pattern: `src/modular_simulation/unit_processes/heat_exchanger.py:313` - Existing inlet-side controlled state pattern for exchanger runtime inputs.
  - Test: `tests/unit_process/test_layer4_heat_exchanger.py` - Existing exchanger semantics baseline.
  - Test: `tests/components/test_controller_wiring_api.py:180` - Rollback-safe failure pattern.
  - Test: `tests/connection/test_runtime_mutation_contract.py:180` - Runtime reconfiguration rejection pattern.
  - External: `.sisyphus/evidence/task-5-pass1-register.md` - Group 1 decision is to reject unsafe runtime control of exchanger design knobs.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `HeatExchanger` leaves `ua` and `flow_arrangement` out of `controlled_view.state_list`.
  - [ ] `uv run python -m pytest -q tests/unit_process/test_layer4_heat_exchanger.py tests/components/test_controller_wiring_api.py tests/connection/test_runtime_mutation_contract.py -k heat_exchanger` passes with explicit rejection coverage.
  - [ ] Negative tests prove controller install/activation and runtime mutation reject `ua` and `flow_arrangement` with rollback-safe behavior.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: HeatExchanger retains existing exchanger semantics
    Tool: Bash
    Steps: Run `uv run python -m pytest -q tests/unit_process/test_layer4_heat_exchanger.py` and save output to `.sisyphus/evidence/task-4-heat-exchanger-rejection.log`.
    Expected: Existing exchanger tests pass unchanged.
    Evidence: .sisyphus/evidence/task-4-heat-exchanger-rejection.log

  Scenario: Unsupported HeatExchanger actuators fail cleanly
    Tool: Bash
    Steps: Run the new negative controller/runtime-mutation tests for `ua` and `flow_arrangement` and save output to `.sisyphus/evidence/task-4-heat-exchanger-rejection-error.log`.
    Expected: Rejection occurs with rollback-safe behavior; no exchanger design constant is mutated at runtime.
    Evidence: .sisyphus/evidence/task-4-heat-exchanger-rejection-error.log
  ```

  **Commit**: YES | Message: `test(heat-exchanger): reject unsupported runtime actuators` | Files: `tests/unit_process/test_layer4_heat_exchanger.py`, `tests/components/test_controller_wiring_api.py`, `tests/connection/test_runtime_mutation_contract.py`

- [x] 5. Complete `ShortcutDistillation` reflux-ratio controller coverage

  **What to do**: Keep `ShortcutDistillation` exactly on its existing direct-control contract and add the missing unit-specific and controller-integration coverage for `reflux_ratio_setpoint`. Prove both the explicit positive setpoint path and the fallback factor path still work, and add one negative test for invalid reflux-ratio usage or unsupported binding.
  **Must NOT do**: Do not redesign distillation equations, key-component logic, or the meanings of `light_key_recovery`, `heavy_key_recovery`, or `reflux_factor`.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: this is a contained but important regression/coverage closure task.
  - Skills: `[]` - Existing test patterns are sufficient.
  - Omitted: `playwright`, `frontend-ui-ux` - No browser or UI work is involved.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 11, 12 | Blocked By: 1

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `src/modular_simulation/unit_processes/shortcut_distillation.py:176` - `ShortcutDistillation` class entry point.
  - Pattern: `src/modular_simulation/unit_processes/shortcut_distillation.py:220` - `reflux_factor` direct controlled fallback path.
  - Pattern: `src/modular_simulation/unit_processes/shortcut_distillation.py:228` - `reflux_ratio_setpoint` direct controlled state that needs explicit coverage.
  - Pattern: `src/modular_simulation/unit_processes/shortcut_distillation.py:336` - Existing validation for finite non-negative reflux input.
  - Pattern: `src/modular_simulation/unit_processes/shortcut_distillation.py:649` - Runtime/algebraic use of reflux ratio in the column calculations.
  - Test: `tests/unit_process/test_layer4_distillation.py` - Existing distillation semantics baseline.
  - Test: `tests/components/test_controller_wiring_api.py:133` - Happy-path controller activation template.
  - External: `.sisyphus/evidence/task-5-pass1-register.md` - Coverage gap is the only required Pass 1 remediation for this unit.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `uv run python -m pytest -q tests/unit_process/test_layer4_distillation.py tests/components/test_controller_wiring_api.py -k reflux` passes with explicit `reflux_ratio_setpoint` happy-path coverage.
  - [ ] Existing fallback behavior using `reflux_factor` remains covered and passing when `reflux_ratio_setpoint <= 0`.
  - [ ] A negative test proves invalid reflux-ratio input or unsupported binding fails without changing baseline distillation behavior.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: ShortcutDistillation accepts explicit reflux-ratio control
    Tool: Bash
    Steps: Run `uv run python -m pytest -q tests/unit_process/test_layer4_distillation.py tests/components/test_controller_wiring_api.py -k reflux` and save output to `.sisyphus/evidence/task-5-shortcut-distillation.log`.
    Expected: New reflux-ratio control tests and existing distillation tests pass.
    Evidence: .sisyphus/evidence/task-5-shortcut-distillation.log

  Scenario: Invalid reflux-ratio usage fails safely
    Tool: Bash
    Steps: Run the new invalid-input or unsupported-binding test for `reflux_ratio_setpoint` and save output to `.sisyphus/evidence/task-5-shortcut-distillation-error.log`.
    Expected: The test passes by asserting a clear failure without altering baseline column semantics.
    Evidence: .sisyphus/evidence/task-5-shortcut-distillation-error.log
  ```

  **Commit**: YES | Message: `test(distillation): cover reflux ratio control path` | Files: `tests/unit_process/test_layer4_distillation.py`, `tests/components/test_controller_wiring_api.py`

- [x] 6. Expose `Pump` pressure rise through a controlled proxy

  **What to do**: Add a unit-local controlled proxy named `pressure_rise_setpoint`, initialize it from the existing `pressure_rise`, and route pump runtime calculations through the proxy while keeping `pressure_rise` as the construction-time/default alias until Task 12. Preserve hydraulic efficiency semantics and add controller wiring plus unit/hydraulic regression coverage for both nominal and zero-flow behavior.
  **Must NOT do**: Do not change the meaning of `efficiency` or repurpose other hydraulic parameters as actuators. Do not defer zero-flow parity work beyond the targeted guardrails in Task 11.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: the task is unit-local but touches runtime calculations, hydraulic adapters, and controller exposure.
  - Skills: `[]` - Existing repo patterns are sufficient.
  - Omitted: `playwright`, `frontend-ui-ux` - No browser or UI work is involved.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 8, 10, 11, 12 | Blocked By: 1

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `src/modular_simulation/unit_processes/pump.py:65` - `Pump` class entry point.
  - Pattern: `src/modular_simulation/unit_processes/pump.py:86` - Existing `pressure_rise` design-time constant that seeds the new proxy.
  - Pattern: `src/modular_simulation/unit_processes/pump.py:317` - Runtime validation currently checks `pressure_rise`; preserve equivalent validation for the new proxy.
  - Pattern: `src/modular_simulation/unit_processes/pump.py:336` - Algebraic zero-flow/thermal behavior anchor.
  - Pattern: `src/modular_simulation/unit_processes/pump.py:355` - `step()` path anchor for parity work later in Task 11.
  - Test: `tests/unit_process/test_layer4_pump_valve.py` - Pump semantics baseline and constructor/runtime validation pattern.
  - Test: `tests/unit_process/test_hydraulic_elements.py:66` - Pump hydraulic adapter expectations use `pressure_rise` today.
  - Test: `tests/components/test_controller_wiring_api.py:133` - Controller activation template.
  - External: `.sisyphus/evidence/task-5-pass1-register.md` - `Pump` remediation is adapter/proxy exposure with bounds and rollback tests.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `Pump` exposes `pressure_rise_setpoint` through `controlled_view.state_list` while preserving constructor compatibility for `pressure_rise`.
  - [ ] `uv run python -m pytest -q tests/unit_process/test_layer4_pump_valve.py tests/unit_process/test_hydraulic_elements.py tests/components/test_controller_wiring_api.py -k pump` passes with new controller-happy-path coverage.
  - [ ] A negative test proves unsupported direct mutation of `efficiency` or other design-time parameters is rejected with rollback-safe behavior.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Pump controller drives pressure rise setpoint
    Tool: Bash
    Steps: Run `uv run python -m pytest -q tests/unit_process/test_layer4_pump_valve.py tests/unit_process/test_hydraulic_elements.py tests/components/test_controller_wiring_api.py -k pump` and save output to `.sisyphus/evidence/task-6-pump-control-surface.log`.
    Expected: New pump control-surface tests and existing hydraulic regressions pass.
    Evidence: .sisyphus/evidence/task-6-pump-control-surface.log

  Scenario: Pump rejects non-actuator configuration writes
    Tool: Bash
    Steps: Run the new negative controller/runtime-mutation tests for unsupported pump config fields and save output to `.sisyphus/evidence/task-6-pump-control-surface-error.log`.
    Expected: Rejection occurs cleanly with rollback-safe behavior.
    Evidence: .sisyphus/evidence/task-6-pump-control-surface-error.log
  ```

  **Commit**: YES | Message: `feat(pump): expose pressure rise control surface` | Files: `src/modular_simulation/unit_processes/pump.py`, `tests/unit_process/test_layer4_pump_valve.py`, `tests/unit_process/test_hydraulic_elements.py`, `tests/components/test_controller_wiring_api.py`

- [x] 7. Expose `CSTR` volume control through a controlled proxy

  **What to do**: Add a unit-local controlled proxy named `reactor_volume_setpoint`, initialize it from the existing `reactor_volume`, and update the internal level-control law to consume the proxy while preserving current outlet-flow behavior and constructor compatibility. Keep `jacket_temperature`, `jacket_heat_transfer_coeff`, `jacket_area`, and `level_control_gain` as design-time configuration in this plan.
  **Must NOT do**: Do not convert `jacket_temperature` or `level_control_gain` into runtime-controlled fields. Do not rewrite the embedded control law beyond swapping its setpoint source to the new proxy.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: the task changes a reactor-internal control seam and requires careful unit/controller regression coverage.
  - Skills: `[]` - Existing patterns are sufficient.
  - Omitted: `playwright`, `frontend-ui-ux` - No browser or UI work is involved.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 11, 12 | Blocked By: 1, 2, 3, 4, 5, 6

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `src/modular_simulation/unit_processes/cstr.py:57` - `CSTR` class entry point.
  - Pattern: `src/modular_simulation/unit_processes/cstr.py:108` - Existing `reactor_volume` constant that behaves like a setpoint.
  - Pattern: `src/modular_simulation/unit_processes/cstr.py:128` - `jacket_temperature` remains design-time in this plan.
  - Pattern: `src/modular_simulation/unit_processes/cstr.py:132` - `level_control_gain` remains design-time in this plan.
  - Pattern: `src/modular_simulation/unit_processes/cstr.py:451` - Internal level-control law uses the volume setpoint.
  - Pattern: `src/modular_simulation/unit_processes/cstr.py:506` - Secondary runtime path also uses the volume setpoint.
  - Test: `tests/unit_process/test_layer4_cstr.py` - Existing reactor behavior baseline.
  - Test: `tests/components/test_controller_wiring_api.py:133` - Controller activation template.
  - External: `.sisyphus/evidence/task-5-pass1-register.md` - `CSTR` remediation is to proxy the embedded control hook, not redesign reactor physics.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `CSTR` exposes `reactor_volume_setpoint` through `controlled_view.state_list` while preserving constructor compatibility for `reactor_volume`.
  - [ ] `uv run python -m pytest -q tests/unit_process/test_layer4_cstr.py tests/components/test_controller_wiring_api.py -k cstr` passes with new controller-happy-path coverage.
  - [ ] A negative test proves unsupported runtime control of `jacket_temperature` or `level_control_gain` is rejected with rollback-safe behavior.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: CSTR controller drives reactor volume setpoint
    Tool: Bash
    Steps: Run `uv run python -m pytest -q tests/unit_process/test_layer4_cstr.py tests/components/test_controller_wiring_api.py -k cstr` and save output to `.sisyphus/evidence/task-7-cstr-control-surface.log`.
    Expected: New CSTR controller tests and existing unit tests pass with no level-control regression.
    Evidence: .sisyphus/evidence/task-7-cstr-control-surface.log

  Scenario: CSTR rejects non-actuator thermal/gain fields
    Tool: Bash
    Steps: Run the new negative controller/runtime-mutation tests for `jacket_temperature` and/or `level_control_gain` and save output to `.sisyphus/evidence/task-7-cstr-control-surface-error.log`.
    Expected: Rejection occurs with rollback-safe behavior; only the sanctioned setpoint is exposed.
    Evidence: .sisyphus/evidence/task-7-cstr-control-surface-error.log
  ```

  **Commit**: YES | Message: `feat(cstr): expose reactor volume setpoint` | Files: `src/modular_simulation/unit_processes/cstr.py`, `tests/unit_process/test_layer4_cstr.py`, `tests/components/test_controller_wiring_api.py`

- [x] 8. Add narrow vector-MV support for `ComponentSeparator` controlled targets

  **What to do**: Add a unit-local controlled vector proxy named `split_fraction_targets`, initialize it from `split_fractions`, and implement the minimum framework support needed for direct array-valued controlled-state writes when metadata indicates a non-scalar controlled state. Use the Task 1 harness to prove success-path vector writes, dimensionality rejection, and rollback-safe failures, then route `ComponentSeparator` calculations through the new proxy without changing separator mass-balance semantics.
  **Must NOT do**: Do not generalize this into a broad new controller framework. Do not change the meaning of species split fractions or bypass dimensionality validation.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: this is the only justified shared framework adjustment and it must remain narrowly scoped to array-valued controlled states.
  - Skills: `[]` - Existing framework/tests are sufficient.
  - Omitted: `playwright`, `frontend-ui-ux` - No browser or UI work is involved.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: 10, 11, 12 | Blocked By: 1, 6

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `src/modular_simulation/unit_processes/component_separator.py:135` - `ComponentSeparator` class entry point.
  - Pattern: `src/modular_simulation/unit_processes/component_separator.py:162` - Existing `split_fractions` design-time vector that seeds the new proxy.
  - Pattern: `src/modular_simulation/components/control_system/control_element.py:103` - Direct process-model setter binding path for `mv_tag` writes.
  - Pattern: `src/modular_simulation/components/control_system/control_element.py:118` - Existing scalar `float(...)` coercion that cannot remain on the vector-success path.
  - Pattern: `src/modular_simulation/components/control_system/control_element.py:198` - Vector clipping already exists in `_update`; preserve it.
  - Test: `tests/unit_process/test_layer4_component_separator.py` - Existing separator semantics baseline.
  - Test: `tests/unit_process/test_layer4_mixer_splitter.py:117` - Existing split-ratio dimensionality/error expectations to mirror.
  - Test: `tests/components/test_controller_wiring_api.py` - Extend with explicit vector happy-path and rejection-path coverage.
  - External: `.sisyphus/evidence/task-5-pass1-register.md` - `ComponentSeparator` remediation is vector-MV proxy exposure with dimensional validation parity.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `ComponentSeparator` exposes `split_fraction_targets` through `controlled_view.state_list` and preserves constructor compatibility for `split_fractions`.
  - [ ] `uv run python -m pytest -q tests/unit_process/test_layer4_component_separator.py tests/components/test_controller_wiring_api.py -k component_separator` passes with one real vector-MV happy path.
  - [ ] A dimensionality mismatch test proves vector writes are rejected before state drift and that runtime state rolls back unchanged.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: ComponentSeparator accepts vector manipulated-variable writes
    Tool: Bash
    Steps: Run `uv run python -m pytest -q tests/unit_process/test_layer4_component_separator.py tests/components/test_controller_wiring_api.py -k component_separator` and save output to `.sisyphus/evidence/task-8-component-separator-vector.log`.
    Expected: The new vector happy-path test passes and existing separator semantics remain intact.
    Evidence: .sisyphus/evidence/task-8-component-separator-vector.log

  Scenario: ComponentSeparator rejects dimensionality mismatch with rollback
    Tool: Bash
    Steps: Run the new vector dimensionality rejection tests and save output to `.sisyphus/evidence/task-8-component-separator-vector-error.log`.
    Expected: Rejection occurs with rollback-safe behavior; no partial vector write reaches the process model.
    Evidence: .sisyphus/evidence/task-8-component-separator-vector-error.log
  ```

  **Commit**: YES | Message: `feat(separator): add vector control surface support` | Files: `src/modular_simulation/unit_processes/component_separator.py`, `src/modular_simulation/components/control_system/control_element.py`, `tests/unit_process/test_layer4_component_separator.py`, `tests/components/test_controller_wiring_api.py`

- [x] 9. Harden the thermal direct-MV baseline for `FlashDrum` and `HeaterCooler`

  **What to do**: Preserve the existing direct `T.CONTROLLED` surfaces for `FlashDrum` and `HeaterCooler`, add any missing controller/subsystem coverage that proves their sanctioned MVs remain first-class, and add explicit negative tests showing the mode selectors (`thermal_mode`, `mode`) are not runtime actuators. Treat `HeaterCooler` as the unchanged gold baseline and use its tests to validate that earlier proxy/reject work did not regress the portfolio reference pattern.
  **Must NOT do**: Do not rename `target_temperature_setpoint`, `duty_setpoint`, `pressure_drop`, `flash_pressure`, or `flash_temperature_setpoint` in this task. Do not expose `thermal_mode` or `mode` as runtime-controlled fields.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: this task is mostly regression hardening, but it protects the portfolio reference contract and selector policy.
  - Skills: `[]` - Existing patterns are sufficient.
  - Omitted: `playwright`, `frontend-ui-ux` - No browser or UI work is involved.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 11, 12 | Blocked By: 1, 2, 3, 4, 5, 6

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `src/modular_simulation/unit_processes/flash_drum.py:117` - `thermal_mode` remains a design-time selector.
  - Pattern: `src/modular_simulation/unit_processes/flash_drum.py:139` - `flash_pressure` is a sanctioned direct MV.
  - Pattern: `src/modular_simulation/unit_processes/flash_drum.py:143` - `flash_temperature_setpoint` is a sanctioned direct MV.
  - Pattern: `src/modular_simulation/unit_processes/heater_cooler.py:92` - `mode` remains a design-time selector.
  - Pattern: `src/modular_simulation/unit_processes/heater_cooler.py:115` - `pressure_drop` is the direct MV baseline for pressure-type control in this portfolio.
  - Pattern: `src/modular_simulation/unit_processes/heater_cooler.py:123` - `target_temperature_setpoint` is the gold-standard controller target.
  - Test: `tests/unit_process/test_layer4_flash_drum.py` - Flash-drum semantics and mode coverage baseline.
  - Test: `tests/unit_process/test_layer4_heater_cooler.py` - Heater/cooler direct-MV baseline.
  - Test: `tests/unit_process/test_flowsheet_integration.py:61` - Gold-standard controller-coupled flowsheet path that must stay green.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `uv run python -m pytest -q tests/unit_process/test_layer4_flash_drum.py tests/unit_process/test_layer4_heater_cooler.py tests/unit_process/test_flowsheet_integration.py -k "flash or heater"` passes.
  - [ ] Negative tests prove `thermal_mode` and `mode` are rejected as runtime actuators while sanctioned direct MVs remain controllable.
  - [ ] No public MV name changes land in this task.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: FlashDrum and HeaterCooler retain direct controller readiness
    Tool: Bash
    Steps: Run `uv run python -m pytest -q tests/unit_process/test_layer4_flash_drum.py tests/unit_process/test_layer4_heater_cooler.py tests/unit_process/test_flowsheet_integration.py` and save output to `.sisyphus/evidence/task-9-thermal-direct-mv.log`.
    Expected: Existing direct-MV behavior and flowsheet controller coupling stay green.
    Evidence: .sisyphus/evidence/task-9-thermal-direct-mv.log

  Scenario: Thermal selectors reject runtime control attempts
    Tool: Bash
    Steps: Run the new negative tests for `thermal_mode` and `mode` runtime-control attempts and save output to `.sisyphus/evidence/task-9-thermal-direct-mv-error.log`.
    Expected: Selector writes are rejected with rollback-safe behavior; sanctioned MVs remain unaffected.
    Evidence: .sisyphus/evidence/task-9-thermal-direct-mv-error.log
  ```

  **Commit**: YES | Message: `test(thermal-units): harden direct control contracts` | Files: `tests/unit_process/test_layer4_flash_drum.py`, `tests/unit_process/test_layer4_heater_cooler.py`, `tests/unit_process/test_flowsheet_integration.py`, `tests/components/test_controller_wiring_api.py`

- [x] 10. Harden the direct vector/scalar baseline for `Valve` and `Splitter`

  **What to do**: Keep `Valve.open_fraction` and `Splitter.split_ratios` as direct controller surfaces, add explicit runtime algebraic revalidation for valve bounds, and add controller-level vector happy-path plus dimensionality rejection coverage for splitter now that Task 8 has established the vector-write path. Preserve existing unit semantics and improve diagnostics only where the current direct-MV contract is under-specified.
  **Must NOT do**: Do not rename `open_fraction` or `split_ratios`. Do not relax splitter dimensionality checks or change how outlet fractions sum to unity.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: this task is direct-contract hardening with one shared dependency on vector-write support.
  - Skills: `[]` - Existing patterns are sufficient.
  - Omitted: `playwright`, `frontend-ui-ux` - No browser or UI work is involved.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 11, 12 | Blocked By: 1, 8

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `src/modular_simulation/unit_processes/valve.py:115` - `open_fraction` is the sanctioned direct MV.
  - Pattern: `src/modular_simulation/unit_processes/valve.py:78` - `Cv` and related constants remain configuration only.
  - Pattern: `src/modular_simulation/unit_processes/splitter.py:93` - `split_ratios` is the sanctioned vector MV.
  - Pattern: `src/modular_simulation/unit_processes/splitter.py:61` - Existing ratio validation helper anchors dimensionality expectations.
  - Pattern: `src/modular_simulation/unit_processes/splitter.py:272` - Runtime length checks and error paths must stay intact.
  - Test: `tests/unit_process/test_layer4_pump_valve.py` - Valve semantics and bounds baseline.
  - Test: `tests/unit_process/test_layer4_mixer_splitter.py:117` - Splitter ratio semantics and invalid-ratio baseline.
  - Test: `tests/components/test_controller_wiring_api.py` - Extend for direct vector success/failure coverage once Task 8 is in place.
  - External: `.sisyphus/evidence/task-5-pass1-register.md` - Splitter remains direct-ready and needs dimensionality-focused hardening only.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `uv run python -m pytest -q tests/unit_process/test_layer4_pump_valve.py tests/unit_process/test_layer4_mixer_splitter.py tests/components/test_controller_wiring_api.py -k "valve or splitter"` passes.
  - [ ] `Valve` revalidates `open_fraction` bounds in its algebraic/runtime update path and rejects out-of-range values explicitly.
  - [ ] `Splitter` has one direct controller vector happy-path test and one dimensionality rejection test with rollback-safe behavior.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Valve and Splitter retain direct controller readiness
    Tool: Bash
    Steps: Run `uv run python -m pytest -q tests/unit_process/test_layer4_pump_valve.py tests/unit_process/test_layer4_mixer_splitter.py tests/components/test_controller_wiring_api.py -k "valve or splitter"` and save output to `.sisyphus/evidence/task-10-valve-splitter.log`.
    Expected: Direct scalar/vector controller tests and existing unit tests pass.
    Evidence: .sisyphus/evidence/task-10-valve-splitter.log

  Scenario: Invalid direct-MV writes fail with explicit diagnostics
    Tool: Bash
    Steps: Run the new negative valve-bound and splitter-dimensionality tests and save output to `.sisyphus/evidence/task-10-valve-splitter-error.log`.
    Expected: Invalid writes are rejected without state drift; diagnostics identify the failing bound or dimensionality condition.
    Evidence: .sisyphus/evidence/task-10-valve-splitter-error.log
  ```

  **Commit**: YES | Message: `fix(flow-control): harden direct actuator validation` | Files: `src/modular_simulation/unit_processes/valve.py`, `src/modular_simulation/unit_processes/splitter.py`, `tests/unit_process/test_layer4_pump_valve.py`, `tests/unit_process/test_layer4_mixer_splitter.py`, `tests/components/test_controller_wiring_api.py`

- [x] 11. Standardize reactor-family validation and pump zero-flow parity

  **What to do**: Implement the Group 4 fixes that belong to the active-reactor and pump family only. Standardize `CSTR`, `PFR`, and `ConversionReactor` so invalid controller-facing values fail fast in both algebraic and stepped/runtime paths instead of being silently clamped, and align pump zero-flow algebraic behavior with the existing `step()` expectation that zero flow preserves inlet temperature.
  **Must NOT do**: Do not touch passive pressure policy, public field names, or alias behavior in this task. Do not change governing reactor or pump physics beyond the minimum fail-fast/parity fixes.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: this task crosses multiple active-process models and locks the portfolio fail-fast policy.
  - Skills: `[]` - Existing repo patterns are sufficient.
  - Omitted: `playwright`, `frontend-ui-ux` - No browser or UI work is involved.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: 13, 14, 15 | Blocked By: 2, 3, 4, 5, 6, 7, 8, 9, 10

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `src/modular_simulation/unit_processes/cstr.py:448` - Reactor-family clamp/validation hotspot.
  - Pattern: `src/modular_simulation/unit_processes/cstr.py:505` - Alternate CSTR runtime path that must match the same fail-fast policy.
  - Pattern: `src/modular_simulation/unit_processes/pfr.py:510` - PFR runtime validation hotspot called out in the audit.
  - Pattern: `src/modular_simulation/unit_processes/pump.py:336` - Algebraic zero-flow path currently diverges from stepped behavior.
  - Pattern: `src/modular_simulation/unit_processes/pump.py:355` - `step()` path whose zero-flow behavior becomes canonical for this plan.
  - Test: `tests/unit_process/test_layer4_cstr.py`, `tests/unit_process/test_layer4_pfr.py`, `tests/unit_process/test_layer4_conversion_reactor.py`, `tests/unit_process/test_layer4_pump_valve.py` - Family-specific semantic baselines.
  - External: `.sisyphus/evidence/task-9-pass2-register.md` - Group 4 reactor/pump inconsistency rows.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Reactor-family tests prove invalid controller-facing values fail fast in both algebraic and stepped/runtime paths instead of being silently clamped.
  - [ ] Pump zero-flow algebraic and stepped behavior match, with zero flow preserving inlet temperature.
  - [ ] `uv run python -m pytest -q tests/unit_process/test_layer4_pfr.py tests/unit_process/test_layer4_conversion_reactor.py tests/unit_process/test_layer4_cstr.py tests/unit_process/test_layer4_pump_valve.py` passes.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Reactor and pump safety semantics are consistent
    Tool: Bash
    Steps: Run `uv run python -m pytest -q tests/unit_process/test_layer4_pfr.py tests/unit_process/test_layer4_conversion_reactor.py tests/unit_process/test_layer4_cstr.py tests/unit_process/test_layer4_pump_valve.py` and save output to `.sisyphus/evidence/task-11-reactor-pump-safety.log`.
    Expected: All targeted reactor and pump semantic-consistency tests pass.
    Evidence: .sisyphus/evidence/task-11-reactor-pump-safety.log

  Scenario: Invalid active-unit values fail explicitly without drift
    Tool: Bash
    Steps: Run the new fail-fast and zero-flow parity tests and save output to `.sisyphus/evidence/task-11-reactor-pump-safety-error.log`.
    Expected: Each edge-case test passes by asserting explicit rejection or parity, not silent coercion.
    Evidence: .sisyphus/evidence/task-11-reactor-pump-safety-error.log
  ```

  **Commit**: YES | Message: `fix(runtime): align reactor and pump safety semantics` | Files: `src/modular_simulation/unit_processes/cstr.py`, `src/modular_simulation/unit_processes/pfr.py`, `src/modular_simulation/unit_processes/conversion_reactor.py`, `src/modular_simulation/unit_processes/pump.py`, `tests/unit_process/test_layer4_cstr.py`, `tests/unit_process/test_layer4_pfr.py`, `tests/unit_process/test_layer4_conversion_reactor.py`, `tests/unit_process/test_layer4_pump_valve.py`

- [x] 12. Standardize passive pressure policy and `pressure_drop` semantics

  **What to do**: Implement the remaining Group 4 fixes for passive units and semantic clarity. Enforce one positive-finite passive pressure rule for `Mixer` and `Splitter`, and add explicit coverage that `ConversionReactor.pressure_drop` is fixed configuration while `HeaterCooler.pressure_drop` remains a controlled actuator with unchanged behavior.
  **Must NOT do**: Do not rename `pressure_drop` in this task. Do not introduce any new controller surfaces or revisit the direct/proxy/reject outcomes.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: this task locks the cross-unit passive-pressure and semantic-policy baseline.
  - Skills: `[]` - Existing repo patterns are sufficient.
  - Omitted: `playwright`, `frontend-ui-ux` - No browser or UI work is involved.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: 13, 14, 15 | Blocked By: 8, 9, 10

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `src/modular_simulation/unit_processes/mixer.py:90` - Passive mixer pressure contract anchor.
  - Pattern: `src/modular_simulation/unit_processes/splitter.py:69` - Passive splitter pressure contract anchor.
  - Pattern: `src/modular_simulation/unit_processes/conversion_reactor.py:272` - `pressure_drop` remains fixed configuration.
  - Pattern: `src/modular_simulation/unit_processes/heater_cooler.py:115` - `pressure_drop` remains a controlled actuator here.
  - Test: `tests/unit_process/test_layer4_mixer_splitter.py`, `tests/unit_process/test_layer4_heater_cooler.py`, `tests/unit_process/test_layer4_conversion_reactor.py` - Semantic baselines for this slice.
  - External: `.sisyphus/evidence/task-9-pass2-register.md` - Passive pressure and `pressure_drop` divergence rows.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Mixer and Splitter reject or floor passive negative pressures according to one positive-finite portfolio rule, and the chosen rule is covered by explicit tests.
  - [ ] Tests explicitly prove `ConversionReactor.pressure_drop` remains fixed configuration while `HeaterCooler.pressure_drop` remains a direct actuator.
  - [ ] `uv run python -m pytest -q tests/unit_process/test_layer4_mixer_splitter.py tests/unit_process/test_layer4_heater_cooler.py tests/unit_process/test_layer4_conversion_reactor.py` passes.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Passive pressure and pressure-drop semantics are explicit
    Tool: Bash
    Steps: Run `uv run python -m pytest -q tests/unit_process/test_layer4_mixer_splitter.py tests/unit_process/test_layer4_heater_cooler.py tests/unit_process/test_layer4_conversion_reactor.py` and save output to `.sisyphus/evidence/task-12-passive-pressure.log`.
    Expected: Passive pressure policy tests and pressure-drop semantic tests pass.
    Evidence: .sisyphus/evidence/task-12-passive-pressure.log

  Scenario: Invalid passive pressure inputs fail without drift
    Tool: Bash
    Steps: Run the new negative passive-pressure tests and save output to `.sisyphus/evidence/task-12-passive-pressure-error.log`.
    Expected: Invalid passive-pressure inputs are rejected or normalized according to the chosen rule with no contradictory behavior.
    Evidence: .sisyphus/evidence/task-12-passive-pressure-error.log
  ```

  **Commit**: YES | Message: `fix(pressure): align passive pressure contracts` | Files: `src/modular_simulation/unit_processes/mixer.py`, `src/modular_simulation/unit_processes/splitter.py`, `tests/unit_process/test_layer4_mixer_splitter.py`, `tests/unit_process/test_layer4_heater_cooler.py`, `tests/unit_process/test_layer4_conversion_reactor.py`

- [x] 13. Add compatibility aliases for proxied control surfaces

  **What to do**: Implement the compatibility layer for the three proxy-backed units only: preserve legacy constructor kwargs, controller `mv_tag` strings, raw tag lookups, and save/load payload keys for `pressure_rise -> pressure_rise_setpoint`, `reactor_volume -> reactor_volume_setpoint`, and `split_fractions -> split_fraction_targets`. Keep `PFR.jacket_temperature` as the constructor/default input that seeds `jacket_temperature_setpoint` without introducing a second public alias. Every legacy path must emit `DeprecationWarning` with `stacklevel=2`.
  **Must NOT do**: Do not broaden this task into cross-unit naming cleanup. Do not remove any legacy name or change warning policy after it is introduced.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: this task touches persistence, raw tags, and public controller-binding names.
  - Skills: `[]` - Existing repo patterns and `warnings.warn` usage are sufficient.
  - Omitted: `playwright`, `frontend-ui-ux` - No browser or UI work is involved.

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocks: 14, 15 | Blocked By: 11, 12

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `src/modular_simulation/measurables/process_model.py:206` - `save()` serialization must preserve compatibility for legacy payload keys.
  - Pattern: `src/modular_simulation/measurables/process_model.py:224` - `load()` reconstruction must accept legacy and canonical keys.
  - Pattern: `src/modular_simulation/framework/system.py:1295` - Full-system save/load path persists controller config and MV tags.
  - Pattern: `src/modular_simulation/components/control_system/control_element.py:72` - Raw tag names are derived from `metadata.type.name`, so alias logic must preserve legacy bindings.
  - Pattern: `src/modular_simulation/components/sensors/abstract_sensor.py:128` - Sensor lookup also depends on metadata-backed names.
  - Pattern: `src/modular_simulation/connection/unit_process_wiring.py:69` - Unit-process wiring publishes metadata-derived states into runtime/connection layers.
  - Test: `tests/test_save_load_minimal.py` - Minimum persistence compatibility gate.
  - Test: `tests/integration/test_dynamic_process_network_workflow.py` - Integration-level controller binding and runtime workflow gate.
  - Test: `tests/unit_process/test_layer4_pump_valve.py`, `tests/unit_process/test_layer4_cstr.py`, `tests/unit_process/test_layer4_component_separator.py` - Constructor-kwargs compatibility gates for proxied units.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Legacy constructor kwargs, controller `mv_tag` strings, raw tag lookups, and save/load payload keys continue to work for proxied units, while canonical names also work.
  - [ ] Legacy compatibility paths emit `DeprecationWarning` with `stacklevel=2`, and canonical paths do not emit warnings.
  - [ ] `uv run python -m pytest -q tests/test_save_load_minimal.py tests/integration/test_dynamic_process_network_workflow.py tests/unit_process/test_layer4_pump_valve.py tests/unit_process/test_layer4_cstr.py tests/unit_process/test_layer4_component_separator.py` passes.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Proxied-unit legacy and canonical names both work
    Tool: Bash
    Steps: Run `uv run python -m pytest -q tests/test_save_load_minimal.py tests/integration/test_dynamic_process_network_workflow.py tests/unit_process/test_layer4_pump_valve.py tests/unit_process/test_layer4_cstr.py tests/unit_process/test_layer4_component_separator.py` and save output to `.sisyphus/evidence/task-13-proxy-compatibility.log`.
    Expected: Legacy and canonical names both pass, with warnings emitted only on legacy paths.
    Evidence: .sisyphus/evidence/task-13-proxy-compatibility.log

  Scenario: Unsupported alias names fail explicitly
    Tool: Bash
    Steps: Run the new negative alias-resolution and load-payload mismatch tests for proxied units and save output to `.sisyphus/evidence/task-13-proxy-compatibility-error.log`.
    Expected: Unknown names fail explicitly; accepted legacy names resolve to the canonical target without silent ambiguity.
    Evidence: .sisyphus/evidence/task-13-proxy-compatibility-error.log
  ```

  **Commit**: YES | Message: `feat(compat): add proxy control-surface aliases` | Files: `src/modular_simulation/measurables/process_model.py`, `src/modular_simulation/framework/system.py`, `src/modular_simulation/components/control_system/control_element.py`, `src/modular_simulation/components/sensors/abstract_sensor.py`, `src/modular_simulation/connection/unit_process_wiring.py`, `tests/test_save_load_minimal.py`, `tests/integration/test_dynamic_process_network_workflow.py`, `tests/unit_process/test_layer4_pump_valve.py`, `tests/unit_process/test_layer4_cstr.py`, `tests/unit_process/test_layer4_component_separator.py`

- [x] 14. Add cross-unit naming-coherence aliases and warnings

  **What to do**: Implement the remaining Group 5 naming/coherence work with aliases rather than breaking renames. Add warning-emitting alias coverage for thermal selector naming (`mode` vs `thermal_mode`), setpoint naming (`reactor_volume` vs `reactor_volume_setpoint` now that Task 13 exists), split vocabulary (`split_ratios` vs `split_fraction_targets`/`split_fractions`), and thermal-conductance naming metadata (`ua` vs `heat_transfer_coeff * jacket_area`) without changing solver behavior. Every supported legacy alias must emit `DeprecationWarning` with `stacklevel=2`.
  **Must NOT do**: Do not remove or hard-rename existing public fields in this task. Do not change parser behavior except to accept explicitly documented aliases.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: this task coordinates cross-unit public naming without reopening earlier contract decisions.
  - Skills: `[]` - Existing repo patterns and warning policy are sufficient.
  - Omitted: `playwright`, `frontend-ui-ux` - No browser or UI work is involved.

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocks: 15 | Blocked By: 13

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `src/modular_simulation/unit_processes/heater_cooler.py:92` - `mode` naming reference.
  - Pattern: `src/modular_simulation/unit_processes/flash_drum.py:117` - `thermal_mode` naming reference.
  - Pattern: `src/modular_simulation/unit_processes/conversion_reactor.py:267` - `thermal_mode` naming reference for reactor-family consistency.
  - Pattern: `src/modular_simulation/unit_processes/cstr.py:108` - Legacy setpoint-like `reactor_volume` name.
  - Pattern: `src/modular_simulation/unit_processes/splitter.py:93` - `split_ratios` naming reference.
  - Pattern: `src/modular_simulation/unit_processes/component_separator.py:162` - Legacy `split_fractions` naming reference.
  - Pattern: `src/modular_simulation/unit_processes/heat_exchanger.py:308` - `ua` naming reference.
  - Pattern: `src/modular_simulation/unit_processes/pfr.py:121` - Reactor-side conductance naming reference.
  - External: `.sisyphus/evidence/task-9-pass2-register.md` - Group 5 naming/coherence rows.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Warning-emitting aliases exist for every naming row chosen in this plan, and canonical names are documented in tests/evidence.
  - [ ] `uv run python -m pytest -q tests/unit_process/test_layer4_flash_drum.py tests/unit_process/test_layer4_heater_cooler.py tests/unit_process/test_layer4_conversion_reactor.py tests/unit_process/test_layer4_cstr.py tests/unit_process/test_layer4_mixer_splitter.py tests/unit_process/test_layer4_component_separator.py tests/unit_process/test_layer4_heat_exchanger.py` passes with new naming-coherence coverage.
  - [ ] No solver or unit-physics behavior changes are introduced solely to improve nomenclature.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Cross-unit naming aliases resolve consistently
    Tool: Bash
    Steps: Run `uv run python -m pytest -q tests/unit_process/test_layer4_flash_drum.py tests/unit_process/test_layer4_heater_cooler.py tests/unit_process/test_layer4_conversion_reactor.py tests/unit_process/test_layer4_cstr.py tests/unit_process/test_layer4_mixer_splitter.py tests/unit_process/test_layer4_component_separator.py tests/unit_process/test_layer4_heat_exchanger.py` and save output to `.sisyphus/evidence/task-14-naming-coherence.log`.
    Expected: Alias-backed naming tests pass and no behavior regressions appear.
    Evidence: .sisyphus/evidence/task-14-naming-coherence.log

  Scenario: Unknown names still fail explicitly
    Tool: Bash
    Steps: Run the new negative alias/parser tests for unsupported names and save output to `.sisyphus/evidence/task-14-naming-coherence-error.log`.
    Expected: Only documented aliases resolve; unsupported names fail explicitly.
    Evidence: .sisyphus/evidence/task-14-naming-coherence-error.log
  ```

  **Commit**: YES | Message: `feat(naming): add compatibility aliases across units` | Files: `src/modular_simulation/unit_processes/heater_cooler.py`, `src/modular_simulation/unit_processes/flash_drum.py`, `src/modular_simulation/unit_processes/conversion_reactor.py`, `src/modular_simulation/unit_processes/cstr.py`, `src/modular_simulation/unit_processes/component_separator.py`, `src/modular_simulation/unit_processes/splitter.py`, `src/modular_simulation/unit_processes/heat_exchanger.py`, `tests/unit_process/test_layer4_flash_drum.py`, `tests/unit_process/test_layer4_heater_cooler.py`, `tests/unit_process/test_layer4_conversion_reactor.py`, `tests/unit_process/test_layer4_cstr.py`, `tests/unit_process/test_layer4_mixer_splitter.py`, `tests/unit_process/test_layer4_component_separator.py`, `tests/unit_process/test_layer4_heat_exchanger.py`

- [x] 15. Refresh benign-divergence documentation and the final evidence bundle

  **What to do**: Complete the Group 6 closeout by documenting the low-severity benign divergences without changing behavior, then refresh the implementation evidence bundle so the final verification wave can audit one coherent artifact set. Re-state which divergences remain intentional and why, and make sure the evidence index points to the compatibility and runtime-safety logs generated by Tasks 11-14.
  **Must NOT do**: Do not make new behavioral changes in this task. Do not introduce fresh backlog items unless a verification command fails and the failure is evidenced.

  **Recommended Agent Profile**:
  - Category: `writing` - Reason: this task is primarily evidence/documentation synthesis with one final verification-oriented pass.
  - Skills: `[]` - No extra skill is required.
  - Omitted: `playwright`, `frontend-ui-ux` - No browser or UI work is involved.

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocks: Final Verification Wave | Blocked By: 14

  **References** (executor has NO interview context - be exhaustive):
  - External: `.sisyphus/evidence/task-9-pass2-register.md` - Source of the benign divergence list.
  - External: `.sisyphus/evidence/task-10-two-pass-backlog.md` - Final implementation ordering and guardrails.
  - External: `.sisyphus/evidence/task-11-evidence-index.md` - Structure to mirror when refreshing the new evidence index.

  **Acceptance Criteria** (agent-executable only):
  - [ ] A refreshed benign-divergence summary explicitly marks the low-severity rows as documentation-only and names the tests that protect them.
  - [ ] A refreshed evidence index links the logs/artifacts from Tasks 11-14.
  - [ ] `uv run python -m pytest -q tests/test_save_load_minimal.py tests/integration/test_dynamic_process_network_workflow.py tests/unit_process/test_flowsheet_integration.py tests/components/test_controller_wiring_api.py tests/connection/test_runtime_mutation_contract.py tests/connection/test_transaction_atomicity.py` passes before the Final Verification Wave.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Final evidence bundle is complete and reproducible
    Tool: Bash
    Steps: Run `uv run python -m pytest -q tests/test_save_load_minimal.py tests/integration/test_dynamic_process_network_workflow.py tests/unit_process/test_flowsheet_integration.py tests/components/test_controller_wiring_api.py tests/connection/test_runtime_mutation_contract.py tests/connection/test_transaction_atomicity.py` and save output to `.sisyphus/evidence/task-15-final-evidence.log`.
    Expected: The compatibility/runtime/controller integration bundle passes and the evidence index can be refreshed without gaps.
    Evidence: .sisyphus/evidence/task-15-final-evidence.log

  Scenario: Evidence refresh catches missing artifacts
    Tool: Bash
    Steps: Run the new evidence-index completeness check and save output to `.sisyphus/evidence/task-15-final-evidence-error.log`.
    Expected: The check passes only when every required Task 11-14 artifact exists; missing files fail explicitly.
    Evidence: .sisyphus/evidence/task-15-final-evidence-error.log
  ```

  **Commit**: YES | Message: `docs(evidence): refresh benign divergence summary` | Files: `.sisyphus/evidence/task-15-benign-divergence-summary.md`, `.sisyphus/evidence/task-15-evidence-index.md`

## Final Verification Wave (4 parallel agents, ALL must APPROVE)
- [x] F1. Plan Compliance Audit - oracle
- [x] F2. Code Quality Review - unspecified-high
- [x] F3. Real Manual QA - unspecified-high
- [x] F4. Scope Fidelity Check - deep

## Commit Strategy
- Commit after every numbered task with the message specified in that task.
- Do not squash Tasks 1-4 together; they anchor the controller-contract policy and need isolated rollback points.
- Re-run the smallest relevant regression bundle before each commit and the full Definition-of-Done bundle before the final verification wave.

## Success Criteria
- Every unit in the audit has a finished remediation outcome that matches the per-unit decision table in this plan.
- Unsupported runtime-control targets fail explicitly at controller install/activation or runtime mutation with rollback-safe behavior.
- All direct/proxy surfaces are visible through subsystem/controller wiring and preserve existing physical behavior at default settings.
- Naming cleanup preserves compatibility for constructor kwargs, raw tags, controller bindings, and persisted payload keys.
- All Definition-of-Done commands pass, and the evidence bundle is refreshed without requiring new user decisions.

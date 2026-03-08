# Control Surface Remediation

## TL;DR
> **Summary**: Remove controller-facing pseudo-actuators and `*setpoint` state semantics from the process-model portfolio, route indirect objectives through cascade control onto physical control elements, and unify cross-layer authority where the network and unit models currently disagree.
> **Deliverables**:
> - Portfolio-wide control-surface contract and naming policy
> - Refactored controller/runtime wiring contract for reference-to-actuator cascade control
> - Remediated unit-model surfaces for pump, CSTR, flash drum, heater/cooler, PFR, splitter, separator, and shortcut distillation
> - Migration, persistence, and regression tests covering controller wiring, hydraulics, and flowsheet integration
> **Effort**: Large
> **Parallel**: YES - 3 waves
> **Critical Path**: 1 -> 2 -> 4 -> 8 -> 10 -> 11

## Context
### Original Request
Create a work plan for the process-unit misalignment remediation. User requirement: no state named or modeled as a `setpoint` ever; any indirectly controlled variable must be handled via cascade control onto a physical control element.

### Interview Summary
- The simulator must demonstrate real dynamics and control considerations rather than hand-waved abstractions.
- Portfolio policy must distinguish physical manipulated variables, measured states, external boundary conditions, and reduced-order specification parameters.
- Public/runtime/persisted state and tags must not expose `setpoint` semantics after remediation.
- Indirect objectives remain allowed only as controller reference signals that terminate at explicit physical actuators.

### Metis Review (gaps addressed)
- Applied default: the `setpoint` ban covers public/runtime/persisted state and tags; purely local private variable names are not in scope unless they leak into the public contract.
- Applied default: keep constructor/load compatibility aliases for one migration window with deterministic deprecation warnings; runtime controller activation against banned/non-physical tags must fail immediately and rollback cleanly.
- Added guardrails for rollback/idempotency, hydraulic solvability, vector/scalar validation, and bumpless MANUAL/AUTO/CASCADE/TRACKING transfers.
- Added acceptance gates for banned-name removal, compatibility behavior, runtime controller binding failures, and hydraulic/network regression.

## Work Objectives
### Core Objective
Replace pseudo-actuator unit states with a coherent control-surface architecture where controller-facing manipulated variables are physical final elements, indirect objectives flow through cascade control, and network/unit authority is single-sourced.

### Deliverables
- Shared control-surface taxonomy and validation guardrails.
- Controller/runtime wiring updated to use public reference-signal semantics instead of public setpoint state semantics.
- Unit-model APIs reclassified so each controller-facing field is either a physical MV, a measured state, or a documented external boundary/specification parameter.
- Pump hydraulics and unit thermodynamics unified on one actuator source of truth.
- Migration coverage for runtime wiring, save/load, raw-tag resolution, and examples.

### Definition of Done (verifiable conditions with commands)
- `python -m pytest tests/components/test_controller_wiring_api.py tests/controller_contract_harness.py`
- `python -m pytest tests/unit_process/test_layer4_pump_valve.py tests/unit_process/test_layer4_mixer_splitter.py tests/unit_process/test_layer4_component_separator.py tests/unit_process/test_layer4_distillation.py`
- `python -m pytest tests/connection/test_hydraulic_solver.py tests/connection/test_hydraulic_solver_solvability.py tests/connection/test_process_interface_adapter.py`
- `python -m pytest tests/unit_process/test_flowsheet_integration.py tests/integration/test_dynamic_process_network_workflow.py tests/test_save_load_minimal.py`
- `python -m pytest tests/unit_process`

### Must Have
- No public/runtime/persisted unit state or tag containing `setpoint` after remediation.
- Every allowed controller-facing MV terminates at one explicit physical control element or actuator proxy with documented physical meaning.
- Indirect objectives are implemented through cascade controllers/reference signals, not hidden unit-internal supervisory laws.
- Unit/network authority is single-sourced for pump head, splitter branch allocation, and any other remediated cross-layer quantity.
- Reduced-order specification variables remain allowed only as non-controller-facing configured parameters on explicitly abstract models.

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- No silent renaming without compatibility policy and tests.
- No unit model that both solves a quantity internally and exposes the same quantity as an independently solved network authority.
- No partial migration where constructor/load aliases exist but runtime controller binding still accepts banned pseudo-actuator tags.
- No broad physics redesign beyond what is required to remove fake MVs and single-source control authority.
- No changes to unrelated unit models or solver contracts outside the targeted remediation set.

## Verification Strategy
> ZERO HUMAN INTERVENTION — all verification is agent-executed.
- Test decision: tests-after with `pytest`
- QA policy: Every task includes agent-executed happy-path and failure/edge-case scenarios
- Evidence: `.sisyphus/evidence/task-{N}-{slug}.txt`

## Execution Strategy
### Parallel Execution Waves
> Target: 5-8 tasks per wave. Extract shared dependencies into Wave 1.

Wave 1: contract, controller/runtime, runtime guardrails, pump authority
Wave 2: reactor/thermal/boundary semantics, hydraulic splitter semantics
Wave 3: abstract separator/distillation cleanup, migration/docs/examples, end-to-end regression

### Dependency Matrix (full, all tasks)
- 1 blocks 2, 3, 5, 6, 7, 8, 9, 10, 11
- 2 blocks 3, 4, 10, 11
- 3 blocks 10, 11
- 4 blocks 8, 10, 11
- 5 blocks 10, 11
- 6 blocks 10, 11
- 7 blocks 10, 11
- 8 blocks 10, 11
- 9 blocks 10, 11
- 10 blocks 11
- 11 blocks Final Verification Wave

### Agent Dispatch Summary (wave -> task count -> categories)
- Wave 1 -> 4 tasks -> `deep`, `unspecified-high`
- Wave 2 -> 4 tasks -> `deep`, `unspecified-high`
- Wave 3 -> 3 tasks -> `unspecified-high`, `writing`, `deep`

## TODOs
> Implementation + Test = ONE task. Never separate.
> EVERY task MUST have: Agent Profile + Parallelization + QA Scenarios.

- [ ] 1. Codify the control-surface taxonomy and banned-name contract

  **What to do**: Introduce one shared portfolio contract that classifies every exposed unit/process field as one of: physical actuator, measured state, external boundary condition, or configured abstract specification. Add a validation gate that forbids public/runtime/persisted names containing `setpoint` and forbids indirect-objective fields from entering controller-facing `controlled_view.state_list`. Use the current audit note as the seed inventory and convert it into executable contract coverage.
  **Must NOT do**: Do not grandfather existing `*setpoint` names. Do not let reduced-order spec variables stay controller-bindable just because tests already cover them.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: this defines the semantic contract that all later remediations depend on.
  - Skills: `[]` — shared repo exploration and precise test shaping are enough.
  - Omitted: `[playwright]` — no browser/UI work is involved.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 2, 3, 5, 6, 7, 8, 9, 10, 11 | Blocked By: none

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `src/modular_simulation/unit_processes/cstr.py:104` — current `reactor_volume_setpoint` shows a banned indirect-objective surface.
  - Pattern: `src/modular_simulation/unit_processes/flash_drum.py:138` — current `flash_pressure` is exposed as controller-facing state.
  - Pattern: `src/modular_simulation/unit_processes/flash_drum.py:142` — current `flash_temperature_setpoint` shows banned naming and indirect thermal authority.
  - Pattern: `src/modular_simulation/unit_processes/pfr.py:100` — current `jacket_temperature_setpoint` is a utility-boundary surrogate.
  - Pattern: `src/modular_simulation/unit_processes/pump.py:99` — current `pressure_rise_setpoint` is controller-facing but not a physical actuator.
  - Pattern: `src/modular_simulation/unit_processes/splitter.py:97` — current `split_ratios` is a controller-facing allocation surrogate.
  - Pattern: `src/modular_simulation/unit_processes/component_separator.py:169` — current `split_fraction_targets` is a controller-facing spec surrogate.
  - Pattern: `src/modular_simulation/unit_processes/shortcut_distillation.py:210` — current shortcut recoveries are controller-facing product specs.
  - Pattern: `.sisyphus/notepads/process-unit-misalignment-remediation/problems.md` — full seed inventory of known abstraction defects.
  - Test: `tests/components/test_controller_wiring_api.py` — existing controller-facing activation rules provide the enforcement pattern.

  **Acceptance Criteria** (agent-executable only):
  - [ ] A new/updated contract test suite fails if any targeted unit still exposes a public/runtime/persisted `*setpoint` name.
  - [ ] A new/updated contract test suite fails if any reduced-order spec variable remains controller-bindable after remediation.
  - [ ] The inventory of targeted surfaces is encoded in tests rather than only in notes.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Contract suite passes for allowed vs banned surface classes
    Tool: Bash
    Steps: Run `python -m pytest tests/components/test_controller_wiring_api.py tests/unit_process -k "control_surface or actuator_contract or banned_setpoint"`
    Expected: All new contract tests pass; no targeted unit exposes `*setpoint` or non-physical controller surfaces.
    Evidence: .sisyphus/evidence/task-1-control-surface-contract.txt

  Scenario: Banned surface remains controller-bindable
    Tool: Bash
    Steps: Run the negative tests added for runtime activation/metadata validation that attempt to bind a controller to a banned pseudo-actuator tag.
    Expected: Each negative test fails for the right reason before code changes and passes after remediation by raising the expected deterministic error.
    Evidence: .sisyphus/evidence/task-1-control-surface-contract-error.txt
  ```

  **Commit**: YES | Message: `refactor(control): codify control-surface contract` | Files: `src/modular_simulation/**`, `tests/components/**`, `tests/unit_process/**`

- [ ] 2. Refactor public controller semantics from `setpoint` state to `reference` signal

  **What to do**: Update the control-system public contract so controller-public signals use `reference` semantics instead of `setpoint` semantics. Replace public `.sp` point/tag/state exposure with a public `.ref` or equivalent reference-signal contract, while preserving the underlying cascade behavior: AUTO consumes the controller’s local reference trajectory, CASCADE consumes the upstream controller output, and MANUAL bypasses controller output through the control element. Keep any private local implementation names only if they do not appear in public state, persistence, or runtime tags.
  **Must NOT do**: Do not remove CASCADE/AUTO/MANUAL/TRACKING semantics. Do not leave mixed `.sp` and `.ref` public tags alive after the migration window is defined.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: touches controller lifecycle, point registry exposure, and mode semantics.
  - Skills: `[]` — repository-local architecture work only.
  - Omitted: `[playwright]` — no browser/UI work is involved.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 3, 4, 10, 11 | Blocked By: 1

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `src/modular_simulation/components/control_system/abstract_controller.py:46` — `sp_trajectory` is the current public reference source.
  - Pattern: `src/modular_simulation/components/control_system/abstract_controller.py:183` — controller install currently creates a point tagged `"{cv_tag}.sp"`.
  - Pattern: `src/modular_simulation/components/control_system/abstract_controller.py:251` — `ControllerModeManager` is wired with `auto_sp_source` and `cascade_sp_source`.
  - Pattern: `src/modular_simulation/components/control_system/mode_manager.py:211` — AUTO currently uses the local setpoint source.
  - Pattern: `src/modular_simulation/components/control_system/mode_manager.py:222` — CASCADE currently resolves reference from the cascade controller.
  - Pattern: `src/modular_simulation/components/control_system/controller_mode.py:6` — public mode docs currently reference setpoint semantics.
  - Pattern: `src/modular_simulation/framework/system.py` — point registry and controller publication contract must stay coherent after renaming.
  - Test: `tests/controller_contract_harness.py:115` — runtime mutations and activation patterns must survive the rename.
  - Test: `tests/components/test_controller_wiring_api.py` — controller activation/rollback behavior already exists and must be updated rather than replaced.

  **Acceptance Criteria** (agent-executable only):
  - [ ] No public controller point/tag/state name uses `.sp` or `setpoint` after the migration policy is applied.
  - [ ] CASCADE, AUTO, MANUAL, and TRACKING mode tests still pass with the new public reference-signal contract.
  - [ ] Runtime controller creation/binding/activation continues to work through the updated public names.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Mode transitions work with public reference tags
    Tool: Bash
    Steps: Run `python -m pytest tests/controller_contract_harness.py tests/components/test_controller_wiring_api.py -k "reference or cascade or manual or tracking"`
    Expected: All targeted controller/runtime tests pass and only the new reference terminology is exposed publicly.
    Evidence: .sisyphus/evidence/task-2-controller-reference-contract.txt

  Scenario: Legacy public `.sp` tag is still used after migration gate
    Tool: Bash
    Steps: Run the negative tests that attempt to read/write the removed public `.sp` contract beyond the approved compatibility path.
    Expected: The runtime rejects stale `.sp` usage deterministically or emits the expected compatibility warning exactly where policy allows it.
    Evidence: .sisyphus/evidence/task-2-controller-reference-contract-error.txt
  ```

  **Commit**: YES | Message: `refactor(control): rename public setpoint contract to reference` | Files: `src/modular_simulation/components/control_system/**`, `src/modular_simulation/framework/**`, `tests/components/**`, `tests/**`

- [ ] 3. Enforce runtime binding, migration, and rollback rules for banned pseudo-actuators

  **What to do**: Implement the migration policy across runtime wiring, raw-tag resolution, save/load, and publication maps. Constructor/load compatibility aliases may remain for one migration window with deterministic warnings, but runtime controller activation against banned/non-physical tags must fail immediately and rollback cleanly. Ensure vector/scalar validation and queued mutation ordering remain deterministic.
  **Must NOT do**: Do not keep half-migrated aliases where load works but runtime activation still silently binds banned tags. Do not break rollback snapshots or idempotent runtime mutation semantics.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: broad API/persistence surface with strict behavioral contracts.
  - Skills: `[]` — focused repository work only.
  - Omitted: `[playwright]` — no browser/UI work is involved.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 10, 11 | Blocked By: 1, 2

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `src/modular_simulation/components/control_system/runtime_wiring_api.py:12` — controller creation entry point.
  - Pattern: `src/modular_simulation/components/control_system/runtime_wiring_api.py:38` — input binding entry point.
  - Pattern: `src/modular_simulation/components/control_system/runtime_wiring_api.py:56` — output binding entry point.
  - Pattern: `src/modular_simulation/components/control_system/runtime_wiring_api.py:92` — activation entry point.
  - Pattern: `src/modular_simulation/components/control_system/control_element.py` — control-element lookup and mode semantics must remain stable.
  - Pattern: `src/modular_simulation/framework/system.py` — raw state/tag lookup and publication maps must align with migrated names.
  - Test: `tests/components/test_controller_wiring_api.py` — activation, failure, and rollback behavior is already asserted here.
  - Test: `tests/test_save_load_minimal.py:105` — persisted payloads currently include old names such as `pressure_rise_setpoint`.
  - Test: `tests/controller_contract_harness.py:188` — activation contract must stay deterministic.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Constructor/load aliases behave exactly as the migration policy states and are covered by tests.
  - [ ] Runtime activation of banned/non-physical tags fails with deterministic rollback and no snapshot drift.
  - [ ] Vector/scalar mismatch and stale-tag tests still fail deterministically after the migration.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Compatibility path works and rollback remains clean
    Tool: Bash
    Steps: Run `python -m pytest tests/components/test_controller_wiring_api.py tests/test_save_load_minimal.py -k "rollback or compatibility or deprecation or load"`
    Expected: Approved compatibility aliases pass with the documented warning behavior; runtime rollback tests pass unchanged.
    Evidence: .sisyphus/evidence/task-3-runtime-migration-contract.txt

  Scenario: Stale pseudo-actuator tag is activated at runtime
    Tool: Bash
    Steps: Run the negative controller-wiring tests that attempt activation against removed/banned tags and vector-shape mismatches.
    Expected: Activation fails deterministically, rollback is preserved, and no partial wiring survives.
    Evidence: .sisyphus/evidence/task-3-runtime-migration-contract-error.txt
  ```

  **Commit**: YES | Message: `refactor(runtime): enforce pseudo-actuator migration rules` | Files: `src/modular_simulation/components/control_system/**`, `src/modular_simulation/framework/**`, `tests/components/**`, `tests/**`

- [ ] 4. Unify pump control on one physical actuator source of truth

  **What to do**: Replace the split `pressure_rise_setpoint`/`pressure_rise` authority with a single physical actuator contract centered on pump speed. The unit model, controller-facing actuator surface, and flowsheet hydraulic solver must all consume the same `pump_speed` state/input, while pressure rise becomes a derived consequence of the pump curve rather than an independently commanded state. Update tests, save/load coverage, and any runtime tags accordingly.
  **Must NOT do**: Do not leave hydraulics keyed off one field while unit thermodynamics/controllers use another. Do not keep `pressure_rise_setpoint` as a public compatibility surface beyond the defined migration path.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: highest-severity cross-layer authority split and core hydraulic/control dependency.
  - Skills: `[]` — repo-local code and tests only.
  - Omitted: `[playwright]` — no browser/UI work is involved.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 8, 10, 11 | Blocked By: 2

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `src/modular_simulation/unit_processes/pump.py:99` — current controller-facing `pressure_rise_setpoint`.
  - Pattern: `src/modular_simulation/unit_processes/pump.py:105` — current design-time `pressure_rise` field.
  - Pattern: `src/modular_simulation/unit_processes/pump.py:326` — runtime calculations currently read `pressure_rise_setpoint`.
  - Pattern: `src/modular_simulation/flowsheet/flowsheet.py:873` — hydraulic solver detects `PumpHydraulicElement`.
  - Pattern: `src/modular_simulation/flowsheet/flowsheet.py:878` — hydraulic solver currently sources pump head from `pressure_rise`.
  - Pattern: `src/modular_simulation/connection/hydraulic_element.py` — pump element consumes `pump_speed` as the hydraulic parameter.
  - Test: `tests/unit_process/test_layer4_pump_valve.py:159` — current pump runtime semantics and deprecation coverage.
  - Test: `tests/unit_process/test_hydraulic_elements.py:104` — pump hydraulic-element tests already exercise the proxy semantics.
  - Test: `tests/test_save_load_minimal.py:105` — persisted payload currently stores `pressure_rise_setpoint`.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Pump unit calculations and hydraulic-network calculations use the same public actuator field.
  - [ ] No public runtime/persistence path depends on `pressure_rise_setpoint` after the migration policy is applied.
  - [ ] Pump unit tests, hydraulic solver tests, and save/load tests pass with the unified actuator contract.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Pump unit and network agree on the same actuator
    Tool: Bash
    Steps: Run `python -m pytest tests/unit_process/test_layer4_pump_valve.py tests/unit_process/test_hydraulic_elements.py tests/connection/test_hydraulic_solver.py -k pump`
    Expected: All pump-related tests pass and no assertion references diverging unit-vs-network pump-head sources.
    Evidence: .sisyphus/evidence/task-4-pump-single-source.txt

  Scenario: Legacy pressure-rise proxy is activated after migration
    Tool: Bash
    Steps: Run the negative migration/runtime tests that attempt to bind or persist `pressure_rise_setpoint` as the public actuator after the migration path closes.
    Expected: The system rejects the stale public proxy deterministically or emits the approved compatibility warning only where policy allows it.
    Evidence: .sisyphus/evidence/task-4-pump-single-source-error.txt
  ```

  **Commit**: YES | Message: `refactor(pump): unify actuator authority on pump speed` | Files: `src/modular_simulation/unit_processes/pump.py`, `src/modular_simulation/flowsheet/flowsheet.py`, `tests/unit_process/**`, `tests/connection/**`, `tests/**`

- [ ] 5. Remove unit-internal CSTR volume control and make level/volume external-actuator driven

  **What to do**: Remove `reactor_volume_setpoint` and any embedded supervisory law that makes CSTR volume look directly controllable. Publish reactor volume/level only as measured state. The canonical control pattern must be an external controller/cascade chain that manipulates a physical final element, with the default documented pattern being reactor volume/level controller -> outlet valve opening (or discharge pump speed where a pump is explicitly modeled). Update unit tests and at least one flowsheet/integration example to use that external-actuator pattern.
  **Must NOT do**: Do not replace the embedded setpoint with another hidden supervisory proxy. Do not make the CSTR itself own a hidden valve unless the unit explicitly models that actuator as part of its contract.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: changes reactor semantics and the recommended control topology.
  - Skills: `[]` — repo-local model and test work only.
  - Omitted: `[playwright]` — no browser/UI work is involved.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 10, 11 | Blocked By: 1

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `src/modular_simulation/unit_processes/cstr.py:104` — current `reactor_volume_setpoint` definition.
  - Pattern: `src/modular_simulation/unit_processes/cstr.py:175` — current seeding from `reactor_volume`.
  - Pattern: `src/modular_simulation/unit_processes/cstr.py:468` — runtime calculations currently consume `reactor_volume_setpoint`.
  - Pattern: `src/modular_simulation/components/control_system/control_element.py` — final actuator wiring must terminate here, not inside CSTR state logic.
  - Pattern: `src/modular_simulation/components/control_system/abstract_controller.py` — cascade/reference behavior to follow for the external level loop.
  - Test: `tests/unit_process/test_layer4_cstr.py` — unit-level CSTR behavior anchor.
  - Test: `tests/unit_process/test_flowsheet_integration.py` — integration pattern for replacing internal control with external wiring.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `reactor_volume_setpoint` is gone from public/runtime/persisted state and no longer participates in unit calculations.
  - [ ] CSTR still publishes measured volume/level and passes its unit tests.
  - [ ] At least one controller/integration test demonstrates level or volume control through an external final element rather than unit-internal supervisory logic.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: CSTR level control is exercised through an external actuator
    Tool: Bash
    Steps: Run `python -m pytest tests/unit_process/test_layer4_cstr.py tests/unit_process/test_flowsheet_integration.py -k "cstr and (level or volume or valve or cascade)"`
    Expected: The CSTR tests pass and the integration case shows external-actuator-driven control without any public `reactor_volume_setpoint`.
    Evidence: .sisyphus/evidence/task-5-cstr-volume-control.txt

  Scenario: Runtime activation still targets the removed CSTR proxy
    Tool: Bash
    Steps: Run the negative controller-wiring tests that attempt to bind against the removed CSTR volume proxy tag.
    Expected: Activation fails deterministically and rollback remains intact.
    Evidence: .sisyphus/evidence/task-5-cstr-volume-control-error.txt
  ```

  **Commit**: YES | Message: `refactor(cstr): remove internal volume setpoint control` | Files: `src/modular_simulation/unit_processes/cstr.py`, `tests/unit_process/**`, `tests/components/**`

- [ ] 6. Reclassify flash-drum and PFR indirect thermal/pressure surfaces as external boundaries, not controller states

  **What to do**: Remove `flash_pressure`, `flash_temperature_setpoint`, and `jacket_temperature_setpoint` from the controller-facing unit-state portfolio. Keep idealized operating conditions only as explicit external boundary parameters with non-controller names: use `imposed_pressure` and `imposed_temperature` for the idealized flash contract, and `imposed_jacket_temperature` for the PFR utility boundary. The physical control story must be external: flash pressure is controlled through a vapor-outlet backpressure element; flash/PFR temperature is controlled through upstream/downstream thermal equipment or utility-side control elements.
  **Must NOT do**: Do not keep the old names as controller-facing aliases. Do not let the bare flash drum or PFR masquerade as if they own the physical final actuator.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: touches two important unit families plus controller-facing semantics.
  - Skills: `[]` — repository-local model/test work only.
  - Omitted: `[playwright]` — no browser/UI work is involved.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 10, 11 | Blocked By: 1

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `src/modular_simulation/unit_processes/flash_drum.py:138` — current `flash_pressure` definition.
  - Pattern: `src/modular_simulation/unit_processes/flash_drum.py:142` — current `flash_temperature_setpoint` definition.
  - Pattern: `src/modular_simulation/unit_processes/flash_drum.py:366` — outlet pressure currently follows `flash_pressure` directly.
  - Pattern: `src/modular_simulation/unit_processes/flash_drum.py:369` — flash temperature is currently imposed directly into the flash calculation.
  - Pattern: `src/modular_simulation/unit_processes/pfr.py:100` — current `jacket_temperature_setpoint` definition.
  - Pattern: `src/modular_simulation/unit_processes/pfr.py:562` — runtime calculations currently consume the PFR jacket proxy.
  - Test: `tests/unit_process/test_layer4_flash_drum.py` — flash-drum regression anchor.
  - Test: `tests/unit_process/test_layer4_pfr.py` — PFR regression anchor.
  - Test: `tests/components/test_controller_wiring_api.py` — removed pseudo-actuator bindings must fail here.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Flash drum and PFR no longer expose controller-facing `setpoint`-style or pseudo-actuator thermal/pressure state names.
  - [ ] Idealized boundary-condition variants, if retained, use explicit non-controller names and are documented as external conditions.
  - [ ] Unit tests and controller-wiring rejection tests pass for the new contracts.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Flash drum and PFR pass with boundary-condition naming only
    Tool: Bash
    Steps: Run `python -m pytest tests/unit_process/test_layer4_flash_drum.py tests/unit_process/test_layer4_pfr.py -k "flash or jacket or pressure or temperature"`
    Expected: Unit tests pass with the new boundary-condition names and no public controller-facing pseudo-actuator states.
    Evidence: .sisyphus/evidence/task-6-flash-pfr-boundaries.txt

  Scenario: Removed flash/PFR pseudo-actuator tags are activated at runtime
    Tool: Bash
    Steps: Run the negative controller-wiring tests for removed flash and PFR tags.
    Expected: Runtime activation fails deterministically and rollback remains intact.
    Evidence: .sisyphus/evidence/task-6-flash-pfr-boundaries-error.txt
  ```

  **Commit**: YES | Message: `refactor(thermal): demote flash and pfr pseudo-actuators` | Files: `src/modular_simulation/unit_processes/flash_drum.py`, `src/modular_simulation/unit_processes/pfr.py`, `tests/unit_process/**`, `tests/components/**`

- [ ] 7. Demote heater/cooler and conversion-reactor pressure or thermal proxies to fixed design data or explicit boundaries

  **What to do**: Remove controller-facing `pressure_drop` and idealized temperature/duty proxies from the affected thermal/reaction units unless a physical final element is modeled explicitly. For `HeaterCooler`, treat pressure drop as fixed/configured hydraulic data or move pressure authority to an explicit valve/restriction element; demote any remaining idealized temperature/duty knobs to explicit external boundary parameters with non-controller names. For `ConversionReactor`, keep `pressure_drop` only as fixed design/hydraulic data unless and until a physical restriction element is modeled.
  **Must NOT do**: Do not leave nouns like `pressure_drop` or idealized duty/temperature fields exposed as if they were direct manipulators. Do not expand this task into a full exchanger-physics redesign.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: multi-unit cleanup with clear but bounded semantics.
  - Skills: `[]` — repository-local work only.
  - Omitted: `[playwright]` — no browser/UI work is involved.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 10, 11 | Blocked By: 1

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `.sisyphus/notepads/process-unit-misalignment-remediation/problems.md:2` — heater/cooler target-temperature and duty proxy concern.
  - Pattern: `.sisyphus/notepads/process-unit-misalignment-remediation/problems.md:8` — heater/cooler `pressure_drop` concern.
  - Pattern: `src/modular_simulation/unit_processes/heater_cooler.py:114` — current `pressure_drop` definition.
  - Pattern: `src/modular_simulation/unit_processes/heater_cooler.py:309` — outlet pressure currently follows `inlet_pressure - pressure_drop`.
  - Pattern: `src/modular_simulation/unit_processes/conversion_reactor.py:271` — current `pressure_drop` definition.
  - Pattern: `src/modular_simulation/unit_processes/conversion_reactor.py:535` — outlet pressure currently follows `inlet_pressure - pressure_drop`.
  - Test: `tests/unit_process/test_layer4_heater_cooler.py` — heater/cooler regression anchor.
  - Test: `tests/unit_process/test_layer4_conversion_reactor.py` — conversion-reactor regression anchor if present; otherwise create the nearest equivalent unit/regression file in the existing test layout.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Affected thermal/reaction units no longer expose controller-facing `pressure_drop` or idealized thermal proxy state names as MVs.
  - [ ] Any retained idealized boundary parameter uses explicit non-controller naming and is covered by tests.
  - [ ] Unit tests pass with fixed-design or explicit-boundary semantics.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Heater/cooler and conversion reactor pass with demoted proxy semantics
    Tool: Bash
    Steps: Run `python -m pytest tests/unit_process/test_layer4_heater_cooler.py tests/unit_process -k "conversion_reactor or pressure_drop or duty or temperature"`
    Expected: Relevant unit tests pass and no controller-facing proxy fields remain exposed as MVs.
    Evidence: .sisyphus/evidence/task-7-thermal-proxy-cleanup.txt

  Scenario: Removed thermal/reaction proxy tags are used as runtime actuators
    Tool: Bash
    Steps: Run the negative runtime/controller tests for removed `pressure_drop` or thermal proxy tags.
    Expected: Activation fails deterministically and compatibility behavior matches the migration policy.
    Evidence: .sisyphus/evidence/task-7-thermal-proxy-cleanup-error.txt
  ```

  **Commit**: YES | Message: `refactor(units): demote thermal and pressure proxy surfaces` | Files: `src/modular_simulation/unit_processes/heater_cooler.py`, `src/modular_simulation/unit_processes/conversion_reactor.py`, `tests/unit_process/**`, `tests/components/**`

- [ ] 8. Make the physical splitter hydraulic-owned and remove split-ratio actuator authority

  **What to do**: Make the base `Splitter` a hydraulic/topology-owned branch-allocation unit. Remove `split_ratios` from the controller-facing runtime state of the physical splitter and let branch flow emerge from pressures, valves, and resistances. If the repo still needs abstract branch allocation for reduced-order studies, introduce a separate explicitly abstract unit (for example `IdealSplitter`) rather than overloading the physical splitter contract. Update flowsheet and unit tests so there is no dual authority between splitter-internal branch allocation and the hydraulic network.
  **Must NOT do**: Do not preserve the current hybrid implicit overlap where `Splitter` publishes branch flows while the network also solves them. Do not keep `split_ratios` as a hidden alias on the physical splitter.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: cross-layer unit/network authority change with flowsheet implications.
  - Skills: `[]` — repository-local work only.
  - Omitted: `[playwright]` — no browser/UI work is involved.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: 10, 11 | Blocked By: 1, 4

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `src/modular_simulation/unit_processes/splitter.py:97` — current `split_ratios` definition.
  - Pattern: `src/modular_simulation/unit_processes/splitter.py:305` — runtime calculations currently consume `split_ratios` to compute branch allocation.
  - Pattern: `.sisyphus/notepads/process-unit-misalignment-remediation/problems.md:14` — existing split-authority architecture finding.
  - Pattern: `src/modular_simulation/flowsheet/flowsheet.py` — hydraulic-system construction is the competing branch-flow authority.
  - Test: `tests/unit_process/test_layer4_mixer_splitter.py:180` — current splitter ratio semantics test.
  - Test: `tests/unit_process/test_flowsheet_integration.py` — flowsheet-level authority reconciliation must be verified here.
  - Test: `tests/connection/test_hydraulic_solver.py` — hydraulic branch flow behavior anchor.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Base `Splitter` no longer exposes controller-facing `split_ratios` or internally publishes branch flows as an independent hydraulic authority.
  - [ ] Flowsheet and hydraulic tests prove branch allocation now comes from the network for the physical splitter.
  - [ ] If an abstract allocation unit is added, it is explicitly segregated from the physical splitter contract and tested separately.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Physical splitter branch allocation is solved hydraulically
    Tool: Bash
    Steps: Run `python -m pytest tests/unit_process/test_layer4_mixer_splitter.py tests/unit_process/test_flowsheet_integration.py tests/connection/test_hydraulic_solver.py -k splitter`
    Expected: Splitter-related tests pass and all branch-allocation assertions route through the hydraulic solver for the physical splitter.
    Evidence: .sisyphus/evidence/task-8-splitter-hydraulic-ownership.txt

  Scenario: Removed split-ratio actuator is targeted at runtime
    Tool: Bash
    Steps: Run the negative controller-wiring/runtime tests that attempt to bind against the removed physical-splitter ratio tag.
    Expected: The runtime rejects the stale tag deterministically and rollback remains intact.
    Evidence: .sisyphus/evidence/task-8-splitter-hydraulic-ownership-error.txt
  ```

  **Commit**: YES | Message: `refactor(splitter): move branch allocation to hydraulics` | Files: `src/modular_simulation/unit_processes/splitter.py`, `src/modular_simulation/flowsheet/**`, `tests/unit_process/**`, `tests/connection/**`

- [ ] 9. Demote abstract separator and shortcut-distillation specs out of the runtime actuator portfolio

  **What to do**: Keep `ComponentSeparator` and `ShortcutDistillation` explicitly usable as reduced-order abstract models, but remove their specification variables from the runtime controller-facing actuator portfolio. Convert `split_fraction_targets`, `light_key_distillate_recovery`, `heavy_key_bottoms_recovery`, `reflux_ratio_setpoint`, and `reflux_ratio_factor` into non-controller configured specification parameters with explicit names that communicate abstraction (for example `configured_split_fractions`, `configured_light_key_recovery`, `configured_reflux_ratio`). Runtime controller activation must reject them. Document that physical control for separation performance belongs in family-specific higher-fidelity units and physical manipulated quantities.
  **Must NOT do**: Do not pretend these configured specs are physical MVs. Do not remove the reduced-order units entirely in this pass.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: broad API cleanup across abstract reduced-order units with significant test impact.
  - Skills: `[]` — repository-local code/test work only.
  - Omitted: `[playwright]` — no browser/UI work is involved.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: 10, 11 | Blocked By: 1

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `src/modular_simulation/unit_processes/component_separator.py:169` — current `split_fraction_targets` definition.
  - Pattern: `src/modular_simulation/unit_processes/component_separator.py:417` — current direct partitioning from `split_fraction_targets`.
  - Pattern: `src/modular_simulation/unit_processes/shortcut_distillation.py:210` — current `light_key_distillate_recovery` definition.
  - Pattern: `src/modular_simulation/unit_processes/shortcut_distillation.py:214` — current `heavy_key_bottoms_recovery` definition.
  - Pattern: `src/modular_simulation/unit_processes/shortcut_distillation.py:218` — current `reflux_ratio_factor` definition.
  - Pattern: `src/modular_simulation/unit_processes/shortcut_distillation.py:226` — current `reflux_ratio_setpoint` definition.
  - Pattern: `src/modular_simulation/unit_processes/shortcut_distillation.py:649` — current fallback `reflux_ratio_factor * r_min` behavior.
  - Test: `tests/unit_process/test_layer4_component_separator.py:171` — separator runtime semantics anchor.
  - Test: `tests/unit_process/test_layer4_distillation.py:146` — shortcut-distillation runtime semantics anchor.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Runtime controller activation rejects the abstract separator/distillation spec surfaces.
  - [ ] Reduced-order units still function as configured models under their explicit non-controller spec names.
  - [ ] Distillation and separator tests pass with the new configured-spec semantics.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Reduced-order separator and distillation models still run as configured specs
    Tool: Bash
    Steps: Run `python -m pytest tests/unit_process/test_layer4_component_separator.py tests/unit_process/test_layer4_distillation.py -k "separator or distillation or reflux or recovery"`
    Expected: Unit tests pass, but none of the configured-spec variables remain runtime controller actuators.
    Evidence: .sisyphus/evidence/task-9-abstract-spec-cleanup.txt

  Scenario: Runtime binds a controller to an abstract configured spec
    Tool: Bash
    Steps: Run the negative controller-wiring tests for removed separator/distillation pseudo-actuator tags.
    Expected: Runtime activation fails deterministically and rollback remains intact.
    Evidence: .sisyphus/evidence/task-9-abstract-spec-cleanup-error.txt
  ```

  **Commit**: YES | Message: `refactor(models): demote abstract spec surfaces from runtime control` | Files: `src/modular_simulation/unit_processes/component_separator.py`, `src/modular_simulation/unit_processes/shortcut_distillation.py`, `tests/unit_process/**`, `tests/components/**`

- [ ] 10. Migrate persistence, fixtures, examples, and docs to the new control vocabulary and contracts

  **What to do**: Update constructor aliases, load/save payloads, raw-tag resolution, examples, and docs so they reflect the remediated control vocabulary. Keep compatibility behavior exactly as defined in Task 3: constructor/load aliases may emit deterministic deprecation warnings during the migration window, but public runtime controller tags must use the new contracts immediately. Update representative examples and wiring docs to show cascade control onto a physical control element instead of unit-internal pseudo-actuators.
  **Must NOT do**: Do not leave stale examples, save/load snapshots, or wiring docs that still teach removed `setpoint`/pseudo-actuator patterns. Do not silently persist old names under new wrappers.

  **Recommended Agent Profile**:
  - Category: `writing` — Reason: this task is migration-surface cleanup heavy and must explain the new semantics clearly.
  - Skills: `[]` — repository-local docs/examples/persistence work only.
  - Omitted: `[playwright]` — no browser/UI work is involved.

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocks: 11 | Blocked By: 1, 2, 3, 4, 5, 6, 7, 8, 9

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `tests/test_save_load_minimal.py:105` — persisted payloads currently include old public names.
  - Pattern: `tests/test_save_load_minimal.py:149` — save/load regression anchor for renamed state surfaces.
  - Pattern: `src/modular_simulation/components/control_system/controllers/wiring.md` — wiring documentation must reflect the cascade-to-actuator contract.
  - Pattern: `src/modular_simulation/components/control_system/runtime_wiring_api.py` — docs/examples for runtime controller creation/binding/activation must match the new tags.
  - Pattern: `.sisyphus/notepads/process-unit-misalignment-remediation/problems.md` — seed list for migration messaging and release notes.
  - Test: `tests/controller_contract_harness.py` — example-like controller runtime usage.
  - Test: `tests/integration/test_dynamic_process_network_workflow.py` — integration/example workflow anchor.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Save/load tests pass with the documented compatibility behavior.
  - [ ] Wiring docs and examples use only the new public control vocabulary and physical-actuator patterns.
  - [ ] No representative example or fixture teaches removed pseudo-actuator usage.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Save/load, examples, and wiring docs align with the new contract
    Tool: Bash
    Steps: Run `python -m pytest tests/test_save_load_minimal.py tests/integration/test_dynamic_process_network_workflow.py tests/controller_contract_harness.py`
    Expected: Persistence and workflow tests pass while docs/examples/fixtures reference only the new vocabulary and actuator patterns.
    Evidence: .sisyphus/evidence/task-10-migration-docs.txt

  Scenario: Stale example or save/load payload still depends on removed public names
    Tool: Bash
    Steps: Run the migration compatibility tests and any grep-backed assertions added for stale example/docs usage.
    Expected: The suite fails until all stale public names are removed or intentionally covered by the documented migration path.
    Evidence: .sisyphus/evidence/task-10-migration-docs-error.txt
  ```

  **Commit**: YES | Message: `docs(control): migrate examples and persistence contracts` | Files: `tests/**`, `src/modular_simulation/components/control_system/**`, `docs/** if present`, `.sisyphus/notepads/** if updated`

- [ ] 11. Run the end-to-end regression wave and prove the new control architecture under dynamics

  **What to do**: Add or update the end-to-end regression scenarios that demonstrate the intended architecture in action: controller reference -> cascade -> physical control element -> controllable process state. Cover at least pump-speed control, CSTR level/volume control through an outlet element, and one thermal/pressure boundary case. Then run the targeted suites plus the full `tests/unit_process` pass and fix any fallout until the portfolio is coherent.
  **Must NOT do**: Do not stop at isolated unit tests. Do not declare success without hydraulic, integration, and persistence coverage.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: final cross-cutting proof across control, hydraulics, units, and workflows.
  - Skills: `[]` — repository-local verification work only.
  - Omitted: `[playwright]` — no browser/UI work is involved.

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocks: Final Verification Wave | Blocked By: 1, 2, 3, 4, 5, 6, 7, 8, 9, 10

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `tests/unit_process/test_flowsheet_integration.py` — core flowsheet regression harness.
  - Pattern: `tests/integration/test_dynamic_process_network_workflow.py` — dynamic network workflow regression anchor.
  - Pattern: `tests/connection/test_hydraulic_solver.py` — hydraulic coupling regression anchor.
  - Pattern: `tests/connection/test_hydraulic_solver_solvability.py` — solvability regression anchor.
  - Pattern: `tests/components/test_controller_wiring_api.py` — runtime binding/rollback regression anchor.
  - Pattern: `tests/controller_contract_harness.py` — controller lifecycle/runtime harness.
  - Test: `tests/unit_process` — final portfolio-wide unit-process pass.

  **Acceptance Criteria** (agent-executable only):
  - [ ] All targeted regression commands in the Definition of Done pass.
  - [ ] New end-to-end scenarios prove cascade-to-actuator behavior for at least pump, CSTR, and one thermal/pressure case.
  - [ ] No rollback, solvability, or save/load regression remains in the targeted remediation portfolio.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Full targeted regression wave passes
    Tool: Bash
    Steps: Run the exact Definition-of-Done commands in order, ending with `python -m pytest tests/unit_process`.
    Expected: Every command exits 0 and the evidence bundle shows the final green regression state.
    Evidence: .sisyphus/evidence/task-11-end-to-end-regression.txt

  Scenario: Cross-layer regression remains after unit-level fixes
    Tool: Bash
    Steps: Run `python -m pytest tests/connection/test_hydraulic_solver.py tests/connection/test_hydraulic_solver_solvability.py tests/unit_process/test_flowsheet_integration.py tests/integration/test_dynamic_process_network_workflow.py`
    Expected: Any remaining cross-layer defect is surfaced here; task is incomplete until all of these pass together.
    Evidence: .sisyphus/evidence/task-11-end-to-end-regression-error.txt
  ```

  **Commit**: YES | Message: `test(control): prove remediated control architecture end to end` | Files: `tests/**`, `src/modular_simulation/**`

## Final Verification Wave (4 parallel agents, ALL must APPROVE)
- [ ] F1. Plan Compliance Audit — oracle
- [ ] F2. Code Quality Review — unspecified-high
- [ ] F3. Real Manual QA — unspecified-high
- [ ] F4. Scope Fidelity Check — deep

## Commit Strategy
- Commit Wave 1 foundation changes together so the shared control-surface contract and controller/runtime APIs land atomically.
- Commit Wave 2 unit-family remediations in 2-3 focused commits grouped by semantic family (`reactor/boundary`, `hydraulic split`, `pressure/thermal cleanup`).
- Commit Wave 3 migration/docs/examples and final regression adjustments separately so compatibility fallout is isolated.

## Success Criteria
- Controller-facing unit surfaces correspond only to physical actuators or explicitly documented external boundaries/specifications.
- No public process-model state, runtime actuator tag, or persisted payload exposes `setpoint` semantics.
- Pump, splitter, and other remediated quantities have exactly one authority path.
- Targeted controller, hydraulic, integration, and save/load suites pass without rollback or solvability regressions.

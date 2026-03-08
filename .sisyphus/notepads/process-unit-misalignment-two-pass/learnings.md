# Task 1 Learnings

## Pass 1 Classification Patterns

### Mode Selector Pattern (4 units)
Units with mode selectors that switch operational modes:
- HeaterCooler: mode field (0=duty, 1=temperature)
- FlashDrum: thermal_mode field (0=adiabatic, 1=isothermal)
- ConversionReactor: thermal_mode field (0=adiabatic, 1=isothermal)
- HeatExchanger: flow_arrangement field (0=counter, 1=co, 2=cross)

Pattern: All mode selectors are T.CONSTANT with numeric encoding, validated via _mode_from_selector() helper functions.

### Setpoint Pattern (4 units)
Units with explicit setpoint fields:
- HeaterCooler: duty_setpoint, target_temperature_setpoint (T.CONTROLLED)
- FlashDrum: flash_temperature_setpoint (T.CONTROLLED)
- CSTR: reactor_volume (T.CONSTANT) - setpoint with internal level_control_gain
- ShortcutDistillation: reflux_ratio_setpoint (T.CONTROLLED)

Pattern: Setpoints named *_setpoint except CSTR which uses reactor_volume with gain.

### Internal Control Law Pattern (1 unit)
- CSTR: reactor_volume setpoint with level_control_gain creates internal volume control loop
  - Outlet flow calculated as: inlet_flow + level_gain * (volume - volume_setpoint)
  - This is a Proportional-only controller embedded in the unit physics

### Actuation Constant Pattern (3 units)
Units with T.CONSTANT fields providing actuation-like behavior:
- Pump: pressure_rise (constant-tag actuation contract)
- PFR: jacket_temperature, heat_transfer_coeff, jacket_area (thermal actuation)
- ComponentSeparator: split_fractions (constant split-fraction contract)

Pattern: Constants that control process behavior despite being T.CONSTANT (not T.CONTROLLED).

### Direct MV Candidate Pattern (2 units)
Units with T.CONTROLLED fields that are direct MV candidates:
- Valve: open_fraction (throttling control)
- Splitter: split_ratios (flow split control)

Pattern: T.CONTROLLED fields that directly manipulate process flows/ratios.

## Pass 2 Audit Scope

All 12 units require Pass 2 audit for:
- Naming consistency: mode/setpoint/parameter terminology patterns
- Validation consistency: finite checks, pressure floors, composition normalization
- Edge-case semantics: mode parsing strictness, no-flow behavior

## Inventory Statistics

- Total units: 12
- Pass 1 included: 11 (92%)
- Pass 1 excluded: 1 (8% - Mixer only, pure passive mixing with no control-contract elements)
- Pass 2 included: 12 (100%)

## Evidence Verification

Both Task 1 acceptance commands passed:
- task1-inventory-ok: All 12 unit files enumerated correctly
- task1-rubric-base-ok: All required units present

## Task 3 Learnings

- Direct controller readiness in this repo is strongest when the candidate MV already lives in `process_model.controlled_view`, because `System._validate_controllers_resolvable()` treats those tags as first-class control elements.
- Wrapped subsystems make local CV/MV binding practical because `create_subsystem_for_unit()` publishes algebraic outputs and `Subsystem._refresh_published_process_view()` expands visibility to the full unit `state_list`.
- HeaterCooler is the only unit with explicit end-to-end wrapped-unit evidence for direct runtime binding today: `target_temperature_setpoint` is bound as an MV against an `outlet_temperature` sensor alias.

## Task 4 Learnings

- HeaterCooler is the only concrete unit with explicit unit-specific controller coupling evidence in `tests/unit_process/test_flowsheet_integration.py`, where `mv_tag="target_temperature_setpoint"` is bound to a real unit field.
- FlashDrum, CSTR, ConversionReactor, Pump, Valve, Splitter, HeatExchanger, and ComponentSeparator all have direct unit-specific Pass 1 surface coverage in dedicated layer4 tests even when controller-wiring tests are absent.
- ShortcutDistillation has direct tests for recovery and reflux-factor controls, but the explicit `reflux_ratio_setpoint` candidate from Task 1 is not exercised in the current unit-specific test set.
- PFR currently has only physics-oriented unit tests in the reviewed directories; no unit-specific test or example exercises the Task 1 Pass 1 jacket-actuation candidates.

## Task 2 Learnings

- Pass 1 control surfaces split into three dominant archetypes across units: (a) explicit mode plus setpoint pairs (`HeaterCooler`, `FlashDrum`), (b) direct MV tags (`Valve.open_fraction`, `Splitter.split_ratios`), and (c) constant-encoded actuation surfaces (`Pump.pressure_rise`, `PFR.jacket_temperature`, `ComponentSeparator.split_fractions`, `HeatExchanger.ua`).
- `CSTR` remains a special internal-control unit: `reactor_volume` is modeled as a constant setpoint and combined with `level_control_gain` to compute `outlet_flow` via an embedded proportional law (`outlet_flow = inlet_flow + level_gain * (volume - volume_setpoint)`).
- `ConversionReactor` hotspot confirmed for Pass 1: it has an explicit `thermal_mode` selector and runtime mode branches, while reaction-driving knobs (`conversion_fractions`, `stoichiometric_matrix`) are currently constant-tagged rather than MV-tagged.
- `ShortcutDistillation` is the densest explicit controlled setpoint cluster in this set (`reflux_ratio_setpoint`, recoveries, reflux factor) and should stay high-visibility in later severity ranking.

## Task 5 Learnings

- Severity ranking was most stable when combining Task 3 runtime-readiness labels with Task 4 coverage labels; `missing` plus `ready-with-adapter` generated the top-priority row (`pfr`).
- `conversion_reactor` must remain Pass 1-included even as `not-ready`: explicit mode selection plus constant-encoded reaction knobs creates a real control-contract hotspot rather than a pure Pass 2 naming issue.
- `shortcut_distillation` should be treated as direct-ready but still medium-priority because partial coverage centers on a concrete omitted setpoint path (`reflux_ratio_setpoint`), making this a test-completeness remediation before interface redesign.
- `heater_cooler` remains the reference contract because it is the only concrete unit with explicit integration-level controller-to-unit MV coupling evidence.

## Task 6 Learnings

- Pass 2 taxonomy successfully separates broader model-consistency scope (naming/validation/edge-case/cross-unit coherence) from Pass 1 control-contract scope, preventing scope drift.
- Detection rules are deterministic across all 4 categories with explicit file scan patterns, evidence formats, and misalignment conditions that Tasks 7 and 8 can execute directly.
- Severity rubric is actionable and principled: high severity assigned for controller intent obscuration or runtime risk; medium for silent failure risk or confusion; low for cosmetic differences.
- Non-goals section effectively prevents Pass 2 from drifting back into Pass 1 actuator redesign, controller-readiness evaluation, or runtime contract safety.
- Cross-unit contract coherence category bridges individual unit audits to portfolio-level terminology alignment (e.g., thermal mode terminology, actuation surface naming).
- Taxonomy completeness verification ensures Tasks 7 and 8 have all required categories, detection rules, and severity rubrics before starting the scans.

## Task 8 Learnings

- The clearest Category 2 and 3 reactor-family gap is not naming but constructor-vs-runtime validation shape: `CSTR`, `PFR`, and `ConversionReactor` validate internal parameters, while controlled inlet scalars are either deferred or silently clamped later.
- `Mixer` and `Splitter` are the strongest cross-unit pressure outliers in Pass 2 because they only require finite pressure and propagate negative values unchanged, unlike the positive-pressure contract used by most other units.
- `Pump` exposes the sharpest edge-case semantic split inside a single unit: algebraic zero-flow behavior adds pressure-rise heating while `step()` explicitly preserves inlet temperature.
- Zero-flow composition fallbacks split cleanly by model type: reactor holdup models (`CSTR`, `PFR`) use uniform composition recovery, while pass-through and separation units preserve feed composition.

## Task 7 Learnings

- Exact field names matter more than token counts: `pressure_drop` is a stronger contract-coherence signal than broader pressure vocabulary because the same noun flips from `T.CONTROLLED` in `heater_cooler` to `T.CONSTANT` in `conversion_reactor` while the outlet-pressure equation stays the same.
- `CSTR` confirms the need to anchor naming findings in field semantics, not grep counts alone: `reactor_volume` only qualifies as a naming mismatch because the description calls it a setpoint and the outlet-flow law materializes `volume_setpoint` from that field.
- Thermal conductance terminology is portfolio-fragmented even when the physics role matches: `heat_exchanger.ua` and reactor-side `heat_transfer_coeff * jacket_area` have the same contract role but require equation-level evidence to prove equivalence.

## Task 9 Learnings

- A severity-ranked Pass 2 register is clearer when split into two explicit sections: actionable misalignments first, then benign divergences, while keeping one shared schema.
- Cross-linking overlaps to `.sisyphus/evidence/task-5-pass1-register.md` prevents duplicate issue narratives and keeps Pass 2 focused on consistency dimensions instead of reopening Pass 1 scoring.
- Using exact relative file paths in both `unit` and `evidence` fields makes Task 9 checks deterministic and keeps handoff to Task 10 dependency sequencing straightforward.

## Task 10 Learnings

- The cleanest execution-ready merge keeps Pass 1 remediation groups ahead of every Pass 2 group, even when some Pass 2 `high` rows look urgent, because unresolved actuator-contract decisions would otherwise destabilize later naming and validation cleanup.
- Task 10 is easier to reuse in Task 11 when every group repeats the same four fields, `dependency`, `rollback guardrail`, `stop condition`, and `priority order`, instead of relying on narrative-only sequencing.
- Preserving the verified severity baseline without deviation keeps `PFR`, `ConversionReactor`, `HeatExchanger`, then `ShortcutDistillation`/`CSTR`/`Pump`/`ComponentSeparator`, then `Splitter`/`FlashDrum`/`Valve`/`HeaterCooler` at the front of Pass 1 work, while Pass 2 `high` items remain queued behind completed Pass 1 contract stabilization.

## Task 11 Learnings

- The Task 11 acceptance-command order is truly fail-fast: `ruff` blocked `mypy`, the targeted `pytest` bundle, and the artifact-index check from running, so the verification wave produced a precise repo baseline rather than a partial success narrative.
- The current blocking quality baseline is outside the audit artifacts: `src/modular_simulation/cli/backend_session.py` has 4 unused imports and `tests/unit_process/test_hydraulic_elements.py` has 1 unused import, all reported by `ruff` as fixable `F401` findings.
- Task 10's group-order guidance still applies even in failure mode: the first quality gate should fail before any later pass-order interpretation or artifact-index conclusions are made.

## Task 11 Rerun Learnings

- After the lint unblock, the same Task 11 sequence advanced one gate further: `ruff` now passes cleanly, so `mypy` is the next real reproducibility blocker for the final verification wave.
- The current typed baseline is concentrated in 5 files and 7 `mypy` errors, mostly NumPy shape-annotation mismatches in `flash_drum`, `cstr`, `conversion_reactor`, and `flowsheet`, plus attribute/type issues in `thermodynamics/property_package.py`.
- Because Task 11 remains strictly fail-fast, the targeted regression bundle and artifact-index command still stay unverified until the `mypy` gate is cleared.

## Task 11 Final Rerun Learnings

- The full ordered Task 11 sequence now completes cleanly: `ruff` passes, `mypy` reports success on 93 source files aside from one non-blocking note, the targeted regression bundle passes 27 tests, and the artifact-index script prints `task11-evidence-index-ok`.
- The verification log is most reproducible when it records each command block exactly in plan order, because the final success baseline now shows both prior blockers as cleared without hiding the original fail-fast structure.
- The artifact-index guard confirms the required audit deliverables from Tasks 5 through 10 are all present at final verification time, so Task 11 now provides the expected pass baseline for the upcoming final review wave.

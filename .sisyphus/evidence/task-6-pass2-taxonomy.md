# Pass 2 Consistency Taxonomy and Audit Rules

## Plan: `process-unit-misalignment-two-pass`
## Task: `6 - Define Pass 2 consistency taxonomy and audit rules`

---

## Pass 2 vs Pass 1 Boundary

### Pass 1 Scope (Already Completed)
Pass 1 focused on control-contract alignment across all unit processes:
- Setpoint embedding patterns (explicit `*_setpoint` fields)
- Mode selector implementation (`thermal_mode`, `mode` fields)
- Controller-readiness verification (first-class MV surfaces, constant-tag actuation mediation)
- Runtime contract safety (MV binding, CV validation, subsystem activation)
- Severity ranking based on runtime risk + test gap combinations

**Pass 1 Artifacts:**
- `.sisyphus/evidence/task-2-control-surface.md` - control-surface extraction
- `.sisyphus/evidence/task-3-runtime-readiness.md` - controller-readiness mapping
- `.sisyphus/evidence/task-4-pass1-coverage.md` - unit-specific coverage matrix
- `.sisyphus/evidence/task-5-pass1-register.md` - severity-ranked misalignment register

### Pass 2 Scope (This Task)
Pass 2 focuses on broader model-consistency mismatches across the same unit set:
- **naming consistency**: terminology patterns across mode, setpoint, and control-relevant fields
- **validation consistency**: input validation, finite checks, pressure floors, composition normalization
- **edge-case semantic consistency**: no-flow behavior, mode parsing strictness, boundary condition handling
- **cross-unit contract coherence**: terminology alignment for concepts shared across unit types (e.g., thermal modes, actuation surfaces)

**Pass 2 Targets:**
All 12 units in `src/modular_simulation/unit_processes/` require Pass 2 audit:
- heater_cooler.py, flash_drum.py, cstr.py, conversion_reactor.py, pfr.py
- pump.py, valve.py, splitter.py, heat_exchanger.py, shortcut_distillation.py
- component_separator.py, mixer.py

---

## Pass 2 Taxonomy Categories

### Category 1: Naming Consistency

#### Definition
Audit field names, parameter names, and method names for terminology coherence across units. This is about **semantic naming patterns**, not cosmetic style preferences.

#### Detection Rules
1. **Mode Selector Naming Variants**
   - Detection: Scan all units for fields ending with `_mode` or containing `mode` in the name
   - Pattern: Identify all mode-related fields and compare naming conventions
   - Example patterns: `thermal_mode`, `mode`, `*_mode`, `mode_selector`
   - Evidence: List all mode field names with their file locations and numeric encoding schemes
   - Misalignment condition: Same semantic concept (e.g., thermal operation mode) uses different field names across units

2. **Setpoint Naming Conventions**
   - Detection: Scan all units for fields containing `setpoint` in the name
   - Pattern: Identify setpoint fields and naming patterns
   - Example patterns: `*_setpoint`, `*_target`, `*_sp`
   - Evidence: List all setpoint field names with their file locations
   - Misalignment condition: Same control intent (e.g., temperature target) uses different naming conventions

3. **Actuation Surface Naming Coherence**
   - Detection: Compare naming of control-relevant surfaces across units
   - Pattern: Identify actuation-like parameters and compare terminology
   - Example patterns: `*_ratio`, `*_fraction`, `*_pressure`, `*_temperature`, `*_area`, `*_coeff`
   - Evidence: List all actuation-relevant field names with their semantic categories
   - Misalignment condition: Same physical actuation type (e.g., pressure control) uses inconsistent terminology

4. **Control Parameter Intent Naming**
   - Detection: Scan for control-relevant parameter names (gain, offset, scale, etc.)
   - Pattern: Identify control law parameters and naming patterns
   - Example patterns: `*_gain`, `*_offset`, `*_factor`, `*_coeff`, `*_k`, `*_tau`
   - Evidence: List all control parameter field names with their semantic intent
   - Misalignment condition: Same control law component (e.g., proportional gain) uses different naming conventions

#### Severity Rubric (Naming Consistency)
- **High**: Same thermal/flow concept uses contradictory terminology that obscures controller intent (e.g., `thermal_mode` vs `op_mode` for isothermal/adiabatic selection)
- **Medium**: Same control surface category uses different suffix patterns but remains recognizable (e.g., `*_fraction` vs `*_ratio` for flow splits)
- **Low**: Cosmetic naming differences that do not obscure intent (e.g., `setpoint_temperature` vs `temperature_setpoint`)

---

### Category 2: Validation Consistency

#### Definition
Audit input validation logic, finite checks, pressure floors, composition normalization, and parameter bounds enforcement across units.

#### Detection Rules
1. **Finite Check Patterns**
   - Detection: Scan for `isfinite`, `finite`, `nan`, `inf` checks and validation calls
   - Pattern: Identify all finite validation locations and methods used
   - Example patterns: `assert isfinite(x)`, `check_finite(x)`, `np.isfinite(x).all()`
   - Evidence: List all finite check locations and their validation methods
   - Misalignment condition: Some units perform explicit finite validation while others omit it for equivalent parameters

2. **Pressure Floor Enforcement**
   - Detection: Scan for pressure-related bounds and minimum pressure checks
   - Pattern: Identify pressure floor logic and enforcement mechanisms
   - Example patterns: `pressure > 0`, `pressure >= pressure_min`, `max(pressure, min_pressure)`
   - Evidence: List all pressure floor locations and their enforcement styles
   - Misalignment condition: Some units enforce pressure floors while others allow negative pressures

3. **Composition Normalization**
   - Detection: Scan for composition-related validation and normalization logic
   - Pattern: Identify composition sum checks, normalization calls, and fraction constraints
   - Example patterns: `sum(composition) == 1.0`, `normalize_composition(x)`, `all(x >= 0) for x in composition`
   - Evidence: List all composition normalization locations and their validation methods
   - Misalignment condition: Some units normalize compositions while others assume valid input

4. **Parameter Bounds Enforcement**
   - Detection: Scan for bounds checking on physical parameters (areas, coefficients, volumes)
   - Pattern: Identify parameter bound checks and enforcement styles
   - Example patterns: `area >= 0`, `coeff > 0`, `volume > 0`, `clamp(x, min, max)`
   - Evidence: List all parameter bounds enforcement locations and their validation styles
   - Misalignment condition: Same parameter type (e.g., heat transfer coefficient) has inconsistent bounds checking

#### Severity Rubric (Validation Consistency)
- **High**: Missing finite/pressure/composition validation creates runtime NaN or physics violation risks that differ across units
- **Medium**: Inconsistent bounds checking styles (explicit vs implicit) that could lead to silent failures
- **Low**: Minor validation style differences that do not impact correctness

---

### Category 3: Edge-Case Semantic Consistency

#### Definition
Audit behavior under edge cases: no-flow conditions, boundary inputs, invalid mode selections, and parameter extremes. Focus on whether units handle edge cases consistently with their contracts.

#### Detection Rules
1. **No-Flow Behavior**
   - Detection: Scan for flow checks, zero-flow handling, and flow-dependent calculations
   - Pattern: Identify how units behave when inlet flow is zero or negative
   - Example patterns: `if flow <= 0: return`, `flow = max(flow, 0)`, flow-conditional output calculation
   - Evidence: List all no-flow handling locations and their strategies (early return, clamping, no-op, etc.)
   - Misalignment condition: Same operational concept (e.g., flow-based control) uses different no-flow strategies

2. **Mode Parsing Strictness**
   - Detection: Scan for mode selector parsing and validation logic
   - Pattern: Identify how units handle invalid or out-of-range mode values
   - Example patterns: `if mode not in [0, 1]: raise ValueError`, `mode = clamp(mode, 0, 1)`, mode enum checks
   - Evidence: List all mode parsing locations and their strictness levels
   - Misalignment condition: Some units validate mode values strictly while others silently coerce or ignore invalid modes

3. **Boundary Condition Handling**
   - Detection: Scan for boundary value handling (min/max inputs, zero values, extremes)
   - Pattern: Identify how units handle inputs at or beyond parameter boundaries
   - Example patterns: `x <= 0` checks, `clamp(x, epsilon, max)`, boundary-condition-specific logic
   - Evidence: List all boundary condition handling locations and their strategies
   - Misalignment condition: Same boundary concept (e.g., zero volume) is handled differently across units

4. **Parameter Extreme Behavior**
   - Detection: Scan for handling of parameter extremes (very large or very small values)
   - Pattern: Identify extreme value checks and numerical stability measures
   - Example patterns: `if coeff > 1e6:`, `epsilon = 1e-12`, numerical stability checks
   - Evidence: List all extreme value handling locations and their strategies
   - Misalignment condition: Same parameter type (e.g., heat transfer coefficient) has different extreme value handling

#### Severity Rubric (Edge-Case Semantic Consistency)
- **High**: Inconsistent no-flow or boundary handling creates divergent controller behavior for equivalent flow scenarios
- **Medium**: Mode parsing or extreme value handling differences that could cause silent failures or unexpected behavior
- **Low**: Edge case handling differences that are documented and intentional for unit-specific physics

---

### Category 4: Cross-Unit Contract Coherence

#### Definition
Audit terminology and contract alignment for concepts that span multiple unit types. This is about whether units "speak the same language" for shared concepts.

#### Detection Rules
1. **Thermal Mode Coherence**
   - Detection: Scan all thermal units for thermal mode concepts and terminology
   - Pattern: Identify thermal operation mode terminology and numeric encodings
   - Example patterns: `thermal_mode`, `isothermal`, `adiabatic`, mode values 0/1
   - Evidence: List all thermal mode implementations and compare terminology/encoding
   - Misalignment condition: Same thermal concept (e.g., isothermal operation) uses different field names or numeric encodings across units

2. **Actuation Surface Terminology**
   - Detection: Compare actuation surface naming across units with control capability
   - Pattern: Identify how units name their primary control handles
   - Example patterns: `open_fraction`, `split_ratios`, `pressure_rise`, `reflux_ratio_setpoint`
   - Evidence: List all primary actuation surfaces and compare naming conventions
   - Misalignment condition: Same actuation type (e.g., throttling) uses inconsistent terminology across units

3. **Control Surface Tagging Coherence**
   - Detection: Compare T.CONTROLLED vs T.CONSTANT tagging patterns for equivalent control surfaces
   - Pattern: Identify whether same control concept is consistently tagged across units
   - Example patterns: `T.CONTROLLED` for MV fields, `T.CONSTANT` for configuration
   - Evidence: List all control-relevant fields and their tag types
   - Misalignment condition: Same control concept is tagged differently (CONTROLLED vs CONSTANT) across units

4. **Parameter Intent Consistency**
   - Detection: Compare semantic intent of similarly-named parameters across units
   - Pattern: Identify whether same parameter name implies same control/physics intent
   - Example patterns: `*_coeff`, `*_area`, `*_pressure`, `*_temperature`
   - Evidence: List all parameters with similar names and compare their control/physics intent
   - Misalignment condition: Same parameter name implies different control/physics intent across units (e.g., `coeff` as gain vs constant)

#### Severity Rubric (Cross-Unit Contract Coherence)
- **High**: Same thermal or actuation concept uses contradictory terminology or tagging that obscures shared control intent
- **Medium**: Similarly-named parameters imply different intents, creating confusion for controller configuration
- **Low**: Terminology differences that are unit-specific and documented as intentional

---

## Pass 2 Non-Goals (Guardrails)

### Pass 2 Does NOT Cover
1. **Actuator Redesign**: Do not propose new MV surfaces, adapter patterns, or control-contract changes
   - This is Pass 1 scope (completed in Task 5)
   - Pass 2 focuses on consistency of existing surfaces, not creation of new ones

2. **Controller Readiness**: Do not evaluate whether units are controller-ready or not
   - This was fully addressed in Pass 1 (Task 3) and the severity ranking (Task 5)
   - Pass 2 assumes the Pass 1 controller-readiness classification as a fixed baseline

3. **Runtime Contract Safety**: Do not evaluate MV binding safety or subsystem activation risks
   - This was fully addressed in Pass 1 (Task 3)
   - Pass 2 focuses on naming/validation/edge-case semantics, not runtime contract violations

4. **Physics Model Quality**: Do not assess the correctness of physics models
   - Pass 2 is about consistency of naming/validation/edge-case handling, not physics correctness
   - Different units may have intentionally different physics models

5. **Style Preferences**: Do not report cosmetic differences that do not impact control intent
   - Example: `setpoint_temperature` vs `temperature_setpoint` is a naming difference but low severity
   - Only classify as misalignment if the difference obscures intent or creates confusion

### Pass 2 Does NOT Reopen
1. **Pass 1 Severity Ranking**: The Pass 1 severity order (PFR critical, ConversionReactor/HeatExchanger high, etc.) is frozen
   - Pass 2 builds its own severity rubric independent of Pass 1
   - Cross-linking to Pass 1 in Task 9 is for overlap detection, not revision

2. **Pass 1 Remediation Patterns**: Pass 2 does not revisit the recommended Pass 1 remediation patterns
   - Pass 2 creates its own recommended next steps for consistency issues
   - Remediation is separate for each pass

---

## Pass 2 Severity Rubric Summary

### Overall Severity Mapping
| Severity | When Assigned | Example |
| --- | --- | --- |
| **High** | Inconsistent behavior creates runtime controller risk or obscures control intent | Different thermal mode terminology for same isothermal concept across units |
| **Medium** | Inconsistent style creates confusion or potential silent failures | Different validation patterns for equivalent parameters |
| **Low** | Cosmetic differences that do not impact correctness or intent | `*_fraction` vs `*_ratio` for flow splits (recognizable as same concept) |

### Severity Assignment Principles
1. **Controller Intent Obscuration**: High severity if naming differences hide control intent
2. **Runtime Risk**: High severity if validation/edge-case differences cause divergent controller behavior
3. **Silent Failure Risk**: Medium severity if inconsistent validation could cause silent failures
4. **Cosmetic Differences**: Low severity if differences are recognizable and documented

---

## Pass 2 Audit Execution (Future Tasks)

### Task 7: Naming and Contract-Semantics Scan
- Scan all 12 units for naming consistency and cross-unit contract coherence
- Produce mismatch list with side-by-side evidence snippets
- Use detection rules from Categories 1 and 4
- Apply severity rubric from each category

### Task 8: Validation and Edge-Case Semantics Scan
- Scan all 12 units for validation consistency and edge-case semantic consistency
- Compare validation patterns, finite checks, pressure floors, composition normalization
- Compare no-flow behavior, mode parsing strictness, boundary condition handling
- Use detection rules from Categories 2 and 3
- Apply severity rubric from each category

### Task 9: Pass 2 Severity-Ranked Consistency Register
- Merge Tasks 7-8 findings into a pass2 register
- Cross-link to Pass 1 register for overlaps (but do not duplicate)
- Include fields: unit, consistency_dimension, misalignment, severity, impact, evidence, recommended_next_step
- Ensure no drift into Pass 1 control-contract territory

---

## Taxonomy Completeness Verification

### Required Tokens Present
- [x] `naming consistency`
- [x] `validation consistency`
- [x] `edge-case semantic consistency`
- [x] `severity rubric`
- [x] `detection rule` language (explicit in all 4 categories)
- [x] `cross-unit contract coherence`

### Pass 1 Distinction Explicit
- Pass 1 vs Pass 2 boundary section clearly distinguishes scope
- Pass 2 non-goals section prevents drift into Pass 1 territory
- All Pass 2 detection rules focus on consistency, not actuator redesign

### Reusability for Tasks 7 and 8
- Each category has explicit detection rules
- Each category has explicit severity rubric
- Detection rules are deterministic (file scan patterns, evidence formats, misalignment conditions)
- Severity rubric is actionable (clear criteria for high/medium/low assignment)

---

## Evidence Artifacts
- This taxonomy artifact: `.sisyphus/evidence/task-6-pass2-taxonomy.md`
- Verification log: `.sisyphus/evidence/task-6-pass2-taxonomy.log`
- Error log: `.sisyphus/evidence/task-6-pass2-taxonomy-error.log`

## Notepad Updates
- Learnings: `.sisyphus/notepads/process-unit-misalignment-two-pass/learnings.md`
- Issues: `.sisyphus/notepads/process-unit-misalignment-two-pass/issues.md`

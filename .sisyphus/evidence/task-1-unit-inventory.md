# Canonical Process-Unit Inventory
## Plan: process-unit-misalignment-two-pass
## Task: 1 - Build canonical process-unit inventory and pass rubric

---

## Pass Assignment Rules

### Pass 1: Control-Contract Consistency
Includes units with:
- Mode selectors (fields that switch operational modes)
- Setpoint fields (targets for control loops)
- Controller-binding dependency (fields intended for MV/CV binding)

**Rationale**: These units have embedded control-contract elements that may require alignment with controller runtime requirements.

### Pass 2: Broader Model-Consistency
Includes all units for:
- Naming consistency (mode/setpoint/parameter terminology across units)
- Validation consistency (no-flow behavior, pressure floors, composition normalization)
- Edge-case semantic consistency (mode parsing strictness, finite checks)
- Cross-unit contract coherence

**Rationale**: All units require semantic audit regardless of control-surface presence to ensure consistent patterns.

---

## Unit Inventory

| unit | class | ports | control-surface candidates | pass1 inclusion | pass2 inclusion | justification |
|------|-------|-------|---------------------------|-----------------|-----------------|---------------|
| src/modular_simulation/unit_processes/heater_cooler.py | HeaterCooler | SINGLE_IO | mode (T.CONSTANT, duty/temperature selector), duty_setpoint (T.CONTROLLED), target_temperature_setpoint (T.CONTROLLED) | YES | YES | Pass 1: Mode selector (0=duty, 1=temperature) with embedded setpoint fields matches HeaterCooler archetype from plan. Pass 2: Naming/validation consistency audit. |
| src/modular_simulation/unit_processes/flash_drum.py | FlashDrum | 1->2 | thermal_mode (T.CONSTANT, adiabatic/isothermal selector), flash_temperature_setpoint (T.CONTROLLED) | YES | YES | Pass 1: thermal_mode selector (0=adiabatic, 1=isothermal) with flash_temperature_setpoint matches FlashDrum archetype from plan. Pass 2: Naming/validation consistency audit. |
| src/modular_simulation/unit_processes/cstr.py | CSTR | SINGLE_IO | reactor_volume (T.CONSTANT, setpoint), level_control_gain (T.CONSTANT, internal control law) | YES | YES | Pass 1: reactor_volume setpoint with internal level_control_gain control law creates volume control surface (internal level loop pattern noted in plan). Pass 2: Naming/validation consistency audit. |
| src/modular_simulation/unit_processes/conversion_reactor.py | ConversionReactor | SINGLE_IO | thermal_mode (T.CONSTANT, adiabatic/isothermal selector), conversion_fractions (T.CONSTANT, split control), stoichiometric_matrix (T.CONSTANT, reaction path) | YES | YES | Pass 1: thermal_mode selector (0=adiabatic, 1=isothermal) present; conversion_fractions provide reaction conversion control surface. Pass 2: Naming/validation consistency audit. |
| src/modular_simulation/unit_processes/pfr.py | PFR | SINGLE_IO | jacket_temperature (T.CONSTANT, thermal actuation), heat_transfer_coeff (T.CONSTANT), jacket_area (T.CONSTANT) | YES | YES | Pass 1: jacket_temperature provides thermal actuation surface (constant-tag thermal actuation candidate from plan). Pass 2: Naming/validation consistency audit. |
| src/modular_simulation/unit_processes/pump.py | Pump | SINGLE_IO | pressure_rise (T.CONSTANT, actuation-like) | YES | YES | Pass 1: pressure_rise constant-tag provides actuation surface (pressure_rise constant-tag contract from plan). Pass 2: Naming/validation consistency audit. |
| src/modular_simulation/unit_processes/valve.py | Valve | SINGLE_IO | open_fraction (T.CONTROLLED, direct MV candidate), Cv (T.CONSTANT), minimum_open_fraction (T.CONSTANT), maximum_open_fraction (T.CONSTANT) | YES | YES | Pass 1: open_fraction is T.CONTROLLED and direct MV candidate; Cv, min/max fractions provide configuration surfaces. Pass 2: Naming/validation consistency audit. |
| src/modular_simulation/unit_processes/splitter.py | Splitter | 1->N | split_ratios (T.CONTROLLED, N-1 split ratios) | YES | YES | Pass 1: split_ratios are T.CONTROLLED and provide flow split control surface. Pass 2: Naming/validation consistency audit. |
| src/modular_simulation/unit_processes/heat_exchanger.py | HeatExchanger | 2->2 | flow_arrangement (T.CONSTANT, counter/co/cross selector), ua (T.CONSTANT, thermal actuation) | YES | YES | Pass 1: flow_arrangement mode selector (0=counter, 1=co, 2=cross) with ua thermal actuation surface. Pass 2: Naming/validation consistency audit. |
| src/modular_simulation/unit_processes/shortcut_distillation.py | ShortcutDistillation | 1->2 | reflux_ratio_setpoint (T.CONTROLLED), light_key_distillate_recovery (T.CONTROLLED), heavy_key_bottoms_recovery (T.CONTROLLED), reflux_ratio_factor (T.CONTROLLED) | YES | YES | Pass 1: reflux_ratio_setpoint is T.CONTROLLED; recovery fields provide separation control surfaces. Pass 2: Naming/validation consistency audit. |
| src/modular_simulation/unit_processes/component_separator.py | ComponentSeparator | 1->2 | split_fractions (T.CONSTANT, species-wise split fractions) | YES | YES | Pass 1: split_fractions constant-tag provides species-wise split control surface (constant split-fraction contract from plan). Pass 2: Naming/validation consistency audit. |
| src/modular_simulation/unit_processes/mixer.py | Mixer | N->1 | None directly controller-related | NO | YES | Pass 1: No mode selector, no setpoint fields, no controller-binding dependency (pure passive mixing). Pass 2: Naming/validation consistency audit. |

---

## Pass Statistics

- **Total Units**: 12
- **Pass 1 Included**: 11 (92%)
- **Pass 1 Excluded**: 1 (8% - Mixer only)
- **Pass 2 Included**: 12 (100% - all units)

### Pass 1 Rationale Summary
All units except Mixer have at least one control-surface element:
- Mode selectors: HeaterCooler, FlashDrum, ConversionReactor, HeatExchanger (4 units)
- Setpoint fields: HeaterCooler, FlashDrum, CSTR, ShortcutDistillation (4 units)
- Controller-binding candidates: Valve, Splitter (2 units)
- Actuation constants: Pump, PFR, ComponentSeparator (3 units)
- Mixer is the only unit with no control-contract elements (pure passive N->1 mixing).

### Pass 2 Rationale Summary
All 12 units require Pass 2 audit for:
- Naming consistency (mode/setpoint/parameter terminology patterns)
- Validation consistency (finite checks, pressure floors, composition normalization)
- Edge-case semantics (mode parsing strictness, no-flow behavior)

---

## Port Shape Legend
- **SINGLE_IO**: Single inlet to single outlet (1->1)
- **1->2**: Single inlet to two outlets
- **N->1**: Multiple inlets to single outlet
- **2->2**: Two inlets to two outlets (dual-stream)
- **1->N**: Single inlet to N outlets (configurable)

---

## Evidence Sources
All classifications grounded in source file reads from:
- `src/modular_simulation/unit_processes/heater_cooler.py`
- `src/modular_simulation/unit_processes/flash_drum.py`
- `src/modular_simulation/unit_processes/cstr.py`
- `src/modular_simulation/unit_processes/conversion_reactor.py`
- `src/modular_simulation/unit_processes/pfr.py`
- `src/modular_simulation/unit_processes/pump.py`
- `src/modular_simulation/unit_processes/valve.py`
- `src/modular_simulation/unit_processes/splitter.py`
- `src/modular_simulation/unit_processes/heat_exchanger.py`
- `src/modular_simulation/unit_processes/shortcut_distillation.py`
- `src/modular_simulation/unit_processes/component_separator.py`
- `src/modular_simulation/unit_processes/mixer.py`

Generated: Task 1 acceptance verification

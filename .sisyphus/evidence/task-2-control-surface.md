# Pass 1 Control-Contract Surface Matrix
## Plan: process-unit-misalignment-two-pass
## Task: 2 - Extract Pass 1 control-contract surfaces per unit

## Scope and Method
- Scope: all concrete units in `src/modular_simulation/unit_processes` (12 units from Task 1 inventory).
- Extraction dimensions: `T.CONTROLLED`, `T.CONSTANT`, mode selectors, `*setpoint*` tokens, and obvious MV/CV candidates.
- Evidence policy: every row includes repo-grounded snippets with file path and line anchors.

## Unit Matrix (Pass 1)
| unit | pass1_profile_labels | mode_selector | setpoint_tokens | T.CONTROLLED surface (candidate MV) | T.CONSTANT control surface | obvious CV candidates | evidence anchors |
|---|---|---|---|---|---|---|---|
| `src/modular_simulation/unit_processes/heater_cooler.py` | `MODE_SELECTOR+SETPOINT_PAIR+DUAL_MV_PATH` | `mode` (`0=duty, 1=temperature`) | `duty_setpoint`, `target_temperature_setpoint` | `duty_setpoint`, `target_temperature_setpoint` | `mode` selector | `outlet_temperature`, `duty` | `heater_cooler.py:90`, `heater_cooler.py:117`, `heater_cooler.py:121`, `heater_cooler.py:267`, `heater_cooler.py:301` |
| `src/modular_simulation/unit_processes/flash_drum.py` | `MODE_SELECTOR+SETPOINT_PAIR+THERMAL_SWITCH` | `thermal_mode` (`0=adiabatic, 1=isothermal`) | `flash_temperature_setpoint` | `flash_temperature_setpoint`, `flash_pressure` | `thermal_mode` selector | `outlet_temperature`, `vapor_fraction` | `flash_drum.py:115`, `flash_drum.py:141`, `flash_drum.py:303`, `flash_drum.py:328`, `flash_drum.py:353` |
| `src/modular_simulation/unit_processes/cstr.py` | `INTERNAL_CONTROL_LAW+SETPOINT_STYLE_CONSTANT` | none explicit | `reactor volume setpoint` description; `volume_setpoint` variable in control law | upstream inlet variables only; no dedicated MV-tagged setpoint field | `reactor_volume`, `level_control_gain`, `jacket_temperature` | `volume` via internal level loop; `outlet_flow`; `temperature` | `cstr.py:106`, `cstr.py:130`, `cstr.py:451`, `cstr.py:452`, `cstr.py:506`, `cstr.py:507` |
| `src/modular_simulation/unit_processes/conversion_reactor.py` | `HOTSPOT_MODE_SELECTOR+REACTION_ACTUATION_CONSTANTS` | `thermal_mode` (`0=adiabatic, 1=isothermal`) | none (`setpoint` token absent) | inlet variables only; no explicit reactor MV setpoint tag | `thermal_mode`, `conversion_fractions`, `stoichiometric_matrix`, `pressure_drop` | `outlet_composition`, `outlet_flow`, `outlet_temperature` | `conversion_reactor.py:265`, `conversion_reactor.py:274`, `conversion_reactor.py:282`, `conversion_reactor.py:359`, `conversion_reactor.py:539`, `conversion_reactor.py:557` |
| `src/modular_simulation/unit_processes/pfr.py` | `THERMAL_ACTUATION_CONSTANT+NO_MODE` | none | none | upstream inlet variables only | `jacket_temperature`, `heat_transfer_coeff`, `jacket_area` | `outlet_temperature`, `outlet_flow` | `pfr.py:119`, `pfr.py:123`, `pfr.py:127`, `pfr.py:84`, `pfr.py:152` |
| `src/modular_simulation/unit_processes/pump.py` | `CONSTANT_ACTUATION_PRESSURE` | none | none | upstream inlet variables only | `pressure_rise`, `efficiency` | `outlet_pressure`, `outlet_flow`, `power_consumed` | `pump.py:84`, `pump.py:88`, `pump.py:114`, `pump.py:126` |
| `src/modular_simulation/unit_processes/component_separator.py` | `CONSTANT_SPLIT_ACTUATION` | none | none | upstream inlet variables only | `split_fractions` | `outlet_1_flow`, `outlet_2_flow`, outlet compositions | `component_separator.py:160`, `component_separator.py:186`, `component_separator.py:190`, `component_separator.py:210`, `component_separator.py:214` |
| `src/modular_simulation/unit_processes/valve.py` | `DIRECT_MV_TAG+BOUNDS_GUARDED` | none | none | `open_fraction` (direct throttling MV) | `Cv`, `minimum_open_fraction`, `maximum_open_fraction` | `outlet_flow`, `outlet_pressure` | `valve.py:113`, `valve.py:75`, `valve.py:76`, `valve.py:80`, `valve.py:84`, `valve.py:118`, `valve.py:122` |
| `src/modular_simulation/unit_processes/splitter.py` | `DIRECT_MV_VECTOR` | none | none | `split_ratios` (N-1 ratios) | `n_outlets` config constant | `outlet_flows`, `outlet_compositions` | `splitter.py:91`, `splitter.py:72`, `splitter.py:100`, `splitter.py:112` |
| `src/modular_simulation/unit_processes/mixer.py` | `PASSIVE_MIXING_NO_DEDICATED_MV` | none | none | no dedicated internal MV beyond inlet feeds | `n_inlets`, `n_species` | `outlet_flow`, `outlet_temperature`, `outlet_composition` | `mixer.py:93`, `mixer.py:96`, `mixer.py:117`, `mixer.py:121`, `mixer.py:129` |
| `src/modular_simulation/unit_processes/heat_exchanger.py` | `MODE_SELECTOR_CONSTANT+UA_ACTUATION` | `flow_arrangement` (`0=counter, 1=co, 2=cross`) | none | inlet-side stream variables only | `flow_arrangement`, `ua` | `hot_outlet_temperature`, `cold_outlet_temperature`, `heat_duty` | `heat_exchanger.py:301`, `heat_exchanger.py:306`, `heat_exchanger.py:442`, `heat_exchanger.py:349`, `heat_exchanger.py:366`, `heat_exchanger.py:387` |
| `src/modular_simulation/unit_processes/shortcut_distillation.py` | `MULTI_CONTROLLED_SETPOINT_CLUSTER` | none explicit | `reflux_ratio_setpoint` | `reflux_ratio_setpoint`, `reflux_ratio_factor`, key recoveries | key indices are constants | `distillate_composition`, `bottoms_composition`, `actual_reflux_ratio` | `shortcut_distillation.py:210`, `shortcut_distillation.py:214`, `shortcut_distillation.py:218`, `shortcut_distillation.py:226`, `shortcut_distillation.py:649`, `shortcut_distillation.py:652` |

## Hotspot Focus: ConversionReactor
- Explicit mode selector contract is present and validated: `thermal_mode` is declared as constant selector (`conversion_reactor.py:265`) and parsed through `_parse_mode` (`conversion_reactor.py:359`).
- Mode path changes runtime thermal behavior in `step`: isothermal branch guards appear at `conversion_reactor.py:539` and `conversion_reactor.py:557`.
- Reaction actuation is currently encoded as constants (`conversion_fractions`, `stoichiometric_matrix`) rather than `T.CONTROLLED` MV tags (`conversion_reactor.py:274`, `conversion_reactor.py:282`).
- Pass 1 implication label: `HOTSPOT_MODE_SELECTOR+REACTION_ACTUATION_CONSTANTS` (controller-readiness depends on adapter strategy rather than direct MV metadata).

## Evidence Snippets
- HeaterCooler mode and setpoints:
  - `mode: ... M(type=T.CONSTANT, ... "mode selector: 0=duty, 1=temperature")` at `src/modular_simulation/unit_processes/heater_cooler.py:90`.
  - `duty_setpoint` and `target_temperature_setpoint` are `T.CONTROLLED` at `src/modular_simulation/unit_processes/heater_cooler.py:117` and `src/modular_simulation/unit_processes/heater_cooler.py:121`.
- FlashDrum thermal selector and setpoint:
  - `thermal_mode` constant selector at `src/modular_simulation/unit_processes/flash_drum.py:115`.
  - `flash_temperature_setpoint` controlled at `src/modular_simulation/unit_processes/flash_drum.py:141`.
- CSTR embedded control law:
  - `reactor_volume` constant described as setpoint at `src/modular_simulation/unit_processes/cstr.py:106`.
  - Internal level law: `outlet_flow = ... + level_gain * (volume - volume_setpoint)` at `src/modular_simulation/unit_processes/cstr.py:452` (and in RHS at `src/modular_simulation/unit_processes/cstr.py:507`).
- Direct MV units:
  - Valve `open_fraction` controlled at `src/modular_simulation/unit_processes/valve.py:113`.
  - Splitter `split_ratios` controlled vector at `src/modular_simulation/unit_processes/splitter.py:91`.

## Pass 1 Severity-Ready Labels
- `MODE_SELECTOR+SETPOINT_PAIR`: explicit mode and setpoint coupling (`heater_cooler`, `flash_drum`).
- `INTERNAL_CONTROL_LAW+SETPOINT_STYLE_CONSTANT`: implicit controller inside physics (`cstr`).
- `HOTSPOT_MODE_SELECTOR+REACTION_ACTUATION_CONSTANTS`: mode selector plus constant-encoded reaction actuation (`conversion_reactor`).
- `DIRECT_MV_TAG`: direct controlled actuator (`valve`, `splitter`).
- `CONSTANT_ACTUATION_*`: control-like actuation encoded as constants (`pump`, `pfr`, `component_separator`, `heat_exchanger`).
- `PASSIVE_MIXING_NO_DEDICATED_MV`: passive aggregation with no dedicated internal MV (`mixer`).

Generated for Task 2 acceptance and downstream Pass 1 severity ranking.

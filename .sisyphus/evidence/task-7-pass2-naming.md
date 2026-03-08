# Pass 2 Naming and Contract-Semantics Scan

Plan: `process-unit-misalignment-two-pass`
Task: `7 - Execute Pass 2 naming and contract-semantics scan`

## Scope and rule lock

- Scan scope is limited to Task 6 Category 1 (`naming consistency`) and Category 4 (`cross-unit contract coherence`).
- Detection rules applied: mode selector naming variants, setpoint naming conventions, actuation surface terminology, control surface tagging coherence, and parameter intent consistency.
- Task 5 overlap is awareness-only: this artifact records naming/contract-language mismatches and does not reopen Pass 1 controller-readiness scoring.

## Audit coverage snapshot

| unit | relative path | audited naming / contract surfaces | mismatch refs |
| --- | --- | --- | --- |
| `heater_cooler` | `src/modular_simulation/unit_processes/heater_cooler.py` | `mode`, `pressure_drop`, `duty_setpoint`, `target_temperature_setpoint` | `M1`, `M3` |
| `flash_drum` | `src/modular_simulation/unit_processes/flash_drum.py` | `thermal_mode`, `flash_pressure`, `flash_temperature_setpoint` | `M1` |
| `conversion_reactor` | `src/modular_simulation/unit_processes/conversion_reactor.py` | `thermal_mode`, `pressure_drop`, `conversion_fractions`, `stoichiometric_matrix` | `M1`, `M3` |
| `cstr` | `src/modular_simulation/unit_processes/cstr.py` | `reactor_volume`, `level_control_gain`, `heat_transfer_coeff`, `jacket_area`, `jacket_temperature` | `M2`, `M5` |
| `pfr` | `src/modular_simulation/unit_processes/pfr.py` | `heat_transfer_coeff`, `jacket_area`, `jacket_temperature` | `M5` |
| `pump` | `src/modular_simulation/unit_processes/pump.py` | `pressure_rise` | none |
| `valve` | `src/modular_simulation/unit_processes/valve.py` | `open_fraction`, `minimum_open_fraction`, `maximum_open_fraction` | none |
| `splitter` | `src/modular_simulation/unit_processes/splitter.py` | `split_ratios` | `M4` |
| `component_separator` | `src/modular_simulation/unit_processes/component_separator.py` | `split_fractions` | `M4` |
| `heat_exchanger` | `src/modular_simulation/unit_processes/heat_exchanger.py` | `flow_arrangement`, `ua` | `M5` |
| `shortcut_distillation` | `src/modular_simulation/unit_processes/shortcut_distillation.py` | `reflux_ratio_factor`, `reflux_ratio_setpoint` | `M2` |
| `mixer` | `src/modular_simulation/unit_processes/mixer.py` | array-shaped inlet names only; no unit-local selector/setpoint surface | none |

## Mismatch list

### M1

- `mismatch_type`: `thermal_selector_name_divergence`
- `severity`: `medium`
- `affected_units`: `heater_cooler`, `flash_drum`, `conversion_reactor`
- `why_it_matters`: Thermal selector discovery is not uniform. A deterministic scan for `thermal_mode` misses `HeaterCooler`, while a broad scan for `mode` overmatches unrelated helpers and local variables.
- `evidence`:

| `src/modular_simulation/unit_processes/heater_cooler.py` | `src/modular_simulation/unit_processes/flash_drum.py` | `src/modular_simulation/unit_processes/conversion_reactor.py` |
| --- | --- | --- |
| `def _normalize_mode(mode: str) -> Literal["duty", "temperature"]:` | `def _normalize_mode(mode: str) -> Literal["adiabatic", "isothermal"]:` | `def _normalize_mode(mode: str) -> Literal["adiabatic", "isothermal"]:` |
| `mode: Annotated[` | `thermal_mode: Annotated[` | `thermal_mode: Annotated[` |
| `M(type=T.CONSTANT, unit="", description="mode selector: 0=duty, 1=temperature")` | `M(type=T.CONSTANT, unit="", description="thermal mode selector: 0=adiabatic, 1=isothermal")` | `M(type=T.CONSTANT, unit="", description="thermal mode selector: 0=adiabatic, 1=isothermal")` |

### M2

- `mismatch_type`: `implicit_setpoint_name_and_tag`
- `severity`: `medium`
- `affected_units`: `cstr`, `heater_cooler`, `flash_drum`, `shortcut_distillation`
- `why_it_matters`: `CSTR` carries a real control target, but the public field name reads like geometry/configuration instead of a setpoint. Cross-unit scans and operator code have to inspect descriptions and equations to learn that `reactor_volume` is a setpoint-bearing contract.
- `evidence`:

| `src/modular_simulation/unit_processes/cstr.py` | `src/modular_simulation/unit_processes/heater_cooler.py` | `src/modular_simulation/unit_processes/flash_drum.py` | `src/modular_simulation/unit_processes/shortcut_distillation.py` |
| --- | --- | --- | --- |
| `reactor_volume: Annotated[` | `duty_setpoint: Annotated[` | `flash_temperature_setpoint: Annotated[` | `reflux_ratio_setpoint: Annotated[` |
| `M(type=T.CONSTANT, unit="L", description="reactor volume setpoint")` | `M(type=T.CONTROLLED, unit="W", description="heat duty setpoint used in duty mode")` | `M(type=T.CONTROLLED, unit="K", description="isothermal flash temperature setpoint")` | `M(type=T.CONTROLLED, unit="", description="optional explicit reflux ratio (>0 overrides factor)")` |
| `volume_setpoint = max(_MIN_VOLUME, float(k[k_map["reactor_volume"]]))` | `target_temperature_setpoint: Annotated[` | - | `if not isfinite(self.reflux_ratio_setpoint) or self.reflux_ratio_setpoint < 0.0:` |
| `outlet_flow = max(0.0, inlet_flow + level_gain * (volume - volume_setpoint))` | `M(type=T.CONTROLLED, unit="K", description="target outlet temperature setpoint used in temperature mode")` | - | `raise ValueError("reflux_ratio_setpoint must be finite and non-negative.")` |

### M3

- `mismatch_type`: `shared_parameter_name_contract_divergence`
- `severity`: `high`
- `affected_units`: `heater_cooler`, `conversion_reactor`
- `why_it_matters`: The exact same public field name, `pressure_drop`, means two different external contracts: runtime-controlled in `HeaterCooler`, fixed configuration in `ConversionReactor`. The shared name hides whether the pressure loss is expected to be tuned or treated as static equipment data.
- `evidence`:

| `src/modular_simulation/unit_processes/heater_cooler.py` | `src/modular_simulation/unit_processes/conversion_reactor.py` |
| --- | --- |
| `pressure_drop: Annotated[` | `pressure_drop: Annotated[` |
| `M(type=T.CONTROLLED, unit="Pa", description="pressure drop across the unit")` | `M(type=T.CONSTANT, unit="Pa", description="pressure drop across the reactor")` |
| `pressure_drop = float(u[u_map["pressure_drop"]])` | `pressure_drop = float(k[k_map["pressure_drop"]])` |
| `outlet_pressure = max(inlet_pressure - pressure_drop, _TINY_POSITIVE_PRESSURE)` | `outlet_pressure = max(inlet_pressure - pressure_drop, _TINY_POSITIVE_PRESSURE)` |

### M4

- `mismatch_type`: `split_allocation_name_and_tag_divergence`
- `severity`: `medium`
- `affected_units`: `splitter`, `component_separator`
- `why_it_matters`: Both units expose vectorized outlet-allocation handles, but one is a first-class controlled `split_ratios` surface and the other is a constant `split_fractions` surface. The noun change and tag change together prevent a single deterministic rule from identifying "split handle" contracts without unit-specific exceptions.
- `evidence`:

| `src/modular_simulation/unit_processes/splitter.py` | `src/modular_simulation/unit_processes/component_separator.py` |
| --- | --- |
| `def _validate_split_ratios(split_ratios: NDArray[np.float64]) -> NDArray[np.float64]:` | `def _validate_split_fractions(split_fractions: NDArray[np.float64]) -> None:` |
| `split_ratios: Annotated[` | `split_fractions: Annotated[` |
| `M(type=T.CONTROLLED, unit="", description="N-1 split ratios; final ratio computed as 1-sum(split_ratios)")` | `M(type=T.CONSTANT, unit="", description="species-wise split fraction to outlet_1 (remainder goes to outlet_2)")` |
| `return np.concatenate((split_ratios, np.array([1.0 - ratio_sum], dtype=np.float64)))` | `outlet_1_component_flows = inlet_component_flows * split_fractions` |

### M5

- `mismatch_type`: `thermal_conductance_alias_divergence`
- `severity`: `medium`
- `affected_units`: `heat_exchanger`, `cstr`, `pfr`
- `why_it_matters`: `HeatExchanger` exposes thermal coupling as the collapsed term `ua`, while reactor units publish the same effective conductance as `heat_transfer_coeff * jacket_area`. Reviewers and tooling must decode equations to recognize that these surfaces play the same contract role.
- `evidence`:

| `src/modular_simulation/unit_processes/heat_exchanger.py` | `src/modular_simulation/unit_processes/cstr.py` | `src/modular_simulation/unit_processes/pfr.py` |
| --- | --- | --- |
| `ua: Annotated[` | `heat_transfer_coeff: Annotated[` | `heat_transfer_coeff: Annotated[` |
| `M(type=T.CONSTANT, unit="W/K", description="overall heat-transfer conductance")` | `M(type=T.CONSTANT, unit="W/(m^2*K)", description="jacket heat transfer coefficient")` | `M(type=T.CONSTANT, unit="W/(m^2*K)", description="wall heat transfer coefficient")` |
| `ua: float,` | `jacket_area: Annotated[` | `jacket_area: Annotated[` |
| `ua = float(k[k_map["ua"]])` | `ua = max(0.0, float(k[k_map["heat_transfer_coeff"]])) * max(0.0, float(k[k_map["jacket_area"]]))` | `ua_total = max(0.0, float(k[k_map["heat_transfer_coeff"]])) * max(0.0, float(k[k_map["jacket_area"]]))` |

## Units with no actionable Category 1 / 4 mismatch after scan

- `src/modular_simulation/unit_processes/pump.py`: `pressure_rise` is consistently named and remains a unit-specific pressure-boost term rather than a reused shared contract noun.
- `src/modular_simulation/unit_processes/valve.py`: `open_fraction` and its bound names are internally coherent and do not reuse another unit's contract noun with conflicting tags.
- `src/modular_simulation/unit_processes/mixer.py`: arrays are inlet-shape descriptors rather than unit-local selector/setpoint contracts, so no naming/coherence mismatch survives the Task 6 filters.

## Notes for Task 9 cross-linking

- `M3` and `M4` overlap with Pass 1 adapter hotspots, but the issue recorded here is narrower: the public contract language itself is inconsistent before any controller-readiness judgment is applied.
- No Category 2 or Category 3 findings are included here; validation and edge-case semantics stay reserved for Task 8.

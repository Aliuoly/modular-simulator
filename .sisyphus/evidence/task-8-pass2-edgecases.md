# Pass 2 Validation and Edge-Case Semantics Scan

Plan: `process-unit-misalignment-two-pass`
Task: `8 - Execute Pass 2 validation and edge-case semantics scan`

## Scope and detection basis

- Categories applied: Task 6 Category 2 (`validation consistency`) and Category 3 (`edge-case semantic consistency`).
- Deterministic checks applied across all 12 units: finite checks, pressure floors, composition normalization, no-flow behavior, mode parsing strictness, boundary conditions, and extreme-parameter handling.
- Baseline behavior anchors from the active plan test set: `tests/unit_process/test_layer4_cstr.py:40`, `tests/unit_process/test_layer4_pfr.py:72`, `tests/unit_process/test_layer4_distillation.py:56`, `tests/unit_process/test_layer4_distillation.py:94`.

## Unit-by-unit audit matrix

| unit | validation consistency evidence | edge-case semantic evidence | classification |
| --- | --- | --- | --- |
| `heater_cooler` | Strict finite and positive checks at `src/modular_simulation/unit_processes/heater_cooler.py:188`, `src/modular_simulation/unit_processes/heater_cooler.py:192`, `src/modular_simulation/unit_processes/heater_cooler.py:201`, repeated in algebraic path at `src/modular_simulation/unit_processes/heater_cooler.py:276`. | Zero-flow duty mode raises when duty is non-zero at `src/modular_simulation/unit_processes/heater_cooler.py:296`; zero-flow temperature mode remains defined in `step()` at `src/modular_simulation/unit_processes/heater_cooler.py:332`; baseline coverage at `tests/unit_process/test_layer4_heater_cooler.py:116`. | benign divergence |
| `flash_drum` | Strict finite and positive checks at `src/modular_simulation/unit_processes/flash_drum.py:218`, `src/modular_simulation/unit_processes/flash_drum.py:224`, `src/modular_simulation/unit_processes/flash_drum.py:229`, repeated in algebraic path at `src/modular_simulation/unit_processes/flash_drum.py:311`. | No-flow remains stable because outlet flows scale with inlet flow at `src/modular_simulation/unit_processes/flash_drum.py:334`; phase-boundary normalization fallback at `src/modular_simulation/unit_processes/flash_drum.py:378`; baseline boundary test at `tests/unit_process/test_layer4_flash_drum.py:97`. | no actionable mismatch detected |
| `cstr` | Constructor validates internal reactor parameters at `src/modular_simulation/unit_processes/cstr.py:198` but does not validate controlled inlet scalars or reactor pressure; inlet flow is silently clamped in algebraic and differential paths at `src/modular_simulation/unit_processes/cstr.py:449` and `src/modular_simulation/unit_processes/cstr.py:502`. | Zero/near-zero holdup falls back to uniform composition at `src/modular_simulation/unit_processes/cstr.py:456`; baseline steady-state and energy checks exist at `tests/unit_process/test_layer4_cstr.py:40` and `tests/unit_process/test_layer4_cstr.py:101`. | actionable misalignment |
| `pfr` | Constructor validates discretization and thermal constants at `src/modular_simulation/unit_processes/pfr.py:189` but does not validate controlled inlet scalars or reactor pressure; inlet flow and volume are silently clamped in solver paths at `src/modular_simulation/unit_processes/pfr.py:462`, `src/modular_simulation/unit_processes/pfr.py:510`, and `src/modular_simulation/unit_processes/pfr.py:513`. | Zero/near-zero outlet holdup falls back to uniform composition at `src/modular_simulation/unit_processes/pfr.py:454`; baseline coverage is physics-only steady-state behavior at `tests/unit_process/test_layer4_pfr.py:72`. | actionable misalignment |
| `conversion_reactor` | Constructor validates `pressure_drop`, composition, and conversion fractions at `src/modular_simulation/unit_processes/conversion_reactor.py:376`, `src/modular_simulation/unit_processes/conversion_reactor.py:404`, and `src/modular_simulation/unit_processes/conversion_reactor.py:405`, but controlled inlet scalars are only checked later in algebraic evaluation at `src/modular_simulation/unit_processes/conversion_reactor.py:482`. | Zero-flow conversion falls back to feed composition at `src/modular_simulation/unit_processes/conversion_reactor.py:517`; thermal mode parsing is strict at `src/modular_simulation/unit_processes/conversion_reactor.py:361`. | actionable misalignment |
| `pump` | Strict finite, positive, and composition checks at `src/modular_simulation/unit_processes/pump.py:158`, `src/modular_simulation/unit_processes/pump.py:162`, `src/modular_simulation/unit_processes/pump.py:164`, `src/modular_simulation/unit_processes/pump.py:169`, repeated in algebraic path at `src/modular_simulation/unit_processes/pump.py:311`. | Algebraic zero-flow path still adds pressure-rise heating at `src/modular_simulation/unit_processes/pump.py:338`, while `step()` no-ops temperature on zero flow at `src/modular_simulation/unit_processes/pump.py:355`; baseline happy-path test at `tests/unit_process/test_layer4_pump_valve.py:105`. | actionable misalignment |
| `valve` | Constructor enforces open-fraction bounds at `src/modular_simulation/unit_processes/valve.py:175` and `src/modular_simulation/unit_processes/valve.py:181`, but algebraic evaluation only checks finiteness at `src/modular_simulation/unit_processes/valve.py:334`; pressure floor remains present at `src/modular_simulation/unit_processes/valve.py:359`. | Zero-flow path remains stable through the smooth flow term at `src/modular_simulation/unit_processes/valve.py:358`; isenthalpic baseline coverage at `tests/unit_process/test_layer4_pump_valve.py:151`. | actionable misalignment |
| `splitter` | Composition and ratio validation are strict at `src/modular_simulation/unit_processes/splitter.py:171`, `src/modular_simulation/unit_processes/splitter.py:172`, and `src/modular_simulation/unit_processes/splitter.py:291`, but inlet pressure only needs to be finite at `src/modular_simulation/unit_processes/splitter.py:169` and `src/modular_simulation/unit_processes/splitter.py:278`. | Zero-flow remains algebraically stable because outlet flows are direct scaled copies at `src/modular_simulation/unit_processes/splitter.py:294`; no pressure floor is applied to outlet pressures at `src/modular_simulation/unit_processes/splitter.py:296`. | actionable misalignment |
| `mixer` | Vector and composition-row checks are strict at `src/modular_simulation/unit_processes/mixer.py:173`, `src/modular_simulation/unit_processes/mixer.py:175`, and `src/modular_simulation/unit_processes/mixer.py:177`, but inlet pressures only need to be finite at `src/modular_simulation/unit_processes/mixer.py:175` and `src/modular_simulation/unit_processes/mixer.py:309`. | Zero-total-flow fallback uses the first inlet composition at `src/modular_simulation/unit_processes/mixer.py:321`; outlet pressure is the raw minimum inlet pressure at `src/modular_simulation/unit_processes/mixer.py:325`; positive-flow step path exits early on no-flow at `src/modular_simulation/unit_processes/mixer.py:341`. | actionable misalignment |
| `heat_exchanger` | Strict non-negative/positive validation for both sides at `src/modular_simulation/unit_processes/heat_exchanger.py:466`, `src/modular_simulation/unit_processes/heat_exchanger.py:494`, `src/modular_simulation/unit_processes/heat_exchanger.py:508`, repeated in algebraic path at `src/modular_simulation/unit_processes/heat_exchanger.py:591`. | No-flow or zero-UA short-circuit is explicit in `_solve_exchanger()` at `src/modular_simulation/unit_processes/heat_exchanger.py:156`; arrangement parsing accepts deterministic aliases at `src/modular_simulation/unit_processes/heat_exchanger.py:41`; baseline arrangement coverage at `tests/unit_process/test_layer4_heat_exchanger.py:107`. | benign divergence |
| `component_separator` | Strict finite, positive, composition, and split-fraction checks at `src/modular_simulation/unit_processes/component_separator.py:253`, `src/modular_simulation/unit_processes/component_separator.py:257`, `src/modular_simulation/unit_processes/component_separator.py:284`, `src/modular_simulation/unit_processes/component_separator.py:287`, repeated in algebraic path at `src/modular_simulation/unit_processes/component_separator.py:356`. | Zero-flow product fallback preserves feed composition at `src/modular_simulation/unit_processes/component_separator.py:381`; explicit regression test exists at `tests/unit_process/test_layer4_component_separator.py:94`. | no actionable mismatch detected |
| `shortcut_distillation` | Strict recovery, reflux, pressure, and composition validation at `src/modular_simulation/unit_processes/shortcut_distillation.py:324`, `src/modular_simulation/unit_processes/shortcut_distillation.py:331`, `src/modular_simulation/unit_processes/shortcut_distillation.py:334`, and `src/modular_simulation/unit_processes/shortcut_distillation.py:364`; extreme-value root guards appear at `src/modular_simulation/unit_processes/shortcut_distillation.py:126` and `src/modular_simulation/unit_processes/shortcut_distillation.py:169`. | Zero-feed path resets outputs cleanly at `src/modular_simulation/unit_processes/shortcut_distillation.py:545`; degenerate non-zero-flow splits raise at `src/modular_simulation/unit_processes/shortcut_distillation.py:612`; baseline coverage at `tests/unit_process/test_layer4_distillation.py:56`. | no actionable mismatch detected |

## Actionable misalignments

### A1. Reactor-family controlled-input validation and clamping are inconsistent with the rest of the unit library

- category: `validation consistency` plus `edge-case semantic consistency`
- severity: `high`
- classification: `actionable misalignment`
- units: `cstr`, `pfr`, `conversion_reactor`
- why: Most units reject invalid controlled inlet scalars and positive-pressure violations before simulation. `CSTR`, `PFR`, and `ConversionReactor` do not enforce the same constructor contract, and `CSTR` plus `PFR` silently clamp invalid runtime inputs instead of failing. That creates divergent controller-facing behavior for equivalent bad inputs.
- evidence:
  - `src/modular_simulation/unit_processes/cstr.py:198`, `src/modular_simulation/unit_processes/cstr.py:242`, `src/modular_simulation/unit_processes/cstr.py:449`, `src/modular_simulation/unit_processes/cstr.py:502`
  - `src/modular_simulation/unit_processes/pfr.py:193`, `src/modular_simulation/unit_processes/pfr.py:233`, `src/modular_simulation/unit_processes/pfr.py:462`, `src/modular_simulation/unit_processes/pfr.py:513`
  - `src/modular_simulation/unit_processes/conversion_reactor.py:376`, `src/modular_simulation/unit_processes/conversion_reactor.py:404`, `src/modular_simulation/unit_processes/conversion_reactor.py:482`
  - strict comparators: `src/modular_simulation/unit_processes/heater_cooler.py:188`, `src/modular_simulation/unit_processes/flash_drum.py:218`, `src/modular_simulation/unit_processes/pump.py:158`, `src/modular_simulation/unit_processes/valve.py:161`

### A2. Mixer and Splitter accept non-physical pressures that most other units reject or floor

- category: `validation consistency`
- severity: `high`
- classification: `actionable misalignment`
- units: `mixer`, `splitter`
- why: Pressure is treated as a positive physical quantity everywhere else in the library. `Mixer` and `Splitter` only require finite pressure and then propagate it unchanged, so a negative pressure can survive portfolio-level composition and flow operations without any floor or error.
- evidence:
  - `src/modular_simulation/unit_processes/mixer.py:175`, `src/modular_simulation/unit_processes/mixer.py:309`, `src/modular_simulation/unit_processes/mixer.py:325`
  - `src/modular_simulation/unit_processes/splitter.py:169`, `src/modular_simulation/unit_processes/splitter.py:278`, `src/modular_simulation/unit_processes/splitter.py:296`
  - strict comparators: `src/modular_simulation/unit_processes/heater_cooler.py:192`, `src/modular_simulation/unit_processes/flash_drum.py:222`, `src/modular_simulation/unit_processes/component_separator.py:257`, `src/modular_simulation/unit_processes/heat_exchanger.py:508`

### A3. Pump zero-flow semantics diverge between algebraic evaluation and stepped state updates

- category: `edge-case semantic consistency`
- severity: `high`
- classification: `actionable misalignment`
- units: `pump`
- why: For the same zero-flow input, `calculate_algebraic_values()` reports a pressure-rise-driven temperature increase while `step()` explicitly preserves inlet temperature. That is an internal no-flow contract split likely to leak into solver/controller behavior.
- evidence:
  - `src/modular_simulation/unit_processes/pump.py:336`, `src/modular_simulation/unit_processes/pump.py:338`, `src/modular_simulation/unit_processes/pump.py:355`, `src/modular_simulation/unit_processes/pump.py:356`

### A4. Valve bound enforcement is incomplete in the algebraic path

- category: `validation consistency`
- severity: `medium`
- classification: `actionable misalignment`
- units: `valve`
- why: The constructor rejects `open_fraction` outside configured min/max bounds, but the algebraic path only checks finiteness and then computes resistance. Similar bounded split controls (`splitter`, `component_separator`) revalidate bounds in their active calculation paths.
- evidence:
  - `src/modular_simulation/unit_processes/valve.py:175`, `src/modular_simulation/unit_processes/valve.py:181`, `src/modular_simulation/unit_processes/valve.py:334`, `src/modular_simulation/unit_processes/valve.py:350`
  - comparator paths: `src/modular_simulation/unit_processes/splitter.py:292`, `src/modular_simulation/unit_processes/component_separator.py:372`

## Benign divergences

### B1. HeaterCooler zero-flow handling is stricter than FlashDrum, but the difference tracks the thermal contract

- category: `edge-case semantic consistency`
- severity: `low`
- classification: `benign divergence`
- units: `heater_cooler`, `flash_drum`
- why: `HeaterCooler` duty mode rejects non-zero duty at zero flow because finite duty over zero throughput is undefined, while temperature targeting remains valid and matches the isothermal-style `FlashDrum` behavior. The split is deliberate and internally consistent once mode intent is considered.
- evidence:
  - `src/modular_simulation/unit_processes/heater_cooler.py:296`, `src/modular_simulation/unit_processes/heater_cooler.py:332`
  - `src/modular_simulation/unit_processes/flash_drum.py:328`, `src/modular_simulation/unit_processes/flash_drum.py:386`
  - regression anchors: `tests/unit_process/test_layer4_heater_cooler.py:116`, `tests/unit_process/test_layer4_flash_drum.py:97`

### B2. Composition fallback differs between reactor holdup models and pass-through split/mix units

- category: `edge-case semantic consistency`
- severity: `low`
- classification: `benign divergence`
- units: `cstr`, `pfr`, `mixer`, `component_separator`, `shortcut_distillation`, `flash_drum`, `conversion_reactor`
- why: `CSTR` and `PFR` recover depleted internal holdup with a uniform composition fallback, while pass-through and split units preserve the current feed composition when a product flow collapses. The behavior is different, but it follows different state semantics rather than contradictory contracts.
- evidence:
  - reactor fallbacks: `src/modular_simulation/unit_processes/cstr.py:456`, `src/modular_simulation/unit_processes/pfr.py:454`
  - pass-through fallbacks: `src/modular_simulation/unit_processes/mixer.py:321`, `src/modular_simulation/unit_processes/component_separator.py:381`, `src/modular_simulation/unit_processes/shortcut_distillation.py:545`, `src/modular_simulation/unit_processes/flash_drum.py:381`, `src/modular_simulation/unit_processes/conversion_reactor.py:517`

### B3. HeatExchanger mode parsing is intentionally more permissive than the thermal-mode units

- category: `edge-case semantic consistency`
- severity: `low`
- classification: `benign divergence`
- units: `heat_exchanger`, `heater_cooler`, `flash_drum`, `conversion_reactor`
- why: `HeatExchanger` accepts deterministic aliases like `counter-current` and `parallel`, but still rejects out-of-family values and invalid numeric selectors. That improves ergonomics without silently coercing an unknown mode.
- evidence:
  - `src/modular_simulation/unit_processes/heat_exchanger.py:41`, `src/modular_simulation/unit_processes/heat_exchanger.py:52`, `src/modular_simulation/unit_processes/heat_exchanger.py:442`
  - strict comparators: `src/modular_simulation/unit_processes/heater_cooler.py:33`, `src/modular_simulation/unit_processes/flash_drum.py:34`, `src/modular_simulation/unit_processes/conversion_reactor.py:34`

## Acceptance-check mapping

- `no-flow`: covered in `heater_cooler`, `flash_drum`, `pump`, `mixer`, `component_separator`, `shortcut_distillation`, `conversion_reactor`
- `pressure`: covered in `heater_cooler`, `flash_drum`, `pump`, `valve`, `splitter`, `mixer`, `heat_exchanger`, `component_separator`, `conversion_reactor`
- `composition`: covered in every unit, including normalization fallback notes for `flash_drum`, `cstr`, `pfr`, `shortcut_distillation`
- `finite`: covered via constructor/algebraic validation comparisons across all 12 units
- `classification`: every recorded finding is explicitly labeled `actionable misalignment` or `benign divergence`

- Added one reusable helper module at `tests/controller_contract_harness.py` instead of per-file utility duplication to keep later remediation tasks on one controller-contract assertion vocabulary.
- Kept all runtime-behavior changes out of `src/` and implemented contract coverage entirely in tests/evidence scope per Task 1 guardrails.
- Used a test-only `ArrayAgnosticController` in the helper module to isolate dimensionality-contract coverage from PID scalar assumptions and assert the framework-level mismatch rejection path.
- Recorded the 12-unit direct/proxy/reject target table in `.sisyphus/evidence/task-1-controller-contract-decision-table.md` with conservative compatibility-impact notes limited to future alias/shim implications.
- Implemented the PFR jacket remediation as a unit-local proxy: the constructor still seeds from legacy `jacket_temperature`, but `differential_rhs()` now reads `jacket_temperature_setpoint` so controller/runtime mutation can target temperature intent without exposing transport coefficients as manipulated variables.
- Implemented the pump remediation as a unit-local proxy: the constructor still accepts legacy `pressure_rise`, but runtime-controlled behavior now targets `pressure_rise_setpoint` and leaves `pressure_rise`/`efficiency` on the design-time surface for hydraulic compatibility.

- Kept ShortcutDistillation source unchanged per Task 5 guardrails; all reflux behavior is exercised through additive tests without touching FUG/Underwood/Gilliland calculations or field names.
- Added branch-isolated reflux tests (positive setpoint, factor fallback, negative input) rather than relying on existing textbook/FUG coverage, making the explicit vs. factor-based runtime path contractually visible.
- Used ArrayAgnosticController in controller wiring tests to isolate distillation actuator binding from PID-specific assumptions, consistent with the pump and heat exchanger test patterns.
- Parametrized the distillation negative test across algebraic (actual_reflux_ratio, minimum_reflux_ratio) and constant (n_species) fields to prove that the framework correctly rejects bindings to non-controlled states even though they are valid distillation fields.
- Kept HeatExchanger source unchanged per Task 4 guardrails; all coverage is additive tests with controlled_view assertions and controller rejection patterns, no runtime behavior changes to `src/modular_simulation/unit_processes/heat_exchanger.py`.
- Used the same ArrayAgnosticController pattern from pump/distillation tests to isolate HeatExchanger actuator binding from PID-specific assumptions and assert the framework-level rejection path for `ua` and `flow_arrangement`.
- Parametrized HeatExchanger negative tests across both `ua` (overall heat-transfer conductance) and `flow_arrangement` (counter/co/cross selector) to prove that the framework correctly rejects bindings to CONSTANT states even though they are valid exchanger fields.
#VN|- Kept ConversionReactor source unchanged per Task 3 guardrails; all coverage is additive tests with controlled_view assertions and controller rejection patterns, no runtime behavior changes to `src/modular_simulation/unit_processes/conversion_reactor.py`.
#PK|- Used ArrayAgnosticController pattern from pump/distillation/heat_exchanger tests to isolate ConversionReactor actuator binding from PID-specific assumptions and assert framework-level rejection path for `thermal_mode` and `conversion_fractions`.
#YR|- Parametrized ConversionReactor negative tests across both `thermal_mode` (adiabatic/isothermal selector) and `conversion_fractions` (species-specific conversion array) to prove that the framework correctly rejects bindings to CONSTANT states even though they are valid reactor fields.
#MS|- Required a test-only system builder with sensor/control_element setup to ensure `inlet_temperature` is registered as a measurable point, allowing the actuator binding failure to be the first validation error rather than unresolved signal error.

- Implemented the CSTR remediation as a unit-local proxy: the constructor still accepts legacy reactor_volume, but controller/runtime writes now target reactor_volume_setpoint and leave jacket_temperature, heat_transfer_coeff, jacket_area, and level_control_gain on the design-time surface.

- Kept Task 9 entirely test-only: no `src/` runtime behavior changes landed while hardening FlashDrum/HeaterCooler unit, controller, and flowsheet coverage.
- Used parametrized controller-wiring tests to prove the sanctioned direct thermal MVs (`flash_pressure`, `flash_temperature_setpoint`, `pressure_drop`, `duty_setpoint`, `target_temperature_setpoint`) remain first-class and paired them with rollback-safe rejection tests for `thermal_mode` and `mode`.
- Implemented ComponentSeparator remediation with a narrow proxy pattern: retained `split_fractions` as constructor-compatible constant input and moved runtime algebraic consumption to controlled `split_fraction_targets` only.
- Kept framework change local to `ControlElement._install` setter selection by enabling array assignment exclusively when the target process state is both controlled and non-scalar; avoided broader controller/system contract changes.

- Kept Task 10 source scope to `Valve` only: `Splitter` runtime validation already covered length, non-negativity, and sum-to-unity semantics, so hardening landed as additive controller/unit tests rather than a parity rewrite.
- Proved `Splitter.split_ratios` direct vector control in the narrowest stable seam by writing through `ControlElement`'s bound setter for the happy path and reserving normal `System` activation for rollback-safe scalar/vector mismatch rejection.
- Standardized passive pressure policy to one portfolio-consistent rule for non-actuated pressure propagation: finite-and-positive only, applied in both `Mixer` inlet pressure vector validation and `Splitter` inlet pressure scalar validation.
- Kept `pressure_drop` noun divergence explicit and unchanged: tests now lock `ConversionReactor.pressure_drop` as constant configuration and `HeaterCooler.pressure_drop` as a controlled manipulated variable, with no renames or controller-surface changes.

- Kept Task 13 load-path repair minimal in `ProcessModel.load`: retained existing constructor hydration flow (for unit-local coercion/validators) and added only field-default-driven ndarray list coercion plus existing legacy/canonical alias normalization.
- Kept ComponentSeparator fix local to `model_post_init` by deriving `split_fractions` from canonical `split_fraction_targets` only when the legacy vector is empty; warning behavior and broader naming contracts remain unchanged.

- Kept Task 14 alias scope intentionally narrow to Group 5 naming rows: constructor-only alias coercion with explicit either/or conflict errors, no state-type changes, and no solver-equation changes.
- Implemented thermal-conductance coherence as a HeatExchanger parser alias requiring both legacy terms (heat_transfer_coeff and jacket_area) to derive canonical ua, rejecting partial alias input to avoid ambiguous semantics.
- Kept Task 15 strictly documentation-and-evidence scoped: created a new benign-divergence summary and final evidence index that link the real Task 11-14 runtime-safety and compatibility artifacts without reopening behavior or adding new backlog work.

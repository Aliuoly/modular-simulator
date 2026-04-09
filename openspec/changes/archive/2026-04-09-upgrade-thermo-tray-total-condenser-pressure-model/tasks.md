## Dependency gate

- [ ] D0 Confirm this change pack is approved, linked Beads execution items exist, and implementation starts from this pack as the active source of truth for `upgrade-thermo-tray-total-condenser-pressure-model`.

## Wave 1 — Freeze the new contract with failing realism tests first

- [ ] 1.1 `simulation-realism-required: true` Expand `tests/unit_process/test_layer4_thermo_tray_distillation.py` with red equation-fidelity coverage for `GE-TTD-MAT-3a` through `GE-TTD-MAT-3c` and `GE-TTD-TC-1` through `GE-TTD-TC-8`, including headspace pressure, condensed/non-condensed flow split, hydrostatic liquid outlet pressure, and dynamic bottom pressure derived from accepted tray pressure-drop terms.
- [ ] 1.2 `simulation-realism-required: true` Add red unit/integration coverage for restoring the framework solver path so thermo-tray no longer silently bypasses configured `System.solver_options`. Cover `src/modular_simulation/measurables/process_model.py`, `src/modular_simulation/framework/system.py`, and `src/modular_simulation/unit_processes/separation/thermo_tray_distillation.py` only where the runtime seam requires it.
- [ ] 1.3 `simulation-realism-required: true` Add red demo/runtime coverage in `tests/integration/test_thermo_tray_distillation_runtime.py` and `tests/integration/test_thermo_tray_distillation_demo_operating_point.py` proving:
  - insufficient condenser duty yields nonzero `non_condensed_flow`,
  - top pressure rises from headspace accumulation,
  - condenser liquid can become subcooled,
  - and total-condenser overload does not silently imply the partial-condenser contract.
- [ ] 1.4 `simulation-realism-required: true` Run the red boundary:
  - `uv run pytest tests/unit_process/test_layer4_thermo_tray_distillation.py -k "pressure or condenser or headspace or subcool or solver"`
  - `uv run pytest tests/integration/test_thermo_tray_distillation_runtime.py -k "pressure or condenser or headspace or solver"`
  - `uv run pytest tests/integration/test_thermo_tray_distillation_demo_operating_point.py -k "pressure or condenser or subcool"`
  - Expected evidence: the new tests fail against the old constant-pressure, liquid-only top-end, explicit-Euler override, and no-noncondensed-flow behavior.

## Wave 2 — Rename/split the thermo-tray unit family and restore the solver seam

- [ ] 2.1 `simulation-realism-required: true` Split the thermo-tray public unit family into an explicit total-condenser implementation path plus a separately reserved partial-condenser sibling surface/stub so total-condenser overload cannot be mistaken for partial-condenser topology, while keeping gameplay/client exposure unchanged. Update exact files when implementation starts, likely including:
  - `src/modular_simulation/unit_processes/separation/thermo_tray_distillation.py`
  - `src/modular_simulation/unit_processes/separation/__init__.py`
  - `src/modular_simulation/unit_processes/__init__.py`
- [ ] 2.2 `simulation-realism-required: true` Restore the framework-owned solver path for the total-condenser thermo-tray model. If bounded internal substep refinement is still required later, make it wrap and delegate to the accepted framework seam instead of replacing integration outright.
- [ ] 2.3 `simulation-realism-required: true` Keep the old live thermo-tray top-end bugfixes intact during the rename/split:
  - shared drum withdrawal realizability budget
  - explicit reflux request
  - dry-drum guard
  - no per-component drum mass recreation.

## Wave 3 — Implement total-condenser headspace, pressure, and subcooling physics

- [ ] 3.1 `simulation-realism-required: true` Add the new top-end conserved/dynamic states required by `GE-TTD-TC-*` in `src/modular_simulation/unit_processes/separation/thermo_tray_distillation.py`, including headspace component inventory, any accepted headspace thermal state, and live top pressure/output pressure states. Name exact fields to match the frozen spec labels.
- [ ] 3.2 `simulation-realism-required: true` Implement the explicit total-condenser realization equations:
  - `realized_condensed_flow`
  - `non_condensed_flow`
  - liquid drum balance
  - excess-headspace gas balance plus any duty-limited recondensation sink
  - subcooled condenser/drum liquid energy balance
  preserving exact equation fidelity to the frozen PR-bubble-plus-excess-headspace-pressure closure in `design.md`.
- [ ] 3.3 `simulation-realism-required: true` Add live liquid outlet source pressures for reflux and distillate based on headspace pressure plus hydrostatic head, and expose them through the unit’s hydraulic participation / outlet stream surfaces without splitting the drum into a separate process unit.
- [ ] 3.4 `simulation-realism-required: true` Implement the optional blanket-gas and vent physical capability in the total-condenser class as boundary/port terms only. Do not embed setpoint control laws or PSV logic into the unit.

## Wave 4 — Replace constant pressure anchors with dynamic end-pressure treatment

- [ ] 4.1 `simulation-realism-required: true` Replace the constant `p_top_pa` / `p_bottom_pa` top-end contract in `src/modular_simulation/unit_processes/separation/thermo_tray_distillation.py` with the live pressure treatment frozen in `GE-TTD-MAT-3a` through `GE-TTD-MAT-3c`.
- [ ] 4.2 `simulation-realism-required: true` Implement the accepted dynamic column pressure-drop family using the frozen Bennett-Agrawal-Cook-style tray decomposition (dry tray drop plus liquid/froth head, plus only named residual terms if justified). Do not invent pressure-drop surrogates without provenance or switch to a different tray-correlation family without a spec change.
- [ ] 4.3 `simulation-realism-required: true` Interpolate tray pressures between live top and bottom pressures and update thermo closures, examples, and tests to use those live pressures consistently.
- [ ] 4.4 `simulation-realism-required: true` If any `connection` or hydraulic-participation contract changes are actually required for distinct vapor-side and liquid-side source pressures, limit them to the smallest explicit widening and keep them backend-only.

## Wave 5 — Refresh demos and runtime evidence

- [ ] 5.1 `simulation-realism-required: true` Update `examples/dynamic_simulation_demos/thermo_tray_distillation_startup_demo.py` and `examples/dynamic_simulation_demos/thermo_tray_step_characterization_demo.py` to demonstrate the upgraded total-condenser pressure/headspace/subcooling behavior without overclaiming partial-condenser physics.
- [ ] 5.2 `simulation-realism-required: true` Add explicit observable outputs for:
  - top headspace pressure
  - bottom pressure
  - realized condensed flow
  - non-condensed flow
  - reflux/distillate source pressures
  - condenser/drum subcooling evidence
  in the demo JSON/plots and runtime-owned process-state tests where appropriate.
- [ ] 5.3 `simulation-realism-required: true` Keep the demos honest: if the final implementation still needs bounded internal substep logic for accepted-step realizability, the examples must make clear whether they are using the raw runtime step or a runtime-owned refinement wrapper rather than a demo-only physics surrogate.

## Wave 6 — Independent review gate

- [ ] 6.1 `simulation-realism-required: true` Run an independent review focused on:
  - equation fidelity of `GE-TTD-MAT-3*` and `GE-TTD-TC-*`
  - top/headspace vs liquid outlet pressure semantics
  - solver-path alignment with framework expectations
  - total-condenser overload staying distinct from partial-condenser topology
  - no invented pressure-drop or condensation correlations.
- [ ] 6.2 `simulation-realism-required: true` Do not close implementation until review evidence is non-blocking and still shows:
  - stronger top-end pressure realism
  - explicit condensation vs non-condensation behavior
  - subcooling support
  - optional blanket/vent capability without built-in control policy
  - no gameplay/client widening.

## Wave 7 — Verification and closure hygiene

- [ ] 7.1 `simulation-realism-required: true` Run the focused and full verification set:
  - `uv run pytest tests/unit_process/test_layer4_thermo_tray_distillation.py`
  - `uv run pytest tests/integration/test_thermo_tray_distillation_runtime.py`
  - `uv run pytest tests/integration/test_thermo_tray_distillation_demo_operating_point.py`
  - `uv run python examples/dynamic_simulation_demos/thermo_tray_distillation_startup_demo.py`
  - `uv run python examples/dynamic_simulation_demos/thermo_tray_step_characterization_demo.py`
  - `openspec validate --specs --strict --no-interactive`
- [ ] 7.2 `simulation-realism-required: true` Expected evidence:
  - total-condenser overload produces non-condensed carryover and rising top pressure rather than silent topology switching
  - liquid outlet pressures differ from vapor headspace pressure by documented hydrostatic head terms
  - bottom pressure is derived from the frozen tray-pressure-drop family rather than fixed constants
  - condenser liquid can be subcooled below bubble point
  - optional blanket/vent physical terms affect headspace pressure without embedding controller policy
  - thermo-tray runtime honors framework solver options
  - gameplay/build/client exposure remains unchanged.
- [ ] 7.3 Sync any modified live specs (`openspec/specs/thermo-tray-distillation/spec.md`, and only if actually needed `openspec/specs/units-and-components/spec.md` / `openspec/specs/connection/spec.md`) after implementation, verification, and review are complete, then update Beads with final evidence before closure.

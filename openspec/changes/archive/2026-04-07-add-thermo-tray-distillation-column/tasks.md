## Dependency gate

- [ ] D0 Confirm this change pack is approved, linked Beads execution items exist, and implementation starts from this pack as the active source of truth for `add-thermo-tray-distillation-column`.

## Wave 1 — Write the failing thermo-tray tests first

- [ ] 1.1 `simulation-realism-required: true` Add red unit coverage in `tests/unit_process/test_layer4_thermo_tray_distillation.py` for the frozen tray material balances, tray thermo closure, dynamic `Cp` usage, end-region balances, startup-state builder defaults, and settle-metric behavior.
- [ ] 1.2 `simulation-realism-required: true` Add red runtime/integration coverage in `tests/integration/test_thermo_tray_distillation_runtime.py` for backend-only startup-and-settle operation, reuse of the normal runtime stepping path, product withdrawal compatibility, reuse of the existing substrate observability contract, and no broad hard clipping during normal runtime.
- [ ] 1.3 `simulation-realism-required: true` Add a red executable example in `examples/dynamic_simulation_demos/thermo_tray_distillation_startup_demo.py` that starts from a numerically dry state, settles under fixed boundary conditions, and records tray temperature/holdup evolution plus condenser/reboiler end-region behavior.
- [ ] 1.4 Run the red boundary:
  - `uv run pytest tests/unit_process/test_layer4_thermo_tray_distillation.py`
  - `uv run pytest tests/integration/test_thermo_tray_distillation_runtime.py`
  - Expected evidence: the new tests fail before the new sibling model and thermo-backed closures exist.

## Wave 2 — Add the thermo closure seam and new sibling model

- [ ] 2.1 `simulation-realism-required: true` Add `src/modular_simulation/thermodynamics/distillation_closures.py` with the named PR-backed tray/end-region closure helpers required by `GE-TTD-TH-1`, `GE-TTD-END-3`, and `GE-TTD-END-4`, keeping the closure layer testable independently from the full column RHS.
- [ ] 2.2 `simulation-realism-required: true` Extend `src/modular_simulation/thermodynamics/property_package.py` only where needed to support the tray/end-region closure helper without widening thermo scope beyond the current PR-backed vapor-liquid-equilibrium envelope.
- [ ] 2.3 `simulation-realism-required: true` Create `src/modular_simulation/unit_processes/separation/thermo_tray_distillation.py` with `ThermoTrayDistillationColumn` as a new `ProcessModel` sibling implementing the frozen differential states, algebraic closures, tray balances, and end-region balances from `GE-TTD-MAT-1` through `GE-TTD-END-7`.
- [ ] 2.4 `simulation-realism-required: true` Update `src/modular_simulation/unit_processes/separation/__init__.py` and `src/modular_simulation/unit_processes/__init__.py` to export `ThermoTrayDistillationColumn` without repurposing or removing the existing stagewise or paper-faithful model exports.

## Wave 3 — Implement startup-and-settle and narrow numerical guards

- [ ] 3.1 `simulation-realism-required: true` Implement the numerically dry startup-state builder and settle-metric flow defined by `GE-TTD-ST-1` through `GE-TTD-ST-4` inside `src/modular_simulation/unit_processes/separation/thermo_tray_distillation.py` (or a tightly scoped helper imported only by that file); do not introduce a separate equation-oriented steady-state solver in this pack.
- [ ] 3.2 `simulation-realism-required: true` Keep numerical safeguards narrow and explicit: epsilon holdup floors, composition normalization, and bounded flash-protection fallback only when a raw thermo call would otherwise fail; do not add broad repeated hard clipping of temperature, pressure, or flow states inside normal runtime stepping.
- [ ] 3.3 `simulation-realism-required: true` Prove in tests that startup-and-settle reuses the normal runtime equations, that startup avoids exact-zero singularities, and that flash-protection behavior is diagnostic and bounded rather than silently redefining the governing equations.

## Wave 4 — Integrate existing runtime seams without widening scope

- [ ] 4.1 `simulation-realism-required: true` Reuse the existing backend runtime/subnetwork composition path rooted in `src/modular_simulation/measurables/process_model.py` and `src/modular_simulation/connection/runtime/runtime.py` so `ThermoTrayDistillationColumn` is stepped through the same runtime orchestration surfaces as other process models; widen runtime/session files only if direct repo evidence proves the existing path insufficient.
- [ ] 4.2 `simulation-realism-required: true` Keep distillate and bottoms behavior aligned with the existing owner-holdup and conservative withdrawal rules already frozen in `openspec/specs/connection/spec.md`; do not add hidden distillation-specific valve or line-restriction semantics.
- [ ] 4.3 `simulation-realism-required: true` Keep public gameplay/build/client exposure unchanged. No start allowlists, public build catalogs, controller binding, or Godot/client-facing distillation widening belong in this pack.
- [ ] 4.4 `simulation-realism-required: true` Keep `ThermoTrayDistillationColumn` compatible with the existing dynamic distillation observability contract already frozen in `openspec/specs/observability/spec.md`; if implementation updates are needed, keep them on the current substrate observability projection surfaces without widening the top-level snapshot schema.

## Wave 5 — Equation fidelity, review, and closeout

- [ ] 5.1 `simulation-realism-required: true` Add explicit equation-fidelity assertions in `tests/unit_process/test_layer4_thermo_tray_distillation.py` that the implemented tray balances, temperature-state equation, and startup/settle procedure match `GE-TTD-MAT-*`, `GE-TTD-TH-*`, `GE-TTD-END-*`, and `GE-TTD-ST-*` rather than a prose-only interpretation.
- [ ] 5.2 `simulation-realism-required: true` Run focused verification and capture expected evidence:
  - `uv run pytest tests/unit_process/test_layer4_thermo_tray_distillation.py`
  - `uv run pytest tests/integration/test_thermo_tray_distillation_runtime.py`
  - `uv run python examples/dynamic_simulation_demos/thermo_tray_distillation_startup_demo.py`
  - `openspec validate --specs --strict --no-interactive`
  - Expected evidence:
    - tray holdup and temperature evolve from the frozen equations
    - `Cp` is dynamic and thermo-derived rather than constant
    - startup-and-settle reaches a bounded settled condition using the runtime model itself
    - existing substrate observability still exposes the required distillation process-state, pressure, and duty readouts for the thermo-tray path without a snapshot-schema widening
    - no broad hard clipping is required for normal runtime evolution
    - gameplay/build/client exposure stays unchanged.
- [ ] 5.3 `simulation-realism-required: true` Run independent implementation review focused on simulation realism, thermo-closure correctness, startup behavior, and numerical-guard discipline before closing the Beads work.
- [ ] 5.4 Sync the final spec deltas, implementation evidence, and Beads notes together before closeout.

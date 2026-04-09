## Why

The post-implementation audit of `ThermoTrayDistillationColumn` (Beads `ModularSimulator-4k3`) identified three concrete top-end pathologies that make the condenser drum and reflux path produce non-physical behavior at the current operating point:

1. **Shared drum overdraw plus epsilon mass recreation pins distillate at floor values.** `distillate_flow` is realized from drum holdup alone (`thermo_tray_distillation.py:941-943`), then `reflux_flow` is independently realized from the same drum inventory (`thermo_tray_distillation.py:1087-1092`). The per-component epsilon flooring in `step()` (`thermo_tray_distillation.py:774-777`) silently creates mass, so the drum stays pinned at `3e-08 mol`, which implies `distillate_flow = 1.5e-07 mol/s` — matching the characterization evidence exactly.

2. **Missing explicit reflux-request boundary.** The spec defines a unit-local `R_req` reflux return request (`spec.md:145-153,183-194`), but the implementation has no explicit reflux-request input. Reflux is back-computed as `vap_flow[0] - distillate_flow` (`thermo_tray_distillation.py:1087`). This removes top-end actuation causality and collapses the top tray liquid inlet whenever the drum is dry.

3. **Dry-drum temperature integration produces non-physical temperatures.** The drum energy ODE keeps integrating on essentially empty inventory (`thermo_tray_distillation.py:1148-1162`). `n_drum` is clamped to `max(eps_n, ...)`, but the actual inventory is dry, so the temperature ODE amplifies thermo noise into values like `-1125 K` to `-2630 K`.

These are real bugs, not speculative. The characterization demo at `.tmp/thermo_tray_step_plots/thermo_tray_step_characterization.json` confirms the pathology signatures.

## What Changes

- Replace the independent distillate-then-reflux drum withdrawal sequence with a **single shared realizability budget**: the drum can only supply `D + R_req` up to its actual holdup per timestep. Distillate and reflux are allocated from one budget, and no per-component epsilon flooring is used to mask the overdraft.
- Add an **explicit reflux-request boundary input** (`reflux_withdrawal_flow`) to the boundary map, consistent with the spec's `R_req` intent. Remove the back-computation `reflux = vap_flow[0] - distillate_flow`. Reflux is now a causal input that the caller or controller provides, and the shared budget realizes it against actual drum holdup.
- Add a **dry-drum thermo guard** that freezes condenser-drum temperature integration when drum total holdup drops below a meaningful inventory threshold (`N^D_dry_guard`). Below this threshold, the drum thermo state is physically undefined, so `dT_D/dt` is set to zero rather than integrating on dry inventory.
- Do **not** change tray balances, reboiler-kettle behavior, tray thermo closure, or the PR-backed closure family. Do not change the stagewise, Howard, or Gani models.

## Capabilities

### Modified Capabilities
- `thermo-tray-distillation`: fix condenser-drum realizability (shared `D + R_req` budget), add explicit reflux-request boundary, and add dry-drum temperature guard. This capability is equation-bearing; the delta spec carries the revised drum balance, the new reflux-request equation, and the dry-drum guard condition directly.

### Unchanged Capabilities
- `units-and-components`, `session`, `connection`, `observability`: no changes. The bugfix is internal to `ThermoTrayDistillationColumn` behavior and does not widen public build, gameplay, or client exposure.

## Impact

- Implementation focus:
  - `src/modular_simulation/unit_processes/separation/thermo_tray_distillation.py` — lines 130-166 (boundary map), 69-79 (realized withdrawal), 939-943 (distillate realization), 1087-1099 (reflux computation), 1145-1162 (drum RHS), 774-777 (epsilon flooring)
  - No changes expected in `distillation_closures.py` or `property_package.py`.
- Verification focus:
  - `tests/unit_process/test_layer4_thermo_tray_distillation.py`
  - `tests/integration/test_thermo_tray_distillation_runtime.py`
  - `examples/dynamic_simulation_demos/thermo_tray_distillation_startup_demo.py`
- No live spec updates outside `thermo-tray-distillation/spec.md`.
- No changes to `StagewiseDistillationColumn`, `Howard1970DistillationColumn`, or `Gani1986DistillationColumn`.

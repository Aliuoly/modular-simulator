## Dependency gate

- [ ] D0 Confirm this change pack is approved, linked Beads execution items exist, and implementation starts from this pack as the active source of truth for `fix-thermo-tray-top-end-pathologies`.

## Wave 1 — Write failing tests for the three top-end pathologies

- [ ] 1.1 `simulation-realism-required: true` Add red unit tests in `tests/unit_process/test_layer4_thermo_tray_distillation.py` for:
  - Shared drum overdraw: construct a drum with small holdup, request both distillate and reflux that individually would each consume the full drum, verify that `D_realized + R_realized <= drum_total / dt` and that per-component drum inventory does not go negative after one step.
  - Explicit reflux request: verify that `reflux_withdrawal_flow` exists as a boundary input and that the realized reflux matches the explicit request (not `vap_flow[0] - distillate_flow`).
  - Dry-drum temperature guard: construct a drum state with `N^D < N^D_dry_guard`, step the model, verify that `dT_D/dt = 0` and drum temperature does not change.
  - Per-component flooring removal for drum: verify that `step()` does not apply per-component epsilon flooring to `condenser_drum_component_moles`.

- [ ] 1.2 `simulation-realism-required: true` Add red runtime/integration tests in `tests/integration/test_thermo_tray_distillation_runtime.py` for:
  - Top-end realizability: run the characterization scenario and verify drum holdup is not pinned at `3e-08 mol` and distillate flow is not pinned at `1.5e-07 mol/s`.
  - Drum temperature sanity: verify that condenser drum temperature remains in a physically plausible range (positive, within `100-500 K` of feed temperature) throughout the startup transient.
  - Reflux causality: verify that reflux responds to the explicit boundary input and not to a back-computed value.

- [ ] 1.3 Run the red boundary:
  - `uv run pytest tests/unit_process/test_layer4_thermo_tray_distillation.py`
  - `uv run pytest tests/integration/test_thermo_tray_distillation_runtime.py`
  - Expected evidence: the new tests fail before the bugfix implementation.

## Wave 2 — Implement the shared drum realizability budget and reflux-request boundary

- [ ] 2.1 `simulation-realism-required: true` Add `reflux_withdrawal_flow` as a `BOUNDARY` field in `ThermoTrayBoundaryMap` in `src/modular_simulation/unit_processes/separation/thermo_tray_distillation.py` (default `0.0`), alongside the existing `distillate_withdrawal_flow`.
- [ ] 2.2 `simulation-realism-required: true` Replace the independent `_realized_withdrawal_flow` calls for distillate (line ~941) and reflux (lines ~1087-1092) with the shared budget logic from `GE-TTD-END-2`:
  - Compute `D_R_budget = max(0.0, N^D - N^D_min) / dt` once.
  - `D_realized = min(D_request, D_R_budget)`.
  - `R_realized = min(R_request, D_R_budget - D_realized)`.
  - Use `R_realized` as `L_0` for the top tray boundary and in the drum component balance.
- [ ] 2.3 `simulation-realism-required: true` Remove the back-computation `reflux_request = max(0.0, float(vap_flow[0]) - distillate_flow)` at line ~1087. Reflux now comes from the explicit boundary input `R_request`.
- [ ] 2.4 `simulation-realism-required: true` In `step()`, skip per-component epsilon flooring for `condenser_drum_component_moles` in the holdup floor loop (lines ~774-777). Keep flooring for `tray_component_holdup` and `reboiler_kettle_component_moles`.

## Wave 3 — Implement the dry-drum temperature guard

- [ ] 3.1 `simulation-realism-required: true` Add the dry-drum guard in the drum temperature RHS (lines ~1148-1162): when `N^D < N^D_dry_guard`, set `dT_D/dt = 0`. The threshold `N^D_dry_guard` should be a configurable constant (suggested default `1e-4 mol`).
- [ ] 3.2 `simulation-realism-required: true` Verify in unit tests that:
  - Below-threshold drum inventory freezes temperature.
  - Above-threshold drum inventory integrates temperature normally.
  - The transition is clean (no discontinuous jumps when inventory crosses the threshold).

## Wave 4 — Rerun characterization and verify end-to-end behavior

- [ ] 4.1 `simulation-realism-required: true` Update `examples/dynamic_simulation_demos/thermo_tray_distillation_startup_demo.py` to provide an explicit `reflux_withdrawal_flow` boundary value (suggested: use the previous operating point's implied reflux or a reasonable fixed reflux request for the demo scenario).
- [ ] 4.2 `simulation-realism-required: true` Rerun the full verification suite:
  - `uv run pytest tests/unit_process/test_layer4_thermo_tray_distillation.py`
  - `uv run pytest tests/integration/test_thermo_tray_distillation_runtime.py`
  - `uv run python examples/dynamic_simulation_demos/thermo_tray_distillation_startup_demo.py`
  - `openspec validate --specs --strict --no-interactive`
  - Expected evidence:
    - drum holdup is not pinned at `3e-08 mol`
    - distillate flow is not pinned at `1.5e-07 mol/s`
    - drum temperature remains physically plausible (positive, near feed temperature)
    - reflux matches the explicit boundary request
    - dry-drum temperature guard activates when drum holdup drops below threshold
    - shared budget prevents overdraw
    - tray and reboiler tests remain green
    - gameplay/build/client exposure is unchanged.

- [ ] 4.3 `simulation-realism-required: true` Add equation-fidelity assertions verifying that the implemented drum balance and temperature guard match `GE-TTD-END-2`, `GE-TTD-END-2a`, and `GE-TTD-END-3` rather than a prose-only interpretation.

## Wave 5 — Review and closeout

- [ ] 5.1 `simulation-realism-required: true` Run independent implementation review focused on:
  - shared budget correctness (no overdraft, no mass creation)
  - reflux-request causality (boundary input, not back-computation)
  - dry-drum guard behavior (threshold, freeze, resume)
  - no unintended changes to tray or reboiler behavior.
- [ ] 5.2 Sync the final spec deltas, implementation evidence, and Beads notes together before closeout.

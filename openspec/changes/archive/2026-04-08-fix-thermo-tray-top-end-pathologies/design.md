## Context

- `ThermoTrayDistillationColumn` was added in the archived change `add-thermo-tray-distillation-column` and is the backend-only actual-tray equilibrium-stage distillation model.
- A post-implementation audit (Beads `ModularSimulator-4k3`) identified three concrete top-end pathologies that produce non-physical condenser-drum behavior at the current operating point. The characterization demo (`.tmp/thermo_tray_step_plots/thermo_tray_step_characterization.json`) confirms:
  - drum holdup pinned at `3e-08 mol`
  - distillate flow pinned at `1.5e-07 mol/s`
  - drum temperature spiraling from `-1125 K` to `-2630 K`.
- This follow-on change fixes only those three pathologies. It does not change tray balances, reboiler-kettle behavior, the PR-backed thermo closure family, or any other model.

## Goals / Non-Goals

**Goals:**
- Fix the shared condenser-drum overdraw so distillate and reflux share a single realizability budget from actual drum holdup.
- Add an explicit reflux-request boundary input consistent with the spec's `R_req` intent.
- Add a dry-drum temperature guard that freezes `dT_D/dt` when drum inventory is below a physically meaningful threshold.
- Remove per-component epsilon flooring in `step()` for drum states (keep it for tray and kettle states where it is not the root cause of pathology).

**Non-Goals:**
- Changing tray material balances, tray thermo closure, or tray hydraulics.
- Changing reboiler-kettle balances or boilup behavior.
- Changing `StagewiseDistillationColumn`, `Howard1970DistillationColumn`, or `Gani1986DistillationColumn`.
- Widening gameplay, build, client, or public exposure.
- Changing `distillation_closures.py` or `property_package.py`.

## Decisions

1. **Shared realizability budget replaces independent withdrawal calls.**
   - Currently: `distillate_flow = _realized_withdrawal_flow(owner_moles=drum_moles, ...)` at line 941, then `reflux_flow = _realized_withdrawal_flow(owner_moles=drum_moles, ...)` at line 1088. Each call sees the same drum holdup and can each consume up to `drum_total / dt`, overdrawing by up to 2×.
   - Fix: compute `D_R_budget = max(0.0, N^D - N^D_min) / dt` once, then `D_realized = min(D_request, D_R_budget)`, `R_realized = min(R_request, D_R_budget - D_realized)`.
   - Distillate gets priority in the allocation order (it was already realized first), and reflux takes what remains.

2. **Reflux-request becomes an explicit boundary input.**
   - Currently: `reflux_request = max(0.0, float(vap_flow[0]) - distillate_flow)` at line 1087. This is a back-computation, not a causal input.
   - Fix: add `reflux_withdrawal_flow` to the `ThermoTrayBoundaryMap` as a `BOUNDARY` field, analogous to `distillate_withdrawal_flow`. The RHS reads it directly. Default value is zero (no reflux) when the caller does not provide it, which is safe and conservative.
   - The tray component balance top boundary (`L_0 = R_req` with `z^D_k` composition from `GE-TTD-MAT-7`) now uses the realized reflux from the shared budget, not the back-computed value.

3. **Dry-drum temperature guard freezes integration below inventory threshold.**
   - Currently: `n_drum = max(eps_n, float(np.sum(np.clip(drum_moles, 0.0, None))))` at line 1155, so the ODE denominator stays finite even on dry inventory, producing huge `dT_D/dt` from small enthalpy imbalances.
   - Fix: when `N^D < N^D_dry_guard`, set `dT_D/dt = 0`. The threshold `N^D_dry_guard` should be meaningfully larger than `eps_N` (suggested `1e-4 mol` or a configurable parameter). This prevents non-physical temperature integration without introducing broad hard clipping of temperature itself.

4. **Per-component epsilon flooring in `step()` is removed for drum states only.**
   - The current `step()` loop at lines 774-777 applies `np.maximum(y[index], eps_n)` to all holdup/moles states. This silently creates per-component mass when the drum is overdrawn, which is the root cause of pathology 1.
   - Fix: skip the epsilon floor for `condenser_drum_component_moles` in the `step()` floor loop. The shared budget ensures the drum balance does not go negative. Keep the floor for `tray_component_holdup` and `reboiler_kettle_component_moles` where it is harmless.

5. **No changes to `distillation_closures.py`.**
   - The audit confirmed that `_safe_flash` bounded fallback behavior (`distillation_closures.py:61-89`) is not itself buggy; the issue is that the drum temperature ODE drives invalid inputs into it. Fixing the ODE guard at the caller level is the correct layer.

## Equation Basis

Only the end-region drum equations change. All other equations remain as frozen in the live spec.

### Revised drum component balance (`GE-TTD-END-2`)

```
D_R_budget = max(0.0, N^D - N^D_min) / dt    [mol/s]

D_realized = min(D_request, D_R_budget)         [mol/s]
R_realized = min(R_request, D_R_budget - D_realized)  [mol/s]

dN^D_k/dt = V_1 * y_{1,k} - D_realized * z^D_k - R_realized * z^D_k  [mol/s]
```

Constraint: `D_realized + R_realized <= D_R_budget` always. No per-component mass creation.

### New reflux-request boundary (`GE-TTD-END-2a`)

```
R_request = reflux_withdrawal_flow   (explicit BOUNDARY input)
```

The top tray liquid inlet boundary `L_0 = R_realized` uses the realized value from the shared budget, not the raw request.

### Revised drum temperature with dry-drum guard (`GE-TTD-END-3`)

```
h^L_D, Cp^L_D, rho^L_D = Thermo_PR_liq(T_D, P_D, z_D)

if N^D < N^D_dry_guard:
    dT_D/dt = 0
else:
    dT_D/dt = (V_1 * h^V_1 - D_realized * h^L_D - R_realized * h^L_D
               - Q_C - h^L_D * sum_k dN^D_k/dt)
              / max(N^D * Cp^L_D, eps_C)    [K/s]
```

All other governing equations (`GE-TTD-MAT-*`, `GE-TTD-TH-*`, `GE-TTD-END-4` through `GE-TTD-END-7`, `GE-TTD-ST-*`) are unchanged.

## Risks / Trade-offs

- **Reflux-request default of zero may change behavior for callers that relied on the back-computation.**
  - The current back-computation `reflux = vap_flow[0] - distillate_flow` implicitly provides reflux when vapor overhead exceeds distillate. Callers that do not yet set `reflux_withdrawal_flow` will get zero reflux.
  - Mitigation: the startup demo and integration tests will be updated to provide an explicit reflux request. The characterization demo should be rerun to verify the fix.
  - This is an acceptable trade-off because the back-computation was itself the bug — it removed causal control authority.

- **Dry-drum guard threshold `N^D_dry_guard` is a tuning parameter.**
  - Too small: may not prevent all non-physical temperature excursions.
  - Too large: may freeze temperature during legitimate low-holdup transients.
  - Mitigation: make it a configurable constant in the parameter/boundary map with a sensible default (`1e-4 mol`), and test both above-threshold and below-threshold drum states.

- **Distillate gets priority in the shared budget allocation.**
  - This is a deliberate choice: distillate was already realized first, and keeping that priority minimizes behavioral surprise.
  - Alternative: proportional allocation or reflux-first. Rejected because reflux-first would starve distillate on dry drum, and proportional adds complexity without clear benefit for a bugfix.

## Verification Strategy

- TDD leads the implementation: write failing tests first, then fix the code.
- Required verification commands:
  - `uv run pytest tests/unit_process/test_layer4_thermo_tray_distillation.py`
  - `uv run pytest tests/integration/test_thermo_tray_distillation_runtime.py`
  - `uv run python examples/dynamic_simulation_demos/thermo_tray_distillation_startup_demo.py`
  - `openspec validate --specs --strict --no-interactive`
- Required verification evidence:
  - drum holdup is no longer pinned at `3e-08 mol`; distillate flow is no longer pinned at `1.5e-07 mol/s`
  - drum temperature remains in a physically plausible range (positive, within `100-500 K` of feed temperature)
  - reflux flows match the explicit boundary request when drum holdup is sufficient
  - when drum holdup is below `N^D_dry_guard`, drum temperature is frozen (rate = 0)
  - when drum holdup recovers above `N^D_dry_guard`, temperature integration resumes
  - shared budget prevents `D_realized + R_realized` from exceeding `D_R_budget`
  - characterization/demo rerun shows physically plausible top-end behavior
  - existing tray and reboiler tests remain green
  - gameplay/build/client exposure is unchanged.

## Open Questions

- None. The scope is narrow, the three pathologies are well-characterized, and the fixes are equation-level and testable.

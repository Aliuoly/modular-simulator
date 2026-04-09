## Context

- The live distillation runtime family currently has:
  - `StagewiseDistillationColumn` as the reduced-order backend baseline,
  - `Howard1970DistillationColumn` and `Gani1986DistillationColumn` as backend-only paper-faithful comparison siblings,
  - and no general thermo-backed actual-tray runtime path.
- The user wants a stronger backend-only model that can work with arbitrary active species inside the repo's currently supported Peng-Robinson vapor-liquid-equilibrium envelope, but does **not** want a vague or hand-wavy contract.
- Exploration and stress testing established several hard constraints:
  - use a new sibling model rather than repurposing `StagewiseDistillationColumn`
  - keep the change backend-only and preserve current gameplay/build/client gating
  - do not require a separate steady-state solver in v1; use startup-and-settle with the same runtime equations
  - do not assume constant heat capacity
  - treat tray temperature as one shared equilibrium tray temperature
  - avoid broad hard clipping; keep guards limited to epsilon floors, composition normalization, and flash-protection fallback when thermo would otherwise stall
  - keep v1 narrow and PR-only.
- Repo constraints that materially shape the design:
  - `src/modular_simulation/thermodynamics/property_package.py` currently supports only `model="PR"`
  - `ProcessModel.step()` integrates through `solve_ivp`
  - `FlashDrum` already demonstrates a property-package-backed separation seam
  - live `connection` specs already freeze the right runtime-owned withdrawal and hydraulic-demand semantics, so this pack should reuse them rather than redefine them.
- Public-reference guidance used during exploration:
  - ChemSep for actual-tray equilibrium-stage structure and future efficiency/rate-based layering
  - IDAES for thermo/unit separation and property-package discipline
  - NeqSim / DWSIM for pragmatic startup/steady warmup and specialized column-solver ideas
  - but the v1 implementation target remains a lightweight runtime model, not a mini-ChemSep or equation-oriented Pyomo stack.

## Goals / Non-Goals

**Goals:**
- Add a backend-only `ThermoTrayDistillationColumn` sibling runtime model with explicit actual trays.
- Freeze the governing material, thermal, end-region, and startup equations so implementation does not guess its physics.
- Make tray thermodynamics property-package-backed inside the repo's PR-only envelope.
- Support startup-and-settle operation using the same runtime model rather than a separate steady-state solver.
- Keep numerical safeguards narrow and explicit.
- Preserve existing connection/runtime product-withdrawal semantics and keep gameplay/build/controller exposure unchanged.

**Non-Goals:**
- Replacing or widening `StagewiseDistillationColumn`.
- Turning Howard/Gani into the general production model.
- Adding Murphree efficiency, rate-based transport, flooding/weeping, entrainment, or packed-column behavior in this pack.
- Adding a separate equation-oriented steady-state solver.
- Broadening public starts, build lists, tutorials, controller scope, or client-facing gameplay surfaces.
- Claiming thermodynamic validity outside the supported PR/VLE envelope.

## Decisions

1. **The new model is a new sibling class, not a stagewise rewrite.**
   - `StagewiseDistillationColumn` remains the reduced-order baseline.
   - `ThermoTrayDistillationColumn` becomes the backend-only actual-tray thermo-backed path.

2. **v1 models actual trays directly; it does not collapse trays into equivalent stages.**
   - If a column is configured with `n_trays = N`, the runtime model uses `N` explicit tray control volumes.
   - Murphree tray efficiency is deferred so v1 first proves stable thermo-backed actual-tray dynamics.

3. **The primary tray differential states are liquid component holdups plus shared tray temperature.**
   - Tray vapor accumulation is neglected in v1.
   - This avoids a heavier DAE-style tray energy inversion while still preserving dynamic thermal behavior.

4. **Tray heat capacity is dynamic and thermo-derived, never constant.**
   - `Cp^L_j` comes from the PR-backed tray thermo closure at the current tray state.
   - The temperature-state ODE is therefore a reduced but still thermodynamic energy model.

5. **One equilibrium tray temperature is used per tray.**
   - Liquid and vapor leaving a tray are treated as sharing the tray's equilibrium temperature.
   - Separate liquid/vapor temperatures are deferred with rate-based/nonequilibrium transport.

6. **The tray thermo closure is PR-backed and encapsulated as a named closure family.**
   - The pack freezes the closure family as `Thermo_PR(...)` / `Flash_PR(...)` rather than collapsing it to a reduced-order `K_ref` surrogate.
   - Apply-time implementation may need helper functions or a new wrapper module so the unit does not embed raw flash logic everywhere.

7. **Startup-and-settle replaces a separate steady-state solver in v1.**
   - v1 only requires a lightweight startup-state builder (epsilon holdups, valid initial composition, initial temperatures, initial pressure profile).
   - Settling uses the runtime equations themselves and an explicit settle metric / hold horizon.

8. **Broad hard clamping is rejected.**
   - Use only epsilon floors, composition normalization, and minimal flash-protection fallback when a raw thermo call would otherwise fail.
   - If flash-protection fallback cannot recover a valid thermo evaluation, runtime fails explicitly rather than fabricating a stable trajectory.

9. **Connection/runtime withdrawal semantics are reused, not reinvented.**
   - Existing `connection` live specs already freeze hydraulic-solved withdrawal demand and conservative owner-holdup realizability rules.
   - The new model should plug into those seams instead of inventing hidden distillation-specific line restrictions.

10. **The v1 thermo-backed model stays backend-only.**
    - Session-level stagewise-only wording must be relaxed so backend runtime may use the new sibling path.
    - Public gameplay/build exposure remains gated exactly as-is.

11. **No observability delta spec is needed for this pack.**
    - The live `observability` capability already freezes substrate-owned dynamic distillation process-state, pressure, and duty readouts through the existing snapshot envelope.
    - Apply-time work must keep `ThermoTrayDistillationColumn` compatible with that existing observability contract rather than widening the snapshot schema in this pack.

## Equation Basis

The equations below are the implementation-guiding basis for the new capability and should match the delta spec labels.

### Symbols and region conventions

- Tray index `j = 1..N`, top tray `j = 1`, bottom tray `j = N`
- Species index `k = 1..Ns`
- `N_{j,k}` = tray `j` liquid component holdup of species `k` `[mol]`
- `N^L_j = sum_k N_{j,k}` = total liquid holdup on tray `j` `[mol]`
- `x_{j,k}` = tray `j` liquid composition `[-]`
- `y_{j,k}` = tray `j` equilibrium vapor composition `[-]`
- `T_j` = tray `j` shared equilibrium temperature `[K]`
- `P_j` = tray `j` pressure `[Pa]`
- `L_j` = liquid downflow leaving tray `j` toward tray `j+1` `[mol/s]`
- `V_j` = vapor upflow leaving tray `j` toward tray `j-1` `[mol/s]`
- `N^D_k`, `T_D`, `P_D` = condenser-drum component holdup, temperature, pressure
- `N^B_k`, `T_B`, `P_B` = reboiler-kettle component holdup, temperature, pressure
- `D`, `B`, `R_req` = distillate withdrawal, bottoms withdrawal, and reflux-return request `[mol/s]`
- `Q_C`, `Q_R` = condenser heat removal and reboiler heat input `[W]`

### Smooth guard operators

- `GE-TTD-MAT-4` smooth-plus:

  `sp(a) = 0.5 * (a + sqrt(a^2 + eps_sp^2))`

- `GE-TTD-MAT-6` smooth-min:

  `smin(a, b) = 0.5 * (a + b - sqrt((a - b)^2 + eps_sm^2))`

These operators are deliberate replacements for repeated hard clipping in the normal runtime closure.

### Tray material and hydraulic closure

- `GE-TTD-MAT-1` liquid holdup and composition:

  `N^L_j = sum_k N_{j,k}`

  `x_{j,k} = N_{j,k} / max(N^L_j, eps_N)`

- `GE-TTD-MAT-2` feed flash split:

  `(beta_F,m, x^F_{m,k}, y^F_{m,k}, h^L_F,m, h^V_F,m) = Flash_PR(T_F,m, P_F,m, z_F,m)`

- `GE-TTD-MAT-3` tray pressure profile:

  `P_j = P_top + (j - 1) * DeltaP_tray`

- `GE-TTD-MAT-5` liquid downflow:

  `V^L_j = N^L_j * MW^L_j / rho^L_j`

  `h_j = V^L_j / A_act,j`

  `L_j = C_L,j * sp(h_j - h_weir,j)^(3/2)`

- `GE-TTD-MAT-6` vapor capacity and supply limit:

  `DeltaP_avail,j = sp(DeltaP_tray - rho^L_j * g * h_j - DeltaP_dry,j)`

  `V_cap,j = C_V,j * sqrt(DeltaP_avail,j / max(rho^V_j, eps_rho))`

  `V_sup,N = V_B + sum_{m: j_m = N} beta_F,m * F_m`

  `V_sup,j = V_{j+1} + sum_{m: j_m = j} beta_F,m * F_m` for `j < N`

  `V_j = smin(V_cap,j, V_sup,j)`

- `GE-TTD-MAT-7` tray component balance:

  `dN_{j,k}/dt = L_{j-1} * x_{j-1,k} + V_{j+1} * y_{j+1,k} + sum_{m: j_m = j} ((1 - beta_F,m) * F_m * x^F_{m,k} + beta_F,m * F_m * y^F_{m,k}) - L_j * x_{j,k} - V_j * y_{j,k}`

Boundary substitutions:
- top tray uses `L_0 = R_req` with tray-top liquid composition from the reflux drum
- bottom tray uses `V_{N+1} = V_B` with vapor composition from the reboiler kettle.

### Tray thermo and temperature closure

- `GE-TTD-TH-1` PR-backed tray thermo/property closure:

  `K_{j,k}, h^L_j, h^V_j, rho^L_j, rho^V_j, Cp^L_j = Thermo_PR(T_j, P_j, x_j)`

- `GE-TTD-TH-2` equilibrium vapor composition:

  `y_{j,k} = K_{j,k} * x_{j,k} / sum_r (K_{j,r} * x_{j,r})`

- `GE-TTD-TH-3` enthalpy-flow totals:

  `Hdot_in,j = L_{j-1} * h^L_{j-1} + V_{j+1} * h^V_{j+1} + sum_{m: j_m = j} ((1 - beta_F,m) * F_m * h^L_F,m + beta_F,m * F_m * h^V_F,m)`

  `Hdot_out,j = L_j * h^L_j + V_j * h^V_j`

- `GE-TTD-TH-4` tray temperature-state equation:

  `dT_j/dt = (Hdot_in,j - Hdot_out,j + Q_j - h^L_j * sum_k dN_{j,k}/dt) / max(N^L_j * Cp^L_j, eps_C)`

- `GE-TTD-TH-5` ordinary-tray heat input:

  `Q_j = 0`

Interpretation:
- `T_j` is one shared equilibrium tray temperature, not separate liquid/vapor temperatures.
- `Cp^L_j` is dynamic and thermo-derived, not constant.
- vapor thermal storage is neglected, but vapor enthalpy still enters through `Hdot_in,j` / `Hdot_out,j`.

### Dynamic end regions

#### Total condenser and reflux drum

- `GE-TTD-END-1` drum composition:

  `N^D = sum_k N^D_k`

  `z^D_k = N^D_k / max(N^D, eps_N)`

- `GE-TTD-END-2` drum component balance:

  `dN^D_k/dt = V_1 * y_{1,k} - D * z^D_k - R_req * z^D_k`

- `GE-TTD-END-3` drum temperature-state equation:

  `h^L_D, Cp^L_D, rho^L_D = Thermo_PR_liq(T_D, P_D, z_D)`

  `dT_D/dt = (V_1 * h^V_1 - D * h^L_D - R_req * h^L_D - Q_C - h^L_D * sum_k dN^D_k/dt) / max(N^D * Cp^L_D, eps_C)`

Assumption: v1 top closure is total-condenser only; partial condenser behavior is deferred.

#### Equilibrium kettle / reboiler

- `GE-TTD-END-4` kettle thermo closure:

  `N^B = sum_k N^B_k`

  `z^B_k = N^B_k / max(N^B, eps_N)`

  `(beta_B, x^B_k, y^B_k, h^L_B, h^V_B, Cp^L_B, rho^L_B) = Flash_PR(T_B, P_B, z_B)`

- `GE-TTD-END-5` duty-limited and holdup-limited boilup:

  `V_therm,B = sp(Q_R) / max(h^V_B - h^L_B, eps_H)`

  `V_cap,B = C_B * sqrt(sp(N^B - N^B_min))`

  `V_B = smin(V_therm,B, V_cap,B)`

- `GE-TTD-END-6` kettle component balance:

  `dN^B_k/dt = L_N * x_{N,k} - B * z^B_k - V_B * y^B_k`

- `GE-TTD-END-7` kettle temperature-state equation:

  `dT_B/dt = (L_N * h^L_N - B * h^L_B - V_B * h^V_B + Q_R - h^L_B * sum_k dN^B_k/dt) / max(N^B * Cp^L_B, eps_C)`

Interpretation:
- v1 reboiler boilup uses a thermo-backed latent enthalpy difference `h^V_B - h^L_B`, not a fixed `Q/lambda` constant.
- Bottoms liquid withdrawal still remains owner-holdup-bounded and connection-runtime compatible through the existing `connection` contract.

### Startup-and-settle procedure

- `GE-TTD-ST-1` numerically dry startup state:

  `N_{j,k}(0) = eps_start * z^0_k`

  `N^D_k(0) = eps_drum * z^0_k`

  `N^B_k(0) = eps_kettle * z^0_k`

  `T_j(0) = T^0_j`, `T_D(0) = T^0_D`, `T_B(0) = T^0_B`

  `P_j(0) = P_top,0 + (j - 1) * DeltaP_tray`

- `GE-TTD-ST-2` default v1 startup guesses:

  `z^0 = z_first_feed` when a first feed exists, otherwise the constructor default composition

  `T^0_j = T_first_feed` for all trays when no stronger startup profile is supplied

- `GE-TTD-ST-3` settle metric:

  `r_settle(t) = max(max_{j,k} |dN_{j,k}/dt| / max(N_scale,j, eps_N), max_j |dT_j/dt| / max(T_scale,j, eps_T), |dT_D/dt| / max(T_scale,D, eps_T), |dT_B/dt| / max(T_scale,B, eps_T))`

- `GE-TTD-ST-4` settle completion:

  settled only when `r_settle(t) <= eps_settle` for contiguous horizon `tau_settle` under fixed boundary conditions.

This deliberately replaces a separate steady-state solver in v1 with startup-and-settle using the same runtime equations.

### Thermodynamic scope and numerical guards

- v1 thermo basis is the repo's current PR vapor-liquid-equilibrium envelope only.
- No azeotrope, LLE/VLLE, water-heavy nonideal, reactive-distillation, or cryogenic fidelity claims are made.
- Broad hard clipping is rejected.
- Allowed guards are limited to:
  - epsilon holdup floors (`eps_*`)
  - composition normalization
  - bounded flash-protection fallback when a raw thermo call would otherwise fail
  - explicit runtime failure if even the bounded fallback cannot recover a valid thermo evaluation.

## Risks / Trade-offs

- **Semi-explicit temperature-state ODE is less rigorous than a full energy-holdup / DAE formulation.**
  - Chosen because it fits the current `ProcessModel` / `solve_ivp` runtime without requiring a separate equation-oriented solver stack.
- **PR-only thermo scope is intentionally narrow.**
  - This keeps v1 honest and implementable, but it means the model cannot promise arbitrary-mixture fidelity outside that envelope.
- **Startup-and-settle is slower than a dedicated steady-state solve for operating-point studies.**
  - Chosen because the user prefers avoiding a separate initializer subsystem in v1.
- **Deferring Murphree efficiency removes one path for fitting actual-tray inefficiency.**
  - Chosen because v1 first needs to prove stable thermo-backed actual-tray dynamics before adding another calibration layer.
- **Reduced vapor/hydraulic closure is still a heuristic.**
  - It is explicit, named, and smoother than hard-clipped stepper behavior, but it is not full tray-hydraulics design fidelity.

## Verification Strategy

- TDD leads the implementation.
- Required verification commands:
  - `uv run pytest tests/unit_process/test_layer4_thermo_tray_distillation.py`
  - `uv run pytest tests/integration/test_thermo_tray_distillation_runtime.py`
  - `uv run python examples/dynamic_simulation_demos/thermo_tray_distillation_startup_demo.py`
  - `openspec validate --specs --strict --no-interactive`
- Required verification evidence:
  - tray component holdups evolve according to the frozen material balances rather than fixed internal flows
  - tray temperatures evolve from thermo-backed dynamic `Cp` and enthalpy-flow terms rather than constant-Cp or feed-temperature proxy behavior
  - condenser/reboiler end regions remain dynamic and mass-conservative
  - startup from numerically dry state settles under fixed boundary conditions using the same runtime equations rather than a separate steady-state solve
  - no broad hard clamping is required in normal runtime behavior; flash-protection fallback is bounded and explicit
  - gameplay/build/client exposure remains unchanged.

## Open Questions

- None. The v1 scope is intentionally narrow and the unresolved higher-fidelity items (Murphree, rate-based transport, non-PR thermo, broad public exposure) are explicitly deferred rather than left ambiguous.

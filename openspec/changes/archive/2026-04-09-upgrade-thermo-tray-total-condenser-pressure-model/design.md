## Context

- The live `thermo-tray-distillation` capability already froze a backend-only PR-backed actual-tray model with explicit tray liquid holdup, shared tray temperature, dynamic end regions, startup-and-settle, and narrow numerical guards.
- Exploration and audit work showed that the current top closure is still too weak for the desired realism boundary:
  - `p_top_pa` is a constant pressure anchor,
  - tray pressures are algebraic `P_top + (j - 1) * DeltaP_tray`,
  - the top end has only a liquid drum state and no vapor headspace,
  - condenser duty acts in the drum liquid temperature balance but does not explicitly realize condensation vs non-condensed carryover,
  - and the current unit override of `step()` bypasses the framework-owned `solve_ivp` / LSODA integration path.
- User decisions reached in exploration and now frozen for planning:
  - keep the main path as an explicit **total-condenser** model
  - treat insufficient cooling as degraded total-condenser behavior, not as an automatic switch to partial-condenser semantics
  - create a separate **partial-condenser** sibling capability for semantic clarity
  - include condenser subcooling explicitly
  - use a medium-complexity pressure model:
    - top vapor-headspace pressure
    - liquid outlet pressures derived from headspace pressure plus hydrostatic head
    - bottom pressure derived from top pressure plus accepted tray/column pressure-drop decomposition
    - tray pressures interpolated between live top and bottom pressures
  - allow optional blanket-gas and vent physical ports, but keep pressure-control policy outside the unit
  - ground equations in accepted first-principles balances and accepted tray-hydraulics / condenser practice rather than invented surrogates.
- Repo constraints that still shape the design:
  - `ProcessModel.step()` is intended to integrate through `solve_ivp` with configured solver options.
  - `ThermoTrayDistillationColumn` currently overrides `step()` and bypasses that path.
  - hydraulic participation already supports multiple ports and distinct/shared pressure states within one monolithic unit, so a separate reflux-drum process unit is not structurally required.
  - the live `connection` runtime consumes process-unit outlet pressures from `get_outlet_stream(...)`, but explicit downstream backpressure feedback into thermo-tray is not clearly present as a current unit boundary contract.
  - the user explicitly said not to use other distillation unit implementations in the repo as sources of trusted physics; they may be used only as structural/runtime precedents.

## Goals / Non-Goals

**Goals:**
- Upgrade the thermo-tray top closure to an explicit total-condenser-with-headspace model that can represent incomplete condensation, headspace pressure buildup, and subcooled condenser/drum liquid.
- Freeze accepted governing equations for:
  - realized condensed flow,
  - non-condensed carryover,
  - headspace pressure,
  - hydrostatic liquid outlet pressure,
  - bottom pressure derived from top pressure plus accepted tray/column pressure drop,
  - and interpolation of tray pressures between live end pressures.
- Split total-condenser and partial-condenser semantics into distinct backend-only capabilities/classes.
- Preserve explicit reflux/distillate liquid-withdrawal ownership from the drum.
- Restore alignment with the framework-owned solver path instead of maintaining a unit-private explicit-Euler integration path.
- Keep optional blanket-gas and vent physical capability in the unit while leaving pressure-control policy to controllers.

**Non-Goals:**
- Implementing the partial-condenser capability in this pack; this pack only freezes its need as a separate contract.
- Adding PSV / relief-valve safety logic.
- Adding full rate-based nonequilibrium condensation, distributed condenser-wall dynamics, or full tray-by-tray pressure states.
- Promising arbitrary nonideal, water-heavy, reactive, or cryogenic fidelity outside the repo’s PR/VLE envelope.
- Splitting the condenser drum into a separate placeable/process unit solely to obtain hydraulic behavior.
- Widening gameplay/build/client/catalog/controller exposure in this change.

## Decisions

1. **Total-condenser overload remains total-condenser topology.**
   - Insufficient cooling must not silently become partial-condenser semantics.
   - The total-condenser capability will therefore include `realized_condensed_flow` plus `non_condensed_flow` and a vapor headspace region.

2. **Total-condenser and partial-condenser capabilities are split into sibling classes/contracts.**
   - This avoids mode-dependent topology and port semantics inside one static-schema process-model contract.
   - The total-condenser path becomes the main upgraded path in this pack; the partial-condenser path is only reserved/declared here.

3. **The top region is modeled as vapor headspace plus liquid reflux drum.**
   - Vapor leaving the top tray discharges into the condenser/headspace region.
   - Condensed liquid joins the reflux drum.
   - Non-condensed vapor accumulates in or leaves from the headspace.
   - Distillate and reflux remain liquid withdrawals from the drum inventory.

4. **Top vapor pressure and liquid outlet pressures are distinct.**
   - The top tray sees the condenser vapor-headspace pressure `P_H`.
   - Reflux/distillate liquid outlets see `P_H + rho_L g h_submergence`.
   - This keeps vapor-side and liquid-side hydraulic semantics physically separate without splitting the unit.

5. **Bottom pressure is derived from top pressure plus Bennett-Agrawal-Cook-style tray-hydraulics pressure drop.**
   - The frozen first-apply closure family is standard tray decomposition using the Bennett, Agrawal, Cook (1983) sieve-tray pressure-drop family as the accepted provenance basis:
     - dry tray drop
     - plus liquid/froth head
     - plus only explicitly named residual end terms when physically justified
   - Tray pressures are then interpolated between live top and bottom pressures.
   - This is simpler than full tray-by-tray pressure states while still tying pressure to actual operating conditions.

6. **Condenser subcooling is explicit in the enthalpy balance.**
   - The condenser/drum liquid state is allowed to be subcooled rather than pinned to bubble point.
   - Condenser duty must therefore account for desuperheating + condensation + subcooling as needed through the enthalpy difference between incoming top vapor and outgoing drum liquid state.

7. **Blanket-gas and vent are physical ports/boundaries, not built-in control laws.**
   - The unit may expose optional blanket-gas addition and vent withdrawal capability.
   - Control logic such as `blanket gas if pressure below setpoint` / `vent if pressure above setpoint` belongs to external controllers and tutorials later, not to the intrinsic unit equations.

8. **Framework-owned integration path is restored.**
   - The total-condenser thermo-tray unit should not keep bypassing system solver options with a private explicit-Euler step.
   - If any internal substep refinement is still needed later for realizability or event handling, it should wrap and delegate to the base process-model integration seam rather than replace it.

9. **The headspace pressure closure is frozen as PR bubble pressure plus excess-headspace gas pressure.**
   - The first apply slice does **not** leave the headspace closure as an EOS-vs-bubble open choice.
   - The frozen reduced-order closure is:
     - `P_bubble,PR(T_D, z_D)` from the official `thermo` PR flash bubble-point solve (`FlashVL.flash(T=T_D, VF=0, zs=z_D)` or an equivalent repo helper)
     - plus an excess-headspace gas partial-pressure term from explicit headspace inventory and volume.
   - The excess-headspace inventory owns overload carryover and optional blanket-gas/vent terms above the condensable equilibrium already implied by `P_bubble,PR`, so the same vapor contribution is not counted twice.
   - This closure is chosen because it is directly supported by the repo’s shipped `thermo` dependency and official docs, is easier to verify than a coupled fugacity root solve, and still preserves explicit pressure buildup from overload/blanket inventory.

## Equation Basis

The equations below are the implementation-guiding basis for the upgraded total-condenser thermo-tray path and are intended to align with the new delta spec labels.

### Symbols and region conventions

- Tray index `j = 1..N`, top tray `j = 1`, bottom tray `j = N`
- Species index `k = 1..Ns`
- `N_{j,k}` = tray `j` liquid component holdup of species `k` `[mol]`
- `N^L_j = sum_k N_{j,k}` = total liquid holdup on tray `j` `[mol]`
- `x_{j,k}` = tray `j` liquid composition `[-]`
- `y_{j,k}` = tray `j` equilibrium vapor composition `[-]`
- `T_j` = tray `j` shared equilibrium temperature `[K]`
- `P_j` = tray `j` pressure `[Pa]`
- `L_j` = liquid downflow leaving tray `j` `[mol/s]`
- `V_j` = vapor upflow leaving tray `j` `[mol/s]`
- `N^D_k`, `T_D` = condenser-drum liquid component holdup and liquid temperature
- `n^X_k`, `T_H`, `P_H` = condenser excess-headspace-gas component holdup, temperature, and total pressure
- `N^B_k`, `T_B`, `P_B` = reboiler-kettle component holdup, temperature, and pressure
- `D_realized`, `R_realized`, `B_realized` = realized distillate, reflux, and bottoms liquid withdrawals `[mol/s]`
- `Q_C`, `Q_R` = condenser heat removal and reboiler heat input `[W]`
- `V_cond,realized` = realized condensed flow from top-tray vapor `[mol/s]`
- `V_noncond` = non-condensed vapor carryover into the headspace `[mol/s]`
- `V_shell` = total top-end shell volume assigned to drum + headspace `[m^3]`
- `V_LD` = reflux-drum liquid volume `[m^3]`
- `V_H = V_shell - V_LD` = headspace vapor volume `[m^3]`

### Provenance and accepted sources

The frozen equation families below are grounded in standard dynamic distillation and vessel-pressure practice, not invented repo-local surrogates. Design-time reference set:

- Choe & Luyben (1987), “Rigorous dynamic models of distillation columns” — dynamic distillation balance structure and tray-pressure-drop decomposition context.
- Luyben (2012), “Realistic Models for Distillation Columns with Partial Condensers Producing Both Liquid and Vapor Products” — condenser/reflux-drum vapor-liquid pressure behavior and realistic top-end dynamics.
- Luyben (2017), “Dynamic simulation of flooded condensers” — overloaded total-condenser behavior and condenser/drum interaction under insufficient condensation.
- Bennett, Agrawal, Cook (1983), sieve-tray pressure-drop correlation — accepted dry-drop / froth-head correlation family.
- Kister, *Distillation Operation* — accepted industrial tray, condenser, reflux drum, and pressure-control practice.
- Seader, Henley, Roper, *Separation Process Principles* and Perry’s Handbook — VLE, hydrostatic outlet pressure, and condenser energy-balance fundamentals.

### Tray pressure and column pressure drop

The accepted reduced-order family for the first dynamic end-pressure slice is:

`DeltaP_j = DeltaP_dry,j + DeltaP_head,j + DeltaP_res,j`

with:

`DeltaP_head,j = rho_eff,j * g * h_eff,j`

and:

`P_bottom = P_H + sum_{j=1..N} DeltaP_j + DeltaP_misc`

`P_j = P_H + ((j - 1) / max(N - 1, 1)) * (P_bottom - P_H)`

Interpretation:
- `DeltaP_dry,j` is the accepted dry tray-drop family from tray openings/valves/caps.
- `DeltaP_head,j` is the accepted liquid/froth static head contribution.
- `DeltaP_res,j` and `DeltaP_misc` are only allowed if tied to identified physical end losses or residual pressure losses documented explicitly during implementation; they must not become catch-all tuning buckets.

The first apply slice should use the Bennett-Agrawal-Cook sieve-tray family as the accepted provenance basis for `DeltaP_dry,j` and effective froth/head treatment, mapped onto the thermo-tray’s reduced-order geometry fields (`A_act,j`, retained liquid/froth height from holdup, and named dry-drop coefficient terms). This freezes one accepted correlation family and avoids implementation-time correlation shopping.

The first apply slice should prefer the simplest executable member of that accepted family already compatible with repo state variables:
- thermo-backed liquid density
- tray liquid/froth retained height from tray holdup and active area
- Bennett-Agrawal-Cook-style dry-drop coefficient/correlation

### Total-condenser realization with overload and subcooling

#### Condensation / non-condensation split

Use a total-condenser realization with explicit non-condensed carryover:

`V_top = V_1`

`Q_C,avail = max(0.0, -Q_C)`

`V_cond,therm = Q_C,avail / max(h^V_top - h^L_D, eps_H)`

`V_cond,realized = min(V_top, V_cond,therm, V_cond,cap)`

`V_noncond = max(0.0, V_top - V_cond,realized)`

Notes:
- `h^L_D` is evaluated at the current drum liquid state, so the enthalpy difference naturally includes subcooling when `T_D` falls below saturation.
- `V_cond,cap` is optional in the first slice only if there is an accepted physical capacity basis available (for example UA/area or documented condenser-flow heuristic). If not yet available, omit it rather than inventing a made-up capacity term.

#### Drum/headspace component balances

Liquid drum:

`dN^D_k/dt = V_cond,realized * y_top,k - D_realized * z^D_k - R_realized * z^D_k + N_cond,interface,k`

Excess headspace gas inventory:

`dn^X_k/dt = V_noncond * y_top,k - V_vent,k + n_blanket,k - N_cond,interface,k`

`N_cond,interface,k` is the explicit duty-limited recondensation sink from excess headspace gas back to drum liquid. The implementation may collapse it only if the same mass and energy bookkeeping is preserved and tested explicitly.

#### Headspace pressure closure

The frozen first-apply closure is the reduced-order PR bubble-pressure plus excess-headspace-gas pressure form:

`P_H = P_bubble,PR(T_D, z_D) + P_X`

`P_X = n_X * Z_H * R * T_H / max(V_H, eps_V)`

`n_X = sum_k n^X_k`

`P_bubble,PR(T_D, z_D)` is obtained from the repo’s official PR-backed flash dependency by solving the bubble-point pressure at fixed drum liquid state, e.g. `FlashVL.flash(T=T_D, VF=0, zs=z_D).P` through a repo helper seam.

Interpretation:
- `P_bubble,PR` carries the condensable equilibrium contribution implied by the drum liquid state.
- `P_X` carries the additional pressure from overload carryover and optional blanket gas accumulated in the explicit headspace inventory.
- The first apply slice may evaluate `Z_H` from the PR gas state for the headspace composition; if that proves numerically brittle for the supported mixture slice, `Z_H = 1` is an allowed initialization/hot-start simplification only when the implementation still preserves the same governing pressure law and documents the retained approximation honestly.

### Drum liquid energy / subcooling

The total-condenser liquid energy balance is:

`dT_D/dt = (V_cond,realized * h^V_top - D_realized * h^L_D - R_realized * h^L_D - Q_C - h^L_D * sum_k dN^D_k/dt) / max(N^D * Cp^L_D, eps_C)`

Interpretation:
- This is a well-accepted lumped enthalpy balance.
- It allows desuperheating + condensation + subcooling through the enthalpy term `h^V_top - h^L_D(T_D, P_H, z_D)`.
- The total-condenser class therefore does not pin the liquid outlet to bubble point.

### Liquid outlet pressures from hydrostatic head

For each drum liquid outlet nozzle `m`:

`P_liq,out,m = P_H + rho^L_D * g * h_sub,m + DeltaP_static,m`

This is the recommended medium-complexity separation between:
- top tray downstream vapor pressure: `P_H`
- liquid source pressure for reflux/distillate hydraulics: `P_H + hydrostatic head`

This keeps reflux flow physically possible even when there is no vapor outlet flow because liquid outlets can still see positive hydrostatic head above the headspace pressure.

### Blanket gas and vent capability

If blanket gas or venting are configured:

`dn_inert/dt = ndot_blanket - ndot_vent,inert`

`ndot_vent = f(P_H, P_downstream, u_vent)`

These are **physical boundary terms**, not intrinsic control laws.

The unit should expose the capability to add/remove headspace species physically, while external controllers own rules such as:
- add inert gas if `P_H < P_set`
- vent if `P_H > P_set`

### Solver-path decision

The total-condenser thermo-tray model should return to the framework-owned integration seam:

- base `ProcessModel.step()` integrates through `solve_ivp(..., **self._solver_options)`
- the thermo-tray class must not silently replace that with a private explicit-Euler-only path

If bounded substeps are later still required for realizability, they should wrap and delegate to the framework path analogously to accepted runtime patterns rather than overriding the solver itself.

## Risks / Trade-offs

- **Headspace pressure closure is intentionally reduced-order rather than a full coupled EOS/interface solve.**
  - This is a deliberate first-apply simplification, not an unresolved decision.
  - The fidelity boundary is explicit: PR bubble pressure for the drum liquid plus excess-headspace gas pressure for overload/blanket inventory.

- **Column pressure drop remains reduced-order.**
  - Bennett-Agrawal-Cook provenance is frozen, but the thermo-tray geometry is still a reduced-order mapping to an effective sieve-tray family.
  - The implementation must avoid turning `DeltaP_res,j` or `DeltaP_misc` into tuning buckets with no provenance.

- **Monolithic unit structure is still more complex than the current liquid-only top closure.**
  - However, splitting the condenser drum into a separate process unit would widen topology and hydraulic seams unnecessarily for this slice.

- **Blanket/vent capability can widen scope if treated as built-in control.**
  - To keep scope tight, the unit only owns physical ports/boundaries; control policy is explicitly deferred to later controller work.

- **Solver-path restoration may surface hidden stiffness or realizability issues.**
  - This is a desirable exposure because the current explicit-Euler override is already inconsistent with framework expectations.

## Verification Strategy

- TDD leads the implementation.
- Equation-fidelity tests are required for the newly frozen total-condenser pressure/headspace equations.
- Required verification commands:
  - `uv run pytest tests/unit_process/test_layer4_thermo_tray_distillation.py`
  - `uv run pytest tests/integration/test_thermo_tray_distillation_runtime.py`
  - `uv run pytest tests/integration/test_thermo_tray_distillation_demo_operating_point.py`
  - `uv run python examples/dynamic_simulation_demos/thermo_tray_distillation_startup_demo.py`
  - `uv run python examples/dynamic_simulation_demos/thermo_tray_step_characterization_demo.py`
  - `openspec validate --specs --strict --no-interactive`
- Required evidence:
  - insufficient cooling produces `V_noncond > 0` without silently changing the unit to partial-condenser semantics
  - top-headspace pressure rises when non-condensed vapor accumulates and falls when condensation/venting dominates
  - reflux/distillate source pressures exceed headspace pressure by documented hydrostatic head terms
  - bottom pressure follows the frozen dynamic pressure-drop family rather than a constant constructor value
  - condenser liquid can be subcooled below bubble point when duty permits
  - blanket-gas and vent physical terms affect headspace inventory/pressure without embedding controller logic in the unit
  - runtime stepping honors framework solver options rather than silently using a private explicit-Euler path
  - gameplay/build/client exposure remains unchanged.

## Planning closure

- No blocking design questions remain in this pack.
- The frozen headspace pressure closure is PR bubble pressure plus excess-headspace-gas pressure.
- The frozen pressure-drop provenance family is Bennett-Agrawal-Cook-style dry-drop plus froth-head decomposition.

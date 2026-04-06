## Context

- The live distillation contract currently allows only `StagewiseDistillationColumn` as a runtime distillation model and explicitly forbids reintroducing a `ShortcutDistillation` compatibility path.
- Repo evidence shows the existing runtime seams already support monolithic process models with explicit feed/product/reflux ports and hydraulic-solved outlet-demand application through `apply_requested_outlet_through_flow_demand(...)`.
- The user explicitly asked for two paper-faithful dynamic multicomponent distillation approaches, with equations taken directly from the papers rather than invented closures.
- Source evidence is now good enough to freeze a planning contract:
  - Howard, G. M. (1970), *Unsteady State Behavior of Multicomponent Distillation Columns: Part I: Simulation*
  - Gani, R., Ruiz, C. A., and Cameroni, I. T. (1986), *A generalized model for distillation columns—I. Model description and applications*
- Howard was verified from extracted text plus optimized page images covering the plate-balance, equilibrium/efficiency, bubble-point derivative, feed-plate, and constant-volume-holdup blocks.
- Howard Eqs. (22) through (30), including the constant-volume-holdup page that shows Eqs. (26) through (30), are backed locally by `.tmp/paper_eq_images_optimized/howard-5.png`.
- Gani was verified from extracted text plus optimized main-text images and the optimized appendix image for `A.1` through `A.8`; appendix `A.25` through `A.34` had already been verified separately.
- The current separation package exports only `StagewiseDistillationColumn`, so later implementation will need explicit sibling-module and package-export updates.

## Goals / Non-Goals

**Goals:**
- Add two explicit sibling runtime classes:
  - `Howard1970DistillationColumn`
  - `Gani1986DistillationColumn`
- Keep `StagewiseDistillationColumn` intact as the repo's existing reduced-order baseline.
- Freeze paper-faithful governing equations, named closures, and first-slice boundaries so implementation is not forced to guess.
- Reuse the repo's existing monolithic process-model and runtime-demand seams instead of inventing a parallel distillation runtime path.
- Keep the change backend-only and comparison-oriented.

**Non-Goals:**
- Replacing `StagewiseDistillationColumn`.
- Reintroducing any `ShortcutDistillation` class, alias, or shim.
- Widening gameplay/start/build exposure for distillation units in this change.
- Defining a new connection-capability contract unless implementation proves the current runtime-demand seam is insufficient.
- Implementing every optional mode in either paper.
- Requiring full rigorous MESH, rate-based mass transfer, pressure-swing distillation, or non-paper control heuristics in this pack.
- For Gani specifically: multiple columns, closed-loop controller execution, start-up procedure support, alternative plate families beyond the frozen first slice, and optional warning-only hydraulic checks remain out of scope here.

## Decisions

1. **The new models are explicit sibling classes, not modifications of the existing stagewise class.**
   - `StagewiseDistillationColumn` already owns a reduced-order repo-specific realism contract.
   - Howard and Gani must stay identifiable as paper-faithful comparison models rather than silently changing the meaning of the existing class.

2. **The runtime seam stays monolithic and backend-only.**
   - All three distillation classes should remain monolithic `ProcessModel` units in the separation package.
   - Implementation should reuse the current feed/product/reflux seam shape and the existing outlet-demand callback path when physically meaningful for the paper-faithful models.
   - This pack does not reopen gameplay/catalog/start exposure.

3. **Howard's first executable slice is the paper's open-loop single-column plate model with feed-plate extension and constant-volume holdup.**
   - Howard's paper is intentionally general about specified pressures, holdups, and heat leaks.
   - To keep the contract executable instead of underdetermined, this pack freezes the first Howard slice around:
     - the general component-balance family,
     - equilibrium and tray-efficiency relations,
      - the implicit-variable temperature/bubble-point block,
      - the feed-plate extension,
      - and the direct constant-volume-holdup closure from Eqs. (26)–(29).
   - Howard Eq. (30) is treated in this repo as a coefficient-family shorthand derived from the Eq. (28) expansion, not as a required first executable interface.
   - If Eq. (30) is later recovered exactly from source evidence or derived deterministically from the direct equations, implementation may expose that coefficient family as a secondary algebraic convenience.
   - Invented or heuristic `F_j`, `G_j`, `K_j` surrogates do **not** satisfy this contract.
   - This keeps the implementation source-faithful without promising every alternative Howard specification family on day one.

4. **Gani's first executable slice is a single-column, open-loop generalized model with the paper's core ODE balances, thermodynamic/property closures, reflux-drum/reboiler balances, generic hydraulic dependency family, and bubble-cap appendix A.1–A.8.**
   - The paper itself is broader than what this repo needs immediately.
   - This change therefore freezes a bounded single-column open-loop slice, not the paper's full multi-column, closed-loop, start-up, and all-plate-family package.
   - Bubble-cap hydraulics from `A.1`–`A.8` are the first concrete appendix path for the Gani implementation.
   - Controller equations (22)–(24), external wall heat-transfer procedures, start-up procedures, and alternate plate families remain deferred.

5. **The live connection contract stays unchanged in this planning pack.**
   - Current live connection specs already define hydraulic-solved product demand, explicit withdrawal ownership, and conservative demand-vs-realizability handling.
   - Current code already exposes `apply_requested_outlet_through_flow_demand(...)` and hydraulic participation seams.
   - The new pack therefore modifies `units-and-components` only.

6. **Equation fidelity is a first-class verification target.**
   - Tests for the new classes should include small synthetic-state regression checks against the frozen Howard and Gani equations, not only qualitative transient behavior.
   - `simulation-realism-required: true` applies to implementation and review of this change.

## Equation Basis

### Howard (1970) first-slice contract

**Paper assumptions used in this pack**
- Vapor holdup is negligible on and between plates.
- Liquid on and leaving each plate is well mixed.
- Vapor-liquid relation is established instantaneously through the paper's equilibrium/efficiency relations.
- Condenser and reboiler pools are treated as well mixed.

**Frozen symbols**
- `j` = plate index, `i` = component index
- `R_j` = liquid holdup on plate `j`
- `x_{j,i}`, `y_{j,i}`, `y^*_{j,i}` = liquid, actual vapor, and equilibrium vapor compositions
- `V_j`, `L_j` = vapor and liquid flow rates
- `h_j`, `H_j` = liquid and vapor enthalpies
- `Q_{Lj}` = plate heat loss term

**Frozen governing equations**

- `GE-H70-1` General component balance (Howard Eq. 5):

  `R_j * dx_{j,i}/dt = V_{j+1} * (y_{j+1,i} - x_{j,i}) + L_{j-1} * (x_{j-1,i} - x_{j,i}) - V_j * (y_{j,i} - x_{j,i})`

- `GE-H70-2` Equilibrium relation (Howard Eq. 6):

  `y^*_{j,i} = K_i(T_j, P_j) * x_{j,i}`

- `GE-H70-3` Vaporization efficiency (Howard Eq. 7):

  `E^o_{j,i} = y_{j,i} / y^*_{j,i}`

- `GE-H70-4` Murphree efficiency (Howard Eq. 8):

  `E^M_{j,i} = (y_{j,i} - y_{j-1,i}) / (y^*_{j,i} - y_{j-1,i})`

- `GE-H70-5` Liquid enthalpy and algebraic energy-balance form (Howard Eqs. 9 and 14):

  `h_j = sum_i x_{j,i} * f_i(T_j) + phi_M(x_{j,1} ... x_{j,NC})`

  `0 = V_{j+1} * ((H_{j+1} - h_j) - A_j) + L_{j-1} * ((h_{j-1} - h_j) - B_j) - V_j * ((H_j - h_j) - C_j) - Q_{Lj}`

- `GE-H70-6` Bubble-point condition and implicit temperature derivative block (Howard Eqs. 15–21):

  `sum_i K_i(T_j) * x_{j,i} = 1`

  `dT_j/dx_{j,i} = -(dZ/dx_{j,i}) / (dZ/dT_j)`

  with

  `Z(T_j, x_j) = sum_{m=1}^{NC-1} [K_m(T_j) - K_c(T_j)] * x_{j,m} + K_c(T_j)`

  and the paper's Eq. (21) working expression used for `dT_j/dx_{j,i}` over the `NC - 1` independent components.

- `GE-H70-7` Feed-plate extension (Howard Eqs. 22–25):

  `R_j * dx_{j,i}/dt = V_{j+1} * (y_{j+1,i} - x_{j,i}) + L_{j-1} * (x_{j-1,i} - x_{j,i}) + F * (x_{F,i} - x_{j,i}) - V_j * (y_{j,i} - x_{j,i})`

  `dR_j/dt = V_{j+1} + L_{j-1} + F - V_j - L_j`

  `d(R_j h_j)/dt = V_{j+1} * H_{j+1} + L_{j-1} * h_{j-1} + F * h_F - V_j * H_j - L_j * h_j + Q_{Lj}`

  `+ F * ((h_F - h_j) - D_j)`

- `GE-H70-8` Constant-volume-holdup closure (Howard Eqs. 26–29, with Eq. 30 optional only as a source-exact or deterministically derived shorthand):

  `R_j = V_bar * v(x_j, T_j)`

  `v(x_j, T_j) = sum_i x_{j,i} * v_i(T_j)`

  `-V_bar * d(v(x_j, T_j)) / dt = V_{j+1} + L_{j-1} - V_j - L_j`

  `0 = V_{j+1} * (1 - F_j) + L_{j-1} * (1 - G_j) - V_j * (1 - K_j) - L_j`

  with the first executable slice required to satisfy the direct Eq. (28) derivative balance and the Eq. (29) rearranged closure without inventing surrogate coefficient families.

  If the Eq. (30) shorthand is used, `F_j`, `G_j`, and `K_j` must come from the source-exact or deterministically derived coefficient family implied by the Eq. (28) expansion, not from unnamed heuristics.

**Howard first-slice boundary for this repo**
- Open-loop, single-column execution only.
- Constant-volume holdup is the frozen first executable holdup specification in this pack.
- Direct Eq. (28) and Eq. (29) closure is the normative runtime path for this first slice; Eq. (30) shorthand is optional only when source-exact or deterministically derived.
- Pressure, holdup-specification inputs, and heat-leak terms remain named inputs or named closures rather than being silently replaced by the repo's reduced-order stagewise hydraulics.

### Gani, Ruiz, Cameroni (1986) first-slice contract

**Paper assumptions used in this pack**
- Molar vapor holdup is negligible compared to molar liquid holdup.
- Liquid and vapor leaving each plate are in thermal equilibrium.
- Murphree plate efficiency applies and liquid/vapor are perfectly mixed on each plate.

**Frozen symbols**
- `c` = column index, `p` = plate index, `i` = component index
- `C^c_{p,i}` = plate component holdup
- `C^c_{T,p}` = total plate holdup
- `C^c_{E,p}` = total plate energy holdup
- `x^c_{p,i}`, `y^c_{p,i}`, `y^{*c}_{p,i}` = liquid, actual vapor, and equilibrium vapor compositions
- `Theta^c_p`, `Pi^c_p` = plate temperature and pressure
- `V^c_p`, `L^c_p` = vapor and liquid plate flow rates
- `E^c_{L,p}`, `E^c_{V,p}` = liquid and vapor entrainment/weeping-type terms from the hydraulic subset
- `P^c_{L,p}`, `P^c_{V,p}` = liquid and vapor product or side draw terms in the paper notation

**Frozen governing equations**

- `GE-G86-1` Component mass balance (Gani Eq. 1):

  `dC^c_{p,i}/dt = F^c_{V,p} * Y^c_{F,p,i} + F^c_{L,p} * x^c_{F,p,i} + V^c_{p-1} * y^c_{p-1,i} + E^c_{L,p-1} * x^c_{p-1,i} + L^c_{p+1} * x^c_{p+1,i} + E^c_{V,p+1} * y^c_{p+1,i} - (P^c_{V,p} + V^c_p + E^c_{V,p}) * y^c_{p,i} - (P^c_{L,p} + L^c_p + E^c_{L,p}) * x^c_{p,i}`

- `GE-G86-2` Total energy balance (Gani Eq. 2):

  `dC^c_{E,p}/dt = F^c_{V,p} * H^c_{F,p} + F^c_{L,p} * h^c_{F,p} + V^c_{p-1} * H^c_{p-1} + E^c_{L,p-1} * h^c_{p-1} + L^c_{p+1} * h^c_{p+1} + E^c_{V,p+1} * H^c_{p+1} - (P^c_{V,p} + V^c_p + E^c_{V,p}) * H^c_p - (P^c_{L,p} + L^c_p + E^c_{L,p}) * h^c_p`

- `GE-G86-3` Total mass balance (Gani Eq. 3):

  `dC^c_{T,p}/dt = F^c_{V,p} + F^c_{L,p} + V^c_{p-1} + E^c_{L,p-1} + L^c_{p+1} + E^c_{V,p+1} - V^c_p - E^c_{L,p} - L^c_p - E^c_{V,p} - P^c_{V,p} - P^c_{L,p}`

- `GE-G86-4` Definitions and Murphree efficiency (Gani Eqs. 4–8):

  `C^c_{T,p} = sum_i C^c_{p,i}`

  `C^c_{E,p} = h^c_p * C^c_{T,p}`

  `sum_i x^c_{p,i} = sum_i y^c_{p,i} = 1`

  `x^c_{p,i} = C^c_{p,i} / C^c_{T,p}`

  `h^c_p = C^c_{E,p} / C^c_{T,p}`

  `y^{*c}_{p,i} = (y^c_{p,i} - y^c_{p-1,i}) / ME^c_p + y^c_{p-1,i}`

- `GE-G86-5` Equilibrium, enthalpy, density, and molecular-weight closures (Gani Eqs. 9–18):

  `y^{*c}_{p,i} = K^c_{p,i} * x^c_{p,i}`

  `K^c_{p,i} = f(x^c_p, y^c_p, Theta^c_p, Pi^c_p)`

  `H^c_p = f(y^c_p, Theta^c_p, Pi^c_p)`

  `h^c_p = f(x^c_p, Theta^c_p, Pi^c_p)`

  `rho_bar^c_{L,p} = sum_i rho^c_{L,p,i} * x^c_{p,i}`

  `rho_bar^c_{V,p} = sum_i rho^c_{V,p,i} * y^c_{p,i}`

  `rho^c_{L,p,i} = f(Pi^c_p, R, Theta^c_p, Z^c_{L,p,i})`

  `rho^c_{V,p,i} = f(Pi^c_p, R, Theta^c_p, Z^c_{V,p,i})`

  `M_bar^c_{L,p} = sum_i M^c_{L,p,i} * x^c_{p,i}`

  `M_bar^c_{V,p} = sum_i M^c_{V,p,i} * y^c_{p,i}`

- `GE-G86-6` Generic hydraulic dependency family (Gani Eq. 19):

  `DeltaPi^c_p = Pi^c_{p-1} - Pi^c_p`

  `V^c_p = f(DeltaPi^c_p, C^c_{T,p}, plate geometry)`

  `L^c_p = f(C^c_{T,p}, plate geometry)`

  `L^c_{w,p} = f(C^c_{T,p}, V^c_p, plate geometry)`

  `V^c_{f,p} = f(V^c_p, L^c_p, plate geometry)`

  `E^c_{L,p} = f(C^c_{T,p}, DeltaPi^c_p, plate geometry)`

  `E^c_{V,p} = f(C^c_{T,p}, DeltaPi^c_p, plate geometry)`

- `GE-G86-7` Reflux-drum and reboiler component balances (Gani Eqs. 20–21):

  `dM^c_{RD,i}/dt = V^c_{N_p} * y^c_{N_p,i} - (L^c_0 + D^c) * x^c_{D,i}`

  `dM^c_{RB,i}/dt = L^c_1 * x^c_{1,i} - B^c * x^c_{B,i} - V^c_B * y^c_{B,i}`

- `GE-G86-8` Bubble-cap appendix hydraulic subset (Gani Appendix A.1–A.8):

  `h_ow = ((L^D_p) / (W * rho_{L,p} * 999.0))^(2/3)`

  `h^da_p = (0.003 / 12.0) * (g^L / (100.0 * A_D1))^2`

  `C_{T,p} = beta_p * (h_w + h_ow) * (A_p * rho_{L,p} / M_{L,p}) + (h^T_p + h^da_p + h^L_p - l) * (rho_{L,p} * A_D2 / M_{L,p})`

  If `h^L_{p-1} < h_bc`, the downcomer is not sealed and

  `h^T_p = (6.0 / (g * rho_{L,p} * rho_{V,p})) * (V^D_p * M_{V,p} / (3600.0 * A_D2))^2 * [0.7 * (A_D2 / A_D1)^2 + 1.2 + f_0 * (l_D / d_be)]`

  `U_f = F_1 * F_2 * (sigma_{L,p} / rho_{L,p})^(1/2)`

  `h^L_p = h^{bc}_p + h^{op}_p + h^{hu}_p`

  `h^{aL}_p = beta_p * (h_w + h_ow + Delta p / 2.0)`

  `Q'_p = 2.36 * (A_h / h_dc) * ((rho_{L,p} - rho_{V,p}) / rho_{V,p})^(1/2) * [(2 / (31 + R_s)) * (h^{os}_p)^(3/2) + (4 / (151 + R_s)) * (1 - R_s * h^{os}_p / h_sh)^(5/2)]`

  with `R_s = d_st / d_tb`.

**Gani first-slice boundary for this repo**
- Single-column, open-loop execution only.
- Bubble-cap appendix path is the frozen first hydraulic appendix slice.
- Controllers (Eqs. 22–24), multiple columns, start-up procedures, optional external wall heat-transfer procedures, alternate plate families, and warning-only appendix checks remain deferred.

## Risks / Trade-offs

- **Howard and Gani are not just stronger versions of the current stagewise model.**
  - Risk: implementation could silently reuse repo-specific reduced-order closures and only rename the class.
  - Mitigation: equation-fidelity tests must compare synthetic states against the frozen `GE-H70-*` and `GE-G86-*` forms.

- **Howard and Gani make different physical assumptions.**
  - Risk: implementation may incorrectly unify Howard's specified-pressure/holdup structure with Gani's explicit hydraulic subset.
  - Mitigation: keep separate classes and separate equation-bearing requirements.

- **Gani's paper is broader than the first implementation slice.**
  - Risk: the plan could accidentally promise controllers, start-up, multiple columns, and every appendix option.
  - Mitigation: freeze the bounded single-column open-loop bubble-cap slice explicitly and defer the rest.

- **Runtime seam mismatch could tempt an unnecessary connection-spec rewrite.**
  - Risk: contributors may widen connection semantics even though current runtime demand seams are already sufficient.
  - Mitigation: treat connection-spec changes as out of scope unless implementation evidence proves otherwise.

## Verification Strategy

- TDD should lead the new paper-faithful model work.
- Required verification commands:
  - `uv run pytest tests/unit_process/test_layer4_howard1970_distillation.py`
  - `uv run pytest tests/unit_process/test_layer4_gani1986_distillation.py`
  - `uv run pytest tests/unit_process/test_layer4_stagewise_distillation.py`
  - `uv run pytest tests/integration/test_paper_faithful_distillation_runtime.py`
  - `uv run python examples/dynamic_simulation_demos/paper_faithful_distillation_comparison.py`
  - `openspec validate --specs --strict --no-interactive`
- Expected evidence:
  - `Howard1970DistillationColumn` preserves the frozen Howard equation family rather than collapsing to the repo's stagewise reduced-order closure.
  - `Gani1986DistillationColumn` preserves the frozen Gani ODE, closure, and bubble-cap appendix family rather than collapsing to the repo's stagewise reduced-order closure.
  - `StagewiseDistillationColumn` remains present and continues to pass its own regression suite.
  - No `ShortcutDistillation` shim path is introduced.
  - Gameplay/start/build exposure remains unchanged.
  - Runtime outlet-demand behavior remains compatible with the existing connection contract.

## Open Questions

- None. The first-slice scope boundaries for Howard and Gani are now frozen tightly enough for implementation planning.

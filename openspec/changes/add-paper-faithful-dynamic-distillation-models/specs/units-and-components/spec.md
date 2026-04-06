## ADDED Requirements

### Requirement: Howard 1970 Comparison Model Preserves Published Plate-Balance Family
`Howard1970DistillationColumn` SHALL implement the Howard (1970) single-column dynamic plate-balance family with its published equilibrium, tray-efficiency, bubble-point, feed-plate, and constant-volume-holdup forms rather than collapsing the model into the repo's reduced-order stagewise closure.

#### Governing Equations
- `GE-H70-1` General component balance (Howard Eq. 5):

  `R_j * dx_{j,i}/dt = V_{j+1} * (y_{j+1,i} - x_{j,i}) + L_{j-1} * (x_{j-1,i} - x_{j,i}) - V_j * (y_{j,i} - x_{j,i})`

- `GE-H70-2` Equilibrium relation (Howard Eq. 6):

  `y^*_{j,i} = K_i(T_j, P_j) * x_{j,i}`

- `GE-H70-3` Vaporization efficiency (Howard Eq. 7):

  `E^o_{j,i} = y_{j,i} / y^*_{j,i}`

- `GE-H70-4` Murphree efficiency (Howard Eq. 8):

  `E^M_{j,i} = (y_{j,i} - y_{j-1,i}) / (y^*_{j,i} - y_{j-1,i})`

- `GE-H70-5` Liquid enthalpy and algebraic energy-balance family (Howard Eqs. 9 and 14):

  `h_j = sum_i x_{j,i} * f_i(T_j) + phi_M(x_{j,1} ... x_{j,NC})`

  `0 = V_{j+1} * ((H_{j+1} - h_j) - A_j) + L_{j-1} * ((h_{j-1} - h_j) - B_j) - V_j * ((H_j - h_j) - C_j) - Q_{Lj}`

- `GE-H70-6` Bubble-point closure and implicit temperature-derivative family (Howard Eqs. 15–21):

  `sum_i K_i(T_j) * x_{j,i} = 1`

  `dT_j/dx_{j,i} = -(dZ/dx_{j,i}) / (dZ/dT_j)`

  with

  `Z(T_j, x_j) = sum_{m=1}^{NC-1} [K_m(T_j) - K_c(T_j)] * x_{j,m} + K_c(T_j)`

  and the paper's Eq. (21) working expression used over the `NC - 1` independent components.

- `GE-H70-7` Feed-plate extension (Howard Eqs. 22–25):

  `R_j * dx_{j,i}/dt = V_{j+1} * (y_{j+1,i} - x_{j,i}) + L_{j-1} * (x_{j-1,i} - x_{j,i}) + F * (x_{F,i} - x_{j,i}) - V_j * (y_{j,i} - x_{j,i})`

  `dR_j/dt = V_{j+1} + L_{j-1} + F - V_j - L_j`

  `d(R_j * h_j)/dt = V_{j+1} * H_{j+1} + L_{j-1} * h_{j-1} + F * h_F - V_j * H_j - L_j * h_j + Q_{Lj}`

  `+ F * ((h_F - h_j) - D_j)`

- `GE-H70-8` Constant-volume-holdup closure (Howard Eqs. 26–30):

  `R_j = V_bar * v(x_j, T_j)`

  `v(x_j, T_j) = sum_i x_{j,i} * v_i(T_j)`

  `0 = V_{j+1} * (1 - F_j) + L_{j-1} * (1 - G_j) - V_j * (1 - K_j) - L_j`

  with `F_j`, `G_j`, and `K_j` preserved as the explicit coefficient family from Howard Eq. (30).

- Symbols and assumptions:
  - `j` = plate index, `i` = component index
  - `R_j` = plate liquid holdup
  - `x_{j,i}`, `y_{j,i}`, `y^*_{j,i}` = liquid, actual vapor, and equilibrium vapor compositions
  - `V_j`, `L_j` = vapor and liquid flow rates
  - `h_j`, `H_j` = liquid and vapor enthalpies
  - `Q_{Lj}` = plate heat-loss term
  - vapor holdup is neglected, liquid on each plate is well mixed, and vapor-liquid relation is established instantaneously as in the paper
  - this change freezes Howard's constant-volume-holdup executable slice; it does not require every alternative Howard specification family in the first implementation.

#### Scenario: Howard runtime behavior follows the published balance family
- **WHEN** implementation or tests evaluate `Howard1970DistillationColumn`
- **THEN** its dynamic plate behavior follows `GE-H70-1` through `GE-H70-8`
- **AND** the model does not replace those equations with the repo's existing reduced-order stagewise hydraulic and thermal closure family
- **AND** Howard's feed-plate and constant-volume-holdup forms remain explicit rather than implied by prose.

### Requirement: Gani 1986 Comparison Model Preserves Published Generalized Column Family
`Gani1986DistillationColumn` SHALL implement the Gani, Ruiz, Cameroni (1986) single-column open-loop generalized column family with explicit plate balances, algebraic thermodynamic/property closures, generic hydraulic dependencies, reflux-drum/reboiler balances, and bubble-cap appendix hydraulics rather than collapsing the model into the repo's reduced-order stagewise closure.

#### Governing Equations
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

- `GE-G86-7` Reflux-drum and reboiler balances (Gani Eqs. 20–21):

  `dM^c_{RD,i}/dt = V^c_{N_p} * y^c_{N_p,i} - (L^c_0 + D^c) * x^c_{D,i}`

  `dM^c_{RB,i}/dt = L^c_1 * x^c_{1,i} - B^c * x^c_{B,i} - V^c_B * y^c_{B,i}`

- `GE-G86-8` Bubble-cap hydraulic subset (Gani Appendix A.1–A.8):

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

- Symbols and assumptions:
  - `c` = column index, `p` = plate index, `i` = component index
  - `C^c_{p,i}`, `C^c_{T,p}`, `C^c_{E,p}` = component, total-holdup, and total-energy plate states
  - `x^c_{p,i}`, `y^c_{p,i}`, `y^{*c}_{p,i}` = liquid, actual vapor, and equilibrium vapor compositions
  - `Theta^c_p`, `Pi^c_p` = plate temperature and pressure
  - `V^c_p`, `L^c_p` = vapor and liquid plate flows
  - `ME^c_p` = Murphree efficiency in the paper notation
  - the paper assumptions of negligible vapor holdup, thermal equilibrium, and perfect mixing apply
  - this change freezes a single-column open-loop bubble-cap slice; controllers, multiple columns, start-up procedures, external wall heat-transfer procedures, and alternate plate families remain deferred.

#### Scenario: Gani runtime behavior follows the published generalized family
- **WHEN** implementation or tests evaluate `Gani1986DistillationColumn`
- **THEN** its dynamic plate and hydraulic behavior follows `GE-G86-1` through `GE-G86-8`
- **AND** the model does not replace those equations with the repo's existing reduced-order stagewise closure
- **AND** the first implementation slice stays within the explicit single-column open-loop bubble-cap boundary instead of silently claiming the paper's deferred controller, start-up, or multi-column modes.

### Requirement: Paper-Faithful Comparison Models Reuse The Existing Monolithic Runtime Boundary
`Howard1970DistillationColumn` and `Gani1986DistillationColumn` SHALL remain backend-only monolithic runtime units with explicit feed and product ownership, and SHALL NOT widen gameplay/start/build exposure in this change.

#### Scenario: Paper-faithful models coexist with the stagewise baseline without widening gameplay
- **WHEN** contributors inspect the runtime distillation surfaces after this change
- **THEN** `Howard1970DistillationColumn` and `Gani1986DistillationColumn` exist as explicit sibling runtime model classes alongside `StagewiseDistillationColumn`
- **AND** no gameplay/start/build contract is widened merely because the new classes exist
- **AND** the change does not introduce a shortcut compatibility model under a different name.

## MODIFIED Requirements

### Requirement: Distillation-Column Foundation Work Targets Dynamic Stagewise Behavior
This capability SHALL keep one monolithic `StagewiseDistillationColumn` as the repo's existing reduced-order dynamic distillation baseline, SHALL additionally allow monolithic `Howard1970DistillationColumn` and `Gani1986DistillationColumn` comparison models in this slice, and SHALL NOT define a lumped main model as the completion contract.

#### Scenario: Dynamic model boundary is monolithic and comparison-ready
- **WHEN** contributors inspect the runtime distillation-model contract for this change
- **THEN** `StagewiseDistillationColumn`, `Howard1970DistillationColumn`, and `Gani1986DistillationColumn` are explicit monolithic runtime model classes
- **AND** no lumped main model is the completion contract
- **AND** the paper-faithful models do not replace the existing stagewise baseline.

### Requirement: Distillation Runtime Semantics Are Stagewise-Only With No Shortcut Shim
This capability SHALL treat `StagewiseDistillationColumn` as the existing reduced-order runtime distillation baseline, SHALL additionally allow `Howard1970DistillationColumn` and `Gani1986DistillationColumn` as approved paper-faithful runtime comparison-model paths in this slice, and SHALL NOT reintroduce a `ShortcutDistillation` class, alias, or compatibility shim.

#### Scenario: Completion cannot rely on a shortcut compatibility path
- **WHEN** implementation or tests evaluate dynamic distillation behavior
- **THEN** completion may use runtime behavior from `StagewiseDistillationColumn`, `Howard1970DistillationColumn`, or `Gani1986DistillationColumn`
- **AND** no `ShortcutDistillation` runtime/shim pathway is required or preserved.

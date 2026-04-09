# Thermo Tray Distillation

## Purpose

This capability defines the thermo-backed actual-tray distillation-column runtime model (`ThermoTrayDistillationColumn`), including explicit actual-tray material balances, PR-backed thermodynamic closure, dynamic end-region modeling, startup-and-settle operation, and the v1 realism boundary.
## Requirements
### Requirement: Thermo Tray Distillation Is An Explicit Backend-Only Runtime Model
`ThermoTrayDistillationColumn` SHALL exist as an explicit backend-only monolithic runtime distillation model path and SHALL NOT widen gameplay, start/build exposure, or client-facing distillation contracts in this change.

#### Scenario: New model exists without widening public exposure
- **WHEN** contributors inspect the supported runtime distillation model family after this change
- **THEN** `ThermoTrayDistillationColumn` exists as a sibling runtime model class alongside `StagewiseDistillationColumn`, `Howard1970DistillationColumn`, and `Gani1986DistillationColumn`
- **AND** its existence does not by itself widen topology-only starts, public build lists, tutorial/client exposure, or controller-binding scope.

#### Scenario: Actual trays stay actual in v1
- **WHEN** a runtime configures `ThermoTrayDistillationColumn` with `n_trays = N`
- **THEN** the runtime model uses `N` explicit actual tray control volumes according to `GE-TTD-MAT-1` through `GE-TTD-MAT-6`
- **AND** v1 does not collapse those trays into an overall-efficiency equivalent-stage count
- **AND** Murphree tray efficiency remains deferred in this pack.

### Requirement: Actual-Tray Material And Reduced-Order Hydraulic Closure Are Explicit
`ThermoTrayDistillationColumn` SHALL evolve explicit actual-tray liquid component holdups under tray-by-tray material balances, feed flash splits, algebraic pressure profile, smooth reduced-order liquid downflow, and smooth supply-limited vapor traffic.

#### Governing Equations
- `GE-TTD-MAT-1` Tray liquid holdup and liquid composition for tray `j` and species `k`:

  `N^L_j = sum_k N_{j,k}`  `[mol]`

  `x_{j,k} = N_{j,k} / max(N^L_j, eps_N)`  `[-]`

- `GE-TTD-MAT-2` Feed flash split for feed `m` assigned to tray `j_m`:

  `(beta_F,m, x^F_{m,k}, y^F_{m,k}, h^L_F,m, h^V_F,m) = Flash_PR(T_F,m, P_F,m, z_F,m)`

- `GE-TTD-MAT-3` Algebraic tray pressure profile:

  `P_j = P_top + (j - 1) * DeltaP_tray`  `[Pa]`

- `GE-TTD-MAT-4` Smooth-plus operator used to avoid hard clipping in normal runtime closure:

  `sp(a) = 0.5 * (a + sqrt(a^2 + eps_sp^2))`

- `GE-TTD-MAT-5` Reduced-order liquid downflow law:

  `V^L_j = N^L_j * MW^L_j / rho^L_j`  `[m^3]`

  `h_j = V^L_j / A_act,j`  `[m]`

  `L_j = C_L,j * sp(h_j - h_weir,j)^(3/2)`  `[mol/s]`

- `GE-TTD-MAT-6` Smooth supply-limited vapor traffic:

  `DeltaP_avail,j = sp(DeltaP_tray - rho^L_j * g * h_j - DeltaP_dry,j)`  `[Pa]`

  `V_cap,j = C_V,j * sqrt(DeltaP_avail,j / max(rho^V_j, eps_rho))`  `[mol/s]`

  `V_sup,N = V_B + sum_{m: j_m = N} beta_F,m * F_m`  `[mol/s]`

  `V_sup,j = V_{j+1} + sum_{m: j_m = j} beta_F,m * F_m` for `j < N`  `[mol/s]`

  `smin(a, b) = 0.5 * (a + b - sqrt((a - b)^2 + eps_sm^2))`

  `V_j = smin(V_cap,j, V_sup,j)`  `[mol/s]`

- `GE-TTD-MAT-7` Tray component balance family for tray `j`, species `k`:

  `dN_{j,k}/dt = L_{j-1} * x_{j-1,k} + V_{j+1} * y_{j+1,k} + sum_{m: j_m = j} ((1 - beta_F,m) * F_m * x^F_{m,k} + beta_F,m * F_m * y^F_{m,k}) - L_j * x_{j,k} - V_j * y_{j,k}`  `[mol/s]`

- Symbols and assumptions:
  - `N_{j,k}` = tray `j` liquid component holdup of species `k` `[mol]`
  - `N^L_j` = total liquid holdup on tray `j` `[mol]`
  - `F_m`, `T_F,m`, `P_F,m`, `z_F,m` = feed `m` flow, temperature, pressure, and composition
  - `P_top` = top pressure anchor used to derive the tray pressure profile `[Pa]`
  - `DeltaP_tray` = per-tray pressure increment parameter `[Pa]`
  - `A_act,j`, `C_L,j`, `h_weir,j`, `C_V,j`, `DeltaP_dry,j` = named geometric/hydraulic parameters
  - `MW^L_j`, `rho^L_j`, `rho^V_j` = tray liquid molecular weight and liquid/vapor densities from the thermo closure
  - `g` = gravitational acceleration `[m/s^2]`
  - `eps_N`, `eps_sp`, `eps_sm`, `eps_rho` = small positive numerical guard constants
  - vapor accumulation on trays is neglected in v1; tray differential inventory is represented by liquid component holdup only
  - Murphree efficiency, flooding, weeping, entrainment, and rate-based transport remain explicitly deferred.

#### Scenario: Tray material dynamics use actual trays and feed flash splits
- **WHEN** one or more feeds are applied to `ThermoTrayDistillationColumn` and the unit is stepped over time
- **THEN** tray liquid component holdups evolve according to `GE-TTD-MAT-1` through `GE-TTD-MAT-7`
- **AND** feed contributions are applied at their assigned trays through explicit feed flash splits rather than post-hoc output adjustment
- **AND** tray-to-tray liquid and vapor traffic is not represented as a pair of fixed global flow constants.

#### Scenario: Normal runtime closure avoids broad hard clipping
- **WHEN** tray liquid level or vapor capacity approaches zero during normal runtime stepping
- **THEN** liquid and vapor traffic remain governed by the smooth closure family `GE-TTD-MAT-4` through `GE-TTD-MAT-6`
- **AND** the model does not rely on broad hard clipping of tray flow states as the primary stability mechanism.

### Requirement: Shared Equilibrium Tray Temperature Uses Dynamic Thermodynamic Closure
`ThermoTrayDistillationColumn` SHALL use one shared equilibrium tray temperature state per tray, derive tray thermodynamic properties dynamically from the Peng-Robinson-based thermo closure, and evolve that temperature from a semi-explicit tray energy balance rather than from constant heat capacity or feed-temperature proxy behavior.

#### Governing Equations
- `GE-TTD-TH-1` PR-backed tray thermo/property closure for tray `j`:

  `K_{j,k}, h^L_j, h^V_j, rho^L_j, rho^V_j, Cp^L_j = Thermo_PR(T_j, P_j, x_j)`

- `GE-TTD-TH-2` Equilibrium vapor composition from thermo-backed `K`-values:

  `y_{j,k} = K_{j,k} * x_{j,k} / sum_r (K_{j,r} * x_{j,r})`  `[-]`

- `GE-TTD-TH-3` Tray enthalpy-flow totals:

  `Hdot_in,j = L_{j-1} * h^L_{j-1} + V_{j+1} * h^V_{j+1} + sum_{m: j_m = j} ((1 - beta_F,m) * F_m * h^L_F,m + beta_F,m * F_m * h^V_F,m)`  `[W]`

  `Hdot_out,j = L_j * h^L_j + V_j * h^V_j`  `[W]`

- `GE-TTD-TH-4` Tray temperature-state equation:

  `dT_j/dt = (Hdot_in,j - Hdot_out,j + Q_j - h^L_j * sum_k dN_{j,k}/dt) / max(N^L_j * Cp^L_j, eps_C)`  `[K/s]`

- `GE-TTD-TH-5` Ordinary-tray heat input in v1:

  `Q_j = 0` for ordinary trays; condenser and reboiler duty act only in the end-region balances.

- Symbols and assumptions:
  - `T_j` = one shared equilibrium tray temperature for tray `j` `[K]`
  - `h^L_j`, `h^V_j` = liquid and vapor molar enthalpies from the thermo closure `[J/mol]`
  - `Cp^L_j` = dynamic liquid-phase molar heat capacity from the thermo closure `[J/mol/K]`
  - `Q_j` = tray heat input `[W]`
  - vapor thermal storage on trays is neglected in v1, but vapor enthalpy still enters the numerator through `Hdot_in,j` and `Hdot_out,j`
  - the v1 tray thermo closure is PR-only and does not claim azeotrope, LLE/VLLE, or pressure-swing fidelity outside the supported PR/VLE envelope.

#### Scenario: Tray temperature is thermodynamic and dynamic, not constant-Cp proxy behavior
- **WHEN** tray compositions, feed conditions, or reboiler/condenser duties change over multiple runtime steps
- **THEN** tray temperatures and vapor compositions follow `GE-TTD-TH-1` through `GE-TTD-TH-5`
- **AND** the denominator of the tray thermal-state equation uses dynamic thermo-backed `Cp^L_j` rather than a fixed constant heat capacity
- **AND** tray temperature is not copied from feed temperature or reconstructed from a proxy thermal field.

### Requirement: Condenser Drum And Reboiler Kettle Are Dynamic End Regions

`ThermoTrayDistillationColumn` SHALL model a liquid reflux drum under a total-condenser top closure and an equilibrium reboiler kettle under a thermo-backed boilup closure, with both end regions carrying their own dynamic component holdup and temperature states. The condenser drum SHALL use a shared realizability budget for distillate and reflux withdrawals, an explicit reflux-request boundary, and a dry-drum temperature guard.

#### Governing Equations

- `GE-TTD-END-1` Total-condenser drum composition (unchanged):

  `N^D = sum_k N^D_k`  `[mol]`

  `z^D_k = N^D_k / max(N^D, eps_N)`  `[-]`

- `GE-TTD-END-2` Reflux-drum component balance with shared realizability budget (revised):

  First, compute the shared drum withdrawal budget:

  `D_R_budget = max(0.0, N^D - N^D_min) / dt`  `[mol/s]`

  where `N^D_min` is a small positive holdup reserve (not a per-component floor).

  Then allocate distillate and reflux from the single budget:

  `D_realized = min(D_request, D_R_budget)`  `[mol/s]`

  `R_realized = min(R_request, D_R_budget - D_realized)`  `[mol/s]`

  The drum component balance becomes:

  `dN^D_k/dt = V_1 * y_{1,k} - D_realized * z^D_k - R_realized * z^D_k`  `[mol/s]`

  **Constraint:** `D_realized + R_realized <= D_R_budget` at all times. No per-component mass creation is used to mask the overdraft.

- `GE-TTD-END-2a` Reflux-request boundary (new):

  `R_request` SHALL be an explicit boundary input (`reflux_withdrawal_flow`) provided by the caller or controller. It SHALL NOT be back-computed from vapor flow and distillate flow.

  - Symbols:
    - `D_request` = external distillate withdrawal request `[mol/s]`
    - `R_request` = explicit reflux return request `[mol/s]` (boundary input)
    - `D_R_budget` = shared drum realizability budget `[mol/s]`
    - `D_realized` = realized distillate withdrawal `[mol/s]`
    - `R_realized` = realized reflux return `[mol/s]`
    - `N^D_min` = minimum drum holdup reserve `[mol]` (configurable, default small positive)
    - `dt` = integration timestep `[s]`

- `GE-TTD-END-3` Reflux-drum temperature-state equation with dry-drum guard (revised):

  `h^L_D, Cp^L_D, rho^L_D = Thermo_PR_liq(T_D, P_D, z_D)`

  Dry-drum guard:

  `if N^D < N^D_dry_guard:`

  &nbsp;&nbsp;&nbsp;&nbsp;`dT_D/dt = 0`  (freeze temperature; drum thermo state is physically undefined)

  `else:`

  &nbsp;&nbsp;&nbsp;&nbsp;`dT_D/dt = (V_1 * h^V_1 - D_realized * h^L_D - R_realized * h^L_D - Q_C - h^L_D * sum_k dN^D_k/dt) / max(N^D * Cp^L_D, eps_C)`  `[K/s]`

  - Symbols:
    - `N^D_dry_guard` = drum inventory threshold below which temperature integration is frozen `[mol]`. This is a positive constant larger than `eps_N` (suggested default: `1e-4 mol` or similar), representing the minimum holdup for a physically meaningful thermo evaluation.
    - All other symbols as previously defined.

- `GE-TTD-END-4` Reboiler-kettle equilibrium closure (unchanged):
  - See current live spec.

- `GE-TTD-END-5` Duty-limited and holdup-limited boilup (unchanged):
  - See current live spec.

- `GE-TTD-END-6` Reboiler-kettle component balance (unchanged):
  - See current live spec.

- `GE-TTD-END-7` Reboiler-kettle temperature-state equation (unchanged):
  - See current live spec.

#### Scenario: Drum withdrawals share a single realizability budget
- **WHEN** both distillate and reflux withdrawals are requested from the condenser drum
- **THEN** `D_realized` and `R_realized` are allocated from a single budget `D_R_budget = max(0.0, N^D - N^D_min) / dt` according to `GE-TTD-END-2`
- **AND** `D_realized + R_realized <= D_R_budget` at all times
- **AND** no per-component epsilon flooring is used to create mass that masks the overdraft in the drum balance.

#### Scenario: Reflux request is an explicit causal boundary input
- **WHEN** the caller or controller provides a reflux-request value via `reflux_withdrawal_flow`
- **THEN** `R_request` comes from that explicit boundary input according to `GE-TTD-END-2a`
- **AND** reflux is not back-computed as `vap_flow[0] - distillate_flow`.

#### Scenario: Dry-drum temperature does not integrate on empty inventory
- **WHEN** condenser-drum total holdup `N^D` falls below `N^D_dry_guard`
- **THEN** `dT_D/dt = 0` according to `GE-TTD-END-3`
- **AND** the drum temperature remains at its last valid value rather than integrating toward non-physical temperatures
- **AND** once drum holdup recovers above `N^D_dry_guard`, temperature integration resumes from the frozen value.

#### Scenario: End-region duties and product withdrawals stay dynamic and monolithic
- **WHEN** condenser duty, reboiler duty, reflux request, distillate withdrawal, or bottoms withdrawal changes over runtime stepping
- **THEN** condenser-drum and reboiler-kettle states evolve according to `GE-TTD-END-1` through `GE-TTD-END-7`
- **AND** distillate and reflux remain liquid withdrawals from the reflux drum under the total-condenser closure
- **AND** reboiler boilup is derived from the thermo-backed kettle closure rather than a fixed latent-heat constant.

### Requirement: Startup-And-Settle Uses The Runtime Model Itself
`ThermoTrayDistillationColumn` SHALL support startup-and-settle operation by evolving the same runtime governing equations from a numerically dry initial state, and v1 SHALL NOT require a separate steady-state solver as the completion contract.

#### Governing Equations
- `GE-TTD-ST-1` Numerically dry startup state for tray `j`, species `k`:

  `N_{j,k}(0) = eps_start * z^0_k`  `[mol]`

  `N^D_k(0) = eps_drum * z^0_k`  `[mol]`

  `N^B_k(0) = eps_kettle * z^0_k`  `[mol]`

  `T_j(0) = T^0_j`, `T_D(0) = T^0_D`, `T_B(0) = T^0_B`  `[K]`

  `P_j(0) = P_top,0 + (j - 1) * DeltaP_tray`  `[Pa]`

- `GE-TTD-ST-2` Default startup guesses in v1:

  `z^0 = z_first_feed` when a first feed exists, otherwise the constructor default composition

  `T^0_j = T_first_feed` for all trays when no stronger startup profile is supplied

- `GE-TTD-ST-3` Settle metric over the active runtime state:

  `r_settle(t) = max(max_{j,k} |dN_{j,k}/dt| / max(N_scale,j, eps_N), max_j |dT_j/dt| / max(T_scale,j, eps_T), |dT_D/dt| / max(T_scale,D, eps_T), |dT_B/dt| / max(T_scale,B, eps_T))`

- `GE-TTD-ST-4` Startup-and-settle completion criterion:

  the runtime is considered settled only when `r_settle(t) <= eps_settle` for a contiguous hold horizon `tau_settle` under fixed boundary conditions.

- Symbols and assumptions:
  - `eps_start`, `eps_drum`, `eps_kettle` = small positive startup holdup floors `[mol]`
  - `z^0_k` = startup composition used for epsilon inventories
  - `T_first_feed`, `z_first_feed` = the first configured feed's temperature and composition when available
  - `N_scale,*`, `T_scale,*`, `eps_T`, `eps_settle`, `tau_settle` = named startup/settle tolerances or scales
  - startup uses the same `GE-TTD-MAT-*`, `GE-TTD-TH-*`, and `GE-TTD-END-*` runtime equations; no separate steady-state solver is required by this pack.

#### Scenario: Startup mode uses numerically dry initial state rather than exact zero singularities
- **WHEN** a runtime starts `ThermoTrayDistillationColumn` from an empty or cold column condition
- **THEN** startup uses the numerically dry state and defaults defined by `GE-TTD-ST-1` and `GE-TTD-ST-2`
- **AND** v1 does not require exact zero tray holdup states that would make composition, thermo closure, or hydraulics singular.

#### Scenario: Settle mode reuses the runtime equations instead of a separate steady-state solver
- **WHEN** fixed boundary conditions are applied and a caller wants the column to reach operating conditions before a later disturbance
- **THEN** settle detection follows `GE-TTD-ST-3` and `GE-TTD-ST-4`
- **AND** the same runtime governing equations are reused to reach the settled condition
- **AND** this pack does not require a separate equation-oriented steady-state solve path.

### Requirement: Numerical Guards Stay Narrow And Flash-Protection Scoped

`ThermoTrayDistillationColumn` SHALL avoid broad hard clipping of internal temperature, pressure, and flow states during normal runtime stepping, and SHALL confine numerical guards to epsilon floors, composition normalization, shared realizability budgets, dry-drum thermo guards, and bounded flash-protection behavior when a raw thermo closure would otherwise fail.

#### Scenario: Normal runtime avoids broad hard clipping
- **WHEN** tray, drum, or kettle states remain inside the supported thermo/runtime envelope
- **THEN** the model evolves those states through `GE-TTD-MAT-*`, `GE-TTD-TH-*`, `GE-TTD-END-*`, and `GE-TTD-ST-*`
- **AND** it does not repeatedly hard-clamp temperature, pressure, or flow values as the primary stability mechanism.

#### Scenario: Shared drum realizability prevents per-component mass creation
- **WHEN** the condenser drum is nearly empty and both distillate and reflux are requested
- **THEN** the shared budget `D_R_budget` prevents total withdrawal from exceeding actual drum holdup
- **AND** the `step()` method does not restore negative per-component drum inventory via epsilon flooring.

#### Scenario: Flash-protection fallback is bounded and diagnostic
- **WHEN** a raw tray or end-region thermo closure would otherwise fail and stall the runtime step
- **THEN** runtime may apply bounded flash-protection fallback limited to the smallest guard needed to obtain a valid thermo evaluation
- **AND** the fallback does not silently redefine the governing equations as repeated broad clipping
- **AND** if even the bounded fallback cannot produce a valid thermo state, runtime fails explicitly rather than fabricating a stable trajectory.

### Requirement: V1 Thermodynamic Scope Is Explicitly Narrow
The v1 thermo-backed tray model SHALL promise only the repo's supported Peng-Robinson vapor-liquid-equilibrium envelope and SHALL NOT claim azeotrope, liquid-liquid, vapor-liquid-liquid, water-heavy nonideal, reactive-distillation, or cryogenic fidelity in this pack.

#### Scenario: V1 scope stays inside the supported PR/VLE envelope
- **WHEN** contributors inspect the realism boundary for `ThermoTrayDistillationColumn`
- **THEN** the promised thermo basis is the repo's existing Peng-Robinson-backed vapor-liquid-equilibrium closure family
- **AND** the pack does not claim broader thermodynamic realism than that supported envelope.


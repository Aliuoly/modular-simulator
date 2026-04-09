# Thermo Tray Distillation

## Purpose

This capability defines the thermo-backed actual-tray distillation-column runtime model path, with `ThermoTrayDistillationColumnTotalCondenser` as the active backend-only implementation and `ThermoTrayDistillationColumnPartialCondenser` reserved as a separate sibling boundary, including explicit actual-tray material balances, PR-backed thermodynamic closure, dynamic end-region modeling, startup-and-settle operation, and the v1 realism boundary.
## Requirements
### Requirement: Thermo Tray Distillation Is An Explicit Backend-Only Runtime Model
`ThermoTrayDistillationColumnTotalCondenser` SHALL be the explicit backend-only runtime implementation path in this change, and the partial-condenser path SHALL remain a separately named backend-only reserved capability/class boundary rather than being implied by total-condenser overload behavior. This change SHALL NOT widen gameplay, start/build exposure, or client-facing distillation contracts.

#### Scenario: Total and partial condenser semantics remain separate without widening public exposure
- **WHEN** contributors inspect the supported runtime distillation model family after this change
- **THEN** the total-condenser thermo-tray path is the implemented backend-only runtime contract for this pack
- **AND** the partial-condenser path is reserved as a distinct backend-only capability/class boundary rather than being inferred from total-condenser overload behavior
- **AND** the total-condenser path is the one that carries `GE-TTD-TC-*` behavior for headspace, overload, subcooling, and live end-pressure treatment
- **AND** gameplay, client, and public build/catalog exposure remain unchanged.

#### Scenario: Actual trays stay actual in v1
- **WHEN** a runtime configures `ThermoTrayDistillationColumnTotalCondenser` with `n_trays = N`
- **THEN** the runtime model uses `N` explicit actual tray control volumes according to `GE-TTD-MAT-1` through `GE-TTD-MAT-6`
- **AND** v1 does not collapse those trays into an overall-efficiency equivalent-stage count
- **AND** Murphree tray efficiency remains deferred in this pack.

### Requirement: Actual-Tray Material And Reduced-Order Hydraulic Closure Are Explicit
`ThermoTrayDistillationColumnTotalCondenser` SHALL evolve explicit actual-tray liquid component holdups under tray-by-tray material balances, feed flash splits, dynamic end-pressure interpolation, smooth reduced-order liquid downflow, and smooth supply-limited vapor traffic. The total-condenser top closure SHALL provide the live top vapor pressure anchor used by the tray pressure profile, and bottom pressure SHALL be derived from the live top pressure plus accepted column pressure-drop closure rather than from a fixed constant per-tray increment alone.

#### Governing Equations
- `GE-TTD-MAT-1` Tray liquid holdup and liquid composition for tray `j` and species `k`:

  `N^L_j = sum_k N_{j,k}`  `[mol]`

  `x_{j,k} = N_{j,k} / max(N^L_j, eps_N)`  `[-]`

- `GE-TTD-MAT-2` Feed flash split for feed `m` assigned to tray `j_m`:

  `(beta_F,m, x^F_{m,k}, y^F_{m,k}, h^L_F,m, h^V_F,m) = Flash_PR(T_F,m, P_F,m, z_F,m)`

- `GE-TTD-MAT-3a` Dynamic total-condenser top pressure anchor:

  `P_top = P_H`  `[Pa]`

  where `P_H` is the vapor-headspace pressure from `GE-TTD-TC-4` through `GE-TTD-TC-6`.

- `GE-TTD-MAT-3b` Column pressure-drop decomposition:

  `DeltaP_j = DeltaP_dry,j + DeltaP_head,j + DeltaP_res,j`  `[Pa]`

  `DeltaP_head,j = rho_eff,j * g * h_eff,j`  `[Pa]`

  `DeltaP_column = sum_{j=1..N} DeltaP_j + DeltaP_misc`  `[Pa]`

  `P_bottom = P_top + DeltaP_column`  `[Pa]`

- `GE-TTD-MAT-3c` End-pressure anchored tray pressure profile:

  `P_j = P_top + ((j - 1) / max(N - 1, 1)) * (P_bottom - P_top)`  `[Pa]`

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
  - `P_H` = condenser vapor-headspace pressure `[Pa]`
  - `DeltaP_dry,j` = tray dry pressure-drop term from accepted tray hydraulics `[Pa]`
  - `rho_eff,j`, `h_eff,j` = accepted effective froth/liquid density and retained liquid/froth height on tray `j`
  - `DeltaP_res,j` = accepted per-tray residual pressure-drop term only when tied to a named physical mechanism `[Pa]`
  - `DeltaP_misc` = accepted non-tray residual pressure-drop term for the column top/bottom attachment regions `[Pa]`
  - `P_top`, `P_bottom` = live end pressures, not constant constructor anchors
  - `P_j` = interpolated tray pressure used by the tray thermo closure `[Pa]`
  - `A_act,j`, `C_L,j`, `h_weir,j`, `C_V,j` = named geometric/hydraulic parameters
  - `MW^L_j`, `rho^L_j`, `rho^V_j` = tray liquid molecular weight and liquid/vapor densities from the thermo closure
  - `g` = gravitational acceleration `[m/s^2]`
  - `eps_N`, `eps_sp`, `eps_sm`, `eps_rho` = small positive numerical guard constants
  - `GE-TTD-MAT-3b` uses the well-accepted tray pressure-drop decomposition `dry drop + liquid/froth head`; exact accepted correlations for `DeltaP_dry,j` and `rho_eff,j * h_eff,j` are frozen in `design.md` and implemented/tested explicitly rather than improvised during apply.
  - vapor accumulation on trays remains neglected in this capability; only the total-condenser top headspace adds explicit vapor inventory.
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

#### Scenario: Tray pressure profile is tied to live top and bottom pressures
- **WHEN** top-headspace pressure, tray liquid holdup, vapor traffic, or bottom-region conditions change over runtime stepping
- **THEN** tray pressures follow `GE-TTD-MAT-3a` through `GE-TTD-MAT-3c`
- **AND** the pressure profile is not frozen to a constant constructor `P_top + (j - 1) * DeltaP_tray` relation.

#### Scenario: Column pressure drop uses accepted tray-hydraulics decomposition
- **WHEN** contributors inspect or verify how bottom pressure is derived from top pressure in the total-condenser thermo-tray model
- **THEN** the governing pressure-drop family is `GE-TTD-MAT-3b`
- **AND** the implementation uses accepted dry-tray and liquid/froth-head closure terms named in the design record rather than invented surrogate pressure laws.

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

`ThermoTrayDistillationColumnTotalCondenser` SHALL model a subcooled total-condenser top closure as an explicit vapor headspace plus liquid reflux-drum region, and SHALL retain the equilibrium reboiler kettle under a thermo-backed boilup closure. The total-condenser top closure SHALL expose `realized_condensed_flow` and `non_condensed_flow`, use dynamic vapor-headspace pressure, derive liquid outlet pressures from headspace pressure plus hydrostatic head, and keep reflux/distillate as liquid withdrawals from the drum inventory. The condenser drum SHALL also continue to use a shared realizability budget for distillate and reflux withdrawals, an explicit reflux-request boundary, and a dry-drum temperature guard.

#### Governing Equations

- `GE-TTD-TC-1` Drum liquid composition and liquid hold-up:

  `N^D = sum_k N^D_k`  `[mol]`

  `z^D_k = N^D_k / max(N^D, eps_N)`  `[-]`

- `GE-TTD-TC-2` Total-condenser realized condensation and non-condensed carryover:

  `V_top = V_1`  `[mol/s]`

  `V_cond,therm = max(0.0, Q_C,avail / max(h^V_top - h^L_D, eps_H))`  `[mol/s]`

  `V_cond,realized = min(V_top, V_cond,therm, V_cond,cap)`  `[mol/s]`

  `V_noncond = max(0.0, V_top - V_cond,realized)`  `[mol/s]`

  where `Q_C,avail = max(0.0, -Q_C)` under the repo sign convention that negative condenser duty removes heat.

- `GE-TTD-TC-3` Drum liquid component balance:

  `dN^D_k/dt = V_cond,realized * y_top,k - D_realized * z^D_k - R_realized * z^D_k + N_cond,interface,k`  `[mol/s]`

  with `D_realized` and `R_realized` still subject to the shared drum-withdrawal budget from `GE-TTD-END-2` / `GE-TTD-END-2a`.

- `GE-TTD-TC-4` Excess headspace gas component balance:

  `dn^X_k/dt = V_noncond * y_top,k - V_vent,k + n_blanket,k - N_cond,interface,k`  `[mol/s]`

- `GE-TTD-TC-5` Vapor-headspace excess-pressure and volume closure:

  `V_H = max(V_shell - V_LD, eps_V)`  `[m^3]`

  `P_X = n_X * Z_H * R * T_H / max(V_H, eps_V)`  `[Pa]`

  `n_X = sum_k n^X_k`  `[mol]`

- `GE-TTD-TC-6` Drum-pressure closure from PR bubble pressure plus excess headspace gas pressure:

  `P_bubble,PR = Flash_PR_Bubble_P(T_D, z_D)`  `[Pa]`

  `P_H = P_bubble,PR + P_X`  `[Pa]`

- `GE-TTD-TC-7` Subcooled total-condenser / drum liquid temperature balance:

  `dT_D/dt = (V_cond,realized * h^V_top - D_realized * h^L_D - R_realized * h^L_D - Q_C - h^L_D * sum_k dN^D_k/dt) / max(N^D * Cp^L_D, eps_C)`  `[K/s]`

  with `h^L_D = h^L(T_D, P_H, z_D)` allowed to represent a subcooled liquid state rather than being forced to bubble point.

- `GE-TTD-TC-8` Liquid outlet source pressures from headspace plus hydrostatic head:

  `P_distillate,src = P_H + rho^L_D * g * h_D,dist`  `[Pa]`

  `P_reflux,src = P_H + rho^L_D * g * h_D,reflux`  `[Pa]`

- `GE-TTD-TC-9` Optional blanket-gas and vent capability:

  `n_blanket,k = 0`, `V_vent,k = 0` when blanket/vent ports are not configured.

  When configured, blanket-gas addition and vent withdrawal enter only through `GE-TTD-TC-4`; pressure-control policy remains external to the unit.

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

#### Scenario: Total condenser can overload without silently becoming a partial condenser
- **WHEN** condenser duty is insufficient to fully condense the incoming top-tray vapor
- **THEN** `V_cond,realized` and `V_noncond` follow `GE-TTD-TC-2`
- **AND** non-condensed vapor accumulates or leaves through configured headspace boundaries according to `GE-TTD-TC-4` through `GE-TTD-TC-6`
- **AND** the unit remains under total-condenser topology semantics rather than silently switching to a partial-condenser contract.

#### Scenario: Condenser duty can produce subcooled drum liquid
- **WHEN** condenser duty removes more energy than the minimum needed to reach saturated liquid at the top pressure
- **THEN** drum liquid temperature and liquid enthalpy follow `GE-TTD-TC-7`
- **AND** the total-condenser outlet liquid is allowed to be subcooled rather than being pinned to bubble point.

#### Scenario: Liquid outlet pressures exceed headspace pressure by hydrostatic head
- **WHEN** the reflux drum contains liquid above the reflux or distillate outlet nozzle elevations
- **THEN** the liquid outlet source pressures follow `GE-TTD-TC-8`
- **AND** the top tray vapor still sees `P_H` as the downstream vapor-side pressure while the liquid outlets see `P_H` plus hydrostatic head.

#### Scenario: Blanket gas and vent are physical ports, not internal control policy
- **WHEN** a caller configures blanket-gas addition or vent withdrawal for the total-condenser headspace
- **THEN** those flows enter the headspace balances through `GE-TTD-TC-4` and `GE-TTD-TC-9`
- **AND** pressure-control logic such as `add blanket gas below setpoint` or `vent above setpoint` remains an external controller concern rather than an intrinsic unit law.

#### Scenario: End-region duties and product withdrawals stay dynamic and monolithic
- **WHEN** condenser duty, reboiler duty, reflux request, distillate withdrawal, or bottoms withdrawal changes over runtime stepping
- **THEN** condenser-drum and reboiler-kettle states evolve according to `GE-TTD-END-1` through `GE-TTD-END-7`
- **AND** distillate and reflux remain liquid withdrawals from the reflux drum under the total-condenser closure
- **AND** reboiler boilup is derived from the thermo-backed kettle closure rather than a fixed latent-heat constant.

### Requirement: Startup-And-Settle Uses The Runtime Model Itself
`ThermoTrayDistillationColumnTotalCondenser` SHALL support startup-and-settle operation by evolving the same runtime governing equations from a numerically dry initial state, and the runtime step path SHALL use the framework-owned integration seam rather than a private explicit-Euler override that bypasses configured solver options.

#### Governing Equations
- `GE-TTD-ST-1` Numerically dry startup state for tray `j`, drum liquid, excess headspace gas, and kettle regions:

  `N_{j,k}(0) = eps_start * z^0_k`  `[mol]`

  `N^D_k(0) = eps_drum * z^0_k`  `[mol]`

  `n^X_k(0) = eps_headspace * y^0_k`  `[mol]`

  `N^B_k(0) = eps_kettle * z^0_k`  `[mol]`

  `T_j(0) = T^0_j`, `T_D(0) = T^0_D`, `T_H(0) = T^0_H`, `T_B(0) = T^0_B`  `[K]`

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
  - `eps_headspace` = small positive startup vapor inventory for the condenser headspace `[mol]`
  - `z^0_k` = startup composition used for epsilon inventories
  - `y^0_k` = startup headspace vapor composition guess consistent with the accepted startup thermo closure
  - `T_first_feed`, `z_first_feed` = the first configured feed's temperature and composition when available
  - `N_scale,*`, `T_scale,*`, `eps_T`, `eps_settle`, `tau_settle` = named startup/settle tolerances or scales
  - startup uses the same `GE-TTD-MAT-*`, `GE-TTD-TH-*`, and `GE-TTD-END-*` runtime equations; no separate steady-state solver is required by this pack.
  - solver-method choice is runtime/framework-owned through the base process-model stepping contract; the thermo-tray total-condenser class may add bounded substep logic only if it still delegates actual integration through the accepted framework seam.

#### Scenario: Startup mode uses numerically dry initial state rather than exact zero singularities
- **WHEN** a runtime starts `ThermoTrayDistillationColumn` from an empty or cold column condition
- **THEN** startup uses the numerically dry state and defaults defined by `GE-TTD-ST-1` and `GE-TTD-ST-2`
- **AND** v1 does not require exact zero tray holdup states that would make composition, thermo closure, or hydraulics singular.

#### Scenario: Settle mode reuses the runtime equations instead of a separate steady-state solver
- **WHEN** fixed boundary conditions are applied and a caller wants the column to reach operating conditions before a later disturbance
- **THEN** settle detection follows `GE-TTD-ST-3` and `GE-TTD-ST-4`
- **AND** the same runtime governing equations are reused to reach the settled condition
- **AND** this pack does not require a separate equation-oriented steady-state solve path.

#### Scenario: Thermo tray total condenser honors the framework solver path
- **WHEN** the total-condenser thermo-tray model is attached to a `System` with configured solver options
- **THEN** runtime stepping uses the framework-owned integration seam according to the startup-and-settle contract
- **AND** the unit does not silently replace the configured solver with a private explicit-Euler-only path.

### Requirement: Partial-Condenser Thermo Tray Is A Separate Capability
`ThermoTrayDistillationColumnPartialCondenser` SHALL be specified as a separate backend-only capability/class boundary from the total-condenser thermo-tray path because its top-end topology, ports, and observable behavior differ materially from overload behavior in a total condenser.

#### Governing Equations
- `GE-TTD-PC-1` Partial condenser is a distinct top-closure family and SHALL NOT be inferred by setting `V_noncond > 0` in the total-condenser equations.

- Symbols and assumptions:
  - this change does not freeze the full partial-condenser governing equations or require the full partial-condenser runtime implementation yet
  - it freezes the separate capability/class boundary now so later work does not blur topology or semantics.

#### Scenario: Total-condenser overload does not satisfy the partial-condenser contract
- **WHEN** contributors inspect the total-condenser thermo-tray behavior under insufficient cooling
- **THEN** `GE-TTD-TC-*` defines overload/degraded total-condenser behavior
- **AND** `GE-TTD-PC-1` prevents that behavior from being treated as the partial-condenser capability by implication.

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

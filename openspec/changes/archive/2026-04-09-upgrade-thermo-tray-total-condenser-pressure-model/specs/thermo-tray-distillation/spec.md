## MODIFIED Requirements

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

  `DeltaP_avail,j = sp(DeltaP_j - DeltaP_head,j - DeltaP_dry,j)`  `[Pa]`

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
  - `GE-TTD-MAT-3b` uses the well-accepted tray pressure-drop decomposition `dry drop + liquid/froth head`; exact accepted correlations for `DeltaP_dry,j` and `rho_eff,j * h_eff,j` are frozen in design.md and implemented/tested explicitly rather than improvised during apply.
  - vapor accumulation on trays remains neglected in this capability; only the total-condenser top headspace adds explicit vapor inventory.

#### Scenario: Tray pressure profile is tied to live top and bottom pressures
- **WHEN** top-headspace pressure, tray liquid holdup, vapor traffic, or bottom-region conditions change over runtime stepping
- **THEN** tray pressures follow `GE-TTD-MAT-3a` through `GE-TTD-MAT-3c`
- **AND** the pressure profile is not frozen to a constant constructor `P_top + (j - 1) * DeltaP_tray` relation.

#### Scenario: Column pressure drop uses accepted tray-hydraulics decomposition
- **WHEN** contributors inspect or verify how bottom pressure is derived from top pressure in the total-condenser thermo-tray model
- **THEN** the governing pressure-drop family is `GE-TTD-MAT-3b`
- **AND** the implementation uses accepted dry-tray and liquid/froth-head closure terms named in the design record rather than invented surrogate pressure laws.

### Requirement: Condenser Drum And Reboiler Kettle Are Dynamic End Regions
`ThermoTrayDistillationColumnTotalCondenser` SHALL model a subcooled total-condenser top closure as an explicit vapor headspace plus liquid reflux-drum region, and SHALL retain the equilibrium reboiler kettle under a thermo-backed boilup closure. The total-condenser top closure SHALL expose `realized_condensed_flow` and `non_condensed_flow`, use dynamic vapor-headspace pressure, derive liquid outlet pressures from headspace pressure plus hydrostatic head, and keep reflux/distillate as liquid withdrawals from the drum inventory.

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

- Symbols and assumptions:
  - `n^X_k` = explicit excess headspace gas inventory of species `k` above the condensable equilibrium already implied by `P_bubble,PR` `[mol]`
  - `n_X`, `T_H`, `P_H`, `P_X`, `Z_H` = excess-gas total inventory, headspace temperature, total headspace pressure, excess-gas partial pressure, and headspace compressibility
  - `V_shell` = total top-region shell volume; `V_LD` = liquid drum volume; `V_H` = vapor headspace volume
  - `V_cond,cap` = accepted condenser-capacity limit when present; if no separate area/UA limit is modeled in this slice, it may be omitted and `V_cond,realized = min(V_top, V_cond,therm)`
  - `N_cond,interface,k` = duty-limited recondensation sink from excess headspace gas back to drum liquid; if not represented as a separately named term, the implementation must preserve the same mass and energy bookkeeping under an equivalent collapsed form documented in `design.md`
  - `n_blanket,k` = blanket-gas addition rate for species `k` `[mol/s]`
  - `V_vent,k` = vent withdrawal rate for species `k` `[mol/s]`
  - `h_D,dist`, `h_D,reflux` = hydrostatic nozzle submergence heights for the liquid outlets `[m]`
  - `Flash_PR_Bubble_P(...)` denotes the repo helper seam that obtains PR bubble pressure from the official `thermo` flash dependency at fixed drum liquid state (for example, `FlashVL.flash(T=T_D, VF=0, zs=z_D).P`)
  - `GE-TTD-TC-6` freezes the reduced-order PR-bubble-plus-excess-headspace-pressure closure for this pack; no alternate EOS/fugacity headspace closure is implied.
  - The total-condenser class remains the intended topology even when `V_noncond > 0`; incomplete condensation is treated as overload/degraded total-condenser behavior, not automatic partial-condenser mode switching.

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

### Requirement: Thermo Tray Distillation Is An Explicit Backend-Only Runtime Model
`ThermoTrayDistillationColumnTotalCondenser` SHALL be the explicit backend-only runtime implementation path in this change, and the partial-condenser path SHALL remain a separately named backend-only reserved capability/class boundary rather than being implied by total-condenser overload behavior. This change SHALL NOT widen gameplay, start/build exposure, or client-facing distillation contracts.

#### Scenario: Total and partial condenser semantics remain separate without widening public exposure
- **WHEN** contributors inspect the thermo-tray runtime family after this change
- **THEN** the total-condenser thermo-tray path is the implemented backend-only runtime contract for this pack
- **AND** the partial-condenser path is reserved as a distinct backend-only capability/class boundary rather than being inferred from total-condenser overload behavior
- **AND** the total-condenser path is the one that carries `GE-TTD-TC-*` behavior for headspace, overload, subcooling, and live end-pressure treatment
- **AND** gameplay, client, and public build/catalog exposure remain unchanged.

### Requirement: Startup-And-Settle Uses The Runtime Model Itself
`ThermoTrayDistillationColumnTotalCondenser` SHALL support startup-and-settle operation by evolving the same runtime governing equations from a numerically dry initial state, and the runtime step path SHALL use the framework-owned integration seam rather than a private explicit-Euler override that bypasses configured solver options.

#### Governing Equations
- `GE-TTD-ST-1` Numerically dry startup state for tray `j`, drum liquid, excess headspace gas, and kettle regions:

  `N_{j,k}(0) = eps_start * z^0_k`  `[mol]`

  `N^D_k(0) = eps_drum * z^0_k`  `[mol]`

  `n^X_k(0) = eps_headspace * y^0_k`  `[mol]`

  `N^B_k(0) = eps_kettle * z^0_k`  `[mol]`

  `T_j(0) = T^0_j`, `T_D(0) = T^0_D`, `T_H(0) = T^0_H`, `T_B(0) = T^0_B`  `[K]`

- `GE-TTD-ST-2` Runtime-settle contract:

  startup and settle reuse the same governing equation families `GE-TTD-MAT-*`, `GE-TTD-TH-*`, `GE-TTD-TC-*`, and `GE-TTD-END-*`; no separate explicit-Euler-only step path may redefine the accepted dynamics.

- Symbols and assumptions:
  - `eps_headspace` = small positive startup vapor inventory for the condenser headspace `[mol]`
  - `y^0_k` = startup headspace vapor composition guess consistent with the accepted startup thermo closure
  - solver-method choice is runtime/framework-owned through the base process-model stepping contract; the thermo-tray total-condenser class may add bounded substep logic only if it still delegates actual integration through the accepted framework seam.

#### Scenario: Thermo tray total condenser honors the framework solver path
- **WHEN** the total-condenser thermo-tray model is attached to a `System` with configured solver options
- **THEN** runtime stepping uses the framework-owned integration seam according to `GE-TTD-ST-2`
- **AND** the unit does not silently replace the configured solver with a private explicit-Euler-only path.

## ADDED Requirements

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

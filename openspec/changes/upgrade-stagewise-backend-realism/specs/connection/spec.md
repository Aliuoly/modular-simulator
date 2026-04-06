## MODIFIED Requirements

### Requirement: Distillation Actuation Uses Unit-Local Boundary Requests Without Controller-Binding Claims
Dynamic distillation-column actuation in this change SHALL use unit-local boundary requests for duty and internal return behavior together with explicit external material-routing seams and hydraulic-solved product-withdrawal demand, and SHALL NOT claim controller-bindable distillation control elements in this pack.

#### Governing Equations
- `GE-DA-1` Product-line driving pressure for connected product port `p`:

  `DeltaP_p = P_owner,p - P_dest,p - DeltaP_static,p - DeltaP_minor,p`  `[Pa]`

- `GE-DA-2` Hydraulic-solved outlet demand for connected product port `p`:

  `F_req,p = Psi_line(DeltaP_p, rho_p, mu_p, line_geometry_p)`  `[mol/s]`

  with `F_req,p = 0` when `DeltaP_p <= 0`.

- `GE-DA-3` Unit-local duty requests remain explicit boundary inputs:

  `u_top = condenser_duty_request_W`  `[W]`

  `u_bottom = reboiler_duty_request_W`  `[W]`

- Symbols and assumptions:
  - `P_owner,p` = runtime pressure at the owning unit product port `[Pa]`
  - `P_dest,p` = receiving node or downstream boundary pressure `[Pa]`
  - `DeltaP_static,p` = static-head contribution on the connected line `[Pa]`
  - `DeltaP_minor,p` = connection-line minor/friction loss contribution `[Pa]`
  - `rho_p`, `mu_p` = line-fluid density and viscosity used by the hydraulic solve
  - `Psi_line(...)` = existing connection-network hydraulic flow law family
  - This requirement freezes only that the demand is hydraulic-solved from network state; it does not require a distillation-specific actuator namespace or hidden internal valve law.

#### Scenario: Actuation surfaces remain runtime-owned and line namespace guidance stays general
- **WHEN** condenser duty requests, reboiler duty requests, reflux return, or product routing is actuated
- **THEN** runtime applies unit-local duty requests and hydraulic-solved product-line demand according to `GE-DA-1` through `GE-DA-3`
- **AND** `StagewiseDistillationColumn` uses unit-local boundary request fields for duty and internal return behavior plus explicit external material-routing seams
- **AND** product-line valves, pumps, and other line-owned hydraulic restrictions remain explicit runtime-owned topology rather than hidden distillation-specific valve/head knobs
- **AND** no distillation-specific controller binding contract is introduced by this requirement.

### Requirement: Product Withdrawals Are External Holdup Withdrawals
Distillate and bottoms routing SHALL be wired as external withdrawals from reflux-drum and bottoms-sump holdups, respectively, and any transient mismatch between hydraulic-solved demand and locally realizable withdrawal SHALL be resolved conservatively inside runtime behavior rather than by widening the public actuation surface.

#### Governing Equations
- `GE-PW-1` Owner-holdup withdrawal balance for owner region `o` and component `k`:

  `dM_o,k/dt = F_in,o,k - F_internal,out,o,k + F_internal,in,o,k - F_realized,o * z_o,k`  `[mol/s]`

- `GE-PW-2` Accepted-step realizability constraint:

  `M_o,k(t + dt_acc) >= 0` for every withdrawn owner component holdup.

- `GE-PW-3` Preferred mismatch-handling order:

  1. compute `F_req,o` from `GE-DA-1` and `GE-DA-2`
  2. attempt internal substep refinement down to bounded `dt_sub >= dt_min`
  3. if `GE-PW-2` still fails, set

     `F_realized,o = min(F_req,o, F_withdrawable,o(dt_sub))`

- `GE-PW-4` Withdrawable flow bound over the accepted internal step:

  `F_withdrawable,o(dt_sub) = M_withdrawable,o(dt_sub) / dt_sub`  `[mol/s]`

- Symbols and assumptions:
  - `M_o,k` = owner-region component holdup `[mol]`
  - `F_realized,o` = realized liquid withdrawal from owner region `o` `[mol/s]`
  - `z_o,k` = owner-region liquid withdrawal composition
  - `dt_acc` = accepted macro-step duration
  - `dt_sub` = internal refined substep used to test realizability
  - `dt_min` = bounded minimum internal refinement step
  - `M_withdrawable,o(dt_sub)` = physically withdrawable owner holdup over `dt_sub`
  - This requirement freezes the conservative runtime behavior order; it does not widen any public demand-override API.

#### Scenario: Product withdrawal connectivity is explicit
- **WHEN** product lines are connected in runtime
- **THEN** distillate and bottoms withdrawal follow the explicit external-holdup routing and owner-balance form defined by `GE-PW-1` through `GE-PW-4`
- **AND** distillate flow is withdrawn from reflux-drum holdup through explicit product-line seams
- **AND** bottoms flow is withdrawn from bottoms-sump holdup through explicit product-line seams
- **AND** both withdrawals remain liquid-phase and bounded by available owner holdup
- **AND** withdrawal behavior is not represented as implicit internal sink terms detached from external routing.

#### Scenario: Temporary demand-realizability mismatch stays conservative
- **WHEN** an accepted runtime step temporarily encounters hydraulic-solved product-line demand greater than the owning reflux drum or bottoms sump can physically realize for that step
- **THEN** runtime resolves the step according to `GE-PW-2` through `GE-PW-4`
- **AND** runtime does not overdraw owner holdup or create component moles to satisfy the line demand
- **AND** any safeguard remains internal runtime behavior rather than a new public demand override API.

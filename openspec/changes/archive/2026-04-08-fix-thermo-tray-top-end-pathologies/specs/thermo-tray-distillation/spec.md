# Thermo Tray Distillation — Top-End Bugfix Delta

## MODIFIED Requirements

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

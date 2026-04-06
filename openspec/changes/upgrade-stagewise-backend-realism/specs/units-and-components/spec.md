## ADDED Requirements

### Requirement: Internal Hydraulic States Drive Dynamic Stage Traffic
`StagewiseDistillationColumn` SHALL drive internal liquid and vapor traffic from runtime-owned hydraulic and holdup state rather than fixed global constant-molar-overflow traffic.

#### Governing Equations
- `GE-HYD-1` Stage liquid holdup:

  `M_liq,i = sum_k M_stage[i,k]`  `[mol]`

- `GE-HYD-2` Liquid volume and head:

  `V_liq,i = M_liq,i * MW_mix,i / rho_liq,i`  `[m^3]`

  `h_i = V_liq,i / A_active,i`  `[m]`

- `GE-HYD-3` Liquid downflow law:

  `L_i = C_L,i * max(h_i - h_weir,i, 0)^(3/2)`  `[mol/s]`

- `GE-HYD-4` Available vapor driving pressure:

  `DeltaP_i = P_{i+1} - P_i`  `[Pa]`

  `DeltaP_head,i = rho_liq,i * g * h_i`  `[Pa]`

  `DeltaP_avail,i = max(DeltaP_i - DeltaP_dry,i - DeltaP_head,i, 0)`  `[Pa]`

- `GE-HYD-5` Vapor upflow law:

  `V_i = C_V,i * sqrt(DeltaP_avail,i / max(rho_vap,i, eps))`  `[mol/s]`

- Symbols and assumptions:
  - `M_stage[i,k]` = stage `i` component holdup of species `k` `[mol]`
  - `MW_mix,i` = stage-liquid mixture molecular weight `[kg/mol]`
  - `rho_liq,i`, `rho_vap,i` = reduced-order liquid and vapor densities `[kg/m^3]`
  - `A_active,i` = active cross-sectional area implied by geometry `[m^2]`
  - `C_L,i`, `C_V,i`, `h_weir,i`, `DeltaP_dry,i` = named hydraulic closure parameters
  - `g` = gravitational acceleration `[m/s^2]`
  - flooding, weeping, entrainment, and other regime switching are explicitly out of scope for this slice.

#### Scenario: Internal stage traffic responds to runtime state
- **WHEN** feed, condenser duty, reboiler duty, reflux routing, or product withdrawal disturbs the column over multiple runtime steps
- **THEN** internal liquid and vapor traffic evolves according to `GE-HYD-1` through `GE-HYD-5`
- **AND** stage-to-stage coupling is not represented as a pair of fixed global liquid/vapor flow constants
- **AND** the current slice does not yet require flooding, weeping, or entrainment regime switching.

### Requirement: Reduced-Order Thermal State Evolution Is Thermodynamic Rather Than Proxy-Based
`StagewiseDistillationColumn` SHALL expose reduced-order thermal behavior derived from runtime thermal state and explicit thermodynamic closure rather than mixed-feed proxy temperatures.

#### Governing Equations
- `GE-TH-1` Stage liquid-region energy balance for stage `i`:

  `dU_i/dt = F_i * hF_i + L_{i-1} * hL_{i-1} + V_{i+1} * hV_{i+1} - L_i * hL_i - V_i * hV_i`  `[W]`

- `GE-TH-2` Reflux-drum energy balance:

  `dU_drum/dt = V_top * hV_top - Q_condenser + R_ext * hR_ext - D * hD - L_reflux * hL_drum`  `[W]`

- `GE-TH-3` Bottoms-sump energy balance:

  `dU_sump/dt = L_bottom * hL_bottom + Q_reboiler - V_boilup * hV_boilup - B * hB`  `[W]`

- `GE-TH-4` Temperature recovery from reduced-order thermodynamic state:

  `U_region = M_region * h_liq(T_region, x_region, P_region)`

  `T_region = h_liq^(-1)(U_region / M_region, x_region, P_region)`

- Symbols and assumptions:
  - `U_i`, `U_drum`, `U_sump` = internal energy states `[J]`
  - `h*` = reduced-order phase enthalpies `[J/mol]`
  - `Q_condenser`, `Q_reboiler` = applied duty terms `[W]`
  - `T_region` is recovered from thermodynamic state, not copied from feed temperature
  - the slice still does not require full rigorous MESH, superheat modeling, or pressure-swing distillation.

#### Scenario: Duty response changes reported thermal state
- **WHEN** condenser or reboiler duty changes over multiple runtime steps
- **THEN** reported top and bottom thermal state evolves according to `GE-TH-1` through `GE-TH-4`
- **AND** the thermal response is derived from runtime thermodynamic state rather than a feed-temperature passthrough.

## MODIFIED Requirements

### Requirement: Realism Boundary Is Frozen For This Slice
This change SHALL freeze a reduced-order but physically grounded dynamic column boundary with multicomponent stagewise inventories, dynamic internal hydraulic states, a dynamic condenser plus reflux-drum region, a dynamic sump plus thermosyphon-inspired reboiler region, stronger internal pressure treatment, and explicit reduced-order thermal-state evolution, while still deferring flooding/weeping and full rigorous MESH in this slice.

#### Governing Equations
- `GE-RB-1` Stage component balance family:

  `dM[i,k]/dt = F[i,k] + L_{i-1} * x[i-1,k] + V_{i+1} * y[i+1,k] - L_i * x[i,k] - V_i * y[i,k]`  `[mol/s]`

- `GE-RB-2` Internal hydraulic traffic is defined by `GE-HYD-1` through `GE-HYD-5`.
- `GE-RB-3` Thermal-state evolution is defined by `GE-TH-1` through `GE-TH-4`.
- `GE-RB-4` Top and bottom dynamic regions are defined by `GE-CR-1` through `GE-CR-4` and `GE-BR-1` through `GE-BR-4`.
- Symbols and assumptions:
  - `x[i,k]`, `y[i,k]` = liquid and vapor compositions on stage `i`
  - the slice remains multicomponent and reduced-order
  - flooding/weeping, full rigorous MESH, and rate-based mass transfer remain explicitly deferred.

#### Scenario: Initial closure is still reduced-order and multicomponent
- **WHEN** contributors inspect the model closure assumptions in this change
- **THEN** the frozen realism boundary is the reduced-order multicomponent balance family defined by `GE-RB-1` through `GE-RB-4`
- **AND** the contract does not require full rigorous MESH or rate-based mass-transfer fidelity in this change.

#### Scenario: Initial thermodynamic and hydraulic basis is explicit
- **WHEN** contributors inspect the stagewise-column closure assumptions in this slice
- **THEN** stage separation, hydraulic traffic, and thermal behavior are anchored by `GE-HYD-1` through `GE-HYD-5`, `GE-TH-1` through `GE-TH-4`, and `GE-K-1` through `GE-K-2`
- **AND** the contract no longer relies on fixed global internal liquid/vapor traffic, bare fixed-latent-heat `Q/λ` as the whole primary closure, or proxy temperatures.

### Requirement: Condenser/Reboiler Actuation Is Direct-Duty Service Coupled Into RHS
Condenser and reboiler actuation in this change SHALL be modeled as unit-local duty-request boundary fields coupled into dynamic top and bottom thermal-hydraulic regions of the monolithic column rather than as direct fixed-latent-heat shortcuts alone.

#### Governing Equations
- `GE-CR-1` Reflux-drum and condenser energy balance:

  `dU_drum/dt = V_top * hV_top - Q_condenser + R_ext * hR_ext - D * hD - L_reflux * hL_drum`  `[W]`

- `GE-CR-2` Top-region flash closure:

  `(beta_top, x_drum, y_top) = Flash_top(P_top, H_top, z_top)`

- `GE-CR-3` Bottoms-sump energy balance:

  `dU_sump/dt = L_bottom * hL_bottom + Q_reboiler - V_boilup * hV_boilup - B * hB`  `[W]`

- `GE-CR-4` Bottom-region vapor generation is derived from the bottom thermodynamic and circulation closure rather than a bare fixed-latent-heat `Q/λ` mapping.

- Symbols and assumptions:
  - `Flash_top(...)` = explicit top-region thermodynamic flash closure, preferably property-package-backed
  - `H_top`, `z_top` = top-region molar enthalpy and composition inputs to the flash closure
  - `Q_condenser`, `Q_reboiler` remain unit-local duty-request inputs `[W]`
  - the slice does not require separate placeable condenser/reboiler equipment.

#### Scenario: Utility actuation contract is explicit and runtime-owned
- **WHEN** condenser or reboiler actuation is configured
- **THEN** runtime behavior applies unit-local duty-request boundary fields into the monolithic stagewise RHS according to `GE-CR-1` through `GE-CR-4`
- **AND** realized duty response remains mass-conservative and inventory-aware
- **AND** the contract does not require controller-proof acceptance or separate placeable condenser/reboiler units in this change.

### Requirement: Bottoms-Side Reboiler Closure Remains Internal-Only And Monolithic
The monolithic `StagewiseDistillationColumn` SHALL keep stronger reboiler-circulation and boiling closure unit-internal while allowing a dynamic sump plus thermosyphon-inspired reboiler region in this slice.

#### Governing Equations
- `GE-BR-1` Natural-circulation driving pressure:

  `DeltaP_drive = max((rho_downcomer - rho_riser) * g * H_loop, 0)`  `[Pa]`

- `GE-BR-2` Internal circulation law:

  `L_circ = C_circ * sqrt(DeltaP_drive / max(rho_liq,sump, eps))`  `[mol/s]`

- `GE-BR-3` Reboiler outlet flash closure:

  `(beta_boilup, x_return, y_boilup) = Flash_bottom(P_bottom, h_circ,out, x_sump)`

- `GE-BR-4` Boilup from internal circulation:

  `V_boilup = beta_boilup * L_circ`  `[mol/s]`

- Symbols and assumptions:
  - `rho_downcomer`, `rho_riser` = effective liquid-rich and vaporizing-leg densities `[kg/m^3]`
  - `H_loop` = effective thermosyphon static-head height `[m]`
  - `C_circ` = named internal circulation coefficient
  - `Flash_bottom(...)` = explicit bottom-region thermodynamic flash closure, preferably property-package-backed
  - this is an internal-only thermosyphon-inspired heuristic; it does not create a public circulation port or line-level circulation edge.

#### Scenario: Hidden circulation custody does not widen the public surface
- **WHEN** contributors inspect the bottoms-side closure used by `StagewiseDistillationColumn`
- **THEN** the bottoms-side circulation and boilup behavior follows `GE-BR-1` through `GE-BR-4`
- **AND** the bottoms sump remains the owner of liquid holdup
- **AND** the change does not add a public circulation port, public circulation actuator, connection-layer circulation edge, or separate placeable reboiler unit.

#### Scenario: Stronger bottoms-side closure does not widen public model contracts
- **WHEN** contributors inspect the public/runtime-facing contract of `StagewiseDistillationColumn` after this slice
- **THEN** runtime actuation authority still stays on the existing duty-request and liquid-routing seams
- **AND** no public circulation-related boundary field, session-visible circulation contract, or new public circulation observability promise is required by `GE-BR-1` through `GE-BR-4`.

### Requirement: Geometry Semantics Are Explicit And Non-Misleading
`active_contact_height_m` SHALL control tray-equivalent stage count under fixed tray spacing, and `shell_diameter_m` SHALL control area, liquid holdup, hydraulic capacity, and pressure-response semantics.

#### Governing Equations
- `GE-GEO-1` Effective stage count:

  `N_stage = max(1, round(active_contact_height_m / tray_spacing_m))`

- `GE-GEO-2` Active column area:

  `A_active = pi * shell_diameter_m^2 / 4`  `[m^2]`

- `GE-GEO-3` Geometry enters the hydraulic and pressure closures through `A_active`, vapor-space volumes, and the holdup/head terms used in `GE-HYD-1` through `GE-HYD-5` and `GE-PR-1` through `GE-PR-3`.

- Symbols and assumptions:
  - `tray_spacing_m` = fixed tray-equivalent spacing used to map contact height to stage count
  - `shell_diameter_m` influences residence, holdup, hydraulic capacity, and pressure response, not thermodynamic selectivity directly.

#### Scenario: Geometry wording avoids false selectivity claims
- **WHEN** geometry fields are interpreted in this change contract
- **THEN** stage count and area semantics follow `GE-GEO-1` through `GE-GEO-3`
- **AND** shell width is not framed as directly changing thermodynamic selectivity.

### Requirement: Pressure Contract Guarantees Dynamic Column Pressure Minimum
The minimum guaranteed pressure contract SHALL keep one shared `column_pressure_pa` interface for existing runtime and connection surfaces while requiring that interface to be derived from a stronger internal dynamic pressure solution rather than a dead placeholder.

#### Governing Equations
- `GE-PR-1` Top vapor-space pressure:

  `P_top = Z_top * R * T_top * n_top_vap / V_top_vap`  `[Pa]`

- `GE-PR-2` Bottom vapor-space pressure:

  `P_bottom = Z_bottom * R * T_bottom * n_bottom_vap / V_bottom_vap`  `[Pa]`

- `GE-PR-3` Shared compatibility pressure for existing external interfaces:

  `column_pressure_pa = 0.5 * (P_top + P_bottom)`  `[Pa]`

- Symbols and assumptions:
  - `Z_top`, `Z_bottom` = reduced-order compressibility factors
  - `n_top_vap`, `n_bottom_vap` = top and bottom vapor holdup states `[mol]`
  - `V_top_vap`, `V_bottom_vap` = effective top and bottom vapor-space volumes `[m^3]`
  - `column_pressure_pa` is the shared compatibility interface for existing runtime/connection surfaces, not the full internal pressure field.

#### Scenario: Stagewise pressure implementations remain allowed and stronger pressure behavior stays interface-compatible
- **WHEN** a stronger implementation provides sectionwise or otherwise richer internal dynamic pressure treatment
- **THEN** the exposed shared compatibility pressure follows `GE-PR-1` through `GE-PR-3`
- **AND** the exposed shared pressure is derived from the internal dynamic pressure solution rather than a constant or dead placeholder
- **AND** this change text does not require a wider public pressure-actuation surface.

### Requirement: Reduced-Order Multicomponent Equilibrium Is Explicit
The live stagewise equilibrium closure in this slice SHALL remain multicomponent and explicit rather than relying on binary-only constant-alpha reasoning.

#### Governing Equations
- `GE-K-1` Reduced-order multicomponent `K`-value model for species `k` on region `i`:

  `ln(K[i,k]) = ln(K_ref[k]) + a[k] * (1/T_i - 1/T_ref) - b[k] * ln(P_i / P_ref)`

- `GE-K-2` Vapor composition from `K`-values:

  `y[i,k] = K[i,k] * x[i,k] / sum_j(K[i,j] * x[i,j])`

- Symbols and assumptions:
  - `K_ref[k]`, `a[k]`, `b[k]` = named reduced-order equilibrium parameters for species `k`
  - `x[i,k]`, `y[i,k]` = liquid and vapor mole fractions
  - this slice allows stronger property-package-backed flash closure in the top and bottom regions, but does not require tray-by-tray rigorous flash on every RHS evaluation.

#### Scenario: Multicomponent equilibrium stays explicit and reduced-order
- **WHEN** contributors inspect the live stagewise equilibrium story in this slice
- **THEN** the multicomponent equilibrium closure follows `GE-K-1` and `GE-K-2`
- **AND** the contract does not collapse the model back to binary-only constant-alpha reasoning.

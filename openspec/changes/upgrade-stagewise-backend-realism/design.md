## Context

- The archived backend gas-starter proof proved that `StagewiseDistillationColumn` can show multi-step causal response through current backend/runtime surfaces, but the live realism boundary still freezes fixed internal stage traffic, fixed-latent-heat `Q/λ` phase-change, proxy temperatures, and only a minimum shared pressure contract.
- The updated `openspec/config.yaml` now makes realism-first planning explicit: educational value is not an excuse for gross realism compromises, and any heuristic must be named and justified against realism, stability, and speed.
- Repo evidence shows connected-runtime outlet demand is already hydraulic-solved from the network and then applied back to processes through `apply_requested_outlet_through_flow_demand(...)`, but repo evidence also shows a real unit may still need a conservative realizability guard inside the accepted macro-step. `HoldingTank` already clips realized withdrawal by physically withdrawable holdup over the step.
- The user explicitly wants that demand-vs-realizability chain of thought preserved, including the possibility that internal macro-step refinement may be needed later if an accepted step is not physically realizable.
- The user also explicitly rejected arbitrary first-order lags unless they are strongly physically justified. The new closure should prefer dynamics that arise from differential mass, energy, and hydraulic relations.
- Relevant related work:
  - current runtime/subnetwork distillation requirements in `openspec/specs/connection/spec.md`
  - current live stagewise realism boundary in `openspec/specs/units-and-components/spec.md`
  - archived backend proof change `2026-03-28-backend-gas-starter-causal-proof`
  - control/dynamic distillation literature emphasizing pressure, holdup, condenser/reboiler inventory, and hydraulic coupling before higher-order fidelity work, including Skogestad (1997), Skogestad and Morari (1988), Häggblom (1991), and Montesi and Brambilla (1995).

## Goals / Non-Goals

**Goals:**
- Strengthen `StagewiseDistillationColumn` into a more credible backend substrate for future gameplay migration without widening gameplay or public client contracts now.
- Replace fixed internal liquid/vapor traffic with dynamic internal hydraulic states and state-driven stage traffic.
- Replace dead/proxy pressure and temperature behavior with stronger reduced-order internal pressure and thermal-state behavior.
- Keep condenser/reflux-drum and sump/reboiler behavior dynamic and mass-conservative while preserving a monolithic column boundary.
- Keep product withdrawals compatible with the existing connected-runtime hydraulic demand path.
- Preserve explicit realism boundaries: flooding/weeping, full rigorous MESH, and public controller/gameplay widening remain deferred.

**Non-Goals:**
- Rewriting gameplay starts, `SandboxSessionRuntime`, or public game/session APIs.
- Introducing separate placeable condenser, reflux drum, reboiler, or thermosyphon circulation units.
- Requiring flooding, weeping, entrainment, or other regime-switch behavior in this pack.
- Requiring full rigorous MESH, rate-based mass transfer, or full pressure-swing/superheat coverage.
- Treating line-owned restrictions as hidden distillation-specific internal valve knobs when they belong on explicit connection-network hydraulic components.

## Decisions

1. **The change stays backend/substrate-only and modifies the live distillation realism contract rather than reopening gameplay scope.**
   - Primary spec targets are `connection` and `units-and-components`.
   - The proof/example and tests are important implementation evidence, but the main contract shift is in the backend unit/runtime behavior.

2. **Internal stage traffic becomes hydraulic-state-driven, not constant-molar-overflow traffic.**
   - The new bounded model should evolve liquid and vapor movement from runtime-owned hydraulic state, holdup, geometry, and pressure relations rather than frozen global `stage_liquid_flow_mol_s` and `stage_vapor_flow_mol_s` constants.
   - Flooding/weeping stay deferred so the first stronger slice can focus on ordinary dynamic behavior rather than regime switching.
   - Smooth reduced-order hydraulic laws are preferred over hard switches to avoid unnecessary stiffness and numerical fragility.

3. **Pressure remains interface-compatible but becomes internally stronger than a dead shared placeholder.**
   - The minimum shared `column_pressure_pa` interface stays available for current runtime and connection surfaces.
   - Internally, the stronger model should use more natural dynamic pressure behavior than `d_pressure = 0.0`, with at least top/bottom or sectionwise pressure semantics if that is what the implementation needs.
   - The change should not widen a public pressure-actuation surface beyond the already frozen runtime seams.

4. **Thermal behavior becomes reduced-order thermodynamic behavior, not feed-temperature proxy behavior.**
   - Reported temperatures and duty response should arise from reduced-order thermodynamic/enthalpy state rather than mixed-feed proxy temperatures.
   - Existing `PropertyPackage` seams are the preferred basis when stronger thermodynamic closure is needed.
   - The contract still does not require full rigorous MESH or rate-based thermal transport in this slice.

5. **The top and bottom closures become stronger dynamic regions without splitting the monolithic unit.**
   - Top side: model a dynamic condenser plus reflux-drum region.
   - Bottom side: model a dynamic sump plus thermosyphon-inspired reboiler region.
   - The bottom closure may still use a bounded heuristic, but it must be named, justified, mass-conservative, and more physically grounded than the old bare `Q/λ` primary story.
   - No public circulation seam, no public circulation actuator, and no separate reboiler equipment are introduced.

6. **Withdrawals stay network-driven first, with local realizability only as a conservative physical safeguard.**
   - Connected-runtime hydraulic line flow remains the source of requested outlet through-flow demand.
   - `StagewiseDistillationColumn` should gain the same outlet-demand callback seam used by other dynamic units so connected-runtime product routing remains explicit and authoritative.
   - Hidden distillation-specific valve/head limits are rejected as the main explanation when those limits really belong in line/network hydraulics.
   - Local process-side safeguarding is still allowed where necessary to preserve mass conservation, owner holdup, and accepted-step realizability.

7. **The demand-vs-realizability mismatch must be recorded explicitly rather than hand-waved away.**
   - If an accepted runtime step can temporarily request more withdrawal than the owner holdup can physically realize, the runtime must resolve that step conservatively.
   - Acceptable first-slice handling may include conservative realized-flow limiting and/or internal step refinement, as long as:
     - no component moles are created,
     - no owner holdup is overdrawn,
     - and no new public override API is introduced.
   - The exact first implementation choice is left to apply-time engineering, but the design pack preserves the concern so it is not lost.

8. **Reduced-order multicomponent equilibrium remains acceptable, but it must no longer hide behind binary-only constant-alpha thinking.**
   - A multicomponent reduced-order equilibrium closure is still acceptable in this pack.
   - It may use componentwise reduced-order equilibrium factors and/or stronger property-package-backed thermodynamic closure.
   - Full tray efficiencies, Murphree non-ideality, and rate-based transport remain deferred until pressure, hydraulics, thermal behavior, and withdrawal compatibility are stronger.

9. **Rejected alternatives that would make the backend feel fake or create the wrong seam**
   - Keep fixed global internal liquid/vapor flow constants as the live stagewise traffic story.
   - Keep bare fixed-latent-heat `Q/λ` as the primary condenser/reboiler closure.
   - Keep proxy temperatures as the reported thermal behavior.
   - Hide line-owned hydraulic restrictions inside distillation-specific internal valve/head semantics.
   - Jump immediately to flooding/weeping or full rigorous MESH before the stronger baseline substrate is in place.

## Chosen Reduced-Order Model

This change freezes one concrete reduced-order path so implementation does not invent its own physics.

### Differential states

- Existing conserved liquid-holdup states remain the primary material states:
  - `stage_component_moles[i, k]`
  - `reflux_drum_component_moles[k]`
  - `bottoms_sump_component_moles[k]`
- Add reduced-order energy states:
  - `stage_internal_energy_J[i]`
  - `reflux_drum_internal_energy_J`
  - `bottoms_sump_internal_energy_J`
- Add vapor-space pressure-driving states instead of artificial flow-lag states:
  - `top_vapor_holdup_mol`
  - `bottom_vapor_holdup_mol`

These are the hydraulic/thermal dynamic states for this slice. The model does **not** add arbitrary first-order `L_i` or `V_i` lag states.

### Algebraic states and closures

- Per-stage liquid composition:
  - `x[i, k] = stage_component_moles[i, k] / sum_k stage_component_moles[i, k]`
- Per-stage liquid temperature from reduced-order energy closure:
  - solve `U_i = n_i * Cp_mix_liq(T_i, x_i, P_i) * (T_i - T_ref)` with a bounded reduced-order liquid `Cp` model
- Top and bottom pressures from vapor holdup states:
  - `P_top = Z_top * R * T_top * top_vapor_holdup_mol / V_top_vapor`
  - `P_bottom = Z_bottom * R * T_bottom * bottom_vapor_holdup_mol / V_bottom_vapor`
  - `column_pressure_pa` remains the minimum shared external interface and is derived from the stronger internal pressure solution rather than solved as a dead standalone state
- Internal tray/section pressures may be interpolated or otherwise derived from `P_top`, `P_bottom`, and local pressure-drop closure, as long as the implementation stays smooth and consistent.

### Internal liquid-flow law

Liquid downflow is holdup/head-driven and uses a smooth weir/downcomer-style closure:

- `h_i = V_liq_i / A_active_i`
- `V_liq_i = M_liq_i * MW_mix_i / rho_liq_i`
- `L_i = C_L_i * max(h_i - h_weir_i, 0)^(3/2)`

where:
- `M_liq_i = sum_k stage_component_moles[i, k]`
- `rho_liq_i` comes from the reduced-order thermodynamic closure for the stage liquid
- `C_L_i` and `h_weir_i` are named hydraulic parameters, not hidden tuning magic.

This gives naturally arising liquid-flow dynamics from holdup and density without adding arbitrary liquid-flow lags.

### Internal vapor-flow law

Vapor upflow is pressure-drop-driven and responds to liquid loading:

- `DeltaP_i = P_{i+1} - P_i`
- `DeltaP_head_i = rho_liq_i * g * h_i`
- `DeltaP_available_i = max(DeltaP_i - DeltaP_dry_i - DeltaP_head_i, 0)`
- `V_i = C_V_i * sqrt(DeltaP_available_i / max(rho_vap_i, eps))`

where:
- `DeltaP_dry_i` is the reduced-order dry tray/section loss term
- `rho_vap_i` comes from the reduced-order vapor state
- `C_V_i` is a named hydraulic capacity coefficient.

Flooding/weeping logic is **not** included in this slice. The flow laws must stay smooth near zero to avoid unnecessary stiffness and solver chatter.

### Material balances

For stage `i` and component `k`:

`dM[i,k]/dt = F[i,k] + L[i-1] * x[i-1,k] + V[i+1] * y[i+1,k] - L[i] * x[i,k] - V[i] * y[i,k]`

with the top-stage, reflux-drum, bottom-stage, and sump/reboiler boundary terms handled explicitly rather than by global fixed traffic.

### Energy balances

For each stage liquid region:

`dU[i]/dt = F_i * hF_i + L[i-1] * hL[i-1] + V[i+1] * hV[i+1] - L[i] * hL[i] - V[i] * hV[i]`

For the reflux drum / condenser region:

`dU_drum/dt = V_top * hV_top - Q_condenser + R_ext * hR_ext - D * hD - L_reflux * hL_drum`

For the bottoms sump / reboiler region:

`dU_sump/dt = L_bottom * hL_bottom + Q_reboiler - V_boilup * hV_boilup - B * hB`

These are reduced-order balances; the slice still does not require full rigorous MESH.

### Multicomponent equilibrium closure

The live stagewise equilibrium story for this slice is:

- internal trays/stages use a reduced-order multicomponent `K`-value closure with weak pressure and temperature dependence:
  - `ln(K[i,k]) = ln(K_ref[k]) + a[k] * (1/T_i - 1/T_ref) - b[k] * ln(P_i / P_ref)`
  - `y[i,k] = K[i,k] * x[i,k] / sum_j(K[i,j] * x[i,j])`
- top condenser/reflux-drum and bottom sump/reboiler regions may use the repo `PropertyPackage` flash path directly because there are only a few such regions and the added cost is justified there.

This keeps the tray-by-tray closure multicomponent and pressure/temperature-sensitive without requiring a full property-package flash on every tray during every RHS evaluation.

### Top closure: dynamic condenser plus reflux-drum region

The top is modeled as a dynamic condenser plus reflux-drum region, not as a dead duty-to-condensation map:

- incoming top vapor updates `top_vapor_holdup_mol`
- condenser duty removes energy from the top region
- liquid holdup and energy remain owned by `reflux_drum_component_moles` and `reflux_drum_internal_energy_J`
- top-region phase split may use `flash_ph(P_top, H_top, z_top)` or an equivalent explicit thermodynamic closure
- distillate and reflux are withdrawals from the liquid phase only.

### Bottom closure: dynamic sump plus thermosyphon-inspired reboiler region

The bottom is **not** treated as a generic detached flash drum. The chosen bounded story is a dynamic sump plus thermosyphon-inspired reboiler region:

- driving pressure for internal circulation comes from density difference and static head:
  - `DeltaP_drive = max((rho_downcomer - rho_riser) * g * H_loop, 0)`
- internal circulation follows a reduced-order hydraulic law:
  - `L_circ = C_circ * sqrt(DeltaP_drive / max(rho_liq_sump, eps))`
- duty raises the circulating-liquid enthalpy
- the reboiler outlet vapor fraction is recovered from explicit thermodynamic closure, preferably `flash_ph(P_bottom, h_circ_out, x_sump)`
- boilup is then:
  - `V_boilup = beta_boilup * L_circ`

This keeps the reboiler unit-internal, mass-conservative, and more physically grounded than the old bare `Q/λ` primary story while avoiding a new public circulation seam.

### Demand vs realizability handling order

The preferred handling order for withdrawal mismatch is frozen here so implementation does not guess:

1. The network hydraulic solve computes connected product-line through-flow demand.
2. `StagewiseDistillationColumn` receives that demand through the existing outlet-demand callback seam.
3. If the requested withdrawal would violate owner holdup or accepted-step realizability, runtime first attempts internal substep refinement down to a bounded minimum internal step.
4. Only if the step is still not physically realizable does runtime conservatively cap realized withdrawal.

The model must never create component moles, overdraw owner holdup, or fake a satisfied line flow when the local state cannot realize it.

## Stability / Speed Expectations

- The main added cost drivers are:
  - per-stage energy states,
  - top and bottom vapor-holdup pressure states,
  - smooth hydraulic flow closures,
  - top/bottom thermodynamic flash work.
- The pack deliberately avoids two major cost multipliers in this slice:
  - flooding/weeping regime switching,
  - full property-package flash on every tray during every RHS evaluation.
- Expected speed trade-off:
  - more expensive than the current fixed-flow and `Q/λ` slice,
  - materially cheaper and less stiff than a full rigorous MESH or regime-switch hydraulic model.
- Expected stiffness trade-off:
  - pressure and hydraulic states will add fast modes,
  - but smooth closures and limited flash use should keep the model tractable under the current `solve_ivp(..., method="LSODA")` substrate.

## Risks / Trade-offs

- **Hydraulic and pressure states will increase stiffness and solve cost.**
  - Mitigation: keep the first stronger slice smooth and reduced-order; defer flooding/weeping and hard regime switching.
- **Thermodynamic closure can increase compute cost.**
  - Mitigation: reuse the repo’s existing property-package seam and keep the contract reduced-order rather than full rigorous MESH.
- **Network-demand vs local-realizability mismatch may still appear in transients.**
  - Mitigation: keep mass-conservative local safeguarding explicit in the design and test it directly.
- **The previous closed `9tr.5.2` work froze a more limited internal-only reboiler story.**
  - Mitigation: treat this change as a stronger follow-on boundary rather than silently reusing the old realism claim.
- **Observability may need to expand to prove the stronger pressure/hydraulic/thermal claims.**
  - Mitigation: treat proof/example updates and runtime-owned observability evidence as part of the implementation waves.

## Verification Strategy

- TDD should lead the realism upgrade.
- Required verification commands:
  - `uv run pytest tests/unit_process/test_layer4_stagewise_distillation.py`
  - `uv run pytest tests/integration/test_dynamic_process_network_workflow.py -k "stagewise or distillation or withdrawal"`
  - `uv run pytest tests/integration/test_backend_gas_starter_causal_proof.py`
  - `uv run python examples/dynamic_simulation_demos/backend_gas_starter_causal_proof.py`
  - `openspec validate --specs --strict --no-interactive`
- Expected evidence:
  - internal stage traffic changes dynamically with runtime state rather than fixed global liquid/vapor constants,
  - pressure and thermal outputs evolve from stronger internal state rather than dead/proxy placeholders,
  - condenser and reboiler behavior is mass-conservative and no longer rests on bare fixed-latent-heat `Q/λ` as the whole closure,
  - connected-runtime withdrawal demand remains hydraulic-solved and explicit while realized withdrawal stays conservative and holdup-safe,
  - gameplay, Godot, and public controller/actuation contracts remain unchanged,
  - flooding/weeping remain explicitly deferred.

## Open Questions

- None. Any first-slice choice between conservative realized-flow limiting and internal step refinement stays within the bounded design above and is not a planning blocker.

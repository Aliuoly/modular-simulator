## Context

- The approved target for this change is a **monolithic `StagewiseDistillationColumn`** with explicit expanded actuation topology, not generic plant-ready wording.
- Repo patterns already support this direction:
  - Differential/process-model units exist (`CSTR`, `PFR`, `FlashDrum`) and multi-port unit composition patterns exist (`HeatExchanger`, `FlashDrum`).
  - Runtime/subsystem/network composition already supports bound process stepping and should remain the foundation path.
- `place_shortcut_distillation_column` already exists as the identity/gating anchor and must remain hidden/rejected on current topology-only starts.
- The live repository no longer preserves a `ShortcutDistillation` runtime/shim path for this scope; stagewise behavior is the only dynamic distillation path.

## Goals

- Freeze the dynamic model boundary as:
  - multicomponent, stage-by-stage component balances as live RHS
  - multi-feed inputs with configurable stage assignment (feed height/stage)
  - two-product behavior with duty-limited condenser surrogate + reflux drum and partial-equilibrium kettle reboiler + bottoms sump
  - material-balance-first dynamic slice with constant molar overflow first closure.
- Freeze the monolithic topology seams on `StagewiseDistillationColumn`:
  - reflux liquid outlet plus reflux-return inlet
  - distillate and bottoms as external withdrawals from reflux-drum/bottoms-sump holdups
  - condenser and reboiler as direct-duty services coupled into the RHS.
- Freeze material-custody semantics on those seams:
  - reflux return and product withdrawals remain liquid-phase and holdup-bounded
  - no runtime seam may bypass reflux-drum or bottoms-sump inventory ownership.
- Freeze the first-pass utility surrogate:
  - condenser and reboiler direct-duty services map duty to internal condensation/boilup through a named fixed-latent-heat `Q/λ` surrogate under the constant-molar-overflow slice
  - surrogate flows remain bounded by available vapor/liquid inventory and do not create or destroy component moles.
- Freeze runtime knob semantics:
  - `reflux_ratio` and `boilup_ratio` are initialization/reference/derived-observable fields only
  - live runtime actuation uses explicit unit-local boundary request fields plus external material-routing seams instead of ratio knobs.
- Freeze geometry semantics:
  - `active_contact_height_m` controls tray-equivalent stage count under fixed tray spacing
- `shell_diameter_m` controls area/holdup/capacity effects through an area-scaled proxy heuristic
  - width must not be framed as directly changing thermodynamic selectivity.
- Freeze pressure contract:
  - minimum guaranteed contract is one shared dynamic `column_pressure_pa` used by all stages and ports
  - wording allows a more natural stagewise dynamic pressure treatment if implemented.
- Freeze explicit unit-local boundary request seams plus external material-routing seams, and runtime observability needed for future control work without adding controller-state hacks.

## Non-Goals

- Do not prove closed-loop control in this change (deferred to `ModularSimulator-9tr.6`).
- Do not introduce any `ShortcutDistillation` compatibility class, alias, or shim.
- Do not widen current public gameplay starts/build lists.
- Do not broaden `_install_unit()` invalid-config translation beyond the existing boundary.
- Do not claim rigorous full MESH energy fidelity in this slice.
- Do not split the dynamic implementation into separately placeable condenser/reboiler/tower units in this pack.

## Decisions

1. **Pivot in place, no new change pack.**
   - Keep `honest-shortcut-distillation-sandbox-ready` and rewrite artifacts to the approved dynamic scope.

2. **Dynamic closure is stagewise multicomponent VLE, not shortcut algebra.**
   - Live dynamic RHS must use stage-by-stage component balances with a named stagewise VLE closure.
   - If constant relative volatility is used first, freeze it as a multicomponent alpha vector / LK-referenced set.
   - Non-key species remain explicit in inventories, feeds, and products.
   - Fenske/Underwood/Gilliland/Hengstebeck-Geddes may support initialization/reference but are not the dynamic closure contract.

3. **Implementation shape is one monolithic stagewise column with no shortcut shim.**
   - Keep one ProcessModel-style `StagewiseDistillationColumn` unit as the distillation runtime path.
   - Preserve legacy gameplay gating identity via `place_shortcut_distillation_column` item id only.
   - Reuse existing multi-port/differential unit patterns (HeatExchanger/FlashDrum/CSTR/PFR) rather than replacing shortcut internals.

4. **Actuation contract is explicit and monolith-local.**
   - Control interaction seams include unit-local boundary seam fields on `StagewiseDistillationColumn` (including condenser/reboiler duty-request fields plus reflux/withdrawal boundary fields) and external product routing seams from drum/sump holdups.
   - Material-line actuation remains repo-native and namespaced (`actuator/valve/<id>`, `actuator/pump/<id>`, `actuator/heat/<id>`) as the general platform contract; distillation-specific controller binding to that namespace is deferred.
   - No controller-bindable process-state control elements are introduced.

5. **Ratio fields are non-actuating in runtime.**
   - `reflux_ratio` and `boilup_ratio` are initialization/reference/derived-observable only.
   - If exposed, ratio values are derived from actual runtime flows.
   - Runtime actuation authority belongs to explicit unit-local boundary request fields plus external material-routing seams.

6. **Observability contract is substrate runtime state.**
   - `observables.process_state_values` must expose selected stage compositions, product compositions for all active species, reflux-drum holdup, bottoms-sump holdup, actual flows, each feed’s actual flow/composition and assigned stage, and shared dynamic `column_pressure_pa`.
   - When exposed by runtime composition, observability also includes public/runtime geometry values, duty-service readouts, and seam state readouts needed to inspect reflux-return and external withdrawal behavior.

7. **Gameplay honesty boundary remains unchanged in this change.**
   - Keep current topology-only starts and supported-build lists unchanged.
   - Keep hide/reject behavior for `place_shortcut_distillation_column`.

## Risks

- **Model complexity risk:** stagewise multicomponent dynamics can drift from conservation if state/flow bookkeeping is inconsistent.
  - Mitigation: Wave 1 red tests prioritize transients + conservation + multi-feed stage assignment.
- **Semantic drift risk:** geometry/pressure wording can accidentally imply wrong physics.
  - Mitigation: explicit normative geometry/pressure clauses in specs.
- **Scope creep risk:** controller proof or gameplay exposure may leak into this change.
  - Mitigation: explicit defer to `ModularSimulator-9tr.6` and unchanged-surface regression checks.
- **Contract drift risk:** teams may accidentally reintroduce `reflux_ratio`/`boilup_ratio` as live runtime knobs.
  - Mitigation: explicit non-actuation decision in units/session/connection/observability deltas and task gates.
- **Actuation surrogate risk:** direct-duty services and withdrawal seams may accidentally imply nonphysical source/sink behavior.
  - Mitigation: freeze boundary-field duty requests, external material-routing seams, inventory bounds, liquid-phase seam ownership, and explicit conservation tests before implementation.

## Verification Strategy

- **Wave 0 (artifact rewrite gate):** proposal/design/tasks/spec deltas must align to dynamic stagewise scope and unwind obsolete checked implementation tasks.
- **Wave 1 (red tests first):** introduce failing tests for stagewise transients, conservation, multi-feed assignment, geometry semantics, dynamic pressure, unit-local reflux/product/duty-request boundary seams, holdup-bounded withdrawals, runtime observability, unchanged gating, and stagewise-only/no-shim behavior.
- **Wave 2 (implementation):** keep stagewise runtime wiring as the only distillation behavior path and preserve existing gated catalog identity.
- **Wave 3 (runtime proof):** prove behavior through normal subsystem/network composition and substrate observability, with no controller-state hacks.
- **Wave 4 (closure):** independent `hybrid-code-reviewer` + `simulation-advisor` review in parallel, OpenSpec verification/sync, then closure.

## Context

- `src/modular_simulation/unit_processes/separation/stagewise_distillation.py` currently computes stage vapor compositions from a constant `relative_volatility_reference` vector and uses fixed latent heats for condenser/reboiler `Q/λ` mapping.
- The same file currently reports `distillate_temperature`, `bottoms_temperature`, and `reflux_outlet_temperature` as proxy values derived from mixed feed temperature logic rather than a rigorous enthalpy path.
- The unit exposes no property-package dependency, no enthalpy state, and no reboiler outlet flash calculation.
- On the bottoms side, `calculate_algebraic_values(...)` currently clips reboiler boilup by sump holdup and a vapor-capacity proxy, but it does not represent an explicit internal circulation draw from the sump or liquid return from an internal reboiler pass.
- `tests/unit_process/test_layer4_stagewise_distillation.py` already proves the current reduced-order baseline: direct duty actuation, inventory-bounded `Q/λ` clipping, pressure-insensitive composition behavior, and no public circulation seam.
- `openspec/specs/session/spec.md` already states that any retained sump-to-reboiler surrogate remains internal-only and originally pointed at `ModularSimulator-9tr.5.2` as the follow-up that must freeze the stronger closure.

## Goals

- Freeze **Gate A** as an internal-only bottoms-side circulation closure that stays inside the monolithic `StagewiseDistillationColumn`.
- Freeze **Gate B** as an explicit reduced-order thermodynamic-basis statement for the stagewise column in this slice.
- Make the limiting-duty behavior concrete enough for TDD-first implementation and realism review.
- Keep the scope small enough to avoid hidden architecture widening.

## Non-Goals

- Do not add a property-package hook, enthalpy flash path, or rigorous thermal-state semantics.
- Do not claim thermosyphon, forced-circulation, or pressure-swing behavior.
- Do not add a new connection-layer edge, public circulation actuator, public port, or separate reboiler unit.
- Do not introduce superheat handling in the retained reduced-order path.
- Do not widen session, gameplay, or controller surfaces.

## Decisions

1. **Gate A uses an internal support surrogate, not hydraulic equipment modeling.**
    - The first implementation stays monolithic and unit-internal.
    - The first implementation is also **pure algebraic only**: no hidden reboiler differential state, no hidden reboiler algebraic inventory, and no separate internal circulation state variable are introduced in this slice.
    - The bottoms sump remains the owner of liquid holdup.
    - The design assumes a hidden internal loop: sump liquid feeds an internal reboiler pass, vapor returns to the bottom stage, and unvaporized liquid returns to the sump.
    - This is a custody story only. It does **not** claim thermosyphon head, pump head, Darcy-Weisbach friction, or two-phase hydraulic prediction.

2. **The leading candidate is a project-specific inventory-throttle surrogate with an explicit time basis.**
   - Use one fixed internal support time constant for the first slice rather than a named thermosyphon or forced-circulation correlation.
   - Design default: treat available sump holdup as supporting at most `L_support_available_mol / τ_support_s` mol/s of boilup, with `τ_support_s = 4.0 s` as a project-specific bounded surrogate constant.
   - This constant remains internal-only. It is not a new runtime actuation seam, not a public session contract, and not a claim about real hydraulic circulation equipment.
   - This gives an explicit new limiter without inventing a circulation control knob or overclaiming a generic engineering rule.
   - Freeze the algebraic support law exactly as:
     - `L_support_available_mol = max(0.0, sum(bottoms_sump_component_moles))`
     - `τ_support_s = 4.0`
     - `V_requested = max(0.0, reboiler_duty_request_W / reboiler_latent_heat_j_per_mol)`
     - `V_support_limited = L_support_available_mol / τ_support_s`
     - `V_realized = min(V_requested, V_support_limited, maximum_vapor_capacity_flow_mol_s)`
     - `Q_realized = reboiler_latent_heat_j_per_mol * V_realized`
   - Preserve existing sump-owned non-negative-inventory behavior in the retained reduced-order path; this slice adds the support limiter above rather than a new hidden holdup state.
   - This slice does **not** add a separate holdup-degradation law, stage-liquid-flow coupling term, or alternate outlet-quality formula.

3. **Requested duty is only an attempted boilup request under the reduced-order basis.**
   - Compute requested boilup from the existing latent-heat surrogate and apply the exact limiter set frozen above.
   - In the **non-limiting regime**, realized boilup continues to follow the requested `Q/λ` value.
   - In the **support-limiting regime**, realized boilup clips to the support-limited value defined above.
   - Realized reboiler duty then becomes `Q_realized = λ * V_realized`.
   - If the support surrogate is the active limiter, there is no extra retained sensible-heating or superheat path in this slice.

4. **Bottoms-withdrawal coupling remains dynamic through sump ownership, not a new same-step algebraic bypass.**
   - This pack does not require bottoms withdrawal to reduce boilup through a new same-step algebraic subtraction term inside the same closure evaluation.
   - Instead, bottoms withdrawal interacts through the shared sump inventory owner over time: less sump holdup means less `L_support_available_mol` on later evaluations.
   - This keeps the slice aligned with the existing monolithic inventory-first structure and avoids hidden ordering changes being treated as a new public contract.

5. **Gate B keeps the current stagewise thermodynamic basis explicitly reduced-order.**
   - Stage equilibrium remains a constant-relative-volatility surrogate.
   - Condenser and reboiler phase change remain fixed-latent-heat `Q/λ` surrogates.
   - Reported temperatures remain proxy values, not rigorous state predictions.
   - `StagewiseDistillationColumn` still has no property-package hook and no enthalpy-based flash path in this slice.
   - The honest claim is limited to duty/reflux/feed/holdup-driven composition changes inside the material-balance model.
   - Pressure-sensitive VLE, pressure swing, and rigorous superheat claims remain out of scope.

6. **Fallbacks are evaluated but not selected for this pack.**
   - **Fallback A:** a fixed vaporized-fraction / outlet-quality heuristic is acknowledged only as background context. It is **not** selected for this change and may not silently replace the support-surrogate closure during implementation.
   - **Fallback B:** keeping the current merged-kettle surrogate and only renaming it is rejected for this pack because it does not answer the new support-limited clipping requirement.
   - If implementation later proves the fixed support-surrogate shape cannot be added without hidden architecture widening, stop and return to planning rather than silently switching to a different public story.

## Consequences

- The model stays honest about being pedagogical and reduced-order.
- The bottoms side gains a new internal limiter beyond raw `Q/λ` plus sump holdup.
- The pack remains bounded because it does not open a property-package or hydraulics redesign.

## Risks / Trade-offs

- **Surrogate-tuning risk:** the support time constant is a project-specific throttle, not a measured hydraulic model.
  - Mitigation: keep it internal, fixed, and explicitly documented as a reduced-order realism guard rather than a named engineering correlation.
- **Overclaiming risk:** reviewers may mistake stronger bottoms-side wording for stronger thermodynamic realism.
  - Mitigation: repeat the constant-alpha / fixed-latent-heat / proxy-temperature boundary in proposal, design, delta specs, and review gate.
- **Scope-creep risk:** implementation may drift into superheat or property-package work once duty clipping is introduced.
  - Mitigation: tasks explicitly require stopping and handing work back if the bounded reduced-order path becomes insufficient.

## Verification Strategy

- Artifact gate:
  - `openspec validate bound-stagewise-bottoms-closure-and-thermodynamic-basis --strict --no-interactive`
- Repo-health check (non-blocking until the pre-existing `spec/progression` wording baseline is fixed elsewhere):
  - `openspec validate --specs --strict --no-interactive`
- Baseline evidence gate:
  - `uv run pytest tests/unit_process/test_layer4_stagewise_distillation.py -k "reboiler or duty or inventory"`
- Future implementation evidence gate:
  - prove a non-limiting regime where realized boilup still follows requested `Q/λ`,
  - prove a support-limited regime where realized boilup and realized duty clip below request,
  - prove bottoms withdrawal still interacts through sump ownership rather than bypassing it,
  - prove no new public circulation seam or widened connection/session contract appears,
  - prove the model still behaves as a constant-relative-volatility / fixed-latent-heat / proxy-temperature surrogate unless a later change explicitly upgrades that basis.

## Implementation packet metadata

- Beads task: `ModularSimulator-9tr.5.2`
- `simulation-realism-required: true`
- Required closure review: `hybrid-code-reviewer`
- Realism assumptions the implementation packet must preserve:
  - internal-only circulation closure,
  - no thermosyphon or forced-circulation claim,
  - no pressure-swing or property-package claim,
  - no superheat redesign in this slice,
  - realized duty clips with realized boilup when circulation is the active limiter.

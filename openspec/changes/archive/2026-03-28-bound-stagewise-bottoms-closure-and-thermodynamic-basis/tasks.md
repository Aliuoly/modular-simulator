## Implementation packet metadata

- Beads task: `ModularSimulator-9tr.5.2`
- `simulation-realism-required: true`
- Review gate before closure: `hybrid-code-reviewer`
- Realism assumptions to preserve:
  - Gate A stays internal-only: no public circulation seam, no connection-layer widening, no separate reboiler unit.
  - Gate B stays reduced-order: constant-relative-volatility stage closure, fixed-latent-heat `Q/λ` duty mapping, and proxy temperatures remain the active basis.
  - If the retained internal support surrogate cannot support requested boilup, realized boilup and realized duty clip to the support-limited value.
  - Do not imply thermosyphon hydraulics, forced circulation, pressure swing, property-package thermodynamics, or superheat carryover in this slice.

## Dependency gate

- [x] D0 Do not start implementation until this change pack is approved and a bounded implementation packet is created from these tasks. Implementation packet created in Beads as `ModularSimulator-9tr.5.2.1`.
- [x] D1 If implementation requires a property-package hook, public circulation seam, connection-layer widening, thermosyphon claim, forced-circulation claim, or superheat redesign to make progress, stop and return the work to planning instead of improvising.
- [x] D2 Keep the closure pure algebraic and unit-internal for this slice: no hidden reboiler inventory/state, no hidden circulation state variable, and no silent substitution of the fixed outlet-quality fallback.

## Wave 1 — Write the red tests for the new bottoms-side limiter first

- [x] 1.1 Extend `tests/unit_process/test_layer4_stagewise_distillation.py` with a red test that proves a **non-limiting regime** still follows the existing latent-heat relation: higher positive `reboiler_duty_request_W` increases realized boilup and realized duty while the internal support surrogate is not the active limiter.
- [x] 1.2 Extend the same file with a red test that proves a **support-limited regime**: when duty request implies more boilup than the hidden internal support surrogate can support, `realized_reboiler_boilup_flow_mol_s` clips below the requested `Q/λ` value and `reboiler_duty_W` clips to `reboiler_latent_heat_j_per_mol * realized_reboiler_boilup_flow_mol_s`.
- [x] 1.3 Add a red interaction test that proves the limiter still respects sump ownership and existing bottoms withdrawal semantics: reduced starting sump holdup, or sump depletion caused over time by bottoms withdrawal, reduces later support-limited boilup, but no same-step bypass, fake source, or negative inventory appears.
- [x] 1.4 Add a red seam-preservation test that proves `StagewiseDistillationColumn` still exposes the same public ports and does not gain a circulation inlet/outlet or other new public boundary field for this slice.
- [x] 1.5 Re-run and preserve the existing honesty baseline in `tests/unit_process/test_layer4_stagewise_distillation.py` for pressure-insensitive constant-alpha behavior and direct-duty `Q/λ` semantics.
- [x] 1.6 Run the red boundary:
  - `uv run pytest tests/unit_process/test_layer4_stagewise_distillation.py -k "reboiler or duty or inventory or pressure"`
  - Expected evidence: the new support-limited expectations fail before implementation changes land.

## Wave 2 — Implement the bounded internal-only closure in the unit model

- [x] 2.1 Update `src/modular_simulation/unit_processes/separation/stagewise_distillation.py` so the bottoms-side algebraic closure computes requested boilup from the existing `Q/λ` relation and then clips it by a hidden internal support surrogate with an explicit time basis before applying retained reduced-order capacity behavior.
- [x] 2.1a Freeze the exact algebraic law from `design.md` during implementation:
  - `L_support_available_mol = max(0.0, sum(bottoms_sump_component_moles))`
  - `τ_support_s = 4.0`
  - `V_requested = max(0.0, reboiler_duty_request_W / reboiler_latent_heat_j_per_mol)`
  - `V_support_limited = L_support_available_mol / τ_support_s`
  - `V_realized = min(V_requested, V_support_limited, maximum_vapor_capacity_flow_mol_s)`
  - `Q_realized = reboiler_latent_heat_j_per_mol * V_realized`
- [x] 2.2 Keep the custody story explicit inside the monolithic unit:
  - bottoms sump remains the liquid owner,
  - hidden circulation draw is internal-only,
  - vapor returns to the bottom stage,
  - unvaporized liquid returns internally to the sump,
  - bottoms product withdrawal remains a sump-owned external withdrawal.
- [x] 2.3 Keep the implementation bounded:
  - no hidden reboiler inventory/state,
  - no hidden circulation state variable,
  - no property-package hook,
  - no enthalpy flash path,
  - no superheat carryover path,
  - no thermosyphon/forced-circulation naming in code comments or tests unless actually modeled.
- [x] 2.4 Preserve the current public/runtime surface:
  - no new public ports,
  - no new public circulation-related field or readout contract,
  - no new connection-layer semantics,
  - no new session/gameplay seam,
  - no ratio knob repurposed into actuation.

## Wave 3 — Make the verification set pass and sync the OpenSpec deltas

- [x] 3.1 Make the new red tests pass in `tests/unit_process/test_layer4_stagewise_distillation.py`.
- [x] 3.2 Re-run the focused regression evidence:
  - `uv run pytest tests/unit_process/test_layer4_stagewise_distillation.py -k "reboiler or duty or inventory or pressure"`
- [x] 3.3 Re-run the full affected unit file:
  - `uv run pytest tests/unit_process/test_layer4_stagewise_distillation.py`
- [x] 3.4 Confirm the implemented behavior still supports the honesty boundary required by this pack:
  - support-limited clipping is present,
  - realized duty equals latent heat times realized boilup in the reduced-order path,
  - pressure-sensitive VLE claims are still unsupported,
  - no new public circulation seam exists.
- [x] 3.5 Sync the implemented deltas into the live specs after code and tests pass:
  - update `openspec/specs/units-and-components/spec.md`,
  - update `openspec/specs/session/spec.md`,
  - archive this change only after implementation, verification, and review are complete.
- [x] 3.6 Re-run OpenSpec validation after spec sync:
  - required: `openspec validate bound-stagewise-bottoms-closure-and-thermodynamic-basis --strict --no-interactive`
  - repo-health check only: `openspec validate --specs --strict --no-interactive` (record the known unrelated `spec/progression` baseline failure unless it is fixed separately)

## Wave 4 — Independent realism review gate

- [x] 4.1 Run `hybrid-code-reviewer` with the same task packet and `simulation-realism-required: true`.
- [x] 4.2 Do not close the Beads implementation work until review is non-blocking and explicitly confirms:
  - the model stayed monolithic and unit-internal,
  - no thermosyphon/forced-circulation/pressure-swing claims were introduced,
  - support-limited clipping is implemented honestly,
  - the reduced-order thermodynamic basis is still named correctly,
  - no public seam widened.

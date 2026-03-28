## Why

`StagewiseDistillationColumn` currently mixes two reduced-order stories that are still too loose for realism review of the bottoms side.

- `src/modular_simulation/unit_processes/separation/stagewise_distillation.py` uses a constant `relative_volatility_reference` vector for stage separation.
- The condenser and reboiler map duty to phase change through fixed latent heats (`Q/λ`).
- Distillate, reflux, and bottoms temperatures are proxy values, not rigorous thermodynamic states.
- The unit has no property-package hook and no enthalpy-based flash path.
- The bottoms side still behaves like a merged kettle-style surrogate: requested duty creates boilup that is clipped by sump holdup and vapor-capacity proxies, but there is no explicit internal circulation draw/return closure.

That leaves one open realism question for `ModularSimulator-9tr.5.2`: when requested duty implies more boilup than the retained internal bottoms-side circulation can support, the model must say whether duty still "counts" thermally or whether realized boilup and realized duty both clip to the circulation-supported value.

This pack freezes a bounded, honest answer without widening the public model surface:

- **Gate A:** keep the bottoms-side circulation closure internal-only and unit-local.
- **Gate B:** keep the current stagewise thermodynamic basis explicitly reduced-order for this slice and state what it can and cannot honestly claim.

## What Changes

- Define the bounded first implementation for bottoms-side closure as an **internal-only support-limited reboiler surrogate** inside `StagewiseDistillationColumn`.
- Freeze that first closure as a **pure algebraic, no-extra-inventory** surrogate for this slice: no hidden reboiler vessel state, no separate circulation state, and no public circulation-facing contract.
- Freeze the implementation intent around a hidden, project-specific internal support surrogate with an explicit time basis rather than a thermosyphon, forced-circulation, pressure-swing, or connection-layer redesign.
- Require the key limiting behavior:
  - if requested reboiler duty implies more boilup than the retained internal support surrogate can support,
  - realized boilup clips to the support-limited value,
  - realized reboiler duty clips to `λ * realized_boilup`,
  - this slice does **not** bank extra duty as sensible heating or superheat.
- Freeze the thermodynamic honesty boundary for this slice:
  - stage separation remains constant-relative-volatility based,
  - condenser/reboiler phase change remains fixed-latent-heat `Q/λ` based,
  - temperatures remain proxy values,
  - no property-package or enthalpy-flash path is introduced here,
  - pressure-sensitive VLE and pressure-swing claims remain out of scope.
- Keep the unit monolithic and internal:
  - no new public circulation seam,
  - no new public circulation-related boundary field or session-visible contract,
  - no connection-layer widening,
  - no separate placeable condenser/reboiler/tower split,
  - no thermosyphon or forced-circulation claim unless later work explicitly models those mechanisms.

## Capabilities

### Modified Capabilities
- `units-and-components`
- `session`

## Impact

- OpenSpec change-pack files created by this slice:
  - `openspec/changes/bound-stagewise-bottoms-closure-and-thermodynamic-basis/proposal.md`
  - `openspec/changes/bound-stagewise-bottoms-closure-and-thermodynamic-basis/design.md`
  - `openspec/changes/bound-stagewise-bottoms-closure-and-thermodynamic-basis/tasks.md`
  - `openspec/changes/bound-stagewise-bottoms-closure-and-thermodynamic-basis/specs/units-and-components/spec.md`
  - `openspec/changes/bound-stagewise-bottoms-closure-and-thermodynamic-basis/specs/session/spec.md`
- Expected future implementation files:
  - `src/modular_simulation/unit_processes/separation/stagewise_distillation.py`
  - `tests/unit_process/test_layer4_stagewise_distillation.py`
- Expected future spec-sync targets after implementation:
  - `openspec/specs/units-and-components/spec.md`
  - `openspec/specs/session/spec.md`

## Explicitly Deferred

- Property-package-backed stagewise thermodynamics.
- Enthalpy-based flash closure on `StagewiseDistillationColumn`.
- Superheat modeling or any redesign that retains duty after boilup clipping as sensible heating.
- Thermosyphon head, buoyancy-loop, pump-loop, or two-phase friction closure.
- Pressure-sensitive VLE, pressure-swing distillation, or full MESH energy closure.
- Any new public session, connection, or controller seam for circulation.

## Why

The active pack still contains ambiguous "plant-ready" actuation language that no longer matches the approved architecture. Before implementation continues, the change must explicitly freeze the expanded monolithic design so the remaining work is honest about what is and is not implemented.

## What Changes

- Freeze one monolithic `StagewiseDistillationColumn` as the implementation contract for this pack.
- Freeze explicit topology and withdrawal seams on that monolith:
  - reflux liquid outlet plus reflux-return inlet
  - distillate withdrawal as external withdrawal from reflux-drum holdup
  - bottoms withdrawal as external withdrawal from bottoms-sump holdup.
- Freeze condenser/reboiler actuation for this slice as direct duty services coupled into the RHS through a named fixed-latent-heat `Q/λ` surrogate under the constant-molar-overflow slice, with available vapor/liquid inventory bounds and no component creation/destruction.
- Freeze reflux-return and product-withdrawal seams as liquid-phase, holdup-bounded runtime seams that cannot bypass reflux-drum or bottoms-sump custody.
- Freeze `reflux_ratio` and `boilup_ratio` semantics to initialization/reference/derived-observable only; if exposed at runtime, they are derived from actual runtime flows rather than live actuation knobs.
- Keep multicomponent, stage-by-stage dynamic behavior, multi-feed assignment, and geometry/pressure contracts as normative runtime requirements.
- Keep `place_shortcut_distillation_column` hide/reject boundary unchanged on topology-only starts.
- Rewrite tasks/spec deltas to remove evidence claims that are not backed under the expanded actuation architecture.

## Capabilities

### Modified Capabilities
- `units-and-components`
- `connection`
- `observability`
- `session`

## Deferred

- Controller proof and closed-loop evidence are deferred to `ModularSimulator-9tr.6`.
- No new public start exposure or build-list widening in this change.

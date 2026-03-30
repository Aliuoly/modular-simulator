# Phase 2: Kernel Adapter, Warm Starts & Delay State - Context

**Gathered:** 2026-03-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Add a reusable candidate-kernel adapter seam beneath the existing simulation/session stack so the team can evaluate coupled kernel directions without rewriting live facades first. Phase 2 covers the shared adapter contract, canonical warm-start and restore behavior, and explicit handling of transport-lag and deadtime state; it does not yet decide benchmark winners, realtime viability, or the migration roadmap.

</domain>

<decisions>
## Implementation Decisions

### Adapter Surface
- **D-01:** Phase 2 should define the full shared candidate-kernel contract up front: state, residual, Jacobian, bounds, initialization, warm start, and telemetry are part of the same seam rather than being phased in later.
- **D-02:** The current split runtime should be wrapped fully as one adapter implementation so the baseline and future candidates are compared through the same contract.
- **D-03:** Comparable telemetry is mandatory in the adapter contract from the start rather than being deferred to Phase 3.

### Facade Preservation
- **D-04:** Phase 2 should be substrate-first by default: keep adapter work behind substrate/runtime boundaries unless there is a clear technical reason to widen session or API contracts.
- **D-05:** Higher-layer session or API contract changes are allowed when they materially improve adapter integration; preserving today's gameplay/API contract shape is not a hard constraint by itself.

### Warm Starts And Restore
- **D-06:** Checkpoint-style accepted snapshots are the one canonical restore mechanism underneath normal resume, save/load, and post-edit recovery paths.
- **D-07:** The authoritative source for warm starts is the accepted coupled plant snapshot rather than mixed reconstruction from helper caches or gameplay-owned state.
- **D-08:** If a candidate cannot safely restore from a requested warm-start path, the runtime must fail explicitly with a clear reason rather than silently cold-starting or attempting lossy repair.

### Delay And Transport State
- **D-09:** Candidate kernels may choose their own delay or deadtime treatment in Phase 2 rather than being forced to keep the current external-history representation.
- **D-10:** Any candidate that replaces the current transport-history approach must document the mapping from existing delay/transport state to its own representation and define safe restore behavior across checkpoint reloads and runtime edits.
- **D-11:** Delay semantics remain open for exploration in Phase 2; semantic consistency with the current runtime is preferred only when justified by later research rather than locked now.

### the agent's Discretion
- Choose the exact Python surface for the adapter seam and whether it lands as protocols, dataclasses, or other typed substrate contracts, as long as the full contract in D-01 stays explicit.
- Choose the minimum justified higher-layer session/API changes case by case under D-04 and D-05 rather than widening public contracts speculatively.
- Choose the exact artifact shape for candidate-specific delay-state mapping and restore documentation under D-10.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone and phase contract
- `.planning/PROJECT.md` — Milestone v1.0 goal, brownfield constraints, and compatibility requirement to preserve current substrate consumers where practical.
- `.planning/REQUIREMENTS.md` — `KERN-04`, `SOLV-02`, `DELY-01`, `DELY-02`, and `DELY-03` define the Phase 2 adapter, warm-start, and delay-state requirements.
- `.planning/ROADMAP.md` — Phase 2 goal and success criteria for the adapter seam, initialization/warm starts, and delay-state restore behavior.
- `.planning/STATE.md` — Current planning state and carried-forward concern that delay semantics must stay explicit in later benchmark and migration work.

### Prior locked decisions
- `.planning/phases/01-failure-semantics-acceptance-gates/01-CONTEXT.md` — Carries forward the accepted whole-plant snapshot boundary, explicit rejection semantics, replay/checkpoint seam preference, and persistence-vs-observability separation.

### Session and substrate ownership
- `openspec/specs/session/spec.md` §§202-219 — `PlantBackendSession` changes must remain substrate-generic and higher layers must consume substrate-owned observability reads.
- `docs/plant_backend_session_user_guide.md` §§1-32 — Describes `PlantBackendSession` as the low-level runtime-editing substrate with checkpoint save/load and rollback-safe runtime operations.

### Runtime and delay semantics
- `openspec/specs/connection/spec.md` §§178-195 — Canonical line-flow ownership and explicit runtime fallback behavior when hydraulic data is missing.
- `openspec/specs/connection/spec.md` §§323-336 — Process runtime state must stay distinct from public observability and round-trip authoritatively through checkpoint persistence.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/modular_simulation/connection/runtime/runtime.py` — Already exposes injectable step seams for hydraulic solve, transport/mixing update, and boundary propagation, plus checkpoint export/restore hooks.
- `src/modular_simulation/cli/backend_session.py` — Already provides substrate save/load checkpoint APIs that can anchor the canonical restore path.
- `src/modular_simulation/connection/runtime/runtime_persistence.py` — Already stages runtime/network/process state restore with rollback on failure, which is the strongest existing warm-start safety seam.
- `src/modular_simulation/connection/runtime/connected_plant_orchestrator.py` — Already exports and restores authoritative process runtime state per process.
- `src/modular_simulation/connection/runtime/transport_runtime.py` and `src/modular_simulation/connection/domain/transport.py` — Already provide explicit transport-history state and built-in lag-transport behavior that future candidates may map from or replace.

### Established Patterns
- The runtime uses typed substrate seams and protocol-based step injection rather than forcing all behavior through one monolith.
- Checkpoint restore is already explicit, validated, and rollback-safe; the codebase does not treat gameplay/session mirrors as authoritative simulation state.
- Public observability is separated from persistence payloads, so new adapter state should follow that split rather than widening read models casually.

### Integration Points
- `src/modular_simulation/connection/runtime/runtime.py:193-220` — Existing protocol seams for hydraulic solve, transport/mixing, and boundary propagation are the closest insertion point for the Phase 2 adapter contract.
- `src/modular_simulation/connection/runtime/runtime.py:820-855` — Live runtime snapshot export/resume path that should become the canonical adapter restore seam.
- `src/modular_simulation/connection/runtime/runtime_persistence.py:470-530` — Rollback-safe snapshot restore path that downstream work should preserve.
- `src/modular_simulation/cli/backend_session.py:871-885` — Current client-facing checkpoint API that anchors save/load expectations.

</code_context>

<specifics>
## Specific Ideas

- The user expects save/load game behavior to remain the intuitive restore story, so multiple warm-start modes should collapse onto one canonical checkpoint-style restore path rather than becoming separate user-facing concepts.
- The user is not attached to the current gameplay service or API contract shape; higher-layer changes are acceptable when they have a clear technical payoff for the adapter seam.
- Delay/deadtime treatment should stay open enough for real candidate exploration, but any alternative must come with explicit state-mapping and restore rules.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 02-kernel-adapter-warm-starts-delay-state*
*Context gathered: 2026-03-29*

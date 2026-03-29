# Phase 1: Failure Semantics & Acceptance Gates - Context

**Gathered:** 2026-03-29 (assumptions mode)
**Status:** Ready for planning

<domain>
## Phase Boundary

Make the current split-kernel failure modes, accepted coupled-state boundary, and explicit structural and physical rejection rules concrete for the connected-plant runtime. This phase is about defining and reproducing failure semantics for the existing kernel and candidate-kernel comparisons; it does not yet add the solver adapter seam, benchmark harness, or migration implementation from later phases.

</domain>

<decisions>
## Implementation Decisions

### Failure Taxonomy
- **D-01:** Phase 1 must classify four first-class failure families: stale hydraulic lag, inventory or physical-feasibility breaks, structural inconsistency, and solver masking or fake stability.
- **D-02:** Phase 1 evidence must cover four scenario classes: inventory-sensitive cases, delay-heavy cases, strongly coupled cases, and runtime-edit or restart cases.

### Accepted-Step Boundary
- **D-03:** The accepted or rejected state boundary is the whole connected-plant macro-step, not only the `MacroCoupler` sequence, because subsystem process phases mutate unit state before connection runtime coupling runs.
- **D-04:** A candidate step is acceptable only when it yields one coupled plant snapshot for that macro-step; partially updated unit state and connection state must not be exposed as if the step succeeded.

### Structural And Physical Rejection
- **D-05:** Under-specified, over-specified, and structurally inconsistent flowsheet states should be rejected through the existing compile and reconfiguration-barrier path before runtime stepping starts.
- **D-06:** Phase 1 needs an explicit plant-level physical acceptance layer because current guards are partial and some non-physical states can still be hidden behind observability clipping or local fallback behavior.

### Replay And Diagnostics
- **D-07:** Failure reproduction and classification should use the backend/runtime checkpoint seam plus macro-step bookkeeping rather than gameplay-side state, so evidence is deterministic and comparable across kernel directions.
- **D-08:** Rejection reasons should extend the repo's structured diagnostic-payload pattern into runtime-step failures; plain `RuntimeError` strings are not sufficient for acceptance-gate or benchmark disqualification decisions.

### the agent's Discretion
- Choose the exact data shape for Phase 1 failure taxonomy tables, as long as the four locked failure families and four locked scenario classes remain explicit.
- Choose whether Phase 1 evidence uses full snapshot rollback, staged candidate state, or another acceptance/publication pattern after the required external research on low-latency transactional state publication.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone and phase contract
- `.planning/PROJECT.md` — Milestone v1.0 goal, brownfield constraints, and top-level performance/correctness priorities.
- `.planning/REQUIREMENTS.md` — `KERN-01`, `KERN-02`, `KERN-03`, and `KERN-05` define Phase 1 acceptance and rejection requirements.
- `.planning/ROADMAP.md` — Phase 1 goal, success criteria, and sequencing relative to later adapter, benchmark, and migration phases.
- `.planning/STATE.md` — Current planning state and carried-forward concerns, especially explicit deadtime handling and missing `.planning/config.json`.

### Runtime and connection semantics
- `openspec/specs/connection/spec.md` §§91-112 — Junction runtime semantics, near-zero-flow fallback rules, and failure behavior when required runtime state is missing.
- `openspec/specs/connection/spec.md` §§137-195 — Canonical hydraulic solve ownership, pressure/flow solve contract, and explicit fallback behavior when hydraulic data is missing.

### Session and substrate ownership
- `openspec/specs/session/spec.md` §§202-219 — `PlantBackendSession` must remain a generic substrate hook and higher layers must consume substrate-owned observability reads.

### Observability contract
- `openspec/specs/observability/spec.md` §§16-22 — Public observability must stay distinct from persistence/checkpoint payloads.
- `openspec/specs/observability/spec.md` §§23-52 — Frozen observability envelope and current holding-tank process-state read semantics, including near-empty clipping behavior.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/modular_simulation/cli/backend_session.py` — already exposes `step()`, `save_checkpoint()`, `load_checkpoint()`, and structured commit diagnostics; this is the cleanest Phase 1 replay and failure-reproduction seam.
- `src/modular_simulation/connection/runtime/runtime_persistence.py` — already supports validated restore, rollback-safe recovery, and deterministic replay hashes that can anchor reproducible failure classification.
- `src/modular_simulation/connection/runtime/connection_layer.py` — `MacroStepBookkeeping` already captures executed sequence, Picard usage, fallback keys, and residual metadata that Phase 1 can reuse for classification.
- `src/modular_simulation/connection/runtime/transport_runtime.py` — already enforces transport-level invariants such as finite values and normalized composition, which can feed plant-level physical acceptance checks.

### Established Patterns
- `src/modular_simulation/connection/runtime/connected_plant_orchestrator.py` and `src/modular_simulation/connection/runtime/runtime.py` use a fixed macro-step order where unit process stepping happens before connection coupling.
- `src/modular_simulation/connection/topology/network.py`, `src/modular_simulation/connection/runtime/reconfiguration_barrier_processor.py`, and `src/modular_simulation/cli/backend_session.py` already prefer pre-step validation plus rollback-safe barrier application for structural failures.
- `src/modular_simulation/connection/runtime/runtime_persistence.py` and `openspec/specs/observability/spec.md` separate persistence payloads from public observability reads; Phase 1 should preserve that distinction.
- The codebase already uses structured diagnostics for barrier and commit failures, but runtime-step coupling failures still degrade to broad `RuntimeError` strings in `src/modular_simulation/connection/runtime/connection_layer.py`.

### Integration Points
- `src/modular_simulation/connection/runtime/connected_plant_orchestrator.py:334-410` — defines the plant-wide macro-step boundary and where accepted-state publication currently becomes ambiguous.
- `src/modular_simulation/connection/runtime/runtime.py:684-773` — owns barrier apply, macro-step coupling, bookkeeping publication, and runtime observability state.
- `src/modular_simulation/connection/runtime/connected_plant_orchestrator.py:442-483` — clips holding-tank observability values, which is a critical masking seam for Phase 1 physical-feasibility work.
- `src/modular_simulation/connection/hydraulics/hydraulic_solver.py` — already rejects invalid hydraulic system structure such as missing anchors, DOF mismatch, and singular solves; Phase 1 should classify these as structural rejection, not generic runtime failure.

</code_context>

<specifics>
## Specific Ideas

- Phase 1 should preserve the already agreed acceptance semantics: one coupled accepted snapshot, physical validity, explicit rejection reasons, and no hidden recovery paths.
- Phase 1 should preserve the already agreed scenario coverage: inventory-sensitive, delay-heavy, strongly coupled, and runtime-edit or restart cases.
- External research focus still needed for this phase: compare low-latency transactional state-publication patterns for mixed unit-step plus plant-coupling simulators, especially full snapshot rollback versus staged candidate state.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 01-failure-semantics-acceptance-gates*
*Context gathered: 2026-03-29*

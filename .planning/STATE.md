---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: completed
stopped_at: Completed 01-04-PLAN.md
last_updated: "2026-03-31T01:09:00.000Z"
last_activity: 2026-03-31
progress:
  total_phases: 5
  completed_phases: 5
  total_plans: 19
  completed_plans: 19
  percent: 100
---

# Project State

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-03-29)

**Core value:** Deliver a grounded, composable process-simulation backend that stays physically credible enough for teaching while still usable as a realtime game substrate.
**Current focus:** Phase 01 — failure-semantics-acceptance-gates

## Current Position

Phase: 01 (failure-semantics-acceptance-gates) — COMPLETED
Plan: 4 of 4
Status: Completed 01-04-PLAN.md
Last activity: 2026-03-31 -- Completed 01-04-PLAN.md

Progress: [██████████] 100%

## Performance Metrics

**Velocity:**

- Total plans completed: 19
- Average duration: 6 min
- Total execution time: 1.9 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 4 | 62 min | 16 min |
| 02 | 3 | 9 min | 3 min |
| 03 | 3 | 27 min | 9 min |
| 04 | 2 | 7 min | 4 min |

**Recent Trend:**

- Last 5 plans: 05-03 (6 min), 05-04 (3 min), 01-01 (13 min), 01-02 (10 min), 01-03 (17 min)
- Trend: Stable

| Phase 01 P01 | 13 min | 2 tasks | 6 files |
| Phase 02 P01 | 3 min | 2 tasks | 4 files |
| Phase 02 P02 | 4 min | 2 tasks | 6 files |
| Phase 02 P03 | 2 min | 2 tasks | 5 files |
| Phase 03 P01 | 4 min | 2 tasks | 4 files |
| Phase 03 P02 | 18 min | 2 tasks | 7 files |
| Phase 03 P03 | 5 min | 2 tasks | 6 files |
| Phase 04 P01 | 1 min | 2 tasks | 3 files |
| Phase 04 P02 | 6 min | 2 tasks | 4 files |
| Phase 05 P01 | 3 min | 2 tasks | 4 files |
| Phase 05 P02 | 4 min | 2 tasks | 2 files |
| Phase 05 P03 | 6 min | 2 tasks | 2 files |
| Phase 05 P04 | 3 min | 2 tasks | 3 files |
| Phase 01 P02 | 10 min | 2 tasks | 13 files |
| Phase 01 P03 | 17 min | 2 tasks | 8 files |
| Phase 01 P04 | 22 min | 3 tasks | 6 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap] Treat split-step instability and possible whole-flowsheet escalation as one milestone decision problem.
- [Roadmap] Use hybrid-coupled kernel as the default roadmap direction, with SciPy as the disciplined baseline and `sundials4py` as the first serious post-SciPy path.
- [Phase 02]: Use a small required CandidateKernelAdapter core and move solver-shaped hooks into separate optional protocols.
- [Phase 02]: Expose split runtime delay treatment as external transport history and leave optional solver capabilities empty until real seams exist.
- [Phase 02]: Normalize checkpoint envelopes into connection_runtime_v1 payloads before adapter warm start — One accepted-snapshot restore helper now serves checkpoint restore and resume without cold-start fallback.
- [Phase 02]: Keep PlantBackendSession save_checkpoint/load_checkpoint names stable while routing load through canonical restore — Preserves substrate-facing session API while moving restore policy under the shared adapter seam.
- [Phase 02]: Delay semantics and mapping metadata belong to the required adapter core so candidate comparisons cannot hide delay treatment.
- [Phase 02]: The split baseline keeps the existing transport_runtime_state schema in Phase 2 instead of renaming snapshot payloads prematurely.
- [Phase 02]: Future candidates using augmented_state or hybrid must publish explicit transport-history mapping and restore rules for checkpoint reloads and runtime edits.
- [Phase 03]: Adopt one shared benchmark contract package under src/modular_simulation/connection/benchmarking for fairness metadata, attempt records, and accepted-step latency summaries. — Phase 3 context and research require one reusable substrate contract so every candidate uses the same checkpoint, tolerance, telemetry, and delay-semantics language instead of bespoke dicts.
- [Phase 03]: Keep accepted-step viability summaries separate from all-attempt traces so rejected and disqualified attempts remain visible without polluting latency gates. — D-02 and D-03 require median/p95/p99 latency to use accepted attempts only while fallback, hidden failure, and rejection evidence stays explicit in the benchmark trace.
- [Phase 03]: Keep the Phase 3 benchmark canon fixed to exactly three checkpoint-first workloads with explicit multi-tag coverage rows. — The locked Phase 3 context prefers a deliberately small canonical suite, so the implementation encodes exactly three reusable workloads and makes scenario coverage explicit in a machine-readable matrix instead of expanding the suite ad hoc.
- [Phase 03]: Reject candidate and workload fairness mismatches before execution so checkpoints, tolerances, physical-acceptance profiles, telemetry versions, and delay semantics cannot drift per candidate. — Phase 3 requires fair substrate comparison under one shared contract, so the reusable harness validates fairness metadata eagerly rather than relying on wrapper discipline or post-hoc report inspection.
- [Phase 03]: Make the macro benchmark example a thin wrapper that returns JSON-serializable attempt-record summaries from the reusable Phase 3 harness. — The example benchmark must stop being a disconnected smoke stub; returning serialized harness traces keeps example behavior aligned with the reusable substrate and gives Phase 3 reporting work one stable summary shape.
- [Phase 03]: Separate minimum viability from headline target in benchmark reports — Reports now keep minimum_rtf_gate=4.0 distinct from headline_rtf_target=100.0 so viability and aspirational headroom stay explicit.
- [Phase 03]: Keep disqualified baseline visible but unranked — Phase 3 reporting now always shows the disciplined split/SciPy baseline while excluding producer-backed disqualified runs from `candidate_rankings`.
- [Phase 04]: Keep `hybrid_coupled` as the default kernel direction while separating architecture direction from solver-stack escalation. — The public decision surface and roadmap now freeze `hybrid_coupled` as the default direction unless benchmark evidence disproves it.
- [Phase 04]: Leave SciPy only when Phase 3 gates miss and profiling shows `solver_core_fraction >= 0.5`; try `sundials4py` before PETSc. — The reusable decision gate, public wrapper, and docs now enforce `sundials4py` as the first post-SciPy path and keep `petsc4py` later-only.
- [Phase 05]: Keep the Phase 5 runnable comparison set hard-coded and phase-local instead of introducing discovery or registry logic.
- [Phase 05]: Preserve public slot ids as disciplined_split, sundials4py, and petsc4py while recording concrete bindings separately as split_kernel_adapter, scikits.odes.ida, and petsc4py.PETSc.SNES.
- [Phase 05]: Preserve external transport-history delay semantics by reusing runtime export/restore payloads instead of inventing a new delay model.
- [Phase 05]: Implement PETSc as a lazy-imported SNES adapter over the compiled hydraulic residual/Jacobian seam so the public runtime facade stays unchanged. — Phase 5 requires a real PETSc-backed comparison candidate behind the existing CandidateKernelAdapter seam, and lazy import keeps the facade stable while allowing test doubles in environments without a native PETSc install.
- [Phase 05]: Reuse the existing external transport-history delay bundle and validated snapshot restore path for PETSc so same-canon fairness remains checkpoint-first. — D-08 and D-09 require every runnable comparison candidate to start from comparable accepted snapshots and delay payloads rather than a PETSc-specific fresh-start path.
- [Phase 05]: Keep the Phase 5 benchmark wrapper hard-coded to disciplined_split, sundials4py, and petsc4py using explicit factories instead of discovery or registry logic.
- [Phase 05]: Preserve failed or disqualified candidate visibility by reusing the Phase 3 report surface and filtering nullable aggregate latency fields instead of dropping candidates.
- [Phase 01]: Keep Wave 0 on one shared failure-taxonomy contract module and checkpoint-first pytest fixtures; later Phase 1 plans should extend those names instead of redefining ad hoc dicts.
- [Phase 01]: Normalize structural failures through one dedicated translator module so barrier, compile, invariant, and hydraulic rejection payloads share explicit pre-step semantics instead of relying on string parsing.
- [Phase 01]: Run structural preflight before both ConnectionNetwork.step() and ConnectedPlantOrchestrator.step() so structural invalidity never reaches subsystem phases or connection macro-coupling work.
- [Phase 01]: Carry Phase 1 runtime-step rejection metadata on one dedicated diagnostic payload helper so MacroCoupler failures expose failure family, executed sequence, fallback keys, Picard status, and residual context without string parsing. — Plan 01-03 required machine-readable runtime-step evidence for D-01 and D-08 while keeping macro-coupler behavior compatible with later benchmark work.
- [Phase 01]: Build canonical Phase 1 evidence as scenario rows that mutate checkpoint-first runtime fixtures per scenario class and assert selected replay hashes plus bookkeeping expectations rather than gameplay-side snapshots. — Plan 01-03 required deterministic reproduction for D-02 and D-07, so checkpoint and replay-hash evidence needed to stay explicit in one reusable scenario matrix.
- [Phase 01]: Plant-level physical guards evaluate actual process model state, not clipped observability projections; guard ordering prioritizes masking/zero-inventory detection before composition normalization. — Plan 01-04 required that observability clipping alone cannot make a non-physical state look acceptable.

### Pending Todos

None yet.

### Blockers/Concerns

- Deadtime/transport-delay semantics must stay explicit in benchmark and migration planning, especially for hybrid or whole-flowsheet coupling.

### Roadmap Evolution

- Phase 5 added: Runnable solver candidates

## Session Continuity

Last session: 2026-03-31T01:09:00.000Z
Stopped at: Completed 01-04-PLAN.md
Resume file: None

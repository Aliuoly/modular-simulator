---
phase: 04-hybrid-decision-gate-migration-roadmap
plan: 02
subsystem: testing
tags: [benchmarking, roadmap, scipy, sundials4py, petsc4py]
requires:
  - phase: 04-hybrid-decision-gate-migration-roadmap
    provides: reusable Phase 4 decision gate over the verified Phase 3 benchmark surface
provides:
  - thin public Phase 4 decision wrapper over the Phase 3 benchmark substrate
  - grep-verifiable kernel-direction decision documentation
  - facade-preserving migration roadmap with explicit solver-stack ordering
affects: [phase-4, migration-roadmap, kernel-direction-decision, benchmark-evidence]
tech-stack:
  added: []
  patterns:
    - keep Phase 4 public output as a thin wrapper over Phase 3 benchmark evidence plus the reusable decision gate
    - freeze roadmap guidance with direct test coverage over docs and public output shape
key-files:
  created:
    - examples/connection_layer/benchmarks/kernel_direction_decision.py
    - docs/kernel_direction_decision.md
    - docs/kernel_migration_roadmap.md
    - tests/connection/test_kernel_direction_decision_example.py
  modified: []
key-decisions:
  - "Expose one public decision surface with exact top-level keys `phase3_report`, `decision`, `migration_candidates`, and `roadmap_stages` so Phase 4 guidance is reproducible rather than implicit."
  - "Keep `sundials4py` as the first post-SciPy path and describe `petsc4py` only as later escalation after benchmark justification."
patterns-established:
  - "Wave 2 docs are enforced by pytest reading the markdown files directly, not by manual review."
  - "Migration guidance preserves `PlantBackendSession` and the `CandidateKernelAdapter` seam while separating `hybrid_coupled` architecture direction from solver-stack escalation."
requirements-completed: [PERF-05, SOLV-04, SOLV-05]
duration: 6 min
completed: 2026-03-30
---

# Phase 4 Plan 2: Decision example and migration docs summary

**Thin Phase 4 decision wrapper, exact migration candidate matrix, and facade-preserving roadmap docs grounded in the Phase 3 benchmark canon**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-30T11:59:42Z
- **Completed:** 2026-03-30T12:05:01Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Added a thin `run_kernel_direction_decision()` wrapper that reuses the Phase 3 benchmark runner plus the reusable Phase 4 decision gate.
- Published a fixed three-row migration candidate matrix for `disciplined_scipy`, `sundials4py`, and `petsc4py` on the same Phase 3 workload basis.
- Added direct regression coverage for the public decision output and both roadmap docs so the solver-stack ordering and facade-preservation rules stay grep-verifiable.
- Closed the direct-PETSc policy leak in the reusable decision gate so `sundials4py` remains the first escalation path everywhere, not just in the public wrapper/docs.

## Task Commits

Each task was committed atomically:

1. **Task 1: Write failing tests for the Phase 4 decision example and roadmap docs** - `1af3cef` (test)
2. **Task 2: Implement the thin Phase 4 decision example and publish the migration docs** - `ef0f8c7` (feat)

_Note: Task 1 followed RED -> GREEN across the task commits._

## Files Created/Modified
- `examples/connection_layer/benchmarks/kernel_direction_decision.py` - thin public Phase 4 wrapper returning the fixed decision payload, migration matrix, and roadmap stages
- `docs/kernel_direction_decision.md` - documents the exact workload canon, `hybrid_coupled` default direction, and the evidence bar for leaving SciPy
- `docs/kernel_migration_roadmap.md` - stages `disciplined_scipy` hardening, `hybrid_coupled` default direction, `sundials4py` exploration, and PETSc later-only escalation
- `tests/connection/test_kernel_direction_decision_example.py` - freezes the public output shape and required doc strings by reading markdown files directly

## Decisions Made
- Kept the example wrapper thin by delegating benchmark work to `run_benchmark()` and decision logic to `build_kernel_direction_decision(...)` instead of reimplementing either layer.
- Returned `needs_more_evidence` from the public decision example by passing `solver_core_fraction=None`, which keeps SciPy as the current recommendation until explicit profiling proves solver-core dominance.
- Locked roadmap language to preserve `PlantBackendSession` and the `CandidateKernelAdapter` seam across any later stack migration.
- Removed the evaluator's direct `petsc4py` first-recommendation path and covered that forbidden case with a regression test so the reusable policy matches the published roadmap.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Corrected one typo in the internal `roadmap_stages` label from `discipled_scipy_hardening` to `disciplined_scipy_hardening` before final verification.
- Corrected a reviewer-found policy mismatch where the reusable decision gate still allowed direct `petsc4py` escalation; fixed by always recommending `sundials4py` first and syncing validation state.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 4 now has one reproducible public decision surface plus exact docs that lock in the migration sequence and workload basis.
- The phase is ready for final verification and milestone tracking updates.

## Self-Check: PASSED

- Verified `examples/connection_layer/benchmarks/kernel_direction_decision.py` exists.
- Verified `docs/kernel_direction_decision.md` exists.
- Verified `docs/kernel_migration_roadmap.md` exists.
- Verified `uv run python -m pytest tests/connection/test_kernel_direction_decision_example.py tests/connection/test_benchmark_decision_gate.py tests/connection/test_benchmark_reporting.py tests/connection/test_examples_benchmarks.py -q` passes (`21 passed`).

---
*Phase: 04-hybrid-decision-gate-migration-roadmap*
*Completed: 2026-03-30*

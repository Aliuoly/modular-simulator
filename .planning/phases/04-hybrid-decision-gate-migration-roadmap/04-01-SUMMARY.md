---
phase: 04-hybrid-decision-gate-migration-roadmap
plan: 01
subsystem: testing
tags: [benchmarking, decision-gate, scipy, sundials4py, roadmap]
requires:
  - phase: 03-benchmark-harness-disciplined-baseline-comparison
    provides: reusable benchmark report surface, workload canon, and latency gates
provides:
  - machine-readable kernel direction decision contract over Phase 3 benchmark evidence
  - explicit SciPy sufficiency, solver-limited, and needs-more-evidence policy rules
  - public benchmark package exports for the Phase 4 decision evaluator
affects: [phase-4, migration-roadmap, kernel-direction-decision]
tech-stack:
  added: []
  patterns:
    - keep kernel architecture direction separate from solver-stack recommendation
    - derive Phase 4 decisions from the existing Phase 3 report shape instead of a new benchmark layer
key-files:
  created:
    - src/modular_simulation/connection/benchmarking/decision_gate.py
    - tests/connection/test_benchmark_decision_gate.py
  modified:
    - src/modular_simulation/connection/benchmarking/__init__.py
key-decisions:
  - "Always keep `default_kernel_direction` fixed at `hybrid_coupled` even when the near-term solver recommendation remains on SciPy."
  - "Only recommend `sundials4py` when the disciplined split baseline misses the Phase 3 gates and profiling shows solver-core dominance at or above 0.5."
patterns-established:
  - "Phase 4 decision helpers consume `candidate_rankings`, `coverage_matrix`, `minimum_rtf_gate`, and `latency_budget_fraction` from the Phase 3 report surface."
  - "PETSc remains visible only as later escalation metadata rather than the first post-SciPy recommendation."
requirements-completed: [PERF-05, SOLV-05]
duration: 1 min
completed: 2026-03-30
---

# Phase 4 Plan 1: Kernel direction decision gate summary

**Machine-readable Phase 4 kernel-direction policy that preserves `hybrid_coupled`, judges SciPy from Phase 3 evidence, and exposes `sundials4py` as the first post-SciPy path**

## Performance

- **Duration:** 1 min
- **Started:** 2026-03-30T11:57:38Z
- **Completed:** 2026-03-30T11:58:42Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Added a reusable `decision_gate.py` module with typed decision and profiling contracts for the Phase 4 kernel-direction judgment.
- Wrote regression tests that pin the exact Phase 4 decision surface for viable SciPy, solver-limited escalation, later PETSc escalation, and missing-evidence handling.
- Exported the new decision helpers from the benchmarking package so the Phase 4 example and docs can reuse one stable policy surface.

## Task Commits

Each task was committed atomically:

1. **Task 1: Write failing decision-gate tests for SciPy sufficiency and escalation triggers** - `284f716` (test)
2. **Task 2: Implement the reusable Phase 4 decision evaluator and public export surface** - `496c762` (feat)

_Note: Task 1 followed RED -> GREEN across the two task commits._

## Files Created/Modified
- `src/modular_simulation/connection/benchmarking/decision_gate.py` - typed Phase 4 decision contract and evaluator over the Phase 3 report surface
- `tests/connection/test_benchmark_decision_gate.py` - regression coverage for sufficiency, solver-limited escalation, PETSc later-only policy, and missing-evidence handling
- `src/modular_simulation/connection/benchmarking/__init__.py` - re-exports the new decision-gate symbols from the benchmark package

## Decisions Made
- Kept architecture direction and solver-stack recommendation separate so `hybrid_coupled` stays the default roadmap direction even when SciPy remains sufficient.
- Required explicit profiling evidence before marking SciPy solver-limited; missing profiling now returns `needs_more_evidence` instead of forcing migration.
- Kept `petsc4py` out of the first recommendation path and surfaced it only as later escalation metadata.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 4 now has one reusable decision artifact that Wave 2 can present through an example wrapper and docs.
- The decision gate already exposes the exact workload ids and solver-stack ordering needed by the migration-documentation plan.

## Self-Check: PASSED

- Verified `src/modular_simulation/connection/benchmarking/decision_gate.py` exists.
- Verified `tests/connection/test_benchmark_decision_gate.py` exists.
- Verified `uv run python -m pytest tests/connection/test_benchmark_decision_gate.py -q` passes.
- Verified commits `284f716` and `496c762` exist in git history.

---
*Phase: 04-hybrid-decision-gate-migration-roadmap*
*Completed: 2026-03-30*

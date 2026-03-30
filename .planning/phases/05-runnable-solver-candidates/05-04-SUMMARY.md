---
phase: 05-runnable-solver-candidates
plan: 04
subsystem: benchmarking
tags: [benchmarking, sundials4py, petsc4py, reporting, phase5]
requires:
  - phase: 05-runnable-solver-candidates
    provides: hard-coded candidate ids plus runnable SUNDIALS and PETSc adapter implementations
provides:
  - Fixed three-candidate public benchmark wrapper over the Phase 3 canon
  - Regression coverage for explicit split/SUNDIALS/PETSc wiring and visible disqualification
  - Shared report aggregation that tolerates candidates with no accepted-step latency rows
affects: [phase-5-benchmark-surface, benchmark-reporting, solver-candidate-comparison]
tech-stack:
  added: []
  patterns: [phase-local explicit candidate factories, shared report reuse, visible disqualification retention]
key-files:
  created: []
  modified:
    - examples/connection_layer/benchmarks/macro_coupling_benchmark.py
    - tests/connection/test_examples_benchmarks.py
    - src/modular_simulation/connection/benchmarking/reporting.py
key-decisions:
  - "Keep the Phase 5 benchmark wrapper hard-coded to disciplined_split, sundials4py, and petsc4py using explicit factories instead of discovery or registry logic."
  - "Preserve failed or disqualified candidate visibility by reusing the Phase 3 report surface and filtering nullable aggregate latency fields instead of dropping candidates."
patterns-established:
  - "Phase-local benchmark wrappers should build candidate configs once, then iterate workloads through per-candidate factories."
  - "Aggregate benchmark summaries must tolerate candidates with no accepted-step latency values when failures remain visible in the report."
requirements-completed: [PERF-06]
duration: 3 min
completed: 2026-03-30
---

# Phase 5 Plan 4: Final three-candidate benchmark wrapper Summary

**Fixed same-canon benchmark wrapper comparing disciplined_split, sundials4py, and petsc4py with visible disqualification in the shared report surface**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-30T21:04:14Z
- **Completed:** 2026-03-30T21:07:55Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Added RED tests that freeze the exact three-candidate wrapper contract, canonical workload ids, visible disqualification, and explicit adapter wiring.
- Wired the public benchmark example to run disciplined split, SUNDIALS, and PETSc candidates through the same Phase 3 harness and report shape.
- Fixed aggregate reporting so candidates with no accepted-step latency remain visible instead of crashing or disappearing.

## Task Commits

Each task was committed atomically:

1. **Task 1: Write failing wrapper tests for the final three-candidate comparison surface** - `4f2c802` (test)
2. **Task 2: Wire the hard-coded three-candidate benchmark wrapper** - `1e931a9` (feat)

**Plan metadata:** Captured in the separate docs commit that records summary/state/roadmap updates.

## Files Created/Modified
- `tests/connection/test_examples_benchmarks.py` - Freezes the exact Phase 5 wrapper surface, fixed canon rows, and explicit split-vs-constructor wiring.
- `examples/connection_layer/benchmarks/macro_coupling_benchmark.py` - Runs all three Phase 5 candidates through the shared harness with phase-local explicit factories.
- `src/modular_simulation/connection/benchmarking/reporting.py` - Filters nullable latency aggregates so disqualified candidates still produce visible report rows.

## Decisions Made
- Kept candidate selection phase-local and explicit in the benchmark wrapper rather than adding registry or environment discovery logic.
- Reused `build_phase3_report()` for the final comparison surface so baseline visibility, per-workload rows, and disqualification behavior stay on the established contract.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Switched local verification to `uv run --no-sync` because synced PETSc dependency resolution fails in this environment**
- **Found during:** Task 1 (Write failing wrapper tests for the final three-candidate comparison surface)
- **Issue:** `uv run python -m pytest ...` attempted to build native `petsc`/`petsc4py` dependencies and failed before the wrapper tests could execute.
- **Fix:** Used `uv run --no-sync python -m pytest ...` for task and plan verification so the wrapper and reporting behavior could be validated against the already-available environment.
- **Files modified:** None
- **Verification:** `uv run --no-sync python -m pytest tests/connection/test_examples_benchmarks.py -q`; `uv run --no-sync python -m pytest tests/connection/test_examples_benchmarks.py tests/connection/test_kernel_direction_decision_example.py tests/connection/test_benchmark_reporting.py tests/connection/test_benchmark_harness.py -q`
- **Committed in:** 4f2c802, 1e931a9

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Verification routing changed to avoid an unrelated native dependency bootstrap failure; the benchmark surface and fairness contract landed as planned.

## Issues Encountered
- Aggregate reporting originally assumed every candidate had accepted-step latency values; once all three candidates were included, visible failure cases required filtering `None` latency entries during summary aggregation.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 5 now has the final same-canon public comparison surface required for milestone evidence.
- This phase is complete; roadmap/state can advance beyond runnable solver candidate implementation.

## Self-Check: PASSED

---
*Phase: 05-runnable-solver-candidates*
*Completed: 2026-03-30*

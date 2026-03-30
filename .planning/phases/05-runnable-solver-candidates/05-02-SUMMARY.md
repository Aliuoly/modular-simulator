---
phase: 05-runnable-solver-candidates
plan: "02"
subsystem: runtime
tags: [sundials, scikits.odes, ida, hydraulic-solver, benchmarking]
requires:
  - phase: 05-runnable-solver-candidates
    provides: "Phase 5 candidate-slot contract and dependency declarations from 05-01"
provides:
  - "Runnable SUNDIALS-backed CandidateKernelAdapter implementation"
  - "Restore and delay-state parity regression coverage for the SUNDIALS candidate"
affects: [phase-05, benchmarking, candidate-kernel-adapters]
tech-stack:
  added: []
  patterns: ["Compiled hydraulic residual/Jacobian callbacks wrapped behind CandidateKernelAdapter", "Checkpoint restore plus transport-history parity for runnable solver candidates"]
key-files:
  created: [src/modular_simulation/connection/runtime/sundials_kernel_adapter.py, tests/connection/test_sundials_kernel_adapter.py]
  modified: [src/modular_simulation/connection/runtime/sundials_kernel_adapter.py, tests/connection/test_sundials_kernel_adapter.py]
key-decisions:
  - "Use scikits.odes IDA as the concrete SUNDIALS binding while keeping the candidate behind the existing adapter seam."
  - "Preserve external transport-history delay semantics by reusing runtime export/restore payloads instead of inventing a new delay model."
patterns-established:
  - "Runnable solver candidates restore accepted snapshots through network.restore_validated_runtime_snapshot before candidate stepping."
  - "Phase 5 adapter tests may use uv --no-sync when heavy native dependencies would otherwise block unrelated RED/GREEN verification."
requirements-completed: [SOLV-06, DELY-05]
duration: 4 min
completed: 2026-03-30
---

# Phase 5 Plan 2: Runnable SUNDIALS candidate Summary

**SUNDIALS IDA candidate adapter over the compiled hydraulic system with checkpoint restore parity and transport-history delay-state round-tripping**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-30T20:51:47Z
- **Completed:** 2026-03-30T20:56:39Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Added RED-phase regression coverage for accepted-snapshot restore, delay-state parity, finite solver telemetry, and optional capability publication.
- Implemented `SundialsIdaKernelAdapter` as a real candidate adapter using compiled hydraulic residual and Jacobian callbacks.
- Kept the candidate on the existing runtime seam by restoring accepted snapshots and transport history through existing network/runtime helpers.

## Task Commits

Each task was committed atomically:

1. **Task 1: Write failing SUNDIALS-adapter restore and telemetry tests** - `a74a83b` (test)
2. **Task 2: Implement the SUNDIALS-backed adapter on the compiled hydraulic seam** - `aa0f65b` (feat)

**Plan metadata:** recorded in the final docs commit after state updates

## Files Created/Modified
- `tests/connection/test_sundials_kernel_adapter.py` - TDD coverage for restore parity, delay-state round-trip, telemetry finiteness, and optional capabilities.
- `src/modular_simulation/connection/runtime/sundials_kernel_adapter.py` - Concrete SUNDIALS IDA-backed candidate adapter using compiled hydraulic callbacks.

## Decisions Made
- Used `scikits.odes` IDA as the concrete SUNDIALS binding because it matches the residual/Jacobian-shaped compiled hydraulic seam.
- Kept delay semantics as `EXTERNAL_TRANSPORT_HISTORY` and reused runtime transport payload export/restore to preserve benchmark fairness.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Bypassed native PETSc sync during SUNDIALS test verification**
- **Found during:** Task 1 (Write failing SUNDIALS-adapter restore and telemetry tests)
- **Issue:** `uv run` attempted to sync Phase 5 native solver dependencies and failed while building `petsc/petsc4py`, preventing the RED test from reaching the intended missing-adapter failure.
- **Fix:** Switched task-local verification to `uv run --no-sync python -m pytest ...` so the existing environment could execute the targeted adapter tests without unrelated native builds.
- **Files modified:** None
- **Verification:** `uv run --no-sync python -m pytest tests/connection/test_sundials_kernel_adapter.py -q`, `uv run --no-sync python -m pytest tests/connection/test_sundials_kernel_adapter.py tests/connection/test_benchmark_harness.py -q`
- **Committed in:** `a74a83b` (workflow-only adjustment during task verification)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Verification stayed focused on the SUNDIALS adapter slice; no code scope changed.

## Issues Encountered
- `uv run` tried to build PETSc-related dependencies before test collection. Using `--no-sync` kept the plan runnable in the current environment.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 5 now has a runnable SUNDIALS-backed candidate behind the shared adapter seam.
- Ready for 05-03 PETSc adapter work and later multi-candidate benchmark wiring in 05-04.

## Self-Check: PASSED
- FOUND: `src/modular_simulation/connection/runtime/sundials_kernel_adapter.py`
- FOUND: `tests/connection/test_sundials_kernel_adapter.py`
- FOUND: `a74a83b`
- FOUND: `aa0f65b`

---
*Phase: 05-runnable-solver-candidates*
*Completed: 2026-03-30*

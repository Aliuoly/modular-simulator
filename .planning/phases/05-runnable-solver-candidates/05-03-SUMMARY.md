---
phase: 05-runnable-solver-candidates
plan: 03
subsystem: api
tags: [petsc, petsc4py, snes, benchmarking, hydraulics]
requires:
  - phase: 05-runnable-solver-candidates
    provides: hard-coded Phase 5 candidate ids and truthful implementation-binding metadata
provides:
  - Runnable PETSc-backed candidate adapter behind the existing kernel-adapter seam
  - Regression coverage for snapshot restore, delay-state parity, finite telemetry, and policy-order preservation
affects: [phase-5-benchmark-surface, benchmark-harness, candidate-adapters]
tech-stack:
  added: [petsc4py, PETSc.SNES]
  patterns: [lazy native dependency import, compiled hydraulic callback reuse, external transport-history parity]
key-files:
  created:
    - src/modular_simulation/connection/runtime/petsc_kernel_adapter.py
    - tests/connection/test_petsc_kernel_adapter.py
  modified: []
key-decisions:
  - "Implement PETSc as a lazy-imported SNES adapter over the compiled hydraulic residual/Jacobian seam so the public runtime facade stays unchanged."
  - "Reuse the existing external transport-history delay bundle and validated snapshot restore path for PETSc so same-canon fairness remains checkpoint-first."
patterns-established:
  - "Runnable solver candidates can expose optional state/residual/Jacobian capabilities while still honoring the core warm-start and delay-state contract."
  - "Native solver bindings should be wrapped behind test-double-tolerant shims so contract tests stay runnable without the real native library present."
requirements-completed: [SOLV-06, DELY-05]
duration: 6 min
completed: 2026-03-30
---

# Phase 5 Plan 3: PETSc runnable adapter Summary

**PETSc SNES candidate adapter with accepted-snapshot restore, external transport-history parity, and finite hydraulic callback telemetry**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-30T20:51:53Z
- **Completed:** 2026-03-30T20:58:10Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Added RED-phase PETSc adapter regression tests that freeze restore parity, delay-state round-tripping, finite telemetry, and migration-order expectations.
- Implemented `PetscSnesKernelAdapter` as a real `CandidateKernelAdapter` using `petsc4py.PETSc.SNES` over compiled hydraulic residual and Jacobian callbacks.
- Preserved the checkpoint-first fairness contract by reusing validated snapshot restore and external transport-history delay-state handling.

## Task Commits

Each task was committed atomically:

1. **Task 1: Write failing PETSc-adapter restore and telemetry tests** - `e3409ee` (test)
2. **Task 2: Implement the PETSc-backed adapter on the compiled hydraulic seam** - `4825a67` (feat)

**Plan metadata:** `PENDING`

## Files Created/Modified
- `tests/connection/test_petsc_kernel_adapter.py` - RED/GREEN regression coverage for snapshot restore, delay-state parity, PETSc telemetry, and candidate-order policy.
- `src/modular_simulation/connection/runtime/petsc_kernel_adapter.py` - Runnable PETSc SNES candidate adapter with lazy PETSc import, residual/Jacobian callbacks, telemetry capture, and optional capability support.

## Decisions Made
- Used lazy `petsc4py` imports inside the adapter so the runtime/session facade remains unchanged and tests can supply lightweight PETSc doubles.
- Reused `network.restore_validated_runtime_snapshot(...)` plus the split adapter’s external transport-history pattern instead of inventing a PETSc-specific restore or delay model.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Switched verification to `uv run --no-sync` because PETSc native dependency sync failed in this environment**
- **Found during:** Task 1 (Write failing PETSc-adapter restore and telemetry tests)
- **Issue:** `uv run python -m pytest ...` attempted to build `petsc4py`/`petsc` and failed before tests executed because the environment lacks a functional BLAS-backed PETSc build path.
- **Fix:** Used `uv run --no-sync python -m pytest ...` for task verification so the RED/GREEN cycle validated the intended missing-adapter and implemented-adapter behavior without changing project dependencies or weakening test assertions.
- **Files modified:** None
- **Verification:** `uv run --no-sync python -m pytest tests/connection/test_petsc_kernel_adapter.py -q`; `uv run --no-sync python -m pytest tests/connection/test_petsc_kernel_adapter.py tests/connection/test_benchmark_harness.py -q`
- **Committed in:** e3409ee, 4825a67 (task commits)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Verification command routing changed to bypass environment bootstrap only; implementation scope and fairness contract remained exactly on plan.

## Issues Encountered
- Native `petsc4py` resolution currently tries to build PETSc from source and fails on missing BLAS support in this environment. The adapter itself remains lazily imported and testable through monkeypatched PETSc doubles.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- PETSc is now a runnable comparison candidate behind `CandidateKernelAdapter` and is ready to be wired into the Phase 5 three-candidate benchmark surface.
- Full synced verification still depends on a working native PETSc toolchain in the execution environment.

## Self-Check: PASSED

---
*Phase: 05-runnable-solver-candidates*
*Completed: 2026-03-30*

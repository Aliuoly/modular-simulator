---
phase: 05-runnable-solver-candidates
plan: "01"
subsystem: benchmarking
tags: [phase-5, solver-candidates, sundials, petsc, benchmarking]
requires:
  - phase: 04-hybrid-decision-gate-migration-roadmap
    provides: hard-coded migration order and solver escalation policy for SUNDIALS then PETSc
provides:
  - Hard-coded Phase 5 candidate slot contract for disciplined split, SUNDIALS, and PETSc comparison
  - Truthful implementation-binding metadata for roadmap-stable public candidate IDs
  - Per-workload candidate config builder that preserves fairness metadata from canonical workloads
affects: [phase-5-adapter-work, benchmark-surface, runtime-candidates]
tech-stack:
  added: [scikits.odes, petsc, petsc4py]
  patterns: [phase-local hard-coded candidate selection, truthful binding metadata beside stable public ids]
key-files:
  created: [src/modular_simulation/connection/benchmarking/runnable_candidate_contracts.py, tests/connection/test_runnable_candidate_contracts.py]
  modified: [pyproject.toml, src/modular_simulation/connection/benchmarking/__init__.py]
key-decisions:
  - "Keep the Phase 5 runnable comparison set hard-coded and phase-local instead of introducing discovery or registry logic."
  - "Preserve public slot ids as disciplined_split, sundials4py, and petsc4py while recording concrete bindings separately as split_kernel_adapter, scikits.odes.ida, and petsc4py.PETSc.SNES."
patterns-established:
  - "Phase 5 candidate contracts build BenchmarkCandidateConfig values by copying workload fairness fields verbatim."
  - "Public comparison ids remain roadmap-stable even when implementation bindings are more specific than the display label."
requirements-completed: [SOLV-06]
duration: 3 min
completed: 2026-03-30
---

# Phase 5 Plan 01: Runnable candidate contract summary

**Hard-coded Phase 5 solver candidate slots with truthful SUNDIALS and PETSc binding metadata plus fairness-preserving config builders.**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-30T20:45:00Z
- **Completed:** 2026-03-30T20:48:35Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Froze the Phase 5 candidate slot order in a dedicated regression test file before implementation.
- Added a reusable `RunnableCandidateDefinition` contract and `build_phase5_candidate_configs()` helper for per-workload benchmark configs.
- Declared the planned `scikits.odes`, `petsc`, and `petsc4py` dependencies so upcoming adapter plans can build against explicit package names.

## Task Commits

Each task was committed atomically:

1. **Task 1: Freeze the Phase 5 candidate-slot contract in failing tests** - `dbb1947` (test)
2. **Task 2: Implement the Phase 5 contract module and dependency declarations** - `d72a81a` (feat)

**Plan metadata:** Pending final docs commit after state and roadmap updates.

## Files Created/Modified
- `tests/connection/test_runnable_candidate_contracts.py` - TDD contract tests for candidate order, truthful bindings, fairness-field copying, and dependency declarations.
- `src/modular_simulation/connection/benchmarking/runnable_candidate_contracts.py` - Phase 5 runnable candidate definitions, stable public slot order, and workload-driven config builder.
- `src/modular_simulation/connection/benchmarking/__init__.py` - Public exports for the new Phase 5 candidate contract helpers.
- `pyproject.toml` - Declares `scikits.odes`, `petsc`, and `petsc4py` for upcoming runnable adapter work.

## Decisions Made
- Kept the Phase 5 comparison surface explicit and phase-local so downstream plans inherit one reproducible candidate set rather than a registry or discovery mechanism.
- Preserved roadmap-stable public ids while separating them from concrete implementation bindings to keep the comparison surface honest.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Avoided native PETSc builds during contract-only verification**
- **Found during:** Task 2 (Implement the Phase 5 contract module and dependency declarations)
- **Issue:** After adding `petsc` and `petsc4py` to `pyproject.toml`, `uv run` attempted a full dependency sync and failed while building native PETSc wheels before the lightweight contract tests could start.
- **Fix:** Switched this plan's verification command to `uv run --no-sync python -m pytest tests/connection/test_runnable_candidate_contracts.py -q` so the contract test runs against the existing environment while still validating the new declarations in `pyproject.toml`.
- **Files modified:** None
- **Verification:** `uv run --no-sync python -m pytest tests/connection/test_runnable_candidate_contracts.py -q`
- **Committed in:** d72a81a (part of task verification)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** No scope creep. The deviation only prevented premature native dependency builds from blocking a contract-only verification step.

## Issues Encountered
- Native PETSc packaging is not yet available in the current environment for automatic `uv` sync builds; adapter plans will need explicit environment handling when runnable PETSc work begins.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Ready for `05-02-PLAN.md`; the Phase 5 candidate ids, truthful bindings, and fairness-field contract are now fixed for SUNDIALS adapter work.
- Future runnable solver plans should expect native dependency/bootstrap work for SUNDIALS and PETSc rather than treating these declarations as pure-Python installs.

## Self-Check: PASSED

- Verified summary and key implementation files exist on disk.
- Verified task commits `dbb1947` and `d72a81a` exist in git history.
- Re-ran `uv run --no-sync python -m pytest tests/connection/test_runnable_candidate_contracts.py -q` successfully.

---
*Phase: 05-runnable-solver-candidates*
*Completed: 2026-03-30*

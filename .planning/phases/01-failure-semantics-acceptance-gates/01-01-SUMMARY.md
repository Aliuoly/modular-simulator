---
phase: 01-failure-semantics-acceptance-gates
plan: "01"
subsystem: simulation
tags: [phase1, failure-semantics, acceptance-gates, pytest, replay]

# Dependency graph
requires: []
provides:
  - Shared Phase 1 failure-family and scenario-class contracts
  - Checkpoint-first pytest fixture substrate for replay hashes and bookkeeping assertions
  - Collecting Phase 1 test modules for KERN-01, KERN-02, KERN-03, and KERN-05
affects: [phase-01-plan-02, phase-01-plan-03, phase-01-plan-04, acceptance-gates]

# Tech tracking
tech-stack:
  added: []
  patterns: [checkpoint-first Phase 1 fixtures, shared failure-taxonomy contracts, uv no-sync verification on existing Python 3.13 environment]

key-files:
  created:
    - src/modular_simulation/connection/domain/phase1_failure_semantics.py
    - tests/phase1/conftest.py
    - tests/phase1/test_failure_taxonomy.py
    - tests/phase1/test_structural_rejection.py
    - tests/phase1/test_macro_step_acceptance.py
    - tests/phase1/test_physical_acceptance.py
  modified:
    - .planning/phases/01-failure-semantics-acceptance-gates/01-01-SUMMARY.md
    - .planning/STATE.md
    - .planning/ROADMAP.md
    - .planning/REQUIREMENTS.md

key-decisions:
  - "Keep Phase 1 Wave 0 on shared dataclass and enum contracts backed by replay hashes and MacroStepBookkeeping, without introducing Phase 2 adapter abstractions."
  - "Use the repo's existing Python 3.13 uv environment with `--no-sync` for Wave 0 verification because synced uv resolution currently trips native solver dependency bootstrap unrelated to this plan."

patterns-established:
  - "Phase 1 scenarios are represented once as manifest rows that bind one scenario class, one primary failure family, and one expected acceptance gate."
  - "Phase 1 collecting tests depend on checkpoint/runtime fixtures and bookkeeping expectations rather than gameplay fixtures."

requirements-completed: [KERN-01, KERN-02, KERN-03, KERN-05]

# Metrics
duration: 13 min
completed: 2026-03-31
---

# Phase 1 Plan 1: Failure semantics substrate summary

**Shared Phase 1 failure-taxonomy contracts, checkpoint-first fixture helpers, and collecting pytest modules for the four locked kernel-correctness requirements.**

## Performance

- **Duration:** 13 min
- **Started:** 2026-03-31T00:05:12Z
- **Completed:** 2026-03-31T00:18:54Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments
- Added a dedicated `phase1_failure_semantics.py` contract module with the four locked failure families, four locked scenario classes, acceptance-gate metadata, and typed result objects for later Phase 1 waves.
- Added `tests/phase1/conftest.py` with canonical checkpoint-first helpers for scenario manifests, runtime snapshot export, replay-hash capture, and `MacroStepBookkeeping` expectation builders.
- Added four dedicated collecting test modules mapping directly to `KERN-01`, `KERN-02`, `KERN-03`, and `KERN-05`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create Phase 1 failure-semantics contracts and scenario substrate** - `476606e` (feat)
2. **Task 2: Add collecting Phase 1 pytest modules and Python 3.13 execution path** - `256ab6b` (test)

**Plan metadata:** captured in the separate docs commit for this plan.

## Files Created/Modified
- `src/modular_simulation/connection/domain/phase1_failure_semantics.py` - shared Wave 0 failure-family, scenario-class, and acceptance-result contracts.
- `tests/phase1/conftest.py` - checkpoint/runtime-based fixture builders for scenario manifests, snapshot export, replay hashes, and bookkeeping expectations.
- `tests/phase1/test_failure_taxonomy.py` - collecting `KERN-01` contract coverage for scenario-manifest coverage, replay hashes, and bookkeeping-backed evidence.
- `tests/phase1/test_structural_rejection.py` - collecting `KERN-03` contract coverage for pre-step structural rejection semantics.
- `tests/phase1/test_macro_step_acceptance.py` - collecting `KERN-02` contract coverage for one accepted snapshot and rollback-on-reject semantics.
- `tests/phase1/test_physical_acceptance.py` - collecting `KERN-05` contract coverage for negative inventory, normalization, non-finite, and masking rejection cases.

## Decisions Made
- Kept Phase 1 Wave 0 focused on one shared contract module and pytest substrate only, matching the plan's boundary and avoiding solver-adapter abstractions from Phase 2.
- Left `pyproject.toml` unchanged because the repo already declares Python 3.13 and pytest-compatible dev configuration for this wave.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Verified through `uv --no-sync` to avoid unrelated native solver bootstrap during Phase 1 collection**
- **Found during:** Task 1 and Task 2 verification
- **Issue:** The plan's literal `uv run --python 3.13 ...` sync path attempted to resolve native solver dependencies and failed before Phase 1 collection, even though the repo already had a valid Python 3.13 `.venv` for this work.
- **Fix:** Used `uv run --python 3.13 --no-sync ...` for verification so the existing project environment executed the required collection checks without changing later-phase solver packaging.
- **Files modified:** None
- **Verification:** `uv run --python 3.13 --no-sync python --version`; `uv run --python 3.13 --no-sync python -m pytest tests/phase1 --collect-only -q`
- **Committed in:** `476606e`, `256ab6b`

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** No scope creep. The deviation only changed verification routing around an environment sync problem and intentionally avoided touching validated later-phase solver work.

## Issues Encountered
- The synced `uv` resolution path currently reports `modular-simulation[candidate-solvers]` and attempts native PETSc bootstrap in this environment; the existing `.venv` already satisfies this plan's Python 3.13 collection needs.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 1 now has one importable contract surface and a reusable pytest substrate for later structural rejection, runtime classification, macro-step acceptance, and physical-acceptance implementation waves.
- `01-02-PLAN.md` can now build real structural rejection routing on top of the dedicated `tests/phase1/` suite.

## Self-Check: PASSED

- Verified all six key implementation files exist on disk.
- Verified task commits `476606e` and `256ab6b` exist in git history.
- Verified the repo's existing Python 3.13 uv environment collects all four Phase 1 modules successfully.

---
*Phase: 01-failure-semantics-acceptance-gates*
*Completed: 2026-03-31*

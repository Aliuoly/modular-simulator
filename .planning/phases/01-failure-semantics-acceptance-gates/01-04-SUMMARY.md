---
phase: 01-failure-semantics-acceptance-gates
plan: "04"
subsystem: simulation
tags: [phase1, failure-semantics, physical-acceptance, macro-step-transaction, pytest]

# Dependency graph
requires:
  - phase: 01-01
    provides: Shared Phase 1 failure taxonomy contracts and checkpoint-first replay fixture substrate
  - phase: 01-02
    provides: Structural pre-step rejection routing and barrier failure translation
  - phase: 01-03
    provides: Runtime diagnostic classification, replay-backed scenario evidence
provides:
  - Plant-level physical acceptance guards that reject non-physical candidate states before accepted-state publication
  - Whole-plant macro-step acceptance transaction with rollback-on-reject using existing save/restore contract
  - Explicit rejection for negative inventory, invalid composition normalization, non-finite values, and masking/fallback artifacts
affects: [phase-01-complete, acceptance-gates, physical-acceptance, macro-step-transaction]

# Tech tracking
tech-stack:
  added: []
  patterns: [plant-level physical guard evaluation before publication, optimistic execute + rollback-on-reject transaction, structured rejection codes]

key-files:
  created:
    - src/modular_simulation/connection/domain/plant_physical_acceptance.py
    - .planning/phases/01-failure-semantics-acceptance-gates/01-04-SUMMARY.md
  modified:
    - src/modular_simulation/connection/runtime/connected_plant_orchestrator.py
    - src/modular_simulation/connection/runtime/macro_step_acceptance.py
    - tests/phase1/test_macro_step_acceptance.py
    - tests/phase1/test_physical_acceptance.py
    - .planning/STATE.md

key-decisions:
  - "Plant-level physical guards evaluate actual process model state, not clipped observability projections, ensuring masking or clipping cannot make a non-physical state look acceptable."
  - "Physical acceptance check ordering prioritizes masking/zero-inventory detection before composition normalization so zero-everywhere states get the more specific MASKING_OR_FALLBACK_EVIDENCE code."

patterns-established:
  - "Physical guards run after candidate macro-step execution but before accepted-state publication, leveraging the existing rollback capsule for automatic state restoration on rejection."

requirements-completed: [KERN-02, KERN-05]

# Metrics
duration: 22 min
completed: 2026-03-31
---

# Phase 1 Plan 4: Whole-plant acceptance boundary and physical guards summary

**Macro-step transactional acceptance with explicit plant-level physical rejection guards for non-physical states.**

## Performance

- **Duration:** 22 min
- **Started:** 2026-03-31T00:47:19Z
- **Completed:** 2026-03-31T01:09:00Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments
- Implemented whole-plant macro-step acceptance transaction using the existing save/restore contract as the Phase 1 oracle, ensuring rejected steps fully rollback to the pre-step state.
- Added plant-level physical acceptance guards that check negative inventory, invalid composition normalization, non-finite values, and masking/fallback evidence before accepted-state publication.
- Verified the complete Phase 1 acceptance suite: 30 tests across 4 test modules, plus 63 tests when combined with the barrier-translation regression suites.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add whole-plant macro-step acceptance transaction with rollback-on-reject** - `1e1e282` (test), `c746a12` (feat)
2. **Task 2: Add explicit plant-level physical acceptance guards before publication** - `e0daa20` (feat)
3. **Task 3: Prove accepted-state publication and physical rejection behavior end-to-end** - verified via combined suite run (no separate commit needed; test coverage already present)

## Files Created/Modified
- `src/modular_simulation/connection/domain/plant_physical_acceptance.py` - evaluates plant-level physical validity for negative inventory, invalid composition normalization, non-finite values, and masking/fallback evidence.
- `src/modular_simulation/connection/runtime/connected_plant_orchestrator.py` - wires physical acceptance guard after candidate execution but before accepted-state publication, preserving rollback-on-reject transaction semantics.
- `src/modular_simulation/connection/runtime/macro_step_acceptance.py` - rollback capsule and accepted-publication transaction helpers (from Task 1).
- `tests/phase1/test_macro_step_acceptance.py` - three regression tests proving rejected steps restore pre-step snapshot, accepted steps publish exactly one new snapshot, and second run after rejection starts from restored state.
- `tests/phase1/test_physical_acceptance.py` - four parametrized rejection tests covering negative inventory, invalid composition, non-finite state, and masking/fallback evidence.
- `.planning/STATE.md` - advances Phase 1 to complete.

## Decisions Made
- Guard evaluation uses actual process model fields (holdup_component_moles, outlet_composition, temperature, holdup_temperature), not the clipped observability projections, so observability clipping alone cannot mask non-physical state.
- Zero-inventory + zero-composition is detected as MASKING_OR_FALLBACK_EVIDENCE before the composition normalization check, giving the more specific diagnostic code for this important edge case.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Reused the active Python 3.13 environment with `uv --active --no-sync` for verification**
- **Found during:** All task verifications
- **Issue:** Plain `uv run --python 3.13 ...` still attempts to sync unconditional PETSc dependencies before pytest starts in this workspace.
- **Fix:** Re-ran the plan's verification commands through `uv run --python 3.13 --active --no-sync ...`, which uses the already working local Python 3.13 environment without modifying dependency configuration.
- **Files modified:** None
- **Verification:** `uv run --python 3.13 --active --no-sync python -m pytest tests/phase1/ -q` (30 passed); combined regression suite (63 passed)
- **Committed in:** `e0daa20`

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** No scope creep. The deviation only changed verification routing around the local dependency-sync blocker and preserved the intended test coverage.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 1 is now fully executed: failure taxonomy contracts (01-01), structural rejection routing (01-02), runtime diagnostics and replay evidence (01-03), and whole-plant acceptance with physical guards (01-04) are all complete.
- KERN-01, KERN-02, KERN-03, and KERN-05 are satisfied at the Phase 1 acceptance boundary.
- The `/gsd-validate-phase 1` workflow can now be re-run to update the validation file from its current blocked/audited state to reflect actual execution evidence.

## Self-Check: PASSED

- Verified `.planning/phases/01-failure-semantics-acceptance-gates/01-04-SUMMARY.md` and `src/modular_simulation/connection/domain/plant_physical_acceptance.py` exist on disk.
- Verified task commits `1e1e282`, `c746a12`, and `e0daa20` exist in git history.
- Verified the required Phase 01 Plan 04 verification commands pass in the repo's active Python 3.13 uv environment: 30 Phase 1 tests pass, 63 combined regression tests pass.

---
*Phase: 01-failure-semantics-acceptance-gates*
*Completed: 2026-03-31*

---
phase: 02-kernel-adapter-warm-starts-delay-state
plan: 02
subsystem: runtime
tags: [kernel-adapter, warm-start, checkpoint, restore, backend-session]
requires:
  - phase: 02-01
    provides: capability-first kernel adapter core and split runtime baseline adapter
provides:
  - canonical adapter-owned restore helper for accepted snapshots
  - save/load and recovery wiring through one warm-start path
  - explicit failure coverage for unsafe restores
affects: [phase-02-plan-03, delay-state-restore, backend-session]
tech-stack:
  added: []
  patterns: [canonical checkpoint-based warm-start restore, explicit warm-start failure reporting]
key-files:
  created:
    - src/modular_simulation/connection/runtime/kernel_adapter_restore.py
    - tests/connection/test_kernel_adapter_restore.py
  modified:
    - src/modular_simulation/connection/topology/network.py
    - src/modular_simulation/cli/backend_session.py
    - src/modular_simulation/connection/runtime/split_kernel_adapter.py
    - tests/cli/test_backend_session.py
key-decisions:
  - "Normalize checkpoint envelopes to the live runtime snapshot shape before calling adapter warm_start so one restore helper can serve save/load and resume without cold-start fallback."
  - "Keep PlantBackendSession save_checkpoint/load_checkpoint public names unchanged while routing load through the canonical adapter restore seam."
patterns-established:
  - "Canonical restore path: validate accepted snapshot, normalize if needed, then call adapter warm_start with restore_reason metadata."
  - "Network recovery surfaces use restore reasons (`resume`, `save_load`, `post_edit_recovery`) instead of branching into separate restore implementations."
requirements-completed: [KERN-04]
duration: 4 min
completed: 2026-03-30
---

# Phase 02 Plan 02: Canonical warm-start restore Summary

**Canonical accepted-snapshot warm starts now normalize checkpoint envelopes and route resume, save/load, and post-edit recovery through one adapter-owned restore path.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-30T01:14:44Z
- **Completed:** 2026-03-30T01:18:53Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Added `restore_kernel_from_snapshot()` and `KernelWarmStartFailure` so warm starts validate accepted snapshots and fail explicitly instead of silently cold-starting.
- Routed `PlantBackendSession.load_checkpoint()` and `ConnectionNetwork` recovery helpers through the canonical adapter restore seam while preserving existing public save/load method names.
- Added regression coverage for core-only adapter restores, unsafe restore rejection, backend-session checkpoint loads, and post-edit recovery restore reasons.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add canonical adapter restore helpers** - `3061210` (test), `da9ee44` (feat)
2. **Task 2: Wire save/load and resume surfaces to the canonical restore path** - `27f2cc3` (feat)

**Additional fix:** `4649fd5` (fix test double for the new restore seam)

## Files Created/Modified
- `src/modular_simulation/connection/runtime/kernel_adapter_restore.py` - Canonical snapshot-validation and adapter warm-start helper with explicit failure reporting.
- `tests/connection/test_kernel_adapter_restore.py` - TDD and regression coverage for restore success, rejection, backend session load, and post-edit recovery.
- `src/modular_simulation/connection/topology/network.py` - Canonical network restore entry points and post-edit recovery helper wired to the adapter seam.
- `src/modular_simulation/cli/backend_session.py` - Stable `load_checkpoint()` facade now delegates to the canonical restore path.
- `src/modular_simulation/connection/runtime/split_kernel_adapter.py` - Warm-start path reuses validated runtime restore instead of direct ad hoc resume calls.
- `tests/cli/test_backend_session.py` - Fake network updated for the new canonical restore seam.

## Decisions Made
- Normalize checkpoint envelopes into the live `connection_runtime_v1` payload before invoking adapter warm start so accepted checkpoint snapshots remain the authoritative restore source.
- Keep the public substrate save/load API stable and push restore policy into `ConnectionNetwork` and the adapter-owned helper.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Accepted checkpoint envelopes needed normalization before warm start**
- **Found during:** Task 1 (Add canonical adapter restore helpers)
- **Issue:** The initial helper only accepted live runtime snapshots, but the plan requires canonical restore from accepted checkpoint snapshots as well.
- **Fix:** Added checkpoint-envelope validation and normalization into the live snapshot shape before calling `adapter.warm_start(...)`.
- **Files modified:** `src/modular_simulation/connection/runtime/kernel_adapter_restore.py`
- **Verification:** `uv run python -m pytest tests/connection/test_kernel_adapter_restore.py -q`
- **Committed in:** `da9ee44`

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** The auto-fix aligned the implementation with the plan's checkpoint-based restore contract and avoided a split restore story.

## Issues Encountered
- Backend-session tests used a fake network that only implemented `resume_from_snapshot`; after wiring the canonical restore seam, the fake needed the new `restore_from_checkpoint_snapshot` entry point.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Canonical warm-start restore is in place for resume, save/load, and post-edit recovery entry points.
- Phase 02-03 can now focus on explicit delay-state mapping and restore/update regressions on top of the shared restore seam.

## Self-Check: PASSED
- Found summary file: `.planning/phases/02-kernel-adapter-warm-starts-delay-state/02-02-SUMMARY.md`
- Verified commits exist: `3061210`, `da9ee44`, `27f2cc3`, `4649fd5`

---
*Phase: 02-kernel-adapter-warm-starts-delay-state*
*Completed: 2026-03-30*

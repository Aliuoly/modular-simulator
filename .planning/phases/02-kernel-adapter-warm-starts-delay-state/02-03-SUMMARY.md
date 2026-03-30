---
phase: 02-kernel-adapter-warm-starts-delay-state
plan: 03
subsystem: runtime
tags: [kernel-adapter, delay-state, warm-start, transport-history, pytest]
requires:
  - phase: 02-kernel-adapter-warm-starts-delay-state
    provides: canonical adapter warm-start restore seam from plans 02-01 and 02-02
provides:
  - explicit split-baseline delay semantics metadata and mapping rules
  - adapter-level delay-state round-trip coverage for resume checkpoint and edit recovery
  - human-readable delay semantics contract for future kernel candidates
affects: [phase-03-benchmarks, future-kernel-adapters, delay-semantics]
tech-stack:
  added: []
  patterns:
    - adapter-owned delay mapping metadata over existing transport_runtime_state payloads
    - explicit restore-path regression coverage for delay bundles
key-files:
  created:
    - tests/connection/test_split_kernel_delay_mapping.py
    - docs/kernel_adapter_delay_semantics.md
  modified:
    - src/modular_simulation/connection/kernel_adapter.py
    - src/modular_simulation/connection/runtime/split_kernel_adapter.py
    - tests/connection/test_runtime_persistence_contract.py
key-decisions:
  - "Expose delay-semantics metadata and mapping requirements on the required adapter core rather than hiding them in split-runtime internals."
  - "Keep the split baseline bound to transport_runtime_state while requiring future augmented_state or hybrid candidates to publish explicit replacement mappings."
patterns-established:
  - "Delay Mapping Metadata: adapters publish payload key, mapped fields, and replacement rules alongside delay strategy."
  - "Restore Coverage: resume, checkpoint reload, and post_edit_recovery all assert the same adapter-visible delay bundle."
requirements-completed: [DELY-01, DELY-02, DELY-03]
duration: 2 min
completed: 2026-03-30
---

# Phase 02 Plan 03: Delay State Explicitness Summary

**Split-kernel delay semantics are now explicit through adapter metadata, transport-history bundle mapping, and restore-path regressions across resume, checkpoint reload, and post-edit recovery.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-30T01:22:26Z
- **Completed:** 2026-03-30T01:25:08Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Published explicit `external_transport_history` delay semantics and mapped transport-history fields for the split baseline.
- Added adapter-visible delay bundle round-trip tests that match the current `transport_runtime_state` payload shape.
- Locked in delay restore behavior across live snapshot resume, checkpoint restore, and `post_edit_recovery`, then documented future-candidate rules for `augmented_state` and `hybrid` strategies.

## Task Commits

Each task was committed atomically:

1. **Task 1: Expose explicit split-baseline delay semantics and delay-state mapping** - `9d507b1` (feat)
2. **Task 2: Lock in restore/update regressions and document future-candidate rules** - `c5e9252` (feat)

**Plan metadata:** Pending final docs commit

## Files Created/Modified
- `src/modular_simulation/connection/kernel_adapter.py` - Added typed delay-state mapping metadata to the shared adapter contract.
- `src/modular_simulation/connection/runtime/split_kernel_adapter.py` - Declares split-baseline delay mapping and wraps capture/restore around `transport_runtime_state`.
- `tests/connection/test_split_kernel_delay_mapping.py` - Covers explicit semantics, payload-shape round-trip, future replacement rules, and `resume_from_snapshot` delay restoration.
- `tests/connection/test_runtime_persistence_contract.py` - Verifies adapter-visible delay restore survives checkpoint reload and post-edit recovery.
- `docs/kernel_adapter_delay_semantics.md` - Documents baseline strategy, mapped fields, and mandatory rules for future `augmented_state` and `hybrid` candidates.

## Decisions Made
- Delay semantics and mapping metadata belong to the required adapter core so candidate comparisons cannot hide delay treatment.
- The split baseline keeps the existing `transport_runtime_state` schema in Phase 2 instead of renaming snapshot payloads prematurely.
- Future candidates using `augmented_state` or `hybrid` must publish explicit transport-history mapping and restore rules for checkpoint reloads and runtime edits.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 2 now satisfies the explicit delay-semantics and restore-path contract needed before Phase 3 benchmarking.
- Benchmark candidates can no longer ignore transport-history semantics when comparing split, hybrid, or augmented-state directions.

## Self-Check: PASSED

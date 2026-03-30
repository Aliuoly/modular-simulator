---
phase: 02-kernel-adapter-warm-starts-delay-state
plan: 01
subsystem: simulation
tags: [kernel-adapter, protocol, telemetry, delay-state, runtime]

# Dependency graph
requires:
  - phase: 01-failure-semantics-acceptance-gates
    provides: accepted coupled-state semantics and replay-safe runtime expectations
provides:
  - capability-first candidate kernel adapter core
  - split runtime baseline adapter with explicit delay semantics
  - contract tests for optional capabilities and comparable telemetry
affects: [phase-02-warm-starts, benchmark-harness, solver-comparison]

# Tech tracking
tech-stack:
  added: []
  patterns: [capability-first adapter protocols, honest optional capability declaration, machine-readable delay semantics]

key-files:
  created:
    - src/modular_simulation/connection/kernel_adapter.py
    - src/modular_simulation/connection/runtime/split_kernel_adapter.py
    - tests/connection/test_kernel_adapter_contract.py
  modified:
    - src/modular_simulation/connection/__init__.py

key-decisions:
  - "Use a small required CandidateKernelAdapter core and move solver-shaped hooks into separate optional protocols."
  - "Expose split runtime delay treatment as external transport history and leave optional solver capabilities empty until real seams exist."

patterns-established:
  - "Capability-first kernel adapters: baseline candidates implement initialize/warm-start/step/delay-state/telemetry only."
  - "Comparable telemetry comes from ConnectionRuntimeStepResult plus MacroStepBookkeeping translation rather than candidate-specific dicts."

requirements-completed: [SOLV-02, DELY-02]

# Metrics
duration: 3 min
completed: 2026-03-30
---

# Phase 2 Plan 1: Kernel Adapter Core Summary

**Capability-first kernel adapter contracts with a split-runtime baseline wrapper, explicit external transport-history delay semantics, and comparable runtime telemetry.**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-30T01:05:57Z
- **Completed:** 2026-03-30T01:09:08Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Added a shared `CandidateKernelAdapter` protocol with typed initialization, warm-start, candidate-step, telemetry, and delay-state contracts.
- Split solver-shaped hooks into optional typed protocols for state-vector, residual, Jacobian, and bounds access.
- Wrapped the current split runtime in `SplitKernelAdapter` with explicit external transport-history semantics and honest zero-capability optional declaration.
- Locked the seam with contract tests covering core-only candidates, optional capability discovery, and split baseline telemetry behavior.

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: adapter contract tests** - `d7a584a` (test)
2. **Task 1 GREEN: capability-first core** - `e16fdf5` (feat)
3. **Task 2 RED: split baseline adapter tests** - `675c5fb` (test)
4. **Task 2 GREEN: split runtime adapter** - `c6a4463` (feat)

**Plan metadata:** recorded in the final docs commit for this plan.

## Files Created/Modified
- `src/modular_simulation/connection/kernel_adapter.py` - shared adapter dataclasses, enum metadata, required core protocol, and optional solver capability protocols.
- `src/modular_simulation/connection/runtime/split_kernel_adapter.py` - baseline wrapper around `ConnectionNetwork` and `ConnectionRuntimeOrchestrator` that translates runtime results into shared telemetry.
- `src/modular_simulation/connection/__init__.py` - public re-exports for the new adapter seam symbols.
- `tests/connection/test_kernel_adapter_contract.py` - TDD contract coverage for core-only candidates and split baseline behavior.

## Decisions Made
- Used a capability-first adapter seam because the locked Phase 2 context supersedes the older monolithic-contract research note.
- Kept `SplitKernelAdapter.supported_optional_capabilities()` empty so the baseline does not fake solver-facing hooks it cannot honestly back.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Dataclass inheritance from the protocol caused a runtime property/setter conflict in `SplitKernelAdapter`; fixed by satisfying the protocol structurally instead of subclassing it directly.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- The shared adapter seam and split baseline wrapper are in place for canonical warm-start routing work in `02-02-PLAN.md`.
- Delay semantics are now machine-readable, so later restore and benchmark plans can compare candidates without guessing transport-history treatment.

## Self-Check: PASSED
- Verified created files exist on disk.
- Verified task commits `d7a584a`, `e16fdf5`, `675c5fb`, and `c6a4463` exist in git history.

---
*Phase: 02-kernel-adapter-warm-starts-delay-state*
*Completed: 2026-03-30*

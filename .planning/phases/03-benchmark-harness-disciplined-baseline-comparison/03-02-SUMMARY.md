---
phase: 03-benchmark-harness-disciplined-baseline-comparison
plan: 02
subsystem: simulation
tags: [benchmarking, workloads, harness, checkpoint-restore, baseline]

# Dependency graph
requires:
  - phase: 03-benchmark-harness-disciplined-baseline-comparison
    provides: reusable benchmark contracts, accepted-step telemetry summaries, and explicit delay semantics metadata
provides:
  - fixed three-workload checkpoint-first Phase 3 benchmark canon
  - reusable benchmark harness enforcing one shared fairness contract per candidate run
  - thin macro benchmark wrapper over the reusable harness and canonical workloads
affects: [phase-03-plan-03, solver-comparison, disciplined-baseline-reporting]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - checkpoint-first workload seeds attached directly to workload definitions
    - reusable benchmark harness with eager fairness-contract validation before candidate execution

key-files:
  created:
    - src/modular_simulation/connection/benchmarking/workloads.py
    - src/modular_simulation/connection/benchmarking/harness.py
    - tests/connection/test_benchmark_harness.py
  modified:
    - src/modular_simulation/connection/benchmarking/contracts.py
    - src/modular_simulation/connection/benchmarking/__init__.py
    - examples/connection_layer/benchmarks/macro_coupling_benchmark.py
    - tests/connection/test_examples_benchmarks.py

key-decisions:
  - "Keep the Phase 3 canon fixed to exactly three checkpoint-first workloads with explicit multi-tag coverage rows rather than a broader evolving suite."
  - "Reject candidate/workload fairness mismatches before any benchmark run so checkpoint, tolerance, physical-acceptance, telemetry, and delay semantics cannot drift per candidate."
  - "Make the example benchmark wrapper return JSON-serializable attempt-record summaries from the reusable harness instead of keeping a disconnected smoke-stub surface."

patterns-established:
  - "Canonical Workload Seed: each workload carries a deterministic checkpoint builder returning a session, accepted checkpoint, and macro-step size."
  - "Thin Example Wrapper: benchmark example files import reusable harness primitives and contain no comparison business logic."

requirements-completed: [PERF-01, PERF-02, SOLV-01, DELY-04]

# Metrics
duration: 18 min
completed: 2026-03-30
---

# Phase 3 Plan 2: Benchmark Harness and Canonical Workloads Summary

**Fixed checkpoint-first benchmark workloads and a reusable harness now run the disciplined split baseline through one shared fairness contract with JSON-serializable attempt traces.**

## Performance

- **Duration:** 18 min
- **Started:** 2026-03-30T04:13:21Z
- **Completed:** 2026-03-30T04:31:45Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- Added the fixed three-workload Phase 3 benchmark canon with explicit coverage rows for warm-run, recycle-heavy, disturbance, controller/network coupling, restart/reconfiguration, and delay-heavy evidence.
- Implemented `BenchmarkHarness` and `run_candidate_workload(...)` so every candidate run validates shared checkpoint, tolerance, physical-acceptance, telemetry, and delay-semantics metadata before execution.
- Replaced the old macro benchmark smoke stub with a thin wrapper that builds canonical workloads, runs the disciplined split baseline path, and returns JSON-serializable attempt summaries.

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: workload catalog tests** - `a9588a1` (test)
2. **Task 1 GREEN: canonical workload catalog** - `2bc78e0` (feat)
3. **Task 2 RED: reusable harness and wrapper tests** - `1f8a8c2` (test)
4. **Task 2 GREEN: reusable harness runner and thin wrapper** - `4f23995` (feat)

**Plan metadata:** pending final docs commit.

## Files Created/Modified
- `src/modular_simulation/connection/benchmarking/workloads.py` - fixed Phase 3 workload catalog, explicit coverage matrix, checkpoint seed builders, and lightweight checkpoint seeding helpers.
- `src/modular_simulation/connection/benchmarking/harness.py` - reusable benchmark harness, fairness-contract validation, attempt-record execution loop, and JSON-ready attempt serialization helpers.
- `src/modular_simulation/connection/benchmarking/__init__.py` - public exports for workload and harness primitives.
- `src/modular_simulation/connection/benchmarking/contracts.py` - workload contract expanded so workload definitions can carry deterministic checkpoint builders.
- `examples/connection_layer/benchmarks/macro_coupling_benchmark.py` - thin wrapper that runs the disciplined split baseline over the canonical Phase 3 workload set.
- `tests/connection/test_benchmark_harness.py` - TDD coverage for the fixed catalog, explicit coverage matrix, checkpoint-first builders, harness execution, and fairness enforcement.
- `tests/connection/test_examples_benchmarks.py` - wrapper regression coverage for JSON-serializable harness delegation.

## Decisions Made
- Kept the canonical benchmark suite fixed at exactly three workloads, matching the locked Phase 3 context and research recommendation for a deliberately small but balanced canon.
- Enforced the shared fairness contract in the harness itself instead of relying on example-script discipline so candidate-specific checkpoint or tolerance drift is rejected immediately.
- Returned JSON-serializable attempt records from the example wrapper so later reporting and docs work can consume one stable summary shape instead of the old ad hoc float-only smoke output.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Avoided eager import of the staged-control example during workload module import**
- **Found during:** Task 1 (Create the fixed canonical workload catalog and coverage matrix)
- **Issue:** Importing the staged-control example at module load raised an unrelated `StateType.CONTROLLED` error during test collection, blocking the workload module before any checkpoint builders could run.
- **Fix:** Deferred the staged-control example import out of module import time and used deterministic lightweight checkpoint seed builders so the canonical catalog stays importable and testable.
- **Files modified:** `src/modular_simulation/connection/benchmarking/workloads.py`
- **Verification:** `uv run python -m pytest tests/connection/test_benchmark_harness.py -q`
- **Committed in:** `2bc78e0`

**2. [Rule 3 - Blocking] Added a lightweight steady hydraulic solve path for checkpoint seeding helpers**
- **Found during:** Task 1 (Create the fixed canonical workload catalog and coverage matrix)
- **Issue:** Minimal checkpoint seed networks had no compiled hydraulic graph, so `PlantBackendSession.step()` failed before a checkpoint could be saved.
- **Fix:** Added a minimal converged hydraulic solve helper for workload seed sessions so checkpoint-first builders can create accepted snapshots without dragging full example runtime plumbing into the workload substrate.
- **Files modified:** `src/modular_simulation/connection/benchmarking/workloads.py`
- **Verification:** `uv run python -m pytest tests/connection/test_benchmark_harness.py -q`
- **Committed in:** `2bc78e0`

---

**Total deviations:** 2 auto-fixed (2 blocking)
**Impact on plan:** Both fixes were required to make the checkpoint-first workload substrate executable and testable. No scope creep beyond harness correctness.

## Issues Encountered
- The macro benchmark example previously exported a fixed smoke-stub dict, so wrapper tests had to be updated to assert the new JSON-serializable harness summary shape instead of the old `elapsed_seconds`/`macro_steps`/`iterations` placeholder surface.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 3 now has the canonical workload and reusable harness substrate needed for viability scoring, disqualification, and disciplined split/SciPy baseline reporting in `03-03-PLAN.md`.
- Reporting work can consume explicit workload coverage rows and raw attempt traces without rebuilding checkpoint, fairness, or wrapper contracts.

## Self-Check: PASSED
- Found summary file: `.planning/phases/03-benchmark-harness-disciplined-baseline-comparison/03-02-SUMMARY.md`.
- Verified task commits exist in git history: `a9588a1`, `2bc78e0`, `1f8a8c2`, and `4f23995`.

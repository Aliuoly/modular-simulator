---
phase: 03-benchmark-harness-disciplined-baseline-comparison
plan: 03
subsystem: testing
tags: [benchmarking, scipy, reporting, latency, realtime-factor]
requires:
  - phase: 02-kernel-adapter-warm-starts-delay-state
    provides: shared candidate adapter seam, warm-start restore path, and explicit delay semantics
provides:
  - accepted-step viability scoring with explicit latency and realtime gates
  - visible-but-unranked disqualification reporting for the split baseline
  - documented Phase 3 benchmark contract and final wrapper report surface
affects: [phase-4, kernel-direction-decision, benchmark-evidence]
tech-stack:
  added: []
  patterns:
    - accepted-step-only latency gating with separate realtime headline and minimum gates
    - benchmark reports keep disqualified candidates visible while excluding them from ranking
key-files:
  created:
    - src/modular_simulation/connection/benchmarking/reporting.py
    - tests/connection/test_benchmark_reporting.py
    - docs/kernel_benchmark_harness.md
  modified:
    - src/modular_simulation/connection/benchmarking/__init__.py
    - examples/connection_layer/benchmarks/macro_coupling_benchmark.py
    - tests/connection/test_examples_benchmarks.py
key-decisions:
  - "Compute hard latency viability from accepted-step p95, but report realtime factor separately from the 100x headline target."
  - "Always show the disciplined split/SciPy baseline in reports, while excluding any disqualified candidate from candidate_rankings."
patterns-established:
  - "Phase 3 reports aggregate candidate attempts into a JSON-serializable surface with candidate_rankings, disqualified_candidates, coverage_matrix, and explicit gate values."
  - "Benchmark wrapper logic stays thin and delegates scoring/ranking policy to src/modular_simulation/connection/benchmarking/reporting.py."
requirements-completed: [PERF-03, PERF-04, SOLV-03]
duration: 5 min
completed: 2026-03-30
---

# Phase 3 Plan 3: Disciplined baseline reporting summary

**Accepted-step latency scoring, disqualification-aware ranking, and always-visible split baseline reporting for the Phase 3 benchmark harness**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-30T04:34:25Z
- **Completed:** 2026-03-30T04:39:47Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Added a reusable reporting module that scores candidates from accepted-step median/p95/p99 latency, explicit latency-budget fractions, and separated realtime viability versus headline target fields.
- Enforced rank-blocking disqualification for fallback use, hidden solver failure, physical-acceptance failure, clipping-masked apparent stability, hidden recovery, and telemetry contract violations.
- Updated the macro benchmark wrapper and docs so the final report surface always exposes rankings, disqualified candidates, workload coverage, and the disciplined split baseline contract.

## Task Commits

Each task was committed atomically:

1. **Task 1: accepted-step scoring RED** - `cc647a2` (test)
2. **Task 1: implement accepted-step scoring and explicit disqualification** - `680e846` (feat)
3. **Task 2: publish the final benchmark report surface and Phase 3 contract docs** - `d8ded5f` (feat)

_Note: Task 1 followed RED → GREEN. Task 2 landed as one atomic feature commit after extending report-surface coverage._

## Files Created/Modified
- `src/modular_simulation/connection/benchmarking/reporting.py` - scores candidate reports, derives viability gates, and builds ranked/disqualified report sections
- `tests/connection/test_benchmark_reporting.py` - regression coverage for accepted-step-only latency scoring, disqualification, and baseline visibility
- `docs/kernel_benchmark_harness.md` - grep-verifiable benchmark contract for workload ids, hard gates, headline target, and disqualification reasons
- `examples/connection_layer/benchmarks/macro_coupling_benchmark.py` - thin wrapper that now returns the final JSON-serializable report surface
- `tests/connection/test_examples_benchmarks.py` - verifies wrapper output includes rankings, disqualified candidates, coverage, and explicit gate fields
- `src/modular_simulation/connection/benchmarking/__init__.py` - exports reporting helpers from the benchmark package surface

## Decisions Made
- Separated `minimum_rtf_gate=4.0` from the reported `headline_rtf_target=100.0` so Phase 3 keeps the aspirational headroom signal visible without turning it into the hard pass line.
- Used accepted-step p95 relative to simulated step size for the hard latency gate while keeping rejected attempts visible only in counts and disqualification evidence.
- Aggregated all disciplined split baseline attempts into one visible candidate report, with ranking logic driven by report viability instead of hiding disqualified rows.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 3 benchmark evidence now includes explicit viability scoring, disciplined baseline visibility, and rank-blocking disqualification rules.
- Phase 3 is complete and ready for Phase 4 kernel-direction decision and migration-roadmap work.

## Self-Check: PASSED

- Verified `src/modular_simulation/connection/benchmarking/reporting.py` exists.
- Verified `docs/kernel_benchmark_harness.md` exists.
- Verified `.planning/phases/03-benchmark-harness-disciplined-baseline-comparison/03-03-SUMMARY.md` exists.
- Verified commits `cc647a2`, `680e846`, and `d8ded5f` exist in git history.

---
*Phase: 03-benchmark-harness-disciplined-baseline-comparison*
*Completed: 2026-03-30*

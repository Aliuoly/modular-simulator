---
phase: 03-benchmark-harness-disciplined-baseline-comparison
plan: 01
subsystem: simulation
tags: [benchmarking, telemetry, contracts, latency, replay]

# Dependency graph
requires:
  - phase: 02-kernel-adapter-warm-starts-delay-state
    provides: explicit adapter telemetry, restore semantics, and delay-state metadata for fair candidate comparison
provides:
  - reusable benchmark contract package for fairness metadata and per-attempt traces
  - telemetry normalization helpers from candidate-step results into benchmark attempt records
  - accepted-step latency summaries that stay separate from rejected/disqualified trace evidence
affects: [phase-03-plan-02, phase-03-plan-03, solver-comparison, delay-aware-benchmarking]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - accepted-step-only latency summaries with all-attempt diagnostic retention
    - typed benchmark fairness metadata under src/modular_simulation/connection/benchmarking

key-files:
  created:
    - src/modular_simulation/connection/benchmarking/__init__.py
    - src/modular_simulation/connection/benchmarking/contracts.py
    - src/modular_simulation/connection/benchmarking/telemetry.py
    - tests/connection/test_benchmark_contracts.py
  modified: []

key-decisions:
  - "Adopt one shared benchmark contract package under src/modular_simulation/connection/benchmarking for fairness metadata, attempt records, and accepted-step latency summaries."
  - "Keep accepted-step viability summaries separate from all-attempt traces so rejected and disqualified attempts remain visible without polluting latency gates."
  - "Reserve nullable residual, Jacobian, and linear-solve cost fields now so future candidates can report solver-cost telemetry without a contract break."

patterns-established:
  - "Benchmark Attempt Record: every candidate step becomes one typed record carrying checkpoint, tolerance, physical-acceptance, delay, replay-hash, and fallback evidence."
  - "Honest Missing Solver Cost Metrics: unavailable residual/Jacobian/linear-solve costs are represented as explicit None fields rather than omitted keys."

requirements-completed: [PERF-02, SOLV-01]

# Metrics
duration: 4 min
completed: 2026-03-30
---

# Phase 3 Plan 1: Benchmark Contracts and Telemetry Summary

**Typed benchmark fairness contracts and telemetry normalization now preserve accepted/rejected outcomes, fallback evidence, delay semantics, replay hashes, and accepted-step latency summaries in one reusable comparison layer.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-30T02:49:47Z
- **Completed:** 2026-03-30T02:54:33Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Added a reusable benchmark contract package with typed workload, candidate, attempt, latency-budget, disqualification, and summary records under `src/modular_simulation/connection/benchmarking/`.
- Encoded fairness metadata directly in workload and candidate contracts so checkpoints, tolerances, physical-acceptance profiles, telemetry contract versions, and delay semantics stay machine-readable across candidate comparisons.
- Added telemetry normalization helpers that convert `KernelCandidateStepResult` into one benchmark attempt shape while preserving fallback keys, replay hashes, Picard details, and accepted/rejected outcomes.
- Locked the layer with focused pytest coverage for fairness defaults, disqualification enums, attempt-record normalization, and accepted-step-only latency summaries.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create benchmark contracts for fairness, thresholds, and disqualification** - `d9ec4e7` (feat)
2. **Task 2: Normalize adapter/runtime evidence into benchmark attempt records** - `d3b36cf` (feat)
3. **Rule 2 follow-up: Reserve nullable solver cost telemetry fields** - `a6a1a29` (fix)

**Plan metadata:** recorded in the final docs commit for this plan.

## Files Created/Modified
- `src/modular_simulation/connection/benchmarking/contracts.py` - benchmark enums and typed dataclasses for workloads, candidates, attempts, latency budgets, summaries, and accepted-step latency aggregates.
- `src/modular_simulation/connection/benchmarking/telemetry.py` - helper functions that normalize candidate-step telemetry into benchmark attempt records and compute accepted-step latency summaries.
- `src/modular_simulation/connection/benchmarking/__init__.py` - public re-exports for the benchmark contract and telemetry surface.
- `tests/connection/test_benchmark_contracts.py` - TDD-style contract and normalization coverage for Phase 3 benchmark substrate behavior.

## Decisions Made
- Used a dedicated benchmark substrate package under `src/modular_simulation/connection/benchmarking/` rather than growing an example script, matching the Phase 3 research recommendation for reusable comparison infrastructure.
- Kept `RTF >= 100` as a headline target and `minimum_rtf_gate=4.0` as the explicit hard viability floor in the latency-budget contract, consistent with the locked Phase 3 context.
- Computed median, p95, and p99 from accepted attempts only while retaining rejected attempts in counts and disqualification data, matching D-02 and D-03.
- Added nullable residual, Jacobian, and linear-solve cost fields so future candidates can report solver-cost telemetry honestly with explicit `None` when unavailable.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Reserved nullable solver-cost telemetry slots in the attempt contract**
- **Found during:** Task 2 (Normalize adapter/runtime evidence into benchmark attempt records)
- **Issue:** The initial attempt-record contract preserved fallback, replay, and Picard evidence but left no explicit fields for residual/Jacobian/linear-solve timing, which Phase 3 research identifies as required PERF-02 telemetry that some candidates may not yet provide.
- **Fix:** Added nullable `residual_eval_cost_s`, `jacobian_eval_cost_s`, and `linear_solve_cost_s` fields to `BenchmarkAttemptRecord` so future candidates can publish honest `None` values instead of forcing a breaking contract change later.
- **Files modified:** `src/modular_simulation/connection/benchmarking/contracts.py`
- **Verification:** `uv run python -m pytest tests/connection/test_benchmark_contracts.py -q`
- **Committed in:** `a6a1a29`

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** The auto-fix tightened the benchmark contract so later solver-cost telemetry can land without changing the public attempt-record shape. No scope creep beyond Phase 3 contract correctness.

## Issues Encountered
- A `gsd-tools commit` probe created an extra metadata-only commit (`a566101`) while checking command flags. It touched only `.planning/STATE.md`; execution continued by applying the intended final state updates and documenting the accidental probe transparently.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 3 now has the reusable benchmark contract and telemetry-normalization substrate needed for the fixed checkpoint-first workload catalog and harness runner in `03-02-PLAN.md`.
- Later reporting work can consume accepted-step latency summaries and disqualification-ready attempt traces without rediscovering fairness metadata or delay semantics.

## Self-Check: PASSED
- Verified created files exist on disk: `src/modular_simulation/connection/benchmarking/__init__.py`, `src/modular_simulation/connection/benchmarking/contracts.py`, `src/modular_simulation/connection/benchmarking/telemetry.py`, and `tests/connection/test_benchmark_contracts.py`.
- Verified task commits exist in git history: `d9ec4e7`, `d3b36cf`, and `a6a1a29`.

---
*Phase: 03-benchmark-harness-disciplined-baseline-comparison*
*Completed: 2026-03-30*

# Roadmap: ModularSimulator

## Overview

This roadmap turns the v1.0 kernel-stability milestone into a decision-driven sequence: first make failure modes, coupled-state acceptance, and physical guards explicit; then add the kernel seam needed to test hybrid and whole-flowsheet directions fairly; then benchmark disciplined SciPy, hybrid-coupled, and escalation candidates against the same delay-aware workloads; and finish with an evidence-backed migration roadmap. Because `.planning/config.json` does not exist yet, this roadmap uses standard granularity by default.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Failure Semantics & Acceptance Gates** - Make current kernel failures, coupled-state acceptance, and physical rejection rules explicit. (in progress)
- [x] **Phase 2: Kernel Adapter, Warm Starts & Delay State** - Create the substrate for fair candidate comparison without breaking live runtime facades. (completed 2026-03-30)
- [x] **Phase 3: Benchmark Harness & Disciplined Baseline Comparison** - Compare candidates on the same workloads, telemetry, and realtime acceptance thresholds.
- [x] **Phase 4: Hybrid Decision Gate & Migration Roadmap** - End the milestone with an evidence-backed kernel direction and escalation path. (completed 2026-03-30)

## Phase Details

### Phase 1: Failure Semantics & Acceptance Gates
**Goal**: Team can identify the current split-kernel instability modes and define one accepted coupled plant state with explicit structural and physical rejection rules.
**Depends on**: Nothing (first phase)
**Requirements**: KERN-01, KERN-02, KERN-03, KERN-05
**Success Criteria** (what must be TRUE):
  1. Team can replay representative complex flowsheets and obtain classified evidence of stale-coupling, stale-pressure-driven flow, or non-physical inventory failures in the current split kernel.
  2. Candidate kernels either publish one accepted coupled plant snapshot or reject the step without exposing partially updated unit and connection state.
  3. Under-specified, over-specified, or structurally inconsistent flowsheet states are rejected before runtime stepping begins.
  4. Accepted states satisfy physical feasibility guards, and any negative inventory, invalid composition normalization, or similar non-physical condition is surfaced as an explicit rejection reason.
**Plans**: 4 plans

Plans:
- [x] 01-01-PLAN.md — Create the Python 3.13 test substrate, shared failure taxonomy contracts, and Phase 1 test modules.
- [ ] 01-02-PLAN.md — Route structural compile/barrier/hydraulic failures into explicit pre-step structural rejections.
- [ ] 01-03-PLAN.md — Add runtime-step failure classification, replay-hash evidence, and scenario-matrix coverage.
- [ ] 01-04-PLAN.md — Implement whole-plant macro-step acceptance transaction and plant-level physical acceptance guards.

### Phase 2: Kernel Adapter, Warm Starts & Delay State
**Goal**: Team can evaluate coupled kernel directions through a reusable adapter seam that preserves initialization, warm starts, and transport/deadtime semantics.
**Depends on**: Phase 1
**Requirements**: KERN-04, SOLV-02, DELY-01, DELY-02, DELY-03
**Success Criteria** (what must be TRUE):
  1. Candidate kernels can initialize from the last accepted plant state, checkpoint restore, or post-edit recovery path without replacing the existing runtime/session facades first.
  2. Candidate kernels plug into a shared adapter seam with one required core for initialization, warm-start, candidate-step evaluation, comparable telemetry, and delay semantics, while state, residual, Jacobian, and bounds remain optional typed capabilities.
  3. Existing transport-lag behavior is either preserved or explicitly replaced, with the active delay treatment documented for each candidate direction.
  4. Deadtime and transport-history state can be restored and updated safely across checkpoint reloads, warm starts, and runtime edits.
**Plans**: 3 plans

Plans:
- [x] 02-01-PLAN.md — Define the capability-first kernel adapter core, optional solver-capability protocols, and the honest split-runtime baseline wrapper.
- [x] 02-02-PLAN.md — Route resume, save/load, and post-edit recovery through one canonical accepted-snapshot warm-start path using only the shared core.
- [x] 02-03-PLAN.md — Make delay-state treatment explicit, map the split baseline delay bundle, and lock in restore/update regressions for future candidates.

### Phase 3: Benchmark Harness & Disciplined Baseline Comparison
**Goal**: Team can compare split, hybrid-coupled, and escalation candidates fairly on canonical workloads with trustworthy telemetry and realtime performance gates.
**Depends on**: Phase 2
**Requirements**: PERF-01, PERF-02, PERF-03, PERF-04, SOLV-01, SOLV-03, DELY-04
**Success Criteria** (what must be TRUE):
  1. Team can run a version-controlled benchmark harness over canonical checkpointed workloads covering warm runs, disturbances, recycle-heavy cases, transport-history-sensitive staged flow paths, and restart plus post-edit reconfiguration paths.
  2. Every candidate emits comparable per-step telemetry for accepted/rejected steps, convergence status, residual/Jacobian work, linear-solve cost, and wall-clock latency.
  3. Benchmark results apply explicit realtime viability thresholds using realtime factor plus median, p95, and p99 accepted-step latency on the same tolerances and physical-acceptance gates.
  4. Any candidate that emits producer-backed rank-blocking benchmark evidence is disqualified before speed comparisons are accepted, with fallback use remaining mandatory and additional disqualifier signals surfaced as adapters expose them.
  5. Delay-heavy and transport-lag-sensitive scenarios are included in the benchmark matrix so whole-flowsheet or hybrid directions are not approved by ignoring delay semantics.
**Plans**: 3 plans

Plans:
- [x] 03-01-PLAN.md — Define reusable benchmark contracts, fairness metadata, and telemetry normalization for candidate comparison.
- [x] 03-02-PLAN.md — Build the fixed 3-workload checkpoint-first catalog and reusable benchmark harness runner.
- [x] 03-03-PLAN.md — Add viability scoring, disqualification, and disciplined split/SciPy baseline reporting.

### Phase 4: Hybrid Decision Gate & Migration Roadmap
**Goal**: Team can choose the default kernel direction for v1.0, justify whether SciPy remains sufficient, and publish a concrete migration roadmap for any needed escalation.
**Depends on**: Phase 3
**Requirements**: PERF-05, SOLV-04, SOLV-05
**Success Criteria** (what must be TRUE):
  1. Team can make an evidence-backed decision on whether a disciplined SciPy baseline is sufficient or whether solver-core limits justify leaving it.
  2. When the baseline appears solver-limited, the comparison includes at least one post-SciPy Python-native path and at least one non-Python-capable path under the same workloads, tolerances, and acceptance gates.
  3. The milestone ends with a concrete migration roadmap that treats split-step instability and possible whole-flowsheet escalation as one kernel problem, sets hybrid-coupled as the default direction unless benchmarks disprove it, and preserves existing facades where practical.
  4. Any solver-stack migration is justified in terms of stability, latency, deployment risk, and compatibility; `sundials4py` is the first serious post-SciPy path and PETSc/petsc4py remains a later escalation only if benchmarks justify it.
**Plans**: 2 plans

Plans:
- [x] 04-01-PLAN.md — Add the reusable Phase 4 decision gate that turns Phase 3 benchmark evidence into a SciPy sufficiency or escalation decision.
- [x] 04-02-PLAN.md — Publish the thin Phase 4 decision example plus kernel-direction and migration-roadmap docs grounded in the Phase 3 canon.

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Failure Semantics & Acceptance Gates | 1/4 | In Progress | 2026-03-31 |
| 2. Kernel Adapter, Warm Starts & Delay State | 3/3 | Complete   | 2026-03-30 |
| 3. Benchmark Harness & Disciplined Baseline Comparison | 3/3 | Complete   | 2026-03-30 |
| 4. Hybrid Decision Gate & Migration Roadmap | 2/2 | Complete   | 2026-03-30 |
| 5. Runnable solver candidates | 4/4 | Complete | 2026-03-30 |

### Phase 5: Runnable solver candidates

**Goal:** Team can run the disciplined split baseline, a real SUNDIALS-backed candidate, and a real PETSc-backed candidate through the fixed three-workload canon from comparable accepted snapshots and publish one same-harness report.
**Requirements**: PERF-06, SOLV-06, DELY-05
**Depends on:** Phase 4
**Success Criteria** (what must be TRUE):
  1. Team can run `disciplined_split`, `sundials4py`, and `petsc4py` through the exact fixed canon `ammonia_recycle_warm`, `staged_delay_control_disturbance`, and `checkpoint_restart_reconfigure` using the existing benchmark harness contract.
  2. The SUNDIALS-backed and PETSc-backed candidates restore accepted snapshots and transport-history delay state strongly enough to start from the same checkpoint-first seeds as the disciplined split baseline.
  3. The final report keeps per-workload rows, baseline visibility, and disqualified-candidate visibility instead of silently dropping failed candidates.
  4. Existing public runtime/session facades stay intact; new solver work remains behind `CandidateKernelAdapter` and the benchmark wrapper.
**Plans:** 6 plans

Plans:
- [x] 05-01-PLAN.md — Define the Phase 5 hard-coded comparison contract, binding metadata, and dependency declarations.
- [x] 05-02-PLAN.md — Implement the SUNDIALS-backed runnable adapter with accepted-snapshot and delay-state parity.
- [x] 05-03-PLAN.md — Implement the PETSc-backed runnable adapter with accepted-snapshot and delay-state parity.
- [x] 05-04-PLAN.md — Wire the hard-coded three-candidate benchmark surface and verify visible multi-candidate reporting.
- [ ] 05-05-PLAN.md — Provision a pinned live-backend environment plus CI path for real SUNDIALS and PETSc benchmark execution.
- [ ] 05-06-PLAN.md — Add live same-harness regression checks and rerun the real Phase 5 benchmark gate.

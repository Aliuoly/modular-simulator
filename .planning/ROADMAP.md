# Roadmap: ModularSimulator

## Overview

This roadmap turns the v1.0 kernel-stability milestone into a decision-driven sequence: first make failure modes, coupled-state acceptance, and physical guards explicit; then add the kernel seam needed to test hybrid and whole-flowsheet directions fairly; then benchmark disciplined SciPy, hybrid-coupled, and escalation candidates against the same delay-aware workloads; and finish with an evidence-backed migration roadmap. Because `.planning/config.json` does not exist yet, this roadmap uses standard granularity by default.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Failure Semantics & Acceptance Gates** - Make current kernel failures, coupled-state acceptance, and physical rejection rules explicit.
- [ ] **Phase 2: Kernel Adapter, Warm Starts & Delay State** - Create the substrate for fair candidate comparison without breaking live runtime facades.
- [ ] **Phase 3: Benchmark Harness & Disciplined Baseline Comparison** - Compare candidates on the same workloads, telemetry, and realtime acceptance thresholds.
- [ ] **Phase 4: Hybrid Decision Gate & Migration Roadmap** - End the milestone with an evidence-backed kernel direction and escalation path.

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
- [ ] 01-01-PLAN.md — Create the Python 3.13 test substrate, shared failure taxonomy contracts, and Phase 1 test modules.
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
- [ ] 02-02-PLAN.md — Route resume, save/load, and post-edit recovery through one canonical accepted-snapshot warm-start path using only the shared core.
- [ ] 02-03-PLAN.md — Make delay-state treatment explicit, map the split baseline delay bundle, and lock in restore/update regressions for future candidates.

### Phase 3: Benchmark Harness & Disciplined Baseline Comparison
**Goal**: Team can compare split, hybrid-coupled, and escalation candidates fairly on canonical workloads with trustworthy telemetry and realtime performance gates.
**Depends on**: Phase 2
**Requirements**: PERF-01, PERF-02, PERF-03, PERF-04, SOLV-01, SOLV-03, DELY-04
**Success Criteria** (what must be TRUE):
  1. Team can run a version-controlled benchmark harness over canonical checkpointed workloads covering warm runs, disturbances, recycle-heavy cases, controller/network coupling, restart, and reconfiguration paths.
  2. Every candidate emits comparable per-step telemetry for accepted/rejected steps, convergence status, residual/Jacobian work, linear-solve cost, and wall-clock latency.
  3. Benchmark results apply explicit realtime viability thresholds using realtime factor plus median, p95, and p99 accepted-step latency on the same tolerances and physical-acceptance gates.
  4. Any candidate that hides solver failure, violates physical-acceptance gates, or depends on emergency clipping/fallback is disqualified before speed comparisons are accepted.
  5. Delay-heavy and transport-lag-sensitive scenarios are included in the benchmark matrix so whole-flowsheet or hybrid directions are not approved by ignoring delay semantics.
**Plans**: TBD

### Phase 4: Hybrid Decision Gate & Migration Roadmap
**Goal**: Team can choose the default kernel direction for v1.0, justify whether SciPy remains sufficient, and publish a concrete migration roadmap for any needed escalation.
**Depends on**: Phase 3
**Requirements**: PERF-05, SOLV-04, SOLV-05
**Success Criteria** (what must be TRUE):
  1. Team can make an evidence-backed decision on whether a disciplined SciPy baseline is sufficient or whether solver-core limits justify leaving it.
  2. When the baseline appears solver-limited, the comparison includes at least one post-SciPy Python-native path and at least one non-Python-capable path under the same workloads, tolerances, and acceptance gates.
  3. The milestone ends with a concrete migration roadmap that treats split-step instability and possible whole-flowsheet escalation as one kernel problem, sets hybrid-coupled as the default direction unless benchmarks disprove it, and preserves existing facades where practical.
  4. Any solver-stack migration is justified in terms of stability, latency, deployment risk, and compatibility; `sundials4py` is the first serious post-SciPy path and PETSc/petsc4py remains a later escalation only if benchmarks justify it.
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Failure Semantics & Acceptance Gates | 0/4 | Not started | - |
| 2. Kernel Adapter, Warm Starts & Delay State | 1/3 | In Progress | - |
| 3. Benchmark Harness & Disciplined Baseline Comparison | 0/TBD | Not started | - |
| 4. Hybrid Decision Gate & Migration Roadmap | 0/TBD | Not started | - |

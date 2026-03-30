# Phase 4: Hybrid Decision Gate & Migration Roadmap - Research

**Researched:** 2026-03-30
**Domain:** Evidence-backed kernel-direction decision, post-SciPy comparison framing, and migration-roadmap publication
**Confidence:** MEDIUM-HIGH

<user_constraints>
## Phase Constraints (derived from ROADMAP.md, STATE.md, PROJECT.md)

### Locked Decisions
- **D-01:** Treat split-step instability and possible whole-flowsheet escalation as one kernel decision problem.
- **D-02:** Keep **hybrid-coupled** as the default roadmap direction unless benchmark evidence disproves it.
- **D-03:** Keep the disciplined split/**SciPy** path as the baseline that must be judged by benchmark evidence rather than intuition.
- **D-04:** `sundials4py` is the **first serious post-SciPy path** when baseline evidence shows solver-core limits.
- **D-05:** PETSc/`petsc4py` remains a **later escalation only if benchmarks justify it**.
- **D-06:** Preserve existing `PlantBackendSession`, runtime/session facades, and the Phase 2 `CandidateKernelAdapter` seam where practical.
- **D-07:** Phase 4 must reuse the Phase 3 canonical workload canon, fairness contract, latency gates, and delay semantics rather than inventing a new comparison basis.
- **D-08:** Migration justification must explicitly cover **stability, latency, deployment risk, and compatibility**.

### the agent's Discretion
- Choose the exact machine-readable shape for the Phase 4 decision artifact as long as it makes the SciPy sufficiency decision, default direction, recommended next solver stack, and missing-evidence reasons explicit.
- Choose whether the final Phase 4 output is rendered through a benchmark example, a reporting helper, or a dedicated decision script, as long as it stays thin and reuses Phase 3 benchmark/reporting primitives.

### Deferred Ideas (OUT OF SCOPE)
- Building a real `sundials4py` or `petsc4py` runtime adapter in Phase 4.
- Adding new benchmark workloads beyond the fixed Phase 3 canon.
- Reopening frontend, gameplay, or non-kernel product scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PERF-05 | Team can decide whether leaving the current SciPy baseline is justified using benchmark evidence rather than intuition or single-scenario timing. | Build a machine-readable decision gate that consumes the verified Phase 3 report and records whether SciPy is sufficient, solver-limited, or still missing decisive evidence. |
| SOLV-04 | Team can compare at least one post-SciPy Python-native path and at least one non-Python-capable path when benchmark evidence suggests the baseline may be solver-limited. | Publish one explicit comparison matrix using the Phase 3 workload canon and fairness rules for `sundials4py` (Python-native) and PETSc/`petsc4py` (non-Python-capable escalation path). |
| SOLV-05 | Team can justify any solver-stack migration in terms of stability improvement, latency improvement, deployment risk, and compatibility with the existing runtime/session facades. | Encode migration criteria and roadmap stages that preserve `PlantBackendSession`/runtime facades and require exact justification fields for stability, latency, deployment risk, and compatibility. |
</phase_requirements>

## Summary

Phase 4 should be implemented as an **evidence-synthesis layer** on top of the now-verified Phase 3 benchmark substrate, not as an immediate new-solver integration phase. The repo already has the right Phase 3 inputs: a verified benchmark canon, machine-readable workload coverage, disciplined split/SciPy baseline reporting, explicit disqualification rules, and a reusable reporting surface. The missing piece is a **Phase 4 decision contract** that turns that evidence into a stable, reviewable answer to three questions:

1. Is the disciplined SciPy baseline sufficient right now?
2. If not, which post-SciPy path should be explored first?
3. What migration sequence preserves facades and keeps the hybrid-coupled direction as the default kernel architecture?

The strongest fit is:

1. **A new decision-gate module under `src/modular_simulation/connection/benchmarking/`** that consumes Phase 3 report data plus explicit profiling/deployment inputs.
2. **One thin Phase 4 decision example/wrapper** that reuses `run_benchmark()`/`build_phase3_report()` rather than reimplementing benchmark logic.
3. **Two grep-verifiable docs**: one for the kernel-direction decision, one for the migration roadmap.

## Exact Recommendation for the Open Decision Shape

Use one machine-readable decision object with these minimum fields:

- `default_kernel_direction` — exact value `hybrid_coupled`
- `scipy_status` — exact values `sufficient`, `solver_limited`, or `needs_more_evidence`
- `recommended_solver_stack` — exact values `scipy`, `sundials4py`, or `petsc4py`
- `preserve_existing_facades` — boolean, must remain `true`
- `evidence_workload_ids` — exact Phase 3 workload ids
- `blocking_reasons` — explicit strings describing why migration is or is not justified
- `missing_evidence` — explicit strings when the benchmark report is not enough to justify a rewrite

Use one comparison matrix with exactly these candidate rows:

1. `disciplined_scipy`
2. `sundials4py`
3. `petsc4py`

And exactly these comparison columns:

- `stability_case`
- `latency_case`
- `deployment_risk`
- `compatibility`
- `phase3_workload_basis`

## Recommended Decision Rules

### Stay on SciPy when all are true
- Phase 3 report shows the candidate remains viable under the existing hard gates.
- Disqualification reasons are absent for the disciplined baseline.
- Additional profiling says solver-core dominance is **below 50%** of step wall time, meaning the remaining bottleneck is still likely Python glue, dense conversions, or repo-local overhead.

### Mark SciPy as solver-limited when all are true
- Phase 3 hard gates are missed on representative hard workloads.
- The baseline is not merely disqualified by hidden fallback or malformed telemetry.
- Explicit profiling says solver-core dominated cost is **>= 50%** of step wall time after the obvious SciPy-path fixes.

### Recommend `sundials4py` before PETSc when solver-limited
- It preserves the Python runtime and adapter seam more directly.
- It aligns with the project research recommendation for the first serious post-SciPy path.
- It carries lower deployment and mental-model risk than PETSc.

### Recommend PETSc only as later escalation
- Only after the Phase 4 decision says the problem has outgrown both disciplined SciPy and the `sundials4py` path.
- Only when sparse nonlinear solver composition / preconditioning needs clearly justify PETSc-level complexity.

## Recommended Implementation Decomposition

### Wave 1: Decision contract and benchmark-evidence evaluator
1. Add a focused TDD module for turning Phase 3 report output into a Phase 4 kernel-direction decision.
2. Encode exact sufficiency / solver-limited / missing-evidence rules using Phase 3 workload ids and gate fields.
3. Export the decision helper through `src/modular_simulation/connection/benchmarking/__init__.py`.

### Wave 2: Comparison matrix, thin decision example, and roadmap docs
1. Add a thin Phase 4 decision example/wrapper that reuses the Phase 3 benchmark report.
2. Publish a grep-verifiable decision doc covering exact workload ids, decision rules, and recommended solver sequence.
3. Publish a grep-verifiable migration roadmap that keeps hybrid-coupled as the default direction, preserves facades, and stages `sundials4py` before PETSc.

## Standard Stack

### Core
| Library | Purpose | Why Standard |
|---------|---------|--------------|
| Python 3.13 | Decision/report dataclasses, script output, docs checks | Required by the repo and already used for benchmark/reporting code. |
| pytest | Decision-gate and documentation regression checks | Existing test runner and already used for Phase 3 benchmark coverage. |
| Existing Phase 3 benchmark substrate | Source-of-truth evidence input | Prevents a second benchmark system. |

### Supporting
| Library | Purpose | When to Use |
|---------|---------|-------------|
| Existing `build_phase3_report()` output | Input to the Phase 4 decision gate | Always — Phase 4 should consume verified report data, not duplicate it. |
| Existing project research docs | Migration option evidence for `sundials4py` and PETSc | Use for justification text and comparison matrix values. |

### New dependency recommendation
**Do not add new third-party runtime dependencies in Phase 4.**

Phase 4 is a decision/roadmap layer. New solver libraries belong to later execution if the decision gate actually justifies them.

## Architecture Patterns

### Pattern 1: Decision layer in `src/`, thin Phase 4 wrapper in `examples/`
**What:** Keep reusable Phase 4 decision logic in `src/modular_simulation/connection/benchmarking/decision_gate.py`, then expose one thin example/wrapper for human-readable review.

**Why:** Matches the Phase 3 pattern of keeping examples thin and business logic reusable.

### Pattern 2: Reuse the verified Phase 3 canon exactly
**What:** The Phase 4 decision must carry the exact workload ids `ammonia_recycle_warm`, `staged_delay_control_disturbance`, and `checkpoint_restart_reconfigure`.

**Why:** PERF-05 and SOLV-04 require evidence-backed comparison under the same workloads and gates.

### Pattern 3: Separate architecture direction from solver-stack choice
**What:** Keep `default_kernel_direction=hybrid_coupled` distinct from `recommended_solver_stack`.

**Why:** The roadmap direction is about kernel architecture; the solver-stack recommendation is about when SciPy is sufficient versus when to explore `sundials4py` or later PETSc.

## Recommended Project Structure

```text
src/modular_simulation/connection/benchmarking/
├── decision_gate.py              # Phase 4 decision contract + evaluator
└── __init__.py                   # export Phase 4 helpers

examples/connection_layer/benchmarks/
└── kernel_direction_decision.py  # thin wrapper over Phase 3 benchmark + Phase 4 decision gate

docs/
├── kernel_direction_decision.md
└── kernel_migration_roadmap.md

tests/connection/
├── test_benchmark_decision_gate.py
└── test_kernel_direction_decision_example.py
```

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Phase 4 decision evidence | Ad hoc narrative docs only | Machine-readable decision helper over Phase 3 report output | PERF-05 requires evidence, not prose alone. |
| New comparison workloads | Phase 4-only scenario list | Existing Phase 3 canon and coverage matrix | SOLV-04 requires the same workload basis. |
| Solver option ranking | Taste-based preference list | Exact comparison matrix for `disciplined_scipy`, `sundials4py`, `petsc4py` | Keeps recommendation traceable to roadmap decisions. |
| Migration roadmap | Free-form generic phases | Facade-preserving staged roadmap with exact stack names | SOLV-05 requires compatibility and deployment-risk reasoning. |

## Common Pitfalls

### Pitfall 1: Reopening benchmark methodology in Phase 4
If Phase 4 invents new workloads or new gates, the SciPy decision stops being evidence-backed and becomes apples-to-oranges again.

### Pitfall 2: Confusing kernel architecture with solver library
Hybrid-coupled can remain the default direction even if the near-term solver recommendation stays on SciPy.

### Pitfall 3: Recommending PETSc too early
Project research explicitly holds PETSc as later escalation. Phase 4 should not collapse that into the first post-SciPy move.

### Pitfall 4: Treating missing profiling evidence as proof SciPy is solver-limited
The decision gate must support `needs_more_evidence` rather than forcing a rewrite recommendation from incomplete data.

## Likely File Touch Points

- `src/modular_simulation/connection/benchmarking/reporting.py` — source of Phase 3 report shape and gate fields.
- `src/modular_simulation/connection/benchmarking/contracts.py` — workload ids and latency-budget semantics.
- `src/modular_simulation/connection/benchmarking/__init__.py` — export surface for new Phase 4 helpers.
- `examples/connection_layer/benchmarks/macro_coupling_benchmark.py` — current Phase 3 wrapper to reuse rather than replace.
- `docs/kernel_benchmark_harness.md` — exact Phase 3 canon/gate contract to cite in Phase 4 docs.

## Open Questions

1. **Where should solver-core dominance data come from if it is not yet in the Phase 3 report?**
   - Recommendation: keep it as an explicit Phase 4 profiling input instead of overloading the Phase 3 report shape immediately.

2. **Should the final decision doc be fully generated or partially curated?**
   - Recommendation: keep the decision object generated and the roadmap doc curated but grep-verifiable.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest via `uv run python -m pytest` |
| Config file | `pyproject.toml` |
| Quick run command | `uv run python -m pytest tests/connection/test_benchmark_decision_gate.py -q` |
| Full suite command | `uv run python -m pytest tests/connection/test_benchmark_decision_gate.py tests/connection/test_kernel_direction_decision_example.py tests/connection/test_benchmark_reporting.py tests/connection/test_examples_benchmarks.py -q` |
| Estimated runtime | ~20 seconds |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PERF-05 | Phase 4 emits an explicit SciPy sufficiency / solver-limited / needs-more-evidence decision from benchmark evidence | contract | `uv run python -m pytest tests/connection/test_benchmark_decision_gate.py -q` | ❌ Wave 1 |
| SOLV-04 | Phase 4 compares `sundials4py` and `petsc4py` against the same Phase 3 workload basis | contract/docs | `uv run python -m pytest tests/connection/test_kernel_direction_decision_example.py -q` | ❌ Wave 2 |
| SOLV-05 | Phase 4 roadmap explicitly justifies migration by stability, latency, deployment risk, and compatibility while preserving facades | docs | `uv run python -m pytest tests/connection/test_kernel_direction_decision_example.py -q` | ❌ Wave 2 |

### Sampling Rate
- **Per task commit:** `uv run python -m pytest tests/connection/test_benchmark_decision_gate.py -q`
- **Per wave merge:** `uv run python -m pytest tests/connection/test_benchmark_decision_gate.py tests/connection/test_kernel_direction_decision_example.py tests/connection/test_benchmark_reporting.py tests/connection/test_examples_benchmarks.py -q`
- **Phase gate:** full targeted suite green before `/gsd-verify-work`

### Wave 0 Gaps
Existing pytest infrastructure covers this phase. No separate Wave 0 plan is needed; each execution task should create its tests before implementation.

## Sources

### Primary
- `.planning/phases/03-benchmark-harness-disciplined-baseline-comparison/03-VERIFICATION.md`
- `.planning/phases/03-benchmark-harness-disciplined-baseline-comparison/03-03-SUMMARY.md`
- `.planning/research/SUMMARY.md`
- `.planning/research/STACK-ALTERNATIVES.md`
- `.planning/research/PERFORMANCE.md`
- `src/modular_simulation/connection/benchmarking/contracts.py`
- `src/modular_simulation/connection/benchmarking/harness.py`
- `src/modular_simulation/connection/benchmarking/reporting.py`
- `examples/connection_layer/benchmarks/macro_coupling_benchmark.py`
- `docs/kernel_benchmark_harness.md`

### Secondary
- `.planning/PROJECT.md`
- `.planning/ROADMAP.md`
- `.planning/STATE.md`
- `src/modular_simulation/connection/kernel_adapter.py`
- `src/modular_simulation/connection/runtime/split_kernel_adapter.py`

## Metadata

**Confidence breakdown:**
- Decision-gate shape: HIGH
- Migration option framing: HIGH
- Exact file-level fit: MEDIUM-HIGH
- Need for new external runtime integrations in this phase: LOW

**Research date:** 2026-03-30
**Valid until:** 2026-04-29

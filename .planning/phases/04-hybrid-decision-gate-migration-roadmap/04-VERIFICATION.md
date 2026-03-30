---
phase: 04-hybrid-decision-gate-migration-roadmap
verified: 2026-03-30T12:16:44Z
status: passed
score: 6/6 must-haves verified
---

# Phase 4: Hybrid Decision Gate & Migration Roadmap Verification Report

**Phase Goal:** publish the Phase 4 kernel-direction decision and migration roadmap from reusable benchmark evidence, including a concrete public decision surface, explicit comparison of `disciplined_scipy`, `sundials4py`, and `petsc4py` on the same workload basis, and a facade-preserving migration roadmap.
**Verified:** 2026-03-30T12:16:44Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Team can produce one explicit machine-readable answer for whether the disciplined SciPy baseline is sufficient, solver-limited, or still missing decisive evidence. | ✓ VERIFIED | `src/modular_simulation/connection/benchmarking/decision_gate.py` defines `KernelDirectionDecision`, `KernelProfilingSummary`, and `build_kernel_direction_decision(...)`; `tests/connection/test_benchmark_decision_gate.py`; `uv run python -m pytest tests/connection/test_benchmark_decision_gate.py -q` passes within the targeted suite. |
| 2 | The Phase 4 decision keeps hybrid-coupled as the default kernel direction while separating architecture direction from solver-stack choice. | ✓ VERIFIED | `decision_gate.py` always returns `default_kernel_direction="hybrid_coupled"`; `examples/connection_layer/benchmarks/kernel_direction_decision.py` returns a public `decision` payload; `docs/kernel_direction_decision.md` and `docs/kernel_migration_roadmap.md` state the same rule. |
| 3 | Any recommendation to leave SciPy is tied to explicit benchmark gates and solver-core-dominance evidence rather than intuition. | ✓ VERIFIED | `decision_gate.py` requires gate failure plus `solver_core_fraction >= 0.5` for `solver_limited`, otherwise returns `needs_more_evidence`; covered by tests and direct spot-check command. |
| 4 | Team can read one explicit Phase 4 decision that says whether SciPy remains sufficient and what evidence would justify leaving it. | ✓ VERIFIED | `docs/kernel_direction_decision.md` names the workload canon, gate language, and evidence bar; `examples/.../kernel_direction_decision.py` publishes a concrete `decision` object. |
| 5 | Team can compare one Python-native post-SciPy path and one later non-Python-capable escalation path against the same Phase 3 workloads and gates. | ✓ VERIFIED | `examples/.../kernel_direction_decision.py` returns a 3-row `migration_candidates` matrix for `disciplined_scipy`, `sundials4py`, and `petsc4py`, each with shared `phase3_workload_basis`; docs repeat same ordering and basis. |
| 6 | Team has a concrete migration roadmap that keeps hybrid-coupled as the default direction and preserves existing facades where practical. | ✓ VERIFIED | `docs/kernel_migration_roadmap.md` stages `disciplined_scipy` → `hybrid_coupled` → `sundials4py` adapter spike → PETSc later only if justified, while explicitly preserving `PlantBackendSession` and `CandidateKernelAdapter`. |

**Score:** 6/6 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `src/modular_simulation/connection/benchmarking/decision_gate.py` | Phase 4 decision contract and benchmark-evidence evaluator | ✓ VERIFIED | Exists, substantive (148 lines), exports typed decision surface, and is exercised by direct tests and wrapper usage. |
| `src/modular_simulation/connection/benchmarking/__init__.py` | Public export surface for Phase 4 decision helpers | ✓ VERIFIED | Exists and re-exports `KernelDirectionDecision`, `KernelProfilingSummary`, and `build_kernel_direction_decision`. |
| `tests/connection/test_benchmark_decision_gate.py` | Regression contract for SciPy sufficiency and solver-limited rules | ✓ VERIFIED | Exists with five behavior checks covering sufficient, solver-limited, later PETSc escalation, and missing evidence. |
| `examples/connection_layer/benchmarks/kernel_direction_decision.py` | Thin public Phase 4 decision wrapper | ✓ VERIFIED | Exists, imports `run_benchmark` and `build_kernel_direction_decision`, and returns the exact four top-level keys required by plan/tests. |
| `docs/kernel_direction_decision.md` | Public kernel-direction decision document | ✓ VERIFIED | Exists and contains workload canon, hard-gate language, `sundials4py` first-escalation rule, and PETSc later-only language. |
| `docs/kernel_migration_roadmap.md` | Concrete staged migration roadmap | ✓ VERIFIED | Exists and explicitly preserves `PlantBackendSession` and `CandidateKernelAdapter` while naming the exact migration sequence. |
| `tests/connection/test_kernel_direction_decision_example.py` | Regression checks for public output and docs | ✓ VERIFIED | Exists and directly reads markdown docs plus example output shape. |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `src/modular_simulation/connection/benchmarking/decision_gate.py` | `src/modular_simulation/connection/benchmarking/reporting.py` | Phase 3 report keys consumed by the Phase 4 evaluator | ✓ WIRED | `gsd-tools verify key-links` passed; `decision_gate.py` reads `candidate_rankings`, `minimum_rtf_gate`, and `latency_budget_fraction` from the Phase 3 report shape produced by `reporting.py`. |
| `tests/connection/test_benchmark_decision_gate.py` | `src/modular_simulation/connection/benchmarking/decision_gate.py` | TDD coverage for decision outputs | ✓ WIRED | Test imports evaluator and asserts `scipy_status`, `recommended_solver_stack`, and `default_kernel_direction`. |
| `examples/connection_layer/benchmarks/kernel_direction_decision.py` | `src/modular_simulation/connection/benchmarking/decision_gate.py` | Thin wrapper calling the reusable Phase 4 evaluator | ✓ WIRED | Example imports and calls `build_kernel_direction_decision(...)` directly. |
| `docs/kernel_direction_decision.md` | `docs/kernel_benchmark_harness.md` | Shared workload ids and hard-gate language | ✓ WIRED | Decision doc repeats `ammonia_recycle_warm`, `staged_delay_control_disturbance`, `checkpoint_restart_reconfigure`, and `minimum_rtf_gate=4.0`. |
| `docs/kernel_migration_roadmap.md` | `.planning/research/STACK-ALTERNATIVES.md` | Stack ordering and migration-risk rationale | ✓ WIRED | Roadmap contains `sundials4py`, `petsc4py`, `PlantBackendSession`, and `CandidateKernelAdapter`, matching the research-defined ordering and facade rationale. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| --- | --- | --- | --- | --- |
| `src/modular_simulation/connection/benchmarking/decision_gate.py` | `evidence_workload_ids` / decision fields | `phase3_report` input populated from `build_phase3_report(...)` in `src/modular_simulation/connection/benchmarking/reporting.py` | Yes — Phase 3 report returns real `candidate_rankings`, `candidate_workloads`, `coverage_matrix`, and gate values. | ✓ FLOWING |
| `examples/connection_layer/benchmarks/kernel_direction_decision.py` | `phase3_report` and `decision` | `run_benchmark()` in `examples/connection_layer/benchmarks/macro_coupling_benchmark.py`, then `build_kernel_direction_decision(...)` | Yes — `run_benchmark()` builds workloads, runs `BenchmarkHarness`, and returns `build_phase3_report(...)` output used in the public payload. | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Targeted Phase 4 regression suite stays green | `uv run python -m pytest tests/connection/test_benchmark_decision_gate.py tests/connection/test_kernel_direction_decision_example.py tests/connection/test_benchmark_reporting.py tests/connection/test_examples_benchmarks.py -q` | `21 passed in 0.33s` | ✓ PASS |
| Public decision surface returns required keys and candidate matrix | `uv run python -c "from examples.connection_layer.benchmarks.kernel_direction_decision import run_kernel_direction_decision; ..."` | Printed keys `['decision', 'migration_candidates', 'phase3_report', 'roadmap_stages']`, candidate count `3`, default direction `hybrid_coupled`, and candidate ids `('disciplined_scipy', 'sundials4py', 'petsc4py')`. | ✓ PASS |
| Solver-limited escalation keeps `sundials4py` first and PETSc later-only | `uv run python -c "from modular_simulation.connection.benchmarking import build_kernel_direction_decision, KernelProfilingSummary; ..."` | Printed `hybrid_coupled solver_limited sundials4py ('petsc4py',)` | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| `PERF-05` | `04-01-PLAN.md`, `04-02-PLAN.md` | Team can decide whether leaving the current SciPy baseline is justified using benchmark evidence rather than intuition or single-scenario timing. | ✓ SATISFIED | `decision_gate.py` encodes sufficient / solver-limited / needs-more-evidence states from Phase 3 report data; tests verify all paths; public example and docs expose the decision surface. |
| `SOLV-04` | `04-02-PLAN.md` | Team can compare at least one post-SciPy Python-native path and at least one non-Python-capable path when benchmark evidence suggests the baseline may be solver-limited. | ✓ SATISFIED | `run_kernel_direction_decision()` returns `disciplined_scipy`, `sundials4py`, and `petsc4py` rows with a shared `phase3_workload_basis`; docs state same workload canon and escalation order. |
| `SOLV-05` | `04-01-PLAN.md`, `04-02-PLAN.md` | Team can justify any solver-stack migration in terms of stability improvement, latency improvement, deployment risk, and compatibility with the existing runtime/session facades. | ✓ SATISFIED | Migration matrix includes `stability_case`, `latency_case`, `deployment_risk`, and `compatibility`; roadmap preserves `PlantBackendSession` and `CandidateKernelAdapter`; decision gate preserves `preserve_existing_facades=True`. |

No orphaned Phase 4 requirements were found: ROADMAP and plan frontmatter both map only `PERF-05`, `SOLV-04`, and `SOLV-05` to this phase.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| — | — | No TODO/FIXME/placeholder or empty-implementation stub patterns found in scanned Phase 4 files. | ℹ️ Info | No blocker anti-patterns detected. |

### Human Verification Required

None.

### Gaps Summary

No blocking gaps found. The codebase contains a real Phase 4 decision evaluator, a thin public wrapper over the Phase 3 benchmark substrate, a fixed same-workload comparison matrix for `disciplined_scipy` / `sundials4py` / `petsc4py`, and a facade-preserving migration roadmap. Targeted tests and spot-checks confirm the published decision surface works and keeps `hybrid_coupled` as the default direction while making `sundials4py` the first post-SciPy path and PETSc later-only.

---

_Verified: 2026-03-30T12:16:44Z_
_Verifier: the agent (gsd-verifier)_

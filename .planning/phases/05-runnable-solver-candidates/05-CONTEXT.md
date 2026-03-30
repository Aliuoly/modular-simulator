# Phase 5: Runnable solver candidates - Context

**Gathered:** 2026-03-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Make the existing candidate-adapter seam and Phase 3 benchmark harness run a real multi-candidate comparison on the fixed three-workload canon, adding runnable post-SciPy solver candidates without changing the public runtime facades first. This phase is about executable same-workload comparison evidence for the milestone, not more roadmap prose and not a public runtime rewrite.

</domain>

<decisions>
## Implementation Decisions

### Candidate set
- **D-01:** Phase 5 should deliver two real post-SciPy runnable comparison candidates: one SUNDIALS-backed path and one PETSc-backed path.
- **D-02:** The SUNDIALS-backed path is the first serious post-SciPy escalation and should be treated as the lighter comparison candidate.
- **D-03:** The PETSc-backed path is the heavier comparison candidate and remains later than the SUNDIALS path in the migration order even though both become runnable in this phase.
- **D-04:** Candidate scope is not artificially limited to Python-native solutions in principle, but Phase 5 should lock to the recommended milestone-closing set above rather than broadening into a larger ecosystem bake-off.

### Harness selection flow
- **D-05:** Keep candidate wiring phase-local for now rather than introducing a reusable registry or environment auto-discovery layer.
- **D-06:** The public benchmark/comparison surface should hard-code the Phase 5 comparison set explicitly so runs are reproducible and downstream planning stays focused on getting the real candidates working.
- **D-07:** The current single-candidate wrapper must evolve into an explicit multi-candidate comparison flow over the same canon rather than remaining `disciplined_split`-only.

### Delay-state fidelity
- **D-08:** Every new runnable candidate must support checkpoint restore and delay-state round-trip parity strongly enough to start from comparable accepted snapshots on the canonical workloads.
- **D-09:** Fresh-start-only comparisons are not acceptable for Phase 5 because they would weaken the fairness and same-workload evidence contract established in Phases 2 and 3.

### Comparison readiness
- **D-10:** Phase 5 is only comparison-ready when the disciplined split baseline, SUNDIALS-backed candidate, and PETSc-backed candidate can all run the fixed three-workload canon through the same harness contract.
- **D-11:** Comparable reports must still be produced even when one or more candidates are disqualified by gates; visibility of failure or disqualification is part of milestone readiness.
- **D-12:** The fixed canon remains `ammonia_recycle_warm`, `staged_delay_control_disturbance`, and `checkpoint_restart_reconfigure`.
- **D-13:** Phase 5 must preserve `PlantBackendSession` and the `CandidateKernelAdapter` seam instead of forcing a public runtime facade rewrite to accommodate new solver candidates.

### the agent's Discretion
- Choose the exact SUNDIALS and PETSc bindings or integration layers, as long as the delivered candidates are genuinely runnable and satisfy the locked restore/fairness contract.
- Choose the exact phase-local API shape for selecting the hard-coded comparison set, as long as the benchmark/example entry points remain explicit and reproducible.
- Choose the exact telemetry or adapter helper structure needed to make the new candidates comparable, as long as the existing Phase 3 fairness and reporting contract remains intact.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone and phase contract
- `.planning/PROJECT.md` — Milestone v1.0 constraints and the requirement to finish with a credible kernel-stability comparison rather than documentation alone.
- `.planning/REQUIREMENTS.md` — Existing kernel, delay, and solver requirements carried forward from earlier phases; Phase 5 planning must map the new runnable-candidate work onto updated requirement IDs.
- `.planning/ROADMAP.md` — Phase sequence, completed Phase 4 outcome, and the placeholder Phase 5 entry that this context now sharpens.
- `.planning/STATE.md` — Current project position after Phase 4 completion and the roadmap-evolution note that added Phase 5.

### Prior locked phase decisions
- `.planning/phases/01-failure-semantics-acceptance-gates/01-CONTEXT.md` — Whole-plant accepted snapshot boundary, explicit rejection semantics, and no hidden partial success.
- `.planning/phases/02-kernel-adapter-warm-starts-delay-state/02-CONTEXT.md` — `CandidateKernelAdapter` core, warm-start and checkpoint restore expectations, and explicit delay-state treatment requirements.
- `.planning/phases/03-benchmark-harness-disciplined-baseline-comparison/03-CONTEXT.md` — Fixed checkpoint-first workload canon, fairness contract, telemetry expectations, and the rule that disciplined split remains visible even when disqualified.

### Phase 4 migration policy
- `docs/kernel_direction_decision.md` — Locks `hybrid_coupled` as the default direction unless evidence disproves it and states that leaving SciPy requires the fixed canon plus solver-core evidence.
- `docs/kernel_migration_roadmap.md` — Locks the migration ordering: disciplined SciPy hardening, `hybrid_coupled` default direction, SUNDIALS-first post-SciPy spike, then PETSc later only if justified.
- `examples/connection_layer/benchmarks/kernel_direction_decision.py` — Thin public Phase 4 decision surface showing the intended comparison candidates and roadmap stages.

### Runtime and benchmark seams
- `src/modular_simulation/connection/kernel_adapter.py` — Required adapter contract, optional solver capabilities, and delay-state interfaces every candidate must honor.
- `src/modular_simulation/connection/runtime/split_kernel_adapter.py` — Honest runnable baseline adapter and current transport-history semantics that new candidates must compare against.
- `src/modular_simulation/connection/benchmarking/harness.py` — Existing reusable harness seam that already drives candidate factories from checkpoint seeds and shared fairness metadata.
- `src/modular_simulation/connection/benchmarking/contracts.py` — Formal fairness, latency-budget, and disqualification structures for candidate comparison.
- `src/modular_simulation/connection/benchmarking/reporting.py` — Existing cross-candidate reporting/ranking logic that should be reused once multiple runnable candidates exist.
- `examples/connection_layer/benchmarks/macro_coupling_benchmark.py` — Current thin wrapper that hard-codes only `disciplined_split`; this is the immediate comparison-entry seam Phase 5 will evolve.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/modular_simulation/connection/benchmarking/harness.py` — Already runs a candidate via `candidate_adapter_factory(seed)` and enforces the shared fairness contract before timing and reporting.
- `src/modular_simulation/connection/benchmarking/reporting.py` — Already supports multi-candidate report assembly if given multiple candidate record/config sets.
- `src/modular_simulation/connection/runtime/split_kernel_adapter.py` — Provides the current runnable baseline and an honest example of delay-semantics and telemetry publication.
- `examples/connection_layer/benchmarks/macro_coupling_benchmark.py` — Natural public entry point to expand from one candidate to the hard-coded Phase 5 comparison set.

### Established Patterns
- Public comparison and decision surfaces are thin wrappers over reusable logic rather than monolithic scripts.
- The codebase prefers explicit typed contracts, dataclasses, and `__all__` exports for reusable surfaces.
- Checkpoint restore and accepted-snapshot replay are already treated as the authoritative comparison entry point, not ad hoc model rebuilding.
- Benchmark evidence keeps disqualified candidates visible rather than silently dropping them from reports.

### Integration Points
- `src/modular_simulation/connection/kernel_adapter.py` — Main interface every new candidate must implement or be adapted to.
- `src/modular_simulation/connection/benchmarking/harness.py:25-73` — The exact place where candidate factories are invoked from shared seeds.
- `examples/connection_layer/benchmarks/macro_coupling_benchmark.py:14-35` — The immediate phase-local comparison flow that currently needs to expand beyond `disciplined_split`.
- `tests/connection/test_benchmark_harness.py` and `tests/connection/test_examples_benchmarks.py` — Existing test seams for verifying same-canon execution and example-wrapper behavior.

</code_context>

<specifics>
## Specific Ideas

- The user explicitly said Phase 5 should not be artificially limited to Python-only solutions: "Anything is fair game, even non python solutions."
- The user accepted the recommended concrete set anyway, so planning should stay focused on a milestone-closing `SUNDIALS + PETSc` implementation rather than reopening the candidate search.
- The milestone gap to close is runnable candidate comparison on the same canon, not more policy or roadmap documentation.

</specifics>

<deferred>
## Deferred Ideas

- Julia-based solver comparison path — credible future candidate area, but deferred because it would add cross-runtime integration and state-marshalling work beyond the locked Phase 5 set.
- Broader ecosystem bake-off across CasADi, Assimulo, or other non-SciPy candidates — deferred because this phase should focus on making the selected milestone-closing comparison set genuinely runnable.

</deferred>

---

*Phase: 05-runnable-solver-candidates*
*Context gathered: 2026-03-30*

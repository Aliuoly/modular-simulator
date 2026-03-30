# Phase 5: Runnable solver candidates - Research

**Researched:** 2026-03-30
**Domain:** Runnable SUNDIALS-backed and PETSc-backed benchmark candidates over the fixed canon
**Confidence:** MEDIUM

<user_constraints>
## Locked Decisions

- **D-01:** Deliver two real post-SciPy runnable comparison candidates: one SUNDIALS-backed path and one PETSc-backed path.
- **D-02:** Treat the SUNDIALS-backed path as the lighter first serious post-SciPy escalation.
- **D-03:** Keep the PETSc-backed path as the heavier later migration option even though it becomes runnable in this phase.
- **D-05:** Keep candidate wiring phase-local; do not introduce a reusable registry or environment auto-discovery layer.
- **D-06:** Hard-code the Phase 5 comparison set in the public benchmark/comparison surface.
- **D-08:** Every new runnable candidate must support checkpoint restore and delay-state round-trip parity.
- **D-09:** Fresh-start-only comparisons are not acceptable.
- **D-10:** Comparison readiness requires the disciplined split baseline, SUNDIALS-backed candidate, and PETSc-backed candidate all to run the fixed three-workload canon through the same harness contract.
- **D-11:** Reports must still surface disqualified candidates.
- **D-12:** The fixed canon remains `ammonia_recycle_warm`, `staged_delay_control_disturbance`, and `checkpoint_restart_reconfigure`.
- **D-13:** Preserve `PlantBackendSession` and the `CandidateKernelAdapter` seam; do not force a public runtime rewrite.

## Deferred Ideas

- Julia-based solver comparison path.
- Broader non-SciPy ecosystem bake-off beyond the locked SUNDIALS and PETSc set.
</user_constraints>

<phase_requirements>
## Recommended Phase Requirement IDs

| ID | Description | Why it belongs in Phase 5 |
|----|-------------|---------------------------|
| PERF-06 | Team can run the disciplined split baseline plus the chosen SUNDIALS-backed and PETSc-backed candidates through the fixed canon and publish one same-harness report that keeps disqualified candidates visible. | Phase 5 closes the gap between Phase 4 policy comparison and actual runnable same-workload evidence. |
| SOLV-06 | Team can instantiate real SUNDIALS-backed and PETSc-backed `CandidateKernelAdapter` implementations behind the existing facades without replacing `PlantBackendSession` or the benchmark substrate first. | This is the core implementation scope of the phase. |
| DELY-05 | Team can restore accepted snapshots and transport-history/delay payloads across every runnable comparison candidate so same-workload runs start from comparable checkpoints rather than fresh starts. | The locked fairness contract forbids fresh-start-only evidence. |
</phase_requirements>

## Summary

Phase 5 should be planned as one interface-first wiring step plus two candidate-adapter implementation slices and one final benchmark-surface wiring slice. The existing repo already has the required substrate for fairness, checkpoints, delay-state transport history, telemetry normalization, report ranking, and policy output. The missing pieces are:

1. A truthful Phase 5 comparison contract that hard-codes the three candidate slots without introducing discovery or registry machinery.
2. One runnable SUNDIALS-backed adapter that preserves accepted-snapshot and delay-state parity.
3. One runnable PETSc-backed adapter that preserves the same parity.
4. One thin public benchmark wrapper that runs all three candidates over the fixed canon and emits one combined report.

## Recommended Binding Choices

### SUNDIALS-backed candidate

**Use `scikits.odes` with the IDA path as the concrete Phase 5 implementation binding.**

Why this is the best fit for planning:

- The public SUNDIALS docs are current, but the Python packages surfaced by research split into two camps: newer CVODE-focused wrappers (`scikit-sundae`) and the longer-lived `scikits.odes` family with explicit SUNDIALS packages on conda-forge.
- Phase 5 needs checkpoint-restored coupled-step evaluation with residual/Jacobian-friendly callbacks, not just a black-box ODE smoke runner. `scikits.odes` gives a more plausible DAE/residual-shaped path for the repo’s macro-step solve than the CVODE-only documentation surfaced for `scikit-sundae`.
- Research also found current conda-forge packaging for `scikits.odes` / `scikits_odes_sundials`, which makes it the more conservative planning choice for a “real runnable candidate” phase.

**Important compatibility rule:** keep the externally published Phase 4 comparison slot label `sundials4py` in report/config IDs if needed for roadmap continuity, but record the concrete Phase 5 implementation binding explicitly as `scikits.odes.ida` so the code is truthful.

### PETSc-backed candidate

**Use `petsc4py` with `PETSc.SNES` as the concrete Phase 5 implementation binding.**

Why this is the best fit:

- PETSc and petsc4py are actively maintained with 2025 releases and current documentation.
- The current repo’s hydraulic solve seam is already a nonlinear residual/Jacobian solve, which maps more directly to PETSc SNES than to time-integration-first APIs.
- PETSc remains the heavier candidate per D-03, but Phase 5 still needs a runnable comparison path to close the milestone evidence gap.

## Implementation Shape That Best Fits the Existing Code

### Pattern 1: Keep the public wrapper thin

- Continue the Phase 3 / Phase 4 pattern: `examples/connection_layer/benchmarks/macro_coupling_benchmark.py` remains a thin public entry point.
- Hard-code the comparison set there or in one adjacent Phase-5-only helper.
- Do **not** add a registry, plugin loader, env probing, or dynamic candidate discovery.

### Pattern 2: Treat candidate adapters as honest `CandidateKernelAdapter` implementations

- New adapters should live under `src/modular_simulation/connection/runtime/` beside `split_kernel_adapter.py`.
- Both adapters must honor `initialize`, `warm_start`, `evaluate_candidate_step`, `capture_delay_state`, `restore_delay_state`, and `supported_optional_capabilities`.
- Both adapters must preserve `KernelDelayStrategy.EXTERNAL_TRANSPORT_HISTORY` unless they also publish an explicit replacement mapping. Phase 5 should prefer parity rather than a new delay model.

### Pattern 3: Reuse the existing fairness/reporting substrate instead of inventing a Phase 5 report format

- Keep `BenchmarkHarness`, `BenchmarkCandidateConfig`, `build_phase3_report()`, and existing report keys as the canonical same-workload comparison surface.
- Add only the minimum Phase-5-specific contract needed to define the hard-coded candidate set and truthful implementation-binding metadata.

## File-Level Recommendation

```text
src/modular_simulation/connection/benchmarking/
├── runnable_candidate_contracts.py        # Phase 5 hard-coded candidate slots + binding metadata
└── __init__.py                            # export Phase 5 contract helpers

src/modular_simulation/connection/runtime/
├── sundials_kernel_adapter.py             # concrete SUNDIALS-backed candidate adapter
└── petsc_kernel_adapter.py                # concrete PETSc-backed candidate adapter

examples/connection_layer/benchmarks/
└── macro_coupling_benchmark.py            # final hard-coded three-candidate wrapper

tests/connection/
├── test_runnable_candidate_contracts.py
├── test_sundials_kernel_adapter.py
├── test_petsc_kernel_adapter.py
└── test_examples_benchmarks.py
```

## Concrete Planning Guidance

### Wave 1: Interface-first contract and dependency declaration

- Add a Phase 5 contract module that freezes the hard-coded candidate order as exactly `disciplined_split`, `sundials4py`, and `petsc4py` for public continuity.
- Record concrete implementation-binding metadata separately as `split_kernel_adapter`, `scikits.odes.ida`, and `petsc4py.PETSc.SNES`.
- Add Python dependency declarations for `scikits.odes`, `petsc`, and `petsc4py` while keeping downstream imports lazy so test collection fails only on real runtime use, not import-time discovery.

### Wave 2A: SUNDIALS-backed adapter slice

- Implement one `SundialsIdaKernelAdapter` that restores accepted snapshots through the existing network/runtime seam, carries forward transport-history delay state, and exposes finite telemetry costs.
- Reuse `CompiledHydraulicGraph.build_solver_inputs()` plus the existing residual/Jacobian assembly helpers so the adapter is solving the repo’s real compiled system, not a synthetic toy problem.

### Wave 2B: PETSc-backed adapter slice

- Implement one `PetscSnesKernelAdapter` with the same snapshot and delay-state parity contract.
- Use SNES residual/Jacobian callbacks over the compiled hydraulic system rather than inventing a second nonlinear model.

### Wave 3: Final comparison surface wiring

- Update `run_benchmark()` to run all three candidates through the exact Phase 3 workloads.
- Preserve visible disqualification and per-workload rows for every candidate.
- Keep the split baseline on the existing `_build_kernel_adapter()` path; wire the SUNDIALS and PETSc candidates explicitly rather than hiding them behind new network internals.

## Pitfalls to Avoid

1. **Do not weaken startup conditions** — no fresh-start-only candidate path.
2. **Do not hide missing native dependencies with auto-skip reporting** — Phase 5 must target genuinely runnable candidates, not optional stubs.
3. **Do not fork the benchmark report shape** — build on existing reporting keys.
4. **Do not mutate the default split adapter path** — Phase 5 adds candidates for comparison; it does not replace the default runtime yet.
5. **Do not let public labels and concrete bindings drift silently** — preserve the public comparison slot names for roadmap continuity, but encode the real implementation binding explicitly in code/tests.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest via `uv run python -m pytest` |
| Config file | `pyproject.toml` |
| Quick run command | `uv run python -m pytest tests/connection/test_runnable_candidate_contracts.py tests/connection/test_sundials_kernel_adapter.py tests/connection/test_petsc_kernel_adapter.py tests/connection/test_examples_benchmarks.py -q` |
| Full suite command | `uv run python -m pytest tests/connection/test_runnable_candidate_contracts.py tests/connection/test_sundials_kernel_adapter.py tests/connection/test_petsc_kernel_adapter.py tests/connection/test_examples_benchmarks.py tests/connection/test_benchmark_harness.py tests/connection/test_benchmark_reporting.py tests/connection/test_kernel_direction_decision_example.py -q` |
| Estimated runtime | ~35 seconds |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PERF-06 | One hard-coded benchmark run executes `disciplined_split`, `sundials4py`, and `petsc4py` over the fixed canon and still surfaces disqualified rows. | wrapper/report | `uv run python -m pytest tests/connection/test_examples_benchmarks.py -q` | ❌ Wave 3 |
| SOLV-06 | SUNDIALS-backed and PETSc-backed candidate adapters implement the existing adapter seam without public facade rewrites. | contract/adapter | `uv run python -m pytest tests/connection/test_sundials_kernel_adapter.py tests/connection/test_petsc_kernel_adapter.py -q` | ❌ Wave 2 |
| DELY-05 | Every runnable candidate restores accepted snapshots and transport-history delay state from the same checkpoint seeds. | restore parity | `uv run python -m pytest tests/connection/test_sundials_kernel_adapter.py tests/connection/test_petsc_kernel_adapter.py tests/connection/test_runtime_persistence_contract.py -q` | ❌ Wave 2 |

### Wave 0 Gaps

Existing pytest infrastructure is sufficient. No separate Wave 0 testing plan is needed.

## Sources

### Repo Sources
- `.planning/phases/05-runnable-solver-candidates/05-CONTEXT.md`
- `.planning/phases/03-benchmark-harness-disciplined-baseline-comparison/03-02-SUMMARY.md`
- `.planning/phases/03-benchmark-harness-disciplined-baseline-comparison/03-03-SUMMARY.md`
- `.planning/phases/04-hybrid-decision-gate-migration-roadmap/04-01-SUMMARY.md`
- `.planning/phases/04-hybrid-decision-gate-migration-roadmap/04-02-SUMMARY.md`
- `src/modular_simulation/connection/kernel_adapter.py`
- `src/modular_simulation/connection/benchmarking/harness.py`
- `src/modular_simulation/connection/benchmarking/contracts.py`
- `src/modular_simulation/connection/benchmarking/reporting.py`
- `src/modular_simulation/connection/runtime/split_kernel_adapter.py`
- `examples/connection_layer/benchmarks/macro_coupling_benchmark.py`

### External Sources
- PETSc docs and package pages for current PETSc / petsc4py usage and release status.
- `scikits.odes` / `scikits_odes_sundials` conda-forge package pages.
- scikit-sundae CVODE docs used as a comparison point when evaluating SUNDIALS Python binding fit.

## Metadata

- **Binding choice confidence:** MEDIUM
- **Benchmark substrate fit:** HIGH
- **Delay-state parity fit:** HIGH
- **Risk:** native dependency installation and callback glue are the main execution risks; plan should isolate them into separate adapter slices.

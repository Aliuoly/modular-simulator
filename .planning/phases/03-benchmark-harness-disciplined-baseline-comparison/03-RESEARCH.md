# Phase 3: Benchmark Harness & Disciplined Baseline Comparison - Research

**Researched:** 2026-03-30
**Domain:** Canonical benchmark harness, comparable candidate telemetry, realtime viability gates, and disciplined baseline reporting
**Confidence:** MEDIUM

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Report realtime factor as the headline metric, but treat `RTF >= 100` as a preferred headroom target rather than a hard pass gate.
- **D-02:** Use accepted-step latency with a hard `p95` gate and report median for context.
- **D-03:** Evaluate realtime viability from accepted-step timing only; still record rejected-step and retry activity in telemetry and disqualification output.
- **D-04:** Express the hard latency budget relative to simulated step size, not as a fixed millisecond ceiling.
- **D-05:** Set the initial hard `p95` latency budget to `<= 25%` of simulated step size.
- **D-06:** Keep a small fixed canon of version-controlled benchmark workloads.
- **D-07:** Keep the canonical suite balanced across warm runs, disturbances, recycle-heavy behavior, controller/network coupling, restart/reconfiguration, and delay-heavy semantics.
- **D-08:** Make canonical benchmark entry checkpoint-first so every candidate starts from comparable accepted states.
- **D-09:** Keep the canonical suite to about `3-4` workloads for Phase 3.
- **D-10:** Multi-tag workloads are allowed, but the workload-to-scenario coverage matrix must be explicit.
- **D-11:** Always show the disciplined split/SciPy baseline in reports even when it fails the rules; disqualified runs are excluded from viability ranking.
- **D-12:** Any fallback usage is disqualifying for benchmark acceptance.
- **D-13:** Every candidate must run under the same checkpoints, tolerances, physical-acceptance gates, and telemetry outputs.

### the agent's Discretion
- Choose the exact hard minimum realtime viability line below the reported `100x` headroom target, as long as reports distinguish the minimum pass gate from the aspirational target.
- Choose the exact artifact format for raw traces, summaries, and coverage-matrix output, as long as accepted-step `p95`, median latency, disqualification reasons, and workload coverage remain explicit.
- Choose the exact composition of the `3-4` benchmark workloads, as long as the suite remains checkpoint-first, balanced, and delay-aware.

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PERF-01 | Team can run a version-controlled benchmark harness over canonical checkpointed workloads covering warm runs, disturbances, recycle-heavy cases, controller/network coupling, and restart/reconfiguration paths. | Use a small checkpoint-first workload catalog with explicit tags, deterministic builders, and a reusable harness in `src/modular_simulation/connection/benchmarking/`. |
| PERF-02 | Team can record per-step telemetry for accepted/rejected steps, residual/convergence status, Jacobian or residual assembly cost, linear-solve cost, and wall-clock latency. | Normalize every candidate step into one benchmark attempt record that preserves accepted/rejected outcome, fallback keys, Picard data, replay hashes, and candidate telemetry fields. |
| PERF-03 | Team can evaluate candidate kernels against explicit realtime viability thresholds using realtime factor plus median, p95, and p99 accepted-step latency. | Publish machine-readable latency-budget contracts and report accepted-step-only latency summaries, with `p95 <= 25%` of simulated step size and a separate minimum realtime-factor gate. |
| PERF-04 | Team can disqualify any candidate from performance comparison when it violates physical-acceptance gates, hides solver failure, or depends on emergency clipping/fallback to appear stable. | Treat fallback use, physical-acceptance failure, hidden solver failure, hidden recovery, clipping-masked stability, and telemetry contract violations as explicit disqualification reasons. |
| SOLV-01 | Team can compare candidate solver substrates fairly using the same workloads, checkpoints, tolerances, physical-acceptance gates, and telemetry outputs. | Put checkpoint IDs, tolerance profiles, physical-acceptance profile names, and telemetry contract versions directly in workload and comparison records. |
| SOLV-03 | Team can evaluate a disciplined current-stack baseline before approving a migration to a new solver substrate. | Always run and report the split/SciPy baseline through the same harness, even when it is disqualified, and keep ranking logic separate from reporting visibility. |
| DELY-04 | Team can benchmark delay-heavy and transport-lag-sensitive scenarios so whole-flowsheet directions are not approved without evidence that delay semantics still behave credibly. | Include at least one explicitly tagged delay-heavy workload and carry adapter delay-semantics metadata plus transport-history replay evidence into benchmark traces. |
</phase_requirements>

## Summary

Phase 3 should be planned as a reusable substrate benchmark layer, not as a one-off example script. The repo already has the comparison primitives needed from Phases 1 and 2: a typed `CandidateKernelAdapter`, explicit delay semantics metadata, checkpoint-first restore through `PlantBackendSession` / `ConnectionNetwork`, per-step bookkeeping via `MacroStepBookkeeping`, and deterministic replay hashes from `runtime_replay_state_hash(...)`. The main gap is packaging those seams into one disciplined benchmark contract.

The strongest Phase 3 fit is:

1. **Reusable benchmark contracts under `src/modular_simulation/connection/benchmarking/`** for workloads, attempt records, latency budgets, and report rows.
2. **A checkpoint-first workload catalog with exactly 3 canonical workloads** and an explicit coverage matrix.
3. **A harness that runs the split/SciPy baseline and future candidates through the same checkpoints, tolerances, physical-acceptance gates, and telemetry normalization.**
4. **A reporting layer that separates visibility from ranking** so the split baseline is always shown per D-11, but disqualified candidates never win by speed alone.

### Exact recommendation for the open pass-line choice

Choose:

- **Minimum realtime viability gate:** `RTF >= 4.0`
- **Headline aspirational target:** `RTF >= 100.0` (reported, not required)
- **Hard accepted-step latency gate:** `accepted_step_p95 <= 0.25 * simulated_step_size`

Why this fit is coherent:

- It honors D-01 by keeping `100x` visible without making it the hard pass/fail line.
- It honors D-04 and D-05 by expressing the latency gate as a fraction of step size.
- `RTF >= 4.0` matches the spirit of a game-backend viability floor without collapsing the benchmark into a binary `100x-or-fail` rule.

### Recommended canonical workload set

Keep the canon to **3 workloads** per D-06 and D-09, with explicit tags per D-10:

1. **`ammonia_recycle_warm`**
   - Source anchor: `examples/unit_process_flowsheet/complex_6_ammonia_recycle_loop.py`
   - Tags: `warm_run`, `recycle_heavy`
   - Purpose: honest warm-run baseline on a recycle-sensitive flowsheet.

2. **`staged_delay_control_disturbance`**
   - Source anchor: `examples/simple_irreversible_energy_balance_system/three_tank_staged_connected_control.py`
   - Tags: `disturbance`, `controller_network_coupling`, `delay_heavy`
   - Purpose: cover controller/network coupling and delay-sensitive disturbance handling in one checkpoint-first case.

3. **`checkpoint_restart_reconfigure`**
   - Source anchor: Phase-3-owned deterministic builder using `PlantBackendSession`, `ConnectionNetwork`, and saved accepted checkpoints
   - Tags: `restart_reconfiguration`, `delay_heavy`
   - Purpose: prove replay-safe restart/reconfiguration behavior under the same acceptance and delay rules.

This 3-workload set satisfies D-07 without padding the suite.

## Recommended Implementation Decomposition

### Wave 1: Benchmark contracts and telemetry normalization
1. Create typed benchmark contracts for workloads, attempt records, latency budgets, coverage rows, and report rows.
2. Normalize `KernelCandidateStepResult`, `KernelAdapterTelemetry`, delay semantics, fallback metadata, and replay hashes into one benchmark-attempt record.
3. Lock the contract with targeted pytest coverage before building the runner.

### Wave 2: Canonical workload catalog and harness runner
1. Create the 3-workload checkpoint-first catalog with explicit multi-tag coverage.
2. Implement a reusable harness that loads accepted checkpoints, runs one candidate over one workload, and emits deterministic raw attempt traces.
3. Expand `examples/connection_layer/benchmarks/macro_coupling_benchmark.py` into a thin wrapper over the reusable harness.

### Wave 3: Viability scoring, disqualification, and disciplined baseline reporting
1. Add accepted-step latency summaries (median, p95, p99), realtime-factor scoring, and the explicit `RTF >= 4.0` / `RTF >= 100.0` distinction.
2. Add disqualification logic for fallback, hidden solver failure, physical-acceptance failure, clipping-masked stability, hidden recovery, and telemetry contract violations.
3. Publish ranked and disqualified report rows while always showing the split/SciPy baseline.

## Standard Stack

### Core
| Library | Purpose | Why Standard |
|---------|---------|--------------|
| Python 3.13 | Benchmark dataclasses, timing utilities, JSON-serializable result shaping | Required by `pyproject.toml` and current repo conventions. |
| pytest | Contract, harness, and reporting regression coverage | Existing test runner and already used for deterministic contract tests. |
| SciPy / current split runtime | Baseline candidate substrate | Phase 3 must evaluate the current stack before any migration decision. |

### Supporting
| Library | Purpose | When to Use |
|---------|---------|-------------|
| Existing `CandidateKernelAdapter` seam | Candidate-neutral stepping and telemetry source | Use for every benchmark candidate to preserve Phase 2 fairness rules. |
| Existing runtime snapshot helpers | Checkpoint-first workload entry and replay hash evidence | Use for every workload start and restart/reconfiguration path. |

### New dependency recommendation
**Do not add new third-party benchmark dependencies in Phase 3.**

The repo already has the primitives needed: timing via Python stdlib, typed records via dataclasses, and candidate execution via the adapter seam. Adding a benchmarking framework would increase surface area without helping the locked fairness rules.

## Architecture Patterns

### Pattern 1: Benchmark substrate in `src/`, thin example wrapper in `examples/`
**What:** Keep reusable harness logic under `src/modular_simulation/connection/benchmarking/` and let `examples/connection_layer/benchmarks/macro_coupling_benchmark.py` stay a thin importable wrapper.

**Why:** The current example benchmark is a deterministic smoke stub, but Phase 3 needs reusable substrate code that later phases can consume directly.

### Pattern 2: Checkpoint-first workload definitions
**What:** Each canonical workload should identify a deterministic builder + accepted checkpoint entry, not a cold-start-only demo path.

**Why:** D-08 and D-13 require all candidates to start from comparable accepted states under the same contract.

### Pattern 3: Accepted-step-only viability metrics, all-attempt diagnostics
**What:** Store every attempt, but compute viability summaries from accepted-step latency only.

**Why:** This is the only way to satisfy D-03 without hiding rejected-step instability or fallback behavior.

### Pattern 4: Visibility separate from ranking
**What:** Reports should always include the split/SciPy baseline row, but ranking should exclude disqualified runs.

**Why:** D-11 requires disciplined visibility; PERF-04 requires disqualified candidates never be accepted by speed alone.

## Recommended Project Structure

```text
src/modular_simulation/connection/benchmarking/
├── __init__.py
├── contracts.py        # workload, attempt, threshold, and report dataclasses/enums
├── telemetry.py        # candidate-step normalization helpers
├── workloads.py        # canonical checkpoint-first workload catalog
├── harness.py          # candidate/workload execution loop
└── reporting.py        # latency summaries, disqualification, ranking, coverage matrix

examples/connection_layer/benchmarks/
└── macro_coupling_benchmark.py  # thin wrapper around the reusable harness

tests/connection/
├── test_benchmark_contracts.py
├── test_benchmark_harness.py
├── test_benchmark_reporting.py
└── test_examples_benchmarks.py
```

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Candidate comparison surface | Per-candidate bespoke benchmark adapters | Existing `CandidateKernelAdapter` seam | Phase 2 already made fairness and delay semantics explicit. |
| Workload start state | Ad hoc cold-start reconstruction | `save_checkpoint()` / `load_checkpoint()` / accepted snapshot restore | D-08 requires checkpoint-first comparability. |
| Telemetry comparison | Candidate-specific dicts with different keys | One benchmark attempt record fed from `KernelAdapterTelemetry` and replay hashes | PERF-02 and SOLV-01 require one shape. |
| Report disqualification | Narrative comments in docs only | Machine-readable disqualification enums + report rows | PERF-04 needs enforceable rules, not prose only. |
| Delay coverage | Generic “stress” workload labels | Explicit `delay_heavy` tags plus adapter delay-semantics capture | DELY-04 must stay observable in the evidence itself. |

## Common Pitfalls

### Pitfall 1: Letting the example wrapper become the benchmark architecture
The current `macro_coupling_benchmark.py` is a smoke stub. If Phase 3 grows all logic there, later phases will need to reverse-engineer the harness out of an example file.

### Pitfall 2: Mixing accepted and rejected attempts into latency gates
That would violate D-03 and make unstable candidates look slower for the wrong reason instead of explicitly disqualified.

### Pitfall 3: Treating fallback as a warning instead of a disqualifier
D-12 makes fallback disqualifying. Reports should count it, explain it, and exclude the run from viability ranking.

### Pitfall 4: Hiding delay semantics behind generic workload names
If the workload tags and traces do not explicitly mark `delay_heavy`, later decisions can accidentally approve a candidate that never demonstrated credible lag behavior.

### Pitfall 5: Re-using different tolerances or acceptance profiles for different candidates
That breaks SOLV-01 and D-13 immediately, even if the code looks clean.

## Likely File Touch Points

- `src/modular_simulation/connection/kernel_adapter.py` — source of comparable candidate telemetry and delay semantics.
- `src/modular_simulation/connection/runtime/split_kernel_adapter.py` — disciplined baseline adapter for the split/SciPy path.
- `src/modular_simulation/connection/runtime/runtime.py` — source of `ConnectionRuntimeStepResult` timing/bookkeeping data and runtime snapshots.
- `src/modular_simulation/connection/runtime/runtime_persistence.py` — deterministic replay-hash support.
- `src/modular_simulation/cli/backend_session.py` — stable checkpoint save/load seam for checkpoint-first workloads.
- `examples/connection_layer/benchmarks/macro_coupling_benchmark.py` — current smoke benchmark wrapper to expand, not replace with business logic.
- `tests/connection/test_examples_benchmarks.py` — existing smoke-level benchmark wrapper test to evolve alongside the richer wrapper shape.

## Open Questions

1. **Should raw traces be stored as JSONL-like per-attempt rows or as one nested JSON-style report object?**
   - Recommendation: keep the in-memory contract as typed per-attempt rows plus one summarized report object; serialize however is most convenient later.

2. **Should the Phase 3 restart/reconfiguration workload be sourced from an existing example or a dedicated deterministic builder?**
   - Recommendation: use a dedicated Phase-3-owned deterministic builder so restart and queued reconfiguration stay explicit and stable.

3. **How much of residual/Jacobian/linear-solve cost is available from the split baseline today?**
   - Recommendation: encode nullable fields in the benchmark telemetry contract and require explicit `None` rather than missing keys when a candidate cannot provide the metric honestly.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest via `uv run python -m pytest` |
| Config file | `pyproject.toml` |
| Quick run command | `uv run python -m pytest tests/connection/test_benchmark_contracts.py -q` |
| Full suite command | `uv run python -m pytest tests/connection/test_benchmark_contracts.py tests/connection/test_benchmark_harness.py tests/connection/test_benchmark_reporting.py tests/connection/test_examples_benchmarks.py -q` |
| Estimated runtime | ~35 seconds |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PERF-01 | Canonical workload catalog is fixed, checkpoint-first, and explicitly tagged | contract/integration | `uv run python -m pytest tests/connection/test_benchmark_harness.py -q` | ❌ Wave 1 |
| PERF-02 | Benchmark attempt records normalize accepted/rejected steps into one comparable shape | contract | `uv run python -m pytest tests/connection/test_benchmark_contracts.py -q` | ❌ Wave 1 |
| PERF-03 | Reporting computes accepted-step median, p95, p99, and realtime factor against explicit gates | contract | `uv run python -m pytest tests/connection/test_benchmark_reporting.py -q` | ❌ Wave 3 |
| PERF-04 | Fallback, hidden failure, clipping, and acceptance violations disqualify candidates | contract | `uv run python -m pytest tests/connection/test_benchmark_reporting.py -q` | ❌ Wave 3 |
| SOLV-01 | Same checkpoints, tolerances, gates, and telemetry contract are enforced across candidates | integration | `uv run python -m pytest tests/connection/test_benchmark_harness.py -q` | ❌ Wave 2 |
| SOLV-03 | Split/SciPy baseline is always reported and run through the same harness | integration | `uv run python -m pytest tests/connection/test_benchmark_reporting.py tests/connection/test_examples_benchmarks.py -q` | ❌ Wave 3 |
| DELY-04 | Delay-heavy scenarios stay explicit in the benchmark matrix and traces | integration | `uv run python -m pytest tests/connection/test_benchmark_harness.py -q` | ❌ Wave 2 |

### Sampling Rate
- **Per task commit:** `uv run python -m pytest tests/connection/test_benchmark_contracts.py -q`
- **Per wave merge:** `uv run python -m pytest tests/connection/test_benchmark_contracts.py tests/connection/test_benchmark_harness.py tests/connection/test_benchmark_reporting.py tests/connection/test_examples_benchmarks.py -q`
- **Phase gate:** full targeted suite green before `/gsd-verify-work`

### Wave 0 Gaps
Existing pytest infrastructure covers this phase. No separate Wave 0 plan is needed; each execution task should create its tests before implementation.

## Sources

### Primary
- Repo source: `src/modular_simulation/connection/kernel_adapter.py`
- Repo source: `src/modular_simulation/connection/runtime/split_kernel_adapter.py`
- Repo source: `src/modular_simulation/connection/runtime/runtime.py`
- Repo source: `src/modular_simulation/connection/runtime/runtime_persistence.py`
- Repo source: `src/modular_simulation/connection/topology/network.py`
- Repo source: `src/modular_simulation/connection/runtime/connected_plant_orchestrator.py`
- Repo source: `src/modular_simulation/cli/backend_session.py`
- Repo source: `examples/connection_layer/benchmarks/macro_coupling_benchmark.py`
- Repo source: `tests/connection/test_examples_benchmarks.py`

### Secondary
- `.planning/phases/02-kernel-adapter-warm-starts-delay-state/02-01-SUMMARY.md`
- `.planning/phases/02-kernel-adapter-warm-starts-delay-state/02-02-SUMMARY.md`
- `.planning/phases/02-kernel-adapter-warm-starts-delay-state/02-03-SUMMARY.md`
- `.planning/phases/02-kernel-adapter-warm-starts-delay-state/02-04-SUMMARY.md`
- `docs/examples_catalog.md`

## Metadata

**Confidence breakdown:**
- Benchmark contract shape: HIGH
- Workload decomposition: MEDIUM
- Exact report thresholds: MEDIUM-HIGH
- Existing-code fit: HIGH

**Research date:** 2026-03-30
**Valid until:** 2026-04-29

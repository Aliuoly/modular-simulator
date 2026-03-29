# Performance Benchmarking Guidance

**Project:** ModularSimulator
**Milestone:** v1.0 Kernel stability
**Researched:** 2026-03-29
**Confidence:** HIGH for benchmark method, MEDIUM-HIGH for thresholds

## Executive Recommendation

Do **not** decide “SciPy is too slow” from a single hard flowsheet, a cold-start run, or an average wall-clock number. The right question is: **can a SciPy-based kernel, after obvious structural fixes, meet realtime backend latency and stability targets on representative workloads with acceptable physical fidelity?**

For this milestone, the correct evidence standard is:

1. benchmark the **same scenario/checkpoint** across candidate kernel directions,
2. require **physical parity / invariant compliance** before comparing speed,
3. separate **cold-start**, **warm steady-state**, **disturbance transient**, and **reconfiguration/restart** costs,
4. attribute time into **solver core vs Jacobian assembly vs linear algebra vs Python glue**, and
5. escalate beyond SciPy only when the remaining bottleneck is clearly in solver capabilities, not in repo-local overhead or missed sparse/warm-start opportunities.

Repo evidence already says the current baseline would produce misleading results if benchmarked naively:
- `ProcessModel.step()` uses `solve_ivp(...)` but does **not** check `result.success` before committing state (`src/modular_simulation/measurables/process_model.py`).
- The hydraulic path assembles a sparse triplet, then densifies it and solves with `np.linalg.solve` (`src/modular_simulation/connection/hydraulics/hydraulic_solver.py`).
- Runtime orchestration still advances `subsystem_process_step` before `connection_runtime_coupling` (`src/modular_simulation/connection/runtime/connected_plant_orchestrator.py`, `src/modular_simulation/connection/runtime/runtime.py`).
- The existing “benchmark” is only a deterministic placeholder and must not be used for solver decisions (`examples/connection_layer/benchmarks/macro_coupling_benchmark.py`).

## Benchmark Harness Requirements

The harness should be built to answer **go / no-go** questions for a game backend, not just produce pretty timing plots.

### Required harness characteristics

1. **Identical workload state across candidates**
   - Same compiled flowsheet or same checkpointed initial state.
   - Same disturbance script, command schedule, and solver tolerances.

2. **Warm vs cold runs separated**
   - Report separately:
     - compile + initialization,
     - first accepted step,
     - warm steady-state stepping,
     - restart/reload,
     - post-edit recompile/reinitialize.

3. **Deterministic and low-noise execution**
   - Fixed seeds.
   - CPU pinning / stable benchmark environment (`pyperf` guidance).
   - No plotting, no debug logging, no profiler unless profiling mode is explicitly enabled.

4. **Candidate-neutral API**
   - Every candidate exposes the same outputs:
     - accepted/rejected step,
     - wall time,
     - simulated time advanced,
     - residual / convergence diagnostics,
     - invariant violations.

5. **Two benchmark modes**
   - **Latency mode:** one session on one pinned core.
   - **Throughput mode:** multiple concurrent sessions on representative deployment hardware.

6. **Physical-acceptance gate before performance scoring**
   - A faster candidate that violates mass balance, accepts failed solves, or misses event boundaries does not pass.

## Recommended Benchmark Classes / Workloads

Use repo-native scenarios first. They are closer to actual migration risk than synthetic ODE toys.

| Class | Repo anchor | Why it matters | Benchmark shape |
|---|---|---|---|
| A. Simple acyclic warm run | `examples/unit_process_flowsheet/easy_2_heater_flash.py` or `complex_8_pressure_flash_recovery.py` | Baseline overhead and simple stiff thermo behavior | Warm 200-500 accepted steps; no edits |
| B. Pressure/flash disturbance | `examples/dynamic_simulation_demos/flash_backpressure_valve_demo.py` | Event-like pressure change; flash sensitivity | Warm-up, single valve/backpressure step, measure recovery window |
| C. Recycle-heavy flowsheet | `examples/unit_process_flowsheet/complex_6_ammonia_recycle_loop.py` | Canonical stale-coupling stressor | Cold start + warm run + recycle disturbance |
| D. Controller + network coupling | `examples/dynamic_simulation_demos/coupled_three_tank_edge_valve_demo.py` | Closed-loop behavior, queueing, actuator timing | Warm run with setpoint change / valve action |
| E. Cross-unit dynamic coupling | `examples/dynamic_simulation_demos/coupled_cstr_flash_physical_actuator_demo.py` | Unit interaction under actuator change | Warm run with mid-horizon disturbance |
| F. Reconfiguration / restart | runtime checkpoint + compile/reload path | Brownfield backend must survive live edits | checkpoint restore, parameter-only edit, structure-changing edit |

### Minimum workload matrix

Every solver candidate should be tested on at least:

1. **Cold start:** compile/init + first 5 accepted steps
2. **Warm steady-state:** 200+ accepted steps after warm-up
3. **Disturbance transient:** one scripted event in a warm system
4. **Restart:** restore from checkpoint and continue
5. **Reconfiguration:** one safe parameter edit and one structure-changing edit

If a candidate cannot run C + D + F credibly, it is not ready for solver-stack decisions.

## Metrics That Reflect Realtime Backend Needs

### Primary metrics

1. **Realtime factor (RTF)**
   - `RTF = simulated_seconds / wall_seconds`
   - This is the top-level metric for game viability.

2. **Wall time per accepted macro-step**
   - median / p95 / p99
   - Tail latency matters more than mean latency for a live backend.

3. **Accepted-step ratio**
   - accepted / attempted
   - Rejected-step thrash is operationally equivalent to slowness.

4. **Cold-start latency**
   - compile + initialize + first accepted step

5. **Restart / post-edit recovery latency**
   - checkpoint load to first accepted warm step

6. **Physical quality metrics**
   - mass/energy drift over horizon
   - invariant violations (negative inventory, invalid composition sum, impossible pressure states)
   - missed event / boundary detections

### Solver counters to record

For ODE / implicit candidates, record at minimum:
- `nfev`
- `njev`
- `nlu`
- nonlinear iterations
- line-search / damping backtracks
- rejected internal steps
- convergence / error-test failures

For algebraic / least-squares / root solves, record:
- nonlinear iterations
- Jacobian evaluations
- linear-solver iterations or factorizations
- trust-region or damping reductions
- termination reason / success flag

## Recommended Thresholds / Decision Targets

These thresholds are for **single-session latency mode** on target deployment-class hardware.

### Realtime targets

**Target**
- Warm-run **median RTF >= 3.0** on Class A/B
- Warm-run **median RTF >= 2.0** on Class C/D/E
- Warm-run **p95 RTF >= 1.25** on Class C/D/E

**Minimum acceptable for v1.0**
- Warm-run **median RTF >= 1.5** on representative hard workloads
- Warm-run **p95 wall time per accepted step <= 0.8 x simulation_dt**
- Warm-run **p99 wall time per accepted step <= 1.0 x simulation_dt**

**Fail**
- Sustained **RTF < 1.0** on target hard workloads
- Or **p95 step wall time > simulation_dt**
- Or any candidate that only reaches target by loosening tolerances past acceptable physical error

This directly encodes the user’s requirement: a backend that computes slower than realtime on representative gameplay flowsheets is not acceptable.

### Stability / correctness targets

A candidate is disqualified from performance comparison if any of the following occur at meaningful frequency:
- solver reports failure but state is committed,
- invariant violations exceed tolerance,
- restart/edit recovery is unreliable,
- benchmark only succeeds with emergency clipping or hidden fallback.

## Profiling Dimensions

The benchmark harness should attribute wall time into these buckets:

| Dimension | Why it matters |
|---|---|
| Solver core time | Tells whether the integrator/nonlinear solver is the bottleneck |
| Jacobian assembly time | Common hidden cost in Python models |
| Linear solve / factorization time | Critical for sparse vs dense decisions |
| Residual evaluation time | Often dominates before solver choice matters |
| State pack/unpack / snapshot time | Brownfield adapter overhead |
| Hydraulic solve time | Important because current path densifies sparse structure |
| Boundary propagation / transport update time | Needed to distinguish kernel vs orchestration costs |
| Python overhead | Function-call, object, allocation, and dispatch cost |
| Compile / warm-start preparation cost | Important for cold start and reconfiguration |
| Reinitialization / consistent-IC cost | Mandatory if whole-flowsheet / DAE paths are considered |

### Profiling stack

- **Wall-clock benchmarking:** `pyperf`-style disciplined runs
- **Function profiling:** `cProfile`
- **Solver telemetry:** explicit counters emitted by the kernel
- **Phase timing:** timers around process step, hydraulics, transport, boundary propagation, residual assembly, Jacobian assembly, linear solve

Do not rely on `cProfile` alone for benchmark numbers; Python docs explicitly position it as a profiler, not a benchmarking tool.

## Decision Gates: Stay on SciPy vs Escalate

### Stay on SciPy if all are true

1. After obvious fixes, SciPy meets the realtime thresholds above on Class C/D/E.
2. Physical quality is acceptable without hidden clipping/fallback.
3. Profiling shows the remaining cost is mostly in repo-local model code, orchestration, or avoidable dense conversions.
4. Sparse Jacobians / `jac_sparsity` / warm starts materially improve results.
5. Cold-start and restart costs are acceptable for backend play.

**“Obvious fixes” means at least:**
- propagate `solve_ivp.success` and termination diagnostics,
- stop densifying obviously sparse hydraulic solves where possible,
- benchmark `BDF` / `Radau` with Jacobian or `jac_sparsity`,
- separate cold and warm numbers,
- reuse warm starts / compiled structure.

### Escalate beyond current SciPy use, but still within SciPy, if

1. Current split/hybrid SciPy baseline misses targets,
2. profiling shows cost is still mostly in dense Jacobian estimation / dense linear algebra / missing sparse exploitation,
3. candidate sparse SciPy upgrades plausibly attack the dominant cost center.

This is the most likely next step for this repo.

### Justify a non-SciPy solver stack only if all are true

1. A **well-instrumented SciPy path** with sparse-aware upgrades still fails the realtime thresholds on multiple hard workloads.
2. The failure is **solver-core dominated**, not Python glue dominated.
   - As a rule of thumb: if **< 50%** of step wall time is in solver core / factorization / nonlinear iteration, changing solver stack is probably premature.
3. The missing capability is structural, not incidental. Examples:
   - robust DAE consistent-initial-condition handling,
   - better large sparse linear solver / preconditioning path,
   - stronger root/event handling for coupled algebraic constraints,
   - whole-system implicit solve behavior SciPy cannot deliver adequately.
4. The benchmark gap is material:
   - e.g. SciPy remains **RTF < 1.0** or **p95 step time > simulation_dt** on hard workloads after sparse/warm-start upgrades.

### Justify whole-flowsheet coupled or DAE approaches only if

1. Hybrid / partitioned approaches still fail on recycle-heavy or pressure-coupled classes,
2. failure is mostly due to stale-coupling / algebraic inconsistency rather than raw CPU time,
3. the benchmark includes consistent-initialization and restart cost, not just warm steady-state,
4. the proposed whole-coupled / DAE path is evaluated against the **same** workload matrix and telemetry.

## Pitfalls in Interpreting Results

1. **Benchmarking only easy acyclic flowsheets**
   - This will systematically overstate split-step adequacy.

2. **Using mean latency instead of p95/p99**
   - Game backends fail at the tail first.

3. **Comparing candidates with different tolerances or different physical outcomes**
   - Faster-but-less-correct is not a valid win.

4. **Ignoring cold-start, restart, or reconfiguration cost**
   - Whole-flowsheet / DAE approaches can look good on warm runs and fail operationally.

5. **Confusing Python overhead with solver limits**
   - If adapter glue, array reshaping, or object churn dominates, a solver rewrite is the wrong decision.

6. **Letting failed solves count as completed work**
   - Current repo behavior around `solve_ivp` success propagation makes this a real risk.

7. **Comparing sparse and dense paths unfairly**
   - Current hydraulics path already exposes sparse structure; benchmarking dense-only SciPy as “SciPy baseline” would be misleading.

8. **Not measuring compile / consistent-IC / warm-start preparation**
   - Especially important for DAE or whole-flowsheet approaches.

9. **Benchmarking with noisy machines**
   - Use pinned cores / stable environment or the tail numbers are garbage.

## Milestone Implications for Requirements / Roadmap

### What v1.0 should require

1. A real benchmark harness under version control.
2. Canonical checkpointed workloads for classes A-F.
3. Mandatory solver telemetry for every accepted step.
4. Explicit physical-acceptance gates before performance comparison.
5. Decision review after SciPy sparse/warm-start upgrades, before any non-SciPy commitment.

### Recommended roadmap sequence

1. **Benchmark substrate first**
   - replace the placeholder benchmark with real scenario runners and telemetry.
2. **Instrument current kernel**
   - phase timers, solver success/failure, accepted/rejected steps, invariant checks.
3. **Run SciPy-with-discipline baseline**
   - current split/hybrid path, but with honest success propagation and profiling.
4. **Run sparse SciPy upgrade experiments**
   - Jacobian/Jacobian sparsity, sparse linear algebra, warm-start reuse.
5. **Only then compare non-SciPy / DAE / whole-coupled spikes**
   - using the same workload matrix and thresholds.

### Explicit milestone decision rule

For v1.0, the team should **not** approve a non-SciPy rewrite unless the benchmark report shows:
- representative hard workloads,
- SciPy upgraded baseline still misses minimum realtime thresholds,
- profiling says the dominant cost is solver-structural,
- and whole-coupled / DAE alternatives improve both stability and latency enough to justify migration cost.

## Sources

### HIGH confidence
- `.planning/PROJECT.md`
- `src/modular_simulation/measurables/process_model.py`
- `src/modular_simulation/connection/hydraulics/hydraulic_solver.py`
- `src/modular_simulation/connection/runtime/connected_plant_orchestrator.py`
- `src/modular_simulation/connection/runtime/runtime.py`
- `src/modular_simulation/gameplay/realtime_service.py`
- `examples/connection_layer/benchmarks/macro_coupling_benchmark.py`
- SciPy `solve_ivp` docs: https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.solve_ivp.html
- SciPy `least_squares` docs: https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.least_squares.html
- Python profiling docs: https://docs.python.org/3/library/profile.html
- pyperf system guidance: https://pyperf.readthedocs.io/en/latest/system.html
- SUNDIALS CVODE docs: https://sundials.readthedocs.io/en/latest/cvode/Usage/index.html
- SUNDIALS IDA docs: https://sundials.readthedocs.io/en/latest/ida/Usage/index.html

### MEDIUM confidence
- Repo example workloads listed above are strong proxies for representative stress classes, but still need final milestone approval as the canonical benchmark suite.

---
*Prepared for roadmap creation; do not treat as solver-library selection.*

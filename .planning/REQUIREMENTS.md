# Requirements: ModularSimulator

**Defined:** 2026-03-29
**Core Value:** Deliver a grounded, composable process-simulation backend that stays physically credible enough for teaching while still usable as a realtime game substrate.

## v1 Requirements

Requirements for milestone v1.0 Kernel stability. Each maps to roadmap phases.

### Kernel Correctness

- [ ] **KERN-01**: Team can classify and reproduce the current split-kernel failure modes that create stale-coupling, non-physical inventory, or stale-pressure-driven flow on representative complex flowsheets.
- [ ] **KERN-02**: Team can validate whether a candidate kernel step produced one accepted coupled plant state rather than publishing partially updated unit and connection states.
- [ ] **KERN-03**: Team can reject under-specified, over-specified, or structurally inconsistent flowsheet states before runtime stepping begins.
- [x] **KERN-04**: Team can initialize and warm-start candidate kernels from the last accepted plant state, checkpoint restore, or post-edit recovery path.
- [ ] **KERN-05**: Team can enforce physical feasibility guards that prevent accepted states with negative inventory, invalid composition normalization, or other non-physical plant states.

### Performance Evidence

- [x] **PERF-01**: Team can run a version-controlled benchmark harness over canonical checkpointed workloads covering warm runs, disturbances, recycle-heavy cases, transport-history-sensitive staged flow paths, and restart/reconfiguration paths.
- [x] **PERF-02**: Team can record per-step telemetry for accepted/rejected steps, residual/convergence status, Jacobian or residual assembly cost, linear-solve cost, and wall-clock latency.
- [x] **PERF-03**: Team can evaluate candidate kernels against explicit realtime viability thresholds using realtime factor plus median, p95, and p99 accepted-step latency.
- [x] **PERF-04**: Team can disqualify any candidate from performance comparison when benchmark traces carry producer-backed rank-blocking evidence such as fallback use, hidden solver failure, telemetry-contract failure, or future physical-acceptance/clipping/hidden-recovery signals.
- [x] **PERF-05**: Team can decide whether leaving the current SciPy baseline is justified using benchmark evidence rather than intuition or single-scenario timing.
- [ ] **PERF-06**: Team can run the disciplined split baseline plus the chosen SUNDIALS-backed and PETSc-backed candidates through the fixed canonical workloads and publish one same-harness report that keeps disqualified candidates visible.

### Solver Substrate Comparison

- [x] **SOLV-01**: Team can compare candidate solver substrates fairly using the same flowsheet workloads, checkpoints, tolerances, physical-acceptance gates, and telemetry outputs.
- [x] **SOLV-02**: Team can expose a solver-kernel adapter seam with state, residual, Jacobian, bounds, initialization, warm-start, and telemetry interfaces so candidate stacks can be swapped without rewriting gameplay/session surfaces first.
- [x] **SOLV-03**: Team can evaluate a disciplined current-stack baseline before approving a migration to a new solver substrate.
- [x] **SOLV-04**: Team can compare at least one post-SciPy Python-native path and at least one non-Python-capable path when benchmark evidence suggests the baseline may be solver-limited.
- [x] **SOLV-05**: Team can justify any solver-stack migration in terms of stability improvement, latency improvement, deployment risk, and compatibility with the existing runtime/session facades.
- [ ] **SOLV-06**: Team can instantiate real SUNDIALS-backed and PETSc-backed `CandidateKernelAdapter` implementations behind the existing runtime/session facades without replacing `PlantBackendSession` or the shared benchmark substrate first.

### Delay Semantics

- [x] **DELY-01**: Team can preserve or explicitly replace existing transport-lag behavior so candidate kernels do not erase current delay semantics when moving toward hybrid or whole-flowsheet coupling.
- [x] **DELY-02**: Team can define how deadtime is represented in each candidate kernel direction, including whether delay remains external history/buffer state, becomes augmented state, or requires a different hybrid treatment.
- [x] **DELY-03**: Team can restore and safely update deadtime or transport-history state across checkpoint reloads, warm starts, and runtime edits.
- [x] **DELY-04**: Team can benchmark delay-heavy and transport-lag-sensitive scenarios so whole-flowsheet directions are not approved without evidence that delay semantics still behave credibly.
- [ ] **DELY-05**: Team can restore accepted snapshots and transport-history or delay payloads across every runnable comparison candidate so same-workload benchmark runs start from comparable checkpoint state rather than fresh starts.

## Future Requirements

Deferred until after the milestone establishes the kernel direction and benchmark evidence.

### Kernel Expansion

- **FUTR-01**: Team can deploy hybrid subgraph escalation as the default runtime mode across production workloads.
- **FUTR-02**: Team can support edit-aware incremental recompilation for only the affected kernel subgraph after runtime changes.
- **FUTR-03**: Team can run automated robustness sweeps as regression gates for every kernel mode.

### Advanced Solver Directions

- **FUTR-04**: Team can run a whole-simulator dynamic DAE kernel across all units if hybrid coupling is still insufficient.
- **FUTR-05**: Team can adopt specialized symbolic, JIT, or cross-runtime solver stacks only after the baseline comparison shows a material advantage.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Frontend or client feature work | This milestone is focused on backend kernel decisions, not UI scope |
| New chemistry or new unit-model families | Would confound kernel comparison and migration evidence |
| Automatic hidden solver retries as the main stabilization strategy | Hides failure modes and weakens benchmark evidence |
| Unbounded global solve every tick without a realtime budget | Conflicts with game-backend latency requirements |
| Solver-stack selection based on taste or one-off timings | This milestone requires evidence-backed comparison and decision criteria |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| KERN-01 | Phase 1 | Pending |
| KERN-02 | Phase 1 | Pending |
| KERN-03 | Phase 1 | Pending |
| KERN-04 | Phase 2 | Complete |
| KERN-05 | Phase 1 | Pending |
| PERF-01 | Phase 3 | Complete |
| PERF-02 | Phase 3 | Complete |
| PERF-03 | Phase 3 | Complete |
| PERF-04 | Phase 3 | Complete |
| PERF-05 | Phase 4 | Complete |
| PERF-06 | Phase 5 | Pending |
| SOLV-01 | Phase 3 | Complete |
| SOLV-02 | Phase 2 | Complete |
| SOLV-03 | Phase 3 | Complete |
| SOLV-04 | Phase 4 | Complete |
| SOLV-05 | Phase 4 | Complete |
| SOLV-06 | Phase 5 | Pending |
| DELY-01 | Phase 2 | Complete |
| DELY-02 | Phase 2 | Complete |
| DELY-03 | Phase 2 | Complete |
| DELY-04 | Phase 3 | Complete |
| DELY-05 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 22 total
- Mapped to phases: 22
- Unmapped: 0

---
*Requirements defined: 2026-03-29*
*Last updated: 2026-03-29 after initial milestone requirement definition*

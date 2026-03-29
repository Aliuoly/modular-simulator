# Project Research Summary

**Project:** ModularSimulator
**Domain:** Brownfield simulation kernel stability for complex process flowsheets
**Researched:** 2026-03-29
**Confidence:** MEDIUM-HIGH

## Executive Summary

ModularSimulator is not choosing a brand-new simulator architecture from scratch; it is deciding how to stabilize a brownfield, realtime-capable process-simulation backend without breaking the existing session, gameplay, and HTTP-facing substrate. Across the research, the consistent conclusion is that experts do **not** solve this class of problem by adding more retries to a sequential split-step loop. They add stronger coupled-state semantics, explicit residual ownership, better initialization, sparse Jacobian-aware numerics, and diagnostics that explain why a solve was accepted, degraded, or rejected.

The recommended direction for milestone v1.0 is a **hybrid-coupled kernel**: keep the current outer orchestrator, compile lifecycle, and `PlantBackendSession` facade, but insert a new kernel coordinator that can route between legacy split-step, hybrid coupled correction on strongly interacting regions, and—only later if evidence demands it—a whole-flowsheet coupled solve. In practice that means staying on Python 3.13 while treating SciPy as the first disciplined baseline rather than the assumed final stack: prototype with sparse Jacobians/linear solves, bounded residual correction, warm starts, and deterministic benchmark telemetry first; then evaluate **official SUNDIALS via `sundials4py`** as the first serious post-SciPy substrate and reserve **PETSc/petsc4py** for a later escalation if benchmark evidence shows the kernel needs PETSc-level sparse nonlinear machinery.

The main risks are architectural self-deception and operational regressions: preserving stale unit/network lag inside a “new” kernel, treating algebraic closure as explicit state, hiding instability with clamps, failing at restart or live edits, and losing realtime performance by ignoring sparsity and acceptance semantics. The mitigation is phased: first define coupled-state ownership, invariants, and solver diagnostics; then build pluggable kernel infrastructure and hybrid correction on the worst subgraphs; then decide whether whole-flowsheet or DAE-oriented escalation is actually justified by benchmark evidence.

## Key Findings

### Recommended Stack

The stack recommendation is conservative on platform choice and aggressive on numerical discipline. Keep the existing Python backend and evolve the kernel in place rather than introducing a parallel engine. The strongest near-term upgrades are still inside SciPy, but only as a disciplined baseline: use stiff implicit methods (`BDF`/`Radau`) instead of defaulting research to `LSODA`, keep Jacobians sparse end-to-end, use bounded nonlinear correction for algebraic closure, and add telemetry plus benchmark fixtures so kernel directions are compared on representative flowsheets rather than intuition. If that upgraded baseline still fails realtime or stability targets, the first serious post-SciPy move is **`sundials4py`**, with **PETSc/petsc4py** held in reserve for a later sparse-nonlinear-systems escalation.

**Core technologies:**
- **Python 3.13.x**: retain the existing runtime substrate — avoids a costly migration unrelated to the milestone.
- **SciPy `solve_ivp` with `BDF`/`Radau` (1.17.x)**: disciplined stiff-stepping baseline — necessary evidence step, not assumed end-state.
- **SciPy sparse + sparse linear algebra (1.17.x)**: sparse Jacobian assembly and linear solves — critical because the current hydraulic path throws away sparsity by densifying.
- **SciPy `least_squares` + `Bounds` (1.17.x)**: bounded correction and initialization solves — needed to keep candidate states physically feasible.
- **Solver telemetry + deterministic benchmark harnesses**: compare split, hybrid, and coupled directions on canonical flowsheets — required for roadmap decisions.
- **Numba 0.64.x**: profile-guided acceleration only after the kernel interfaces stabilize.
- **`sundials4py` 7.6.0 beta**: first serious post-SciPy substrate for CVODE/IDA/KINSOL-class ODE, DAE, and nonlinear initialization paths if benchmark evidence justifies leaving SciPy.
- **PETSc + `petsc4py`**: high-ceiling escalation path if representative flowsheets prove the kernel needs custom preconditioning, matrix-free operators, or deeper sparse nonlinear solve control than SciPy/SUNDIALS can provide.

### Expected Features

The table stakes are not flashy user features; they are the minimum capabilities required for a credible kernel decision in a complex flowsheet simulator. If v1.0 cannot validate model structure, initialize consistently, converge recycle-heavy regions, enforce feasibility, explain failures, and stay within a bounded solve budget, the milestone will not produce a trustworthy kernel direction.

**Must have (table stakes):**
- **Flowsheet-level consistency at each accepted step** — eliminate stale unit/network lag as the core stability objective.
- **Recycle / loop convergence controls with damping and acceleration** — necessary for recycles, controllers, and pressure-coupled loops.
- **Determinacy + structural validation before solve** — reject under/over-specified models before runtime divergence.
- **Robust initialization / warm-start pipeline** — required for cold start, checkpoint restore, and post-edit recovery.
- **Physical bounds and feasibility guards** — prevent non-physical inventory, pressure, and state combinations.
- **Solver diagnostics and convergence telemetry** — expose residuals, iteration counts, failure modes, and degraded operation.
- **Bounded realtime solve policy** — preserve gameplay/service responsiveness under hard cases.

**Should have (competitive):**
- **Hybrid kernel mode with selective coupled escalation** — best brownfield fit and likely the milestone’s differentiator.
- **Automated robustness sweeps / kernel comparison harness** — turns the milestone into evidence-backed decision-making.
- **Explainable convergence traces** — useful for planning, debugging, and comparing kernel modes.
- **Edit-aware incremental recompilation** — valuable once the chosen kernel can tolerate runtime mutation.

**Defer (v2+):**
- **Whole-simulator dynamic DAE kernel across all units** — too broad for the current milestone unless benchmarks force escalation.
- **Expanded chemistry or new unit-model scope** — confounds kernel evaluation and should remain frozen during migration.

### Architecture Approach

The architecture recommendation is clear: keep the current outer deterministic phase loop and runtime/session facades, but replace the hard-coded split-step coupling assumption with a **strategy-routed coupled kernel coordinator**. The recommended next step is not “stay split-step” and not “rewrite everything equation-oriented”; it is to make unit prediction and network closure iterate against the same candidate snapshot, starting on strongly coupled partitions.

**Major components:**
1. **`CoupledKernelCoordinator`** — selects split, hybrid, or later whole-coupled mode; owns acceptance/rejection and inner convergence.
2. **`KernelStateSnapshot` / `KernelStateVector`** — captures reversible solver-grade state across units, hydraulics, ports, and transport.
3. **`UnitKernelAdapter`** — exposes predict/correct/residual hooks without rewriting every unit model immediately.
4. **`KernelResidualAssembler`** — builds coupled residuals spanning unit balances, hydraulics, transport, and boundary closure.
5. **`KernelSolverPolicy` / routing layer** — preserves legacy fallback while enabling selective hybrid escalation.
6. **Extended compile metadata in topology/hydraulics** — provides stable variable ordering, partitioning, and warm-start structure.

### Critical Pitfalls

1. **Preserving stale split-step decisions inside the new kernel** — avoid by defining one canonical accepted coupled snapshot and iterating unit and network state together.
2. **Treating algebraic closure as explicit ODE state** — avoid by explicitly partitioning differential vs. algebraic variables and designing around residual/Jacobian evaluation.
3. **Using clamps as fake stability** — avoid by enforcing invariants before step acceptance and logging any emergency recovery behavior.
4. **Tightening the solver without tightening initialization** — avoid by making consistent-state construction a first-class feature for startup, restore, and live edits.
5. **Ignoring runtime mutation and barrier semantics** — avoid by versioning compiled topology, solver structure, and warm starts together, with edits applied only at hard boundaries.
6. **Waiting too long to exploit sparsity and acceptance telemetry** — avoid by instrumenting Jacobian/iteration cost and designing for sparse solves from the first prototype.
7. **Publishing plant state after hidden solver failure** — avoid by making solver acceptance explicit all the way to observability and session APIs.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Solver Contract and Failure Semantics
**Rationale:** This must come first because the current milestone is primarily a decision problem: the team needs trustworthy evidence about stale coupling, algebraic ownership, invariants, and failure modes before choosing how far to escalate the kernel.
**Delivers:** Coupled-state semantics, structural/determinacy preflight, differential-vs-algebraic variable partitioning, invariant/acceptance checks, and baseline solver telemetry.
**Addresses:** Flowsheet-level consistency, structural validation, physical bounds, diagnostics, and bounded solve policy.
**Avoids:** Preserving stale split-step behavior, clamp-driven pseudo-stability, and hidden solver failure.

### Phase 2: Hybrid Kernel Substrate in the Existing Runtime
**Rationale:** Once the contract is defined, the next dependency is infrastructure: the simulator needs pluggable kernel insertion points, reversible snapshots, compile-time ordering/partition metadata, and sparse numerical paths before any serious hybrid correction can be trusted.
**Delivers:** `CoupledKernelCoordinator`, `KernelStateSnapshot` / `KernelStateVector`, adapter interfaces for units, extended compile metadata, sparse hydraulic/coupled solve plumbing, and warm-start support.
**Uses:** Python 3.13, SciPy sparse linear algebra, `least_squares`, and initial `BDF`/`Radau` experiments where appropriate, while defining the adapter seam needed for later `sundials4py` comparison.
**Implements:** The architecture’s runtime-layer insertion points without changing `PlantBackendSession`.

### Phase 3: Hybrid-Coupled Pilot on Strongly Coupled Regions
**Rationale:** This is the recommended default direction and the actual decision gate between “improved brownfield evolution” and “forced whole-flowsheet escalation.” Start where the current kernel is weakest: recycle-rich, pressure-coupled, controller-interacting subgraphs.
**Delivers:** Hybrid predictor/corrector execution, recycle damping/acceleration controls, bounded realtime acceptance policy, parity/shadow comparisons against split-step, and representative benchmark scenarios.
**Addresses:** Flowsheet-level consistency, recycle convergence, diagnostics, and realtime viability.
**Avoids:** Whole-flowsheet rewrite risk before the simulator proves it needs one.

### Phase 4: Runtime Hardening, Live-Edit Safety, and Decision Gate
**Rationale:** A more stable kernel is not useful if it breaks restart, reconfiguration, or hot runtime mutation. This phase also determines whether hybrid is enough or whether a whole-flowsheet/DAE path is justified.
**Delivers:** Consistent initialization/restart pipeline, checkpoint/load validation, barrier-safe mutation semantics, edit-aware recompilation rules, and an explicit go/no-go decision on whole-flowsheet escalation.
**Addresses:** Warm starts, bounded runtime mutation, gameplay-safe integration, and migration-readiness.
**Avoids:** Restart failures, graph-revision races, and nondeterministic live-edit behavior.

### Phase 5: Optional Whole-Flowsheet / Non-SciPy Escalation Spike
**Rationale:** Only do this if Phases 3-4 show that hybrid-coupled correction still fails key benchmark flowsheets or cannot meet stability/performance targets. This is an escalation path, not the default roadmap.
**Delivers:** Adapter-isolated whole-flowsheet residual solve or DAE feasibility prototype, benchmarked against the same scenarios and diagnostics, plus a post-SciPy stack comparison when solver-core limits remain dominant.
**Uses:** `sundials4py` first for CVODE/IDA/KINSOL-class capability, with PETSc/petsc4py reserved for a heavier sparse nonlinear systems spike if SUNDIALS is still insufficient.
**Implements:** The architecture’s future extension path without committing the product to a full rewrite prematurely.

### Phase Ordering Rationale

- Phase 1 comes first because every later decision depends on explicit state ownership, acceptance semantics, and trustworthy diagnostics.
- Phase 2 follows because hybrid coupling is impossible to evaluate honestly without reversible snapshots, variable ordering, partition metadata, and sparse solver plumbing.
- Phase 3 is the recommended proving ground because it tests the preferred hybrid direction on the exact kinds of flowsheets that currently fail.
- Phase 4 is required before rollout because this backend is live-editable and transactional, not an offline simulator.
- Phase 5 is intentionally optional to avoid turning v1.0 into a speculative full-kernel rewrite before the evidence exists.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 4:** live-edit-safe reinitialization, checkpoint consistency, and mutation semantics are tightly coupled to repo-specific runtime behavior and deserve focused planning.
- **Phase 5:** whole-flowsheet/non-SciPy escalation should trigger deeper solver, initialization, and deployment-risk research before commitment because the cost and compatibility risk are high.

Phases with standard patterns (skip research-phase):
- **Phase 1:** structural validation, acceptance diagnostics, invariants, and solver telemetry are well supported by the existing research and official references.
- **Phase 2:** pluggable runtime insertion, sparse Jacobian retention, and warm-start-oriented compile metadata are sufficiently documented by the repo and stack research.
- **Phase 3:** hybrid partitioned correction is well enough framed to move into requirements/planning without another general research pass, though benchmark details still need definition.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Strongly grounded in SciPy, Numba, SUNDIALS docs, plus clear repo integration points. |
| Features | MEDIUM | Well supported by IDAES/TESPy/DWSIM/CHEMCAD patterns, but milestone-specific prioritization still needs validation against actual gameplay workloads. |
| Architecture | HIGH | Directly grounded in current repo boundaries and gives a concrete brownfield migration path. |
| Pitfalls | MEDIUM-HIGH | Strong repo evidence and solid solver literature support, but some performance/runtime failure modes still need empirical confirmation on representative flowsheets. |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address

- **Representative benchmark set is still implicit**: define the exact canonical flowsheets and acceptance budgets early in requirements so SciPy, SUNDIALS, and any later alternatives are compared fairly.
- **Hybrid vs whole-flowsheet threshold is not yet quantified**: planning should define the benchmark evidence that would justify escalation beyond hybrid.
- **SciPy vs non-SciPy escalation threshold is not yet quantified**: planning should define the benchmark evidence that justifies moving from sparse/warm-start SciPy to `sundials4py`, and from SUNDIALS to PETSc if needed.
- **Differential/algebraic partitioning for current units is not yet enumerated**: this should become an explicit requirements artifact, not an implementation detail.
- **Runtime mutation classes need formal policy**: distinguish parameter-only edits, structure-changing edits, and restart-required edits during roadmap planning.
- **Solver-status exposure for external consumers is unresolved**: define what gameplay/API surfaces must know about degraded, retried, or failed steps.

## Sources

### Primary (HIGH confidence)
- `.planning/research/STACK.md` — official SciPy/Numba/SUNDIALS-backed stack recommendations for stiff stepping, sparse Jacobians, bounded correction, and migration constraints.
- `.planning/research/ARCHITECTURE.md` — repo-grounded architecture recommendation for hybrid kernel insertion behind existing runtime/session facades.
- SciPy official docs — `solve_ivp`, `BDF`, `Radau`, `LSODA`, `least_squares`, `Bounds`, sparse linear algebra, and `root` behavior.
- Repo architecture evidence — `connected_plant_orchestrator.py`, `runtime.py`, `connection_layer.py`, `network.py`, `hydraulic_compile.py`, `backend_session.py`, `process_model.py`.
- IDAES official docs — initialization, diagnostics, block-triangularization, and scaling workflows relevant to stable nonlinear flowsheets.
- SUNDIALS IDA docs — consistent initialization, DAE partitioning, rootfinding, and stiff large-system solver concerns.

### Secondary (MEDIUM confidence)
- `.planning/research/FEATURES.md` — synthesized feature expectations from IDAES, TESPy, DWSIM, and CHEMCAD ecosystem patterns.
- `.planning/research/PITFALLS.md` — migration pitfalls grounded in repo behavior plus solver guidance.
- TESPy docs — starting values and debugging practices for nonlinear flowsheets.
- DWSIM and CHEMCAD references — recycle controls, convergence history, and practical loop-convergence guidance.
- Mixed-mode and pressure-flow solver papers cited in PITFALLS.md — useful conceptual support, but older than primary vendor/library sources.

### Tertiary (LOW confidence)
- None identified as roadmap-critical; the main uncertainty is empirical, not source-quality driven.

---
*Research completed: 2026-03-29*
*Ready for roadmap: yes*

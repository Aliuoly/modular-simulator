# Pitfalls Research

**Domain:** Backend simulation kernel migration for complex flowsheets in a real-time process-simulation game backend
**Researched:** 2026-03-29
**Confidence:** MEDIUM-HIGH

## Critical Pitfalls

### Pitfall 1: Preserving stale split-step decisions inside a "new" kernel

**What goes wrong:**
Hydraulics, transport, and unit states are still advanced from different snapshots, so the migration changes implementation details without removing the actual lag that causes stale flow/pressure decisions. Rapidly changing units still feed the network one macro-step late, especially around tanks, valves, recycles, and controller actions.

**Why it happens:**
Brownfield teams often wrap the old sequence instead of changing the state ownership model. In this repo the current runtime explicitly executes `hydraulics_solve -> transport_update -> boundary_state_propagation` as a fixed macro sequence, with only a residual-gated Picard retry layered on top (`src/modular_simulation/connection/runtime/connection_layer.py`). That makes it easy to improve around the edges while keeping the stale-coupling architecture intact.

**How to avoid:**
- Treat stale-coupling removal as a first-class migration goal, not an optimization.
- Define a canonical coupled state snapshot for each step: inventories, pressures, through-flows, and boundary conditions must refer to the same accepted state.
- Add mixed-mode stepping deliberately: start with a bounded coupled inner iteration for strongly interacting subnetworks, not whole-plant full coupling on day one.
- Promote convergence criteria from "hydraulic residual only" to coupled residuals covering flow, pressure, inventory, and key thermodynamic boundary states.

**Warning signs:**
- Outlet flow reverses or jumps after the unit state has already changed.
- Recycles oscillate between two believable-but-different states.
- Picard retries increase, but physical artifacts remain.
- Stability improves only when macro-step size is made unrealistically small.

**Phase to address:**
Phase 1 - Failure characterization and coupled-state semantics

---

### Pitfall 2: Treating algebraic constraints as just more explicit ODE state

**What goes wrong:**
Pressure balance, flow closure, valve relations, and unit/network compatibility constraints are advanced explicitly instead of solved as algebraic constraints. The result is drift, pressure mismatch, artificial compressibility, and non-physical transient inventories.

**Why it happens:**
An existing split-step simulator already has a working explicit unit-step path, so the temptation is to keep pushing more coupling through `solve_ivp`-style explicit stepping. But SciPy's own guidance is that stiff problems should use implicit methods such as Radau/BDF/LSODA, and SUNDIALS IDA explicitly requires consistent DAE initial conditions and differential/algebraic variable separation for index-one systems.

**How to avoid:**
- Decide early which variables are differential vs algebraic.
- For a tighter kernel, model pressure-flow closure and similar network constraints as algebraic equations, not lagged boundary updates.
- If staying in SciPy first, isolate strongly coupled algebraic solves outside explicit unit ODEs; if moving to DAE form, require consistent initial conditions and explicit variable typing from the start.
- Design solver interfaces around residual/Jacobian evaluation, not only "step(dt)" hooks.

**Warning signs:**
- The same state variable is both integrated and later "corrected" by a network pass.
- Pressure equalities or flow balances need repeated clamping after each step.
- Convergence depends heavily on step ordering.
- Initialization becomes fragile after topology edits or restarts.

**Phase to address:**
Phase 1 - State partitioning and solver contract design

---

### Pitfall 3: Relying on clamps instead of invariant-preserving numerics

**What goes wrong:**
Negative holdup, composition drift, pressure spikes, and empty-vessel singularities are hidden by post-step clipping. The simulation looks stable while silently violating conservation or creating solver-dependent behavior.

**Why it happens:**
Clamps are the fastest brownfield patch. This repo already contains some local guards, e.g. `HoldingTank` caps outlet draw against available holdup and clips composition (`src/modular_simulation/unit_processes/storage/holding_tank.py`). Those guards are good locally, but they can hide the fact that the kernel as a whole still lacks global invariant handling.

**How to avoid:**
- Define plant-wide invariants: non-negative inventories, species sum closure, pressure/flow consistency, and conservation tolerances.
- Check invariants before accepting a step, not only after updating visible state.
- Prefer event/root handling or inequality-constrained stepping for dry-out, saturation, valve limit, and flow-reversal boundaries.
- Keep any emergency clipping diagnostic-only unless a compensating conservation correction is also applied and logged.

**Warning signs:**
- Frequent `max(0, x)` patches appear in migration code.
- Mass balance error is "small" but accumulates over long runs.
- Emptying/filling edges are the main source of test flakiness.
- Different tolerances produce different qualitative outcomes, not just slightly different numbers.

**Phase to address:**
Phase 1 - Invariants and acceptance tests

---

### Pitfall 4: Upgrading the solver without upgrading initialization

**What goes wrong:**
The new kernel fails mostly at startup, hot-reload, checkpoint restore, or topology edits because the initial state is inconsistent for the tighter solver. A kernel that is stable in steady runs becomes unusable in the actual game runtime.

**Why it happens:**
Tighter coupling makes inconsistency visible. SUNDIALS IDA is explicit that DAEs require consistent initial conditions and often need `IDACalcIC`; algebraic/differential variable identity must be known. Brownfield systems often assume the current runtime snapshot is "good enough" because the old split solver tolerated mismatch.

**How to avoid:**
- Make initialization a product feature of the kernel, not setup glue.
- Add a consistent-state builder for: cold start, checkpoint load, graph edit barrier application, and controller setpoint changes.
- Store enough state to reconstruct a solver-consistent snapshot, not just user-facing observables.
- Fail fast on inconsistent restart data with diagnostics that identify the violating equations/subsystems.

**Warning signs:**
- Most convergence failures occur on the first few steps after a restart or edit.
- "Warm start" vectors help sometimes but make behavior nondeterministic.
- Topology edits require hidden reset logic.
- Recovery depends on rerunning one or two dummy steps.

**Phase to address:**
Phase 2 - Initialization, restart, and hot-reconfiguration hardening

---

### Pitfall 5: Building a coupled kernel that cannot tolerate runtime mutation

**What goes wrong:**
The numerics improve, but live game features break: topology edits, controller updates, and actuator commands race with solver state, producing graph-revision mismatch, invalid Jacobians, or accepted steps against stale topology.

**Why it happens:**
Simulation-kernel work focuses on equations, while the backend is also a transactional runtime. This repo already has a barrier-based reconfiguration processor and graph revision checks (`src/modular_simulation/connection/runtime/reconfiguration_barrier_processor.py`, `src/modular_simulation/connection/runtime/runtime.py`). A tighter kernel increases the cost of getting this interface wrong.

**How to avoid:**
- Preserve the runtime barrier as a hard solver boundary.
- Version compiled topology, solver structure, and warm-start vectors together.
- Split edits into: no-structure parameter changes, structure-changing recompiles, and restart-required changes.
- Define exactly when pending commands are sampled relative to solver step acceptance.

**Warning signs:**
- Same edit request behaves differently depending on step timing.
- Recompiled networks reuse stale warm-start/Jacobian structure.
- Runtime bug reports mention "after I changed X while running".
- Idempotency/revision infrastructure passes, but physical state becomes inconsistent.

**Phase to address:**
Phase 2 - Runtime integration contract for the new kernel

---

### Pitfall 6: Ignoring stiffness and Jacobian structure until performance collapses

**What goes wrong:**
The new kernel is numerically better but too slow for real-time gameplay. CPU cost explodes with recycle count, network size, or fast control action because the solver uses dense finite-difference Jacobians, too many rejected steps, or whole-plant solves where sparse/block structure exists.

**Why it happens:**
Teams first prove correctness with generic solvers, then discover the runtime budget is gone. SciPy docs explicitly recommend implicit methods for stiff problems and recommend providing `jac`/`jac_sparsity`; SUNDIALS docs emphasize sparse/direct or Krylov + preconditioning for large stiff systems. The current hydraulic stack already exposes sparse Jacobian assembly (`src/modular_simulation/connection/hydraulics/hydraulic_solver.py`), which is a migration asset that could be wasted.

**How to avoid:**
- Treat sparsity, block structure, and warm-start reuse as architecture, not later optimization.
- Benchmark representative flowsheets early: calm, recycle-heavy, controller-heavy, and topology-edit scenarios.
- Keep the option to solve only strongly coupled subnetworks implicitly while leaving weakly coupled units on cheaper paths.
- Instrument `nfev`, `njev`, nonlinear iterations, rejected steps, and step wall time from the first prototype.

**Warning signs:**
- Solver cost scales superlinearly with unit count.
- Most time is spent in Jacobian estimation or repeated factorization.
- Stable runs require tolerances so loose they undermine physical credibility.
- Performance only looks acceptable on acyclic demo flowsheets.

**Phase to address:**
Phase 3 - Performance architecture and sparse solve strategy

---

### Pitfall 7: Keeping a unit API that hides solver failure

**What goes wrong:**
The kernel reports success to the game loop even when sub-solvers failed, stepped partially, or violated acceptance criteria. Downstream state looks valid but is numerically untrusted.

**Why it happens:**
Legacy APIs often assume stepping always succeeds. In this repo, the generic `ProcessModel.step` calls `solve_ivp` and updates state from `result.y[:, -1]` without checking `result.success` or propagating solver diagnostics (`src/modular_simulation/measurables/process_model.py`). That is manageable in a simple explicit world and dangerous in a tighter kernel.

**How to avoid:**
- Make step acceptance explicit in every solver API.
- Return diagnostics: accepted/rejected, residuals, iterations, event hits, constraint hits, and fallback usage.
- Distinguish recoverable instability (retry with smaller step / fallback mode) from fatal kernel inconsistency.
- Refuse to publish plant state after an unaccepted step.

**Warning signs:**
- Runtime observability has physical values but no solver-status metadata.
- "Stability" is inferred only from absence of exceptions.
- Tests assert end-state values but not solver acceptance path.
- Postmortems cannot tell whether a bad state came from physics, numerics, or integration glue.

**Phase to address:**
Phase 2 - Solver API and observability contract

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Add another outer retry loop around the old macro sequence | Cheap apparent stability improvement | Hides stale coupling and creates nondeterministic latency | Only as a temporary diagnostic experiment |
| Clamp negative inventory/state after every step | Prevents crashes and ugly outputs | Masks conservation errors and changes physics | Only for output formatting, never as core kernel behavior |
| Use whole-plant dense finite-difference Jacobians first | Fastest prototype | Performance collapses before roadmap confidence is earned | Only for tiny research prototypes with explicit sunset date |
| Reuse legacy `step(dt)` unit contract unchanged | Minimizes refactor scope | Prevents DAE/mixed-mode solver design and hides failure states | Never for the final kernel boundary |
| Rebuild solver structure on every runtime mutation | Simplifies correctness | Destroys warm-start/performance and makes live edits expensive | Acceptable only for infrequent structure-changing edits |

## Integration Gotchas

Common mistakes when connecting the new kernel to surrounding backend systems.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Runtime reconfiguration | Applying edits mid-step or against stale compiled topology | Keep edits behind a barrier; version topology, solver structure, and warm-start data together |
| Checkpoint/restore | Saving user-visible state only | Save solver-relevant consistent state or rebuild it through a validated initialization pass |
| Controllers/actuators | Sampling commands at ambiguous times within a step | Define one sampling point per accepted step and document it |
| Gameplay/session API | Returning plant state without solver acceptance metadata | Expose accepted/rejected step status and degraded-mode diagnostics |
| Hydraulics ↔ unit models | Letting each side own the same pressure/flow variable differently | Assign single ownership per state and use explicit residual coupling |

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Dense Jacobian estimation for sparse coupled systems | CPU dominated by Jacobian work, especially during transients | Provide Jacobian/Jacobian sparsity or exploit existing sparse hydraulic structure | Usually at medium recycle-rich flowsheets, well before "large plant" scale |
| Whole-plant implicit solve for every edit and every step | Acceptable demos, poor live-play responsiveness | Use subnetwork coupling and compile-time structure reuse | Breaks once players run controller-heavy or branching networks |
| Step-size collapse near dry-out/flow reversal events | Huge internal step counts, apparent freezes | Add event/root handling and invariant-aware switching logic | Breaks first on tank/valve edge cases |
| Reinitializing from scratch after every command | Stable but sluggish game loop | Separate parameter updates from topology-changing recompiles | Breaks under frequent control interaction |

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Letting user-driven runtime edits trigger unbounded expensive solves | Denial-of-service against the simulation backend | Cap per-step work, per-request compile cost, and unstable retry depth |
| Returning raw solver internals/errors directly through the API | Exposes backend structure and creates unstable client behavior | Normalize diagnostics for clients while preserving detailed server-side traces |
| Accepting arbitrary topology mutations without revision checks | Corrupts runtime state and breaks determinism | Keep expected revision and idempotency enforcement at the kernel boundary |

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| "Stable" kernel silently slows to a crawl on hard flowsheets | Game feels frozen or random | Surface degraded-mode status and step-budget warnings |
| Physical clipping without explanation | Users see impossible recoveries or missing material | Expose invariant violations and applied recovery policy in debug/teacher views |
| Topology edit causes hidden full restart | User loses trust in live-edit behavior | Distinguish live-edit-safe changes from restart-required changes in API/UI semantics |

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Coupled kernel prototype:** Verify it uses a single accepted state snapshot, not the old split state ownership with extra retries.
- [ ] **Implicit/DAE migration:** Verify differential vs algebraic variables are explicitly identified and initialization is consistent after restart/edit.
- [ ] **Inventory protection:** Verify conservation/invariant checks happen before state acceptance, not just via post-step clipping.
- [ ] **Performance validation:** Verify representative recycle-heavy and controller-heavy flowsheets, not only simple acyclic demos.
- [ ] **Runtime integration:** Verify topology edits, checkpoint restore, and actuator updates under load, not only cold-start runs.
- [ ] **Observability:** Verify every accepted state has solver diagnostics attached and failed steps cannot be published as success.

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Stale split-step decisions retained | HIGH | Introduce canonical coupled-state ownership, reduce scope to strongly coupled subnetworks first, and re-baseline regression cases |
| Inconsistent DAE/algebraic initialization | HIGH | Build explicit consistent-state initialization pipeline; invalidate old checkpoints if necessary |
| Clamp-driven non-physical stability | MEDIUM-HIGH | Replace silent clipping with acceptance checks, event handling, and invariant diagnostics; re-tune tests around conservation |
| Runtime mutation corrupts solver state | MEDIUM | Reinstate hard barrier semantics, separate safe parameter edits from structure changes, and version warm starts |
| Solver too slow for gameplay | MEDIUM-HIGH | Add sparse/preconditioned or block-structured solves, restrict implicit coupling scope, and add real workload profiling |
| Hidden solver failure in API | MEDIUM | Change step contract to explicit acceptance/failure and update session/gameplay layers to honor it |

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Preserving stale split-step decisions | Phase 1 | Regression scenarios show rapid transients converge without macro-step lag artifacts |
| Treating algebraic constraints as explicit state | Phase 1 | Variable partition and residual ownership are documented and exercised in tests |
| Relying on clamps instead of invariants | Phase 1 | Acceptance tests track conservation, non-negativity, and edge-event behavior |
| Unstable initialization/restart | Phase 2 | Cold start, checkpoint restore, and topology-edit restart all produce solver-consistent states |
| Runtime mutation races | Phase 2 | Barrier tests prove edits cannot invalidate an active accepted step |
| Performance collapse under tighter coupling | Phase 3 | Benchmarks on representative flowsheets meet game-loop budget with diagnostics recorded |
| Hidden solver failure | Phase 2 | Backend/public API distinguishes accepted, retried, degraded, and failed steps |

## Sources

- `.planning/PROJECT.md` - milestone context and constraints for this migration (HIGH)
- `src/modular_simulation/connection/runtime/connection_layer.py` - current fixed macro-coupling sequence and Picard gate implementation (HIGH)
- `src/modular_simulation/connection/runtime/runtime.py` - runtime barrier, step orchestration, and mutation timing (HIGH)
- `src/modular_simulation/connection/runtime/reconfiguration_barrier_processor.py` - reconfiguration transactional semantics (HIGH)
- `src/modular_simulation/measurables/process_model.py` - current unit stepping contract and missing `solve_ivp` success propagation (HIGH)
- `src/modular_simulation/unit_processes/storage/holding_tank.py` - localized inventory guards and explicit RK45 unit stepping (HIGH)
- SciPy `solve_ivp` / `LSODA` docs: stiff problems should use implicit methods, Jacobians/Jacobian sparsity matter, events may be missed within a step, and tolerances/step controls strongly affect robustness (HIGH) — https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.solve_ivp.html, https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.LSODA.html
- SUNDIALS IDA mathematics and usage docs: consistent initial conditions, differential/algebraic partitioning, inequality constraints, rootfinding, and preconditioned large stiff solves are core concerns (HIGH) — https://sundials.readthedocs.io/en/latest/ida/Mathematics_link.html, https://sundials.readthedocs.io/en/latest/ida/Usage/index.html
- Gani & Jørgensen, *Mixed mode simulation - Adding equation oriented convergence to a sequential modular simulation tool* (conceptual support for mixed-mode migration, older source) (MEDIUM)
- Mohajer, Young, Svrcek, *Comparing Pressure Flow Solvers for Dynamic Process Simulation* (pressure/flow solver tradeoff context, older source) (MEDIUM)

---
*Pitfalls research for: backend kernel stability migration*
*Researched: 2026-03-29*

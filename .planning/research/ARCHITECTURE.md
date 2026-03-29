# Architecture Research

**Domain:** backend simulation kernel stability for complex process flowsheets
**Researched:** 2026-03-29
**Confidence:** HIGH

## Standard Architecture

### System Overview

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                   Existing API / gameplay / session facades                 │
│        PlantBackendSession, gameplay services, HTTP game API remain         │
└───────────────────────────────┬──────────────────────────────────────────────┘
                                │ calls step()/commit()/snapshot
┌────────────────────────────────▼──────────────────────────────────────────────┐
│                    Existing flowsheet + topology substrate                   │
│   Flowsheet assembly → ConnectionNetwork compile/reconfigure → graph rev    │
└───────────────────────────────┬──────────────────────────────────────────────┘
                                │ compiled topology + runtime bindings
┌────────────────────────────────▼──────────────────────────────────────────────┐
│                 Connected runtime orchestration layer (modified)             │
│  Sensors → calculations → controllers → process step → kernel policy        │
└───────────────┬───────────────────────────────┬──────────────────────────────┘
                │                               │
                │ current path                  │ recommended new path
                │                               │
┌───────────────▼──────────────┐   ┌────────────▼─────────────────────────────┐
│ Split-step MacroCoupler      │   │ Coupled Kernel Coordinator (new)         │
│ hydraulics → transport →     │   │ selects split / hybrid / coupled mode    │
│ boundary propagation         │   │ and manages inner convergence loop        │
└───────────────┬──────────────┘   └────────────┬─────────────────────────────┘
                │                               │
                │                               │ assembles residual/state
                │                               ▼
                │                  ┌──────────────────────────────────────────┐
                │                  │ Kernel Assembly Layer (new)              │
                │                  │ unit adapters + network equations +      │
                │                  │ state snapshots + convergence metrics     │
                │                  └────────────┬─────────────────────────────┘
                │                               │ solve/iterate
                │                               ▼
                │                  ┌──────────────────────────────────────────┐
                │                  │ Kernel Solvers (new)                     │
                │                  │ 1) hybrid coupled corrector (first)      │
                │                  │ 2) whole-flowsheet root solve (later)    │
                │                  │ 3) implicit dynamic step (optional)      │
                │                  └────────────┬─────────────────────────────┘
                │                               │ accepted state
                └───────────────┬───────────────┴─────────────────────────────┘
                                ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│            Existing runtime state stores remain, but become kernel-owned    │
│      transport state, junction state, port snapshots, process runtime state │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| `ConnectedPlantOrchestrator` (modified) | Preserve current phase order and barrier semantics, but hand off the final simulation advance to a kernel policy instead of hard-coding split-step behavior | Keep as top-level phase runner; replace direct dependence on only `ConnectionRuntimeOrchestrator.step()` with pluggable kernel execution |
| `ConnectionRuntimeOrchestrator` (modified) | Remain owner of barrier apply, runtime snapshots, observability, transport/junction state stores, and default kernel fallback | Split into state ownership + legacy split-step execution helpers |
| `CoupledKernelCoordinator` (new) | Choose kernel mode per flowsheet/region, run inner convergence loop, accept/reject candidate states, publish diagnostics | New runtime-layer service called from the existing orchestrator |
| `KernelStateSnapshot` / `KernelStateVector` (new) | Serialize unit states, hydraulic unknowns, port conditions, transport lags, and actuator commands into reversible solver state | Dataclasses + adapters around existing runtime state exporters |
| `UnitKernelAdapter` (new) | Expose each unit’s contribution as predict/correct/residual hooks without rewriting all unit models at once | Per-unit adapter shim around existing subsystem runtimes/process models |
| `KernelResidualAssembler` (new) | Build coupled residuals from unit balances, hydraulic equations, connection transport/mixing, and boundary closures | Reuse compiled hydraulic graph and port-condition logic; add unit residual blocks |
| `KernelSolverPolicy` (new) | Encapsulate split-step, hybrid coupled corrector, and whole-flowsheet solve strategies behind one interface | Strategy objects; start with legacy + hybrid |
| `ConnectionNetwork` compile lifecycle (modified) | Continue compiling topology/hydraulic graph, but also expose kernel partition metadata and stable state-vector ordering | Extend compile output instead of replacing topology ownership |

## Recommended Project Structure

```text
src/
└── modular_simulation/
    ├── connection/
    │   ├── runtime/
    │   │   ├── connected_plant_orchestrator.py   # existing outer phase runner
    │   │   ├── runtime.py                         # existing runtime owner/barrier state
    │   │   ├── connection_layer.py                # legacy split-step macro coupler
    │   │   ├── kernel_coordinator.py              # NEW kernel entrypoint/policy router
    │   │   ├── kernel_modes.py                    # NEW split/hybrid/coupled mode strategies
    │   │   ├── kernel_state.py                    # NEW reversible state snapshot/vector types
    │   │   ├── kernel_diagnostics.py              # NEW residual/convergence reporting
    │   │   └── kernel_acceptance.py               # NEW commit/rollback of candidate state
    │   ├── kernel/
    │   │   ├── unit_adapter.py                    # NEW unit kernel adapter protocols
    │   │   ├── residual_assembler.py              # NEW whole-kernel residual assembly
    │   │   ├── partitioning.py                    # NEW SCC / coupled-region partitioning
    │   │   ├── solver_root.py                     # NEW scipy.optimize.root integration
    │   │   └── solver_implicit.py                 # NEW optional solve_ivp BDF/Radau path
    │   ├── hydraulics/
    │   │   └── hydraulic_compile.py               # modified to expose ordering/warm-start metadata
    │   └── topology/
    │       └── network.py                         # modified compile output and step dispatch
    └── cli/
        └── backend_session.py                     # unchanged facade; optional diagnostics exposure
```

### Structure Rationale

- **`connection/runtime/`:** keep runtime ownership where it already lives; the new kernel should be an internal runtime evolution, not a new top-level subsystem.
- **`connection/kernel/`:** isolate solver-specific and residual-assembly code from orchestration code so legacy runtime/barrier logic stays understandable.
- **`hydraulics/` + `topology/`:** extend current compile products rather than duplicate them; topology and hydraulic compile are already the right owners of graph structure and variable ordering.

## Architectural Patterns

### Pattern 1: Outer deterministic phase loop, inner coupled solve

**What:** Keep the existing gameplay-safe outer phase ordering, but replace the last “connection runtime coupling” phase with an inner solve that iterates unit and connection states together until a coupled residual converges.
**When to use:** Default direction for complex flowsheets, recycle loops, stiff hydraulic-control interaction, and cases where stale boundary conditions cause non-physical inventories.
**Trade-offs:** Much less invasive than a full rewrite; more stable than pure split-step; still requires unit adapters and reversible state snapshots.

**Example:**
```python
phase_runner.run_preprocess_phases()
candidate = kernel_state.capture(network, subsystems)
result = kernel_policy.solve(candidate, dt=macro_step_time_s)
kernel_acceptance.commit(result.accepted_state)
```

### Pattern 2: Strategy-based kernel policy routing

**What:** One runtime interface with three policies: legacy split-step, hybrid coupled corrector, and later whole-flowsheet coupled solve.
**When to use:** Brownfield migration where some flowsheets remain cheap/simple and others need stronger coupling.
**Trade-offs:** Slightly more abstraction, but it avoids a risky flag day and allows A/B validation against the current runtime.

**Example:**
```python
policy = kernel_policy_router.select(compiled_network, runtime_context)
step_result = policy.advance(state_snapshot, dt)
```

### Pattern 3: Compile-time partitioning, run-time warm starts

**What:** Use the compiled graph to identify strongly coupled regions and stable variable ordering; reuse previous-step solutions as warm starts for nonlinear solves.
**When to use:** Always for hybrid mode; especially important for realtime performance.
**Trade-offs:** Extra compile metadata, but much lower solver cost and better convergence behavior.

**Example:**
```python
partition = compiled.kernel_partition
guess = warm_start_store.last_solution(partition.region_id)
sol = scipy.optimize.root(residual, guess, jac=jacobian, method="hybr")
```

## Data Flow

### Request Flow

```text
User/API commit or step
    ↓
PlantBackendSession
    ↓
ConnectionNetwork / ConnectedPlantOrchestrator
    ↓
Barrier apply + compile revision check
    ↓
Pre-kernel phases (sensor/calc/controller)
    ↓
CoupledKernelCoordinator
    ↓
state snapshot → residual assembly → solver iterations → accepted state
    ↓
observability + checkpoint export
```

### State Management

```text
CompiledConnectionNetwork + process runtime state + transport/junction state
    ↓ capture
KernelStateSnapshot
    ↓ flatten / order
KernelStateVector
    ↓ iterate with warm starts
Solver result
    ↓ accept / rollback
Runtime-owned stores + port snapshots + published observability
```

### Key Data Flows

1. **Current split-step path:** subsystem process models advance first; only afterward does `MacroCoupler` run hydraulics → transport → boundary propagation. This is exactly where stale coupling enters.
2. **Recommended hybrid path:** the process-step phase becomes a predictor only; the kernel then repeatedly updates unit state estimates and connection equations against the same candidate snapshot before accepting one macro-step.
3. **Later whole-flowsheet path:** the kernel assembles one flowsheet-wide state/residual system and solves it directly, but still plugs into the same outer orchestrator, barrier, and snapshot interfaces.

## Recommended Integration Direction

### Recommendation

Use a **hybrid coupled kernel** as the next architecture, not a pure split-step runtime and not an immediate full equation-oriented rewrite.

Why:

- The current code already has the right substrate owners: `ConnectionNetwork` owns compile/revision state, `ConnectedPlantOrchestrator` owns phase order, and `ConnectionRuntimeOrchestrator` owns barrier semantics and runtime state.
- The current Picard gate in `MacroCoupler` only repeats hydraulics/transport/boundary propagation after the unit process step has already happened, so it improves connection-layer closure but does **not** remove the core unit/network lag.
- A full whole-flowsheet coupled solve would be the best end-state for the hardest recycle-rich cases, but introducing it directly would force immediate re-expression of unit dynamics, state ordering, rollback semantics, and diagnostics across the entire simulator.

### Why not stay split-step?

- `ConnectedPlantOrchestrator` explicitly runs `subsystem_process_step` before `connection_runtime_coupling`.
- `ConnectionRuntimeOrchestrator.step()` then runs the macro coupler after that process step.
- Therefore, any unit outlet/holdup decision made during the process phase can be based on previous-step hydraulic/boundary information. For complex recycles, that is the architectural instability source.

### Why not jump straight to whole-flowsheet coupled solve?

- It is feasible with SciPy-style nonlinear and stiff ODE tooling (`scipy.optimize.root`, `scipy.integrate.solve_ivp` with `Radau`/`BDF`), but the repo does not yet have a unified flowsheet state vector, unit residual interface, or solver-grade Jacobian/sparsity layer.
- A direct jump would turn this milestone into a multi-subsystem rewrite rather than a controlled kernel evolution.

### What hybrid means here

- Keep the existing phase model and facades.
- Convert subsystem process stepping into a **predictor** that can produce a candidate next state for a macro-step.
- Add a coupled corrector that iterates unit predictions and connection equations together until residuals on flow, pressure, composition, temperature, and inventory closure are acceptable.
- Support escalation: if a partition is simple, use legacy split-step; if strongly coupled, use hybrid; if still unstable, allow the same interface to route to a whole-flowsheet solve later.

## New vs Modified Components

### New components

| Component | Why it is new | Primary integration points |
|-----------|---------------|----------------------------|
| `CoupledKernelCoordinator` | No current object owns kernel-mode selection or candidate-state iteration | Called from `ConnectedPlantOrchestrator` / `ConnectionRuntimeOrchestrator` |
| `KernelStateSnapshot` + `KernelStateVector` | Current snapshot/export APIs are persistence-focused, not solver-focused | Pulls from runtime stores, process models, compiled hydraulic graph |
| `UnitKernelAdapter` | Existing subsystem interface only supports `run_process_phase(duration)` | Wraps each subsystem/process model with predict/correct/residual hooks |
| `KernelResidualAssembler` | Current residuals stop at hydraulics; unit equations are not assembled with network equations | Consumes compiled network + unit adapters + thermo/transport state |
| `KernelDiagnostics` | Current bookkeeping is macro-coupling focused, not coupled-kernel focused | Feeds observability, tests, and migration comparisons |
| `KernelPolicyRouter` | Brownfield rollout needs per-flowsheet/per-region policy choice | Reads compile metadata and runtime config |

### Modified components

| Component | Required modification | Why |
|-----------|----------------------|-----|
| `connection/runtime/connected_plant_orchestrator.py` | Replace direct “process-step then runtime step” assumption with predictor + kernel coordinator handoff | This is the stable insertion point without changing API/gameplay layers |
| `connection/runtime/runtime.py` | Separate barrier/state ownership from the legacy macro-coupler execution path; expose capture/accept hooks and warm-start state | Runtime already owns snapshots, observability, and barrier semantics |
| `connection/runtime/connection_layer.py` | Keep as legacy mode, but stop treating Picard retries as the long-term stability answer | Needed for fallback and parity testing |
| `connection/topology/network.py` | Extend compile products with kernel partition metadata and state ordering; keep graph revision semantics | Compile is already the right place to define stable ordering |
| `connection/hydraulics/hydraulic_compile.py` | Export reusable unknown/residual ordering and warm-start helpers into the new kernel | Avoid duplicate hydraulic variable bookkeeping |
| unit subsystem runtime classes | Add opt-in adapter hooks instead of forcing all units to rewrite immediately | Enables incremental migration |

## Integration Points

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `ConnectedPlantOrchestrator` ↔ `CoupledKernelCoordinator` | direct API | Preserve current outer phase order; pass macro-step time, compiled network, subsystem handles |
| `CoupledKernelCoordinator` ↔ `ConnectionRuntimeOrchestrator` | direct API | Runtime remains owner of barrier apply, snapshots, observability, and accepted state publication |
| `KernelResidualAssembler` ↔ `CompiledConnectionNetwork` | direct API using compile metadata | Reuse hydraulic ordering, graph revision, topology partitioning |
| `KernelResidualAssembler` ↔ unit adapters | protocol-based API | Unit models contribute predicted states and residual terms without exposing all internals |
| `Kernel solver` ↔ SciPy | library call | `root` for algebraic closure first; `solve_ivp` with `Radau`/`BDF` only after hybrid path is stable |
| `PlantBackendSession` ↔ runtime | unchanged facade | Keep `step`, `compile`, `checkpoint`, `observability` stable for consumers |

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| SciPy `optimize.root` | nonlinear residual solve for coupled algebraic closure | Official docs support user Jacobian and multiple methods; use warm starts and explicit failure diagnostics |
| SciPy `integrate.solve_ivp` (`Radau`/`BDF`) | later implicit integration for stiff dynamic kernels | Official docs recommend implicit methods for stiff problems and supplying Jacobians where possible |
| IDAES / Pyomo references | design inspiration only | Useful patterns: initialization sequencing and block-triangular/strongly connected decomposition, not a replacement stack |

## Comparison: Split-step vs Whole-coupled vs Hybrid

| Criterion | Current split-step | Whole-flowsheet coupled solve | Recommended hybrid |
|-----------|--------------------|-------------------------------|--------------------|
| Brownfield fit | High | Low | High |
| Stability on recycle-heavy flowsheets | Low-Medium | High | High |
| Migration risk | Low | Very high | Medium |
| Runtime diagnosability | High today | Medium until tooling matures | High |
| Realtime performance path | Good for simple flowsheets | Uncertain initially | Good if partitioned and warm-started |
| Uses current compile/barrier/session layers | Yes | Only partially | Yes |
| Recommended now | No | Not first | Yes |

## Build / Migration Order

1. **Stabilize kernel insertion points first**
   - Modify `ConnectedPlantOrchestrator` and `ConnectionRuntimeOrchestrator` so kernel execution is a pluggable policy.
   - Do not change `PlantBackendSession` or API contracts yet.

2. **Add reversible solver-state capture/acceptance**
   - Introduce `KernelStateSnapshot` built from existing process runtime export, transport state, junction state, port snapshots, and hydraulic warm-start data.
   - This is the dependency that makes safe inner iteration possible.

3. **Extend compile output with partitioning and ordering**
   - Add strongly-coupled-region metadata, stable variable ordering, and warm-start handles to compile products.
   - Required before any performant coupled solve.

4. **Introduce hybrid coupled corrector for the worst coupled regions first**
   - Start with recycle-rich partitions, not the whole flowsheet.
   - Use current process step as predictor, then run coupled correction with rollback on failure.

5. **Add parity/shadow mode**
   - Run split-step and hybrid on the same checkpointed state in tests/offline diagnostics.
   - Compare residuals, inventory drift, and convergence cost before turning hybrid on by default.

6. **Promote hybrid to default, retain legacy fallback**
   - Keep split-step for trivial flowsheets and debugging.
   - Expose kernel diagnostics so gameplay/session consumers can still explain slow or failed steps.

7. **Only then consider whole-flowsheet or implicit dynamic solve**
   - Use the same coordinator/state/residual interfaces.
   - Escalate only after adapter coverage and Jacobian/sparsity knowledge are mature.

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| Small acyclic flowsheets | Legacy split-step can remain available for speed and simple debugging |
| Medium flowsheets with localized recycle loops | Hybrid partitioned corrector should be default |
| Large tightly coupled flowsheets | Whole-region or whole-flowsheet solve may be needed, but only after warm starts, sparsity, and partitioning are proven |

### Scaling Priorities

1. **First bottleneck:** nonlinear solve convergence. Fix with warm starts, partitioning, and better unit residual scaling before chasing micro-optimizations.
2. **Second bottleneck:** Jacobian cost. Fix with explicit Jacobians/sparsity metadata for hydraulic and unit blocks before considering more exotic solvers.

## Anti-Patterns

### Anti-Pattern 1: Treating Picard retries as full kernel coupling

**What people do:** Re-run hydraulics/transport/boundary propagation a few times and call the kernel “coupled.”
**Why it's wrong:** It still leaves unit internal state evolution outside the inner loop, so stale unit/network feedback remains.
**Do this instead:** Put unit prediction/correction and network closure inside the same candidate-state iteration.

### Anti-Pattern 2: Replacing the substrate with a brand new solver stack

**What people do:** Introduce a new flowsheet engine beside the existing runtime/session/barrier stack.
**Why it's wrong:** Duplicates topology ownership, breaks graph revision semantics, and creates two incompatible backends.
**Do this instead:** Evolve the kernel behind the existing `ConnectionNetwork` + runtime orchestration boundaries.

### Anti-Pattern 3: Whole-flowsheet solve before state-vector discipline exists

**What people do:** Jump straight to a global implicit solve without reversible snapshots, stable variable ordering, or unit adapters.
**Why it's wrong:** Failures become impossible to diagnose and rollback safely in a live game/backend environment.
**Do this instead:** Build snapshot/ordering/adapter infrastructure first, then expand solve scope.

## Sources

- Repo architecture evidence:
  - `src/modular_simulation/connection/runtime/connected_plant_orchestrator.py`
  - `src/modular_simulation/connection/runtime/runtime.py`
  - `src/modular_simulation/connection/runtime/connection_layer.py`
  - `src/modular_simulation/connection/topology/network.py`
  - `src/modular_simulation/connection/hydraulics/hydraulic_compile.py`
  - `src/modular_simulation/cli/backend_session.py`
- SciPy official docs: `scipy.optimize.root` — https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.root.html
- SciPy official docs: `scipy.integrate.solve_ivp` — https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.solve_ivp.html
- IDAES official docs: initialization methods — https://idaes-pse.readthedocs.io/en/stable/reference_guides/core/util/initialization.html
- IDAES official docs: block triangularization initializer — https://idaes-pse.readthedocs.io/en/stable/reference_guides/initialization/bt_initializer.html
- Pyomo official docs: DAE simulator — https://pyomo.readthedocs.io/en/6.8.2/api/pyomo.dae.simulator.Simulator.html

---
*Architecture research for: backend simulation kernel stability*
*Researched: 2026-03-29*

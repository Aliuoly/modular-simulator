# Feature Research

**Domain:** stable backend kernel for complex process flowsheets
**Researched:** 2026-03-29
**Confidence:** MEDIUM

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = kernel comparison or migration work is not credible.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Flowsheet-level consistency at each accepted step | Stable kernels are expected to solve pressure/flow/inventory interactions without stale upstream/downstream lag. Official guidance from CHEMCAD/IDAES/TESPy all centers on solving coupled dependencies, square models, and robust initialization rather than trusting loose sequential propagation. | HIGH | Must build on existing unit-process and connection runtime. Requires exposing a flowsheet-wide state/residual view over current unit micro-step + macro-step architecture, not replacing `PlantBackendSession` first. |
| Recycle / loop convergence controls with damping and acceleration | Complex flowsheets routinely contain recycles, pressure nodes, controllers, and heat integration loops. Commercial/open simulators expose explicit convergence methods, iteration limits, and acceleration settings because simple direct substitution is not enough. | MEDIUM | Dependency on current topology/hydraulics graph. Needed whether final direction is fully coupled or hybrid partitioned solve. Should preserve realtime budgets by allowing capped iterations and warm starts. |
| Determinacy + structural validation before solve | Stable equation-oriented workflows expect square-model checks, structural singularity detection, and explicit reporting for over/under-specified models before runtime divergence. | MEDIUM | Depends on existing flowsheet builder and runtime-editing APIs. Best added as a compile/preflight pass so current authoring and session layers can reject bad states before simulation ticks. |
| Robust initialization / warm-start pipeline | IDAES and TESPy both treat initialization as first-class because nonlinear flowsheets fail without good starting values. A stable game backend also needs resumable state after edits, not cold-start every solve. | HIGH | Must reuse current per-unit state and connected-plant runtime snapshots. Needs edit-aware reinitialization after topology/spec changes and warm-start from last accepted state. |
| Physical bounds and feasibility guards | Table-stakes kernels prevent obviously non-physical states such as negative inventory, impossible pressure/enthalpy combinations, or out-of-range property calls. | MEDIUM | Should wrap existing unit and property evaluations. Needs bounded state updates, rejected-step/fallback behavior, and compatibility with current hydraulics and transport modules. |
| Solver diagnostics and convergence telemetry | Modern stable kernels are expected to say *why* a solve failed: residuals, offending variables, bad scaling, structural issues, iteration counts. Debug-only black boxes are not acceptable for migration work. | MEDIUM | Depends on current logging/session surfaces. Should feed milestone analysis/comparison work first, then later support gameplay-safe health reporting. |
| Bounded realtime solve policy | For this milestone, correctness alone is insufficient; the kernel must degrade gracefully under a frame budget using iteration caps, fallback modes, or deferred refinement instead of hanging. | HIGH | Depends on existing realtime backend contract. Must integrate with game/session tick cadence and preserve response guarantees for `PlantBackendSession` consumers. |

### Differentiators (Competitive Advantage)

Features that set the milestone apart. Not required for initial stability work, but valuable.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Hybrid kernel mode: partitioned by default, coupled solve on unstable subgraphs | Best fit for this repo: keep cheap sequential behavior where topology is tame, escalate only recycle/pressure-coupled regions to a stronger solve. This protects realtime performance better than an all-at-once rewrite. | HIGH | Strong dependency on current hydraulics compilation and graph partitioning. Recommended differentiator because it fits the brownfield constraint better than a pure greenfield equation-oriented kernel. |
| Edit-aware incremental recompilation | Runtime editing is already a core capability. A kernel that can recompile only affected subgraphs after a valve/spec/topology change will make migration practical and keep sessions responsive. | HIGH | Depends directly on existing `PlantBackendSession` editing flows and connected-plant topology compiler. Valuable because it turns stability work into something usable in live gameplay. |
| Automated robustness sweeps / kernel comparison harness | A milestone differentiator: systematically replay representative flowsheets, perturb specs, and compare convergence rate, physical violations, and wall-clock cost across candidate kernel directions. | MEDIUM | Depends on current canonical examples and backend test fixtures. Especially valuable because this milestone is explicitly about analysis and migration choice, not just implementation. |
| Explainable convergence traces | Human-readable traces of residual reduction, active damping, rejected steps, and dominant failing constraints make roadmap decisions faster and reduce future rewrite risk. | MEDIUM | Builds on diagnostics telemetry. Good milestone differentiator because it helps compare current split runtime vs. candidate coupled methods with evidence. |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Immediate full-engine rewrite to a monolithic equation-oriented kernel | Sounds like the “clean” answer to stale coupling. | High migration risk, likely breaks current gameplay/session consumers, and may miss realtime budgets before basic diagnostics exist. | Build a comparison harness first, then prefer a hybrid migration path with coupled subgraph solving where evidence says it is needed. |
| Solver behavior hidden behind automatic magic retries | Attractive because it masks convergence pain from callers. | Makes failures non-diagnosable, wastes realtime budget, and blocks milestone analysis because you cannot compare kernel directions honestly. | Expose explicit retry/fallback policy with iteration counts, residuals, and accepted/rejected step reasons. |
| Unbounded global solve every tick | Feels “most correct.” | Violates the game-backend performance constraint and couples trivial edits to worst-case flowsheet cost. | Use bounded solve budgets, warm starts, and selective escalation to stronger solves only on affected/coupled regions. |
| Auto-healing invalid specs by silently guessing missing data | Seems user-friendly during runtime edits. | Produces non-reproducible behavior and hides under/over-specified models that should be fixed before migration decisions. | Add explicit preflight validation with actionable diagnostics and optional guided defaults only when clearly safe. |
| New chemistry / unit-model feature expansion during kernel migration | Easy scope creep because instability often reveals model limitations. | Distracts from the milestone, confounds comparisons, and makes it impossible to tell whether improvements came from the kernel or new physics. | Freeze feature scope around existing feeds/sinks/junctions/unit composition and measure kernel stability on that substrate first. |

## Feature Dependencies

```text
[Flowsheet-level consistency at each accepted step]
    ├──requires──> [Determinacy + structural validation before solve]
    ├──requires──> [Robust initialization / warm-start pipeline]
    ├──requires──> [Physical bounds and feasibility guards]
    └──requires──> [Bounded realtime solve policy]

[Recycle / loop convergence controls with damping and acceleration]
    └──requires──> [Current topology/hydraulics graph]

[Hybrid kernel mode: partitioned by default, coupled solve on unstable subgraphs]
    ├──requires──> [Flowsheet-level consistency at each accepted step]
    ├──requires──> [Recycle / loop convergence controls with damping and acceleration]
    └──requires──> [Solver diagnostics and convergence telemetry]

[Edit-aware incremental recompilation]
    └──requires──> [Existing PlantBackendSession runtime editing]

[Automated robustness sweeps / kernel comparison harness]
    └──enhances──> [Migration roadmap toward chosen kernel direction]

[New chemistry / unit-model feature expansion]
    └──conflicts──> [Kernel comparison and migration milestone]
```

### Dependency Notes

- **Flowsheet-level consistency requires structural validation:** coupled or hybrid solves are much harder to stabilize if the model is under-, over-, or circularly specified.
- **Flowsheet-level consistency requires warm starts:** stable kernels for nonlinear flowsheets depend heavily on good initial guesses, especially after runtime edits.
- **Flowsheet-level consistency requires feasibility guards:** without hard physical bounds, stronger coupling can still converge to unusable states.
- **Hybrid kernel mode requires diagnostics telemetry:** without evidence about where the split kernel fails, selective coupling becomes guesswork.
- **Edit-aware recompilation requires existing runtime editing:** this is only valuable because the current system already supports live modifications through `PlantBackendSession`.
- **Kernel comparison conflicts with new feature expansion:** adding new physics during comparison invalidates apples-to-apples evaluation.

## MVP Definition

### Launch With (v1)

Minimum viable milestone output — what is needed to choose and begin a migration path.

- [ ] Flowsheet-level consistency prototype path — enough to compare current split stepping against at least one stronger coupling strategy on representative complex flowsheets.
- [ ] Determinacy / structural / physical preflight checks — essential to separate model-spec problems from kernel problems.
- [ ] Recycle convergence controls + bounded solve policy — essential to keep candidate kernels game-usable instead of academically correct but operationally unusable.
- [ ] Solver diagnostics and comparison telemetry — essential because this milestone is about analysis and roadmap evidence, not just code changes.

### Add After Validation (v1.x)

Features to add once the preferred kernel direction is chosen.

- [ ] Hybrid subgraph escalation — add when benchmarks show that whole-flowsheet coupling is too expensive for every tick but clearly better on unstable regions.
- [ ] Edit-aware incremental recompilation — add when the chosen kernel core can survive topology/spec edits and needs to re-enter live sessions efficiently.
- [ ] Automated robustness sweeps — add when baseline scenarios and acceptance metrics are stable enough to support regression gating.

### Future Consideration (v2+)

Features to defer until the stability migration is proven.

- [ ] Full equation-oriented dynamic DAE stack across all units — defer because it is broader than the current stability milestone and threatens realtime constraints.
- [ ] Expanded chemistry or advanced unit libraries — defer because they complicate migration analysis without directly answering the kernel-stability question.

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Flowsheet-level consistency at each accepted step | HIGH | HIGH | P1 |
| Determinacy + structural validation before solve | HIGH | MEDIUM | P1 |
| Robust initialization / warm-start pipeline | HIGH | HIGH | P1 |
| Recycle / loop convergence controls with damping and acceleration | HIGH | MEDIUM | P1 |
| Physical bounds and feasibility guards | HIGH | MEDIUM | P1 |
| Solver diagnostics and convergence telemetry | HIGH | MEDIUM | P1 |
| Bounded realtime solve policy | HIGH | HIGH | P1 |
| Automated robustness sweeps / kernel comparison harness | HIGH | MEDIUM | P2 |
| Hybrid kernel mode: partitioned by default, coupled solve on unstable subgraphs | HIGH | HIGH | P2 |
| Edit-aware incremental recompilation | MEDIUM | HIGH | P2 |
| Explainable convergence traces | MEDIUM | MEDIUM | P2 |
| Full dynamic DAE kernel across all units | LOW for this milestone | HIGH | P3 |

**Priority key:**
- P1: Must have for launch
- P2: Should have, add when possible
- P3: Nice to have, future consideration

## Competitor / Ecosystem Feature Analysis

| Feature | Ecosystem Example A | Ecosystem Example B | Our Approach |
|---------|---------------------|---------------------|--------------|
| Initialization as first-class workflow | IDAES exposes dedicated Initializer objects, including block triangularization and model-specific initializers. | TESPy documents explicit starting-value generation because bad initial guesses cause singular Jacobians and stalled convergence. | Treat warm start / reinitialization as a kernel feature, not a debugging afterthought. |
| Structural and numerical diagnostics | IDAES recommends square-model checks, structural diagnostics, scaling, Jacobian conditioning, and convergence analysis across expected operating states. | TESPy exposes variable/equation inspection, presolve diagnostics, linear dependency detection, and incidence/Jacobian debugging. | Add preflight and telemetry so kernel comparison is evidence-based and failures are classifiable. |
| Loop / recycle convergence control | CHEMCAD guidance distinguishes sequential modular vs simultaneous modular solving and recommends Wegstein/DEM when loops/controllers make direct substitution unstable. | DWSIM exposes recycle acceleration method, convergence history, iteration counts, maximum iterations, and Wegstein parameters. | Keep explicit recycle/coupling controls even if the long-term direction becomes more coupled. |

## Sources

- `.planning/PROJECT.md` — milestone scope and brownfield constraints.
- IDAES v2.9.0 Concepts: https://idaes-pse.readthedocs.io/en/2.9.0/explanations/concepts.html (HIGH)
- IDAES v2.9.0 Initializing Models: https://idaes-pse.readthedocs.io/en/2.9.0/reference_guides/initialization/index.html (HIGH)
- IDAES v2.9.0 Block Triangularization Initializer: https://idaes-pse.readthedocs.io/en/2.9.0/reference_guides/initialization/bt_initializer.html (HIGH)
- IDAES v2.9.0 Model Diagnostics Workflow: https://idaes-pse.readthedocs.io/en/2.9.0/explanations/model_diagnostics/index.html (HIGH)
- IDAES v2.9.0 Model Diagnostic Functions: https://idaes-pse.readthedocs.io/en/2.9.0/reference_guides/core/util/model_diagnostics.html (HIGH)
- IDAES v2.9.0 Scaling Methods: https://idaes-pse.readthedocs.io/en/2.9.0/reference_guides/core/util/scaling.html (HIGH)
- TESPy v0.9.12 How to Generate Stable Starting Values: https://tespy.readthedocs.io/en/main/advanced_tutorials/starting_values.html (HIGH)
- TESPy v0.9.12 Debug your models efficiently: https://tespy.readthedocs.io/en/main/advanced_tutorials/debugging.html (HIGH)
- DWSIM 8.8.1 Recycle API docs: https://dwsim.org/api_help/html/T_DWSIM_UnitOperations_SpecialOps_Recycle.htm (MEDIUM)
- DWSIM 8.8.1 EnergyRecycle convergence history API docs: https://dwsim.org/api_help/html/P_DWSIM_UnitOperations_SpecialOps_EnergyRecycle_ConvergenceHistory.htm (MEDIUM)
- CHEMCAD / Datacor blog, “From Loops to Logic: Tips for Converging Complex Process Flowsheets” (2025-06-26): https://www.datacor.com/resources/tips-for-converging-complex-process-flowsheets (MEDIUM)

---
*Feature research for: backend simulation kernel stability milestone*
*Researched: 2026-03-29*

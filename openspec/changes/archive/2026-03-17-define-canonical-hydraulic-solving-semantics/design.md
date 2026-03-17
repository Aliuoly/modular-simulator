## Context

The current codebase already contains many of the implementation pieces needed for a canonical hydraulic network model, but they are not yet assembled around one explicit semantics contract. `hydraulic_solver.py` already supports arbitrary unknowns, linear residual equations, connected-component solvability checks, and pressure-reference validation when pressure unknowns exist. Line-level hydraulic overlays also already exist through `HydraulicElement` families and compile-time line overlay management.

At the same time, the active high-level flowsheet path still compiles hydraulics as one flow unknown per edge in `Flowsheet._build_hydraulic_system(...)`, with source and target pressures sampled directly from feeds or unit outlet snapshots instead of being solved as network node pressures. `ConnectionNetwork.compile()` currently emits `junction_nodes=()` even though the topology/runtime layer has an explicit `JunctionNode` concept and dedicated junction-mixing helpers. The domain contract also still carries a `JunctionProcess` shape that is many-in/one-out, which is too narrow for canonical many-in/many-out hydraulic junctions.

This mismatch is already visible in the wrapper units targeted by `canonicalize-hydraulic-junction-api`: `Pump` and `Valve` primarily act as adapters that install line overlays, `Mixer` duplicates junction-mixing behavior that already exists lower in the stack, and `Splitter` documents split ratios even though physical branch flow is meant to come from line hydraulics. The repository therefore needs a semantics-first change that defines what the canonical hydraulic solve actually is before the API-removal and junction-topology changes are implemented.

## Goals / Non-Goals

**Goals:**
- Define the canonical flowsheet hydraulic closure as a network solve over node pressures and line flows rather than as isolated per-edge flow equations with sampled endpoint pressures.
- Specify junctions as true hydraulic nodes with one pressure unknown per junction, mass conservation across all connected lines, and explicit support for simultaneous multiple inlets and multiple outlets.
- Specify that line equations are head-balance relations using line resistance plus optional pump/valve/heat overlays already supported by the line-hydraulic infrastructure.
- Define line-flow ownership so the connection network is the canonical source of physical line flow rates and branch allocation.
- Define how unit processes participate through ports, boundary conditions, pressure/state coupling, and optional constitutive relations without becoming implicit standalone flow solvers.
- Preserve a clean architectural distinction between unit processes and junctions while enabling shared node/port validation and compile helpers.
- Define runtime ordering between hydraulic solving and thermodynamic junction mixing so follow-on implementation work is deterministic.
- Identify how this semantics pack constrains and updates the existing hydraulic/junction API and recycle-loop proposal work.

**Non-Goals:**
- Introduce a brand-new fluid-physics family beyond the existing head-balance and line-overlay model.
- Fully specify every future high-level user-facing API shape; that remains the responsibility of `canonicalize-hydraulic-junction-api`.
- Preserve the old fiction that `Mixer`, `Splitter`, `Pump`, or `Valve` wrappers own canonical physical branch flow behavior.
- Replace genuine thermodynamic/process unit operations such as reactors, flash drums, or heat exchangers with junction semantics.
- Force one specific implementation of constitutive equations for every unit class; the contract is about participation shape, not each unit’s detailed physics.

## Decisions

1. Define the canonical hydraulic closure as a network solve over hydraulic-node pressures and signed line flows.
   - Rationale: the user explicitly requested node-pressure plus mass-balance semantics, and this matches the generic capabilities already present in `HydraulicSystemDefinition`, including pressure-reference equations and connected-component solvability checks.
   - Implementation consequence: the compile layer should emit one signed flow unknown per line, pressure unknowns for participating hydraulic nodes, head-balance residuals per line, and mass-balance residuals for junctions plus any unit-port hydraulic node that must balance more than one attached line, plus at least one reference/boundary equation per connected component.
   - Alternative considered: keep the current per-edge flow-only closure that samples endpoint pressures from feeds and units. Rejected because it cannot formally represent junction pressure solving, makes branch-flow ownership ambiguous, and does not match the requested canonical semantics.

2. Treat junctions as hydraulic nodes rather than as pseudo-unit processes.
   - Rationale: junction behavior is fundamentally a topology and network-solve concern. A junction needs one pressure unknown and one mass-conservation relation over all connected lines, not a many-in/one-out process-model abstraction.
   - Implementation consequence: follow-on work should compile junction definitions into `TopologyGraph.junction_nodes` and related hydraulic-node bookkeeping, with explicit inlet and outlet directionality and support for same-node multi-in/multi-out structures.
   - Alternative considered: keep routing junction semantics through `JunctionProcess`. Rejected because the current contract hardcodes one outlet and would distort the canonical many-in/many-out model.

3. Keep line equations as head-balance relations with optional line-owned overlays.
   - Rationale: the current hydraulic element families and line overlay manager already encode the right ownership boundaries. Pumps and valves alter the hydraulic head relation on a line; heat overlays coexist with the line but do not turn units into hydraulic owners.
   - Implementation consequence: canonical residuals should remain line-centric, with base resistance and optional pump/valve/heat attachments drawn from line configuration rather than wrapper units.
   - Alternative considered: move pump/valve behavior back into unit algebraic models. Rejected because it recreates the wrapper-model mismatch the repository is actively removing.

4. Make the connection network the canonical owner of solved line flow rates.
   - Rationale: branch allocation belongs to the hydraulic closure, not to process-model placeholder fields such as `Splitter.outlet_flows` or `split_ratios`. Runtime thermo coupling already resolves flow primarily from the hydraulic result when available.
   - Implementation consequence: unit models may provide guesses, coupling equations, or boundary conditions, but the network solve remains the source of truth for physical line flow and downstream branch allocation.
   - Alternative considered: allow unit algebraic models to continue defining canonical physical branch flow. Rejected because it conflicts with existing runtime behavior and obscures the solver’s responsibility.

5. Let unit processes participate through ports, boundary conditions, and constitutive couplings rather than as isolated hidden flow solvers.
   - Rationale: unit processes still need to influence hydraulics—for example through fixed outlet pressure, pressure-drop relations, or state-dependent constitutive behavior—but that participation must enter through declared ports that couple to the network closure.
   - Implementation consequence: follow-on compile work should support explicit canonical cases including fixed-pressure ports, pressure-drop or constitutive relations across declared unit ports, passive unit ports that do not add extra hydraulic equations, and explicit failure for conflicting boundary conditions. It should also prevent direct unit-port fan-in/fan-out without an explicit junction unless the unit itself declares the balancing relationship.
   - Alternative considered: define units as self-contained algebraic flow solvers that the network merely samples. Rejected because it breaks the requested canonical ownership model and makes junction solving secondary.

6. Solve hydraulics first and perform thermodynamic junction mixing second.
   - Rationale: runtime junction mixing depends on incoming positive flows and hydraulic pressures. The current runtime already mixes based on resolved incoming flow rates; the semantics change should formalize that ordering instead of leaving it implicit.
   - Implementation consequence: thermo coupling should consume solved hydraulic flows/pressures before evaluating junction mixing, near-zero-flow fallback remains a post-hydraulics fallback for state propagation rather than a replacement for hydraulic solving, and runtime must fail loudly rather than propagate from an unconverged or singular hydraulic solve.
   - Alternative considered: treat thermodynamic mixing and hydraulic solving as one undifferentiated step. Rejected because it blurs ownership, complicates debugging, and conflicts with the current layering.

7. Reuse shared node/port abstractions without collapsing units and junctions into one inheritance tree.
   - Rationale: units and junctions both need port validation, endpoint normalization, and compile adapters, but they are not the same domain concept. Junctions are topology nodes for hydraulic balance; unit processes are process models with port-facing participation in that network.
   - Implementation consequence: introduce shared traits, protocols, or helper abstractions for node/port behavior while preserving distinct compiled representations such as `process_nodes` versus `junction_nodes`.
   - Alternative considered: make `UnitProcess` inherit from `JunctionNode` directly. Rejected because it inverts the domain relationship, muddies API intent, and would make a process model appear to be a special case of a topology junction instead of a separate participant class.

8. Make solver outputs addressable through deterministic topology-to-solution mappings rather than runtime string heuristics.
   - Rationale: the current thermo-coupling layer searches for flow and pressure values by heuristic key matching, but node-pressure solving requires a stable contract for which solved value corresponds to each line endpoint, junction, boundary node, and pressure-coupled unit port.
   - Implementation consequence: compiled hydraulics should expose deterministic lookup data or a stable naming contract for line flow unknowns and node pressure unknowns, and runtime pressure/state propagation should consume that mapping directly.
   - Alternative considered: keep heuristic string lookups in runtime coupling. Rejected because it is too fragile for a canonical solver contract.

9. Define runtime directionality from solved flow sign relative to each attached node.
   - Rationale: the repository already exercises physically reversed signed flow, and many-in/many-out junction semantics are incomplete unless they define how reverse flow changes which node sees a line as incoming versus outgoing in a given step.
   - Implementation consequence: junction mixing and unit-port coupling must classify incoming material by solved sign relative to the local node incidence, not only by declared source/target orientation.
   - Alternative considered: treat declared edge direction as permanent runtime material direction. Rejected because it breaks reverse-flow behavior and contradicts signed line-flow semantics.

10. Treat this change as a governing semantics pack for the existing hydraulic API and recycle validation proposals.
   - Rationale: `canonicalize-hydraulic-junction-api` currently focuses on public API cleanup and wrapper removal, while `reject-invalid-recycle-loops` still references pump-unit semantics. Both need one canonical solving model beneath them.
   - Implementation consequence: follow-on proposal updates should reference this semantics change for flow ownership, junction pressure solving, and line-installed recycle boost rules before implementation begins.
   - Alternative considered: allow each proposal to define its own solver semantics ad hoc. Rejected because that would produce contradictory contracts across overlapping changes.

## Risks / Trade-offs

- Refactoring from sampled endpoint pressures to node-pressure solving touches compile, topology, runtime, and tests across several modules → Mitigation: stage the implementation around explicit compile contracts, then adapt runtime coupling and examples after solver semantics are locked.
- Existing helper code assumes junctions are absent or many-in/one-out only → Mitigation: add shared node/port abstractions and explicit junction-node registration before removing old normalization paths.
- Runtime pressure lookup currently uses heuristic unknown-name discovery in thermo coupling → Mitigation: define deterministic hydraulic-node pressure naming/lookup contracts as part of the implementation tasks and regression tests.
- Reverse-flow behavior can become inconsistent if runtime keeps assuming declared edge orientation determines incoming material → Mitigation: add explicit sign-based directionality requirements and regression tests for reversed junction-connected lines.
- Non-converged hydraulic solves could leave runtime in a partially updated state → Mitigation: require hard failure and actionable diagnostics before junction mixing or state propagation proceeds.
- Cross-change overlap with pending wrapper-removal and recycle-validation proposals could create duplicated or conflicting tasks → Mitigation: make explicit coordination and follow-on updates first-class tasks in this change instead of leaving them implicit.
- Formalizing network-owned branch flow may expose latent assumptions in wrapper units and examples → Mitigation: add regression coverage that proves physical branch flow comes from hydraulic results rather than wrapper-unit placeholders.

## Migration Plan

1. Land the semantics pack and align overlapping proposal/design/spec language so follow-on implementation work starts from one canonical hydraulic model.
2. Refactor topology and hydraulic compilation to emit hydraulic nodes, node-pressure unknowns, mass-balance residuals, and deterministic pressure-reference handling.
3. Update unit/junction participation contracts and shared node/port helpers while preserving distinct topology/runtime node types.
4. Update thermo coupling and junction runtime ordering so hydraulic solve outputs drive mixing and downstream state propagation deterministically.
5. Apply the semantics to the pending high-level junction/line API change, recycle-loop validation change, examples, and wrapper-removal work.
6. If rollback is required before merge, revert the follow-on compile/runtime changes together with proposal/example coordination so the repository does not advertise semantics it does not implement.

## Open Questions

- None. This design intentionally fixes the ownership model, junction pressure semantics, unit participation rules, architectural separation, and hydraulics-first runtime ordering up front so the follow-on API work is constrained rather than exploratory.

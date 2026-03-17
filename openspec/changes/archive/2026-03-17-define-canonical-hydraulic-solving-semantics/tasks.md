## 1. Canonical Hydraulic Closure

- [x] 1.1 Define and implement a hydraulic-node compile model that emits signed line-flow unknowns, hydraulic-node pressure unknowns, and mass-balance residuals for the canonical network solve.
- [x] 1.2 Add compile-time pressure-reference and boundary-condition handling so every connected hydraulic component is square and anchored under the node-pressure closure.
- [x] 1.3 Refactor line-equation assembly so canonical residuals remain head-balance relations with line resistance plus optional pump/valve/heat overlays.
- [x] 1.4 Add deterministic topology-to-solver lookup data for line flows and node pressures so runtime coupling no longer depends on heuristic unknown-name discovery.
- [x] 1.5 Add compile-time validation for conflicting hydraulic anchors or over-constrained unit-port boundary conditions within one connected hydraulic component.

## 2. Junction And Unit Participation Model

- [x] 2.1 Extend topology/domain compilation so junctions are emitted as explicit many-in/many-out hydraulic nodes instead of only via the current many-in/one-out `JunctionProcess` path.
- [x] 2.2 Update unit hydraulic participation contracts to cover canonical cases for fixed-pressure ports, pressure-drop or constitutive relations across ports, passive ports, and invalid conflicting boundary conditions.
- [x] 2.3 Define and enforce whether direct unit-port fan-in/fan-out is illegal without an explicit junction unless the unit itself declares the balancing relationship.
- [x] 2.4 Introduce shared node/port validation or adapter abstractions reused by units and junctions while keeping distinct unit-process and junction node identities.
- [x] 2.5 Replace the current conflation points in `connection/domain/domain_contracts.py`, `connection/domain/reconfiguration_api.py`, and `connection/runtime/runtime.py` so junctions no longer round-trip through `UnitProcess.process_kind="junction"`, `JunctionProcess.as_unit_process()`, or `add_junction -> add_process` routing.

## 3. Runtime Ordering And Coupling

- [x] 3.1 Update thermo-coupling/runtime evaluation so solved hydraulic flows and pressures are resolved before junction mixing and downstream state propagation.
- [x] 3.2 Preserve and verify near-zero-flow junction fallback behavior as a post-hydraulics state-propagation rule rather than a substitute for the hydraulic solve, and forbid silent replacement of solved hydraulic flow with unit payload flow when hydraulic data is present.
- [x] 3.3 Add runtime handling for same-junction multiple-inlet and multiple-outlet cases so one mixed junction state feeds all outgoing edges while branch flows remain network-owned.
- [x] 3.4 Add explicit reverse-flow handling so incoming versus outgoing material at junctions and unit ports is classified from solved flow sign relative to the local node.
- [x] 3.5 Fail runtime steps loudly, with diagnostics, when the hydraulic solve is singular or non-converged instead of propagating thermodynamic state from an invalid solve result.

## 4. Coordination With Existing Proposal Work

- [x] 4.1 Align `canonicalize-hydraulic-junction-api` artifacts and implementation planning with this semantics pack so wrapper removal and junction APIs inherit canonical flow-ownership and pressure-solving rules.
- [x] 4.2 Align `reject-invalid-recycle-loops` artifacts and follow-on implementation so required recycle pressure boost is represented by line-installed pump semantics instead of pump-unit ownership.
- [x] 4.3 Update curated example specs and migration guidance immediately, then land code/example rewrites only after `canonicalize-hydraulic-junction-api` provides the required junction, sink, and line-install public API.

## 5. Verification

- [x] 5.1 Add compile and solver regression tests for node-pressure plus mass-balance closure across feeds, unit ports, and many-in/many-out junctions.
- [x] 5.2 Add regression tests proving canonical physical line flow comes from the hydraulic network solve rather than `Splitter.outlet_flows`, `split_ratios`, or other unit-level placeholders.
- [x] 5.3 Add runtime ordering tests covering hydraulics-first junction evaluation, positive-flow-only mixing, and near-zero fallback behavior.
- [x] 5.4 Add regression tests for reverse-flow classification at junctions and pressure-coupled unit ports.
- [x] 5.5 Add regression tests for non-converged hydraulic solve handling and deterministic pressure/flow lookup from compiled hydraulic outputs.
- [x] 5.6 Add architecture-level coverage confirming shared node/port helpers preserve separate unit and junction representations.

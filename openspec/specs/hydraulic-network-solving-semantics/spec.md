# Hydraulic Network Solving Semantics

## Purpose

This capability defines the canonical hydraulic semantics for flowsheet compilation and runtime coupling: node-pressure plus line-flow network closure, explicit junction-node solving, deterministic topology-to-solution lookup, unit-port hydraulic participation, and hydraulics-first runtime propagation.

## Requirements

### Requirement: Canonical Hydraulic Closure Solves Node Pressures And Line Flows
The canonical flowsheet hydraulic model SHALL be compiled as a network solve with signed line-flow unknowns, hydraulic-node pressure unknowns, line head-balance residuals, mass-balance residuals for multi-connection hydraulic nodes, and explicit pressure-reference or boundary-condition anchoring for each connected hydraulic component.

#### Scenario: Connected hydraulic component compiles under node-pressure closure
- **WHEN** a flowsheet contains connection lines linked through junctions, boundary nodes, or pressure-coupled unit ports
- **THEN** the hydraulic compile path emits one signed flow unknown per line, pressure unknowns for participating hydraulic nodes, and sufficient residual equations to make each connected hydraulic component square and pressure-referenced

#### Scenario: Missing pressure reference fails the network solve contract
- **WHEN** a connected hydraulic component has pressure unknowns but no explicit reference equation or boundary condition anchoring that component
- **THEN** compile or validation fails with an actionable error explaining that the component is missing a hydraulic pressure reference

### Requirement: Canonical Line Equations Remain Head-Balance Relations
Each canonical connection line SHALL contribute a head-balance relation based on line resistance together with any active pump or valve hydraulic overlay, while optional line heat overlays remain co-located line metadata rather than replacing the hydraulic equation family.

#### Scenario: Passive line uses resistance-based head balance
- **WHEN** a line has only its base hydraulic resistance configuration
- **THEN** the canonical hydraulic residual for that line is evaluated as a resistance-based head-balance relation between the solved upstream and downstream hydraulic node pressures and the solved signed line flow

#### Scenario: Pump or valve overlay augments the line head balance
- **WHEN** a line installs a pump or valve overlay
- **THEN** the canonical line residual remains a head-balance equation for that line with the active overlay contribution applied through line-owned hydraulic metadata rather than a standalone unit-process flow equation

#### Scenario: Heat overlay does not change hydraulic ownership
- **WHEN** a line installs a heat actuator together with zero or one hydraulic overlay
- **THEN** the heat actuator remains attached to the line without changing the rule that the line’s flow and head balance are owned by the hydraulic network solve

### Requirement: Junctions Are Solved As Hydraulic Nodes
The canonical model SHALL solve each junction as one hydraulic node with one pressure unknown per junction and mass conservation across all connected lines, including junctions with multiple inlets and multiple outlets at the same node.

#### Scenario: Multi-in multi-out junction compiles as one hydraulic node
- **WHEN** a flowsheet defines one junction with more than one inlet port and more than one outlet port and connects multiple incoming and outgoing lines to that same junction
- **THEN** the compiled hydraulic system contains one pressure unknown for that junction, one node-level mass-balance relation covering all connected lines, and individual line equations for each attached connection

#### Scenario: Junction branch allocation remains network-owned
- **WHEN** multiple outgoing lines leave the same junction
- **THEN** the hydraulic network solve determines the signed branch flow on each outgoing line from the canonical closure rather than from unit-level split-ratio state or placeholder outlet-flow arrays

#### Scenario: Reverse-flow classification follows solved sign at the junction
- **WHEN** a line attached to a junction reverses sign relative to its declared source-to-target orientation during a runtime step
- **THEN** the junction treats that line as incoming or outgoing according to the solved flow sign relative to the junction node for that step rather than according to the line’s declared endpoint orientation alone

### Requirement: Connection Network Owns Canonical Physical Line Flows
The connection network SHALL be the canonical source of solved physical line flow rates, and unit-process algebraic models SHALL NOT define or override canonical line flows outside the network solve.

#### Scenario: Hydraulic result overrides unit-level flow placeholders
- **WHEN** runtime coupling has both a solved hydraulic result and unit-level flow-like values available for the same connection line
- **THEN** the canonical line flow used for connection transport and downstream branch allocation comes from the hydraulic result

#### Scenario: Splitter placeholders do not define physical branch flow
- **WHEN** a flowsheet contains behavior historically represented by `Splitter` state such as `split_ratios` or `outlet_flows`
- **THEN** those placeholders are not treated as the canonical source of physical branch allocation for the connected lines

#### Scenario: Solved near-zero hydraulic flow is not silently replaced by unit payload flow
- **WHEN** the hydraulic result includes an explicit solved line flow value that is zero or near zero for a runtime step
- **THEN** runtime preserves that solved hydraulic flow as canonical instead of silently substituting a unit payload flow value for that line

#### Scenario: Fallback flow path is explicit when hydraulic data is missing
- **WHEN** canonical hydraulic data for a line is unavailable during a runtime path that still supports legacy fallback behavior
- **THEN** any non-hydraulic fallback used for transport is explicitly identified by a defined runtime contract and diagnostics rather than being treated as canonical solved line flow

### Requirement: Unit Processes Participate Through Ports And Coupled Relations
Unit processes that participate in hydraulics SHALL do so through one explicit `ProcessModel.hydraulic_participation` contract rather than as implicit standalone flow solvers or inferred metadata-driven participation.

The canonical declaration surface SHALL name every hydraulically relevant `UnitProcessPorts` port, its role (`passive`, `pressure_state`, or `fixed_pressure_anchor`), the exact declared scalar/indexed/property-backed state reference used for solved or anchored pressure, every balancing group that contributes unit flow-balance equations, every affine pressure relation that the unit truly owns, and any unit-owned hydraulic-element coupling that preserves existing `to_hydraulic_element(...)` behavior.

#### Scenario: Unit contributes a hydraulic boundary condition through an explicit declaration
- **WHEN** a unit process exposes a port with fixed pressure, pressure-drop, or other hydraulic constitutive information relevant to the network
- **THEN** that information enters the canonical hydraulic solve through an explicit unit hydraulic participation declaration rather than being inferred from field naming conventions alone

#### Scenario: Missing explicit hydraulic declaration fails clearly
- **WHEN** a unit requires fixed-pressure, pressure-drop, constitutive, or balancing participation in the hydraulic network but does not declare that participation explicitly
- **THEN** compile fails with an actionable error identifying the missing unit hydraulic declaration instead of silently inferring canonical behavior from metadata patterns

#### Scenario: Connected unit-process ports require an explicit declaration
- **WHEN** any `UnitProcessPorts` endpoint of a unit is connected into the compiled hydraulic topology
- **THEN** that unit must expose a non-`None` `hydraulic_participation` declaration, even if some or all connected ports are declared passive

#### Scenario: Undeclared ports are not implicitly passive
- **WHEN** a hydraulically participating unit omits one of its declared `UnitProcessPorts` from the `hydraulic_participation` contract
- **THEN** validation or compile fails instead of treating the missing port as implicitly passive

#### Scenario: Balancing groups are the only source of unit flow-balance equations
- **WHEN** a single-path unit, paired-path unit, or branching unit is expected to contribute unit continuity equations to the hydraulic solve
- **THEN** those equations come only from explicitly declared balancing groups rather than `_infer_unit_flow_balance_groups()` or other implicit port-pattern inference

#### Scenario: Ordinary and paired-path units declare their balancing semantics explicitly
- **WHEN** a unit has one hydraulic path `(inlet, outlet)` or two independent paired paths such as `(hot_inlet, hot_outlet)` and `(cold_inlet, cold_outlet)`
- **THEN** the unit declares one balancing group per hydraulic path and compile does not invent additional pairings from port names alone

#### Scenario: Conflicting explicit declarations fail validation
- **WHEN** one unit hydraulic participation declaration marks a port passive while another declaration or relation also marks that same port as anchored, pressure-coupled, or balancing-active
- **THEN** model validation or compile fails with an actionable error identifying the conflicting declarations

#### Scenario: Relation and balancing overlap follows fixed rules
- **WHEN** one port is referenced by multiple relation or balancing groups
- **THEN** validation allows that overlap only when the port is non-passive, appears in at most one balancing group, and each referenced relation uses a valid kind/cardinality for the named ports

#### Scenario: Declared state references may be scalar, indexed, shared, or property-backed
- **WHEN** a unit port uses a scalar pressure state, a vector pressure state entry, or a shared/property-backed scalar pressure accessor
- **THEN** the declaration names that exact state reference explicitly and validation confirms the reference exists and is valid for the instantiated unit instead of relying on string heuristics

#### Scenario: Identical declared pressure references share one compiled pressure unknown
- **WHEN** two or more ports in one unit declare the same scalar, indexed, or property-backed pressure-state reference
- **THEN** compile maps those ports to the same hydraulic pressure unknown instead of inventing an extra equality relation for that shared state

#### Scenario: Pump and valve participation preserve unit-owned hydraulic-element behavior
- **WHEN** a pump or valve participates hydraulically through its existing `to_hydraulic_element(...)` surface
- **THEN** the declaration records that participation as an explicit unit-owned hydraulic-element coupling instead of pretending the model is a simple affine compile-time pressure-offset relation

#### Scenario: Passive unit port is declared explicitly
- **WHEN** a unit port participates in topology but is intended to add no hydraulic boundary condition or constitutive relation
- **THEN** the unit declares that port as passive explicitly and the compile path does not invent an additional hydraulic equation for it

#### Scenario: Unknown declaration port fails clearly
- **WHEN** a unit hydraulic participation declaration references a port name not present in the unit's declared `UnitProcessPorts`
- **THEN** model validation or compile fails with an actionable error identifying the unknown port reference

#### Scenario: Direct unit-port fan-in or fan-out requires explicit balancing declaration
- **WHEN** multiple lines are attached directly to one unit port without an explicit junction
- **THEN** compile succeeds only if that physical port belongs to the declared balancing group that admits the direct attachment; otherwise compile fails with an actionable error telling the model author to insert an explicit junction

#### Scenario: Declared direct multi-edge ports use the balancing-group equation, not an extra node equation
- **WHEN** a directly attached unit port is admitted by a declared balancing group
- **THEN** the hydraulic solve uses the declared balancing-group continuity equation for that unit context and does not also add a duplicate automatic node mass-balance equation for the same multi-edge process port

#### Scenario: Diagnostics identify the failing unit, port or group, and remediation
- **WHEN** compile or validation rejects a missing, conflicting, or invalid hydraulic participation declaration
- **THEN** the diagnostic names the unit, the offending port or relation/balancing group, and whether the remedy is to add `hydraulic_participation` metadata or to insert an explicit junction for unsupported direct multi-edge attachment

#### Scenario: Pressure-coupled unit port uses deterministic solved pressure lookup
- **WHEN** runtime or transport logic needs the solved hydraulic pressure associated with a pressure-coupled unit port
- **THEN** it resolves that pressure through the compiled hydraulic topology mapping plus the compiled endpoint-role participation marker for the explicitly declared hydraulic port rather than through heuristic string matching or undeclared inference behavior

#### Scenario: Runtime fallback is limited to passive or non-participating endpoints
- **WHEN** runtime pressure or flow lookup misses a compiled hydraulic mapping
- **THEN** payload, transport-state, or default fallback is allowed only when the compiled participation marker says the endpoint is passive or outside explicit hydraulic participation; pressure-coupled declared endpoints fail instead of silently falling back

### Requirement: Compiled Hydraulics Expose Deterministic Topology-To-Solution Lookup
The compiled hydraulic representation SHALL expose deterministic mapping from topology entities to solved line-flow and node-pressure outputs so runtime transport, junction mixing, and unit-port coupling do not depend on heuristic unknown-name discovery.

#### Scenario: Junction pressure is addressable from compiled hydraulics
- **WHEN** runtime needs the solved pressure for a compiled junction node
- **THEN** the compiled hydraulic graph provides a deterministic way to resolve that junction’s pressure unknown from the junction identifier

#### Scenario: Line endpoint pressure is addressable from compiled hydraulics
- **WHEN** runtime needs the solved upstream or downstream hydraulic pressure associated with a connection line endpoint
- **THEN** the compiled hydraulic graph provides a deterministic mapping from that endpoint’s topology identity to the corresponding solved node pressure

#### Scenario: Canonical line flow is addressable from compiled hydraulics
- **WHEN** runtime needs the solved physical flow for a connection line
- **THEN** the compiled hydraulic graph provides a deterministic mapping from the line identifier to the corresponding solved signed flow unknown

### Requirement: Hydraulic Solve Precedes Junction Mixing And State Propagation
Runtime evaluation SHALL resolve canonical hydraulic flows and available hydraulic pressures before thermodynamic junction mixing or downstream state propagation consumes those values.

#### Scenario: Junction mixing uses solved positive incoming flows
- **WHEN** multiple incoming lines feed a junction during a runtime step
- **THEN** the junction mixing logic runs after hydraulic solving and uses the solved positive incoming line flows to determine the mixed state presented to outgoing edges

#### Scenario: Near-zero incoming flow falls back after hydraulic solving
- **WHEN** the hydraulic solve yields a junction total incoming flow at or below the near-zero fallback threshold for a runtime step
- **THEN** runtime keeps the previous junction state for thermodynamic propagation while leaving the canonical hydraulic solve ownership unchanged

#### Scenario: Non-converged hydraulic solve aborts downstream propagation
- **WHEN** the canonical hydraulic solve for a runtime step is singular or returns non-converged
- **THEN** runtime fails the step with actionable diagnostics and does not continue with junction mixing or downstream thermodynamic state propagation from that invalid solve result

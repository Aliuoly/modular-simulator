## ADDED Requirements

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
Unit processes that participate in hydraulics SHALL do so through declared ports, hydraulic boundary conditions, pressure/state coupling, and optional constitutive relationships that couple unit behavior to the network closure, rather than as implicit standalone flow solvers.

#### Scenario: Unit contributes a hydraulic boundary condition through a port
- **WHEN** a unit process exposes a port with fixed pressure, pressure-drop, or other hydraulic constitutive information relevant to the network
- **THEN** that information enters the canonical hydraulic solve through port-coupled equations or boundary conditions instead of bypassing the network as an isolated unit-owned flow solution

#### Scenario: Fixed-pressure unit port anchors a connected component
- **WHEN** a unit port declares a fixed hydraulic pressure boundary condition and participates in a connected hydraulic component
- **THEN** that port’s pressure condition may serve as one of the canonical anchors for the node-pressure solve of that component

#### Scenario: Pressure-drop relation couples ports through the network solve
- **WHEN** a unit declares a constitutive hydraulic relation such as a pressure-drop law across two or more of its ports
- **THEN** the compile path adds that relation to the canonical hydraulic system as a port-coupled residual rather than solving the connected line flows inside the unit separately from the network

#### Scenario: Passive unit port adds no extra hydraulic equation
- **WHEN** a unit port participates in topology but declares no hydraulic boundary condition or constitutive hydraulic relation
- **THEN** the unit port participates as a passive connection point and does not by itself introduce a separate canonical line-flow equation outside the network closure

#### Scenario: Conflicting unit hydraulic anchors fail clearly
- **WHEN** one connected hydraulic component contains incompatible fixed-pressure or equivalent boundary conditions contributed by unit ports, boundaries, or explicit references
- **THEN** compile or validation fails with an actionable error identifying the conflicting hydraulic anchors

#### Scenario: Direct unit-port fan-in or fan-out requires explicit balancing semantics
- **WHEN** multiple lines are attached directly to one unit port without an explicit junction or unit-declared balancing relation
- **THEN** compile fails with an actionable error directing the model author to add an explicit junction or a unit model that declares the required hydraulic coupling semantics

#### Scenario: Shared node-port helpers preserve separate unit and junction identities
- **WHEN** compile or validation logic reuses shared node-port abstractions for both units and junctions
- **THEN** the resulting topology and runtime models still distinguish unit-process nodes from junction nodes rather than making `UnitProcess` a direct subtype of `JunctionNode`

#### Scenario: Pressure-coupled unit port uses deterministic solved pressure lookup
- **WHEN** runtime or transport logic needs the solved hydraulic pressure associated with a pressure-coupled unit port
- **THEN** it resolves that pressure through the compiled hydraulic topology mapping for that port rather than by heuristic string matching on unknown names

#### Scenario: Reverse-flow classification follows solved sign at a unit port
- **WHEN** a solved line flow reverses sign relative to a pressure-coupled or constitutive unit port during a runtime step
- **THEN** runtime and coupling logic classify incoming versus outgoing material for that unit port from the solved flow sign relative to the port’s local node incidence rather than from declared source/target orientation alone

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

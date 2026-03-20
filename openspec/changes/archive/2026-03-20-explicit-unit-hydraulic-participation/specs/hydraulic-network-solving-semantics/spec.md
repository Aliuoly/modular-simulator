## MODIFIED Requirements

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

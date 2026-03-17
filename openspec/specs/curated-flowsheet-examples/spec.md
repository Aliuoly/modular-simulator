# Curated Flowsheet Examples

## Purpose

This capability defines the standards and structure for a curated set of flowsheet examples that demonstrate recognized process modeling patterns and core repository capabilities. The examples serve as educational reference implementations and test cases for the framework's high-level API.

## Requirements

### Requirement: Curated Example Set Size And Scope
The project SHALL provide a curated set of examples limited to a small, intentional catalog that highlights recognized process modeling patterns and core repository capabilities.

#### Scenario: Example inventory is intentionally limited
- **WHEN** the examples catalog is reviewed for this change
- **THEN** the retained set contains only a handful of examples with clear and distinct educational purpose

### Requirement: Flowsheet-Style Structure
Every retained curated example SHALL define boundary feed streams that connect to process ports or junction inlet ports, SHALL represent hydraulically relevant merge and split topology through explicit connection edges and junction nodes, and SHALL document terminal product handoff through the canonical high-level `Flowsheet` API using boundary sinks when that API is available.

#### Scenario: Boundary streams and hydraulic nodes are explicit
- **WHEN** a curated example is inspected
- **THEN** all external feeds are represented as boundary streams attached to process ports or junction inlet ports, and any product draw is attached to a boundary sink whenever the canonical topology-first flowsheet API exposes sink registration

#### Scenario: Unit and junction connectivity is edge-based
- **WHEN** flow moves between units, junctions, feeds, or sinks in a curated example
- **THEN** each transfer is represented through explicit connection edges rather than hidden internal routing or wrapper-unit shortcuts

#### Scenario: Product handling follows canonical junction and sink capability
- **WHEN** a curated example exports product material under the canonical hydraulic and junction model
- **THEN** the example uses the supported sink or terminal connection path documented by that canonical API instead of legacy undocumented terminal-outlet conventions

#### Scenario: Recycle examples use explicit return edges with line-installed boost
- **WHEN** a curated example is described as a recycle loop that requires positive hydraulic pressure boost on the recycle path
- **THEN** the recycle leg is represented as an explicit return edge with the required boost installed on that line rather than as a second feed boundary or a `Pump` wrapper unit

#### Scenario: Hydraulically relevant merge and split topology uses junction nodes
- **WHEN** a curated example includes mixing, splitting, or recycle merge behavior that is part of the hydraulic network topology
- **THEN** the example represents that behavior with canonical junction nodes rather than `Mixer` or `Splitter` wrapper units


### Requirement: Control Placement On Required Edges
Curated examples SHALL place hydraulic control elements only on required connection edges where manipulated head, throttling, or line heat behavior is intended, and SHALL NOT model those controls through `Pump`, `Valve`, `Mixer`, or `Splitter` wrapper units.

#### Scenario: Control elements are attached to required edges
- **WHEN** a curated example includes control behavior
- **THEN** each hydraulic or thermal control element is bound to a specific required connection edge instead of unit internals or wrapper-unit substitutes

#### Scenario: Recycle pressure boost is edge-owned
- **WHEN** a curated example requires recycle pressure boost to make the loop physically valid
- **THEN** that boost is attached to the recycle connection edge as canonical line-owned control metadata

#### Scenario: Wrapper-unit hydraulic shortcuts are absent from canonical examples
- **WHEN** a curated example is reviewed for canonical hydraulic semantics
- **THEN** it does not use `Pump`, `Valve`, `Mixer`, or `Splitter` wrapper units to represent line hydraulics, splitting, or hydraulic mixing topology

### Requirement: Internal-Only Unit Process States
Curated examples SHALL model unit processes with internal state only and SHALL NOT use unit-level actuators.

#### Scenario: Unit process model excludes actuators
- **WHEN** a curated unit process definition is reviewed
- **THEN** the unit exposes internal states without direct actuator constructs

### Requirement: Example Purpose Documentation
Each curated example SHALL include concise purpose documentation that states what capability it demonstrates and why it is part of the canonical set.

#### Scenario: Example purpose is discoverable
- **WHEN** a user opens a curated example entrypoint or index
- **THEN** they can read a short description of the demonstrated capability and intended learning outcome

### Requirement: Review Alignment Verification
Review-discovered correctness regressions in curated examples and shared calculation behavior SHALL be covered by automated verification.

#### Scenario: Calculation outputs inherit all-input fault state
- **WHEN** any wired input to an `AbstractCalculation` is not ok
- **THEN** every output `DataValue` emitted by that calculation is also marked not ok

#### Scenario: Automated checks cover the curated path
- **WHEN** repository CI runs for this change
- **THEN** it executes lint, type-check, curated example smoke coverage, and the narrow review-alignment regression tests

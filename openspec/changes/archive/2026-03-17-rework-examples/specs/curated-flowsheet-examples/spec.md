## ADDED Requirements

### Requirement: Curated Example Set Size And Scope
The project SHALL provide a curated set of examples limited to a small, intentional catalog that highlights recognized process modeling patterns and core repository capabilities.

#### Scenario: Example inventory is intentionally limited
- **WHEN** the examples catalog is reviewed for this change
- **THEN** the retained set contains only a handful of examples with clear and distinct educational purpose

### Requirement: Flowsheet-Style Structure
Every retained curated example SHALL define boundary feed streams that connect to process ports, SHALL connect unit processes through explicit connection edges, and SHALL document terminal product handoff through the current high-level `Flowsheet` API.

#### Scenario: Boundary streams and process ports are explicit
- **WHEN** a curated example is inspected
- **THEN** all external feeds are represented as boundary streams attached to process ports, and any product draw is either attached to a boundary sink or explicitly documented as a unit outlet when the high-level flowsheet API does not yet expose boundary sinks

#### Scenario: Unit connectivity is edge-based
- **WHEN** unit-to-unit flow is represented in a curated example
- **THEN** each transfer occurs through explicit connection objects between process ports

#### Scenario: Product handling follows current runtime capability
- **WHEN** a curated example exports product material with the current high-level `Flowsheet` API
- **THEN** the example documents the product stream via the terminal unit outlet unless a boundary-sink helper is available in that API

#### Scenario: Recycle examples use explicit return edges
- **WHEN** a curated example is described as a recycle loop
- **THEN** the recycle leg is represented as an explicit unit-to-unit connection rather than a second external feed boundary

### Requirement: Control Placement On Required Edges
Curated examples SHALL place control elements only on required connection edges where manipulated behavior is intended.

#### Scenario: Control elements are attached to required edges
- **WHEN** a curated example includes control behavior
- **THEN** each control element is bound to a specific required connection edge instead of unit internals

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

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
Every retained curated example SHALL define boundary feed streams that connect to process ports or junction inlet ports, SHALL represent unit and junction connectivity through explicit connection edges, and SHALL document terminal product handoff through the current high-level `Flowsheet` API or the canonical sink-based API once that sibling capability is available.

#### Scenario: Boundary streams and process ports are explicit
- **WHEN** a curated example is inspected
- **THEN** all external feeds are represented as boundary streams attached to process ports or junction inlet ports, and any product draw is either attached to a boundary sink or explicitly documented against the currently available API surface when the canonical sink helper is not yet available

#### Scenario: Unit connectivity is edge-based
- **WHEN** unit-to-unit, unit-to-junction, or junction-to-unit flow is represented in a curated example
- **THEN** each transfer occurs through explicit connection objects between the relevant ports or endpoints

#### Scenario: Product handling follows current runtime capability
- **WHEN** a curated example exports product material with the current high-level `Flowsheet` API
- **THEN** the example documents the product stream via the terminal unit outlet unless a boundary-sink helper is available in that API

#### Scenario: Recycle examples use explicit return edges and line-installed boost
- **WHEN** a curated example is described as a recycle loop
- **THEN** the recycle leg is represented as an explicit return connection in the topology rather than a second external feed boundary, and any required pressure boost is installed on that recycle line rather than modeled as a pressure-boost wrapper unit

#### Scenario: Recycle examples remain physically viable
- **WHEN** a curated example is described as a recycle loop
- **THEN** the recycle path includes supported positive line-installed pump boost so the example remains physically viable and passes recycle-loop validation under the current high-level API

#### Scenario: Junction-and-sink migration follows sibling API availability
- **WHEN** this recycle validation change is implemented before `canonicalize-hydraulic-junction-api`
- **THEN** curated examples may continue using the currently available high-level endpoint surface for shipped code and smoke coverage, while final canonical migration details still track the sibling junction-and-sink API change


### Requirement: Control Placement On Required Edges
Curated examples SHALL place control elements only on required connection edges where manipulated behavior is intended.

#### Scenario: Control elements are attached to required edges
- **WHEN** a curated example includes control behavior
- **THEN** each control element is bound to a specific required connection edge through the canonical high-level line-element API instead of through deleted flow-control or topology wrapper units

### Requirement: Internal-Only Unit Process States
Curated examples SHALL reserve unit-process models for intrinsic process behavior only and SHALL NOT use deleted topology-wrapper or flow-control-wrapper unit models.

#### Scenario: Unit process model excludes flow-control and topology wrappers
- **WHEN** a curated example unit definition is reviewed
- **THEN** the example uses thermodynamic/process unit models for intrinsic behavior and uses junctions plus line-installed controls for mixing, splitting, throttling, and pressure boost

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

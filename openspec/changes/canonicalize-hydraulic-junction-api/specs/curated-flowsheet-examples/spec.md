## MODIFIED Requirements

### Requirement: Flowsheet-Style Structure
Every retained curated example SHALL define boundary feed streams that connect to process ports or junction ports, SHALL connect process units and junctions through explicit connection edges, and SHALL document terminal product handoff through the current high-level `Flowsheet` API.

#### Scenario: Boundary streams and process or junction ports are explicit
- **WHEN** a curated example is inspected
- **THEN** all external feeds are represented as boundary streams attached to process or junction ports, and any product draw is attached to an explicit high-level boundary sink rather than a terminal-outlet convention

#### Scenario: Unit and junction connectivity is edge-based
- **WHEN** flow is represented in a curated example
- **THEN** each transfer occurs through explicit connection objects between process ports and junction ports rather than through `Mixer` or `Splitter` wrapper units

#### Scenario: Product handling follows current runtime capability
- **WHEN** a curated example exports product material with the current high-level `Flowsheet` API
- **THEN** the example uses the high-level boundary sink API so product handoff is explicit in the topology

#### Scenario: Recycle examples use explicit return edges and line-installed boost
- **WHEN** a curated example is described as a recycle loop
- **THEN** the recycle leg is represented as an explicit edge and any required pressure boost is installed on that recycle line rather than modeled as a `Pump` unit

### Requirement: Control Placement On Required Edges
Curated examples SHALL place control elements only on required connection edges where manipulated behavior is intended.

#### Scenario: Control elements are attached to required edges
- **WHEN** a curated example includes control behavior
- **THEN** each control element is bound to a specific required connection edge through the canonical high-level line-element API instead of through `Pump` or `Valve` wrapper units

### Requirement: Internal-Only Unit Process States
Curated examples SHALL reserve unit-process models for intrinsic process behavior only and SHALL NOT use `Pump`, `Valve`, `Mixer`, or `Splitter` wrapper units.

#### Scenario: Unit process model excludes flow-control and topology wrappers
- **WHEN** a curated example unit definition is reviewed
- **THEN** the example uses thermodynamic/process unit models for intrinsic behavior and uses junctions plus line-installed controls for mixing, splitting, throttling, and pressure boost

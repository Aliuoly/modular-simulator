## MODIFIED Requirements

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

#### Scenario: Recycle examples use explicit return edges
- **WHEN** a curated example is described as a recycle loop
- **THEN** the recycle leg is represented as an explicit unit-to-unit connection rather than a second external feed boundary

#### Scenario: Recycle examples remain physically viable
- **WHEN** a curated example is described as a recycle loop
- **THEN** the recycle path includes supported positive line-installed pump boost so the example passes recycle-loop validation once the canonical junction/line API is available

#### Scenario: Junction-and-sink migration follows sibling API availability
- **WHEN** this recycle validation change is implemented before `canonicalize-hydraulic-junction-api`
- **THEN** any example wording or interim example code may remain on the currently available high-level endpoint surface, but final canonical example migration still tracks the sibling junction-and-sink API change

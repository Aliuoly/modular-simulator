## ADDED Requirements

### Requirement: Live connection requirements are consolidated in one domain
Live connection behavior requirements SHALL be kept in the `connection` domain so topology API, hydraulic solving semantics, and recycle-loop validation are maintained together.

#### Scenario: Connection domain owns merged requirements
- **WHEN** a contributor inspects live specs after this change
- **THEN** requirements previously split across `flowsheet-junction-line-api`, `hydraulic-network-solving-semantics`, and `recycle-loop-validation` are found under `connection`

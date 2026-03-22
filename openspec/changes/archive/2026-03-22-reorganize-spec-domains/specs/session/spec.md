## ADDED Requirements

### Requirement: Simulation session behavior uses the session domain
Live requirements for simulation session APIs, session error codes, and session state contracts SHALL live under `session`.

#### Scenario: Session requirements are split from economics contracts
- **WHEN** a contributor inspects live specs after this change
- **THEN** session behavior requirements are maintained under `session` without economics-ledger requirement blocks

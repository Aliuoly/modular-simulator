## ADDED Requirements

### Requirement: Economics behavior uses the economics domain
Live requirements for economics-ledger APIs, request errors, contract shapes, and frozen rule/price tables SHALL live under `economics`.

#### Scenario: Economics requirements are separated from simulation-session blocks
- **WHEN** a contributor inspects live specs after this change
- **THEN** economics requirements are maintained under `economics` while session-only behavior remains under `session`

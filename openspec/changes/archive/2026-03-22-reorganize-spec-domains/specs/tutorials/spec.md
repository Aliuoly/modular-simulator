## ADDED Requirements

### Requirement: Tutorial contracts are maintained in the tutorials domain
Live requirements for tutorial boundaries, goal contracts, and frozen tutorial records SHALL live under `tutorials`.

#### Scenario: Tutorial requirements are split out from build catalog packaging
- **WHEN** a contributor inspects live specs after this change
- **THEN** tutorial-specific requirements are maintained under `tutorials` instead of being bundled into a broader catalog work-item spec

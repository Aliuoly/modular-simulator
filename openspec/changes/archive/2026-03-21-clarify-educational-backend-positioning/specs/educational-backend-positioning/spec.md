## ADDED Requirements

### Requirement: Repository Framing Identifies An Educational Backend
The repository SHALL be described as a simulation-first backend for educational chemical-process gameplay and classroom use, aimed primarily at chemical engineering students and instructors.

#### Scenario: Backend-facing docs describe one product identity
- **WHEN** a contributor reads `docs/README.md`, `docs/plant_backend_session_user_guide.md`, and the game-backend overview doc
- **THEN** all three describe the repo as an educational backend built on the existing simulation substrate rather than as only a generic control-simulation sandbox

### Requirement: Phase-1 Scope Remains A Narrow Continuous-Process Curriculum
Phase 1 SHALL remain limited to three teaching tracks grounded in current continuous-process capabilities: topology/separation basics, reactor/control basics, and recycle/process-design basics.

#### Scenario: Phase-1 scope names the starter tracks and defers larger systems
- **WHEN** phase-1 scope is reviewed in the docs
- **THEN** the three teaching tracks are named explicitly and batch-first gameplay, fouling/staffing, and multi-plant vertical integration are listed as deferred work

### Requirement: PlantBackendSession Is Positioned As Substrate
`PlantBackendSession` SHALL be described as a low-level runtime-editing and topology-management substrate for user-facing applications, not as the owner of progression or economics policy.

#### Scenario: Plant backend guide distinguishes substrate from future gameplay logic
- **WHEN** a contributor reads the plant-backend guide
- **THEN** the guide explains that user-facing gameplay or classroom orchestration composes `PlantBackendSession` instead of living inside it

### Requirement: Canonical Example Guidance Stays Separate From Gameplay Roadmapping
Repo-level gameplay framing SHALL not silently replace the current curated canonical example inventory with a broader scenario roadmap.

#### Scenario: Product positioning preserves the curated example catalog contract
- **WHEN** a contributor reads the repo framing docs alongside `docs/examples_catalog.md`
- **THEN** the docs present the canonical examples as the current substrate learning path and do not relabel the catalog as the phase-1 gameplay scenario list

## ADDED Requirements

### Requirement: Phase-1 Starter Catalog Contains Exactly Three Scenarios
The phase-1 gameplay catalog SHALL contain exactly `heater_flash_intro`, `reactor_control_intro`, and `recycle_purge_intro`.

#### Scenario: Catalog stays intentionally small
- **WHEN** the starter scenario catalog is inspected
- **THEN** it contains exactly the three phase-1 starter scenarios and no additional placeholder or deferred scenarios

### Requirement: Starter Scenarios Expose Typed Metadata
Each starter scenario SHALL declare its scenario id, title, teaching track, learning objectives, template provenance, available upgrade ids, success metrics, economics bindings, and victory conditions using typed contract objects.

#### Scenario: Scenario definition reveals what to build and teach
- **WHEN** an implementer inspects a starter scenario definition
- **THEN** the implementer can identify the scenario’s seed asset, what the learner is expected to learn, which upgrades are legal, and how completion is measured

### Requirement: Starter Scenarios Use Explicit Plant-Change Upgrades
Allowed upgrades in the starter catalog SHALL be represented as `UpgradeDefinition` records with fixed `base_cost`, prerequisite upgrade ids, and explicit plant changes such as instrumentation, line-installed equipment, topology edits, or documented parameter changes on the simulated plant.

#### Scenario: Hidden gameplay-only multipliers are rejected
- **WHEN** a starter scenario’s allowed upgrade list is reviewed
- **THEN** each upgrade category traces to an explicit plant change and none of the starter scenarios rely on hidden profit or purity multipliers

### Requirement: Victory Logic References Typed Success Metrics
Victory conditions in the starter catalog SHALL reference declared success metrics by id and SHALL not rely on prose-only completion rules.

#### Scenario: Victory conditions are machine-readable
- **WHEN** a contributor inspects a scenario’s success metrics and victory conditions
- **THEN** each victory condition references an existing metric id and defines a comparison, target value, and hold duration that can be evaluated without guessing

### Requirement: Scenario Economics Bindings Use A Shared Formula Shape
Each starter scenario SHALL declare exactly one `revenue` economics binding and one `utility_cost` economics binding using the shared phase-1 formula shape of `base_amount + sum(coefficient * metric_value)` over declared non-economics success metrics.

#### Scenario: Revenue and utility formulas are machine-readable
- **WHEN** a contributor inspects a scenario’s economics bindings
- **THEN** the contributor can identify the base amount, the metric ids used, and the coefficient for each term without guessing or reading gameplay-session code

### Requirement: Deferred Systems Stay Out Of The Starter Catalog
The starter catalog SHALL exclude batch-first gameplay, staffing/fouling systems, vertical integration, and campaign-wide cross-scenario progression.

#### Scenario: Scope review keeps later-phase ideas out of phase 1
- **WHEN** a contributor reviews the phase-1 starter catalog
- **THEN** those later-phase systems are absent from the catalog contract and remain explicit follow-on work

### Requirement: Starter Scenarios Preserve Seed Provenance
Each starter scenario SHALL record which existing example or process-definition asset its reusable template is derived from.

#### Scenario: Scenario/template provenance is auditable
- **WHEN** a contributor inspects the starter catalog and its template builders
- **THEN** the source asset for each scenario is named explicitly and the implementation does not rely on undocumented example copying

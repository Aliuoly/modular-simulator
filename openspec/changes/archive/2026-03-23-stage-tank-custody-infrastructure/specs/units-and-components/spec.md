## ADDED Requirements

### Requirement: Add-Process Unit Blueprints Remain Runtime-Authoritative
Phase-1 gameplay SHALL interpret `unit_blueprint` catalog records with `apply_kind = "add_process"` from their frozen runtime metadata rather than a slice-hardcoded default port schema, and SHALL remain general to each unit's declared inlet/outlet shape instead of imposing a broader single-inlet/single-outlet rule.

#### Scenario: Holding tank staging uses its real declared ports
- **WHEN** the module-private helper in `src/modular_simulation/gameplay/realtime_service.py` stages `place_holding_tank` from the shared sandbox catalog for `_install_unit()`
- **THEN** it resolves `unit_module = "modular_simulation.unit_processes.storage.holding_tank"`, `unit_type = "HoldingTank"`, and `constructor_payload = {}` from the catalog record
- **AND** it uses the unit's real ports `("inlet",)` and `("outlet",)` instead of forcing generic `("in",)` and `("out",)`

#### Scenario: Constructor payload remains part of runtime-authoritative unit metadata
- **WHEN** the same module-private realtime-service helper resolves `place_quality_control_lab` from the shared sandbox catalog for a non-public staging proof
- **THEN** it preserves `constructor_payload = {"minimum_purity_mol_fraction": 0.95}` exactly from the catalog record alongside `unit_module` and `unit_type`
- **AND** that constructor metadata remains runtime-authoritative even though no current start exposes the quality-control lab yet

#### Scenario: Runtime-authoritative unit metadata does not widen the live slice by itself
- **WHEN** contributors inspect the staged `add_process` runtime seam for cataloged units
- **THEN** catalog metadata remains valid even for items that no current start exposes yet
- **AND** the current live start allowlists and playable build-item lists remain unchanged until a later change explicitly widens them

#### Scenario: Runtime-authoritative placement does not freeze single-port topology as a general rule
- **WHEN** contributors inspect the staged `add_process` runtime seam beyond the current HoldingTank proof case
- **THEN** the seam derives whatever ports a cataloged unit implementation declares
- **AND** the current single-inlet/single-outlet HoldingTank proof case does not imply that future tank or unit-blueprint variants may only expose one inlet and one outlet

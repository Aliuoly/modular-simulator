## MODIFIED Requirements

### Requirement: Realism Boundary Is Frozen For This Slice
This change SHALL freeze a material-balance-first dynamic column boundary with two products, duty-limited condenser surrogate + reflux drum, an internal-only support-limited reboiler surrogate + bottoms sump, and constant-molar-overflow first closure.

#### Scenario: Initial thermodynamic basis stays reduced-order and explicit
- **WHEN** contributors inspect the stagewise-column closure assumptions in this slice
- **THEN** stage separation remains a constant-relative-volatility surrogate
- **AND** condenser and reboiler phase change remain fixed-latent-heat `Q/λ` surrogates
- **AND** reported temperatures remain proxy values rather than rigorous thermodynamic state predictions
- **AND** `StagewiseDistillationColumn` still has no property-package hook or enthalpy-based flash path in this slice
- **AND** the contract does not claim pressure-sensitive VLE, pressure-swing distillation, or superheat modeling.

### Requirement: Condenser/Reboiler Actuation Is Direct-Duty Service Coupled Into RHS
Condenser and reboiler actuation in this change SHALL be modeled as unit-local duty-request boundary fields coupled into the dynamic RHS.

#### Scenario: Utility actuation stays inventory-bounded and honesty-bounded
- **WHEN** condenser or reboiler actuation is configured
- **THEN** runtime behavior applies unit-local duty-request boundary fields into the monolithic stagewise RHS under the constant-molar-overflow slice
- **AND** when the retained internal support surrogate is not limiting, realized reboiler boilup follows the requested fixed-latent-heat `Q/λ` relation
- **AND** surrogate condensation and boilup rates remain bounded by available vapor or liquid support
- **AND** if requested reboiler duty implies more boilup than the retained internal support surrogate can support, realized boilup clips to the support-limited value
- **AND** realized reboiler duty clips with that realized boilup under the same fixed-latent-heat `Q/λ` basis
- **AND** duty service semantics do not create or destroy component moles.

## ADDED Requirements

### Requirement: Bottoms-Side Reboiler Closure Remains Internal-Only And Monolithic
The monolithic `StagewiseDistillationColumn` SHALL keep any stronger bottoms-side circulation closure unit-internal.

#### Scenario: Hidden circulation custody does not widen the public surface
- **WHEN** contributors inspect the bottoms-side closure used by `StagewiseDistillationColumn`
- **THEN** the bottoms sump remains the owner of liquid holdup
- **AND** any internal circulation draw to the retained reboiler pass remains hidden and unit-internal
- **AND** generated vapor returns to the bottom stage while unvaporized liquid returns internally to the sump
- **AND** bottoms product withdrawal remains an external withdrawal from sump-owned holdup
- **AND** the change does not add a public circulation port, public circulation actuator, connection-layer edge, or separate placeable reboiler unit.

#### Scenario: Stronger bottoms-side closure does not widen public model contracts
- **WHEN** contributors inspect the public/runtime-facing contract of `StagewiseDistillationColumn` after this slice
- **THEN** the change does not add a public circulation-related boundary field, session-visible circulation contract, or new public circulation observability promise
- **AND** runtime actuation authority still stays on the existing duty-request and liquid-routing seams already frozen for the monolithic unit.

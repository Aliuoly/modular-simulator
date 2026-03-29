## MODIFIED Requirements

### Requirement: Holding Tank Freezes Minimum Holdup Behavior
`HoldingTank` SHALL behave as a minimal physically transferable single-inlet single-outlet holdup unit owned by the simulation layer and advanced through the repo-standard differential process-model lifecycle.

#### Scenario: Stored inventory is conserved amount state
- **WHEN** the holding tank advances over a macro step
- **THEN** stored inventory advances as conserved differential amount state through the unit’s `ProcessModel.step()` / adaptive internal ODE solver path
- **AND** stored inventory updates from material-balance dynamics rather than from sampled instantaneous `molar_flow_rate` values
- **AND** the unit stores conserved holdup amount state rather than gameplay-owned placeholder inventory.

#### Scenario: Requested outlet demand is clipped by a near-empty depletion guard
- **WHEN** connection runtime applies requested outlet through-flow demand to the tank for its next process step
- **THEN** the tank clips depletion so conserved holdup never steps negative under that requested demand
- **AND** the depletion guard may retain a small positive numerical floor rather than exact zero to stay consistent with repo near-zero conventions
- **AND** downstream transferable outlet flow over a step never exceeds the moles withdrawable above the configured near-empty floor
- **AND** any positive near-zero outlet flow retained at that floor is observability regularization only unless backed by withdrawable holdup above the floor
- **AND** downstream propagation uses the realized outlet state produced by the tank model rather than the raw requested demand.

#### Scenario: Outlet state reflects the well-mixed bulk holdup
- **WHEN** stored holdup contains mixed material from one or more incoming transfers or has been clipped to the near-empty floor
- **THEN** the outlet stream state for the step reflects the current well-mixed bulk tank composition and temperature produced by the unit model
- **AND** realized component withdrawal follows that current mixed-bulk composition on the published species basis
- **AND** near-empty clipping may retain the previous bulk temperature/composition for continuity at the numerical floor
- **AND** that outlet state is a lumped single-bulk approximation for this slice rather than a geometry-, stratification-, or EOS-resolved vessel model
- **AND** the unit does not maintain parallel per-source inventory buckets in the live model.

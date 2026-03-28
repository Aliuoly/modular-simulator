## ADDED Requirements

### Requirement: Backend-Only Stagewise Proof Stays On Generic Session Surfaces
The repository SHALL support a backend-only stagewise causal proof assembled and stepped through the existing generic substrate session/runtime surfaces without widening gameplay or client contracts.

#### Scenario: Proof assembly uses the existing generic backend session surface
- **WHEN** a contributor assembles the bounded backend-only stagewise causal proof
- **THEN** the proof uses the existing generic substrate/session/runtime surface for process placement, runtime stepping, topology reads, and observability reads
- **AND** the implementation does not require a new Godot command, gameplay route, tutorial hook, or sandbox-only helper.

#### Scenario: Proof scope does not invent arbitrary unit-boundary mutation helpers
- **WHEN** the backend-only stagewise proof is reviewed for disturbance coverage
- **THEN** the proof demonstrates causality through already-supported unit-local duty-request seams, with any withdrawal seams treated as optional passive readouts only
- **AND** the proof does not silently widen `PlantBackendSession` with a new generic public helper for arbitrary process-unit boundary-state mutation.

### Requirement: Backend-Only Stagewise Proof Demonstrates Holdup-Driven Multi-Step Causality
The backend-only stagewise causal proof SHALL freeze explicit evidence requirements for top/bottom inventory response, disturbance-driven multi-step evolution, and honest demonstrated-vs-deferred reporting.

#### Scenario: Duty disturbances create multi-step top and bottom response
- **WHEN** the backend-only stagewise proof is executed over multiple runtime steps
- **THEN** condenser-duty and reboiler-duty disturbances create multi-step evolution in reflux-drum holdup, bottoms-sump holdup, and stage or product composition evidence
- **AND** the evidence is more than topology qualification or an instantaneous steady-state jump.

#### Scenario: Product withdrawals remain passive if no withdrawal seam is needed
- **WHEN** the backend-only stagewise proof is evaluated for disturbance coverage
- **THEN** passive product-flow readouts may be observed
- **AND** the proof does not make prescribed bottoms draw rate or withdrawal manipulation the centerpiece of the causal story.

#### Scenario: Proof output separates demonstrated claims from deferred realism claims
- **WHEN** the backend-only stagewise proof reports results
- **THEN** it explicitly distinguishes demonstrated holdup/material-balance evidence from deferred realism or integration claims
- **AND** it does not claim realistic pressure control, rigorous enthalpy-coupled thermal or temperature behavior, physical thermosyphon/pump-loop reboiler circulation, gameplay coupling, or generic controller-to-network auto-staging that this pack does not freeze.

#### Scenario: Any retained sump-to-reboiler surrogate remains internal-only
- **WHEN** the backend-only stagewise proof uses the current bottoms-sump-to-reboiler `Q/lambda` surrogate or a fallback internal circulation simplification
- **THEN** that behavior remains unit-internal rather than a connection-layer or public session seam
- **AND** the proof/report names the realism boundary explicitly and references follow-up `ModularSimulator-9tr.5.2` when the stronger circulation model is still deferred.

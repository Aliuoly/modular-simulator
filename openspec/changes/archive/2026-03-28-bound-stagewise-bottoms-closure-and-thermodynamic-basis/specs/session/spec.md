## MODIFIED Requirements

### Requirement: Backend-Only Stagewise Proof Demonstrates Holdup-Driven Multi-Step Causality
The backend-only stagewise causal proof SHALL freeze explicit evidence requirements for top/bottom inventory response, disturbance-driven multi-step evolution, and honest demonstrated-vs-deferred reporting.

#### Scenario: Any retained sump-to-reboiler surrogate remains internal-only and honesty-bounded
- **WHEN** the backend-only stagewise proof or any later runtime evidence describes the bottoms-side closure
- **THEN** any sump-to-reboiler circulation surrogate remains unit-internal rather than a connection-layer or public session seam
- **AND** if requested reboiler duty implies more boilup than the retained internal support surrogate can support, realized boilup and realized reboiler duty clip to the support-limited value under the current reduced-order `Q/λ` basis
- **AND** the proof or runtime report explicitly states that the current stagewise thermodynamic basis remains constant-relative-volatility, fixed-latent-heat, and proxy-temperature based with no property-package or enthalpy-flash hook
- **AND** it does not claim pressure-swing distillation, thermosyphon hydraulics, forced-circulation hydraulics, or superheat modeling that this pack does not freeze.

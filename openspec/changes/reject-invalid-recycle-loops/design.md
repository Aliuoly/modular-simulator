## Context

The repository already detects directed cycles in `Flowsheet._find_directed_cycle`, but compile validation only emits a warning that convergence handling is not enabled. That behavior was acceptable while the canonical recycle issue was mainly topological, but the open follow-up issue now requires the framework to reject recycle loops that do not include any usable pressure-boosting element. The parent change `define-canonical-hydraulic-solving-semantics` now establishes that pressure boost is line-owned hydraulics (not unit-owned), and the sibling change `canonicalize-hydraulic-junction-api` will provide the high-level API for line-installed pump configuration. This validation change must align with line-installed pump metadata and inherit the canonical network-owned and line-owned hydraulic ownership model.
## Goals / Non-Goals

**Goals:**
- Reject physically invalid recycle loops before `Flowsheet.run()` proceeds, aligned with the canonical network-owned hydraulic model from `define-canonical-hydraulic-solving-semantics`.
- Base the decision on compile-time topology and canonical line-installed pump/hydraulic metadata per the canonical semantics (not unit-owned pump behavior).
- Keep at least one curated recycle example valid under the new rule by using the high-level line-element API once `canonicalize-hydraulic-junction-api` lands.
- Produce error messages and tests that make the rejection actionable.

**Non-Goals:**
- Implement full recycle convergence solving or steady-state recycle iteration.
- Introduce a new compressor model distinct from the existing pump/pressure-boosting support.
- Expand this change into broader hydraulic optimization beyond recycle-loop validation.
- Extend this validation contract to lower-level connection/network APIs outside the high-level `Flowsheet` compiler.

## Decisions

1. Validate recycle viability during flowsheet compile rather than at runtime, constrained by the canonical hydraulic semantics established in `define-canonical-hydraulic-solving-semantics`.
    - Rationale: the invalid condition is structural and can be determined from the directed graph plus hydraulic edge metadata before simulation starts. The canonical semantics define which hydraulic configurations are physically valid, making compile-time enforcement sound.
    - Alternative considered: allow compilation and fail only after observing zero recycle flow. Rejected because it delays feedback and makes the user debug a topology that is already known to be invalid per the canonical model.

2. Treat a recycle loop as valid only when the loop includes supported line-installed pump boost with a strictly positive configured initial boost value at compile time, per the canonical line-owned hydraulic semantics.
    - Rationale: the documented issue is specifically that loops without usable compressor/pump boost are physically unviable, and mere metadata with zero configured boost would not fix that. The canonical semantics establish that pressure boost belongs to the line (not to a unit), so validation targets line-installed pump metadata.
    - Alternative considered: reject every cycle categorically. Rejected because the repository intentionally keeps a canonical recycle example and already has API support for pressure-boosted loop edges.

3. Reuse canonical line-installed pump metadata instead of reintroducing `Pump` wrapper-unit ownership in this proposal.
    - Rationale: the canonical semantics establish that pressure boost belongs to the connection line, and the sibling change `canonicalize-hydraulic-junction-api` removes wrapper-unit ownership. Recycle validation must enforce that canonical ownership model consistently.
    - Alternative considered: keep validation tied to the old `Pump` unit until later. Rejected because it would create contradictory canonical guidance across overlapping changes.

4. Inspect all directed cycles in the high-level `Flowsheet` graph and fail compilation if any one of them is invalid.
    - Rationale: a topology with one valid recycle loop and one invalid recycle loop is still unsafe to run, and checking only the first discovered cycle would make results traversal-order dependent.
    - Alternative considered: stop after the first detected cycle. Rejected because multi-cycle topologies would remain underspecified and harder to diagnose.

5. Raise a hard validation error that reports the offending cycle path(s) and the missing pressure-boost explanation.
    - Rationale: the user request explicitly asks the framework to FAIL or REJECT such configurations with a proper prompt.
    - Alternative considered: escalate the warning text without changing control flow. Rejected because it would still permit invalid simulations.

6. Keep the ammonia example as the curated proof path by installing positive pump boost on the recycle line once `canonicalize-hydraulic-junction-api` lands.
    - Rationale: the example currently demonstrates explicit recycle topology; updating it with a line-installed pump preserves curated coverage while remaining aligned with the canonical line-owned hydraulic model and the sibling API.
    - Alternative considered: remove the recycle example entirely. Rejected because the repository benefits from one advanced canonical recycle scenario.

7. Align curated example specs immediately with the canonical semantics, but defer code/example rewrites until `canonicalize-hydraulic-junction-api` provides the final public API.
    - Rationale: specs and migration guidance can adopt the canonical language now, but implementation of the curated ammonia example requires access to the stable high-level junction and line-element API.
    - Alternative considered: delay all updates until the sibling change lands. Rejected because spec alignment now ensures coherent guidance even before implementation.


## Risks / Trade-offs

- False-positive rejection if validation cannot correctly associate hydraulic boost metadata with cycle edges → Mitigation: implement the check from compiled connection/bootstrap data and cover both positive and negative cases with tests.
- The line-installed pump API lives in a sibling change `canonicalize-hydraulic-junction-api` → Mitigation: align validation specs immediately, coordinate hooks for validation infrastructure, and sequence code/example rewrites as a dependent task in this change after the sibling API lands.
- Terminology mismatch between the issue text ("compressor") and current implementation surface ("pump") → Mitigation: document the rule as a pressure-boosting element and explicitly scope the first implementation to supported positive line-installed pump boost per the canonical semantics.
- Example updates may change reported recycle ratios or product outputs → Mitigation: keep smoke tests focused on viability and topology expectations rather than brittle exact values.
- Multi-cycle validation could produce noisy errors if too many loops are reported at once → Mitigation: require deterministic reporting and allow the implementation to cap reporting after listing the invalid cycle paths needed for actionability.
- Coordinate example spec updates now with `canonicalize-hydraulic-junction-api` to ensure consistency, but defer actual code/example rewrites until the sibling API change lands → Mitigation: explicitly document that curated example rewrites are dependent downstream work sequenced after the junction/line-element API stabilizes.


## Migration Plan

1. Align curated example specs immediately with the canonical hydraulic semantics and line-installed pump ownership model.
2. Add compile-time recycle viability validation targeting line-installed pump metadata with positive configured boost per the canonical semantics.
3. Update example/spec guidance and validation error messaging to reference line-installed pump boost and the canonical hydraulic model.
4. Coordinate validation hooks and infrastructure so this change can consume the high-level line-element API once `canonicalize-hydraulic-junction-api` lands.
5. Once the sibling API change lands, update the curated ammonia recycle example code and docs to use line-installed pump boost on the recycle return path.
6. Add regression tests for invalid-loop rejection and curated-example success.
7. If unexpected downstream breakage appears, temporarily revert the validation gate and example changes together so documentation and runtime behavior stay consistent.

## Open Questions

- None. This proposal intentionally scopes validity to supported line-installed pump metadata with positive configured initial boost per the canonical semantics, and explicitly coordinates spec/migration updates now with code rewrites deferred until the sibling API lands.


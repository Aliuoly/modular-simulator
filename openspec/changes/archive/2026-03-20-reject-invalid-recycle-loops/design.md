## Context

The repository already detects directed cycles in `Flowsheet._find_directed_cycle`, but compile validation only emits a warning that convergence handling is not enabled. That behavior was acceptable while the canonical recycle issue was mainly topological, but the open follow-up issue now requires the framework to reject recycle loops that do not include any usable pressure-boosting element. The parent change `define-canonical-hydraulic-solving-semantics` now establishes that pressure boost is line-owned hydraulics (not unit-owned), and the sibling change `canonicalize-hydraulic-junction-api` will provide the canonical public API for line-installed pump configuration. This validation change must align with line-installed pump metadata and inherit the canonical network-owned and line-owned hydraulic ownership model. The shipped ammonia recycle example already satisfies the validation rule by using the high-level `PumpInstall` API on the recycle return path.
## Goals / Non-Goals

**Goals:**
- Reject physically invalid recycle loops before `Flowsheet.run()` proceeds, aligned with the canonical network-owned hydraulic model from `define-canonical-hydraulic-solving-semantics`.
- Base the decision on compile-time topology and canonical line-installed pump/hydraulic metadata per the canonical semantics (not unit-owned pump behavior).
- Keep at least one curated recycle example valid under the new rule. The shipped ammonia recycle example already satisfies this requirement via the high-level `PumpInstall` API on the recycle return path.
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

6. Keep the ammonia example as the curated proof path by having a positive pump boost (`PumpInstall`) installed on the recycle line.
    - Rationale: the example already demonstrates explicit recycle topology with a line-installed pump via the shipped `PumpInstall` API; the curated example is valid and covered by smoke tests, satisfying the canonical line-owned hydraulic model. Future migration to the final canonical public API from `canonicalize-hydraulic-junction-api` may refine naming or parameter conventions but does not invalidate the current shipped example.
    - Alternative considered: remove the recycle example entirely. Rejected because the repository benefits from one advanced canonical recycle scenario.

7. Align curated example specs and code immediately with the canonical semantics using the already-shipped `PumpInstall` high-level API.
    - Rationale: the ammonia recycle example is already updated and passing smoke tests, so no deferral is needed. The `canonicalize-hydraulic-junction-api` sibling may later refine the public API surface for line-element configuration, and this change explicitly documents that narrower migration path as a future concern rather than a blocking dependency.
    - Alternative considered: delay all updates until the sibling change lands. Rejected because the current shipped `PumpInstall` API already supports the recycle return path and the example is valid today.


## Risks / Trade-offs

- False-positive rejection if validation cannot correctly associate hydraulic boost metadata with cycle edges → Mitigation: implement the check from compiled connection/bootstrap data and cover both positive and negative cases with tests.
- The line-installed pump API lives in a sibling change `canonicalize-hydraulic-junction-api` → Mitigation: the shipped `PumpInstall` API already supports the recycle return path. Future refinements to the canonical public API surface from `canonicalize-hydraulic-junction-api` may require a narrow migration step, but no current validation or example logic is blocked.
- Terminology mismatch between the issue text ("compressor") and current implementation surface ("pump") → Mitigation: document the rule as a pressure-boosting element and explicitly scope the first implementation to supported positive line-installed pump boost per the canonical semantics.
- Example updates may change reported recycle ratios or product outputs → Mitigation: keep smoke tests focused on viability and topology expectations rather than brittle exact values.
- Multi-cycle validation could produce noisy errors if too many loops are reported at once → Mitigation: require deterministic reporting and allow the implementation to cap reporting after listing the invalid cycle paths needed for actionability.


## Migration Plan

1. Align curated example specs and code with the canonical hydraulic semantics and line-installed pump ownership model. The ammonia recycle example is already updated to use `PumpInstall` on the recycle return path.
2. Add compile-time recycle viability validation targeting line-installed pump metadata with positive configured boost per the canonical semantics.
3. Update example/spec guidance and validation error messaging to reference line-installed pump boost and the canonical hydraulic model.
4. Coordinate validation hooks and infrastructure so this change can consume refinements from the canonical line-element API once `canonicalize-hydraulic-junction-api` lands.
5. Add regression tests for invalid-loop rejection and curated-example success. The `test_curated_ammonia_recycle_example_smoke` test already provides smoke coverage for the shipped example.
6. If unexpected downstream breakage appears, temporarily revert the validation gate and example changes together so documentation and runtime behavior stay consistent.

## Open Questions

- None. This proposal intentionally scopes validity to supported line-installed pump metadata with positive configured initial boost per the canonical semantics. The curated ammonia recycle example is already shipped and passing smoke tests using the `PumpInstall` high-level API. Future refinement of the canonical public API surface from `canonicalize-hydraulic-junction-api` may require a narrow migration step for naming or parameter conventions, but no current work is deferred or blocked.

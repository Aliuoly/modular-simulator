## Why

The archived `rework-examples` change fixed recycle-loop topology wording, but the high-level flowsheet compiler still accepts recycle loops that have no usable pressure boost and therefore collapse into physically non-viable zero-flow behavior. The parent change `define-canonical-hydraulic-solving-semantics` now establishes that the canonical hydraulic closure is a network solve where pressure boost is line-owned (not unit-owned), and the sibling change `canonicalize-hydraulic-junction-api` will provide the canonical public API for specifying line-installed pump boost. This follow-up change aligns recycle validation with the canonical line-installed pump model using the already-shipped high-level API.

## What Changes

- Add compile-time validation on the high-level `Flowsheet` API that inspects all directed recycle loops and rejects any loop that lacks supported line-installed pump-based pressure boost with a strictly positive configured initial boost value, aligned with the canonical line-owned hydraulic semantics from `define-canonical-hydraulic-solving-semantics`.
- Require the validation error to identify the offending loop path(s), state that no supported positive pressure boost was found, and tell the user to add a pump/pressure-boosting stage on the recycle path using the canonical line-element API.
- The canonical ammonia recycle example already uses the shipped high-level `PumpInstall` API to install a line-installed pump (`recycle_pump`) on the recycle return path, satisfying the stricter validation rule. No rewrite is deferred; the example is valid and covered by smoke tests.
- Add regression coverage for invalid recycle rejection and for the curated recycle example path.

## Capabilities

### New Capabilities
- `recycle-loop-validation`: Define how the high-level `Flowsheet` compiler detects and rejects physically invalid recycle loops before simulation starts.

### Modified Capabilities
- `curated-flowsheet-examples`: Tighten recycle-example requirements so any canonical recycle loop includes an explicit recycle edge and a supported positive line-installed pump boost that keeps the loop physically viable. The shipped ammonia recycle example satisfies this requirement using `PumpInstall` on the recycle return path.

## Impact

- Affected code: `src/modular_simulation/flowsheet/flowsheet.py` and supporting hydraulic/topology helpers used during compile validation.
- Affected examples/docs: the ammonia recycle flowsheet under `examples/unit_process_flowsheet/` plus any docs that describe it as canonical behavior. The example is already updated and covered by `test_curated_ammonia_recycle_example_smoke`.
- Canonical semantics dependency: this change implements line-based recycle validation constrained by the canonical hydraulic semantics from `define-canonical-hydraulic-solving-semantics` (network-owned flows, line-installed pump ownership, hydraulics-first ordering).
- Sibling API dependency: this change uses the already-shipped `PumpInstall` high-level API for the curated example. Future migration to the final canonical public API surface from `canonicalize-hydraulic-junction-api` may refine naming or parameter conventions, but no code or example rewrite is blocked on that sibling change.
- Coordination impact: this change aligns with `canonicalize-hydraulic-junction-api` on recycle topology so both use line-installed pump ownership consistently.
- Affected tests: integration and validation coverage for recycle detection, rejection messaging, and curated example viability.

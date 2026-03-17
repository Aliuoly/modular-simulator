## Why

The archived `rework-examples` change fixed recycle-loop topology wording, but the high-level flowsheet compiler still accepts recycle loops that have no usable pressure boost and therefore collapse into physically non-viable zero-flow behavior. The parent change `define-canonical-hydraulic-solving-semantics` now establishes that the canonical hydraulic closure is a network solve where pressure boost is line-owned (not unit-owned), and the sibling change `canonicalize-hydraulic-junction-api` will provide the high-level API for specifying line-installed pump boost. This follow-up change must align recycle validation with the canonical line-installed pump model and the new high-level API.

## What Changes

- Add compile-time validation on the high-level `Flowsheet` API that inspects all directed recycle loops and rejects any loop that lacks supported line-installed pump-based pressure boost with a strictly positive configured initial boost value, aligned with the canonical line-owned hydraulic semantics from `define-canonical-hydraulic-solving-semantics`.
- Require the validation error to identify the offending loop path(s), state that no supported positive pressure boost was found, and tell the user to add a pump/pressure-boosting stage on the recycle path using the canonical line-element API.
- Update the canonical ammonia recycle example so it remains a valid recycle configuration under the stricter validation rule by using a line-installed pump on the recycle return path once the canonical junction/line API from `canonicalize-hydraulic-junction-api` lands.
- Align curated example specs immediately with the canonical line-owned hydraulic and network-solve semantics, but defer code/example rewrites until `canonicalize-hydraulic-junction-api` provides the final public API.
- Add regression coverage for invalid recycle rejection and for the curated recycle example path.

## Capabilities

### New Capabilities
- `recycle-loop-validation`: Define how the high-level `Flowsheet` compiler detects and rejects physically invalid recycle loops before simulation starts.

### Modified Capabilities
- `curated-flowsheet-examples`: Tighten recycle-example requirements so any canonical recycle loop includes an explicit recycle edge and a supported positive line-installed pump boost that keeps the loop physically viable.

## Impact

- Affected code: `src/modular_simulation/flowsheet/flowsheet.py` and supporting hydraulic/topology helpers used during compile validation.
- Affected examples/docs: the ammonia recycle flowsheet under `examples/unit_process_flowsheet/` plus any docs that describe it as canonical behavior.
- Canonical semantics dependency: this change implements line-based recycle validation constrained by the canonical hydraulic semantics from `define-canonical-hydraulic-solving-semantics` (network-owned flows, line-installed pump ownership, hydraulics-first ordering).
- Sibling API dependency: this change depends on `canonicalize-hydraulic-junction-api` for the final public API surface for line-installed pump configuration; spec updates and validation hooks align immediately, but code/example rewrites depend on the sibling API landing first.
- Coordination impact: this change aligns with `canonicalize-hydraulic-junction-api` on recycle topology so both use line-installed pump ownership consistently.
- Affected tests: integration and validation coverage for recycle detection, rejection messaging, and curated example viability.

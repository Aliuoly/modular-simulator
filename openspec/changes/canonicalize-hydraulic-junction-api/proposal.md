## Why

The current high-level `Flowsheet` API still exposes `Pump`, `Valve`, `Mixer`, and `Splitter` as unit-process models even though the canonical hydraulic semantics (defined in `define-canonical-hydraulic-solving-semantics`) establish that pressure boost/throttling are line-owned hydraulics, branch flow is network-owned, and junctions are topology nodes with one pressure unknown each. This mismatch leaks architectural bloat into the public API, obscures how flow is really solved, and blocks a clean topology-first surface for the eventual UI/game. The canonical semantics also formalize hydraulics-first runtime ordering and explicit node-pressure solving, making the need for a semantics-aligned high-level API urgent.

## What Changes

- **BREAKING** Remove `Pump`, `Valve`, `Mixer`, and `Splitter` from the supported high-level unit-process API and replace their supported use cases with junction topology plus line-installed hydraulic elements, inheriting the canonical network-owned branch flow and node-pressure semantics from `define-canonical-hydraulic-solving-semantics`.
- Add first-class high-level `Flowsheet` support for named junctions (as explicit hydraulic nodes with one pressure unknown per junction per the canonical semantics) and boundary sinks so mixing, splitting, recycle merge points, and product handoff are represented as topology nodes instead of pseudo-unit wrappers.
- Add a concrete ergonomic high-level line API centered on `Flowsheet.connect(...)` that accepts explicit nested line-element install configs and returns a structured line reference exposing the final line and actuator identifiers, without requiring direct `ConnectionNetwork` or low-level reconfiguration calls. Line-installed hydraulic elements (pump, valve, heat) remain the canonical owners of pressure boost and flow throttling per the canonical semantics.
- Define the canonical split behavior so outgoing branch flow remains hydraulic-owned per the canonical network-solve semantics, rather than driven by unit-level split-ratio state.
- Define immediate-removal migration behavior for stale imports, saved wrapper-unit payloads, and stale examples so failures are explicit and actionable rather than silent.
- Update curated examples, docs, and migration guidance to use junctions and line elements, including recycle examples that need pressure boost on the recycle edge, while ensuring that code/example rewrites depend on the full completion of this API change (including any compiled topology updates and public API stabilization).


## Capabilities

### New Capabilities
- `flowsheet-junction-line-api`: Define the canonical high-level API for junction topology and line-installed hydraulic elements, including removal of the wrapper unit models.

### Modified Capabilities
- `curated-flowsheet-examples`: Replace wrapper-unit examples with junction and line-element examples so the canonical catalog matches the new public API.

## Impact

- Affected code: `src/modular_simulation/flowsheet/flowsheet.py`, `src/modular_simulation/connection/topology/network.py`, `src/modular_simulation/connection/topology/topology.py`, runtime/topology junction handling, and any helper/config models used to describe line controls.
- Affected public API: `modular_simulation.unit_processes` exports and any high-level flowsheet construction examples using `Pump`, `Valve`, `Mixer`, or `Splitter`.
- Affected persistence/contracts: wrapper-unit save/load behavior, control-surface naming/contracts that currently mention `Pump` or `Valve`, and diagnostics for stale API use.
- Affected tests/examples: curated flowsheet examples, recycle examples, hydraulic-element/junction tests, import/API coverage, and persistence compatibility coverage.
- Canonical semantics dependency: this change implements the high-level API surface constrained by `define-canonical-hydraulic-solving-semantics`; all junction definitions, line-owned hydraulic elements, and runtime ordering follow the canonical node-pressure plus mass-balance semantics.
- Coordination impact: this change must align any pending proposal or example guidance (such as `reject-invalid-recycle-loops`) that still assumes the recycle pressure boost is represented as a `Pump` unit rather than a line-installed hydraulic element. Code and example rewrites depending on this API must be deferred until the public API, compiled topology changes, and validation infrastructure are complete.

## 1. High-Level Junction Topology

- [x] 1.1 Add first-class high-level `Flowsheet` support for defining named junctions with explicit inlet/outlet structure.
- [x] 1.2 Add high-level boundary sink support and extend endpoint normalization so feeds, units, junctions, and sinks all use one explicit endpoint syntax.
- [x] 1.3 Update the high-level compile path and `ConnectionNetwork` topology registration so flowsheet-defined junctions produce compiled topology junction nodes instead of fake process-unit wrappers.
- [x] 1.4 Ensure converging and diverging junction behavior uses junction state mixing plus hydraulic-owned branch-flow solving without unit-level split-ratio ownership.
- [x] 1.5 Add validation for duplicate junction IDs, duplicate port names, ambiguous bare endpoints, and missing required junction runtime state/data.

## 2. Ergonomic Line-Element API

- [x] 2.1 Extend the canonical high-level connection API so users can create a line and install pump, valve, or line-heat elements from one ergonomic flowsheet surface.
- [x] 2.2 Replace ambiguous scalar overlay arguments with explicit nested install configs and return a structured `LineReference` that exposes generated and explicit line/actuator identifiers.
- [x] 2.3 Implement deterministic default line geometry and identifier behavior, together with explicit override hooks needed for UI wiring, diagnostics, and runtime control.
- [x] 2.4 Enforce overlay rules in the high-level API: reject pump-plus-valve on one line, allow heat plus one hydraulic overlay, and surface clear configuration errors.
- [x] 2.5 Map the high-level API cleanly onto existing lower-level line attachment/runtime control infrastructure without requiring direct `ConnectionNetwork` mutation calls from users.

## 3. Remove Wrapper Units And Align Examples

- [x] 3.1 Remove `Pump`, `Valve`, `Mixer`, and `Splitter` from the canonical public unit-process surface and replace any remaining compatibility entrypoints with actionable migration guidance.
- [x] 3.2 Define and implement failure behavior for stale imports and saved wrapper-unit payloads, including actionable migration messages.
- [x] 3.3 Update control-surface and actuator-tag contracts that currently reference wrapper-unit ownership so they align with line-owned controls.
- [x] 3.4 Update curated examples, docs, and tutorials to use junctions, boundary sinks, and line-installed hydraulic elements instead of the removed wrapper units.
- [x] 3.5 Rework recycle example guidance so required recycle pressure boost is represented as a line-installed pump element rather than a `Pump` unit.

## 4. Verification

- [x] 4.1 Add regression tests for junction compilation and runtime behavior for both many-in/one-out and one-in/many-out topologies.
- [x] 4.2 Add an explicit regression for a single same-node many-in/many-out junction that verifies compile, directionality, and runtime state behavior.
- [x] 4.3 Add tests for high-level line-element installation that verify pump/valve/heat attachments and deterministic identifier behavior.
- [x] 4.4 Add regression coverage for invalid overlay combinations, duplicate IDs, generated actuator ID discovery, invalid feed/sink/junction directionality, ambiguous endpoints, and zero-inflow junction fallback behavior.
- [x] 4.5 Add regression coverage proving split behavior is hydraulic-owned and no canonical API path depends on zero-filled `Splitter.outlet_flows` placeholders or unit-level `split_ratios` for physical branch allocation.
- [x] 4.6 Add API/docs/persistence/import coverage confirming the removed wrapper-unit names are no longer part of the canonical high-level surface and that migration guidance points to junction and line-element replacements.

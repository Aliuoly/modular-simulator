## 1. High-Level Junction Topology

- [ ] 1.1 Add first-class high-level `Flowsheet` support for defining named junctions with explicit inlet/outlet structure.
- [ ] 1.2 Add high-level boundary sink support and extend endpoint normalization so feeds, units, junctions, and sinks all use one explicit endpoint syntax.
- [ ] 1.3 Update the high-level compile path and `ConnectionNetwork` topology registration so flowsheet-defined junctions produce compiled topology junction nodes instead of fake process-unit wrappers.
- [ ] 1.4 Ensure converging and diverging junction behavior uses junction state mixing plus hydraulic-owned branch-flow solving without unit-level split-ratio ownership.
- [ ] 1.5 Add validation for duplicate junction IDs, duplicate port names, ambiguous bare endpoints, and missing required junction runtime state/data.

## 2. Ergonomic Line-Element API

- [ ] 2.1 Extend the canonical high-level connection API so users can create a line and install pump, valve, or line-heat elements from one ergonomic flowsheet surface.
- [ ] 2.2 Replace ambiguous scalar overlay arguments with explicit nested install configs and return a structured `LineReference` that exposes generated and explicit line/actuator identifiers.
- [ ] 2.3 Implement deterministic default line geometry and identifier behavior, together with explicit override hooks needed for UI wiring, diagnostics, and runtime control.
- [ ] 2.4 Enforce overlay rules in the high-level API: reject pump-plus-valve on one line, allow heat plus one hydraulic overlay, and surface clear configuration errors.
- [ ] 2.5 Map the high-level API cleanly onto existing lower-level line attachment/runtime control infrastructure without requiring direct `ConnectionNetwork` mutation calls from users.

## 3. Remove Wrapper Units And Align Examples

- [ ] 3.1 Remove `Pump`, `Valve`, `Mixer`, and `Splitter` from the canonical public unit-process surface and replace any remaining compatibility entrypoints with actionable migration guidance.
- [ ] 3.2 Define and implement failure behavior for stale imports and saved wrapper-unit payloads, including actionable migration messages.
- [ ] 3.3 Update control-surface and actuator-tag contracts that currently reference wrapper-unit ownership so they align with line-owned controls.
- [ ] 3.4 Update curated examples, docs, and tutorials to use junctions, boundary sinks, and line-installed hydraulic elements instead of the removed wrapper units.
- [ ] 3.5 Rework recycle example guidance so required recycle pressure boost is represented as a line-installed pump element rather than a `Pump` unit.

## 4. Verification

- [ ] 4.1 Add regression tests for junction compilation and runtime behavior for both many-in/one-out and one-in/many-out topologies.
- [ ] 4.2 Add an explicit regression for a single same-node many-in/many-out junction that verifies compile, directionality, and runtime state behavior.
- [ ] 4.3 Add tests for high-level line-element installation that verify pump/valve/heat attachments and deterministic identifier behavior.
- [ ] 4.4 Add regression coverage for invalid overlay combinations, duplicate IDs, generated actuator ID discovery, invalid feed/sink/junction directionality, ambiguous endpoints, and zero-inflow junction fallback behavior.
- [ ] 4.5 Add regression coverage proving split behavior is hydraulic-owned and no canonical API path depends on zero-filled `Splitter.outlet_flows` placeholders or unit-level `split_ratios` for physical branch allocation.
- [ ] 4.6 Add API/docs/persistence/import coverage confirming the removed wrapper-unit names are no longer part of the canonical high-level surface and that migration guidance points to junction and line-element replacements.

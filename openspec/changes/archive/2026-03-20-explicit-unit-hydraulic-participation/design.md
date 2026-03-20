## Context

`openspec/specs/hydraulic-network-solving-semantics/spec.md` already states that unit processes participate in hydraulics through declared ports, boundary conditions, pressure/state coupling, and constitutive relations. In implementation, however, `Flowsheet` still builds unit hydraulic equations by inferring participation from available `UnitProcessPorts`, state metadata, and conventional field names.

Current compile behavior in `src/modular_simulation/flowsheet/flowsheet.py` includes:
- `_append_inferred_unit_hydraulic_relations()` as the umbrella path for unit hydraulic contributions.
- `_infer_unit_flow_balance_groups()` and `_infer_pairwise_unit_flow_balance_groups()` to guess which ports balance together.
- `_infer_unit_pressure_relations()` and `_infer_pairwise_unit_pressure_relations()` to guess pressure-coupled relations from state metadata.
- `_infer_unit_pressure_drop_value()` to translate a `pressure_drop` constant into a hydraulic relation.
- `_process_port_supports_direct_multi_edge_balancing()` currently hardcoded to reject all direct multi-edge balancing unless incidence count is 1.

The runtime layer in `src/modular_simulation/connection/runtime/thermo_coupling.py` already prefers compiled hydraulic lookup, but it still contains fallback paths for pressure and flow resolution when explicit hydraulic data is missing. Today the compiled lookup does not expose a dedicated participation marker, so runtime cannot reliably distinguish a pressure-coupled endpoint from a passive or non-participating endpoint when a lookup misses.

The user chose an **explicit-only** direction for this planning work. That means the change must not preserve heuristic inference as a compatibility bridge inside the canonical compile contract.

## Goals / Non-Goals

**Goals**
- Define an explicit declaration model for unit hydraulic participation that names:
  - which ports are hydraulically active,
  - which ports are passive,
  - which port groups require flow-balance equations,
  - which port pairs/groups impose pressure or constitutive relations,
  - when direct fan-in/fan-out is allowed because the unit declares balancing semantics.
- Replace compile-time heuristic inference with explicit declarations for canonical hydraulic participation.
- Align runtime pressure/flow lookup expectations with the explicit participation model so pressure-coupled ports remain deterministically resolvable.
- Make migration scope concrete enough that supported unit models can be updated intentionally rather than by accidental metadata pattern matching.

**Non-Goals**
- Introduce a second planning or tracking system outside OpenSpec.
- Rework the canonical junction/line API or recycle-loop semantics again.
- Preserve heuristic inference as a supported long-term fallback in the canonical compile path.
- Fully redesign every unit-process class in one undifferentiated refactor; this pack defines the contract and its bounded adoption work.

## Decisions

1. Introduce one explicit hydraulic declaration surface: `ProcessModel.hydraulic_participation`.
   - Each hydraulically participating unit model SHALL expose a `hydraulic_participation` property returning `HydraulicParticipationSpec`; units with no hydraulic participation return `None`.
   - The public property hook SHALL live on `src/modular_simulation/measurables/process_model.py` so both `ProcessModel` and `AlgebraicProcessModel` subclasses use the same declaration surface. `src/modular_simulation/thermodynamics/algebraic_process_model.py` may re-export helpers or narrow typing, but it must not become a second source of truth.
   - The contract types SHALL live in `src/modular_simulation/thermodynamics/hydraulic_participation.py`.
   - The frozen contract shape for this change is:
     - `HydraulicParticipationSpec(ports: Mapping[str, HydraulicPortSpec], balancing_groups: tuple[HydraulicBalancingGroupSpec, ...] = (), relations: tuple[HydraulicRelationSpec, ...] = (), element_couplings: tuple[HydraulicElementCouplingSpec, ...] = ())`
     - `HydraulicScalarStateRef(state: str)`
     - `HydraulicIndexedStateRef(state: str, index: int)`
     - `HydraulicStateRef = HydraulicScalarStateRef | HydraulicIndexedStateRef`
     - `HydraulicPortSpec(role: Literal["passive", "pressure_state", "fixed_pressure_anchor"], pressure_state: HydraulicStateRef | None = None, fixed_value_state: HydraulicStateRef | None = None)`
     - `HydraulicRelationSpec(name: str, kind: Literal["pressure_drop", "pressure_rise", "pressure_equal"], ports: tuple[str, ...], parameter_state: HydraulicStateRef | None = None)`
     - `HydraulicBalancingGroupSpec(name: str, ports: tuple[str, ...])`
     - `HydraulicElementCouplingSpec(name: str, port: str, ports: tuple[str, str])`
   - Operational meaning is fixed as follows:
     - `passive`: the port participates in topology only; compile adds no unit hydraulic equation for it; passive ports may not appear in any relation, balancing group, or element coupling.
     - `pressure_state`: the port maps to a solved hydraulic pressure via `pressure_state`; the port may participate in zero or more relation groups, at most one balancing group, and at most one element coupling.
     - `fixed_pressure_anchor`: the port maps to a solved hydraulic pressure via `pressure_state` and injects a known pressure boundary from `fixed_value_state`; anchored ports may participate in relation groups and at most one balancing group.
     - `balancing_groups` are the only source of unit flow-balance equations. For every declared balancing group with at least two connected ports, compile emits one signed linear flow-balance equation over the connected edges in that group. If a declared group has fewer than two connected ports, compile emits no equation for that group. Closed-component pruning may still remove redundant declared equations, but compile must not synthesize additional groups for single-path or paired-path units.
     - `pressure_equal` relations add explicit same-pressure constraints across the named non-passive ports.
     - `pressure_drop` and `pressure_rise` relations add affine pressure-offset constraints across exactly two named non-passive ports using a declared scalar `parameter_state`.
     - `element_couplings` preserve existing unit-owned hydraulic-element behavior. A declared element coupling names the canonical unit port whose existing `to_hydraulic_element(port)` surface supplies the edge-level pressure/flow law for the named port pair; if the unit also exposes `hydraulic_parameters_for_port(port)`, those parameters seed that coupling, otherwise the hydraulic element's `default_parameters(...)` remain the source.
   - State-reference validation is part of the contract, not implementation discretion:
     - `HydraulicScalarStateRef` may name a measurable scalar state field or a readable scalar property already used by the unit's port maps.
     - `HydraulicIndexedStateRef` may name a measurable vector/sequence state field plus a zero-based index; compile validates that the backing state exists, is indexable, and the referenced index is valid for the instantiated unit.
     - Shared scalar/property-backed state references are allowed for multiple ports (for example one flash-drum outlet pressure shared by both outlets, or distinct shortcut-distillation outlet pressures exposed through properties).
     - If two or more ports declare the same scalar/property-backed or indexed state reference, compile maps those ports to the same hydraulic pressure unknown; that shared unknown is the coupling mechanism, so compile does not invent an additional equality relation for identical refs.
     - Arbitrary string heuristics outside the declared state refs are forbidden in the canonical path.
   - Validation rules are frozen as part of the contract:
     - every port listed in `UnitProcessPorts` for a hydraulically participating unit must appear exactly once in `ports` (undeclared ports are invalid, not implicitly passive),
     - `pressure_state` is required for `pressure_state` and `fixed_pressure_anchor` ports and forbidden for `passive` ports,
     - `fixed_value_state` is required only for `fixed_pressure_anchor` ports and must resolve to a scalar value,
     - `pressure_drop` and `pressure_rise` relations require exactly two non-passive ports and a scalar `parameter_state`,
     - `pressure_equal` relations require two or more non-passive ports and forbid `parameter_state`,
     - each balancing group must name at least two non-passive ports,
     - a port may appear in at most one balancing group,
     - a non-passive port may appear in multiple relation groups,
     - a non-passive port may appear in at most one element coupling,
     - unknown ports, duplicate port declarations, duplicate group or coupling names, invalid state references, or conflicting passive/active overlap fail validation.
   - `hydraulic_participation=None` is valid only when the unit contributes no connected process endpoints to the compiled hydraulic topology. Any unit with one or more connected `UnitProcessPorts` endpoints must return a non-`None` declaration, even when all of those ports are intentionally passive.

2. Replace heuristic compile-time inference with explicit declaration consumption and publish a runtime-visible participation marker.
   - `Flowsheet._append_inferred_unit_hydraulic_relations`, `_infer_unit_flow_balance_groups`, `_infer_pairwise_unit_flow_balance_groups`, `_infer_unit_pressure_relations`, `_infer_pairwise_unit_pressure_relations`, and `_infer_unit_pressure_drop_value` should be replaced or reduced to explicit-declaration consumption.
   - `_resolve_hydraulic_anchor_pressure`, `_process_port_pressure`, `_pressure_attribute_candidates`, `_pressure_vector_attribute_candidates`, `_explicit_pressure_attribute_value`, `_explicit_pressure_vector_value`, `_field_was_explicitly_declared`, and `_pressure_attribute_was_explicitly_declared` should no longer decide canonical hydraulic participation from naming conventions; they may survive only as narrow helpers for resolving already-declared state references.
   - `HydraulicTopologyLookup` (or the equivalent compiled hydraulic lookup artifact) SHALL gain explicit endpoint participation metadata at minimum equivalent to:
     - `endpoint_role_by_endpoint: Mapping[tuple[str, str], Literal["passive", "pressure_state", "fixed_pressure_anchor"]]`
     - `balancing_group_name_by_endpoint: Mapping[tuple[str, str], str]`
   - That participation marker is the canonical handoff from compile to runtime: runtime uses it to distinguish pressure-coupled endpoints that must resolve through compiled lookup from passive or non-participating endpoints that may fall back to payload/transport/default data.
   - Missing declarations for units that need hydraulic participation should fail clearly at compile time instead of silently inferring behavior.
   - Compile-time diagnostics for missing or invalid declarations must name the unit type (and instance id when available), the offending port, group, relation, or coupling name, and the remediation (`add a hydraulic_participation declaration` or `insert an explicit junction` for unsupported direct multi-edge attachment).

3. Freeze the balancing contract for ordinary units, paired-path units, and direct multi-edge admission.
   - Single-path units that currently rely on inferred continuity (`1 inlet / 1 outlet`, `1 inlet / N outlets`, or `N inlets / 1 outlet`) must declare an explicit balancing group whenever the unit is expected to contribute a unit flow-balance equation.
   - Paired-path units such as `HeatExchanger` must declare one balancing group per independent hydraulic side; compile must not infer pairing from port names.
   - Direct unit-port fan-in or fan-out is legal only when the physical port with `incidence_count > 1` belongs to a declared balancing group and that group provides the unique local balance context for the directly attached edges.
   - Multiple edges may land on one declared port; unconnected ports in the same declared balancing group do not invalidate compile.
   - If a multi-edge physical port is passive, ungrouped, or would require combining ports from different balancing groups, compile fails and tells the model author to insert an explicit junction.
   - When a directly attached process port is admitted by a declared balancing group, compile suppresses the automatic per-node mass-balance equation that would otherwise be emitted for `incidence_count > 1`; the declared balancing group contributes the sole continuity equation for that local unit context. Junction nodes keep their own node mass-balance equations.

4. Freeze per-unit declaration semantics before migration begins.
   - `src/modular_simulation/unit_processes/flow/pump.py`
     - declare `inlet` and `outlet` as `pressure_state` ports using scalar refs for `inlet_pressure` and `outlet_pressure`,
     - add one balancing group over `(inlet, outlet)`,
     - add one `element_coupling` declared on `outlet` over `(inlet, outlet)` so the canonical pressure/flow law continues to come from `PumpHydraulicElement` plus `hydraulic_parameters_for_port("outlet")`,
     - do not add a separate affine `pressure_rise` relation for pump behavior.
   - `src/modular_simulation/unit_processes/flow/valve.py`
     - declare `inlet` and `outlet` as `pressure_state` ports using scalar refs for `inlet_pressure` and `outlet_pressure`,
     - add one balancing group over `(inlet, outlet)`,
     - add one `element_coupling` declared on `outlet` over `(inlet, outlet)` so the canonical pressure/flow law continues to come from `ValveHydraulicElement`,
     - do not represent valve behavior as a simple affine `pressure_drop(open_fraction)` relation because the current model pressure change remains flow-dependent.
   - `src/modular_simulation/unit_processes/thermal/heater_cooler.py`
     - declare `inlet` and `outlet` as `pressure_state` ports,
     - add one balancing group over `(inlet, outlet)`,
     - add one `pressure_drop` relation over `(inlet, outlet)` with scalar `parameter_state="pressure_drop"`.
   - `src/modular_simulation/unit_processes/reactors/conversion_reactor.py`
     - declare `inlet` and `outlet` as `pressure_state` ports,
     - add one balancing group over `(inlet, outlet)`,
     - add one `pressure_drop` relation over `(inlet, outlet)` with scalar `parameter_state="pressure_drop"`.
   - `src/modular_simulation/unit_processes/reactors/cstr.py` and `src/modular_simulation/unit_processes/reactors/pfr.py`
     - use the same `ProcessModel.hydraulic_participation` hook as every other unit,
     - declare `inlet` as `pressure_state` using scalar ref `inlet_pressure`,
     - declare `outlet` as `fixed_pressure_anchor` with scalar `pressure_state="pressure"` and scalar `fixed_value_state="pressure"`,
     - add one balancing group over `(inlet, outlet)`.
   - `src/modular_simulation/unit_processes/thermal/heat_exchanger.py`
     - declare `hot_inlet`, `hot_outlet`, `cold_inlet`, and `cold_outlet` as `pressure_state` ports,
     - add one balancing group for the hot side `(hot_inlet, hot_outlet)` and one for the cold side `(cold_inlet, cold_outlet)`,
     - add one `pressure_equal` relation for the hot side `(hot_inlet, hot_outlet)` and one for the cold side `(cold_inlet, cold_outlet)`,
     - no cross-side balancing group or cross-side pressure relation.
   - `src/modular_simulation/unit_processes/mixing/mixer.py`
     - declare each dynamic inlet with `HydraulicIndexedStateRef(state="inlet_pressures", index=<zero-based-port-index>)` and `outlet` with scalar ref `outlet_pressure`,
     - add one `pressure_equal` relation covering the full declared port set,
     - add one balancing group covering the same ports so direct fan-in is allowed only when the model declares it.
   - `src/modular_simulation/unit_processes/separation/splitter.py` and `src/modular_simulation/unit_processes/separation/component_separator.py`
     - declare the inlet and all outlets as `pressure_state` ports,
     - use `HydraulicIndexedStateRef(state="outlet_pressures", index=<zero-based-port-index>)` for splitter outlet pressures and scalar refs for component-separator outlet pressures,
     - add one balancing group covering the full port set,
     - add one `pressure_equal` relation covering the same ports.
   - `src/modular_simulation/unit_processes/separation/flash_drum.py`
     - declare `inlet` as `pressure_state` using scalar ref `inlet_pressure`,
     - declare `vapor_outlet` and `liquid_outlet` as `fixed_pressure_anchor` ports with shared scalar/property-backed ref `pressure_state="outlet_pressure"` and scalar `fixed_value_state="imposed_pressure"`,
     - add one balancing group over `(inlet, vapor_outlet, liquid_outlet)`,
     - do not add a redundant outlet-pressure equality relation because the shared anchored state already couples the outlet pressures.
   - `src/modular_simulation/unit_processes/separation/shortcut_distillation.py`
     - declare `inlet` as `pressure_state` using scalar ref `inlet_pressure`,
     - declare `distillate` as `fixed_pressure_anchor` with scalar/property-backed `pressure_state="condenser_pressure"` and scalar `fixed_value_state="condenser_pressure"`,
     - declare `bottoms` as `fixed_pressure_anchor` with scalar/property-backed `pressure_state="reboiler_pressure"` and scalar `fixed_value_state="reboiler_pressure"`,
     - add one balancing group over `(inlet, distillate, bottoms)`.

5. Keep runtime lookup deterministic and declaration-driven.
   - `src/modular_simulation/connection/runtime/thermo_coupling.py` should continue preferring compiled hydraulic lookup (`_resolve_endpoint_hydraulic_pressure`, `_resolve_hydraulic_pressure`, `_resolve_hydraulic_flow`, `_classify_local_node_flow`).
   - `_resolve_pressure()` may fall back to outlet payload pressure, transport-state pressure, or config default only when the compiled participation marker says the endpoint is passive or outside explicit hydraulic participation. If the marker says the endpoint is `pressure_state` or `fixed_pressure_anchor`, a missing compiled pressure mapping is an error, not a fallback case.
   - `_resolve_flow_rate()` may use solved hydraulic flow first and may retain payload / `0.0` fallback only for already-compiled non-participating output bindings or lines whose compiled lookup exists and resolves to zero flow. It must not mask a missing participating-port declaration or a missing compiled line-flow mapping for a declared hydraulic path.
   - `_resolve_endpoint_hydraulic_pressure()`, `_resolve_source_node_pressure()`, and `_classify_local_node_flow()` may walk compiled topology mappings only after declaration-driven compile succeeds; they must use the compiled participation marker rather than recreating unit participation by string heuristics.
   - `_resolve_binding_payload_outlet_condition()` may reconstruct output conditions from payload fields, but only as runtime transport/output degradation after successful compile, never as the source of truth for whether a unit port participates hydraulically.
   - If a unit requires hydraulic participation but lacks the explicit declaration, compile must fail before runtime is reached.

6. Make the compile trigger for explicit declarations measurable.
   - A unit requires explicit hydraulic participation whenever any of its `UnitProcessPorts` endpoints is connected into the hydraulic topology during compile.
   - Returning `None` is therefore legal only for units that are disconnected from the hydraulic graph or have no process hydraulic ports at all.
   - Canonical compile must not infer whether a connected unit "really meant" to participate from field names, metadata shape, or the presence of `to_hydraulic_element(...)`; connection into the hydraulic topology is the trigger, and the declaration then determines whether each connected port is passive, pressure-coupled, anchored, balanced, or element-coupled.

6. Treat migration unit-by-unit, with explicit verification coverage.
   - Supported units that currently rely on inferred fields such as `inlet_pressure`, `outlet_pressure`, or `pressure_drop` must be updated intentionally.
   - Tests must prove both the positive explicit cases and the negative missing-declaration/error-path cases.

## Risks / Trade-offs

- Explicit-only migration may touch several unit classes at once.
  - Mitigation: group implementation into waves, start with failing tests/spec cases, and name exact files in the task pack.
- Some current tests may encode inferred behavior rather than contractual behavior.
  - Mitigation: update tests to assert declarations and explicit compile/runtime outcomes, not metadata accidents.
- Runtime fallback pressure/flow logic could accidentally mask missing declarations.
  - Mitigation: add negative tests ensuring compile fails before runtime fallback becomes relevant for undeclared hydraulic participation.

## Verification Strategy

- TDD should lead behavior changes in compile-time participation validation.
- Required verification should include targeted commands such as:
  - `uv run pytest tests/connection/test_hydraulic_compile.py`
  - `uv run pytest tests/unit_process/test_flowsheet_validation.py -k "hydraulic or pressure or fan_in or fan_out"`
  - `uv run pytest tests/connection/test_thermo_coupling_runtime_store.py`
  - `uv run pytest tests/connection/test_pressure_inference.py`
  - `uv run pytest tests/unit_process/test_stream_propagation.py`
  - `uv run pytest tests/unit_process/test_layer3_coupling.py`
  - `uv run pytest tests/unit_process/test_hydraulic_elements.py`
  - `uv run pytest tests/unit_process/test_stream_port_io.py`
  - `uv run pytest tests/unit_process/test_asymmetric_ports.py`
  - `uv run pytest tests/unit_process/test_layer4_pump_valve.py`
  - `uv run pytest tests/unit_process/test_layer4_mixer_splitter.py`
  - `uv run pytest tests/unit_process/test_layer4_heater_cooler.py`
  - `uv run pytest tests/unit_process/test_layer4_heat_exchanger.py`
  - `uv run pytest tests/unit_process/test_layer4_component_separator.py`
  - `uv run pytest tests/unit_process/test_layer4_flash_drum.py`
  - `uv run pytest tests/unit_process/test_layer4_distillation.py`
  - `uv run pytest tests/unit_process/test_layer4_cstr.py`
  - `uv run pytest tests/unit_process/test_layer4_pfr.py`
  - `uv run pytest tests/unit_process/test_layer4_conversion_reactor.py`
- Expected evidence:
  - explicit declarations compile into deterministic hydraulic equations and lookup paths,
  - connected units without declarations fail before any heuristic fallback can keep them compiling,
  - identical declared state refs produce shared pressure unknowns where the contract says those ports share pressure,
  - missing/ambiguous declarations fail clearly with diagnostics naming the unit, offending port/group, and required remediation,
  - direct multi-edge balancing only succeeds when a unit declares that balancing contract,
  - runtime lookup continues using compiled hydraulic mappings plus the explicit participation marker rather than hidden inference,
  - `tests/connection/test_pressure_inference.py` continues passing because explicit declarations still produce the deterministic solved-pressure mappings that topology pressure lookup consumes.

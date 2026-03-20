## Wave 1 — Freeze the shared declaration contract and add red boundary tests (TDD first)

- [x] 1.1 Add `src/modular_simulation/thermodynamics/hydraulic_participation.py` with the frozen contract types from the design: `HydraulicParticipationSpec`, `HydraulicScalarStateRef`, `HydraulicIndexedStateRef`, `HydraulicPortSpec`, `HydraulicRelationSpec`, `HydraulicBalancingGroupSpec`, and `HydraulicElementCouplingSpec`.
- [x] 1.2 Add the single public `hydraulic_participation` property hook to `src/modular_simulation/measurables/process_model.py` and keep `src/modular_simulation/thermodynamics/algebraic_process_model.py` as an inheriting/re-exporting surface only; `CSTR`, `PFR`, and algebraic models must all consume the same property.
- [x] 1.3 Add red validation tests in `tests/connection/test_hydraulic_compile.py` covering these exact new contract boundaries:
  - a connected `HeaterCooler` with `hydraulic_participation=None` fails compile and names the unit plus the missing declaration remediation,
  - a declared `Mixer` or `Splitter` using an invalid indexed pressure ref fails and names the invalid state/index,
  - a declared `FlashDrum` with shared `outlet_pressure` refs maps `vapor_outlet` and `liquid_outlet` to the same compiled pressure unknown,
  - declared direct fan-in succeeds only for the admitted `Splitter.inlet` balancing-group case while undeclared direct fan-out at `HeaterCooler.outlet` still fails with the explicit-junction remediation,
  - invalid passive/relation/balancing/coupling overlap names the offending port/group/coupling.
- [x] 1.4 Add red/green compile behavior tests in `tests/unit_process/test_flowsheet_validation.py` covering: declared ordinary single-path balancing groups, paired-path balancing groups, fixed-pressure anchors, affine pressure relations, element-coupled pump/valve participation, and the rule that identical declared pressure refs share one hydraulic unknown instead of relying on inferred equality.

## Wave 2 — Enforce the explicit-only compile contract before unit migration green paths

- [x] 2.1 Refactor `src/modular_simulation/flowsheet/flowsheet.py` so `_append_inferred_unit_hydraulic_relations`, `_infer_unit_flow_balance_groups`, `_infer_pairwise_unit_flow_balance_groups`, `_infer_unit_pressure_relations`, `_infer_pairwise_unit_pressure_relations`, and `_infer_unit_pressure_drop_value` are replaced by consumption of `hydraulic_participation` declarations.
- [x] 2.2 Restrict `_resolve_hydraulic_anchor_pressure`, `_process_port_pressure`, `_pressure_attribute_candidates`, `_pressure_vector_attribute_candidates`, `_explicit_pressure_attribute_value`, `_explicit_pressure_vector_value`, `_field_was_explicitly_declared`, and `_pressure_attribute_was_explicitly_declared` to declared-state resolution only; they must not infer participation from field naming.
- [x] 2.3 Extend `src/modular_simulation/connection/hydraulics/hydraulic_compile.py` and `src/modular_simulation/connection/hydraulics/hydraulic_solver.py` so the compiled hydraulic artifact carries endpoint-role and balancing-group participation metadata, and so directly attached declared multi-edge unit ports suppress the automatic per-node mass-balance equation in favor of the declared balancing-group equation.
- [x] 2.4 Ensure missing/conflicting declaration diagnostics name the unit, the offending port/group/relation/coupling, and whether the remediation is to add `hydraulic_participation` or to insert an explicit junction.
- [x] 2.5 Verify the explicit-only compile gate before any unit migrations are considered complete:
  - `uv run pytest tests/connection/test_hydraulic_compile.py`
  - `uv run pytest tests/unit_process/test_flowsheet_validation.py -k "hydraulic or pressure or fan_in or fan_out"`

## Wave 3 — Migrate the single-path units with bounded semantics

- [x] 3.1 Add explicit declarations to `src/modular_simulation/unit_processes/flow/pump.py` and `src/modular_simulation/unit_processes/flow/valve.py` using one balancing group over `(inlet, outlet)` plus one `element_coupling` on `outlet`, then verify with:
  - `uv run pytest tests/unit_process/test_layer4_pump_valve.py`
  - `uv run pytest tests/unit_process/test_hydraulic_elements.py`
- [x] 3.2 Add explicit declarations to `src/modular_simulation/unit_processes/thermal/heater_cooler.py` and `src/modular_simulation/unit_processes/reactors/conversion_reactor.py` using one balancing group over `(inlet, outlet)` plus one affine `pressure_drop` relation, then verify with:
  - `uv run pytest tests/unit_process/test_layer4_heater_cooler.py`
  - `uv run pytest tests/unit_process/test_layer4_conversion_reactor.py`
- [x] 3.3 Add explicit declarations to `src/modular_simulation/unit_processes/reactors/cstr.py` and `src/modular_simulation/unit_processes/reactors/pfr.py` using the shared `ProcessModel.hydraulic_participation` hook, one balancing group over `(inlet, outlet)`, and `outlet=fixed_pressure_anchor(pressure)`, then verify with:
  - `uv run pytest tests/unit_process/test_layer4_cstr.py`
  - `uv run pytest tests/unit_process/test_layer4_pfr.py`

## Wave 4 — Migrate the paired-path and branching units with explicit state refs

- [x] 4.1 Add explicit declarations to `src/modular_simulation/unit_processes/thermal/heat_exchanger.py` using one balancing group plus one `pressure_equal` relation per side (`hot_inlet↔hot_outlet`, `cold_inlet↔cold_outlet`), then verify with:
  - `uv run pytest tests/unit_process/test_layer4_heat_exchanger.py`
  - `uv run pytest tests/unit_process/test_asymmetric_ports.py -k "heat_exchanger"`
- [x] 4.2 Add explicit declarations to `src/modular_simulation/unit_processes/mixing/mixer.py`, `src/modular_simulation/unit_processes/separation/splitter.py`, and `src/modular_simulation/unit_processes/separation/component_separator.py` using indexed pressure refs where needed, one balancing group over each model's active ports, and one `pressure_equal` relation over the same ports, then verify with:
  - `uv run pytest tests/unit_process/test_layer4_mixer_splitter.py`
  - `uv run pytest tests/unit_process/test_layer4_component_separator.py`
  - `uv run pytest tests/unit_process/test_asymmetric_ports.py -k "mixer or splitter or component_separator"`
- [x] 4.3 Add explicit declarations to `src/modular_simulation/unit_processes/separation/flash_drum.py` and `src/modular_simulation/unit_processes/separation/shortcut_distillation.py` using shared/property-backed scalar refs plus one balancing group over inlet and outlet ports, then verify with:
  - `uv run pytest tests/unit_process/test_layer4_flash_drum.py`
  - `uv run pytest tests/unit_process/test_layer4_distillation.py`
  - `uv run pytest tests/unit_process/test_asymmetric_ports.py -k "flash or distillation"`

## Wave 5 — Tighten runtime boundaries around the explicit compile contract

- [x] 5.1 Update `src/modular_simulation/connection/runtime/thermo_coupling.py` so `_resolve_pressure`, `_resolve_flow_rate`, `_resolve_endpoint_hydraulic_pressure`, `_resolve_source_node_pressure`, `_classify_local_node_flow`, and `_resolve_binding_payload_outlet_condition` consume the compiled participation marker: compiled hydraulic mappings remain first, pressure-coupled lookup misses become errors, shared declared refs remain shared at runtime, and payload/default fallback is allowed only for passive or non-participating endpoints.
- [x] 5.2 Add or update runtime regression coverage in `tests/connection/test_thermo_coupling_runtime_store.py`, `tests/connection/test_pressure_inference.py`, `tests/unit_process/test_stream_propagation.py`, and `tests/unit_process/test_layer3_coupling.py` covering these exact cases:
  - declared pressure-coupled endpoints fail instead of silently falling back when the compiled mapping is missing,
  - passive or non-participating endpoints still use payload/transport/default fallback legally,
  - shared flash-drum outlet pressure refs and declared reactor/heater endpoints propagate through runtime using the compiled participation marker rather than heuristics.
- [x] 5.3 Verify runtime behavior with:
  - `uv run pytest tests/connection/test_thermo_coupling_runtime_store.py`
  - `uv run pytest tests/connection/test_pressure_inference.py`
  - `uv run pytest tests/unit_process/test_stream_propagation.py`
  - `uv run pytest tests/unit_process/test_layer3_coupling.py`

## Wave 6 — Cross-cutting verification and scoped follow-up handling

- [x] 6.1 Run the full targeted matrix:
  - `uv run pytest tests/connection/test_hydraulic_compile.py`
  - `uv run pytest tests/connection/test_thermo_coupling_runtime_store.py`
  - `uv run pytest tests/connection/test_pressure_inference.py`
  - `uv run pytest tests/unit_process/test_flowsheet_validation.py -k "hydraulic or pressure or fan_in or fan_out"`
  - `uv run pytest tests/unit_process/test_hydraulic_elements.py`
  - `uv run pytest tests/unit_process/test_stream_port_io.py`
  - `uv run pytest tests/unit_process/test_asymmetric_ports.py`
  - `uv run pytest tests/unit_process/test_stream_propagation.py`
  - `uv run pytest tests/unit_process/test_layer3_coupling.py`
  - `uv run pytest tests/unit_process/test_layer4_pump_valve.py`
  - `uv run pytest tests/unit_process/test_layer4_heater_cooler.py`
  - `uv run pytest tests/unit_process/test_layer4_heat_exchanger.py`
  - `uv run pytest tests/unit_process/test_layer4_mixer_splitter.py`
  - `uv run pytest tests/unit_process/test_layer4_component_separator.py`
  - `uv run pytest tests/unit_process/test_layer4_flash_drum.py`
  - `uv run pytest tests/unit_process/test_layer4_distillation.py`
  - `uv run pytest tests/unit_process/test_layer4_cstr.py`
  - `uv run pytest tests/unit_process/test_layer4_pfr.py`
  - `uv run pytest tests/unit_process/test_layer4_conversion_reactor.py`
  - Expected evidence: explicit declarations drive compile and runtime behavior across every migrated unit family, including runtime propagation and coupling paths.
- [x] 6.2 If unrelated failures remain after Wave 6.1, stay in the project root and use this exact Beads workflow:
  - `bd show ModularSimulator-m3a --json` and confirm the parent bead is still `in_progress` before creating follow-up work,
  - `bd create --json "Investigate follow-up after explicit hydraulic participation migration" --deps "discovered-from:ModularSimulator-m3a" --description "Targeted verification after explicit hydraulic participation migration still fails in: <nodeids>"`,
  - Expected evidence: the created Beads item records the failing command and nodeids, remains explicitly linked back to `ModularSimulator-m3a`, and the explicit-only contract is not weakened inside this change.

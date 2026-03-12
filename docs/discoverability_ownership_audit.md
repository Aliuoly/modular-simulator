# Discoverability Ownership Audit

Rule source: `docs/discoverability_ownership_policy.md`

Contributor guidance:

- Read `docs/discoverability_ownership_policy.md` first for the rule and sanctioned exceptions.
- Use this audit to confirm whether a public surface stays KEEP or must MOVE to an owner.
- Prefer owner-led usage in docs and examples, for example `compiled.hydraulic.solve()` and `TransportRuntime.step(...)`.
- Keep sanctioned exceptions narrow, for example `create_property_package(...)`, `select_transport_model(...)`, and `update_lag_transport_state(...)`.

Audit method: grep module-level `def <public_name>(...)` candidates across `src/modular_simulation`, then classify only real public free-function surfaces (exported names or intentionally non-underscored module entrypoints). Negative-assertion strings, underscored helpers, class methods, and dunder namespace hooks such as module `__getattr__` were excluded.

## Summary

- `KEEP`: public factory, adapter, validator, deterministic kernel, or utility boundary that does not hide a subsystem workflow owner.
- `MOVE`: public ownerless workflow surface that should live on an obvious owner/facade.
- Task 11 fixed the one MOVE-now violation with an already-obvious owner: `cli/spec_workflow.apply_spec_delta` now lives behind `ModularCli.spec_apply(...)` via a private helper.

## MOVE

| Module | Symbols | Decision | Owner / target API | Rationale | Task 11 status |
| --- | --- | --- | --- | --- | --- |
| `cli.spec_workflow` | `apply_spec_delta` | MOVE | `ModularCli.spec_apply(...)` | CLI spec-apply is an owner-led workflow with queue/apply/rollback lifecycle already owned by `ModularCli`. Public module workflow surface violated policy. | **Fixed now**: symbol removed from public module surface; implementation is private helper only. |
| `connection.hydraulic_solver` | Index-map, unknown-assembly, residual-assembly, Jacobian-triplet, and solve workflow helpers | MOVE | `HydraulicSystemDefinition.build_index_maps(...)`, `.assemble_unknown_vector(...)`, residual assembly owner method, `.assemble_sparse_jacobian_triplet(...)`, `.solve(...)` | Solver workflow surfaces belong on the hydraulic system owner, not as discoverable loose module workflows. | Audit-only; owner methods already exist. |
| `connection.hydraulic_solver` | `triplet_to_dense` | MOVE | `SparseJacobianTriplet.to_dense()` | Dense conversion is owned by the triplet value object rather than a loose helper surface. | Audit-only; owner method already exists. |
| `connection.hydraulic_compile` | `compile_hydraulic_graph` | MOVE | `HydraulicCompileLifecycle.compile(...)` | Graph compilation is lifecycle orchestration and should be discovered from the compile lifecycle owner. | Audit-only; owner method already exists. |
| `connection.hydraulic_compile` | Solver-input build, solve, and valve-command apply workflow helpers for compiled graphs | MOVE | `CompiledHydraulicGraph.build_solver_inputs(...)`, `.solve(...)`, `.with_valve_commands(...)` | Compiled-graph workflow steps belong on the compiled graph owner rather than as ownerless module workflows. | Audit-only; owner methods already exist. |

## KEEP

| Module | Symbols | Decision | Rationale |
| --- | --- | --- | --- |
| `cli.spec_workflow` | `compile_spec_delta` | KEEP | Stateless diff compiler; used as the intentional read-only planning surface while `ModularCli.spec_apply(...)` owns the mutating workflow. |
| `thermodynamics.property_package` | `create_property_package` | KEEP | Explicitly sanctioned factory boundary for thermodynamic package construction. |
| `connection.transport` | `select_transport_model` | KEEP | Explicitly sanctioned model-selection factory boundary. |
| `connection.transport` | `update_lag_transport_state` | KEEP | Explicitly sanctioned low-level deterministic transport kernel beneath owner-led model/runtime APIs. |
| `thermodynamics.hydraulic_adapters` | `validate_outlet_port`, `pipe_hydraulic_element_for_outlet`, `default_pipe_hydraulic_parameters`, `default_pipe_resistance_for_unit`, `default_valve_hydraulic_parameters`, `default_pump_hydraulic_parameters` | KEEP | Explicitly sanctioned adapter namespace; small adapter/factory helpers rather than ownerless workflows. |
| `connection.junction_runtime` | `mix_junction_runtime_states` | KEEP | Stateless runtime mixing kernel over supplied topology/state mappings; no stronger owner is required for discoverability. |
| `connection.pressure_inference` | `build_topology_endpoint_context`, `describe_endpoint`, `resolve_edge_pressure_deltas_pa`, `hydrostatic_pressure_from_submerged_head_pa` | KEEP | Stateless topology/pressure inference helpers; cohesive inference namespace, not lifecycle orchestration. |
| `connection.error_catalog` | `revision_details`, `build_diagnostic_payload`, `diagnostic_value_error`, `diagnostic_runtime_error`, `extract_diagnostic_payload`, `coerce_diagnostic_payload` | KEEP | Diagnostic payload builders/coercers form a shared error-contract utility surface rather than an ownerless subsystem workflow. |
| `connection.hydraulic_compile` | `validate_hydraulic_graph`, `resolve_line_resistance`, `compile_valve_hydraulic_state`, `calculate_effective_valve_resistance` | KEEP | Stateless compile-time validators and kernels; they support owner-led compile flow without replacing it. |
| `connection.junction` | `mix_junction_state`, `mix_junction_state_with_enthalpy` | KEEP | Deterministic mixing kernels over explicit inputs; kept as shared physical calculation surfaces. |
| `connection.runtime_persistence` | `save_runtime_snapshot_contract`, `validate_runtime_snapshot_contract`, `restore_runtime_snapshot_contract`, `runtime_replay_state_hash`, `verify_runtime_replay_hashes` | KEEP | Snapshot-contract and replay-integrity utilities are intentionally stateless contract helpers. |
| `connection.unit_process_wiring` | `create_system_for_unit`, `create_subsystem_for_unit` | KEEP | Small wiring factories/adapters that construct subsystem wrappers from supplied units/context. |
| `connection.asymmetric_adapter` | `build_process_binding` | KEEP | Adapter/factory selector for process binding shapes; no hidden workflow lifecycle. |
| `connection.domain_contracts` | `validate_command_envelope` | KEEP | Public contract validation boundary for command envelopes. |
| `connection.material_models` | `select_density_model` | KEEP | Small stateless factory selector for density-model owners. |
| `connection.hydraulic_element` | `smooth_signed_quadratic_flow_term`, `smooth_signed_quadratic_flow_term_derivative` | KEEP | Pure mathematical kernels shared by hydraulic elements. |
| `thermodynamics.stream` | `default_inlet_map`, `default_outlet_map` | KEEP | Lightweight stream-port attribute map adapters. |
| `thermodynamics.species` | `resolve_species` | KEEP | Shared stateless resolution boundary for species lookup. |
| `utils.wrappers` | `day`, `per_day`, `hour`, `per_hour`, `minute`, `per_minute`, `second`, `per_second` | KEEP | Tiny unit-conversion convenience wrappers; module utility surface, not workflow orchestration. |
| `utils.metadata_extraction` | `extract_unique_metadata` | KEEP | Generic metadata extraction utility with no owner workflow semantics. |
| `utils.bounded_minimize` | `bounded_minimize` | KEEP | Standalone numerical utility kernel. |
| `utils.typing` | `unit_validator`, `unit_serializer`, `second_validator`, `second_serializer`, `per_second_validator`, `per_second_serializer` | KEEP | Public-by-name annotation helpers that support serialization/validation aliases, not workflows. |
| `framework.system` | `checkpoint_runtime_package_metadata`, `checkpoint_payload_checksum` | KEEP | Deterministic checkpoint metadata/checksum helpers shared by persistence code. |
| `plotting.time_series` | `triplets_to_arrays`, `plot_triplet_series`, `triplets_from_history` | KEEP | Standalone plotting/data-shaping utilities. |
| `components.abstract_component` | `get_component_class` | KEEP | Plugin/class-loader utility for component resolution. |
| `components.control_system.controllers.internal_model_controller` | `convert_calculation_to_str` | KEEP | Narrow normalization helper used to accept either type or string model references. |
| `measurables.control_surface_contract` | `get_control_surface_category`, `resolve_process_state_tag`, `validate_no_banned_setpoint_names`, `validate_runtime_actuator_binding`, `validate_controlled_view_has_only_physical_actuators` | KEEP | Shared control-surface contract classifiers/validators. |
| `app.main` | `inject_input` | KEEP | Local UI callback in application bootstrap; not a reusable subsystem workflow API. |

## Notes

- This audit intentionally keeps the sanctioned exceptions named in policy and inherited Task 11 guidance.
- The only Task 11 code movement was the CLI spec-apply surface because `ModularCli.spec_apply(...)` is the already-established owner and behavior had to stay byte-for-byte compatible at the CLI contract level.

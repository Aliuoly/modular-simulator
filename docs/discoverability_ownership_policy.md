# Discoverability Ownership Policy

## Ownership Rule

Public workflow APIs must live on a logical owner class or facade. The owner must hold the workflow context, data contract, or lifecycle role for that behavior.

Contributor guidance:

- Start with this policy for rule intent and allowed exceptions.
- Use `docs/discoverability_ownership_audit.md` to check module-level MOVE or KEEP status.
- Prefer owner-led calls in examples and reviews, for example `compiled.hydraulic.solve()`, `TransportRuntime.step(...)`, and `MacroCoupler.run(...)`.
- Use sanctioned exceptions only for their narrow role, for example `create_property_package(...)`, `select_transport_model(...)`, and `update_lag_transport_state(...)`.

Classification used across this repository:

1. **Owner methods or facades required**
   - Default for any public workflow operation that coordinates multiple steps, mutates lifecycle state, or is the primary entrypoint for a subsystem.
2. **Allowed private/internal free kernels**
   - Allowed for stateless, deterministic helper math and normalization logic that is not part of the public API.
   - These helpers should be private (`_name`) and scoped close to the owner that uses them.
3. **Sanctioned public factories or adapters**
   - Allowed only when the public function is intentionally a small constructor/factory selection point or an adapter namespace.
4. **Forbidden ownerless workflow functions**
   - Public module-level functions that run subsystem workflows without owner context are not allowed.

## Sanctioned Exceptions

The following public free-function surfaces are explicitly sanctioned:

- `create_property_package` in `thermodynamics/property_package.py`, sanctioned factory entrypoint.
- `select_transport_model` in `connection/transport.py`, sanctioned model-selection factory.
- `update_lag_transport_state` in `connection/transport.py`, sanctioned low-level stateless kernel.
- `thermodynamics.hydraulic_adapters` (`validate_outlet_port`, `pipe_hydraulic_element_for_outlet`, `default_pipe_hydraulic_parameters`, `default_pipe_resistance_for_unit`, `default_valve_hydraulic_parameters`, `default_pump_hydraulic_parameters`), sanctioned adapter namespace.

No additional public workflow free-function exceptions are approved unless this document is updated.

## Module Decisions

Decision key:

- `MOVE`: move public workflow free functions to an owner method or facade.
- `KEEP`: keep as sanctioned public factory or adapter surface, or keep as private/internal helper only.

| Current Symbol | Owner | Decision | Reason | Target API | Allowed Public Free Function? |
| --- | --- | --- | --- | --- | --- |
| Solver workflow helpers in `hydraulic_solver.py` (index mapping, unknown assembly, residual assembly, Jacobian triplet assembly, solve, and dense conversion) | `HydraulicSystemDefinition` (and `SparseJacobianTriplet` for dense conversion) | MOVE | Solver operations are core workflow on the system definition, current free-function surface is ownerless and hard to discover | `HydraulicSystemDefinition.build_index_maps()`, `assemble_unknown_vector()`, residual assembly owner method, `assemble_sparse_jacobian_triplet()`, `solve()`; `SparseJacobianTriplet.to_dense()` | No |
| Compile and compiled-graph workflow helpers in `hydraulic_compile.py` (compile, solver-input build, solve, valve-command apply) | `HydraulicCompileLifecycle` and `CompiledHydraulicGraph` | MOVE | Compile/apply/solve are graph lifecycle operations and should be discoverable from lifecycle or compiled graph owners | `HydraulicCompileLifecycle.compile(...)`; `CompiledHydraulicGraph.build_solver_inputs()`, `solve(...)`, `with_valve_commands(...)` | No |
| Macro coupling workflow helper in `connection_layer.py` | `MacroCoupler` | MOVE | Macro orchestration is a class-level coordination concern, not a standalone module workflow | `MacroCoupler.run(...)` | No |
| Transport runtime stepping workflow helper in `transport_runtime.py` | `TransportRuntime` | MOVE | Runtime stepping is the high-level transport workflow and needs owner discoverability | `TransportRuntime.step(...)` | No |
| Helper cluster (`_vector_from_state`, `_coerce_vector`, `_validate_composition`, `_validate_recovery`, `_safe_normalize`, `_extract_k_values`, `_fenske_n_min`, `_underwood_function`, `_solve_underwood_theta`, `_gilliland_n_actual`) in `shortcut_distillation.py` | `ShortcutDistillation` | MOVE (to class-owned private helpers) | Helpers are tightly coupled to one unit-process owner and should not live as a loose top-of-module cluster | Private methods or class-scoped private helpers under `ShortcutDistillation` | No |
| Helper cluster (`_as_finite_float`, `_round_composition`, `_normalize_composition`) in `property_package.py` | `PengRobinsonPackage` | MOVE (to class-owned private helpers) | Preprocessing helpers are package-owner concerns and should be local to `PengRobinsonPackage` behavior | Private static/class methods or class-scoped private helper namespace under `PengRobinsonPackage` | No |
| `create_property_package` in `property_package.py` | Thermodynamics package factory boundary | KEEP | Small sanctioned factory boundary for package construction | `create_property_package(...)` | Yes |
| `select_transport_model` in `transport.py` | Transport model factory boundary | KEEP | Small sanctioned model-selection factory boundary | `select_transport_model(...)` | Yes |
| `update_lag_transport_state` in `transport.py` | Low-level transport kernel boundary | KEEP | Stateless low-level kernel used by owner APIs and tests, kept as explicit exception | `update_lag_transport_state(...)` plus owner-led `MVPLagTransportModel.update(...)` and `TransportRuntime.step(...)` | Yes |
| Public adapter functions in `thermodynamics.hydraulic_adapters` | Adapter namespace | KEEP | Cohesive adapter/factory namespace, not ownerless workflow orchestration | `thermodynamics.hydraulic_adapters` function set | Yes |

## Enforcement Scope For This Plan

This policy is the rule source for Tasks 2-10 in `discoverability-consolidation-sweep`.

- `hydraulic_solver.py`, `hydraulic_compile.py`, `connection_layer.py`, and `transport_runtime.py` are workflow MOVE targets.
- `shortcut_distillation.py` and `property_package.py` are owner-locality MOVE targets for helper clusters.
- `transport.py` sanctioned APIs (`select_transport_model`, `update_lag_transport_state`) and `thermodynamics.hydraulic_adapters` remain KEEP exceptions.

# production-boundary-cleanup-sweep

> Recovered artifact on 2026-03-13 from OpenCode session history.
> Source sessions: `ses_3233beb7fffeBRNFkQUCCkZJ0r`, `ses_320834209ffefskhnb8oUnrri2`.
> This is **not guaranteed to be byte-for-byte identical** to the original lost file.
> It preserves the recoverable checklist, last known statuses, and dependency notes without changing the active boulder plan.

## Recovery notes

- Earliest recovered session message said: `23 implementation tasks + 4 final approvals`.
- Accessible session history preserves concrete titles/statuses for tasks `1-19` and the existence of approvals `F1-F4`.
- Exact original wording for task `5`, tasks `20-23`, and approvals `F1-F4` could not be recovered from available session history.
- Latest recovered checkpoint:
  - Completed/verified: `1, 2, 4, 6, 7, 8, 9, 10, 11, 12, 15, 16`
  - Pending/blocked: `3, 5, 13, 17, 18, 19, 14`

## Current reconciled status (2026-03-13)

- Recoverable and discoverability-compatible implementation scope is now complete and verified on current `main`.
- Completed/verified on current `main`: `1, 2, 3, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19`
- No remaining actionable blockers for the recoverable scope.
- Archival placeholders still unrecovered from session history: `5, 20, 21, 22, 23, F1, F2, F3, F4`.
- Those placeholders are not safe to invent and therefore do not represent unfinished verified implementation work.

## Recovered execution structure

- Wave 1: `{1-5, 15}`
- Wave 2: `{6-10, 16}`
- Wave 3: `{11-13}`
- Wave 4: `{17-19}`
- Final approvals: `{F1-F4}` after task `14`
- Recovered critical path: `1 -> 2 -> 15 -> 3 -> 5 -> 16 -> 17 -> 18 -> 14`

## TODOs

- [x] Task 1: Add public immutable connection query models
  - Recovered outputs: `NetworkProcessSpec`, `NetworkBoundarySpec`, `NetworkLineHydraulicConfig`

- [x] Task 2: Add deterministic `ConnectionNetwork` query methods
  - Recovered outputs: `list_process_specs`, `list_boundary_specs`, `list_connection_edges`, `list_line_hydraulic_configs`, `list_pending_valve_open_fractions`

- [x] Task 3: Migrate CLI spec workflow onto the public connection query surface
  - Reconciled status: completed on current `main`; the old blocking audit was contradictory and is treated as superseded.

- [x] Task 4: Replace runtime/control wiring private `ConnectionNetwork` reads with the public query surface

- [ ] Task 5: Exact original wording unrecovered from accessible session history
  - Recovered status: not started at the last checkpoint.
  - Recovered dependency signal: task 5 sat on the critical path between tasks 3 and 16.
  - Current status: archival placeholder only; exact scope remains unrecoverable and is not safe to invent.

- [x] Task 6: Broaden `ProcessModel` runtime I/O contract

- [x] Task 7: Align concrete unit-process classes with the `ProcessModel` contract
  - Recovered last status: conformance/no-op verification accepted.

- [x] Task 8: Remove `StreamPortIO` from production runtime typing

- [x] Task 9: Remove flowsheet/unit-wiring cast/getattr recovery

- [x] Task 10: Update test fallout from tasks 6-9

- [x] Task 11: Remove duplicate hydraulic contract symbols from `hydraulic_solver.py`

- [x] Task 12: Remove hydraulic `object` erasure from flowsheet and hydraulic producers

- [x] Task 13: Repair required downstream `HydraulicElementLike` cleanup files
  - Reconciled status: required examples/quickstarts compile cleanly and `HydraulicElementLike` is absent from current production/tests.

- [x] Task 14: Final verification wave
  - Reconciled status: completed with targeted pytest, example compilation, focused basedpyright, and package build verification.

- [x] Task 15: Add schema layer for connection/runtime ingress boundaries

- [x] Task 16: Wire typed schemas into runtime and CLI ingress paths

- [x] Task 17: Add quickstart ergonomics
  - Recovered outputs:
    - `ConnectionNetwork.from_single_process(...)`
    - `ConnectionRuntimeOrchestrator.for_system(...)`
  - Reconciled status: completed on current `main`.

- [x] Task 18: Migrate target dynamic API quickstarts to the new ergonomics
  - Reconciled status: completed on current `main`.

- [x] Task 19: Final quickstart scope/hygiene checks
  - Reconciled status: completed on current `main`.

- [ ] Task 20: Exact original wording unrecovered from accessible session history

- [ ] Task 21: Exact original wording unrecovered from accessible session history

- [ ] Task 22: Exact original wording unrecovered from accessible session history

- [ ] Task 23: Exact original wording unrecovered from accessible session history

## Final approvals

- [ ] F1: Exact original wording unrecovered from accessible session history
- [ ] F2: Exact original wording unrecovered from accessible session history
- [ ] F3: Exact original wording unrecovered from accessible session history
- [ ] F4: Exact original wording unrecovered from accessible session history

## Recovered checkpoint notes

- Task 3 was reported as implemented but blocked by a contradictory legacy audit script that flagged required public method names.
- Task 13 remained the main concrete code-fix blocker because required example files were malformed/corrupted.
- Task 17 was the next intended implementation lane after tasks 15/16 and the hydraulic cleanup wave.
- Task 10 had to be completed to properly verify task 16.

## Reconciled completion notes

- Typed ingress/schema validation is now present for reconfiguration request metadata/envelopes, live runtime snapshot payloads, and runtime checkpoint envelopes.
- `StreamPortIO` has been removed from current production typing paths in connection runtime/thermo coupling/flowsheet code, while the legacy thermodynamics protocol definition remains as a non-production reference.
- Required boundary-cleanup examples now compile successfully, including the previously blocked hydraulic/demo set.
- Verification completed on current `main`:
  - `PYTHONPATH=. uv run pytest tests/connection/test_runtime_mutation_contract.py tests/connection/test_runtime_persistence_contract.py tests/connection/test_network_api.py tests/connection/test_destructive_edit_policies.py tests/connection/test_domain_contracts.py tests/cli/test_cli_spec_diff_apply.py tests/integration/test_examples_smoke.py tests/unit_process/test_flowsheet_builder.py tests/unit_process/test_flowsheet_validation.py tests/unit_process/test_stream_port_io.py`
  - `uv run python -m py_compile examples/connection_layer/pump_causality_demo.py examples/simple_irreversible_energy_balance_system/three_tank_staged_connected_components.py examples/simple_irreversible_energy_balance_system/three_tank_staged_connected_control.py examples/dynamic_simulation_demos/coupled_three_tank_edge_valve_demo.py examples/dynamic_simulation_demos/coupled_cstr_flash_physical_actuator_demo.py examples/dynamic_simulation_demos/flash_backpressure_valve_demo.py examples/dynamic_api_cli/minimal_command_quickstart.py examples/dynamic_api_cli/minimal_spec_quickstart.py examples/dynamic_api_cli/minimal_control_loop_save_load.py`
  - `uv run basedpyright src/modular_simulation/connection/network.py src/modular_simulation/connection/runtime.py src/modular_simulation/connection/runtime_persistence.py src/modular_simulation/connection/domain_contracts.py src/modular_simulation/connection/runtime_snapshot_schema.py src/modular_simulation/connection/invariant_validator.py src/modular_simulation/connection/thermo_coupling.py src/modular_simulation/flowsheet/flowsheet.py src/modular_simulation/cli/commands.py src/modular_simulation/connection/process_stream_io.py`
  - `uv run --with build python -m build`

## Non-goals of this recovered artifact

- Do **not** treat this recovered file as the active boulder plan unless boulder state is explicitly updated later.
- Do **not** assume unrecovered tasks/approvals are safe to invent; recover more session evidence first if exact wording matters.

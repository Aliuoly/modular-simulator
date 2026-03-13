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

- [ ] Task 3: Migrate CLI spec workflow onto the public connection query surface
  - Recovered last status: functionally complete, but blocked by a contradictory audit in the old plan.

- [x] Task 4: Replace runtime/control wiring private `ConnectionNetwork` reads with the public query surface

- [ ] Task 5: Exact original wording unrecovered from accessible session history
  - Recovered status: not started at the last checkpoint.
  - Recovered dependency signal: task 5 sat on the critical path between tasks 3 and 16.

- [x] Task 6: Broaden `ProcessModel` runtime I/O contract

- [x] Task 7: Align concrete unit-process classes with the `ProcessModel` contract
  - Recovered last status: conformance/no-op verification accepted.

- [x] Task 8: Remove `StreamPortIO` from production runtime typing

- [x] Task 9: Remove flowsheet/unit-wiring cast/getattr recovery

- [x] Task 10: Update test fallout from tasks 6-9

- [x] Task 11: Remove duplicate hydraulic contract symbols from `hydraulic_solver.py`

- [x] Task 12: Remove hydraulic `object` erasure from flowsheet and hydraulic producers

- [ ] Task 13: Repair required downstream `HydraulicElementLike` cleanup files
  - Recovered last status: blocked by corrupted required example files.

- [ ] Task 14: Final verification wave
  - Recovered dependency note: depends on all implementation tasks.

- [x] Task 15: Add schema layer for connection/runtime ingress boundaries

- [x] Task 16: Wire typed schemas into runtime and CLI ingress paths

- [ ] Task 17: Add quickstart ergonomics
  - Recovered outputs:
    - `ConnectionNetwork.from_single_process(...)`
    - `ConnectionRuntimeOrchestrator.for_system(...)`
  - Recovered last status: active forward path.

- [ ] Task 18: Migrate target dynamic API quickstarts to the new ergonomics
  - Recovered dependency note: depends on task 17.

- [ ] Task 19: Final quickstart scope/hygiene checks
  - Recovered dependency note: depends on task 17.

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

## Non-goals of this recovered artifact

- Do **not** treat this recovered file as the active boulder plan unless boulder state is explicitly updated later.
- Do **not** assume unrecovered tasks/approvals are safe to invent; recover more session evidence first if exact wording matters.

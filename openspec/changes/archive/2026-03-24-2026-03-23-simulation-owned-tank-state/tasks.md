## Dependency gate

- [x] D0 Do not start implementation until this change pack is approved and the implementation packet is created in Beads from these tasks.

## Wave 1 — Write red tests for corrected ownership and minimal physical semantics first

- [x] 1.1 Replace the weak tank behavior contract in `tests/unit_process/test_layer4_holding_tank.py` with red tests for the corrected minimum semantics:
  - stored tank state advances as conserved holdup amount rather than sampled `molar_flow_rate` inventory,
  - the tank advances through the existing `ProcessModel.step()` / ODE path rather than a macrostep-only custom update,
  - depletion guards prevent negative holdup under requested outlet demand using a small positive near-empty floor,
  - outlet composition/temperature reflect the current well-mixed bulk state, and near-empty clipping retains the previous bulk state.
- [x] 1.2 Add focused red runtime-coupling tests under `tests/connection/` (prefer extending `tests/connection/test_thermo_coupling_runtime_store.py`; add one new file only if needed) for the substrate-owned boundary-application seam:
  - canonical hydraulic/runtime flow produces a requested outlet-demand boundary for conserved-holdup units,
  - runtime continues to apply inlet state plus the new requested outlet-demand boundary without gameplay bookkeeping,
  - downstream propagated transfer and snapshots use the tank model’s realized outlet condition rather than the raw requested demand.
- [x] 1.3 Extend `tests/connection/test_connected_plant_orchestrator.py` with a red lifecycle guard:
  - connected-plant phase order remains the existing repo order,
  - `HoldingTank` continues to advance through `subsystem_process_step` / `process_model.step(duration)` rather than a special post-hydraulic integrator,
  - the new runtime work applies requested outlet demand into that existing lifecycle instead of double-stepping the tank.
- [x] 1.4 Extend `tests/connection/test_connection_runtime_sequence.py` with a red runtime-sequence guard:
  - `CONNECTED_PLANT_PHASE_ORDER` remains unchanged,
  - runtime coupling latches requested outlet demand during `connection_runtime_coupling` for consumption on the next macro step’s `subsystem_process_step`,
  - implementation does not introduce same-step hydraulic-to-holdup closure by silently moving tank advancement to another phase.
- [x] 1.5 Extend `tests/connection/test_network_api.py` and `tests/cli/test_backend_session.py` with red observability guards:
  - top-level observability keys remain exactly `schema`, `graph_revision`, `runtime`, `queue`, and `observables`,
  - `observables.process_state_values` is additive and numeric,
  - tank/process keys include at minimum `<process_id>/holdup_total_mol`, `<process_id>/outlet_flow_mol_s`, `<process_id>/bulk_temperature_K`, and `<process_id>/mole_fraction/<species_id>`.
  - prove `process_state_values` is projected from substrate runtime state rather than gameplay leftovers or persistence payload dumping,
  - prove near-empty snapshots retain bulk temperature/composition keys and that any clipped near-zero flow is observability regularization only, not authorization for extra transfer.
- [x] 1.6 Add a red persistence round-trip contract in `tests/connection/test_runtime_persistence_contract.py`:
  - authoritative conserved tank state survives checkpoint/export/restore,
  - restored tank state is not rebuilt from gameplay mirrors or lossy observability payloads,
  - restored runtime state reproduces the same authoritative process-state basis used for later observability reads.
- [x] 1.7 Delete or replace `tests/gameplay/test_tank_custody.py` with a focused ownership-boundary regression (new file only if needed):
  - gameplay no longer owns mirrored tank conserved inventory or mixed thermo state,
  - no new public session/API/UI tank surfaces are introduced,
  - any remaining gameplay-side tank metadata is explicitly non-physical.
- [x] 1.8 Keep existing unchanged-surface guards green in:
  - `tests/gameplay/test_realtime_game_service.py`
  - `tests/gameplay/test_sandbox_catalog.py`
  - `tests/gameplay/test_start_catalog.py`
  - `tests/gameplay/test_sandbox_session.py`
  - Required proof: `place_holding_tank` remains unsupported on current starts and `SUPPORTED_BUILD_ITEM_IDS` remains unchanged.
- [x] 1.9 Run the red boundary:
  - `uv run pytest tests/unit_process/test_layer4_holding_tank.py`
  - `uv run pytest tests/connection/test_connected_plant_orchestrator.py`
  - `uv run pytest tests/connection/test_connection_runtime_sequence.py`
  - `uv run pytest tests/connection/test_network_api.py tests/cli/test_backend_session.py`
  - `uv run pytest tests/connection/test_thermo_coupling_runtime_store.py`
  - `uv run pytest tests/connection/test_runtime_persistence_contract.py`
  - `uv run pytest tests/gameplay/test_tank_custody.py` (or its ownership-boundary replacement if renamed)
  - `uv run pytest tests/gameplay/test_realtime_game_service.py tests/gameplay/test_sandbox_catalog.py tests/gameplay/test_start_catalog.py tests/gameplay/test_sandbox_session.py`
  - Expected evidence: corrected ownership/physics tests fail before implementation exists, while unchanged live-slice guards still describe the frozen current slice.

## Wave 2 — Implement the substrate-owned tank state and runtime seam

- [x] 2.1 Replace the nonphysical tank model in `src/modular_simulation/unit_processes/storage/holding_tank.py` with the minimum corrected semantics frozen in `design.md`:
  - convert the tank to the repo-standard differential process-model / ODE lifecycle,
  - conserved holdup amount state,
  - well-mixed bulk outlet composition/temperature,
  - near-empty depletion guard / numerical floor,
  - no flow-rate-as-inventory storage.
- [x] 2.2 Add the substrate-owned boundary-application seam in the connection runtime, preferring the existing runtime binding path over gameplay workarounds:
  - inspect and update `src/modular_simulation/connection/runtime/process_stream_io.py`
  - update `src/modular_simulation/connection/runtime/runtime.py`
  - update `src/modular_simulation/connection/runtime/thermo_coupling.py`
  - if needed, update `src/modular_simulation/connection/runtime/connected_plant_orchestrator.py` only to preserve the existing lifecycle while adding requested outlet-demand boundary application,
  - freeze one concrete seam that applies canonical inlet state plus per-outlet requested through-flow demand into the tank’s existing process-model lifecycle.
- [x] 2.3 Extend substrate observability without breaking the frozen top-level envelope:
  - update `src/modular_simulation/connection/topology/network.py`
  - update `src/modular_simulation/connection/runtime/runtime.py`
  - update `src/modular_simulation/connection/runtime/connected_plant_orchestrator.py` only if needed to expose the tank model’s realized state after process stepping
  - keep `src/modular_simulation/cli/backend_session.py` as a policy-free forwarder unless signature changes are truly required,
  - implement the near-empty observability policy: retain bulk temperature/composition keys and report clipped near-zero outlet flow using the previous bulk state when the tank is clipped to its numerical floor.
- [x] 2.4 Make conserved tank state checkpoint-restorable through the runtime-owned process-state path:
  - inspect and update `src/modular_simulation/connection/runtime/runtime_persistence.py` and any adjacent export/import helpers as needed,
  - ensure checkpoint/export/restore round-trips the authoritative conserved tank state rather than rebuilding it from gameplay leftovers.
- [x] 2.5 Remove the gameplay-owned physical tank mirror:
  - delete or sharply narrow `src/modular_simulation/gameplay/tank_custody.py`,
  - do not replace it with another gameplay-owned conserved inventory helper,
  - if any residual gameplay metadata remains, keep it explicitly non-physical and non-public.
- [x] 2.6 Do **not** widen the live slice in this wave:
  - do not change `SUPPORTED_BUILD_ITEM_IDS`,
  - do not add `place_holding_tank` to any current start,
  - do not add public tank/session/API commands,
  - do not fold `_resolve_unit_metadata()` error hardening into this pack unless the OpenSpec boundary is updated first.

## Wave 3 — Prove the corrected substrate contract and unchanged live slice

- [x] 3.1 Make the corrected unit-process and runtime tests pass with substrate-owned tank state and runtime-owned transfer updates.
- [x] 3.2 Re-run the observability/public-surface tests until they pass with additive `process_state_values` and the unchanged top-level envelope:
  - `uv run pytest tests/connection/test_network_api.py`
  - `uv run pytest tests/cli/test_backend_session.py`
  - `uv run pytest tests/connection/test_thermo_coupling_runtime_store.py`
- [x] 3.3 Re-run the connected-plant ordering guard:
  - `uv run pytest tests/connection/test_connected_plant_orchestrator.py`
  - `uv run pytest tests/connection/test_connection_runtime_sequence.py`
  - Expected evidence: `HoldingTank` remains on the existing unit-process lifecycle, runtime latches requested outlet demand for the next macro step, and implementation does not add a second state integrator.
- [x] 3.4 Re-run unchanged live-slice guards:
  - `uv run pytest tests/gameplay/test_tank_custody.py` (or its ownership-boundary replacement if renamed)
  - `uv run pytest tests/gameplay/test_realtime_game_service.py`
  - `uv run pytest tests/gameplay/test_sandbox_catalog.py tests/gameplay/test_start_catalog.py tests/gameplay/test_sandbox_session.py`
  - Expected evidence: tank ownership moved into the substrate without widening the current playable slice.
- [x] 3.5 Verify conserved tank state round-trip behavior through runtime persistence:
  - `uv run pytest tests/connection/test_runtime_persistence_contract.py`

## Wave 4 — Sync live specs and enforce review before closure

- [x] 4.1 Sync the implemented ownership and observability changes into:
  - `openspec/specs/session/spec.md`
  - `openspec/specs/observability/spec.md`
  - `openspec/specs/units-and-components/spec.md`
  - `openspec/specs/connection/spec.md`
- [x] 4.2 Do **not** update `openspec/specs/economics/spec.md`, `openspec/specs/client-godot/spec.md`, or the stale broad gas-first pack as part of this change unless implementation evidence proves this change boundary was wrong and the pack is revised first.
- [x] 4.3 Run the final verification matrix:
  - `uv run pytest tests/unit_process/test_layer4_holding_tank.py`
  - `uv run pytest tests/connection/test_connected_plant_orchestrator.py`
  - `uv run pytest tests/connection/test_connection_runtime_sequence.py`
  - `uv run pytest tests/connection/test_network_api.py`
  - `uv run pytest tests/cli/test_backend_session.py`
  - `uv run pytest tests/connection/test_thermo_coupling_runtime_store.py`
  - `uv run pytest tests/gameplay/test_tank_custody.py` (or its ownership-boundary replacement if renamed)
  - `uv run pytest tests/gameplay/test_realtime_game_service.py`
  - `uv run pytest tests/gameplay/test_sandbox_catalog.py tests/gameplay/test_start_catalog.py tests/gameplay/test_sandbox_session.py`
  - `uv run pytest tests/connection/test_runtime_persistence_contract.py`
- [x] 4.4 Before closure, require independent implementation review by `hybrid-code-reviewer` and `simulation-advisor` in parallel.
- [x] 4.5 Expected final evidence:
  - no gameplay-owned mirrored tank inventory remains authoritative,
  - `HoldingTank` stores conserved holdup amount and advances through the repo-standard ODE/process-model path,
  - runtime coupling applies canonical requested outlet demand and downstream propagation / snapshots / observability use the tank model’s realized outlet state,
  - public observability keeps the exact top-level envelope and adds nested `process_state_values`,
  - `place_holding_tank` remains unavailable on all current starts,
  - direct ej7 work can now depend on a stable tank owner boundary instead of `4fm`’s staged placeholder semantics.

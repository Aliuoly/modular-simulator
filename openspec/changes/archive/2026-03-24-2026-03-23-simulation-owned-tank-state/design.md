## Context

- `src/modular_simulation/gameplay/tank_custody.py` currently stores per-tank aggregate inventory keyed by holding-tank `process_id` plus boundary-route assignments keyed by boundary id. It initializes and mixes `total_mol` from `stream["molar_flow_rate"]`, so gameplay is currently mirroring physical inventory with the wrong units.
- `src/modular_simulation/unit_processes/storage/holding_tank.py` is not physically acceptable for live tank semantics. Its `step(dt)` drains the full step-start holdup each step (`outlet_flow = holdup_start / dt_safe`) and then overwrites `_holdup_mol` with `inlet_flow * dt` instead of net-advancing conserved inventory.
- `openspec/specs/session/spec.md` currently contains both `Higher Layers Consume Substrate-Owned Observability Reads` and `Internal Tank-Custody Primitives Remain Session-Owned And Non-Public`, which is a live contradiction under the user’s clarified ownership rule.
- `openspec/specs/observability/spec.md` already defines observability as its own capability domain. The public top-level snapshot envelope is frozen to `schema`, `graph_revision`, `runtime`, `queue`, and `observables`.
- `src/modular_simulation/connection/topology/network.py#get_observability_snapshot()` and `src/modular_simulation/cli/backend_session.py#get_observability_snapshot()` already implement that substrate-owned read model. Current tests freeze the exact top-level key set, but do not freeze the nested `observables` groups as exhaustive.
- Current gameplay runtime composition in `src/modular_simulation/gameplay/start_runtime.py` is topology-only. It creates a bare `ConnectionNetwork()` plus boundary sources/sinks and does not bind real process instances into `ConnectionRuntimeOrchestrator`.
- The repo already has a substrate-owned runtime binding seam in `src/modular_simulation/flowsheet/flowsheet.py`: `ConnectionRuntimeOrchestrator.bind_stream_port_ios(...)` binds real unit instances that implement `ProcessStreamIO`.
- Current runtime coupling in `src/modular_simulation/connection/runtime/thermo_coupling.py` can apply inlet `StreamData`, resolve outlet conditions, and record inlet/outlet `PortCondition` snapshots, but it does not yet freeze how conserved internal process state is advanced from canonical solved transfers.
- `src/modular_simulation/connection/runtime/runtime_persistence.py` already persists generic `process_runtime_state`, so the substrate already has a persistence-level place for per-process state even though the public observability contract does not expose it yet.
- `ModularSimulator-ej7` still owns the later live gas-starter rewrite and public tank-facing gameplay behavior. `ej7.1` is the correct precondition item because ej7 should not freeze against the current gameplay-owned tank mirror or the current nonphysical tank implementation.

## Goals / Non-Goals

**Goals**
- Freeze simulation-owned minimal tank semantics before ej7 depends on tanks.
- Replace gameplay-owned mirrored tank inventory with substrate-owned conserved holdup state.
- Define the minimum connection/runtime-owned boundary-application seam that supplies canonical inlet conditions and requested outlet demand to conserved-state units.
- Add a substrate-owned observability read model for tank/process state without changing the frozen top-level snapshot envelope.
- Keep the current live playable slice unchanged while this corrective substrate contract is established.

**Non-Goals**
- Do not rewrite the live sandbox into the gas-first starter here.
- Do not add public `tank_id` commands, tank UI, or player-facing routing mechanics here.
- Do not widen `SUPPORTED_BUILD_ITEM_IDS`, start allowlists, or public session/API contracts here.
- Do not harden `_resolve_unit_metadata()` failure translation here; that remains `ModularSimulator-9tr.2`.
- Do not add player-managed transport/logistics here; that remains `ModularSimulator-9tr.1`.
- Do not require full vessel geometry, level-pressure coupling, headspace EOS closure, or a rich declarative tank-head constitutive DSL in this slice.

## Decisions

1. **`ej7.1` is a corrective substrate precondition for ej7, not a gameplay-side accumulation tweak.**
   - The old `ej7.1` Beads wording mentions staged `TankCustody` accumulation units, but repo evidence shows the deeper blocker is wrong state ownership.
   - This pack therefore freezes simulation-owned tank state, runtime coupling, and observability exposure before any direct ej7 live gameplay planning proceeds.
   - `9tr.2` remains valid, but it is non-blocking hardening rather than the next immediate dependency.

2. **Physical tank inventory is simulation-owned conserved amount state.**
    - Stored tank state is an extensive amount balance, not a sampled flow-rate placeholder.
    - Minimum contract for this slice:
      - stored inventory is conserved holdup amount,
      - state advance occurs through material-balance dynamics in the tank process model under runtime-supplied boundary conditions,
      - gameplay does not own a mirrored physical inventory record.
    - The implementation may internally track total moles plus per-species component holdup, but it must not treat instantaneous `molar_flow_rate` values as inventory state.

3. **Minimal live tank semantics use the repo-standard differential unit-process pattern with a lumped well-mixed bulk.**
   - Repo evidence shows dynamic units advance through `ProcessModel.step()` and the adaptive ODE solver in `src/modular_simulation/measurables/process_model.py` / `src/modular_simulation/framework/system.py`, while connection runtime remains macrostep-owned.
   - `HoldingTank` should follow that same pattern instead of inventing a macrostep-only holdup integrator.
   - Minimum contract for this slice:
     - conserved tank inventory is stored as differential amount state (preferably component holdup on the published species basis),
     - the tank advances through the existing microstep ODE-solver path during `subsystem_process_step`,
     - inlet stream state and requested outlet demand are boundary conditions supplied by the substrate runtime,
     - realized outlet composition and temperature reflect the current lumped well-mixed bulk state.
   - Full geometry/level/pressure/EOS closure is explicitly deferred; this pack should not freeze bulk-pressure averaging as a physically authoritative vessel model.

4. **Connection runtime owns canonical boundary application; the tank process model owns holdup integration.**
    - Repo evidence shows `ConnectedPlantOrchestrator.step()` already runs `subsystem_process_step` before `connection_runtime_coupling`, and current units advance through `process_model.step(duration)` in `Subsystem.run_process_phase()`.
    - This pack keeps that lifecycle consistent: it does **not** introduce a special post-hydraulic tank-state integrator.
    - Instead, the new substrate seam must let connection runtime apply canonical boundary conditions that the tank consumes on its next unit-process step:
      - runtime continues to apply inlet `StreamData` / transferred inlet state,
      - runtime additionally applies per-outlet requested hydraulic demand (requested outlet through-flow) into a substrate-owned boundary-application seam adjacent to `ProcessStreamIO`,
      - `HoldingTank` then integrates holdup through its ODE/model step using those boundary conditions,
      - downstream propagation, snapshots, and observability use the tank model’s realized outlet condition after that process step rather than the raw requested demand.
    - Under the current connected-plant lifecycle, runtime-applied inlet conditions and requested outlet demand are latched boundary conditions for the following macro step’s `subsystem_process_step`; this pack does not claim same-step hydraulic-to-holdup closure.
    - The ownership outcome is fixed: gameplay must not advance tank holdup or own a second physical-state integrator.

5. **Public observability adds additive numeric process-state reads under `observables`, not a new top-level envelope.**
   - Keep the exact top-level snapshot keys frozen.
   - Add a new nested numeric mapping `observables.process_state_values`.
   - For holding tanks, that map must publish at minimum:
     - always: `<process_id>/holdup_total_mol` and `<process_id>/outlet_flow_mol_s`
     - normally: `<process_id>/bulk_temperature_K`
     - normally: one numeric key per species in the mixed bulk state, `<process_id>/mole_fraction/<species_id>`
    - Near-empty numerical-floor policy for this slice:
      - use a repo-consistent small positive depletion threshold / floor rather than letting conserved inventory step negative,
      - when holdup is clipped to that near-empty floor, `outlet_flow_mol_s` may remain at a clipped near-zero positive value for observability continuity rather than exact zero,
      - that positive near-zero observable does **not** authorize additional material transfer once withdrawable holdup above the configured floor is exhausted,
      - when holdup is clipped to that near-empty floor, bulk temperature and mole fractions retain the previous bulk-state values for observability continuity.
    - `bulk_temperature_K` is a lumped bulk-state observable only; it does not imply full enthalpy balance, stratification, or headspace thermodynamic closure.
    - This keeps the observability provider surface additive and numeric while giving higher layers the tank state they need through the substrate API.

6. **Gameplay-owned `tank_custody` physical inventory is removed/superseded, not preserved as a second owner.**
   - `src/modular_simulation/gameplay/tank_custody.py` is not the authoritative owner of conserved tank state after this pack.
   - If later work needs gameplay-owned route or UI intent metadata, it must remain non-physical, keyed by process/boundary ids only, and must not duplicate conserved amount, outlet flow, or mixed thermodynamic state.
   - This pack does not itself add such route metadata.

7. **The current live playable slice remains unchanged in ej7.1.**
   - `SUPPORTED_BUILD_ITEM_IDS` remains exactly `("place_heater_cooler", "place_flash_drum", "build_process_line")`.
   - `place_holding_tank` remains unsupported on all current starts.
   - No public session method, snapshot field, HTTP route, or Godot contract is widened here.

## Risks / Trade-offs

- **Runtime phase ordering is the main implementation risk.**
  - The current connected-plant phase order runs subsystem process stepping before connection runtime coupling, while conserved tank updates need canonical solved transfers.
  - Mitigation: freeze the ownership/result boundary in spec while preserving the existing process-then-runtime lifecycle; implementation may adjust the boundary-application seam within that lifecycle, but must not move tank advancement to a different phase or add a second integrator.

- **Observability must stay additive and policy-free.**
  - Extending the top-level snapshot envelope would break live tests and the existing observability contract.
  - Mitigation: keep the top-level envelope unchanged and add only nested `process_state_values`.

- **Gameplay cleanup can be tempting to overreach into ej7 scope.**
  - Once tank physical state becomes substrate-owned, it will be tempting to also expose live tank commands or gas-first behavior.
  - Mitigation: keep this pack strictly pre-ej7; do not widen starts, build menus, or public tank gameplay.

## Verification Strategy

- TDD should lead this change because it replaces a live but wrong owner boundary and live weak tank semantics.
- Required implementation evidence:
  - `HoldingTank` stores conserved holdup amount state rather than sampled flow values.
  - `HoldingTank` advances through the existing microstep ODE/process-model path rather than a macrostep-only bookkeeping update.
  - connection runtime applies canonical inlet conditions plus requested outlet demand through a substrate-owned boundary seam, and downstream transfer / snapshots / observability use the tank model’s realized outlet condition rather than the raw requested demand.
  - depletion guards prevent negative holdup using a small positive numerical floor consistent with repo near-zero conventions.
  - public observability keeps the exact top-level envelope and adds nested `process_state_values` for tank/process reads.
  - gameplay no longer owns a mirrored per-tank physical inventory helper.
  - conserved tank state survives checkpoint/export/restore through the runtime-owned process-state path.
  - current starts, supported build items, and public session/API contracts remain unchanged.
- Required verification commands for implementation:
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
- Closure review gate for implementation:
  - because this pack changes simulation behavior, runtime coupling, and named engineering semantics around conserved holdup, implementation must be reviewed by `hybrid-code-reviewer` and `simulation-advisor` in parallel before closure.

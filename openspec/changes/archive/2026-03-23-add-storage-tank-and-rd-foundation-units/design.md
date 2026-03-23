## Context

- The user replaced the earlier gas-first main-sandbox target with a smaller first pack: **foundation only**, **catalog only**, and **additive only**.
- `openspec/specs/units-and-components/spec.md` currently freezes an exact 12-item catalog and exact start allowlists for the current sandbox/tutorial starts.
- `openspec/specs/session/spec.md`, `openspec/specs/economics/spec.md`, and `openspec/specs/client-godot/spec.md` currently freeze the live gameplay/session/client behavior around the existing sandbox slice.
- `src/modular_simulation/gameplay/sandbox_catalog.py` currently contains only the heater/flash-era item records.
- `src/modular_simulation/unit_processes/__init__.py` exports no storage or lab-style foundation units.
- `src/modular_simulation/connection/topology/network.py` requires process nodes to expose at least one outlet, so a true sink-only research building is incompatible with the current topology contract.
- The user asked for more realistic oil-and-gas language where practical. Web terminology research supports **Holding tank** for the storage unit and **Quality control lab** for the placeable lab unit; “R&D building” is less grounded oil-and-gas wording.

## Goals / Non-Goals

**Goals**
- Freeze two durable placeable foundation units needed by later tank-based inventory and progression work.
- Keep the first pack additive so the current sandbox, tutorials, and client slice stay intact.
- Freeze lab acceptance semantics now so later progression work reuses one stable purity/accounting rule.

**Non-Goals**
- Move the live sandbox buy/sell loop through tanks.
- Add an active world-level research program, unlock tree, or progression snapshot.
- Add a new game API route or any Godot HUD/client behavior for the new units.
- Introduce true sink-only topology support.
- Generalize gameplay placement commands in this pack.

## Decisions

1. **This pack adds two shared catalog items, but no current start gets them yet.**
   - The shared gameplay catalog grows:
     - `place_holding_tank`
     - `place_quality_control_lab`
   - Both items use `supported_start_ids = ()` in this first pack.
   - This keeps verification at the catalog and unit-foundation level without changing the live main sandbox, tutorial starts, or client build menus.

2. **Player-facing names use grounded oil-and-gas wording.**
   - Storage unit title: `Holding tank`
   - Lab unit title: `Quality control lab`
   - The pack avoids generic “R&D building” wording in player-facing records, but the lab remains the durable foundation for later research/progression work.

3. **The exact catalog record for the storage foundation is frozen.**

### `place_holding_tank`
- `title = "Holding tank"`
- `item_kind = "unit_blueprint"`
- `apply_kind = "add_process"`
- `default_config = {"unit_type": "HoldingTank", "unit_module": "modular_simulation.unit_processes.storage.holding_tank", "constructor_payload": {}}`
- `required_user_inputs = ("process_id",)`
- `supported_start_ids = ()`
- `educational_summary = "single-inlet single-outlet buffer vessel for future tank-mediated material holdup and transfer"`

4. **The exact catalog record for the lab foundation is frozen.**

### `place_quality_control_lab`
- `title = "Quality control lab"`
- `item_kind = "unit_blueprint"`
- `apply_kind = "add_process"`
- `default_config = {"unit_type": "QualityControlLab", "unit_module": "modular_simulation.unit_processes.analysis.quality_control_lab", "constructor_payload": {"minimum_purity_mol_fraction": 0.95}}`
- `required_user_inputs = ("process_id", "tracked_component_id")`
- `supported_start_ids = ()`
- `educational_summary = "process-stream quality gate that counts accepted moles toward later research progress and rejects off-spec material to disposal"`

5. **Holding Tank is a real holdup foundation, not a renamed pass-through line.**
   - `HoldingTank` is a placeable process/unit with exactly one inlet port and one outlet port.
   - It stores incoming material as internal holdup between advances.
   - Any outlet flow must come from stored holdup; the unit must not invent material when upstream flow is absent.
   - The first implementation may use a simple deterministic discharge rule, but the pack freezes two minimum observable boundaries:
     - outlet flow can never exceed available stored holdup for the simulated step,
     - zero stored holdup means zero outlet flow.
   - `HoldingTank` must expose explicit `hydraulic_participation` so a connected network can compile without relying on undeclared passive-port inference.
   - The tank should follow the existing single-inlet/single-outlet pattern used by other connected units: one balancing group over `("inlet", "outlet")`, explicit pressure-state ownership for the connected ports, and no hidden topology exception.
   - This pack does **not** bind tank holdup to sandbox buy/sell, feed procurement, or product-sale mechanics.

6. **Quality Control Lab is a placeable lab unit with one inlet and one reject/disposal outlet.**
   - `QualityControlLab` is a placeable process/unit with exactly:
     - one inlet port for the tested stream,
     - one reject/disposal outlet port required by the current topology contract.
   - The lab is configured with:
     - `tracked_component_id: str`
     - `minimum_purity_mol_fraction: float`
   - The lab owns one cumulative unit-local progress value:
     - `accepted_progress_mol: float`
   - `QualityControlLab` must expose explicit `hydraulic_participation` so a connected network can compile as an ordinary two-port unit under the current connection rules.
   - The lab should follow the existing single-inlet/single-outlet pattern used by other connected units: one balancing group over `("inlet", "reject_outlet")`, explicit pressure-state ownership for the connected ports, and no hidden topology exception.
   - This pack does **not** bind that value to a world-level unlock tree or session-wide progression catalog yet.

7. **Lab acceptance uses one pass/fail purity rule.**
   - For each incoming stream sample or flow slice, compute the mol-fraction purity of `tracked_component_id` in the incoming stream.
    - If purity is **greater than or equal to** `minimum_purity_mol_fraction`:
      - accept the stream,
      - add the **entire incoming stream molar amount** to `accepted_progress_mol`,
      - discharge the same accepted stream through the sole `reject_outlet` port in this first pack because the topology still requires one outlet and the pack does not add a second accepted-material outlet.
    - If purity is below the threshold:
      - add **zero** to `accepted_progress_mol`,
      - route the incoming stream to the reject/disposal outlet.
   - Accepted progress counts **accepted moles only**.
   - Higher purity above the threshold grants **no bonus credit**.
   - The physical outlet behavior is intentionally simple in this pack: the lab always exposes one outlet stream through `reject_outlet`, while progress accounting separately decides whether the incoming slice earned lab credit.

8. **Current live gameplay/session/client surfaces stay unchanged in this pack.**
   - `phase1_process_sandbox_v1` keeps its current title, provenance, signals, and allowlist.
   - Tutorial starts remain unchanged and separate from the main sandbox.
   - No new session methods, no new game-service commands, and no Godot build-menu changes belong to this pack.
   - Existing item-specific placement handling is acceptable here; generic placement remains follow-on work.

9. **No new live capability domain is justified yet.**
   - `units-and-components` is the right live spec home for this first pack because the pack freezes buildable-item records and observable foundation-unit behavior.
   - A separate progression-like capability becomes justified later only when the lab is connected to actual unlock state or research-program selection.

## Risks / Trade-offs

- **Catalog-only items can look odd because no current start allows them.**
  - Mitigation: freeze that boundary explicitly and test that current starts remain unchanged.
- **The lab is not a physically perfect plant lab model.**
  - Mitigation: keep the wording honest; this is a gameplay foundation unit with grounded QC-language and a clear pass/fail purity rule.
- **Topology still cannot host true sink-only units.**
  - Mitigation: keep the reject/disposal outlet explicit and defer sink support rather than hiding a topology exception in this pack.

## Verification Strategy

- TDD should lead the catalog additions and both unit-process foundations.
- Required verification for implementation:
  - `uv run pytest tests/gameplay/test_sandbox_catalog.py`
  - `uv run pytest tests/gameplay/test_start_catalog.py`
  - `uv run pytest tests/gameplay/test_sandbox_session.py -k "simulation_api_surface_is_frozen or unsupported_on_start or install_catalog_item"`
  - `uv run pytest tests/unit_process/test_layer4_holding_tank.py`
  - `uv run pytest tests/unit_process/test_layer4_quality_control_lab.py`
  - `uv run pytest tests/unit_process/test_layer4_holding_tank.py tests/unit_process/test_layer4_quality_control_lab.py -k "hydraulic_participation or compile"`
  - `uv run pytest tests/gameplay/test_realtime_game_service.py`
  - `uv run pytest tests/app/test_game_api.py`
  - `uv run pytest tests/integration/test_sandbox_start_smoke.py`
- Expected evidence:
  - the shared catalog contains the two exact new item ids and records,
  - both new items remain unsupported on every current start in this first pack,
  - the current sandbox and client slice still expose the existing buildable set only,
  - the holding tank preserves real holdup behavior,
  - both new units expose explicit hydraulic participation and can compile as ordinary connected process nodes,
  - the quality control lab counts only accepted whole-stream moles and routes the single exposed outlet stream through the reject/disposal boundary defined by this pack.

## Dependency gate

- [x] D0 Do not start implementation until this change pack is approved and the implementation packet is created in Beads from these tasks.

## Wave 1 — Freeze the catalog-only foundation boundaries with red tests first

- [x] 1.1 Extend `tests/gameplay/test_sandbox_catalog.py` with red tests covering these exact new catalog boundaries before implementation:
  - the shared gameplay catalog now contains exactly `place_holding_tank` and `place_quality_control_lab` in addition to the existing frozen items,
  - each new item matches the exact `title`, `item_kind`, `apply_kind`, `default_config`, `required_user_inputs`, `supported_start_ids`, and `educational_summary` frozen in `design.md`,
  - both new items use `supported_start_ids = ()` in this first pack.
- [x] 1.2 Extend `tests/gameplay/test_start_catalog.py` with red tests proving this pack does **not** change the current starts:
  - `phase1_process_sandbox_v1` keeps its current title, seed provenance, published signals, and allowed item ids,
  - all tutorial start records remain unchanged,
  - no current start allowlist gains `place_holding_tank` or `place_quality_control_lab`.
- [x] 1.3 Add `tests/unit_process/test_layer4_holding_tank.py` with red tests covering the storage foundation behavior before implementation:
  - `HoldingTank` exposes exactly one inlet and one outlet,
  - incoming material can accumulate as internal holdup across advances,
  - outlet flow can only come from stored holdup and does not invent material when upstream flow is absent,
  - zero stored holdup yields zero outlet flow,
  - `HoldingTank` declares explicit hydraulic participation for `inlet` and `outlet` with one balancing group so a connected network can compile without hidden topology exceptions.
- [x] 1.4 Add `tests/unit_process/test_layer4_quality_control_lab.py` with red tests covering the lab foundation behavior before implementation:
  - `QualityControlLab` exposes exactly one inlet and one reject/disposal outlet,
  - threshold-met streams increase `accepted_progress_mol` by the **entire incoming stream molar amount**,
  - threshold-failing streams increase progress by `0.0` and route the incoming flow to the reject/disposal outlet,
  - purity above the minimum threshold does not add bonus credit,
  - the tracked component id and minimum purity threshold are explicit constructor/config inputs,
  - `QualityControlLab` declares explicit hydraulic participation for `inlet` and `reject_outlet` with one balancing group so a connected network can compile without hidden topology exceptions,
  - accepted streams still leave through the sole `reject_outlet` port in this first pack because there is no second accepted-material outlet yet.
- [x] 1.5 Extend `tests/gameplay/test_sandbox_session.py` with a red guard proving the current session boundary stays intact:
  - attempting to install either new item in `phase1_process_sandbox_v1` is rejected as `unsupported_on_start`,
  - no new session API method or progression snapshot is introduced by this pack.
- [x] 1.6 Run the red boundary:
  - `uv run pytest tests/gameplay/test_sandbox_catalog.py tests/gameplay/test_start_catalog.py`
  - `uv run pytest tests/unit_process/test_layer4_holding_tank.py tests/unit_process/test_layer4_quality_control_lab.py`
  - `uv run pytest tests/gameplay/test_sandbox_session.py -k "simulation_api_surface_is_frozen or unsupported_on_start or install_catalog_item"`
  - Expected evidence: the new foundation items and unit-process tests fail before implementation exists.

## Wave 2 — Implement the new unit foundations and catalog records

- [x] 2.1 Create `src/modular_simulation/unit_processes/storage/__init__.py` and `src/modular_simulation/unit_processes/storage/holding_tank.py` with the frozen `HoldingTank` unit.
- [x] 2.2 Create `src/modular_simulation/unit_processes/analysis/__init__.py` and `src/modular_simulation/unit_processes/analysis/quality_control_lab.py` with the frozen `QualityControlLab` unit.
- [x] 2.3 Update `src/modular_simulation/unit_processes/__init__.py` to export `HoldingTank` and `QualityControlLab`.
- [x] 2.4 Update `src/modular_simulation/gameplay/sandbox_catalog.py` with the exact `place_holding_tank` and `place_quality_control_lab` records frozen in `design.md`.
- [x] 2.5 Implement explicit `hydraulic_participation` for both new units so connected-network compile follows the existing declared-port rules rather than relying on implicit fallback behavior.
- [x] 2.6 Keep both items catalog-only in this pack:
  - do not add them to any current `allowed_item_ids` start record,
  - do not add a new verification start,
  - do not add slice-specific service or client exposure.

## Wave 3 — Prove the current live sandbox and client slice stayed untouched

- [x] 3.1 Make `tests/gameplay/test_start_catalog.py` and the targeted `tests/gameplay/test_sandbox_session.py` checks pass without changing current start ids or start allowlists.
- [x] 3.2 Re-run the unit-process tests until the new foundations pass with the exact holdup and purity-threshold semantics.
- [x] 3.3 Add or extend a narrow connected-network compile check proving both new units can participate as ordinary connected process nodes under the current hydraulic compile rules.
- [x] 3.4 Re-run the current slice guards so this pack does not silently widen live exposure:
  - `uv run pytest tests/gameplay/test_realtime_game_service.py`
  - `uv run pytest tests/app/test_game_api.py`
  - `uv run pytest tests/integration/test_sandbox_start_smoke.py`
  - Expected evidence: bootstrap, game API, and current sandbox start behavior remain unchanged.

## Wave 4 — Sync the live spec only where implemented behavior actually changed

- [x] 4.1 Sync the implemented catalog/unit delta into `openspec/specs/units-and-components/spec.md`:
  - update the exact sandbox catalog item-id requirement from 12 item ids to the new exact 14-item set,
  - add the two exact new catalog records,
  - freeze that both remain unsupported on every current start in this first pack,
  - freeze the minimum connected-unit behavior for both foundations, including explicit hydraulic participation and the lab’s single reject/disposal outlet model,
  - keep the existing start records and live slice allowlists unchanged.
- [x] 4.2 Do **not** edit `openspec/specs/session/spec.md`, `openspec/specs/economics/spec.md`, or `openspec/specs/client-godot/spec.md` unless implementation evidence proves one of those live contracts actually changed.
- [x] 4.3 Run final verification:
  - `uv run pytest tests/gameplay/test_sandbox_catalog.py`
  - `uv run pytest tests/gameplay/test_start_catalog.py`
  - `uv run pytest tests/gameplay/test_sandbox_session.py -k "simulation_api_surface_is_frozen or unsupported_on_start or install_catalog_item"`
  - `uv run pytest tests/unit_process/test_layer4_holding_tank.py`
  - `uv run pytest tests/unit_process/test_layer4_quality_control_lab.py`
  - `uv run pytest tests/unit_process/test_layer4_holding_tank.py tests/unit_process/test_layer4_quality_control_lab.py -k "hydraulic_participation or compile"`
  - `uv run pytest tests/gameplay/test_realtime_game_service.py`
  - `uv run pytest tests/app/test_game_api.py`
  - `uv run pytest tests/integration/test_sandbox_start_smoke.py`
- [x] 4.4 Expected final evidence:
  - the shared catalog contains `place_holding_tank` and `place_quality_control_lab` exactly as frozen,
  - both items remain catalog-only and unsupported on all current starts,
  - the holding tank behaves as a real holdup unit foundation,
  - both units compile as ordinary connected process nodes with explicit hydraulic participation,
  - the quality control lab uses the reject/disposal outlet model and accepted-moles-only threshold accounting,
  - the current main sandbox, tutorial starts, and client slice remain unchanged,
  - archive the change only after implementation and verification are complete.

## Why

The storage/QC foundation pack landed the reusable `HoldingTank` unit, but the gameplay stack still cannot consume it safely. Repo evidence shows the current realtime build path hard-codes every placed process as `inlet_ports=("in",)` and `outlet_ports=("out",)`, while the real `HoldingTank` implementation exposes `("inlet",)` and `("outlet",)`. The live sandbox/session/client/economics slice is also still frozen around direct feed/product inventories, static build items, and withdrawal-token sales.

The user then narrowed `ModularSimulator-4fm` away from a live sandbox rewrite. `4fm` now owns **infrastructure only**: stage the internal tank-custody seams that later work can consume, keep the current live playable slice unchanged, and defer the gas-starter retarget, real product naming/specs, public tank-mediated buy/sell, and transport infrastructure to `ModularSimulator-ej7` and `ModularSimulator-9tr.1`.

Without this pack, `ModularSimulator-ej7` would have to solve item-aware process placement, generic tank-state bookkeeping, route assignment, purge primitives, and the live gas-starter rewrite all at once.

## What Changes

- Stage an **item-aware `add_process` runtime seam** so gameplay can respect the exact runtime metadata already frozen in `unit_blueprint` catalog records — `unit_module`, `unit_type`, and `constructor_payload` when present — instead of forcing generic `in/out` ports.
- Use `HoldingTank` as the minimum acceptance proof for that seam because its real ports differ from the current hard-coded placement path, while keeping the seam general enough to respect any future declared inlet/outlet shape rather than assuming tanks are always single-inlet/single-outlet.
- Stage **internal generic tank-custody primitives** keyed by tank `process_id` and boundary id:
  - internal per-tank custody state stored as aggregate mixed inventory that preserves enough thermodynamic state for later pressure/volume calculations,
  - one-active-route-per-boundary assignment for bought/sold boundary routes only,
  - internal purge-by-tank support.
- Keep the current live slice unchanged in this pack:
  - no start allowlist changes,
  - no `SUPPORTED_BUILD_ITEM_IDS` expansion,
  - no public session method changes,
  - no economics receipt or withdrawal-token rewrite,
  - no Godot/API route or payload changes,
  - no tank or purge command exposed to players yet.

## Capabilities

### Modified Capabilities
- `units-and-components`
- `session`

## Impact

- Affected code:
  - `src/modular_simulation/gameplay/realtime_service.py`
  - `src/modular_simulation/gameplay/sandbox_session.py`
  - `src/modular_simulation/gameplay/tank_custody.py` (new)
  - `src/modular_simulation/unit_processes/storage/holding_tank.py` (read/consumed for runtime metadata, not redesigned here)
- Affected tests:
  - `tests/gameplay/test_tank_custody.py` (new)
  - `tests/gameplay/test_realtime_game_service.py`
  - `tests/gameplay/test_sandbox_session.py`
  - `tests/gameplay/test_sandbox_contracts.py`
  - `tests/gameplay/test_sandbox_catalog.py`
  - `tests/gameplay/test_start_catalog.py`
  - `tests/app/test_game_api.py`
  - `tests/cli/test_backend_session.py` only if implementation must touch transaction helpers
- Affected OpenSpec sync surfaces after implementation:
  - `openspec/changes/2026-03-23-stage-tank-custody-infrastructure/specs/units-and-components/spec.md`
  - `openspec/changes/2026-03-23-stage-tank-custody-infrastructure/specs/session/spec.md`
  - `openspec/specs/units-and-components/spec.md`
  - `openspec/specs/session/spec.md`
- Explicitly deferred to existing Beads follow-ons:
  - `ModularSimulator-ej7` — live gas-starter retarget, real feed/product naming, tank-mediated live buy/sell, and progression layered on top of staged infrastructure
  - `ModularSimulator-9tr.1` — player-managed transport/logistics infrastructure

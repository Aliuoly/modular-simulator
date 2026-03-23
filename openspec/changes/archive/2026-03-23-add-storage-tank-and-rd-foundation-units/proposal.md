## Why

The user narrowed the original oil-and-gas progression work into a smaller first pack: add the durable **storage** and **R&D foundation** pieces first, keep them additive, and defer any live sandbox migration until the foundations are real.

Repo evidence shows the current gameplay stack still centers on direct feed/product inventories, the current build flow is item-specific, there is no holding-tank unit, there is no placeable research or lab unit, and current topology requires every process node to expose at least one outlet. The previously drafted gas-first progression pack is now stale for implementation because it assumes a larger progression layer before these foundations exist.

Without this pack, later work would have to invent storage and lab semantics ad hoc while also changing the sandbox, the client, and progression behavior at the same time.

## What Changes

- Add two **cataloged foundation units** for later oil-and-gas progression work:
  - `place_holding_tank`
  - `place_quality_control_lab`
- Freeze the player-facing names, catalog records, and plain-language unit behavior for both foundations.
- Freeze the minimum topology/connection contract for both units so they can participate as ordinary connected process nodes under the current hydraulic compile rules.
- Freeze the Quality Control Lab acceptance rule:
  - purity threshold gate,
  - if the stream meets the threshold, count the entire accepted molar feed,
  - count accepted moles only,
  - no extra credit for purity above the threshold.
- Freeze the topology-compatible lab boundary for this first pack: one reject/disposal outlet instead of introducing true sink-only unit support.
- Keep exposure **catalog only** for verification in this pack: do not add either item to any current start allowlist, do not rewire the live sandbox, and do not change the current client slice.

## Capabilities

### Modified Capabilities
- `units-and-components`

## Impact

- Affected code:
  - `src/modular_simulation/gameplay/sandbox_catalog.py`
  - `src/modular_simulation/unit_processes/__init__.py`
  - `src/modular_simulation/unit_processes/storage/__init__.py` (new)
  - `src/modular_simulation/unit_processes/storage/holding_tank.py` (new)
  - `src/modular_simulation/unit_processes/analysis/__init__.py` (new)
  - `src/modular_simulation/unit_processes/analysis/quality_control_lab.py` (new)
- Affected tests:
  - `tests/gameplay/test_sandbox_catalog.py`
  - `tests/gameplay/test_start_catalog.py`
  - `tests/gameplay/test_sandbox_session.py`
  - `tests/unit_process/test_layer4_holding_tank.py` (new)
  - `tests/unit_process/test_layer4_quality_control_lab.py` (new)
  - existing slice-smoke tests that prove current sandbox/client behavior stayed unchanged
- Affected OpenSpec sync surfaces after implementation:
  - `openspec/changes/2026-03-23-add-storage-tank-and-rd-foundation-units/specs/units-and-components/spec.md` (new delta spec)
  - `openspec/specs/units-and-components/spec.md`
- Explicitly deferred to existing Beads follow-ons:
  - `ModularSimulator-4fm` — move live sandbox buy/sell through tanks
  - `ModularSimulator-ej7` — build gas-first progression on top of the landed foundations
  - `ModularSimulator-6ei` — generalize gameplay placement commands

## Why

Once the repo is positioned as an educational backend, the next planning risk is scope drift inside the first playable curriculum. The codebase already has grounded examples for heater/flash, recycle/purge, and reactor/control references, but there is no durable contract for which starter scenarios exist, what each scenario is meant to teach, or which kinds of upgrades are allowed.

Without a dedicated starter-scenario pack, implementers would have to guess whether phase 1 is a tiny tutorial ladder or an open-ended chemistry sandbox. That would blur curriculum intent, template reuse, and the boundary between canonical examples and gameplay scenarios.

## What Changes

- Add a new `phase1-starter-scenarios` capability that freezes the exact phase-1 scenario catalog and its teaching purpose.
- Define the three starter scenarios, their seed/example provenance, and the machine-readable contracts for scenario metadata, concrete upgrades, success metrics, victory conditions, and scenario-authored economics bindings.
- Require the starter catalog to stay intentionally small and template-backed.

## Capabilities

### New Capabilities
- `phase1-starter-scenarios`: phase-1 starter scenario definitions, template provenance, learning outcomes, and scenario-scope boundaries.

## Impact

- Affected docs: `docs/game_backend_overview.md` and `docs/examples_catalog.md` need scenario/template cross-references once implemented.
- Affected code: future gameplay modules under `src/modular_simulation/gameplay/` plus reusable builders under `src/modular_simulation/gameplay/templates/`.
- Affected tests: add contract, scenario-catalog, and template-contract coverage under `tests/gameplay/`.
- Dependency: this pack depends on `clarify-educational-backend-positioning` for product framing.

## Why

The user clarified that phase 1 should contain **one true sandbox**, not several named sandboxes. Tutorial content is still allowed, but tutorials must be explicit guided challenges with clear goals rather than being mislabeled as sandbox play.

The repo already supports explicit topology editing, line-owned pump/valve/heat overlays, and runtime instrumentation wiring. But there is no durable OpenSpec pack that freezes:
- the one phase-1 sandbox start state,
- the exact build/apply catalog available in that sandbox,
- the tutorial starter states and their exact goal contracts,
- and the thin generic `TxHandle` helpers still missing from `PlantBackendSession.begin_tx()`.

Without this pack, implementation would drift back toward scenario-first planning, mix tutorial goals into the sandbox definition, or leave substrate-helper gaps implicit.

## What Changes

- Add a new `phase1-sandbox-build-catalog` capability that freezes the exact phase-1 sandbox start state, build catalog, and tutorial challenge boundary.
- Define the exact catalog item ids, repo-grounded apply kinds, `default_config` payloads, supported start states, and the exact generic transaction-helper surface required through `PlantBackendSession.begin_tx()` / `TxHandle`.
- Define tutorial starter states plus exact tutorial goal and guidance payloads separately from the sandbox so guided challenges do not become the source of truth for sandbox mechanics.

## Capabilities

### New Capabilities
- `phase1-sandbox-build-catalog`: one phase-1 sandbox, exact build/apply primitives, tutorial starter states, tutorial goals, and substrate-helper boundaries.

## Impact

- Affected code: `src/modular_simulation/gameplay/` for catalog/start/tutorial data and `src/modular_simulation/cli/backend_session.py` for thin generic transaction helpers via `session.begin_tx()` / `TxHandle`.
- Affected tests: add sandbox/start/tutorial coverage under `tests/gameplay/` and extend `tests/cli/test_backend_session.py` for generic helper coverage.
- Affected docs: `docs/game_backend_overview.md` and `docs/plant_backend_session_user_guide.md` need wording aligned to one sandbox plus tutorial challenges.
- Dependencies: this pack depends on `educational-backend-positioning` and `flowsheet-junction-line-api` because the sandbox must stay consistent with the repo’s substrate identity and explicit line-owned overlay model.

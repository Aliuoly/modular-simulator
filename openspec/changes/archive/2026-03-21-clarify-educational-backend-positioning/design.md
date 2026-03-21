## Context

- `docs/README.md` currently frames the repo as a lightweight framework for closed-loop process simulation and controller learning.
- `docs/plant_backend_session_user_guide.md` and `src/modular_simulation/cli/backend_session.py` already describe a user-facing backend for interactive plant editing, including a game-like UI.
- Existing specs already enforce the physical-fidelity envelope the user wants: explicit junction topology, pressure-driven hydraulics, explicit hydraulic participation, recycle validity, and a deliberately small educational example set (`openspec/specs/flowsheet-junction-line-api/spec.md`, `openspec/specs/hydraulic-network-solving-semantics/spec.md`, `openspec/specs/recycle-loop-validation/spec.md`, `openspec/specs/curated-flowsheet-examples/spec.md`).
- Existing examples show a narrow set of grounded teaching assets: heater/flash, dual-feed exchanger, ammonia recycle loop, and control/reactor references.

## Goals / Non-Goals

**Goals**
- Reconcile the repo identity so contributors can tell what product this backend is for.
- Freeze a manageable phase-1 teaching scope that matches current continuous-process capabilities.
- Clarify which layers own physical truth versus future gameplay rules.

**Non-Goals**
- Define exact scenario ids, template contracts, or gameplay APIs; those belong to follow-on packs.
- Add new economics, progression, or runtime behavior in this pack.
- Reclassify the existing canonical example inventory beyond wording needed to explain product direction.

## Decisions

1. **Position the repo as a simulation-first backend, not a generic sandbox and not a frontend game client.**
   - The durable product description is: backend substrate for educational chemical-process gameplay and classroom exercises.
   - The repo still exposes reusable simulation primitives, but docs should stop presenting the project as only a generic controller-simulation framework.

2. **Target chemical-engineering learners first.**
   - Primary audience: chemical engineering students and instructors.
   - Secondary audience: contributors experimenting with process-control and flowsheet modeling.

3. **Freeze phase 1 to three teaching tracks, not a giant campaign.**
   - Track 1: topology and separation basics.
   - Track 2: reactor dynamics, sensing, and control.
   - Track 3: recycle, purge, and process-design tradeoffs.
   - These tracks intentionally fit the existing continuous-process code and examples.

4. **Keep simulation truth below future gameplay orchestration.**
   - `Flowsheet`, hydraulic semantics, unit-process models, sensors, controllers, and `PlantBackendSession` stay the canonical physical/runtime-editing substrate.
   - Future progression, economics, and scenario rules must compose those layers rather than rewriting them.

5. **Make long-horizon ideas explicit non-goals for phase 1.**
   - Deferred: batch-first gameplay, stochastic equipment failure, fouling accumulation, staffing/engineers, and multi-plant vertical integration.
   - Deferred items should be named in docs so later work does not get smuggled into phase-1 acceptance criteria.

6. **Document the current canonical examples as seeds, not the full game itself.**
   - The canonical examples remain the best starting points for the underlying simulation substrate.
   - Future gameplay packs may build on those examples or on reference-only reactor/control assets, but this positioning pack does not change the canonical keep/remove inventory.

## Risks / Trade-offs

- **Docs may overpromise gameplay before runtime support exists.**
  - Mitigation: describe gameplay/session/economics as planned follow-on capabilities, not current implementation.
- **Product framing could drift from the current curated example guidance.**
  - Mitigation: keep the canonical example inventory intact and present it as the substrate learning path.
- **Future packs could silently re-expand scope.**
  - Mitigation: name the deferred topics now and require later packs to opt into them explicitly.

## Verification Strategy

- Add docs-contract regression coverage in `tests/test_game_backend_positioning.py` before editing docs.
- Required verification:
  - `uv run pytest tests/test_game_backend_positioning.py`
  - `uv run pytest tests/test_rework_examples_review_alignment.py -k "canonical or catalog"`
- Expected evidence:
  - `docs/README.md`, `docs/plant_backend_session_user_guide.md`, and `docs/game_backend_overview.md` all describe the same repo identity,
  - phase-1 teaching tracks and deferred topics are explicit,
  - `PlantBackendSession` is described as substrate rather than as the full gameplay owner,
  - the existing curated-example parity checks remain green.

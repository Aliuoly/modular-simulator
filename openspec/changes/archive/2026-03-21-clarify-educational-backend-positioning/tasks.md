## Wave 1 — Freeze the docs contract with red tests first

- [x] 1.1 Add red docs-contract tests in `tests/test_game_backend_positioning.py` covering these exact assertions before doc edits:
  - `docs/README.md`, `docs/plant_backend_session_user_guide.md`, and `docs/game_backend_overview.md` describe the repo as a simulation-first backend for educational chemical-process gameplay/classroom tooling,
  - the docs name the three phase-1 teaching tracks (topology/separation, reactor/control, recycle/process-design),
  - deferred topics include batch-first gameplay, fouling/staffing, and multi-plant vertical integration,
  - `PlantBackendSession` is described as low-level runtime-editing substrate rather than the owner of progression/economics rules.
- [x] 1.2 Verify the red boundary with:
  - `uv run pytest tests/test_game_backend_positioning.py`
  - Expected evidence: the new docs tests fail before the wording changes land.

## Wave 2 — Align the public docs around one repo identity

- [x] 2.1 Update `docs/README.md` so the intro and quick-start framing describe the repo as a simulation-first backend for educational process gameplay/classroom tooling while preserving the current canonical example inventory.
- [x] 2.2 Update `docs/plant_backend_session_user_guide.md` so it explicitly states that `PlantBackendSession` is the low-level topology/runtime-editing substrate for user-facing applications and future gameplay layers.
- [x] 2.3 Add `docs/game_backend_overview.md` covering target audience, phase-1 teaching tracks, fidelity boundaries, and explicit non-goals/deferred systems.
- [x] 2.4 Cross-check wording so `docs/examples_catalog.md` remains accurate about the current canonical example set and is not implicitly rewritten into a gameplay catalog.

## Wave 3 — Verify doc alignment and preserve existing example guidance

- [x] 3.1 Run the targeted matrix:
  - `uv run pytest tests/test_game_backend_positioning.py`
  - `uv run pytest tests/test_rework_examples_review_alignment.py -k "canonical or catalog"`
  - Expected evidence: the three docs agree on repo identity and phase-1 scope, and the existing curated-example alignment tests stay green.
- [x] 3.2 If doc wording needs additional regression coverage after Wave 3.1, extend `tests/test_game_backend_positioning.py` in the same change rather than weakening the stated product boundary.

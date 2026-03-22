## Why

The user clarified that simulation and economics should remain mostly decoupled:
- the simulation layer consumes feed inventory and accumulates product inventory,
- the economics layer owns quoting, purchasing, selling, and cash accounting,
- and tutorials should track elapsed completion time instead of any generic “score.”

The repo already has measurable plant outputs, plant-calculation infrastructure, and runtime composition surfaces. But it does not yet define:
- a simulation session contract for inventory-backed sandbox play,
- a separate economics ledger for equipment/feed/product transactions,
- or the exact heuristic rulebook for phase-1 equipment, feed, product-sale, and operating costs with user-visible rule names.

Without this pack, implementation would keep mixing buy/sell concepts into the simulation API, turn tutorial progress into a score system, or leave the economics layer too coupled to substrate details.

## What Changes

- Add a new `sandbox-session-and-heuristic-economics` capability that separates the simulation session from the economics ledger while keeping them composable.
- Freeze the exact rulebook for phase-1 equipment pricing, feed procurement, product sales, and operating-cost heuristics with user-visible rule names plus explicit handoff tokens between simulation and economics.
- Define tutorial completion as goal completion plus elapsed time, not a numeric score.

## Capabilities

### New Capabilities
- `sandbox-session-and-heuristic-economics`: inventory-backed simulation session, separate economics ledger, tutorial elapsed-time tracking, and named engineering-economics heuristics.

## Impact

- Affected code: `src/modular_simulation/gameplay/` for session/economics logic, with only thin generic substrate hooks permitted in `src/modular_simulation/cli/backend_session.py` if pack 1 did not already land them.
- Affected tests: add simulation-session and economics-ledger coverage under `tests/gameplay/` and extend integration examples under `tests/integration/`.
- Affected docs: `docs/game_backend_overview.md` and `docs/plant_backend_session_user_guide.md` need the simulation/economics boundary wording.
- Dependency: this pack depends on `define-phase1-sandbox-build-catalog` because it must consume the frozen sandbox start, tutorial starts, published signals, and build catalog as data.

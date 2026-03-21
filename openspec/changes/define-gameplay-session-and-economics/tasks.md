## Wave 1 — Freeze gameplay/economics contracts with red tests first

- [ ] 1.1 Add red tests in `tests/gameplay/test_contracts.py` covering these exact gameplay-session result shapes before implementation:
  - `GameStateSnapshot` exposes `scenario_id`, `time_s`, `cash_balance`, `owned_upgrade_ids`, `available_upgrade_ids`, and `objective_status_by_id`,
  - `ObjectiveStatus` exposes `condition_id`, `currently_satisfied`, `accumulated_hold_time_s`, and `completed`,
  - `UpgradeQuote` exposes `upgrade_id`, `base_cost`, `prerequisite_upgrade_ids`, `unmet_prerequisite_upgrade_ids`, `plant_changes`, and `affordable`,
  - `PurchaseResult` exposes `success`, `reason_code`, and `snapshot`,
  - `StepScoreResult` exposes `snapshot`, `economics`, and `metric_values_by_id`,
  - `EconomicsBreakdown` exposes `revenue`, `utility_cost`, `equipment_capex`, `instrumentation_capex`, and `operating_profit`.
- [ ] 1.2 Add red tests in `tests/gameplay/test_economics.py` covering these exact semantics before implementation:
  - `revenue` and `utility_cost` are step-interval values for the just-completed `dt_s`,
  - `equipment_capex` and `instrumentation_capex` are cumulative spent-to-date totals partitioned by upgrade category,
  - `operating_profit == revenue - utility_cost` and excludes CAPEX,
  - economics are deterministic for a fixed scenario state and step result,
  - manual click-income counters are absent from the gameplay contract.
- [ ] 1.3 Add red tests in `tests/gameplay/test_game_backend_session.py` covering these exact state transitions before implementation:
  - `start_scenario(scenario_id, *, initial_cash=None)` initializes `time_s=0.0`, empty owned upgrades, the scenario-defined or overridden cash balance, and objective status derived from the active scenario’s typed victory conditions,
  - `quote_upgrade(upgrade_id)` is non-mutating and reports fixed `base_cost`, prerequisites, unmet prerequisites, explicit plant changes, and affordability,
  - `purchase_upgrade(upgrade_id)` mutates immediately on success, subtracts `base_cost` once, and rejects `unknown_upgrade`, `already_owned`, `unmet_prerequisite`, `insufficient_cash`, and `out_of_scope` with stable reason codes,
  - `step_and_score(dt_s)` increments `time_s` by `dt_s`, adds `operating_profit` to `cash_balance`, returns the current metric values, and updates one `ObjectiveStatus` per `VictoryCondition` using the fixed hold-timer rules (`+= dt_s` while satisfied, reset to `0.0` otherwise, latch `completed=True` once the threshold is reached),
  - `get_progression_state()` returns the current `GameStateSnapshot` without advancing physics.
- [ ] 1.4 Verify the red boundary with:
  - `uv run pytest tests/gameplay/test_contracts.py tests/gameplay/test_economics.py tests/gameplay/test_game_backend_session.py`
  - Expected evidence: gameplay/economics tests fail before the implementation exists.

## Wave 2 — Implement the gameplay package as a composition layer

- [ ] 2.1 Create or extend `src/modular_simulation/gameplay/contracts.py` with `EconomicsBreakdown`, `ObjectiveStatus`, `GameStateSnapshot`, `UpgradeQuote`, `PurchaseResult`, and `StepScoreResult` alongside the scenario-facing contract types from the starter-scenario pack.
- [ ] 2.2 Create `src/modular_simulation/gameplay/economics.py` so scoring consumes simulation outputs and installed assets using the shared phase-1 formula skeleton and scenario-authored coefficient bindings.
- [ ] 2.3 Create `src/modular_simulation/gameplay/game_backend_session.py` with these exact method signatures and semantics:
  - `start_scenario(scenario_id: str, *, initial_cash: float | None = None) -> GameStateSnapshot`
  - `quote_upgrade(upgrade_id: str) -> UpgradeQuote`
  - `purchase_upgrade(upgrade_id: str) -> PurchaseResult`
  - `step_and_score(dt_s: float) -> StepScoreResult`
  - `get_progression_state() -> GameStateSnapshot`
- [ ] 2.4 Consume upgrade ids, prices, prerequisites, plant changes, success metrics, and victory conditions from `src/modular_simulation/gameplay/scenario_catalog.py`; do not re-author them inside `game_backend_session.py`.
- [ ] 2.5 Keep `src/modular_simulation/cli/backend_session.py` free of pricing/progression policy; if extra hooks are needed, add only thin generic helpers there.

## Wave 3 — Verify rejection paths, determinism, and end-to-end composition

- [ ] 3.1 Extend `tests/gameplay/test_game_backend_session.py` to cover rejected upgrades, prerequisite failures, and traceability from gameplay effects back to explicit plant mutations or documented parameter changes.
- [ ] 3.2 Add or extend `tests/integration/test_gameplay_smoke.py` so each starter scenario can start, quote one upgrade, optionally purchase one valid upgrade, step once, and return a non-empty economics/progression summary.
- [ ] 3.3 Add `examples/dynamic_api_cli/game_backend_minimal.py` showing the canonical backend flow: start a scenario, inspect objectives, quote/purchase one upgrade, step the plant, and print a JSON-friendly summary containing `scenario_id`, `time_s`, `cash_balance`, `owned_upgrade_ids`, and the five economics fields.
- [ ] 3.4 Run the targeted matrix:
  - `uv run pytest tests/gameplay/test_contracts.py`
  - `uv run pytest tests/gameplay/test_economics.py`
  - `uv run pytest tests/gameplay/test_game_backend_session.py`
  - `uv run pytest tests/integration/test_gameplay_smoke.py`
  - `uv run python examples/dynamic_api_cli/game_backend_minimal.py`
  - `uv run pytest tests/cli/test_backend_session.py -k "session or revision or checkpoint"`
  - Expected evidence: gameplay session behavior composes the existing substrate, deterministic economics are produced, and substrate regression coverage remains green.

## Wave 4 — Sync product docs to the implemented gameplay layer

- [ ] 4.1 Update `docs/game_backend_overview.md` with the implemented gameplay-session surface and economics boundary.
- [ ] 4.2 Update `docs/plant_backend_session_user_guide.md` only as needed to point readers to the higher-level gameplay session layer without moving gameplay policy into that guide.
- [ ] 4.3 Re-run `uv run pytest tests/test_game_backend_positioning.py` after doc updates to keep repo identity and layer ownership aligned.

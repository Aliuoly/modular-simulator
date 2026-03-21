## Context

- `src/modular_simulation/cli/backend_session.py` already provides runtime editing, transactionality, preview/commit, revisions, checkpoints, and topology snapshots.
- Existing simulation layers already expose measurable plant outputs and installed assets that can support economics inputs: flows, temperatures, compositions, pressures, sensors, controllers, and line-installed equipment.
- Repo search found no existing gameplay-domain implementation for cash balances, upgrade pricing, CAPEX/OPEX summaries, progression state, staffing/fouling, or vertical integration.

## Goals / Non-Goals

**Goals**
- Define the minimal gameplay orchestration API needed to run a starter scenario.
- Keep gameplay policy above the simulation/runtime substrate.
- Make economics deterministic, auditable, and tied to plant behavior with one unambiguous phase-1 interpretation.

**Non-Goals**
- Implement long-horizon campaign systems, staffing/fouling, or multi-plant supply chains.
- Put progression or economics policy inside hydraulic solving, unit-process models, or `PlantBackendSession` itself.
- Introduce manual click-income mechanics disconnected from simulation results.

## Decisions

1. **Gameplay logic lives in a dedicated package above the simulation core.**
   - Add `src/modular_simulation/gameplay/` with these exact initial modules:
     - `contracts.py`
     - `economics.py`
     - `scenario_catalog.py`
     - `game_backend_session.py`
     - `templates/`
   - `PlantBackendSession` remains the lower-level runtime-editing substrate.

2. **The gameplay session API is intentionally small.**
   - `start_scenario(scenario_id: str, *, initial_cash: float | None = None) -> GameStateSnapshot`
   - `quote_upgrade(upgrade_id: str) -> UpgradeQuote`
   - `purchase_upgrade(upgrade_id: str) -> PurchaseResult`
   - `step_and_score(dt_s: float) -> StepScoreResult`
   - `get_progression_state() -> GameStateSnapshot`
   - The API should be sufficient for a frontend or classroom harness to run a starter scenario without exposing gameplay internals to the simulation core.
   - Rejection surface:
     - `start_scenario(...)` rejects unknown scenario ids.
     - `quote_upgrade(...)` rejects unknown upgrade ids or calls made without an active scenario.
     - `purchase_upgrade(...)` rejects `unknown_upgrade`, `already_owned`, `unmet_prerequisite`, `insufficient_cash`, and `out_of_scope`.
     - `step_and_score(...)` rejects calls made without an active scenario.
   - Required result payloads:
     - `GameStateSnapshot` includes `scenario_id`, `time_s`, `cash_balance`, `owned_upgrade_ids`, `available_upgrade_ids`, and `objective_status_by_id`.
     - `UpgradeQuote` includes `upgrade_id`, `base_cost`, `prerequisite_upgrade_ids`, `unmet_prerequisite_upgrade_ids`, `plant_changes`, and `affordable`.
     - `PurchaseResult` includes `success`, `reason_code`, and the post-attempt `GameStateSnapshot`.
     - `StepScoreResult` includes `snapshot`, `economics`, and `metric_values_by_id`.
   - `objective_status_by_id` values use a typed `ObjectiveStatus` contract with these exact fields:
     - `condition_id: str`
     - `currently_satisfied: bool`
     - `accumulated_hold_time_s: float`
     - `completed: bool`
   - Hold-timer semantics are fixed:
     - if the referenced victory condition is satisfied during a step, `accumulated_hold_time_s += dt_s`
     - otherwise `accumulated_hold_time_s = 0.0`
     - `completed` becomes `True` once `accumulated_hold_time_s >= hold_duration_s` and stays `True` for the rest of the active scenario session

3. **Economics are deterministic and simulation-derived.**
   - Required economics fields:
     - `revenue`
     - `utility_cost`
     - `equipment_capex`
     - `instrumentation_capex`
     - `operating_profit`
   - Phase-1 semantics for those fields are fixed:
     - `revenue` = step-interval product sales value over the just-completed `dt_s`.
     - `utility_cost` = step-interval utility cost over the same `dt_s`.
     - `equipment_capex` = cumulative spent-to-date purchase cost for owned upgrades in categories `line_install`, `unit_parameter`, and `topology_edit`.
     - `instrumentation_capex` = cumulative spent-to-date purchase cost for owned upgrades in category `instrumentation`.
     - `operating_profit` = `revenue - utility_cost` and explicitly excludes CAPEX.
   - Progression cash balance is updated by this exact rule:
     - on `purchase_upgrade(...)`: `cash_balance -= base_cost`
     - on `step_and_score(dt_s)`: `cash_balance += operating_profit`
   - Inputs may include throughput, composition/purity, utility proxies, and installed equipment/instrumentation inventory where relevant.
   - The formula skeleton is shared across all phase-1 scenarios; each scenario supplies explicit `EconomicsFieldDefinition` bindings declared in the starter-scenario catalog.

4. **Upgrade purchase flow must explain plant impact before mutation.**
   - `quote_upgrade(...)` must expose cost, prerequisites, and the explicit plant mutation or parameter change that would be applied.
   - `purchase_upgrade(...)` must reject unsupported, out-of-scope, or prerequisite-violating upgrades rather than silently coercing them.
   - Upgrade ids, prices, prerequisites, plant changes, success metrics, and victory conditions are authored by the starter-scenario pack and consumed here as data; this pack must not invent them.

5. **Gameplay state is local to one scenario session.**
   - Phase 1 progression state includes current cash, owned upgrades, unlocked actions, and objective status for the active scenario.
   - Cross-scenario campaign wallets, staffing rosters, and shared supply-chain inventories are deferred.

6. **Victory evaluation is data-driven from scenario-authored metrics.**
   - `step_and_score(dt_s)` computes current metric values using the active scenario’s `SuccessMetricDefinition` bindings.
   - Objective status is evaluated only from the active scenario’s `VictoryCondition` records.
   - `objective_status_by_id` stores one `ObjectiveStatus` per `VictoryCondition.condition_id` using the fixed hold-timer semantics above.
   - The gameplay-session layer may compute the values, but it does not hardcode scenario-specific victory logic outside those records.

7. **Thin substrate hooks are allowed only when composition is insufficient.**
   - If `game_backend_session.py` needs extra helpers from `PlantBackendSession`, those helpers must stay generic and free of pricing/progression policy.
   - Any helper added to `src/modular_simulation/cli/backend_session.py` must be justified by composition needs and covered by tests.

## Risks / Trade-offs

- **Economics may become arbitrary if plant-to-score mapping is vague.**
  - Mitigation: freeze the step-based field semantics and require explicit per-scenario coefficient bindings into the shared formula skeleton.
- **Gameplay session code may leak into substrate APIs.**
  - Mitigation: require quote/purchase/progression policy to live under `src/modular_simulation/gameplay/` and limit substrate changes to thin generic helpers.
- **Scenario-local progression may feel less like a full idle game.**
  - Mitigation: treat this as a phase-1 constraint that keeps implementation aligned with existing runtime capabilities.

## Verification Strategy

- TDD should lead new gameplay behavior in `tests/gameplay/` before gameplay modules are implemented.
- Required verification for implementation:
  - `uv run pytest tests/gameplay/test_contracts.py`
  - `uv run pytest tests/gameplay/test_economics.py`
  - `uv run pytest tests/gameplay/test_game_backend_session.py`
  - `uv run pytest tests/integration/test_gameplay_smoke.py`
  - `uv run python examples/dynamic_api_cli/game_backend_minimal.py`
  - `uv run pytest tests/cli/test_backend_session.py -k "session or revision or checkpoint"`
- Expected evidence:
  - economics outputs are deterministic, step-based, and expose the required field semantics,
  - upgrade quotation and purchase flows are explicit and reject unsupported actions with stable reason codes,
  - gameplay state remains scenario-local,
  - `PlantBackendSession` integration stays compositional rather than policy-owning.

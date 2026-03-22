## Context

- `src/modular_simulation/connection/runtime/connected_plant_orchestrator.py` already supports published measurement snapshots and plant calculations, which gives the gameplay layer a grounded way to consume named signals instead of scraping opaque runtime state.
- `docs/plant_backend_session_user_guide.md` and `openspec/specs/educational-backend-positioning/spec.md` already keep `PlantBackendSession` as substrate, not progression-policy owner.
- The user explicitly wants economics to own buy/sell concepts and simulation to own inventory consumption / production behavior.
- The user also explicitly rejected generic scoring; tutorials should instead track goal completion and elapsed time.

## Goals / Non-Goals

**Goals**
- Define a stable simulation-session API for one sandbox plus tutorial starts.
- Define a separate economics-ledger API for quoting, purchasing, selling, and operating-cost accrual.
- Freeze the exact phase-1 heuristic rulebook and keep the rule names user-visible.

**Non-Goals**
- Implement dynamic markets, banking, loans, staffing, or campaign systems.
- Put economics policy inside `PlantBackendSession`, runtime solving, or the unit-process classes themselves.
- Reintroduce score-based progression.

## Decisions

1. **Pack 2 separates simulation session from economics ledger.**
   - Pack 2 owns:
     - `src/modular_simulation/gameplay/sandbox_session.py`
     - `src/modular_simulation/gameplay/economics.py`
   - Pack 2 extends dependency-owned contracts in `src/modular_simulation/gameplay/contracts.py`.
   - Pack 2 consumes, but does not redefine, `sandbox_catalog.py`, `start_catalog.py`, `tutorial_catalog.py`, and `starts/`.

2. **Simulation session owns only simulation-facing state.**
   - Stable API:
     - `start_sandbox() -> SimulationSessionSnapshot`
     - `start_tutorial(tutorial_id: str) -> SimulationSessionSnapshot`
     - `install_catalog_item(item_id: str, *, config: Mapping[str, object], equipment_receipt_id: str | None = None) -> BuildApplyResult`
     - `load_feed_inventory(material_id: str, quantity_mol: float, *, procurement_receipt_id: str | None = None) -> InventoryLoadResult`
     - `advance(dt_s: float) -> SimulationAdvanceResult`
     - `withdraw_product_inventory(product_id: str, quantity_mol: float) -> InventoryWithdrawalResult`
     - `get_simulation_state() -> SimulationSessionSnapshot`
   - Invalid requests raise `SandboxRequestError(error_code: str, message: str)`.
   - Rejection surface:
     - `start_tutorial(...)` raises `SandboxRequestError` with `error_code in {"unknown_tutorial"}`.
     - `install_catalog_item(...)` raises `SandboxRequestError` with `error_code in {"no_active_session", "unknown_item", "unsupported_on_start", "invalid_config", "missing_equipment_receipt"}`.
     - `load_feed_inventory(...)` raises `SandboxRequestError` with `error_code in {"no_active_session", "unknown_material", "invalid_quantity", "missing_procurement_receipt", "tutorial_feed_loading_disabled"}`.
     - `advance(dt_s)` raises `SandboxRequestError` with `error_code in {"no_active_session", "invalid_dt_s", "insufficient_feed_inventory"}`.
     - `withdraw_product_inventory(...)` raises `SandboxRequestError` with `error_code in {"no_active_session", "unknown_product", "invalid_quantity", "insufficient_product_inventory"}`.
     - `dt_s` must be finite and strictly positive.

3. **Simulation session contracts are typed and exact.**
    - `SimulationSessionSnapshot` fields:
      - `session_kind: Literal["sandbox", "tutorial"]`
      - `active_start_id: str`
      - `active_tutorial_id: str | None`
      - `elapsed_time_s: float`
      - `tutorial_completion_time_s: float | None`
      - `installed_item_instance_ids: tuple[str, ...]`
      - `feed_inventory_by_material_id: Mapping[str, float]`
      - `product_inventory_by_product_id: Mapping[str, float]`
      - `tutorial_goal_status_by_id: Mapping[str, TutorialGoalStatus]`
   - `TutorialGoalStatus` fields:
     - `goal_id: str`
     - `completed: bool`
     - `completed_at_time_s: float | None`
   - `BuildApplyResult` fields:
     - `success: bool`
     - `reason_code: str | None`
     - `snapshot: SimulationSessionSnapshot`
   - `InventoryLoadResult` fields:
     - `success: bool`
     - `reason_code: str | None`
     - `snapshot: SimulationSessionSnapshot`
    - `InventoryWithdrawalResult` fields:
      - `withdrawal_id: str`
      - `success: bool`
      - `reason_code: str | None`
      - `withdrawn_quantity_mol: float`
      - `snapshot: SimulationSessionSnapshot`
   - `SimulationAdvanceResult` fields:
     - `snapshot: SimulationSessionSnapshot`
     - `feed_consumption_by_material_id: Mapping[str, float]`
     - `product_production_by_product_id: Mapping[str, float]`
     - `published_signal_values_by_id: Mapping[str, float]`
   - `SandboxRequestError` fields:
     - `error_code: str`
     - `message: str`

4. **Economics ledger owns all prices, quotes, and cash.**
   - Stable API:
     - `open_cash_ledger(*, initial_cash: float | None = None) -> CashLedgerSnapshot`
     - `quote_equipment_purchase(item_id: str, *, config: Mapping[str, object]) -> EconomicQuote`
     - `record_equipment_purchase(item_id: str, *, config: Mapping[str, object]) -> EquipmentPurchaseReceipt`
     - `quote_feed_purchase(material_id: str, *, quantity_mol: float) -> EconomicQuote`
     - `record_feed_purchase(material_id: str, *, quantity_mol: float) -> FeedPurchaseReceipt`
      - `quote_product_sale(product_id: str, *, quantity_mol: float) -> EconomicQuote`
      - `record_product_sale(withdrawal_id: str) -> SaleReceipt`
      - `record_operating_costs(dt_s: float, published_signal_values_by_id: Mapping[str, float]) -> OperatingCostResult`
      - `get_cash_ledger() -> CashLedgerSnapshot`
    - Rejection surface:
      - all quote/record methods raise `SandboxRequestError(error_code in {"ledger_not_open", "unknown_item", "unknown_material", "unknown_product", "invalid_quantity", "invalid_config", "invalid_dt_s", "insufficient_cash", "missing_withdrawal_id", "unknown_withdrawal_id"})` as applicable.

5. **Economics contracts are typed and exact.**
   - `EconomicQuote` fields:
     - `subject_id: str`
     - `subject_kind: Literal["equipment", "feed", "product_sale"]`
     - `quoted_amount: float`
     - `applied_rule_ids: tuple[str, ...]`
     - `affordable: bool`
   - `EquipmentPurchaseReceipt` fields:
     - `receipt_id: str`
     - `item_id: str`
     - `amount_paid: float`
   - `FeedPurchaseReceipt` fields:
     - `receipt_id: str`
     - `material_id: str`
     - `quantity_mol: float`
     - `amount_paid: float`
    - `SaleReceipt` fields:
      - `receipt_id: str`
      - `withdrawal_id: str`
      - `product_id: str`
      - `quantity_mol: float`
      - `gross_revenue: float`
   - `OperatingCostResult` fields:
     - `operating_cost_paid: float`
     - `rule_applications: tuple[HeuristicRuleApplication, ...]`
     - `cash_ledger: CashLedgerSnapshot`
   - `CashLedgerSnapshot` fields:
     - `cash_balance: float`
     - `equipment_capex_spent: float`
     - `feed_procurement_spent: float`
     - `product_sales_received: float`
     - `operating_costs_paid: float`
   - `HeuristicRuleApplication` fields:
     - `rule_id: str`
     - `rule_name: str`
     - `subject_id: str`
     - `computed_value: float`
     - `basis_snapshot: Mapping[str, float]`

6. **The one sandbox start has the default cash position.**
   - `phase1_process_sandbox_v1` default starting cash is `900.0`.
   - `open_cash_ledger(initial_cash=...)` may override it for testing or classroom orchestration.
   - Tutorials do not require a score; completion is measured by goal completion and elapsed time, not by cash gain.

7. **Phase-1 equipment pricing uses a named heuristic rulebook.**
   - `lang_factor_fluid_processing`
     - `rule_name = "Lang factor installed-cost heuristic"`
     - `formula = installed_cost = 5.8 * purchase_cost`
   - `six_tenths_scaling`
     - `rule_name = "Six-tenths scaling rule"`
     - `formula = scaled_cost = reference_cost * (size_ratio ** 0.6)`
     - phase-1 note: for frozen build items, `size_ratio = 1.0`
   - `shortcut_piping_length_cost`
     - `rule_name = "Short-cut piping estimate"`
     - `formula = 14.0 * length_m * ((2.0 * radius_m) / 0.10) ** 0.6`
   - `instrument_fixed_price_table`
     - `rule_name = "Instrument fixed-price table"`
     - fixed costs:
       - `install_sampled_delayed_sensor = 35.0`
       - `install_pid_controller = 85.0`
   - `junction_fitting_price_table`
     - `rule_name = "Junction fitting price table"`
     - fixed costs:
       - `place_merge_junction_2x1 = 36.0`
       - `place_split_junction_1x2 = 36.0`

8. **The exact equipment price table is frozen.**
   - Unit and overlay items use `lang_factor_fluid_processing` on these purchase anchors:
     - `place_heater_cooler`: purchase `25.0`, installed `145.0`
     - `place_flash_drum`: purchase `32.0`, installed `185.6`
     - `place_heat_exchanger`: purchase `58.0`, installed `336.4`
     - `place_component_separator`: purchase `42.0`, installed `243.6`
     - `install_line_pump`: purchase `20.0`, installed `116.0`
     - `install_line_valve`: purchase `12.0`, installed `69.6`
     - `install_line_heat_actuator`: purchase `18.0`, installed `104.4`
   - Junction items use `junction_fitting_price_table` directly.
   - `build_process_line` uses `shortcut_piping_length_cost` directly.
   - Instrumentation items use `instrument_fixed_price_table` directly.

9. **Feed purchase and product sale prices belong to the economics ledger.**
   - `feed_purchase_price_table`
     - `rule_name = "Feed purchase price table"`
     - `feed_a = 2.0` per mol
     - `feed_b = 3.0` per mol
   - `product_sale_price_table`
     - `rule_name = "Product sale price table"`
     - `product_a = 8.0` per mol
     - `product_b = 12.0` per mol

10. **Operating-cost heuristics are explicit and utility-named.**
   - `heating_steam_cost_heuristic`
     - `rule_name = "Heating steam cost heuristic"`
     - `formula = heating_steam_duty_W * dt_s * 0.02 / 1_000_000`
     - applies only when `heating_steam_duty_W` is published
   - `pump_electricity_cost_heuristic`
     - `rule_name = "Pump electricity cost heuristic"`
     - `formula = total_normalized_pump_load * dt_s * 0.004`
     - applies only when `total_normalized_pump_load` is published

11. **Simulation and economics stay coupled only through explicit handoffs.**
   - `install_catalog_item(...)` requires an `equipment_receipt_id` whenever a cash ledger is open.
   - `load_feed_inventory(...)` requires a `procurement_receipt_id` whenever a cash ledger is open.
   - `withdraw_product_inventory(...)` removes inventory from simulation state and returns a stable `withdrawal_id` so the economics layer can record the sale separately.
   - `record_product_sale(withdrawal_id)` consumes exactly one prior withdrawal token and may not mint product-sale cash from inventory that was never withdrawn.
   - `record_operating_costs(...)` consumes published signal maps and `dt_s`, not raw runtime internals.

12. **Tutorial completion is elapsed-time based.**
   - Tutorial goals complete when the exact required item counts are satisfied.
   - `SimulationSessionSnapshot.tutorial_completion_time_s` is `None` until all active tutorial goals are complete, then freezes the elapsed time at which the final goal completed.
   - No `score`, `points`, or automatic revenue summary is part of tutorial completion.

## Risks / Trade-offs

- **Inventory semantics are new gameplay architecture.**
  - Mitigation: keep the phase-1 surface narrow and tie inventory changes only to published signal deltas and explicit load/withdraw calls.
- **Economics could leak back into simulation APIs.**
  - Mitigation: make receipts and ledger APIs explicit and keep pricing entirely in `economics.py`.
- **Utility heuristics could still look opaque.**
  - Mitigation: use explicit names like heating steam and pump electricity rather than generic “score” or “proxy” wording.

## Verification Strategy

- TDD should lead the simulation-session and economics-ledger APIs before implementation.
- Required verification for implementation:
  - `uv run pytest tests/gameplay/test_sandbox_contracts.py`
  - `uv run pytest tests/gameplay/test_economics_ledger.py`
  - `uv run pytest tests/gameplay/test_sandbox_session.py`
  - `uv run pytest tests/gameplay/test_tutorial_timing.py`
  - `uv run pytest tests/integration/test_sandbox_session_smoke.py`
  - `uv run python examples/dynamic_api_cli/sandbox_backend_minimal.py`
  - `uv run pytest tests/cli/test_backend_session.py -k "session or revision or checkpoint"`
- Expected evidence:
  - simulation state tracks feed consumption and product accumulation without embedding pricing,
  - economics quotes and receipts expose named heuristic rule applications,
  - tutorials complete on goals plus elapsed time rather than score,
  - the cash ledger and simulation inventory interact only through explicit receipt and withdrawal handoffs,
  - `PlantBackendSession` remains a composed substrate rather than a gameplay-policy owner.

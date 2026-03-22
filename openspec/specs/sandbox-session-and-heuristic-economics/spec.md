# Sandbox Session And Heuristic Economics

## Purpose

This capability defines the phase-1 gameplay split between the simulation session and the separate economics ledger, including stable APIs, stable handoff contracts, frozen engineering-economics heuristics, and tutorial timing semantics.

## Requirements

### Requirement: Simulation Session And Economics Ledger Are Separate
Phase-1 gameplay SHALL keep the simulation session separate from the economics ledger.

#### Scenario: Simulation layer does not own prices
- **WHEN** a contributor inspects the phase-1 gameplay APIs
- **THEN** buy/sell/quote/cash behavior belongs to the economics ledger and the simulation session owns only starts, installs, inventory loading, advancing, withdrawal, and state reads

### Requirement: Simulation Session API Is Stable
The simulation layer SHALL expose exactly `start_sandbox()`, `start_tutorial(tutorial_id)`, `install_catalog_item(...)`, `load_feed_inventory(...)`, `advance(dt_s)`, `withdraw_product_inventory(...)`, and `get_simulation_state()`.

#### Scenario: Sandbox startup uses the one frozen sandbox start
- **WHEN** a caller requests `start_sandbox()`
- **THEN** the session starts `phase1_process_sandbox_v1`

#### Scenario: Tutorial startup uses the tutorial’s bound start
- **WHEN** a caller requests `start_tutorial("heater_flash_guided_build_v1")`
- **THEN** the session starts `heater_flash_tutorial_start_v1` and not the free-play sandbox

### Requirement: Simulation Errors Use Stable Request Codes
Invalid non-purchase simulation requests SHALL raise `SandboxRequestError` with stable `error_code` values.

#### Scenario: Invalid install requests are rejected
- **WHEN** a caller requests `install_catalog_item(...)` without an active session, with an unknown item id, with an unsupported start, with invalid config, or without an equipment receipt while a ledger is active
- **THEN** the session raises `SandboxRequestError` with `error_code` in `{"no_active_session", "unknown_item", "unsupported_on_start", "invalid_config", "missing_equipment_receipt"}`

#### Scenario: Invalid feed loads are rejected
- **WHEN** a caller requests `load_feed_inventory(...)` with an unknown material, invalid quantity, missing procurement receipt while a ledger is active, or during a tutorial that disables feed loading
- **THEN** the session raises `SandboxRequestError` with `error_code` in `{"no_active_session", "unknown_material", "invalid_quantity", "missing_procurement_receipt", "tutorial_feed_loading_disabled"}`

#### Scenario: Invalid step sizes are rejected
- **WHEN** a caller requests `advance(dt_s)` with `dt_s <= 0.0`, `NaN`, or infinity
- **THEN** the session raises `SandboxRequestError(error_code="invalid_dt_s", ...)`

#### Scenario: Unknown tutorials are rejected
- **WHEN** a caller requests `start_tutorial("unknown_tutorial")`
- **THEN** the session raises `SandboxRequestError(error_code="unknown_tutorial", ...)`

#### Scenario: Insufficient feed inventory is rejected on advance
- **WHEN** a caller requests `advance(dt_s)` without enough loaded feed inventory for the required simulation step
- **THEN** the session raises `SandboxRequestError(error_code="insufficient_feed_inventory", ...)`

#### Scenario: Invalid product withdrawals are rejected
- **WHEN** a caller requests `withdraw_product_inventory(...)` without an active session, with an unknown product id, with invalid quantity, or with insufficient product inventory
- **THEN** the session raises `SandboxRequestError` with `error_code` in `{"no_active_session", "unknown_product", "invalid_quantity", "insufficient_product_inventory"}`

### Requirement: Simulation Session Tracks Inventory And Tutorial Time, Not Score
The simulation session SHALL track feed inventory, product inventory, tutorial goal status, and elapsed time, and SHALL not expose any score field.

#### Scenario: Tutorial completion reports elapsed time only
- **WHEN** a tutorial reaches all of its frozen goals
- **THEN** completion is reported from goal status plus `tutorial_completion_time_s` on the simulation snapshot and no score/points field is introduced

### Requirement: The Simulation Contracts Are Stable
`SimulationSessionSnapshot`, `TutorialGoalStatus`, `BuildApplyResult`, `InventoryLoadResult`, `InventoryWithdrawalResult`, `SimulationAdvanceResult`, and `SandboxRequestError` SHALL expose these exact fields and types:
- `SimulationSessionSnapshot`: `session_kind: Literal["sandbox", "tutorial"]`, `active_start_id: str`, `active_tutorial_id: str | None`, `elapsed_time_s: float`, `tutorial_completion_time_s: float | None`, `installed_item_instance_ids: tuple[str, ...]`, `feed_inventory_by_material_id: Mapping[str, float]`, `product_inventory_by_product_id: Mapping[str, float]`, `tutorial_goal_status_by_id: Mapping[str, TutorialGoalStatus]`
- `TutorialGoalStatus`: `goal_id: str`, `completed: bool`, `completed_at_time_s: float | None`
- `BuildApplyResult`: `success: bool`, `reason_code: str | None`, `snapshot: SimulationSessionSnapshot`
- `InventoryLoadResult`: `success: bool`, `reason_code: str | None`, `snapshot: SimulationSessionSnapshot`
- `InventoryWithdrawalResult`: `withdrawal_id: str`, `success: bool`, `reason_code: str | None`, `withdrawn_quantity_mol: float`, `snapshot: SimulationSessionSnapshot`
- `SimulationAdvanceResult`: `snapshot: SimulationSessionSnapshot`, `feed_consumption_by_material_id: Mapping[str, float]`, `product_production_by_product_id: Mapping[str, float]`, `published_signal_values_by_id: Mapping[str, float]`
- `SandboxRequestError`: `error_code: str`, `message: str`

#### Scenario: Simulation contract shapes are fixed
- **WHEN** a contributor inspects the pack-2 contracts
- **THEN** those types expose exactly those fields and no pricing fields appear on the simulation-side result types

### Requirement: Economics Ledger API Is Stable
The economics layer SHALL expose exactly `open_cash_ledger(...)`, `quote_equipment_purchase(...)`, `record_equipment_purchase(...)`, `quote_feed_purchase(...)`, `record_feed_purchase(...)`, `quote_product_sale(...)`, `record_product_sale(withdrawal_id)`, `record_operating_costs(...)`, and `get_cash_ledger()`.

#### Scenario: Economics layer owns quotes and receipts
- **WHEN** a caller inspects the economics API
- **THEN** equipment purchases, feed procurement, product sales, and operating-cost accrual all originate there rather than in the simulation session

### Requirement: Economics Errors Use Stable Request Codes
Invalid economics requests SHALL raise `SandboxRequestError` with stable `error_code` values.

#### Scenario: Invalid ledger calls are rejected
- **WHEN** a caller quotes or records an unknown item/material/product, uses invalid quantity or config, calls before the ledger is open, provides invalid `dt_s`, exceeds cash balance, omits a required `withdrawal_id`, or supplies an unknown withdrawal token
- **THEN** the economics layer raises `SandboxRequestError` with `error_code` in `{"ledger_not_open", "unknown_item", "unknown_material", "unknown_product", "invalid_quantity", "invalid_config", "invalid_dt_s", "insufficient_cash", "missing_withdrawal_id", "unknown_withdrawal_id"}` as applicable

### Requirement: Economics Contracts Are Stable
`EconomicQuote`, `EquipmentPurchaseReceipt`, `FeedPurchaseReceipt`, `SaleReceipt`, `OperatingCostResult`, `CashLedgerSnapshot`, and `HeuristicRuleApplication` SHALL expose these exact fields and types:
- `EconomicQuote`: `subject_id: str`, `subject_kind: Literal["equipment", "feed", "product_sale"]`, `quoted_amount: float`, `applied_rule_ids: tuple[str, ...]`, `affordable: bool`
- `EquipmentPurchaseReceipt`: `receipt_id: str`, `item_id: str`, `amount_paid: float`
- `FeedPurchaseReceipt`: `receipt_id: str`, `material_id: str`, `quantity_mol: float`, `amount_paid: float`
- `SaleReceipt`: `receipt_id: str`, `withdrawal_id: str`, `product_id: str`, `quantity_mol: float`, `gross_revenue: float`
- `OperatingCostResult`: `operating_cost_paid: float`, `rule_applications: tuple[HeuristicRuleApplication, ...]`, `cash_ledger: CashLedgerSnapshot`
- `CashLedgerSnapshot`: `cash_balance: float`, `equipment_capex_spent: float`, `feed_procurement_spent: float`, `product_sales_received: float`, `operating_costs_paid: float`
- `HeuristicRuleApplication`: `rule_id: str`, `rule_name: str`, `subject_id: str`, `computed_value: float`, `basis_snapshot: Mapping[str, float]`

#### Scenario: Economics contract shapes are fixed
- **WHEN** a contributor inspects the economics-ledger contracts
- **THEN** those types expose exactly those fields and `SaleReceipt` carries the `withdrawal_id` used for the product-sale handoff

### Requirement: The Exact Phase-1 Heuristic Rulebook Is Frozen
The gameplay layer SHALL use exactly these rule ids and educational names:
- `lang_factor_fluid_processing` / `Lang factor installed-cost heuristic`
- `six_tenths_scaling` / `Six-tenths scaling rule`
- `shortcut_piping_length_cost` / `Short-cut piping estimate`
- `instrument_fixed_price_table` / `Instrument fixed-price table`
- `junction_fitting_price_table` / `Junction fitting price table`
- `feed_purchase_price_table` / `Feed purchase price table`
- `product_sale_price_table` / `Product sale price table`
- `heating_steam_cost_heuristic` / `Heating steam cost heuristic`
- `pump_electricity_cost_heuristic` / `Pump electricity cost heuristic`

#### Scenario: Equipment rulebook entries are frozen
- **WHEN** a contributor inspects the sandbox economics rule definitions
- **THEN** `lang_factor_fluid_processing = 5.8 * purchase_cost`, `six_tenths_scaling = reference_cost * (size_ratio ** 0.6)` with `size_ratio = 1.0` for frozen build items, `instrument_fixed_price_table` uses fixed costs `35.0` for `install_sampled_delayed_sensor` and `85.0` for `install_pid_controller`, and `junction_fitting_price_table` uses fixed costs `36.0` for both `place_merge_junction_2x1` and `place_split_junction_1x2`

### Requirement: The Exact Equipment Price Table Is Frozen
The economics ledger SHALL use these exact phase-1 equipment anchors:
- `place_heater_cooler = 25.0 / 145.0`
- `place_flash_drum = 32.0 / 185.6`
- `place_heat_exchanger = 58.0 / 336.4`
- `place_component_separator = 42.0 / 243.6`
- `install_line_pump = 20.0 / 116.0`
- `install_line_valve = 12.0 / 69.6`
- `install_line_heat_actuator = 18.0 / 104.4`
- `build_process_line = 14.0 * length_m * ((2.0 * radius_m) / 0.10) ** 0.6`

#### Scenario: Equipment quotes are frozen exactly
- **WHEN** the economics layer quotes one of those build items
- **THEN** the quoted amount uses the exact anchor or formula above and exposes the corresponding heuristic rule ids

### Requirement: The Exact Feed And Product Price Tables Are Frozen
The economics ledger SHALL use `feed_purchase_price_table` with `feed_a = 2.0` per mol and `feed_b = 3.0` per mol, and `product_sale_price_table` with `product_a = 8.0` per mol and `product_b = 12.0` per mol.

#### Scenario: Feed and product ledger prices are frozen exactly
- **WHEN** a caller quotes feed procurement or product sales
- **THEN** the quoted amount uses those exact per-mol prices and not a simulation-owned formula

### Requirement: The Exact Operating-Cost Rules Are Frozen
The economics ledger SHALL use these exact operating-cost formulas:
- `heating_steam_cost_heuristic = heating_steam_duty_W * dt_s * 0.02 / 1_000_000`
- `pump_electricity_cost_heuristic = total_normalized_pump_load * dt_s * 0.004`

#### Scenario: Operating-cost signal applicability is frozen
- **WHEN** operating-cost rules are applied
- **THEN** `heating_steam_cost_heuristic` consumes `heating_steam_duty_W` only when that signal is published, and `pump_electricity_cost_heuristic` consumes `total_normalized_pump_load` only when that signal is published

### Requirement: The One Sandbox Has The Default Cash Position
The economics ledger SHALL default to `900.0` starting cash for `phase1_process_sandbox_v1` unless `open_cash_ledger(initial_cash=...)` explicitly overrides it.

#### Scenario: Default sandbox cash is frozen
- **WHEN** a caller opens the cash ledger without an override
- **THEN** the starting cash balance is exactly `900.0`

### Requirement: Simulation/Economics Handoffs Are Explicit
The simulation and economics layers SHALL interact only through explicit receipts, inventory loads, inventory withdrawals, and published-signal operating-cost calls.

#### Scenario: Equipment install requires a ledger receipt when cash is active
- **WHEN** a cash ledger is open and a caller installs a catalog item
- **THEN** the simulation layer requires an `equipment_receipt_id` instead of recomputing or hiding pricing logic

#### Scenario: Product sale requires withdrawal before cash credit
- **WHEN** a caller wants to sell product inventory
- **THEN** the product quantity is first withdrawn from simulation inventory, `withdraw_product_inventory(...)` returns a stable `withdrawal_id`, and `record_product_sale(withdrawal_id)` uses that exact token rather than auto-selling during `advance(dt_s)`

#### Scenario: Product-sale withdrawal tokens are single-use
- **WHEN** a caller records a product sale with a valid `withdrawal_id` and then attempts to reuse the same token
- **THEN** the first sale succeeds once and the replay is rejected with `SandboxRequestError(error_code="unknown_withdrawal_id", ...)`

### Requirement: Dependency-Owned Catalog And Starts Remain Read-Only
The sandbox-session and economics layer SHALL consume the sandbox catalog, start catalog, tutorial catalog, and start builders from the dependency pack rather than redefining item ids, start ids, published signals, or tutorial goals.

#### Scenario: Ownership remains consistent across packs
- **WHEN** a contributor inspects the build-catalog pack and the pack-2 implementation
- **THEN** item ids, start ids, tutorial bindings, and published signal ids originate in the dependency pack and pack 2 uses them as read-only inputs

### Requirement: PlantBackendSession Remains Free Of Gameplay Policy
Any changes to `PlantBackendSession` made to support sandbox composition SHALL remain generic substrate hooks and SHALL not own sandbox pricing, tutorial timing, or economics policy.

#### Scenario: Sandbox integration preserves substrate ownership boundaries
- **WHEN** the sandbox session implementation requires backend-session support
- **THEN** any added substrate helpers remain generic and all gameplay policy continues to live under `src/modular_simulation/gameplay/`

### Requirement: Higher Layers Consume Substrate-Owned Observability Reads
The sandbox session and economics ledger SHALL consume substrate-owned observability snapshot surfaces for physical-state reads rather than reconstructing those reads from low-level runtime internals.

#### Scenario: Economics-facing observability stays separated from policy
- **WHEN** higher-layer code needs runtime observability for educational signals or future economics rollups
- **THEN** those reads come from the substrate-owned snapshot API and not from pricing, tutorial, or ledger logic being pushed down into `PlantBackendSession` or other substrate internals

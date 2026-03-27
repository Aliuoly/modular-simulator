# Economics

## Purpose

This capability defines economics-ledger behavior for phase-1 gameplay, including stable ledger APIs, stable request errors, contract shapes, frozen pricing heuristics, and explicit handoffs with the simulation session.

## Requirements

### Requirement: Simulation Session And Economics Ledger Are Separate
Phase-1 gameplay SHALL keep the simulation session separate from the economics ledger.

#### Scenario: Simulation layer does not own prices
- **WHEN** a contributor inspects the phase-1 gameplay APIs
- **THEN** buy/sell/quote/cash behavior belongs to the economics ledger and the simulation session owns only starts, installs, inventory loading, advancing, withdrawal, and state reads

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
The economics ledger SHALL expose one default pricing policy for this pack and that policy SHALL use these exact frozen gameplay equipment price anchors:

- retained legacy tutorial-facing items:
  - `place_heater_cooler = 25.0 / 145.0`
  - `place_flash_drum = 32.0 / 185.6`
  - `place_heat_exchanger = 58.0 / 336.4`
  - `place_component_separator = 42.0 / 243.6`
  - `install_line_pump = 20.0 / 116.0`
  - `install_line_valve = 12.0 / 69.6`
  - `install_line_heat_actuator = 18.0 / 104.4`
- gas-first main-world items:
  - `place_inlet_gas_separator = 32.0 / 185.6`
  - `place_teg_contactor = 42.0 / 243.6`
  - `place_rich_glycol_flash_tank = 32.0 / 185.6`
  - `place_lean_rich_glycol_exchanger = 58.0 / 336.4`
  - `place_teg_regenerator = 76.0 / 440.8`
  - `install_glycol_circulation_pump = 20.0 / 116.0`
  - `place_gas_gas_exchanger = 58.0 / 336.4`
  - `install_jt_valve = 12.0 / 69.6`
  - `place_low_temperature_separator = 32.0 / 185.6`
  - `place_condensate_stabilizer = 76.0 / 440.8`
- shared line item:
  - `build_process_line = 14.0 * length_m * ((2.0 * radius_m) / 0.10) ** 0.6`

These equipment prices are educational gameplay anchors chosen to preserve stable build tradeoffs in the first gas-world slice. They SHALL NOT be described as purchased-equipment estimates, Lang-factor plant CAPEX predictions, or real-facility cost correlations. Only `build_process_line` keeps the named length/size scaling rule as a gameplay heuristic.

The default pricing policy SHALL remain an internal economics concern: gameplay/session/API/client contracts SHALL continue to speak in item ids, material ids, product ids, and quotes rather than taking a hard dependency on fixed-price table internals.

#### Scenario: Gas and tutorial equipment quotes are frozen as gameplay anchors
- **WHEN** the economics layer quotes one of those build items
- **THEN** the quoted amount uses the exact anchor or formula above and exposes the corresponding heuristic rule ids

### Requirement: The Exact Feed And Product Price Tables Are Frozen
The default pricing policy SHALL use these exact fixed educational feed and product price tables:

- retained legacy ids:
  - `feed_a = 2.0`
  - `feed_b = 3.0`
  - `product_a = 8.0`
  - `product_b = 12.0`
- gas-first main sandbox ids:
  - `sweet_wet_gas = 2.5`
  - `separator_gas = 6.0`
  - `unstabilized_condensate = 8.0`
  - `dry_gas = 9.0`
  - `ngl_liquids = 12.0`
  - `stabilized_condensate = 10.0`

#### Scenario: Gas-first feed and product prices are frozen as educational sale/procurement anchors
- **WHEN** a caller quotes main-sandbox gas feed procurement or gas-product sales
- **THEN** the quoted amount uses those exact per-mol prices and not a simulation-owned formula, market model, or plant-economics estimator

### Requirement: The Default Fixed-Price Policy Preserves A Future Pricing Seam
The economics implementation SHALL route quote behavior through a narrow default pricing-policy seam so later dynamic pricing can be added without rewriting the gameplay/session/API/client contracts for this pack.

#### Scenario: Quote callers depend on policy output, not hard-wired tables
- **WHEN** a contributor inspects `quote_equipment_purchase(...)`, `quote_feed_purchase(...)`, `quote_product_sale(...)`, or the parallel `CashLedgerRuntime` methods
- **THEN** each caller obtains prices through the shared default pricing-policy seam rather than duplicating or inlining separate fixed-table lookups in each call site

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

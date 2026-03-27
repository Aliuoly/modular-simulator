## MODIFIED Requirements

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
- **WHEN** the economics layer quotes one of those live build items
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

### Requirement: The One Sandbox Has The Default Cash Position
The economics ledger SHALL default to `900.0` starting cash for `phase1_process_sandbox_v1` unless `open_cash_ledger(initial_cash=...)` explicitly overrides it.

#### Scenario: Default sandbox cash remains stable across the gas-first content swap
- **WHEN** a caller opens the cash ledger without an override for the default sandbox
- **THEN** the starting cash balance is exactly `900.0`

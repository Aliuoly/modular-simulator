## MODIFIED Requirements

### Requirement: Simulation Session API Is Stable
The simulation layer SHALL expose exactly `start_sandbox()`, `start_tutorial(tutorial_id)`, `install_catalog_item(...)`, `load_feed_inventory(...)`, `advance(dt_s)`, `withdraw_product_inventory(...)`, `submit_research_unlock(...)`, and `get_simulation_state()`.

#### Scenario: Sandbox startup still uses the stable default sandbox id
- **WHEN** a caller requests `start_sandbox()`
- **THEN** the session starts `phase1_process_sandbox_v1`, now defined as the gas-first main sandbox

### Requirement: Simulation Errors Use Stable Request Codes
Invalid non-purchase simulation requests SHALL raise `SandboxRequestError` with stable `error_code` values.

#### Scenario: Invalid install requests are rejected
- **WHEN** a caller requests `install_catalog_item(...)` without an active session, with an unknown item id, with an unsupported start, with a supported-but-locked item, with invalid config, or without an equipment receipt while a ledger is active
- **THEN** the session raises `SandboxRequestError` with `error_code` in `{"no_active_session", "unknown_item", "unsupported_on_start", "item_locked", "invalid_config", "missing_equipment_receipt"}`

#### Scenario: Rejected simulation install requests are side-effect free
- **WHEN** `install_catalog_item(...)` rejects a request with `unknown_item`, `unsupported_on_start`, `item_locked`, or `invalid_config`
- **THEN** the simulation session leaves its progression state, inventory state, and elapsed-time state unchanged

#### Scenario: Invalid research submissions are rejected
- **WHEN** a caller requests `submit_research_unlock(...)` without an active session, during a tutorial session, with an unknown research id, with a research id that is not currently available, with invalid submitted quantities, or with insufficient product inventory
- **THEN** the session raises `SandboxRequestError` with `error_code` in `{"no_active_session", "research_unavailable_for_session", "unknown_research_unlock", "research_not_available", "invalid_quantity", "insufficient_product_inventory"}`

#### Scenario: Rejected research submissions do not consume inventory
- **WHEN** `submit_research_unlock(...)` rejects a research request for any reason
- **THEN** the session leaves product inventory and unlocked stage state unchanged

### Requirement: The Simulation Contracts Are Stable
`SimulationSessionSnapshot`, `ProgressionSnapshot`, `ResearchSubmissionResult`, `TutorialGoalStatus`, `BuildApplyResult`, `InventoryLoadResult`, `InventoryWithdrawalResult`, `SimulationAdvanceResult`, and `SandboxRequestError` SHALL expose these exact fields and types:
- `SimulationSessionSnapshot`: existing live fields plus `progression_snapshot: ProgressionSnapshot | None`
- `ProgressionSnapshot`: `active_stage_id: str | None`, `unlocked_stage_ids: tuple[str, ...]`, `available_item_ids: tuple[str, ...]`, `available_research_ids: tuple[str, ...]`
- `ResearchSubmissionResult`: `success: bool`, `reason_code: str | None`, `snapshot: SimulationSessionSnapshot`

#### Scenario: Progression-aware simulation contracts are fixed
- **WHEN** a contributor inspects the simulation session contracts
- **THEN** the progression state required by the gas-first ladder is present on the authoritative simulation snapshot and no separate unlock-only side channel is required

#### Scenario: Research submission result is success-only
- **WHEN** `submit_research_unlock(...)` succeeds
- **THEN** it returns `ResearchSubmissionResult(success=True, reason_code=None, snapshot=...)`
- **AND** invalid or unavailable research submissions continue to raise `SandboxRequestError` instead of returning a failed result object

### Requirement: Simulation Session Tracks Progression State For The Main Sandbox
The simulation session SHALL track main-world progression state for `phase1_process_sandbox_v1`, SHALL initialize the starter batch on sandbox start, and SHALL keep tutorial sessions progression-free.

#### Scenario: Starter stage is available immediately in the main sandbox
- **WHEN** a caller starts the main sandbox and inspects the resulting simulation snapshot
- **THEN** the progression snapshot reports `active_stage_id = "teg_dehydration_v1"`, `unlocked_stage_ids = ("gas_inlet_separation_v1", "teg_dehydration_v1")`, and the available item ids are exactly the starter-batch items frozen by the progression spec
- **AND** `available_research_ids = ("unlock_cold_recovery_train_v1",)` so the batched milestone is visible from sandbox start

#### Scenario: Tutorial snapshots do not claim main-world progression
- **WHEN** a caller starts a tutorial and inspects the resulting simulation snapshot
- **THEN** `progression_snapshot` is `None` and tutorial mode remains separate from the main unlock ladder

#### Scenario: Successful unlock yields the exact cold-recovery snapshot
- **WHEN** `submit_research_unlock("unlock_cold_recovery_train_v1", ...)` succeeds in `phase1_process_sandbox_v1`
- **THEN** the resulting `progression_snapshot` matches exactly:
  - `active_stage_id = "condensate_stabilization_v1"`
  - `unlocked_stage_ids = ("gas_inlet_separation_v1", "teg_dehydration_v1", "jt_low_temperature_separation_v1", "condensate_stabilization_v1")`
  - `available_item_ids = ("place_inlet_gas_separator", "place_teg_contactor", "place_rich_glycol_flash_tank", "place_lean_rich_glycol_exchanger", "place_teg_regenerator", "install_glycol_circulation_pump", "place_gas_gas_exchanger", "install_jt_valve", "place_low_temperature_separator", "place_condensate_stabilizer", "build_process_line")`
  - `available_research_ids = ()`

### Requirement: Main-Sandbox Inventory Ids Are Gas-First And Fixed
For `phase1_process_sandbox_v1`, the simulation session SHALL accept exactly `sweet_wet_gas` as the purchasable feed id and SHALL expose exactly these product inventory ids: `separator_gas`, `unstabilized_condensate`, `dry_gas`, `ngl_liquids`, and `stabilized_condensate`.

#### Scenario: Main sandbox inventory ids are exact on startup
- **WHEN** a caller starts the main sandbox and inspects the resulting simulation snapshot
- **THEN** `feed_inventory_by_material_id` contains exactly `sweet_wet_gas`
- **AND** `product_inventory_by_product_id` contains exactly `separator_gas`, `unstabilized_condensate`, `dry_gas`, `ngl_liquids`, and `stabilized_condensate`

### Requirement: Main-Sandbox Product Generation Requires Qualifying Connected Proxy Paths
The main sandbox SHALL generate gas products only from qualifying connected topology. Research unlock state alone SHALL NOT create product inventory.

- `separator_gas` requires a connected path from the `sweet_wet_gas` feed boundary through an installed `place_inlet_gas_separator` to the `separator_gas` sink.
- `unstabilized_condensate` requires a connected path from the `sweet_wet_gas` feed boundary through an installed `place_inlet_gas_separator` to the `unstabilized_condensate` sink.
- `dry_gas` requires:
  - a connected path from the inlet-separator gas path through an installed `place_teg_contactor` to the `dry_gas` sink, and
  - support-package proxies `place_rich_glycol_flash_tank`, `place_lean_rich_glycol_exchanger`, `place_teg_regenerator`, and `install_glycol_circulation_pump` connected within the same dehydration-package topology / connected component as that qualifying contactor path.
- `ngl_liquids` requires a connected path in this order: inlet-separator gas path → `place_teg_contactor` → `place_gas_gas_exchanger` → a line with `install_jt_valve` immediately upstream of `place_low_temperature_separator` → `ngl_liquids` sink.
- `stabilized_condensate` requires a connected path from the inlet-separator liquid path through `place_condensate_stabilizer` to the `stabilized_condensate` sink; it SHALL NOT require public product-inventory refeed or public tank ids.
- Earlier products remain producible after later unlocks if their own qualifying path still exists.
- Duplicate parallel qualifying paths for the same product id do not stack production credit in this pack.

#### Scenario: Unlock alone does not create downstream products
- **WHEN** a research unlock succeeds but no newly qualifying downstream path has been installed and connected
- **THEN** advancing the session does not create the downstream product inventory for that stage

#### Scenario: Earlier products remain producible after later unlocks
- **WHEN** the player unlocks later stages but keeps an earlier product’s qualifying path connected
- **THEN** advancing the session may still produce that earlier product alongside later-stage products

#### Scenario: Disconnected dehydration support items do not qualify dry gas
- **WHEN** `place_rich_glycol_flash_tank`, `place_lean_rich_glycol_exchanger`, `place_teg_regenerator`, or `install_glycol_circulation_pump` are installed outside the qualifying dehydration-package connected component
- **THEN** advancing the session does not produce `dry_gas` from that contactor path

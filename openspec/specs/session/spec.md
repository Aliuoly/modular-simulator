# Session

## Purpose

This capability defines simulation session behavior for phase-1 gameplay, including stable session APIs, stable request errors, inventory and tutorial-time state, and session-side contracts.

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

### Requirement: Invalid Install Requests Include Metadata-Resolution Failures
Phase-1 gameplay SHALL treat invalid runtime-authoritative unit metadata resolution during realtime build placement as an `invalid_config` request failure rather than leaking raw internal exceptions.

#### Scenario: Invalid unit metadata import fails as invalid_config
- **WHEN** a build request targets a `unit_blueprint` record whose configured `unit_module` target cannot be resolved during runtime-authoritative metadata resolution
- **THEN** the session/gameplay layer raises `SandboxRequestError(error_code="invalid_config", ...)`
- **AND** the failure does not escape as a raw module-target resolution exception to callers

#### Scenario: Invalid unit metadata type lookup fails as invalid_config
- **WHEN** a build request targets a `unit_blueprint` record whose configured `unit_type` is missing from the imported module during runtime-authoritative metadata resolution
- **THEN** the session/gameplay layer raises `SandboxRequestError(error_code="invalid_config", ...)`
- **AND** the failure does not escape as a raw attribute lookup exception to callers

#### Scenario: Invalid constructor payload fails as invalid_config
- **WHEN** a build request targets a `unit_blueprint` record whose `constructor_payload` causes constructor-time validation failure while deriving declared ports
- **THEN** the session/gameplay layer raises `SandboxRequestError(error_code="invalid_config", ...)`
- **AND** the failure does not escape as a raw constructor exception to callers

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
- **WHEN** a contributor inspects the simulation session contracts
- **THEN** those types expose exactly those fields and no pricing fields appear on the simulation-side result types

### Requirement: Dependency-Owned Catalog And Starts Remain Read-Only
The sandbox-session and economics layer SHALL consume the sandbox catalog, start catalog, tutorial catalog, and start builders from the owning catalog capability rather than redefining item ids, start ids, published signals, or tutorial goals.

#### Scenario: Ownership remains consistent across capabilities
- **WHEN** a contributor inspects the catalog/source capability and the simulation session implementation
- **THEN** item ids, start ids, tutorial bindings, and published signal ids originate in the dependency-owned catalogs and the session layer uses them as read-only inputs

### Requirement: PlantBackendSession Remains Free Of Gameplay Policy
Any changes to `PlantBackendSession` made to support sandbox composition SHALL remain generic substrate hooks and SHALL not own sandbox pricing, tutorial timing, or economics policy.

#### Scenario: Sandbox integration preserves substrate ownership boundaries
- **WHEN** the sandbox session implementation requires backend-session support
- **THEN** any added substrate helpers remain generic and all gameplay policy continues to live under `src/modular_simulation/gameplay/`

### Requirement: Higher Layers Consume Substrate-Owned Observability Reads
The sandbox session and economics ledger SHALL consume substrate-owned observability snapshot surfaces for physical-state reads, including tank/process holdup reads, rather than reconstructing those reads from low-level runtime internals or gameplay-owned inventory mirrors.

#### Scenario: Economics-facing observability stays separated from policy
- **WHEN** higher-layer code needs runtime observability for educational signals or future economics rollups
- **THEN** those reads come from the substrate-owned snapshot API and not from pricing, tutorial, or ledger logic being pushed down into `PlantBackendSession` or other substrate internals

#### Scenario: Tank state reads use observability rather than gameplay custody
- **WHEN** higher-layer code needs holding-tank holdup, composition, or outlet-flow information
- **THEN** those reads come from the substrate-owned observability snapshot
- **AND** gameplay/session code does not maintain a mirrored tank inventory record with conserved amount or mixed thermodynamic state.

### Requirement: Gameplay Tank Metadata Remains Non-Physical And Non-Public
Phase-1 gameplay SHALL NOT maintain a session-owned mirror of simulation-owned holding-tank conserved inventory or mixed thermodynamic state. Any future gameplay-owned tank metadata introduced above the substrate MAY track only non-physical route or UI intent keyed by tank `process_id`, and SHALL remain non-public.

#### Scenario: Physical tank state is not mirrored in gameplay
- **WHEN** contributors inspect gameplay/session code after `ej7.1`
- **THEN** gameplay does not store per-tank conserved amount, mixed composition, or aggregate thermodynamic state outside the substrate runtime
- **AND** stale helpers such as gameplay-owned `tank_custody.py` are not the authoritative source of tank physical state.

#### Scenario: Public session contracts stay unchanged in ej7.1
- **WHEN** contributors inspect simulation-session methods and snapshots
- **THEN** no new public tank methods, tank snapshot fields, or build/start widenings are introduced by this pack
- **AND** higher-layer tank reads remain observability-driven until a later change explicitly widens gameplay contracts.

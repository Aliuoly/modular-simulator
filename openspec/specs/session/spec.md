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
The simulation layer SHALL expose exactly `start_sandbox()`, `start_tutorial(tutorial_id)`, `install_catalog_item(...)`, `load_feed_inventory(...)`, `advance(dt_s)`, `withdraw_product_inventory(...)`, `submit_research_unlock(...)`, and `get_simulation_state()`.

#### Scenario: Sandbox startup still uses the stable default sandbox id
- **WHEN** a caller requests `start_sandbox()`
- **THEN** the session starts `phase1_process_sandbox_v1`, now defined as the gas-first main sandbox

#### Scenario: Tutorial startup uses the tutorial’s bound start
- **WHEN** a caller requests `start_tutorial("heater_flash_guided_build_v1")`
- **THEN** the session starts `heater_flash_tutorial_start_v1` and not the free-play sandbox

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

### Requirement: Public Gameplay Build Routing Uses Stable Family Dispatch
The phase-1 gameplay build surface SHALL route the currently public playable build families through stable family dispatch rather than exact heater/flash-only item-id branches.

This widened `add_process` exposure remains a gameplay placement/build-surface change only; it does not introduce runtime-backed separator behavior in the current topology-only slice.

#### Scenario: Public sandbox add-process items share one gameplay build family
- **WHEN** a sandbox build request targets `place_heater_cooler`, `place_flash_drum`, or `place_heat_exchanger`
- **THEN** the gameplay layer routes all three through the same public `add_process` family behavior
- **AND** the request continues to use the stable `build(...)` command shape with `process_id` plus layout anchor metadata rather than new per-item public methods.

#### Scenario: Successful widened add-process builds preserve existing install orchestration
- **WHEN** a sandbox build request targets one of the newly public `add_process` items
- **THEN** the gameplay layer still records equipment purchase and calls `install_catalog_item(...)` on the stable gameplay build path
- **AND** no parallel install-count or tutorial-tracking path is introduced for those widened items.

### Requirement: Public Gameplay Line Building Uses Explicit Endpoint Strings
The phase-1 gameplay build surface SHALL keep `build(item_id="build_process_line", config, layout)` on the existing route, but interpret `config.source` and `config.target` as exact topology endpoints rather than inferred process ids.

#### Scenario: Boundary and process-port endpoints use the same stable build route
- **WHEN** a sandbox build request targets `build_process_line`
- **THEN** feed/product boundaries continue to use bare boundary ids such as `feed_a` or `product_a`
- **AND** all non-boundary process endpoints use explicit `<process_id>.<port_name>` strings such as `heater_1.inlet`, `flash_1.vapor_outlet`, or `heat_exchanger_1.hot_outlet`
- **AND** no new public route or top-level payload field is introduced for line building.

#### Scenario: Ambiguous or invalid process endpoints are rejected stably
- **WHEN** a build request uses a bare non-boundary process id, an unknown endpoint id, an unknown port name, malformed endpoint text, or a wrong-direction endpoint for `build_process_line`
- **THEN** the gameplay layer rejects the request with stable `SandboxRequestError(error_code="invalid_config", ...)`
- **AND** the rejected request leaves topology, board layout, install counts, and cash unchanged.

### Requirement: Deferred Public Families Stay Outside The Current Playable Slice
Phase-1 gameplay SHALL keep deferred non-line families outside the current playable build route in this pack.

#### Scenario: Deferred separator and non-line families remain deferred
- **WHEN** a sandbox build request targets `place_component_separator`, `install_sampled_delayed_sensor`, `install_pid_controller`, `install_line_pump`, `install_line_valve`, `install_line_heat_actuator`, `place_merge_junction_2x1`, or `place_split_junction_1x2`
- **THEN** the gameplay layer rejects the request with `SandboxRequestError(error_code="unknown_item", ...)` on the existing current-slice unsupported-item path
- **AND** no new public separator, sensor, controller, junction, or overlay route is introduced by 6ei.

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

### Requirement: The Simulation Contracts Are Stable
`SimulationSessionSnapshot`, `ProgressionSnapshot`, `ResearchSubmissionResult`, `TutorialGoalStatus`, `BuildApplyResult`, `InventoryLoadResult`, `InventoryWithdrawalResult`, `SimulationAdvanceResult`, and `SandboxRequestError` SHALL expose these exact fields and types:
- `SimulationSessionSnapshot`: existing live fields plus `progression_snapshot: ProgressionSnapshot | None`
- `ProgressionSnapshot`: `active_stage_id: str | None`, `unlocked_stage_ids: tuple[str, ...]`, `available_item_ids: tuple[str, ...]`, `available_research_ids: tuple[str, ...]`
- `ResearchSubmissionResult`: `success: bool`, `reason_code: str | None`, `snapshot: SimulationSessionSnapshot`
- `TutorialGoalStatus`: `goal_id: str`, `completed: bool`, `completed_at_time_s: float | None`
- `BuildApplyResult`: `success: bool`, `reason_code: str | None`, `snapshot: SimulationSessionSnapshot`
- `InventoryLoadResult`: `success: bool`, `reason_code: str | None`, `snapshot: SimulationSessionSnapshot`
- `InventoryWithdrawalResult`: `withdrawal_id: str`, `success: bool`, `reason_code: str | None`, `withdrawn_quantity_mol: float`, `snapshot: SimulationSessionSnapshot`
- `SimulationAdvanceResult`: `snapshot: SimulationSessionSnapshot`, `feed_consumption_by_material_id: Mapping[str, float]`, `product_production_by_product_id: Mapping[str, float]`, `published_signal_values_by_id: Mapping[str, float]`
- `SandboxRequestError`: `error_code: str`, `message: str`

#### Scenario: Progression-aware simulation contracts are fixed
- **WHEN** a contributor inspects the simulation session contracts
- **THEN** the progression state required by the gas-first ladder is present on the authoritative simulation snapshot and no separate unlock-only side channel is required

#### Scenario: Research submission result is success-only
- **WHEN** `submit_research_unlock(...)` succeeds
- **THEN** it returns `ResearchSubmissionResult(success=True, reason_code=None, snapshot=...)`
- **AND** invalid or unavailable research submissions continue to raise `SandboxRequestError` instead of returning a failed result object

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
The sandbox session and economics ledger SHALL consume substrate-owned observability snapshot surfaces for physical-state reads rather than reconstructing those reads from low-level runtime internals.

#### Scenario: Economics-facing observability stays separated from policy
- **WHEN** higher-layer code needs runtime observability for educational signals or future economics rollups
- **THEN** those reads come from the substrate-owned snapshot API and not from pricing, tutorial, or ledger logic being pushed down into `PlantBackendSession` or other substrate internals

### Requirement: Internal Tank-Custody Primitives Remain Session-Owned And Non-Public
Phase-1 gameplay SHALL keep staged tank-custody bookkeeping and purge-by-tank support under the gameplay/session layer as internal primitives, without widening the public simulation-session API or snapshot contracts in this change.

#### Scenario: Tank custody is keyed by process id and boundary id
- **WHEN** contributors inspect the staged tank-custody helper used by the simulation session and realtime-service runtime
- **THEN** stored custody state is keyed by holding-tank `process_id`
- **AND** boundary-route assignment is keyed by named boundary id for external bought/sold routes
- **AND** each boundary id has at most one active assigned tank at a time for those external routes

#### Scenario: Mixed tank contents are stored as one aggregate inventory state
- **WHEN** multiple incoming stream contributions are applied to the same staged tank-custody record
- **THEN** the helper combines them into one aggregate stored inventory state suitable for later outlet-pressure and volume calculation
- **AND** that state preserves repo-consistent thermodynamic fields such as temperature, pressure, species ids/composition, and repo-defined optional phase, enthalpy, entropy, or equivalent fields
- **AND** that state is represented as one mixed inventory record rather than separate per-source purity buckets

#### Scenario: Internal purge clears one tank custody record without widening live contracts
- **WHEN** the staged purge primitive clears custody for one holding-tank `process_id`
- **THEN** it removes only that tank's stored custody state
- **AND** it does not delete the tank record, alter ledger state, or require a new public session method, snapshot field, HTTP route, or Godot command

#### Scenario: Internal staging proof does not widen supported build items or start allowlists
- **WHEN** tests exercise the module-private helper in `src/modular_simulation/gameplay/realtime_service.py` that `_install_unit()` uses to stage `place_holding_tank`
- **THEN** that non-public proof stages the tank from catalog metadata without requiring a public build-item change or a current-start allowlist change
- **AND** that staging proof does not by itself define or widen the live playable build slice or current start allowlists.

#### Scenario: Boundary-route uniqueness does not limit general tank connectivity
- **WHEN** contributors inspect the staged one-route-per-boundary bookkeeping rule
- **THEN** that rule applies only to external bought/sold boundary-route assignment
- **AND** it does not by itself forbid future non-boundary multi-stream fan-in or fan-out connections on tanks

### Requirement: Topology-Only Starts Keep Distillation-Column Exposure Gated
Current topology-only gameplay starts SHALL continue to hide and reject `place_shortcut_distillation_column` in this change.

#### Scenario: Public supported-build lists remain unchanged for current starts
- **WHEN** current playable modes/starts expose their supported build surfaces
- **THEN** `place_shortcut_distillation_column` is not advertised on those topology-only surfaces
- **AND** existing gameplay exposure remains unchanged by this change pack.

#### Scenario: Direct install attempts still reject with existing start-allowlist contract
- **WHEN** a caller attempts to install `place_shortcut_distillation_column` on a topology-only start
- **THEN** the session layer rejects with `unsupported_on_start`
- **AND** rejection uses existing start-allowlist behavior rather than a new fallback or broadened error translation path.

### Requirement: Dynamic-Column Runtime Exposure Uses Unit-Local Actuation Requests While Controller Scope Is Deferred
This change SHALL stop at dynamic plant behavior, unit-local boundary seam fields, and runtime observability; controller binding/closed-loop proof for distillation SHALL remain deferred to `ModularSimulator-9tr.6`.

#### Scenario: Session/runtime contract separates plant behavior from controller proof
- **WHEN** contributors inspect completion criteria for this change
- **THEN** runtime dynamic-column behavior and observability are required for completion
- **AND** expanded seams (reflux-return routing, liquid-phase holdup-bounded external product withdrawals, condenser/reboiler unit-local duty-request fields) are required as runtime unit behavior
- **AND** closed-loop controller-proof acceptance remains explicitly out-of-scope for this pack.

### Requirement: Runtime Session Interfaces Do Not Promote Ratio Knobs To Live Actuation
Session/runtime contracts SHALL keep `reflux_ratio` and `boilup_ratio` as initialization/reference/derived-observable semantics only.

#### Scenario: Session completeness is not satisfied by ratio-knob wiring
- **WHEN** session-layer runtime contracts are reviewed for dynamic distillation actuation
- **THEN** live runtime actuation is represented by explicit unit-local boundary request fields plus external material-routing seams
- **AND** any exposed ratio values are derived from actual runtime flows
- **AND** exposing or storing ratio values does not count as providing live actuation wiring.

### Requirement: Dynamic Distillation Session Semantics Are Stagewise-Only
Session-level expectations SHALL treat stagewise runtime behavior as the sole distillation behavior path and SHALL NOT depend on a `ShortcutDistillation` compatibility route.

#### Scenario: Dynamic behavior contract is satisfied only by stagewise runtime
- **WHEN** a contributor evaluates whether this change is complete
- **THEN** completion requires stage-by-stage dynamic runtime behavior
- **AND** no `ShortcutDistillation` runtime/shim pathway is part of completion criteria.

### Requirement: Backend-Only Stagewise Proof Stays On Generic Session Surfaces
The repository SHALL support a backend-only stagewise causal proof assembled and stepped through the existing generic substrate session/runtime surfaces without widening gameplay or client contracts.

#### Scenario: Proof assembly uses the existing generic backend session surface
- **WHEN** a contributor assembles the bounded backend-only stagewise causal proof
- **THEN** the proof uses the existing generic substrate/session/runtime surface for process placement, runtime stepping, topology reads, and observability reads
- **AND** the implementation does not require a new Godot command, gameplay route, tutorial hook, or sandbox-only helper.

#### Scenario: Proof scope does not invent arbitrary unit-boundary mutation helpers
- **WHEN** the backend-only stagewise proof is reviewed for disturbance coverage
- **THEN** the proof demonstrates causality through already-supported unit-local duty-request seams, with any withdrawal seams treated as optional passive readouts only
- **AND** the proof does not silently widen `PlantBackendSession` with a new generic public helper for arbitrary process-unit boundary-state mutation.

### Requirement: Backend-Only Stagewise Proof Demonstrates Holdup-Driven Multi-Step Causality
The backend-only stagewise causal proof SHALL freeze explicit evidence requirements for top/bottom inventory response, disturbance-driven multi-step evolution, and honest demonstrated-vs-deferred reporting.

#### Scenario: Duty disturbances create multi-step top and bottom response
- **WHEN** the backend-only stagewise proof is executed over multiple runtime steps
- **THEN** condenser-duty and reboiler-duty disturbances create multi-step evolution in reflux-drum holdup, bottoms-sump holdup, and stage or product composition evidence
- **AND** the evidence is more than topology qualification or an instantaneous steady-state jump.

#### Scenario: Product withdrawals remain passive if no withdrawal seam is needed
- **WHEN** the backend-only stagewise proof is evaluated for disturbance coverage
- **THEN** passive product-flow readouts may be observed
- **AND** the proof does not make prescribed bottoms draw rate or withdrawal manipulation the centerpiece of the causal story.

#### Scenario: Proof output separates demonstrated claims from deferred realism claims
- **WHEN** the backend-only stagewise proof reports results
- **THEN** it explicitly distinguishes demonstrated holdup/material-balance evidence from deferred realism or integration claims
- **AND** it does not claim realistic pressure control, rigorous enthalpy-coupled thermal or temperature behavior, physical thermosyphon/pump-loop reboiler circulation, gameplay coupling, or generic controller-to-network auto-staging that this pack does not freeze.

#### Scenario: Any retained sump-to-reboiler surrogate remains internal-only
- **WHEN** the backend-only stagewise proof or any later runtime evidence describes the bottoms-side closure
- **THEN** any sump-to-reboiler circulation surrogate remains unit-internal rather than a connection-layer or public session seam
- **AND** if requested reboiler duty implies more boilup than the retained internal support surrogate can support, realized boilup and realized reboiler duty clip to the support-limited value under the current reduced-order `Q/λ` basis
- **AND** the proof or runtime report explicitly states that the current stagewise thermodynamic basis remains constant-relative-volatility, fixed-latent-heat, and proxy-temperature based with no property-package or enthalpy-flash hook
- **AND** it does not claim pressure-swing distillation, thermosyphon hydraulics, forced-circulation hydraulics, or superheat modeling that this pack does not freeze.

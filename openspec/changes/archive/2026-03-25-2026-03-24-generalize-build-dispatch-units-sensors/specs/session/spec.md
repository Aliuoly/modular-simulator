## ADDED Requirements

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

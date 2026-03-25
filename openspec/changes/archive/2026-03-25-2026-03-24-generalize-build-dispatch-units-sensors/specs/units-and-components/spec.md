## ADDED Requirements

### Requirement: Public Add-Process Exposure Follows Cataloged Family Support
The playable gameplay layer SHALL expose current public `unit_blueprint/add_process` items from the bound start's `allowed_item_ids`, filtered by the approved public add-process family, through one family-driven placement path instead of a heater/flash-only public whitelist.

#### Scenario: Sandbox public unit builds widen to the current approved add-process set
- **WHEN** contributors inspect the current playable sandbox build list after 6ei
- **THEN** it includes exactly `place_heater_cooler`, `place_flash_drum`, and `place_heat_exchanger` from the cataloged `add_process` family
- **AND** it does not implicitly expose unsupported-start items such as `place_holding_tank` or `place_quality_control_lab`.

### Requirement: Public Line Wiring Uses Real Named Ports For Exposed Units
The 6ei playable slice SHALL wire publicly exposed units against their runtime-declared named ports rather than an implicit gameplay-only `.in` / `.out` alias.

#### Scenario: Public unit families expose real endpoint names for wiring
- **WHEN** contributors inspect the public 6ei line contract for exposed units
- **THEN** heater/cooler wiring uses `inlet` and `outlet`
- **AND** flash-drum wiring uses `inlet`, `vapor_outlet`, and `liquid_outlet`
- **AND** heat-exchanger wiring uses `hot_inlet`, `cold_inlet`, `hot_outlet`, and `cold_outlet`
- **AND** bare process ids are not treated as a valid public alias for any non-boundary unit endpoint.

#### Scenario: Unknown endpoints fail as invalid wiring requests
- **WHEN** contributors inspect the public 6ei wiring error contract
- **THEN** malformed endpoint strings, unknown process ids, unknown boundaries, and unknown process-port combinations fail on the stable gameplay `invalid_config` path rather than inventing a new public error family.

### Requirement: Deferred Separator And Non-Add-Process Families Remain Deferred
The 6ei playable widening SHALL not implicitly pull deferred separator or non-add-process families into the public slice.

#### Scenario: Deferred separator, sensor, controller, junction, and overlay families remain deferred
- **WHEN** contributors inspect the 6ei public build widening
- **THEN** `place_component_separator`, `install_sampled_delayed_sensor`, `install_pid_controller`, `install_line_pump`, `install_line_valve`, `install_line_heat_actuator`, `place_merge_junction_2x1`, and `place_split_junction_1x2` are not implicitly pulled into the current playable build surface by the add-process refactor.

## MODIFIED Requirements

### Requirement: The First Playable Scope Is Narrow And Explicit
The first playable slice SHALL support exactly the free-play sandbox `phase1_process_sandbox_v1` and the guided tutorial `heater_flash_guided_build_v1`.

For `phase1_process_sandbox_v1`, the client-facing playable build list SHALL advertise exactly `place_heater_cooler`, `place_flash_drum`, `place_heat_exchanger`, and `build_process_line`.

For `heater_flash_guided_build_v1`, the client-facing playable build list SHALL continue to advertise exactly `place_heater_cooler`, `place_flash_drum`, and `build_process_line`.

#### Scenario: Sandbox build list widens to public add-process units
- **WHEN** a client requests bootstrap metadata or the current sandbox snapshot for `phase1_process_sandbox_v1`
- **THEN** the supported build-item list is exactly `place_heater_cooler`, `place_flash_drum`, `place_heat_exchanger`, and `build_process_line`.

#### Scenario: Heater/flash tutorial build list stays narrow
- **WHEN** a client requests bootstrap metadata or the current snapshot for `heater_flash_guided_build_v1`
- **THEN** the supported build-item list remains exactly `place_heater_cooler`, `place_flash_drum`, and `build_process_line`.

#### Scenario: Deferred non-line families stay hidden from the client build surface
- **WHEN** a client inspects the currently advertised playable build items after 6ei
- **THEN** `place_component_separator`, `install_sampled_delayed_sensor`, `install_pid_controller`, `install_line_pump`, `install_line_valve`, `install_line_heat_actuator`, `place_merge_junction_2x1`, and `place_split_junction_1x2` are not advertised as playable build items in this pack.

### Requirement: Public Line Commands Use Explicit Endpoint Strings
Client line-building commands SHALL keep the existing route and top-level JSON shape while using explicit endpoint strings for non-boundary nodes.

This line contract remains topology-only in the current playable slice; successful wiring does not itself claim runtime heater, flash, exchanger, or hydraulic behavior.

#### Scenario: Client wiring uses exact endpoint names on the existing build route
- **WHEN** a client submits `build_process_line` for a feed/product boundary
- **THEN** bare boundary ids remain valid
- **AND WHEN** the client submits `build_process_line` for a public unit endpoint
- **THEN** the request uses exact endpoint strings like `heater_1.inlet`, `flash_1.vapor_outlet`, `heat_exchanger_1.hot_inlet`, or `heat_exchanger_1.cold_outlet` on the same existing JSON build route.

#### Scenario: Invalid endpoint strings return stable JSON and HTTP 400
- **WHEN** a client submits `build_process_line` with a malformed endpoint string, unknown endpoint id, unknown port name, wrong-direction port, or bare non-boundary process id
- **THEN** the HTTP bridge responds with JSON `{error_code, message}` on the stable invalid-request path
- **AND** the response status is HTTP `400`.

### Requirement: The Slice Exposes Stable JSON Error Responses
Rejected playable-slice API requests SHALL return JSON error payloads with stable `error_code` and `message` fields, including widened add-process metadata failures.

#### Scenario: Invalid metadata-driven build returns stable JSON and HTTP 400
- **WHEN** a client submits a widened add-process build whose runtime-authoritative metadata resolution fails
- **THEN** the HTTP bridge responds with JSON `{error_code, message}` using the stable invalid-request error path
- **AND** the response status is HTTP `400`.

# Client Godot

## Purpose
This capability defines the Godot client behavior and the fixed HTTP bridge it uses for the first playable local slice.
## Requirements
### Requirement: The Playable Slice Uses A Thin Game Service Above Existing Backend Layers
The first playable slice SHALL compose the existing sandbox-session, economics-ledger, and substrate layers through a higher-level game service rather than exposing those low-level seams directly to the client.

#### Scenario: Client sends player intent instead of raw backend choreography
- **WHEN** a Godot client places equipment, buys feed, or sells product
- **THEN** it talks to a higher-level game service that orchestrates any required receipt or withdrawal handoffs internally instead of sending raw receipt ids or talking directly to `PlantBackendSession`

### Requirement: The First Playable Scope Is Narrow And Explicit
The first playable slice SHALL support exactly the free-play sandbox `phase1_process_sandbox_v1` and the guided tutorial `heater_flash_guided_build_v1`.

For `phase1_process_sandbox_v1`, the client-facing playable build list SHALL advertise exactly `place_heater_cooler`, `place_flash_drum`, `place_heat_exchanger`, and `build_process_line`.

For `heater_flash_guided_build_v1`, the client-facing playable build list SHALL continue to advertise exactly `place_heater_cooler`, `place_flash_drum`, and `build_process_line`.

#### Scenario: Reactor and recycle client flows stay deferred
- **WHEN** a contributor inspects the playable client scope for the first slice
- **THEN** the reactor-control and recycle/purge tutorials are not treated as required client flows for the first slice

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

### Requirement: Sessions Run Continuously Without Pause
Playable sessions SHALL be always-running once created, SHALL use a configurable fixed simulation step, and SHALL not expose a pause or resume affordance.

#### Scenario: No pause feature is available
- **WHEN** a contributor inspects the game-service routes and the Godot client controls
- **THEN** no `pause` or `resume` operation exists and no pause button/hotkey is surfaced to the player

#### Scenario: Render and simulation rates are decoupled
- **WHEN** the slice is running normally
- **THEN** the Godot client renders at 60 FPS independently of the service’s fixed simulation update cadence

### Requirement: The Slice Exposes An Explicit HTTP Session API
The first playable slice SHALL expose exactly these HTTP endpoints for the Godot client: `GET /game/bootstrap`, `POST /game/sessions`, `GET /game/sessions/{session_id}/snapshot`, `POST /game/sessions/{session_id}/commands/build`, `POST /game/sessions/{session_id}/commands/buy-feed`, `POST /game/sessions/{session_id}/commands/sell-product`, and `POST /game/sessions/{session_id}/restart`.

#### Scenario: HTTP surface is fixed for the first slice
- **WHEN** a contributor inspects the backend-facing client bridge for the playable slice
- **THEN** those exact routes exist and no `pause`, `resume`, or `step-on-demand` route is required for the playable slice

### Requirement: The Slice Advertises Granular Simulation Step Presets
The playable slice SHALL let the session start with an optional `simulation_dt_s`, SHALL advertise the presets `1/60`, `1/30`, and `1/20` seconds, and SHALL use `1/60` when the client omits `simulation_dt_s`.

#### Scenario: Session bootstrap exposes supported fidelity presets
- **WHEN** a client requests the bootstrap metadata for the playable slice
- **THEN** it can discover the supported `simulation_dt_s` presets before creating a session

#### Scenario: Session creation applies the default simulation step
- **WHEN** a client creates a playable session without supplying `simulation_dt_s`
- **THEN** the service uses `1/60` seconds as the default simulation step

#### Scenario: Unsupported simulation steps are rejected
- **WHEN** a client tries to create a playable session with a `simulation_dt_s` outside the advertised preset list
- **THEN** the service rejects the request with `error_code="unsupported_simulation_dt_s"`

### Requirement: The Slice Allows Exactly One Active Local Session
The first playable slice SHALL allow exactly one active local session per backend process and SHALL reject creation of a second concurrent session.

#### Scenario: Second session creation is rejected
- **WHEN** a client requests a new playable session while another local playable session is still active
- **THEN** the service rejects the request with `error_code="session_already_active"`

### Requirement: The Client Consumes A Combined Authoritative Snapshot
The game service SHALL expose a combined authoritative snapshot for the client that includes gameplay state, economics state, topology state, and render-layout state together.

#### Scenario: Snapshot includes gameplay and world-render data together
- **WHEN** a client requests the latest slice snapshot
- **THEN** the response includes the current simulation session state, cash-ledger state, latest published signals, topology payload, board-layout payload, and lag diagnostics in one service-owned snapshot

### Requirement: The Slice Exposes Stable JSON Error Responses
Rejected playable-slice API requests SHALL return JSON error payloads with stable `error_code` and `message` fields, including widened add-process metadata failures.

#### Scenario: Unknown session ids are rejected consistently
- **WHEN** a client requests a snapshot or restart for an unknown `session_id`
- **THEN** the service rejects the request with JSON `{error_code: "unknown_session", message: ...}`

#### Scenario: Invalid build payloads are rejected consistently
- **WHEN** a client submits an invalid build item id, unsupported slice item, invalid build config, or invalid layout payload
- **THEN** the service rejects the request with JSON `{error_code, message}` using stable error codes for the applicable failure

### Requirement: Invalid Metadata-Driven Build Requests Preserve Stable HTTP Errors
The playable-slice HTTP bridge SHALL translate invalid runtime-authoritative unit metadata failures for build requests into the existing stable JSON error payload and invalid-request status path.

#### Scenario: Invalid metadata-driven build request returns stable JSON and HTTP 400
- **WHEN** a build request reaches the gameplay layer and runtime-authoritative unit metadata resolution fails because the configured module, unit type, or constructor payload is invalid
- **THEN** the HTTP bridge responds with JSON `{error_code: "invalid_config", message: ...}`
- **AND** the response status is HTTP `400`

### Requirement: Command Success Responses Are Stable
Successful playable-slice command endpoints SHALL return exactly `accepted`, `message`, and `snapshot` fields.

#### Scenario: Successful command responses use one contract
- **WHEN** a build, buy-feed, sell-product, or restart command succeeds
- **THEN** the HTTP response body includes exactly `accepted: true`, `message: str`, and `snapshot: GameSnapshot`

### Requirement: HTTP Status Semantics Are Stable
The playable-slice HTTP bridge SHALL use stable success and rejection statuses for the first slice.

#### Scenario: Success statuses are consistent
- **WHEN** a client creates a session
- **THEN** the service responds with HTTP `201`
- **AND WHEN** a client fetches a snapshot or submits a successful build, buy-feed, sell-product, or restart command
- **THEN** the service responds with HTTP `200`

#### Scenario: Error statuses are consistent
- **WHEN** a client sends an invalid request payload or unsupported simulation-step/item/material/product value
- **THEN** the service responds with HTTP `400`
- **AND WHEN** a client references an unknown `session_id`
- **THEN** the service responds with HTTP `404`
- **AND WHEN** a client attempts to create a second active session or spends/sells beyond the authoritative state constraints
- **THEN** the service responds with HTTP `409`

### Requirement: Topology And Board Layout Stay Separate But Synchronized
The playable slice SHALL keep topology ownership in the substrate and board-layout ownership in the game layer, while ensuring player build actions update both coherently.

#### Scenario: Build commands update topology and layout together
- **WHEN** a player places a heater, places a flash drum, or draws a process line
- **THEN** the resulting authoritative snapshot reflects both the updated plant topology and the updated board-render placement/path metadata

### Requirement: Presentation Uses A Fixed-Camera Godot Client
The first playable slice SHALL ship with a Godot 4 client that uses a fixed non-rotatable camera and a 2.5D board presentation.

#### Scenario: Camera behavior matches the intended presentation
- **WHEN** the player is inside the main playable scene
- **THEN** the camera remains fixed and the player cannot freely rotate it

### Requirement: The Godot HUD Exposes The Current Slice State
The client SHALL surface the state needed to play the slice: cash, feed inventory, product inventory, published signals, tutorial goals when applicable, and the supported build/feed/sell/restart commands.

#### Scenario: Tutorial mode surfaces guided progression
- **WHEN** the player is in `heater_flash_guided_build_v1`
- **THEN** the HUD shows the current tutorial goals and completion progress derived from the authoritative backend snapshot

### Requirement: The First Slice Is Local And Ephemeral
The first playable slice SHALL support session start and restart locally, and SHALL not promise player-facing save/resume across process restarts.

#### Scenario: Restart is available but persistence is deferred
- **WHEN** a player restarts the active slice session
- **THEN** the session returns to its initial state for that mode, and the playable slice does not claim that cross-process save/load is already part of the player-facing game loop

#### Scenario: Restart preserves session identity
- **WHEN** a player restarts the active slice session
- **THEN** the service keeps the existing `session_id` and resets only the slice state behind it

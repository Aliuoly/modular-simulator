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

`heater_flash_guided_build_v1` remains the client/service mode id and SHALL continue to map to the start-catalog record `heater_flash_tutorial_start_v1`, rather than reusing the start id directly in the client surface.

For `phase1_process_sandbox_v1`, bootstrap SHALL advertise exactly these initial starter-batch build items: `place_inlet_gas_separator`, `place_teg_contactor`, `place_rich_glycol_flash_tank`, `place_lean_rich_glycol_exchanger`, `place_teg_regenerator`, `install_glycol_circulation_pump`, and `build_process_line`.

For `heater_flash_guided_build_v1`, the client-facing playable build list SHALL continue to advertise exactly `place_heater_cooler`, `place_flash_drum`, and `build_process_line`.

#### Scenario: Main-world slice starts on the gas-first starter batch
- **WHEN** a contributor inspects the playable client scope for the default sandbox
- **THEN** the initial main-world build affordances are the starter-batch gas items plus process lines rather than the old heater/flash sandbox set

#### Scenario: Heater/flash tutorial build list stays narrow
- **WHEN** a client requests bootstrap metadata or the current snapshot for `heater_flash_guided_build_v1`
- **THEN** the supported build-item list remains exactly `place_heater_cooler`, `place_flash_drum`, and `build_process_line`.

### Requirement: Sessions Run Continuously Without Pause
Playable sessions SHALL be always-running once created, SHALL use a configurable fixed simulation step, and SHALL not expose a pause or resume affordance.

#### Scenario: No pause feature is available
- **WHEN** a contributor inspects the game-service routes and the Godot client controls
- **THEN** no `pause` or `resume` operation exists and no pause button/hotkey is surfaced to the player

#### Scenario: Render and simulation rates are decoupled
- **WHEN** the slice is running normally
- **THEN** the Godot client renders at 60 FPS independently of the service’s fixed simulation update cadence

### Requirement: The Slice Exposes An Explicit HTTP Session API
The first playable slice SHALL expose exactly these HTTP endpoints for the Godot client: `GET /game/bootstrap`, `POST /game/sessions`, `GET /game/sessions/{session_id}/snapshot`, `POST /game/sessions/{session_id}/commands/build`, `POST /game/sessions/{session_id}/commands/buy-feed`, `POST /game/sessions/{session_id}/commands/sell-product`, `POST /game/sessions/{session_id}/commands/submit-research`, and `POST /game/sessions/{session_id}/restart`.

`POST /game/sessions/{session_id}/commands/buy-feed` SHALL keep the existing payload shape:
- `material_id: string`
- `quantity_mol: number`

`POST /game/sessions/{session_id}/commands/sell-product` SHALL keep the existing payload shape:
- `product_id: string`
- `quantity_mol: number`

Neither route SHALL require or publish a public `tank_id` field in this pack.

`POST /game/sessions/{session_id}/commands/submit-research` SHALL accept exactly this JSON payload shape:
- `research_id: string`
- `submitted_quantities_by_product_id: {product_id: quantity_mol}`

On success, the route SHALL return HTTP `200` with the same `{"accepted", "message", "snapshot"}` command envelope used by the existing build/buy-feed/sell-product/restart commands.

On rejection, the route SHALL return the stable error JSON `{"error_code", "message"}` with these status semantics:
- `404` for `unknown_session`
- `409` for `research_not_available`, `research_unavailable_for_session`, and `insufficient_product_inventory`
- `400` for invalid payload shape, `unknown_research_unlock`, and `invalid_quantity`

#### Scenario: Research submission is part of the fixed HTTP surface
- **WHEN** a contributor inspects the backend-facing client bridge for the playable slice
- **THEN** the research submission route exists as part of the stable first-slice command set

#### Scenario: Research route payload and status semantics are frozen
- **WHEN** a client submits research through the HTTP bridge
- **THEN** the request body keys, success envelope, and rejection status behavior match the frozen contract above

#### Scenario: Unknown session remains a stable research-route transport error
- **WHEN** a client submits any slice command, including `submit-research`, against a nonexistent session id
- **THEN** the service returns `404` with stable error JSON `{"error_code", "message"}` and `error_code = "unknown_session"`

#### Scenario: Buy and sell routes stay direct and tank-free in the narrow slice
- **WHEN** a client submits buy-feed or sell-product commands in this pack
- **THEN** the request uses only the frozen material/product id plus quantity payloads and does not require a public `tank_id` or sale-spec field

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
The game service SHALL expose a combined authoritative snapshot for the client that includes gameplay state, economics state, progression state, topology state, and render-layout state together.

#### Scenario: Snapshot carries current unlock state and current buildable items
- **WHEN** a client requests the latest slice snapshot for the default sandbox
- **THEN** the response includes progression state through the authoritative gameplay snapshot and the top-level `supported_build_item_ids` reflects the currently unlocked build items rather than a static process-wide constant

### Requirement: The Godot Build Panel Supports Explicit Process-Line Authoring
The playable Godot client SHALL let the player submit `build_process_line` through panel-based source and target endpoint selection using the existing authoritative build contract.

#### Scenario: Sandbox line building no longer hard-stops in the panel
- **WHEN** the active build item is `build_process_line` in `phase1_process_sandbox_v1`
- **THEN** the build panel offers explicit source and target endpoint choices instead of returning a fixed `"Line build requires explicit endpoints"` status
- **AND** a valid selection submits the existing build command route with the exact endpoint strings already frozen by the session/build contract.

#### Scenario: Endpoint choices are derived from authoritative topology state
- **WHEN** the panel refreshes from a new authoritative snapshot
- **THEN** source choices reflect source boundaries plus process outlet endpoints
- **AND** target choices reflect sink boundaries plus process inlet endpoints
- **AND** the client does not rely on a second client-invented topology graph to author lines.

#### Scenario: Panel-authored lines use orthogonal layout paths
- **WHEN** the player submits a valid panel-authored `build_process_line` command
- **THEN** the client supplies `layout.path_xy` as an orthogonal polyline with 90-degree elbows derived from the selected source and target anchors
- **AND** process anchors come from authoritative `board_layout.unit_entities_by_process_id`
- **AND** current public boundary anchors use fixed client-side positions for this slice rather than richer in-world path authoring
- **AND** the generated path avoids occupied unit keep-out boxes for the current slice layout when a valid orthogonal route exists.

### Requirement: Active Sessions Poll Authoritative Snapshots In The Background
The Godot client SHALL keep an active playable session synchronized through background snapshot polling at a lower cadence than rendering.

#### Scenario: MainGame updates from background polling after scene load
- **WHEN** `MainGame` becomes active for a running session
- **THEN** the HUD and build panel receive authoritative snapshot updates through background polling without requiring a manual refresh call as the normal post-load sync mechanism
- **AND** at least one observable post-mount snapshot change is delivered by polling alone rather than by command success or `_ready()` hydration.

#### Scenario: Polling and commands do not overlap on the shared HTTPRequest transport
- **WHEN** background polling is active while the player submits build, buy-feed, sell-product, submit-research, or restart commands
- **THEN** the client serializes request use of the shared HTTP transport so polling does not collide with command requests.

#### Scenario: Polling stops cleanly when the session UI tears down
- **WHEN** the client exits the active playable scene or the smoke harness finishes
- **THEN** the polling loop stops and `stop_polling()` performs real cleanup instead of being a no-op stub.

#### Scenario: Tutorial mode also uses polling lifecycle cleanup
- **WHEN** the player runs `heater_flash_guided_build_v1` through the same Godot client flow
- **THEN** polling starts for the active session and is stopped through the same teardown path used by the sandbox mode.

### Requirement: Rejected Build Commands Are Atomic For The Playable Slice
The playable slice SHALL reject locked or otherwise invalid build commands before topology, board layout, or ledger state changes are committed.

#### Scenario: Locked build rejection leaves authoritative state unchanged
- **WHEN** a client submits a build command for a main-world item that is valid for `phase1_process_sandbox_v1` but not yet unlocked
- **THEN** the service returns HTTP `409` with stable error JSON `{"error_code", "message"}`, uses `error_code = "item_locked"`, and a subsequent snapshot shows unchanged topology, unchanged board layout, and unchanged cash relative to the pre-request snapshot

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
- **WHEN** a build, buy-feed, sell-product, submit-research, or restart command succeeds
- **THEN** the HTTP response body includes exactly `accepted: true`, `message: str`, and `snapshot: GameSnapshot`

### Requirement: HTTP Status Semantics Are Stable
The playable-slice HTTP bridge SHALL use stable success and rejection statuses for the first slice.

#### Scenario: Success statuses are consistent
- **WHEN** a client creates a session
- **THEN** the service responds with HTTP `201`
- **AND WHEN** a client fetches a snapshot or submits a successful build, buy-feed, sell-product, submit-research, or restart command
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

### Requirement: The Godot World Renders The Authoritative Board State
The playable Godot client SHALL render a readable in-world view directly from the authoritative topology and board-layout snapshot rather than from a second client-side simulation model.

#### Scenario: Boundary markers appear from authoritative topology presence
- **WHEN** `WorldRenderer` refreshes from an authoritative snapshot
- **THEN** the client renders public boundary markers only for boundary node ids currently present in the authoritative topology payload
- **AND** the current slice continues to use fixed client-side anchor positions for those public boundary ids.

#### Scenario: Sandbox builds refresh rendered units and lines from authoritative layout state
- **WHEN** the player places units and process lines in `phase1_process_sandbox_v1`
- **THEN** `WorldRenderer` rebuilds visible unit markers from `board_layout.unit_entities_by_process_id`
- **AND** visible line markers from `board_layout.line_entities_by_line_id`
- **AND** the rendered ids/counts match the authoritative snapshot after each update.

#### Scenario: Restart clears rendered world state back to the authoritative restart snapshot
- **WHEN** the player restarts the active playable session
- **THEN** the rendered unit and line ids are rebuilt to match the authoritative restarted snapshot rather than preserving stale pre-restart nodes.

### Requirement: The Godot HUD Exposes The Current Slice State
The client SHALL surface the state needed to play the slice: cash, feed inventory, product inventory, published signals, progression state for the main sandbox, tutorial goals when applicable, the supported build/feed/sell/research/restart commands, and panel-first process-line authoring for the currently supported slice topology.

#### Scenario: Main sandbox HUD surfaces stage progress
- **WHEN** the player is in `phase1_process_sandbox_v1`
- **THEN** the HUD shows the current gas-processing stage, the currently available mixed-product research unlock, and the currently unlocked build items derived from the authoritative backend snapshot

#### Scenario: Main sandbox HUD and build panel together support the gas-first operable loop
- **WHEN** the player is in `phase1_process_sandbox_v1`
- **THEN** the HUD shows the current gas-processing stage, the currently available mixed-product research unlock, and the currently unlocked build items derived from the authoritative backend snapshot
- **AND** the build panel can use those authoritative snapshots to place units, build process lines, buy feed, sell product, submit research, and restart without requiring richer in-world rendering first.

### Requirement: The First Slice Is Local And Ephemeral
The first playable slice SHALL support session start and restart locally, and SHALL not promise player-facing save/resume across process restarts.

#### Scenario: Restart is available but persistence is deferred
- **WHEN** a player restarts the active slice session
- **THEN** the session returns to its initial state for that mode, and the playable slice does not claim that cross-process save/load is already part of the player-facing game loop

#### Scenario: Restart preserves session identity
- **WHEN** a player restarts the active slice session
- **THEN** the service keeps the existing `session_id` and resets only the slice state behind it

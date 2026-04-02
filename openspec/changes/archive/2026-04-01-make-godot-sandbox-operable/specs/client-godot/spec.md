## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: The Godot HUD Exposes The Current Slice State
The client SHALL surface the state needed to play the slice: cash, feed inventory, product inventory, published signals, progression state for the main sandbox, tutorial goals when applicable, the supported build/feed/sell/research/restart commands, and panel-first process-line authoring for the currently supported slice topology.

#### Scenario: Main sandbox HUD and build panel together support the gas-first operable loop
- **WHEN** the player is in `phase1_process_sandbox_v1`
- **THEN** the HUD shows the current gas-processing stage, the currently available mixed-product research unlock, and the currently unlocked build items derived from the authoritative backend snapshot
- **AND** the build panel can use those authoritative snapshots to place units, build process lines, buy feed, sell product, submit research, and restart without requiring richer in-world rendering first.

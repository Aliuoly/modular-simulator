## MODIFIED Requirements

### Requirement: The First Playable Scope Is Narrow And Explicit
The first playable slice SHALL support exactly the free-play sandbox `phase1_process_sandbox_v1` and the guided tutorial `heater_flash_guided_build_v1`.

`heater_flash_guided_build_v1` remains the client/service mode id and SHALL continue to map to the start-catalog record `heater_flash_tutorial_start_v1`, rather than reusing the start id directly in the client surface.

For `phase1_process_sandbox_v1`, bootstrap SHALL advertise exactly these initial starter-batch build items: `place_inlet_gas_separator`, `place_teg_contactor`, `place_rich_glycol_flash_tank`, `place_lean_rich_glycol_exchanger`, `place_teg_regenerator`, `install_glycol_circulation_pump`, and `build_process_line`.

For `heater_flash_guided_build_v1`, bootstrap SHALL continue to advertise exactly `place_heater_cooler`, `place_flash_drum`, and `build_process_line`.

#### Scenario: Main-world slice starts on the gas-first starter batch
- **WHEN** a contributor inspects the playable client scope for the default sandbox
- **THEN** the initial main-world build affordances are the starter-batch gas items plus process lines rather than the old heater/flash sandbox set

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

### Requirement: The Client Consumes A Combined Authoritative Snapshot
The game service SHALL expose a combined authoritative snapshot for the client that includes gameplay state, economics state, progression state, topology state, and render-layout state together.

#### Scenario: Snapshot carries current unlock state and current buildable items
- **WHEN** a client requests the latest slice snapshot for the default sandbox
- **THEN** the response includes progression state through the authoritative gameplay snapshot and the top-level `supported_build_item_ids` reflects the currently unlocked build items rather than a static process-wide constant

### Requirement: Rejected Build Commands Are Atomic For The Playable Slice
The playable slice SHALL reject locked or otherwise invalid build commands before topology, board layout, or ledger state changes are committed.

#### Scenario: Locked build rejection leaves authoritative state unchanged
- **WHEN** a client submits a build command for a main-world item that is valid for `phase1_process_sandbox_v1` but not yet unlocked
- **THEN** the service returns HTTP `409` with stable error JSON `{"error_code", "message"}`, uses `error_code = "item_locked"`, and a subsequent snapshot shows unchanged topology, unchanged board layout, and unchanged cash relative to the pre-request snapshot

### Requirement: The Godot HUD Exposes The Current Slice State
The client SHALL surface the state needed to play the slice: cash, feed inventory, product inventory, published signals, progression state for the main sandbox, tutorial goals when applicable, and the supported build/feed/sell/research/restart commands.

#### Scenario: Main sandbox HUD surfaces stage progress
- **WHEN** the player is in `phase1_process_sandbox_v1`
- **THEN** the HUD shows the current gas-processing stage, the currently available mixed-product research unlock, and the currently unlocked build items derived from the authoritative backend snapshot

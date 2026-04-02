## ADDED Requirements

### Requirement: The Godot World Renders The Authoritative Board State
The playable slice SHALL render a minimal readable world view from the authoritative snapshot so placed units, public boundaries, and process lines are visible in the fixed-camera scene without introducing in-world editing.

#### Scenario: Boundary markers appear from authoritative topology state
- **WHEN** a supported playable session loads in the Godot client
- **THEN** the world renderer shows markers for the currently present public boundaries derived from the authoritative topology snapshot

#### Scenario: Sandbox builds refresh rendered units and lines
- **WHEN** the player places units or builds process lines through the existing panel controls
- **THEN** the world renderer refreshes to show unit markers and line segments whose ids/counts match the authoritative board-layout snapshot

#### Scenario: Restart clears rendered topology back to the restarted snapshot
- **WHEN** the player restarts the active supported session
- **THEN** rendered unit and line nodes return to the authoritative restart state instead of persisting stale pre-restart world nodes

# Game Backend Overview

## Repository Identity

`modular_simulation` is a **simulation-first backend for educational chemical-process gameplay and classroom use**. It is not a generic control-simulation sandbox and not a frontend game client. The repo exposes reusable simulation primitives, but its primary purpose is to serve as a grounded substrate for educational tools targeting chemical engineering students and instructors.

## Target Audience

- **Primary**: Chemical engineering students and instructors who need a grounded, simulation-accurate process backend for learning and classroom tooling.
- **Secondary**: Contributors experimenting with process-control design and flowsheet modeling.

## Phase-1 Teaching Scope (Current Live Slice)

The current playable phase-1 slice is intentionally narrow and gas-first:

1. **Main sandbox (`phase1_process_sandbox_v1`)** — sweet-wet-gas progression with staged unlocks: inlet separation + TEG dehydration at start, then a batched mixed-product research unlock for JT/low-temperature separation and condensate stabilization.
2. **Guided tutorial (`heater_flash_guided_build_v1`)** — unchanged heater/flash onboarding flow.

The main sandbox uses real gas-processing names with explicit educational proxies (for example, TEG contactor and regenerator names mapped to currently available unit substrates) and keeps buy/sell commands tank-free in this slice.

## Substrate Layers

The physical simulation and runtime-editing layer consists of:

- `Flowsheet` and hydraulic semantics — physical topology and material flow.
- Unit-process models — heaters, flash drums, heat exchangers, reactors.
- Sensors, controllers, and control elements — instrumentation and closed-loop control.
- `PlantBackendSession` — low-level topology/runtime-editing substrate for user-facing applications (see [`docs/plant_backend_session_user_guide.md`](plant_backend_session_user_guide.md)).

`PlantBackendSession` is the canonical substrate entry point. The gameplay layers, progression systems, and economics rules in this repository compose these substrate layers rather than replacing them.

## Consumer Layers Above the Substrate

For the phase-1 playable vertical slice, the repository now includes consumer layers above the substrate:

- **Instance-backed gameplay runtime layer** (`src/modular_simulation/gameplay/`) — session/economics/board-layout runtimes that orchestrate gameplay state by composing substrate objects.
- **Realtime service + HTTP bridge** (`src/modular_simulation/gameplay/realtime_service.py` and `src/modular_simulation/app/game_api.py`) — the Godot-facing transport seam exposing `GET /game/bootstrap`, session creation, snapshots, build/feed/sell commands, and restart.
- **Godot vertical-slice client** (`clients/godot_phase1_vertical_slice/`) — fixed-camera, 2.5D client consuming the game API for the first playable local slice.

These layers are explicitly consumers of the educational simulation backend/substrate. They are not a replacement for `PlantBackendSession`, `Flowsheet`, or the underlying simulation model contracts.

## Canonical Examples as Substrate Learning Path

The canonical examples are the best starting points for the underlying simulation substrate:

| Example | Teaching track |
| --- | --- |
| `examples/unit_process_flowsheet/gas_1_inlet_separator.py` | Gas starter reachability (`separator_gas`, `unstabilized_condensate`) |
| `examples/unit_process_flowsheet/gas_2_teg_dehydration.py` | Gas starter reachability (`dry_gas`) |
| `examples/unit_process_flowsheet/gas_3_jt_low_temperature_separation.py` | Post-unlock reachability (`ngl_liquids`) |
| `examples/unit_process_flowsheet/gas_4_condensate_stabilizer.py` | Post-unlock reachability (`stabilized_condensate`) |
| `examples/unit_process_flowsheet/easy_2_heater_flash.py` | Guided tutorial seed |
| `examples/unit_process_flowsheet/complex_6_ammonia_recycle_loop.py` | Recycle, purge, and process-design tradeoffs |
| `examples/connection_layer/two_tank_reaction_comparison.py` | Reactor dynamics and connected-plant fidelity |

These examples represent the current substrate learning path. They are not a pre-built gameplay catalog — the sandbox start, tutorial challenges, and higher-level economics/session layers in this repository build on top of this substrate.

See the full [Examples Catalog](examples_catalog.md) for the primary/advanced split and migration map.

## Explicitly Deferred (Non-Goals for Phase 1)

The following topics are intentionally deferred beyond phase 1 and should not be smuggled into phase-1 acceptance criteria:

- **Batch-first gameplay** — batch reactors, sequential recipe execution, and batch scheduling.
- **Stochastic equipment failure, fouling accumulation, and staffing systems** — degradation modeling and maintenance workflows.
- **Multi-plant vertical integration** — supply chains, inter-plant streams, and hierarchical campaign management.
- **Open-ended chemistry sandboxing** — arbitrary species or reaction network authoring beyond the starter scope.

These topics may be addressed in later packs that explicitly opt into them.

## Relationship to Follow-On Packs

This repository now includes the simulation substrate plus the first higher-level gameplay layers:

- Phase-1 gas-first sandbox progression and tutorial challenges (one gas-first sandbox start plus guided heater/flash tutorial).
- Sandbox session and heuristic economics layer (inventory-backed simulation session, separate economics ledger, and named engineering-economics rulebook APIs).
- Realtime service and HTTP game API transport seam for client-facing commands/snapshots.
- Godot phase-1 vertical-slice client that consumes those APIs.

Those layers compose the simulation substrate described here. They do not rewrite it.

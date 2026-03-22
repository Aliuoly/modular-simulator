# Game Backend Overview

## Repository Identity

`modular_simulation` is a **simulation-first backend for educational chemical-process gameplay and classroom use**. It is not a generic control-simulation sandbox and not a frontend game client. The repo exposes reusable simulation primitives, but its primary purpose is to serve as a grounded substrate for educational tools targeting chemical engineering students and instructors.

## Target Audience

- **Primary**: Chemical engineering students and instructors who need a grounded, simulation-accurate process backend for learning and classroom tooling.
- **Secondary**: Contributors experimenting with process-control design and flowsheet modeling.

## Phase-1 Teaching Scope

Phase 1 is intentionally narrow and aligns with the existing continuous-process simulation capabilities. It covers three teaching tracks:

1. **Topology and separation basics** — flowsheet wiring with explicit boundary feeds and boundary sinks, named junction topology, and unit-process composition (heater, flash, heat exchanger).
2. **Reactor dynamics, sensing, and control** — reactor models, closed-loop PID control, sensor noise and delays, and instrumented control loops.
3. **Recycle, purge, and process-design tradeoffs** — explicit recycle return edges, named junction branching, recycle loop validation, purge streams, and material balance tradeoffs.

These tracks fit the existing continuous-process runtime and draw from both canonical examples and reference-backed reactor/control examples. They do not require new simulation-core capabilities.

## Substrate Layers

The physical simulation and runtime-editing layer consists of:

- `Flowsheet` and hydraulic semantics — physical topology and material flow.
- Unit-process models — heaters, flash drums, heat exchangers, reactors.
- Sensors, controllers, and control elements — instrumentation and closed-loop control.
- `PlantBackendSession` — low-level topology/runtime-editing substrate for user-facing applications (see [`docs/plant_backend_session_user_guide.md`](plant_backend_session_user_guide.md)).

`PlantBackendSession` is the canonical substrate entry point. The gameplay layers, progression systems, and economics rules in this repository compose these substrate layers rather than replacing them.

## Canonical Examples as Substrate Learning Path

The canonical examples are the best starting points for the underlying simulation substrate:

| Example | Teaching track |
| --- | --- |
| `examples/unit_process_flowsheet/easy_2_heater_flash.py` | Topology and separation basics |
| `examples/unit_process_flowsheet/easy_3_dual_feed_heat_exchanger.py` | Topology and separation basics |
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

- Phase-1 sandbox build catalog and tutorial challenges (one sandbox start, build/buy primitives, and guided challenge starts layered on canonical and reference-backed examples).
- Sandbox session and heuristic economics layer (inventory-backed simulation session, separate economics ledger, and named engineering-economics rulebook APIs).

Those layers compose the simulation substrate described here. They do not rewrite it.

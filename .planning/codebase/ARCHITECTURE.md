# Architecture

**Analysis Date:** 2026-03-29

## Pattern Overview

**Overall:** Domain-oriented layered simulation platform with composition-based runtime orchestration.

**Key Characteristics:**
- Core simulation primitives live under `src/modular_simulation/measurables/`, `src/modular_simulation/framework/`, and `src/modular_simulation/components/` and are reused by higher-level flowsheet and gameplay code.
- Connected-plant behavior is split into explicit topology, hydraulic compilation, and runtime coupling layers under `src/modular_simulation/connection/`.
- Application entry points stay thin and delegate to service/facade objects such as `src/modular_simulation/app/game_api.py`, `src/modular_simulation/cli/backend_session.py`, and `src/modular_simulation/gameplay/realtime_service.py`.

## Layers

**Application / Delivery Layer:**
- Purpose: Expose the simulator through HTTP, UI, and interactive session facades.
- Location: `src/modular_simulation/app/`, `src/modular_simulation/cli/`, `clients/godot_phase1_vertical_slice/`
- Contains: FastAPI routes in `src/modular_simulation/app/game_api.py`, a NiceGUI demo in `src/modular_simulation/app/main.py`, and the transactional editing facade in `src/modular_simulation/cli/backend_session.py`.
- Depends on: `src/modular_simulation/gameplay/`, `src/modular_simulation/connection/`
- Used by: HTTP clients, Godot client code in `clients/godot_phase1_vertical_slice/scripts/`, example and smoke tests in `tests/app/`, `tests/cli/`, and `tests/integration/`.

**Gameplay Service Layer:**
- Purpose: Translate player-facing actions into catalog lookups, session state changes, backend session mutations, and simulation snapshots.
- Location: `src/modular_simulation/gameplay/`
- Contains: Session state in `src/modular_simulation/gameplay/sandbox_session.py`, realtime orchestration in `src/modular_simulation/gameplay/realtime_service.py`, start composition in `src/modular_simulation/gameplay/start_runtime.py`, and content catalogs in `src/modular_simulation/gameplay/start_catalog.py`, `src/modular_simulation/gameplay/sandbox_catalog.py`, and `src/modular_simulation/gameplay/tutorial_catalog.py`.
- Depends on: `src/modular_simulation/cli/backend_session.py`, `src/modular_simulation/connection/topology/network.py`, and gameplay contracts in `src/modular_simulation/gameplay/contracts.py`.
- Used by: `src/modular_simulation/app/game_api.py` and gameplay tests under `tests/gameplay/`.

**Simulation Composition Layer:**
- Purpose: Assemble individual process models into unit subsystems, flowsheets, and connected plants.
- Location: `src/modular_simulation/flowsheet/`, `src/modular_simulation/connection/topology/unit_process_wiring.py`, `src/modular_simulation/connection/runtime/connected_plant_orchestrator.py`
- Contains: The high-level `Flowsheet` builder in `src/modular_simulation/flowsheet/flowsheet.py`, subsystem creation in `src/modular_simulation/connection/topology/unit_process_wiring.py`, and macro-step plant orchestration in `src/modular_simulation/connection/runtime/connected_plant_orchestrator.py`.
- Depends on: `src/modular_simulation/framework/system.py`, `src/modular_simulation/connection/runtime/runtime.py`, `src/modular_simulation/connection/topology/network.py`, and `src/modular_simulation/thermodynamics/runtime_context.py`.
- Used by: Examples in `examples/unit_process_flowsheet/`, gameplay start bundles in `src/modular_simulation/gameplay/start_runtime.py`, and integration tests in `tests/unit_process/` and `tests/connection/`.

**Connection Domain Layer:**
- Purpose: Own graph declarations, port compatibility, subsystem descriptors, and deterministic mutation contracts.
- Location: `src/modular_simulation/connection/topology/`, `src/modular_simulation/connection/domain/`
- Contains: Graph value objects in `src/modular_simulation/connection/topology/topology.py`, mutable network owner in `src/modular_simulation/connection/topology/network.py`, port binding rules in `src/modular_simulation/connection/topology/process_binding.py`, and subsystem descriptors in `src/modular_simulation/connection/topology/subsystem_descriptor.py`.
- Depends on: Validation helpers in `src/modular_simulation/validation/exceptions.py` and hydraulic/runtime modules for compilation hooks.
- Used by: `src/modular_simulation/cli/backend_session.py`, `src/modular_simulation/flowsheet/flowsheet.py`, and runtime code in `src/modular_simulation/connection/runtime/`.

**Connection Runtime Layer:**
- Purpose: Execute deterministic macro-step coupling, hot-install reconfiguration barriers, transport updates, and observability snapshots.
- Location: `src/modular_simulation/connection/runtime/`
- Contains: The main runtime orchestrator in `src/modular_simulation/connection/runtime/runtime.py`, macro-coupling sequence in `src/modular_simulation/connection/runtime/connection_layer.py`, plant coordination in `src/modular_simulation/connection/runtime/connected_plant_orchestrator.py`, and stream/boundary adapters in `src/modular_simulation/connection/runtime/process_stream_io.py`.
- Depends on: `src/modular_simulation/connection/topology/network.py`, `src/modular_simulation/connection/hydraulics/`, and process-facing types from `src/modular_simulation/thermodynamics/`.
- Used by: `src/modular_simulation/flowsheet/flowsheet.py`, `src/modular_simulation/cli/backend_session.py`, and connection tests under `tests/connection/`.

**Hydraulics Compilation / Solve Layer:**
- Purpose: Compile topology into solvable hydraulic systems and solve for flows and pressures.
- Location: `src/modular_simulation/connection/hydraulics/`
- Contains: Graph compilation lifecycle in `src/modular_simulation/connection/hydraulics/hydraulic_compile.py`, equation/system data structures in `src/modular_simulation/connection/hydraulics/hydraulic_solver.py`, and element contracts in `src/modular_simulation/connection/hydraulics/hydraulic_element.py`.
- Depends on: Topology metadata from `src/modular_simulation/connection/topology/network.py` and domain contracts in `src/modular_simulation/connection/domain/`.
- Used by: `src/modular_simulation/connection/runtime/runtime.py`, `src/modular_simulation/flowsheet/flowsheet.py`, and tests in `tests/connection/test_hydraulic_*.py`.

**Core Simulation Layer:**
- Purpose: Define process-model state, point registries, sensors/calculations/controllers, and time stepping.
- Location: `src/modular_simulation/measurables/`, `src/modular_simulation/framework/`, `src/modular_simulation/components/`
- Contains: Abstract process models in `src/modular_simulation/measurables/process_model.py`, the runtime container in `src/modular_simulation/framework/system.py`, component base classes in `src/modular_simulation/components/abstract_component.py`, and point publication in `src/modular_simulation/components/point/point_registry.py`.
- Depends on: `src/modular_simulation/utils/`, `src/modular_simulation/validation/`, and thermodynamic data structures.
- Used by: Every unit process module, subsystem wiring, and persistence/runtime APIs.

**Physical Domain Layer:**
- Purpose: Implement reusable thermodynamics, kinetics, streams, and unit operations.
- Location: `src/modular_simulation/thermodynamics/`, `src/modular_simulation/unit_processes/`
- Contains: Species/property/runtime context classes in `src/modular_simulation/thermodynamics/runtime_context.py`, `src/modular_simulation/thermodynamics/property_package.py`, and `src/modular_simulation/thermodynamics/stream.py`; concrete equipment in `src/modular_simulation/unit_processes/reactors/`, `src/modular_simulation/unit_processes/separation/`, `src/modular_simulation/unit_processes/storage/`, and `src/modular_simulation/unit_processes/thermal/`.
- Depends on: `src/modular_simulation/measurables/process_model.py`
- Used by: `src/modular_simulation/flowsheet/flowsheet.py`, examples in `examples/`, and gameplay unit metadata resolution in `src/modular_simulation/gameplay/realtime_service.py`.

## Data Flow

**Standalone Unit Runtime:**

1. A concrete process model subclass from `src/modular_simulation/unit_processes/` inherits `ProcessModel` from `src/modular_simulation/measurables/process_model.py` and declares state metadata plus solver callbacks.
2. `System` in `src/modular_simulation/framework/system.py` attaches the model, registers raw points in `PointRegistry`, then installs sensors, calculations, and control elements in dependency order.
3. Components publish updated measurements and references through `PointRegistry` in `src/modular_simulation/components/point/point_registry.py` while `ProcessModel.step()` advances the physical state.

**Connected Plant Runtime:**

1. `Flowsheet.add_unit()` in `src/modular_simulation/flowsheet/flowsheet.py` converts each unit into a `Subsystem` via `create_subsystem_for_unit()` in `src/modular_simulation/connection/topology/unit_process_wiring.py`.
2. `ConnectionNetwork` in `src/modular_simulation/connection/topology/network.py` owns declared processes, boundaries, junctions, edges, and line hydraulic configuration.
3. `ConnectedPlantOrchestrator.initialize()` in `src/modular_simulation/connection/runtime/connected_plant_orchestrator.py` validates that subsystem descriptors match compiled topology.
4. Each macro-step runs the fixed phase order from `CONNECTED_PLANT_PHASE_ORDER` in `src/modular_simulation/connection/runtime/runtime.py`: subsystem sensors, subsystem calculations, plant calculations, subsystem controllers, subsystem process stepping, then connection runtime coupling.
5. During coupling, `MacroCoupler.run()` in `src/modular_simulation/connection/runtime/connection_layer.py` executes hydraulics solve, transport/mixing update, and boundary state propagation, optionally with Picard iterations.

**Gameplay Request Flow:**

1. FastAPI routes in `src/modular_simulation/app/game_api.py` validate primitive request payloads and map domain errors to JSON responses.
2. Route handlers call module-level service functions in `src/modular_simulation/gameplay/realtime_service.py`.
3. `RealtimeGameService` creates a `StartRuntimeBundle` via `src/modular_simulation/gameplay/start_runtime.py`, which composes `SandboxSessionRuntime`, `CashLedgerRuntime`, `ConnectionNetwork`, and `PlantBackendSession`.
4. Build or session commands translate into backend mutations through `PlantBackendSession` in `src/modular_simulation/cli/backend_session.py` and into inventory/progression updates through `SandboxSessionRuntime` in `src/modular_simulation/gameplay/sandbox_session.py`.
5. Snapshots returned to the API combine gameplay state, board layout, and backend simulation state from the active runtime bundle.

**State Management:**
- Physical state is owned by `ProcessModel` instances in `src/modular_simulation/measurables/process_model.py`.
- Measurement and controller state is cached in `System` private attributes and `PointRegistry` inside `src/modular_simulation/framework/system.py`.
- Network topology and pending reconfiguration state are owned by `ConnectionNetwork` in `src/modular_simulation/connection/topology/network.py`.
- Runtime barrier state, idempotency, and port snapshots are owned by `ConnectionRuntimeOrchestrator` in `src/modular_simulation/connection/runtime/runtime.py`.
- Session/gameplay state is owned by dataclasses inside `src/modular_simulation/gameplay/sandbox_session.py` and `src/modular_simulation/gameplay/realtime_service.py`.

## Key Abstractions

**ProcessModel:**
- Purpose: Base abstraction for all simulated equipment and process models.
- Examples: `src/modular_simulation/measurables/process_model.py`, `src/modular_simulation/unit_processes/thermal/heater_cooler.py`, `src/modular_simulation/unit_processes/separation/flash_drum.py`
- Pattern: Abstract base model with metadata-driven state views and solver hooks.

**System:**
- Purpose: Runtime container that installs components around one `ProcessModel` and keeps tags/history synchronized.
- Examples: `src/modular_simulation/framework/system.py`, `src/modular_simulation/connection/topology/unit_process_wiring.py`
- Pattern: Composition root / orchestrator for local process runtime.

**Subsystem + SubsystemRuntimeDescriptor:**
- Purpose: Wrap one `System` so it can participate inside a plant-wide connection network.
- Examples: `src/modular_simulation/connection/topology/subsystem_descriptor.py`, `src/modular_simulation/connection/topology/unit_process_wiring.py`
- Pattern: Adapter between local process runtime and plant-scoped orchestration.

**ConnectionNetwork:**
- Purpose: Mutable owner of process/junction/boundary graph declarations, queued reconfiguration requests, and compiled network state.
- Examples: `src/modular_simulation/connection/topology/network.py`, `src/modular_simulation/cli/backend_session.py`
- Pattern: Aggregate root with compile cache and transaction queue.

**ConnectedPlantOrchestrator:**
- Purpose: Coordinate subsystem phases with connection runtime coupling for a compiled plant.
- Examples: `src/modular_simulation/connection/runtime/connected_plant_orchestrator.py`, `src/modular_simulation/flowsheet/flowsheet.py`
- Pattern: Deterministic macro-step orchestrator.

**PlantBackendSession / TxHandle:**
- Purpose: Provide a typed transactional editing surface for interactive frontends.
- Examples: `src/modular_simulation/cli/backend_session.py`
- Pattern: Facade plus unit-of-work style transaction handle.

**SimulationRuntimeContext:**
- Purpose: Carry species registry, property package, and reaction sets that must be shared across units.
- Examples: `src/modular_simulation/thermodynamics/runtime_context.py`, `src/modular_simulation/flowsheet/flowsheet.py`
- Pattern: Immutable context object passed through composition boundaries.

## Entry Points

**FastAPI Game API:**
- Location: `src/modular_simulation/app/game_api.py`
- Triggers: ASGI import of `app` or direct use of `create_app()`.
- Responsibilities: Define `/game/*` routes, validate payload primitives, and translate `SandboxRequestError` into HTTP responses.

**NiceGUI Demo App:**
- Location: `src/modular_simulation/app/main.py`
- Triggers: Direct module execution.
- Responsibilities: Start a minimal NiceGUI UI; this file is isolated from the main gameplay/backend architecture.

**Plant Backend Session Facade:**
- Location: `src/modular_simulation/cli/backend_session.py`
- Triggers: Constructed by gameplay runtime composition in `src/modular_simulation/gameplay/start_runtime.py` and by tests under `tests/cli/`.
- Responsibilities: Begin transactions, queue typed network mutations, trigger barrier commits, and expose save/load and step operations.

**Gameplay Runtime Composition:**
- Location: `src/modular_simulation/gameplay/start_runtime.py`
- Triggers: `RealtimeGameService.create_session()` in `src/modular_simulation/gameplay/realtime_service.py`.
- Responsibilities: Build the authoritative runtime bundle for each supported mode.

**Examples / Manual Scripts:**
- Location: `examples/connection_layer/`, `examples/unit_process_flowsheet/`, `examples/dynamic_simulation_demos/`
- Triggers: Direct `python` execution via `if __name__ == "__main__"` blocks in files such as `examples/connection_layer/two_tank_reaction_comparison.py` and `examples/unit_process_flowsheet/flowsheet_demo.py`.
- Responsibilities: Exercise flowsheet assembly, connected runtime, and scenario demos outside the API.

## Error Handling

**Strategy:** Fail fast with explicit domain exceptions and structured diagnostics at layer boundaries.

**Patterns:**
- Graph and binding validation raise `ValueError` or `BindingError` in `src/modular_simulation/connection/topology/topology.py` and `src/modular_simulation/connection/topology/process_binding.py` before runtime execution begins.
- Structural pre-step failures are normalized through `src/modular_simulation/connection/domain/structural_rejection.py`, which preserves machine-readable diagnostic details while tagging compile, barrier, invariant, and hydraulic solvability failures as `structural_inconsistency` before macro-step mutation proceeds.
- Barrier and runtime failures are wrapped into structured reports and diagnostics in `src/modular_simulation/connection/runtime/runtime.py` and `src/modular_simulation/cli/backend_session.py`.
- API-specific failures are normalized into JSON error payloads in `src/modular_simulation/app/game_api.py`.
- Component wiring errors use domain-specific validation exceptions from `src/modular_simulation/validation/exceptions.py` and are raised during subsystem or system installation.

## Cross-Cutting Concerns

**Logging:** Logging is initialized with the standard library logger in `src/modular_simulation/framework/system.py`; most other modules prefer explicit return diagnostics over pervasive logging.
**Validation:** Pydantic models validate core simulation objects in `src/modular_simulation/measurables/process_model.py` and `src/modular_simulation/framework/system.py`, while connection/runtime modules use explicit guard methods and deterministic error catalogs in `src/modular_simulation/connection/domain/`.
**Authentication:** Not detected in `src/modular_simulation/app/game_api.py` or `src/modular_simulation/gameplay/`; the game API is an unauthenticated local service surface.

---

*Architecture analysis: 2026-03-29*

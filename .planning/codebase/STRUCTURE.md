# Codebase Structure

**Analysis Date:** 2026-03-29

## Directory Layout

```text
[project-root]/
├── src/modular_simulation/           # Python package with simulation, connection, gameplay, and app code
├── tests/                            # Pytest suites grouped by domain area
├── examples/                         # Runnable scenario and demo scripts
├── clients/godot_phase1_vertical_slice/ # Godot client for the phase-1 vertical slice
├── docs/                             # Architecture notes, guides, and diagrams
├── openspec/                         # OpenSpec specs and active/archive change artifacts
├── .planning/codebase/               # Generated codebase mapping documents
├── pyproject.toml                    # Python project, dependency, and tool configuration
└── verify_serialization.py           # Standalone verification script
```

## Directory Purposes

**`src/modular_simulation/app/`:**
- Purpose: Delivery-layer application entry points.
- Contains: `src/modular_simulation/app/game_api.py` and `src/modular_simulation/app/main.py`.
- Key files: `src/modular_simulation/app/game_api.py`, `src/modular_simulation/app/main.py`

**`src/modular_simulation/cli/`:**
- Purpose: Interactive and workflow-facing façades around simulation/network operations.
- Contains: Transactional backend session APIs and spec workflow helpers.
- Key files: `src/modular_simulation/cli/backend_session.py`, `src/modular_simulation/cli/spec_workflow.py`

**`src/modular_simulation/components/`:**
- Purpose: Reusable runtime components that attach to `System`.
- Contains: Base component contracts, points, sensors, calculations, and control-system logic.
- Key files: `src/modular_simulation/components/abstract_component.py`, `src/modular_simulation/components/point/point_registry.py`, `src/modular_simulation/components/control_system/runtime_wiring_api.py`

**`src/modular_simulation/connection/`:**
- Purpose: Connected-plant graph, hydraulics, runtime coupling, and reconfiguration APIs.
- Contains: `domain/`, `topology/`, `hydraulics/`, and `runtime/` subpackages.
- Key files: `src/modular_simulation/connection/topology/network.py`, `src/modular_simulation/connection/runtime/runtime.py`, `src/modular_simulation/connection/hydraulics/hydraulic_compile.py`, `src/modular_simulation/connection/domain/structural_rejection.py`

**`src/modular_simulation/flowsheet/`:**
- Purpose: High-level flowsheet builder and simulation runner.
- Contains: The monolithic `Flowsheet` implementation.
- Key files: `src/modular_simulation/flowsheet/flowsheet.py`

**`src/modular_simulation/framework/`:**
- Purpose: Core process runtime container.
- Contains: The `System` abstraction and package exports.
- Key files: `src/modular_simulation/framework/system.py`

**`src/modular_simulation/gameplay/`:**
- Purpose: Game/session state, catalogs, progression, economics, and realtime orchestration.
- Contains: Service objects, dataclass contracts, and start builders.
- Key files: `src/modular_simulation/gameplay/realtime_service.py`, `src/modular_simulation/gameplay/sandbox_session.py`, `src/modular_simulation/gameplay/start_runtime.py`, `src/modular_simulation/gameplay/starts/builders.py`

**`src/modular_simulation/measurables/`:**
- Purpose: Core process-model abstractions and control-surface contracts.
- Contains: `ProcessModel` and measurable interfaces.
- Key files: `src/modular_simulation/measurables/process_model.py`, `src/modular_simulation/measurables/control_surface_contract.py`

**`src/modular_simulation/thermodynamics/`:**
- Purpose: Shared physical-domain types and runtime context.
- Contains: Property packages, species registries, streams, kinetics, and hydraulic adapters.
- Key files: `src/modular_simulation/thermodynamics/runtime_context.py`, `src/modular_simulation/thermodynamics/property_package.py`, `src/modular_simulation/thermodynamics/stream.py`

**`src/modular_simulation/unit_processes/`:**
- Purpose: Concrete process equipment grouped by domain.
- Contains: `analysis/`, `reactors/`, `separation/`, `storage/`, and `thermal/` modules plus smaller namespace packages such as `flow/` and `mixing/`.
- Key files: `src/modular_simulation/unit_processes/reactors/cstr.py`, `src/modular_simulation/unit_processes/separation/flash_drum.py`, `src/modular_simulation/unit_processes/storage/holding_tank.py`, `src/modular_simulation/unit_processes/thermal/heater_cooler.py`

**`src/modular_simulation/utils/`:**
- Purpose: Small cross-cutting helpers used across the package.
- Contains: Typing aliases, metadata extraction, wrappers, and numerical helpers.
- Key files: `src/modular_simulation/utils/typing.py`, `src/modular_simulation/utils/metadata_extraction.py`, `src/modular_simulation/utils/wrappers.py`

**`src/modular_simulation/validation/`:**
- Purpose: Shared exception types.
- Contains: Validation exception definitions.
- Key files: `src/modular_simulation/validation/exceptions.py`

**`tests/`:**
- Purpose: Pytest suite organized by domain-facing package or integration scope.
- Contains: Top-level regression tests plus domain directories such as `tests/connection/`, `tests/gameplay/`, `tests/unit_process/`, `tests/components/`, `tests/app/`, `tests/cli/`, and `tests/integration/`.
- Key files: `tests/conftest.py`, `tests/connection/test_connected_plant_orchestrator.py`, `tests/gameplay/test_realtime_game_service.py`, `tests/unit_process/test_flowsheet_integration.py`

**`examples/`:**
- Purpose: Runnable demonstrations and exploratory scripts.
- Contains: `examples/connection_layer/`, `examples/unit_process_flowsheet/`, `examples/dynamic_simulation_demos/`, and other scenario folders.
- Key files: `examples/connection_layer/two_tank_reaction_comparison.py`, `examples/unit_process_flowsheet/flowsheet_demo.py`, `examples/dynamic_simulation_demos/run_all.py`

**`clients/godot_phase1_vertical_slice/`:**
- Purpose: Godot frontend for the gameplay vertical slice.
- Contains: `scripts/`, `scenes/`, project config, and Godot smoke tests.
- Key files: `clients/godot_phase1_vertical_slice/project.godot`, `clients/godot_phase1_vertical_slice/scripts/backend_client.gd`, `clients/godot_phase1_vertical_slice/scripts/world_renderer.gd`

**`docs/`:**
- Purpose: Human-authored reference material and diagrams.
- Contains: Backend overviews, API guides, discoverability policies, and Mermaid diagrams.
- Key files: `docs/README.md`, `docs/game_backend_overview.md`, `docs/plant_backend_session_user_guide.md`

**`openspec/`:**
- Purpose: Product/spec workflow artifacts.
- Contains: `specs/`, `changes/`, and workflow config.
- Key files: `openspec/config.yaml`, `openspec/specs/session/spec.md`

## Key File Locations

**Entry Points:**
- `src/modular_simulation/app/game_api.py`: Main HTTP API surface.
- `src/modular_simulation/app/main.py`: NiceGUI demo entry point.
- `src/modular_simulation/gameplay/start_runtime.py`: Runtime composition root for supported gameplay modes.
- `examples/connection_layer/two_tank_reaction_comparison.py`: Representative command-line example script.
- `examples/unit_process_flowsheet/flowsheet_demo.py`: Representative flowsheet demo script.

**Configuration:**
- `pyproject.toml`: Dependencies, Python version, pytest, ruff, and packaging configuration.
- `pyrightconfig.json`: Type-checker configuration.
- `opencode.json`: Local OpenCode tooling configuration.
- `openspec/config.yaml`: OpenSpec workflow configuration.
- `clients/godot_phase1_vertical_slice/project.godot`: Godot project configuration.

**Core Logic:**
- `src/modular_simulation/measurables/process_model.py`: Base process-model contract.
- `src/modular_simulation/framework/system.py`: Core runtime container.
- `src/modular_simulation/flowsheet/flowsheet.py`: Flowsheet assembly and simulation.
- `src/modular_simulation/connection/topology/network.py`: Mutable network aggregate.
- `src/modular_simulation/connection/runtime/runtime.py`: Macro-step and barrier runtime.
- `src/modular_simulation/gameplay/realtime_service.py`: Authoritative gameplay service.

**Testing:**
- `tests/conftest.py`: Shared pytest fixtures.
- `tests/connection/`: Connection/hydraulics/runtime contract tests.
- `tests/gameplay/`: Gameplay and realtime service tests.
- `tests/unit_process/`: Unit-process and flowsheet tests.
- `tests/integration/`: End-to-end smoke and workflow tests.

## Naming Conventions

**Files:**
- Python modules use `snake_case.py`: `src/modular_simulation/gameplay/realtime_service.py`, `src/modular_simulation/connection/topology/subsystem_descriptor.py`.
- Test files use `test_*.py`: `tests/connection/test_network_api.py`, `tests/gameplay/test_sandbox_session.py`.
- Godot scripts also use `snake_case.gd`: `clients/godot_phase1_vertical_slice/scripts/session_store.gd`.

**Directories:**
- Package directories are lowercase and usually domain-oriented: `src/modular_simulation/gameplay/`, `src/modular_simulation/connection/runtime/`, `src/modular_simulation/unit_processes/separation/`.
- Tests mirror the domain they cover rather than the exact source tree: `tests/connection/`, `tests/gameplay/`, `tests/unit_process/`.

## Where to Add New Code

**New Feature:**
- API/backend gameplay behavior: add service logic in `src/modular_simulation/gameplay/` and expose it from `src/modular_simulation/app/game_api.py` only if it needs HTTP access.
- Connected-network behavior: place graph contracts in `src/modular_simulation/connection/topology/`, runtime sequencing in `src/modular_simulation/connection/runtime/`, and hydraulic solve/compile logic in `src/modular_simulation/connection/hydraulics/`.
- Tests: add domain-aligned pytest coverage under `tests/gameplay/`, `tests/connection/`, `tests/unit_process/`, or `tests/integration/`.

**New Component/Module:**
- New process model or equipment: add it under the matching unit-operation domain in `src/modular_simulation/unit_processes/`.
- New shared runtime component: add it under `src/modular_simulation/components/`.
- New package-wide physical helper: add it under `src/modular_simulation/thermodynamics/`.

**Utilities:**
- Shared helpers: `src/modular_simulation/utils/`
- Shared validation errors: `src/modular_simulation/validation/exceptions.py`

## Special Directories

**`src/modular_simulation.egg-info/`:**
- Purpose: Packaging metadata generated by editable/build installs.
- Generated: Yes
- Committed: Yes

**`.planning/codebase/`:**
- Purpose: Generated mapping documents for planning/execution agents.
- Generated: Yes
- Committed: Intended to be committed when refreshed.

**`openspec/changes/`:**
- Purpose: Active and archived change artifacts.
- Generated: No
- Committed: Yes

**`clients/godot_phase1_vertical_slice/tests/`:**
- Purpose: Godot-side smoke coverage for the vertical slice.
- Generated: No
- Committed: Yes

---

*Structure analysis: 2026-03-29*

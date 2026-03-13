# LLM_CONTEXT.md - Architectural Context for Agentic Work

> Purpose: this file is the architecture map for coding agents.
> For commands, workflow, and style rules, use `AGENTS.md` as the primary source.

## Scope and Priority

- This repository uses a two-file agent guidance model:
  - `AGENTS.md`: build/test/lint commands, style, workflow, safety rules.
  - `LLM_CONTEXT.md`: architecture, runtime behavior, data flow, extension points.
- If guidance differs:
  1. explicit user instruction,
  2. `AGENTS.md`,
  3. `LLM_CONTEXT.md`.
- Keep this file at repo root. Do not split into module-level `AGENTS.md` files unless
  the codebase grows into multiple independently-owned packages.

## Repository Mental Model

- Package root: `src/modular_simulation/`.
- Core abstraction: `System` orchestrates one `ProcessModel` plus component collections.
- Components are template-method based (`install`, `update`, `should_update`) and include:
  - sensors,
  - calculations,
  - control elements (optionally with controllers).
- Shared data exchange is through `PointRegistry` + `Point` + `DataValue`.

## Runtime Loop (Ground Truth)

Primary loop is in `src/modular_simulation/framework/system.py`.

1. `System.step(duration)` computes `nsteps = round(duration / dt)`.
2. Each logical step runs in fixed order:
   - `_update_components()`
   - `process_model.step(dt)`
   - point/history synchronization
3. `_update_components()` runs in dependency-safe sequence:
   - sensors -> calculations -> control elements.

Why this matters:
- Calculations depend on sensor outputs.
- Controllers/control elements can depend on both sensors and calculations.
- Reordering can subtly break closed-loop behavior.

## System Initialization and Wiring

`System.model_post_init` performs core bootstrapping:

- Validates resolvability of sensor and control-element tags.
- Calls `process_model.attach_system(self)`.
- Registers all process-model states into `PointRegistry` with raw tags:
  - format: `(raw, {StateType})_{state_name}`.
- Installs components in strict order:
  1. sensors,
  2. calculations (with iterative dependency resolution),
  3. control elements.
- Aggregates unresolved wiring issues via `ExceptionGroup`.

Do not bypass registry-based wiring with ad-hoc object mutation.

## ProcessModel Contract

Defined in `src/modular_simulation/measurables/process_model.py`.

### State typing model

- State metadata is declared with `Annotated[..., StateMetadata(...)]`.
- Categories are fixed enum values:
  - `DIFFERENTIAL`
  - `ALGEBRAIC`
  - `CONTROLLED`
  - `CONSTANT`
- States are surfaced through categorized array views (`CategorizedStateView`) with
  deterministic name->index mapping.

### Numerical API contract

Subclasses must provide stateless static methods:

- `calculate_algebraic_values(y, u, k, y_map, u_map, k_map, algebraic_map, algebraic_size)`
- `differential_rhs(t, y, u, k, algebraic, y_map, u_map, k_map, algebraic_map)`

Implementation notes:
- Treat these methods as pure functions over arrays/maps.
- Use `y_map`/`u_map`/`k_map`/`algebraic_map` for indexing.
- Avoid reading instance attributes inside these static methods.

### Integration behavior

- `ProcessModel.step(dt)` uses `scipy.integrate.solve_ivp`.
- `_rhs_wrapper` recomputes algebraic values on each solver callback before evaluating RHS.
- After successful integration, final differential and algebraic states are written back,
  and `t` advances.

## Units and Conversion Model

- Units use `astropy.units`.
- `StateMetadata.unit` defines intrinsic process-model units.
- Conversion helpers:
  - `make_converted_getter`
  - `make_converted_setter`
- Sensors and control elements can bridge between registry/process units and requested units.

Practical rule: keep equation internals unit-consistent; rely on conversion helpers at IO edges.

## Component Contracts

Base class: `src/modular_simulation/components/abstract_component.py`.

- Public lifecycle API:
  - `install(system)`
  - `update(t)`
  - `should_update(t)`
  - `save()` / `load()`
- Subclasses implement private hooks (`_install`, `_update`, `_should_update`, etc.).
- Update paths return `ComponentUpdateResult` with `data_value` and `exceptions`.

### Sensors

- Defined via `AbstractSensor`.
- Typically read process truth or registry values, then emit measured points.
- Fault/noise behavior can alter quality (`ok`) and emitted value.

### Calculations

- Defined via `AbstractCalculation`.
- Inputs/outputs are metadata-driven (`PointMetadata`, `TagType`).
- Inputs are wired via converted getters from `PointRegistry`.

### Control elements

- Defined via `ControlElement`.
- Can bind manipulated variable tags to process-model states or registry points.
- Operate in `MANUAL` or `AUTO`, optionally driven by controller chains.

## Persistence Model

- `ProcessModel`, `System`, and components expose `save()` / `load()` payloads.
- Serialization stores `type` + `module` and reconstructs classes via dynamic import.
- Preserve payload compatibility when changing runtime state/config fields.

## Error Model

- Domain exceptions live in `src/modular_simulation/validation/exceptions.py`.
- Configuration/wiring errors should prefer domain-specific exceptions.
- Multi-error startup failures are intentionally surfaced as `ExceptionGroup`.

## High-Value Files for Fast Orientation

- `src/modular_simulation/framework/system.py`
- `src/modular_simulation/measurables/process_model.py`
- `src/modular_simulation/components/abstract_component.py`
- `src/modular_simulation/components/control_system/control_element.py`
- `src/modular_simulation/components/sensors/abstract_sensor.py`
- `src/modular_simulation/components/calculations/abstract_calculation.py`
- `src/modular_simulation/validation/exceptions.py`
- `tests/conftest.py`

## Agent Working Heuristics

- Follow existing ordering and wiring semantics before attempting refactors.
- For bug fixes: prefer surgical edits in the smallest relevant module.
- Add/update tests around `System.step()` interactions when behavior changes cross components.
- Use UV-first verification commands (`uv run python -m pytest`, `uv run python -m ruff check`, `uv run --with mypy python -m mypy`).

## Current-Repo Notes (2026-02)

- Root README in working tree is `readme.md`.
- No Cursor rules detected at `.cursor/rules/**` or `.cursorrules`.
- No Copilot instructions detected at `.github/copilot-instructions.md`.

## Connection Migration and Connected-Plant Guidance

Use the connected-plant path as the active default for connection-layer work.

- Primary runtime composition:
  - `SubsystemRuntimeDescriptor` describes subsystem identity, process binding identity, and publication map.
  - `Subsystem` owns subsystem-local installers and phase execution (`run_sensor_phase`, `run_calculation_phase`, `run_controller_phase`, `run_process_phase`).
  - `ConnectedPlantOrchestrator` coordinates macro-step phase ordering and runtime coupling.
- Subsystem installer contract:
  - `Subsystem.add_sensor(...)` and `Subsystem.add_control_element(...)` validate tags against the subsystem-local published process view.
  - Invalid tags fail fast with explicit configuration errors, no silent fallback wiring.
- Plant calculation contract:
  - Register with `ConnectedPlantOrchestrator.add_calculation(calculation_id, input_tags, output_tags, evaluate)`.
  - Output-tag collisions are rejected against both subsystem publications and existing plant-calculation outputs.
  - Resolution order is deterministic from published subsystem keys plus previously resolved plant outputs.
  - Unresolvable sets raise an `ExceptionGroup` listing per-calculation missing inputs.
- Publication key and namespacing rules:
  - Canonical key shape is `<subsystem>/<published_tag>`.
  - Bare publication tags are normalized to `<descriptor_id>/<published_tag>`.
  - Cross-subsystem collisions on the same published tag are fail-fast and identify both subsystem owners.

### Break-and-replace API mapping

Legacy process-interface symbols are intentionally removed in `modular_simulation.connection.process_interface`.

- `ProcessInterface` -> `ConnectionNetwork.compile().process_bindings['<process_id>']` + `ProcessBinding.bind_inlets(...)` / `ProcessBinding.bind_outlets(...)`
- `ProcessModelAdapter` -> `ConnectionNetwork.compile().process_bindings['<process_id>']`
- `ProcessBalanceTerm` -> `ProcessBinding.get_outlet('<port_name>')` fields (`normalized_inlet_flow`, `inlet_flow`, `outlet_flow`)

Guardrail expectation:

- Removed symbols raise `AttributeError` with actionable migration guidance.
- Legacy flow should not be documented or presented as recommended fallback behavior.

### Example command for migrated path

- Run `uv run python examples/connection_layer/two_tank_reaction_comparison.py --no-show`.
- Expect printed trajectory rows and parity metrics (`max_abs_error_a`, `max_abs_error_b`, `rmse_b`, `b_lag_steps`, monotonic flags).

### Pytest `-k` expression rule

- `pytest -k` requires a valid boolean expression.
- Use forms like `-k "save and load and continue"`, not plain spaced text like `-k "save load continue"`.

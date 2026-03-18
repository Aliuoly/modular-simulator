# Modular Simulation Framework

`modular_simulation` is a lightweight framework for building closed-loop process simulations. It separates the physical model, instrumentation, and control logic into composable pieces, allowing new systems to be assembled from small, well-typed components.

The framework is intended to be used for learning about controller design, trying out different controller algorithms, and performing system identification.

## Key Features

*   **Modular Design**: Easily compose systems using pre-built or custom Sensors, Controllers, and Process Models.
*   **DAE Support**: Implements a workaround to allow `scipy.integrate.solve_ivp` (which typically handles ODEs) to solve Differential-Algebraic Equation (DAE) systems by recomputing algebraic variables at every solver step.
*   **Type Safety**: Built on Pydantic and fully typed Python to ensure correctness and provide excellent IDE support.
*   **Unit-Aware**: Utilizes `astropy` for unit management. However, process governing equations are not unit-validated.  

## Available Components

The framework comes with a set of pre-built components to get you started:

*   **Controllers** (`modular_simulation.components.control_system.controllers`):
    *   `PIDController`: Standard PID algorithm with anti-windup, setpoint weighting, and derivative filtering.
    *   `BangBangController`: Simple on/off control with deadband.
    *   `InternalModelController`: Model-based control using an internal process model.
    *   `FirstOrderTrajectoryController`: Computes MV to drive CV along a desired first-order trajectory.
    *   `MVController`: Pass-through controller that sets MV directly to the setpoint value.
*   **Sensors** (`modular_simulation.components.sensors`):
    *   `SampledDelayedSensor`: Simulates discrete sampling intervals and measurement delays. Also supports Gaussian noise injection and random fault simulation (drift, freeze, bias).

## Installation

Requires Python 3.13+

```bash
# Using pip
pip install .

# Using uv (recommended)
uv sync
```

## Quick Start

The repository still contains many examples, but the canonical user-facing set is intentionally small after the refactor. Start with these and use the rest of `examples/` as advanced/reference material.

The current high-level `Flowsheet` API exposes boundary feeds/sources, explicit boundary sinks via `add_sink(...)`, named junction topology via `add_junction(...)`, and line-installed controls via `connect(..., pump=PumpInstall(...), valve=ValveInstall(...), heat=HeatInstall(...))`.

### Canonical example set

| Example | Why it is in the canonical path |
| --- | --- |
| `examples/unit_process_flowsheet/easy_2_heater_flash.py` | Smallest grounded flowsheet with explicit feed, heater, flash, and product split |
| `examples/unit_process_flowsheet/easy_3_dual_feed_heat_exchanger.py` | Compact multi-branch flowsheet with explicit boundary feeds and exchanger ports |
| `examples/unit_process_flowsheet/complex_6_ammonia_recycle_loop.py` | Advanced recycle-topology flowsheet with junctions, line-installed recycle boost, separation, purge, and explicit boundary sinks |
| `examples/connection_layer/two_tank_reaction_comparison.py --no-show` | Connected-plant fidelity/parity benchmark with clear metrics |


See the curated [Examples Catalog](examples_catalog.md) for the primary/advanced split.

### Fastest starting points

```bash
uv run python examples/unit_process_flowsheet/easy_2_heater_flash.py
uv run python examples/unit_process_flowsheet/easy_3_dual_feed_heat_exchanger.py
uv run python examples/connection_layer/two_tank_reaction_comparison.py --no-show
```

These cover the shortest path to grounded flowsheet modeling, explicit multi-branch port wiring, and connected-plant fidelity checks.

## Canonical flowsheet examples

These are the preferred first examples because they keep topology explicit and the educational intent narrow.

### Heater + flash (smallest grounded path)

```bash
uv run python examples/unit_process_flowsheet/easy_2_heater_flash.py
```

What it covers:

- Single-feed flowsheet authoring
- Explicit heater-to-flash unit connectivity
- Vapor/liquid split from a compact process train

### Dual-feed heat exchange

```bash
uv run python examples/unit_process_flowsheet/easy_3_dual_feed_heat_exchanger.py
```

What it covers:

- Two explicit boundary feeds
- Port-specific exchanger wiring
- Compact multistream energy exchange behavior

### Ammonia recycle loop

```bash
uv run python examples/unit_process_flowsheet/complex_6_ammonia_recycle_loop.py
```

What it covers:

- Fresh-feed plus an explicit recycle return edge through a named junction topology
- Recycle pressure boost represented as a line-installed `PumpInstall(...)` instead of a `Pump` unit
- Downstream separation, purge, and liquid product recovery through explicit boundary sinks

## Grounded Process Examples

### Connected-plant fidelity benchmark

```bash
uv run python examples/connection_layer/two_tank_reaction_comparison.py --no-show
```

This runs the migrated subsystem-based two-tank benchmark and prints CSV-style trajectory rows plus parity metrics such as `max_abs_error_a`, `max_abs_error_b`, `rmse_b`, and `b_lag_steps`.

See the curated [Examples Catalog](examples_catalog.md) for the migration map from older examples to these canonical replacements.

### Pytest `-k` filter note

Use boolean expressions in `-k` filters. Plain space-separated words are invalid.

```bash
# valid
uv run python -m pytest -q tests/integration/test_examples_smoke.py -k "quickstart and two and process"

# invalid
uv run python -m pytest -q tests/integration/test_examples_smoke.py -k "quickstart two process"
```

## Connected-Plant API (Recommended)

The recommended authoring flow is:

1. Build topology with `ConnectionNetwork`.
2. Compile once and use `compiled.process_bindings['<process_id>']` for port binding.
3. Define each subsystem with `SubsystemRuntimeDescriptor` and `Subsystem`.
4. Install local runtime components through subsystem installers (`add_sensor`, `add_control_element`).
5. Coordinate macro-steps with `ConnectedPlantOrchestrator.step(...)`.

### Subsystem installers

- `Subsystem.add_sensor(sensor)` validates `sensor.measurement_tag` against subsystem-local published tags.
- `Subsystem.add_control_element(control_element)` validates controller CV/MV tags against subsystem-local published tags.
- Validation is fail-fast and raises explicit configuration errors when tags are unresolved.

### Plant calculations

- Register plant-level calculations with `ConnectedPlantOrchestrator.add_calculation(calculation_id, input_tags, output_tags, evaluate)`.
- Output tags must be unique and must not collide with subsystem-published tags or existing plant-calculation outputs.
- Resolution order is deterministic, based on currently published subsystem tags plus previously resolved plant outputs.
- Unresolvable dependency sets fail as an `ExceptionGroup` with per-calculation missing-input details.

### Namespaced publication keys and collision policy

- Published measurements use `<subsystem>/<published_tag>` keys.
- If a subsystem publication omits a namespace, the descriptor id is prepended automatically.
- Cross-subsystem ownership collision on the same `published_tag` fails fast.
- Collision errors are explicit, they identify the conflicting subsystems and stop registration/evaluation.

## Architecture & Interactions

The framework orchestrates interactions between the **System** (simulation engine), **Process Model** (physics/chemistry), **Sensors**, **Calculations**, and **Controllers**.

### Interaction Diagrams

We have detailed diagrams illustrating how these components interact:

*   **[Initialization Phase](docs/initialization.mermaid)**: Shows how components are added and wired up before the simulation starts.
*   **[Simulation Step](docs/simulation_step.mermaid)**: Details the order of operations during each time step (Sensors -> Calculations -> Controls -> Process).
*   **[Control Loop Example](docs/control_loop_example.mermaid)**: A specific example of a cascade control loop with a line-installed valve actuator feeding an outer level controller.
*   **[Detailed Control Interaction](docs/control_loop_interaction.mermaid)**: In-depth look at the request/response flow between Control Elements, Mode Managers, and Controllers.

### Core Components

1.  **Measurable Quantities**: The state of the world is defined in a single **`ProcessModel`** subclass.
    *   **Definition**: Users must subclass `ProcessModel` and implement two abstract methods:
        *   `differential_rhs`: Defines the system's differential equations (dx/dt).
        *   `calculate_algebraic_values`: Computes algebraic variables based on current state.
    *   **Fields**: Class attributes are annotated using **`StateMetadata`** to define their role and units.
        *   `DIFFERENTIAL`: Differential variables (integrated over time).
        *   `ALGEBRAIC`: Variables computed instantly from States.
        *   `CONTROLLED`: Actuators manipulated by control elements.
        *   `CONSTANT`: Constant parameters, such as dimensions, rate constants, etc.

2.  **Usable Quantities**:
    *   `Sensors`: Read from ProcessModel fields and add noise/delays.
    *   `Calculations`: Derive calculated values from Sensor data or other calculation results. Define inputs and outputs using **`TagMetadata`**.

    ```python
    class MyCalculation(AbstractCalculation):
        input_tag: Annotated[str, TagMetadata(TagType.INPUT, unit="m")]
        output_tag: Annotated[str, TagMetadata(TagType.OUTPUT, unit="m")]
    ```

3.  **Control System**:
    *   `ControlElements`: Receive actions from Controllers and update the Process Model.
    *   `Controllers`: Used current values of controlled variable (CV) and setpoint (SP) to calculate control action, which is sent to the ControlElement/inner loop controllers.

## Project Structure

*   `src/modular_simulation`: Core framework code.
    *   `framework`: System orchestration and time stepping.
    *   `components`: Sensors, Calculations, and Control components.
    *   `quantities`: Data structures for process state.
*   `examples`: Ready-to-run example simulations.
*   `docs`: Mermaid diagrams and documentation.

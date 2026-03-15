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

The project includes several example systems in the `examples/` directory. To run the simplified gas phase system:

```bash
uv run python examples/dynamic_api_cli/minimal_command_quickstart.py
```

This will execute the simulation and generate plots and logs demonstrating the system's behavior.

For connection-layer work, use the connected-plant flow as the default:

```bash
uv run python examples/connection_layer/two_tank_reaction_comparison.py --no-show
```

This command runs the migrated subsystem-based two-tank benchmark and prints CSV-style trajectory rows plus parity metrics such as `max_abs_error_a`, `max_abs_error_b`, `rmse_b`, and `b_lag_steps`.

## Dynamic API and CLI Quickstarts

These examples are operator-first and minimal boilerplate. Run them with UV.

### Command-based path

```bash
uv run python examples/dynamic_api_cli/minimal_command_quickstart.py
```

What it covers:

- Two-process wiring with `ModularCli` commands
- Junction-as-unit setup with `JunctionProcess`
- Barrier apply confirmation and graph revision bump

### Spec-based path

```bash
uv run python examples/dynamic_api_cli/minimal_spec_quickstart.py
```

What it covers:

- `spec_diff` preview against `examples/dynamic_api_cli/minimal_spec.json`
- `spec_apply` execution through explicit transaction batches
- Deterministic applied request ids and resulting topology shape

### Valve + sensor + controller loop, plus save/load/continue

```bash
uv run python examples/dynamic_api_cli/minimal_control_loop_save_load.py
```

What it covers:

- Runtime valve configuration and controller activation from queued mutations
- Sensor binding and control loop response (`heater_power` moves above zero)
- Save/load/continue round trip for both direct API (`ConnectionNetwork`) and CLI (`ModularCli`)

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
*   **[Control Loop Example](docs/control_loop_example.mermaid)**: A specific example of a cascade control loop (Valve -> Flow Controller -> Level Controller).
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

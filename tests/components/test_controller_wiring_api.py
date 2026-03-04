from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import cast

import pytest

from modular_simulation.components.control_system import (
    ControlElement,
    ControllerMode,
    ControllerRuntimeWiringApi,
    Trajectory,
)
from modular_simulation.components.sensors import SampledDelayedSensor
from modular_simulation.connection.hydraulic_compile import (
    HydraulicCompileLifecycle,
    solve_compiled_hydraulic_graph,
)
from modular_simulation.connection.hydraulic_solver import (
    HydraulicSolveResult,
    HydraulicSystemDefinition,
    LinearResidualEquation,
)
from modular_simulation.connection.network import ConnectionNetwork
from modular_simulation.connection.runtime import (
    ConnectionRuntimeOrchestrator,
    ConnectionRuntimeStepResult,
)
from modular_simulation.framework.system import System
from modular_simulation.measurables.process_model import ProcessModel


def _linear_equation(
    residual_name: str,
    coefficients: dict[str, float],
    *,
    constant: float = 0.0,
) -> LinearResidualEquation:
    return LinearResidualEquation(
        residual_name=residual_name,
        coefficients=coefficients,
        constant=constant,
    )


def _valid_system() -> HydraulicSystemDefinition:
    return HydraulicSystemDefinition(
        equations=(),
        linear_residual_equations=(
            _linear_equation("ref", {"pressure": 1.0}, constant=-5.0),
            _linear_equation("balance", {"pressure": 1.0, "flow": -1.0}),
        ),
    )


def _network(runtime: ConnectionRuntimeOrchestrator) -> ConnectionNetwork:
    network = ConnectionNetwork(
        compile_lifecycle=HydraulicCompileLifecycle(),
        hydraulic_system_builder=lambda topology: _valid_system(),
        runtime_orchestrator=runtime,
    )
    network.add_process("reactor", inlet_ports=("feed",), outlet_ports=("product",))
    network.add_boundary_source("feed_boundary")
    network.add_boundary_sink("product_boundary")
    _ = network.connect("feed_boundary", "reactor.feed")
    _ = network.connect("reactor.product", "product_boundary")
    _ = network.compile()
    return network


def _runtime_with_dispatchers(
    system: System,
    *,
    solve_observer: Callable[[HydraulicSolveResult], None] | None = None,
) -> ConnectionRuntimeOrchestrator:
    def controller_dispatcher(
        *,
        operation: str,
        mutation: Mapping[str, object],
        request_metadata: Mapping[str, object],
    ) -> None:
        system.apply_controller_runtime_mutation(
            operation=operation,
            mutation=mutation,
            request_metadata=request_metadata,
        )

    def hydraulic_solve_step(
        *,
        network: ConnectionNetwork,
        macro_step_time_s: float,
    ) -> HydraulicSolveResult:
        del macro_step_time_s
        compiled = network.compiled
        if compiled is None or compiled.hydraulic is None:
            raise RuntimeError("compiled hydraulic graph is required")
        result = solve_compiled_hydraulic_graph(compiled.hydraulic)
        if solve_observer is not None:
            solve_observer(result)
        return result

    return ConnectionRuntimeOrchestrator(
        hydraulic_solve_step=hydraulic_solve_step,
        controller_mutation_dispatcher=controller_dispatcher,
    )


def _build_system(process_model: ProcessModel) -> System:
    temperature_sensor = SampledDelayedSensor(
        name="temperature_sensor",
        measurement_tag="temperature",
        alias_tag="temperature",
        unit="K",
        sampling_period=0.0,
        deadtime=0.0,
    )
    heater = ControlElement(
        mv_tag="heater_power",
        mv_trajectory=Trajectory(y0=0.0, t0=0.0),
        mv_range=(0.0, 20.0),
        mode=ControllerMode.MANUAL,
    )
    return System(
        dt=1.0,
        process_model=process_model,
        sensors=[temperature_sensor],
        calculations=[],
        control_elements=[heater],
        show_progress=False,
    )


def test_pid_controller_wiring_drives_bound_actuator(
    thermal_process_model: ProcessModel,
) -> None:
    system = _build_system(thermal_process_model)
    runtime = _runtime_with_dispatchers(system)
    network = _network(runtime)
    api = ControllerRuntimeWiringApi(network=network)

    assert (
        api.create_controller(
            controller_id="heater_pid",
            controller_type="PIDController",
            controller_module="modular_simulation.components.control_system.controllers",
            controller_config={
                "name": "heater_pid",
                "cv_range": (250.0, 350.0),
                "Kp": 5.0,
                "Ti": 5.0,
                "Td": 0.0,
            },
        )
        == "rq_0001"
    )
    assert (
        api.bind_controller_input(controller_id="heater_pid", signal_key="temperature") == "rq_0002"
    )
    assert (
        api.bind_controller_output(controller_id="heater_pid", actuator_tag="heater_power")
        == "rq_0003"
    )
    assert api.configure_controller_mode(controller_id="heater_pid", mode="auto") == "rq_0004"
    assert api.activate_controller(controller_id="heater_pid") == "rq_0005"

    step_result = cast(ConnectionRuntimeStepResult, network.step(macro_step_time_s=0.25))
    assert step_result.barrier_reconfiguration.applied_request_ids == (
        "rq_0001",
        "rq_0002",
        "rq_0003",
        "rq_0004",
        "rq_0005",
    )

    _ = system.extend_controller_sp_trajectory("temperature", value=320.0)
    system.step(duration=1.0)
    assert float(getattr(thermal_process_model, "heater_power")) > 0.0


def test_controller_activation_rejects_unresolved_signal_tag(
    thermal_process_model: ProcessModel,
) -> None:
    system = _build_system(thermal_process_model)
    runtime = _runtime_with_dispatchers(system)
    network = _network(runtime)
    api = ControllerRuntimeWiringApi(network=network)

    _ = api.create_controller(
        controller_id="heater_pid",
        controller_type="PIDController",
        controller_module="modular_simulation.components.control_system.controllers",
        controller_config={
            "name": "heater_pid",
            "cv_range": (250.0, 350.0),
            "Kp": 3.0,
            "Ti": 5.0,
            "Td": 0.0,
        },
    )
    _ = api.bind_controller_input(controller_id="heater_pid", signal_key="unknown_tag")
    _ = api.bind_controller_output(controller_id="heater_pid", actuator_tag="heater_power")
    _ = api.configure_controller_mode(controller_id="heater_pid", mode="auto")
    _ = api.activate_controller(controller_id="heater_pid")
    before_failure = network.save_runtime_snapshot()

    with pytest.raises(
        RuntimeError,
        match=(
            "reconfiguration transaction rollback: request 'rq_0005' mutation 1 failed: "
            + "controller 'heater_pid' input signal 'unknown_tag' is unresolved"
        ),
    ):
        _ = network.step(macro_step_time_s=0.25)

    assert network.save_runtime_snapshot() == before_failure
    assert system.control_elements[0].controller is None

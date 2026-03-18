from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Annotated, cast, override

import numpy as np
import pytest
from astropy.units import UnitBase
from numpy.typing import NDArray
from pydantic import Field

from modular_simulation.components.control_system import (
    AbstractController,
    ControlElement,
    ControllerMode,
    ControllerRuntimeWiringApi,
    Trajectory,
)
from modular_simulation.components.control_system.mode_manager import ControllerModeManager
from modular_simulation.components.sensors import SampledDelayedSensor
from modular_simulation.components.point import DataValue
from modular_simulation.connection.hydraulics.hydraulic_compile import HydraulicCompileLifecycle
from modular_simulation.connection.hydraulics.hydraulic_solver import (
    HydraulicSolveResult,
    HydraulicSystemDefinition,
    LinearResidualEquation,
)
from modular_simulation.connection.topology.network import ConnectionNetwork
from modular_simulation.connection.runtime.runtime import ConnectionRuntimeOrchestrator
from modular_simulation.framework.system import System
from modular_simulation.measurables.process_model import (
    ProcessModel,
    StateMetadata as M,
    StateType as T,
)
from modular_simulation.unit_processes.flow.pump import Pump
from modular_simulation.utils.typing import ArrayIndex
from modular_simulation.utils.typing import StateValue


class ArrayAgnosticController(AbstractController):
    @override
    def _control_algorithm(
        self,
        t: float,
        cv: StateValue,
        sp: StateValue,
    ) -> tuple[StateValue, bool]:
        del t, cv
        return sp, True

    @override
    def post_wire_to_element(
        self,
        system: System,
        mv_getter: Callable[[], DataValue],
        mv_range: tuple[StateValue, StateValue],
        mv_tag: str,
        mv_unit: UnitBase,
    ) -> bool:
        del system, mv_getter, mv_range, mv_tag, mv_unit
        return True


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


def build_controller_runtime_api(
    system: System,
    *,
    solve_observer: Callable[[HydraulicSolveResult], None] | None = None,
) -> tuple[ConnectionNetwork, ControllerRuntimeWiringApi]:
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
        result = compiled.hydraulic.solve()
        if solve_observer is not None:
            solve_observer(result)
        return result

    runtime = ConnectionRuntimeOrchestrator(
        hydraulic_solve_step=hydraulic_solve_step,
        controller_mutation_dispatcher=controller_dispatcher,
    )
    network = _network(runtime)
    return network, ControllerRuntimeWiringApi(network=network)


def queue_pid_activation(
    api: ControllerRuntimeWiringApi,
    *,
    controller_id: str,
    signal_key: str,
    actuator_tag: str,
    controller_config: Mapping[str, object] | None = None,
    controller_type: str = "PIDController",
    controller_module: str = "modular_simulation.components.control_system.controllers",
) -> tuple[str, str, str, str, str]:
    controller_payload: dict[str, object] = {
        "name": controller_id,
        "cv_range": (250.0, 350.0),
    }
    if (
        controller_type == "PIDController"
        and controller_module == "modular_simulation.components.control_system.controllers"
    ):
        controller_payload.update(
            {
                "Kp": 5.0,
                "Ti": 5.0,
                "Td": 0.0,
            }
        )
    if controller_config is not None:
        controller_payload.update(controller_config)
    create_request = api.create_controller(
        controller_id=controller_id,
        controller_type=controller_type,
        controller_module=controller_module,
        controller_config=controller_payload,
    )
    bind_input_request = api.bind_controller_input(
        controller_id=controller_id,
        signal_key=signal_key,
    )
    bind_output_request = api.bind_controller_output(
        controller_id=controller_id,
        actuator_tag=actuator_tag,
    )
    mode_request = api.configure_controller_mode(
        controller_id=controller_id,
        mode="auto",
    )
    activate_request = api.activate_controller(controller_id=controller_id)
    return (
        create_request,
        bind_input_request,
        bind_output_request,
        mode_request,
        activate_request,
    )


def assert_step_rolls_back(
    network: ConnectionNetwork,
    *,
    error_match: str,
    macro_step_time_s: float = 0.25,
) -> None:
    before_failure = network.save_runtime_snapshot()
    with pytest.raises(RuntimeError, match=error_match):
        _ = network.step(macro_step_time_s=macro_step_time_s)
    assert network.save_runtime_snapshot() == before_failure


def assert_controller_activation_rolls_back(
    network: ConnectionNetwork,
    system: System,
    *,
    controller_id: str,
    error_match: str,
    macro_step_time_s: float = 0.25,
    absent_reference_tags: Sequence[str] = (),
    control_element_indexes: Sequence[int] = (0,),
) -> None:
    assert_step_rolls_back(
        network,
        error_match=error_match,
        macro_step_time_s=macro_step_time_s,
    )
    assert controller_id not in system.controller_bindings
    for point_tag in absent_reference_tags:
        assert point_tag not in system.point_registry
    for index in control_element_indexes:
        assert system.control_elements[index].controller is None


def build_scalar_thermal_system(process_model: ProcessModel) -> System:
    temperature_sensor = SampledDelayedSensor(
        name="temperature_sensor",
        measurement_tag="temperature",
        alias_tag="temperature",
        unit="K",
        sampling_period=0.0,
        deadtime=0.0,
    )
    heater = ControlElement(
        mv_tag="actuator/heat/heater_power",
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


def build_canonical_pressure_pump_system() -> System:
    pressure_sensor = SampledDelayedSensor(
        name="pump_pressure_sensor",
        measurement_tag="outlet_pressure",
        alias_tag="pressure",
        unit="Pa",
        sampling_period=0.0,
        deadtime=0.0,
    )
    actuator_sensor = SampledDelayedSensor(
        name="pump_speed_alias_sensor",
        measurement_tag="pump_speed",
        alias_tag="actuator/pump/recycle_pump",
        unit="Pa",
        sampling_period=0.0,
        deadtime=0.0,
    )
    pump_speed_element = ControlElement(
        mv_tag="actuator/pump/recycle_pump",
        mv_trajectory=Trajectory(y0=20000.0, t0=0.0),
        mv_range=(0.0, 220000.0),
        mode=ControllerMode.MANUAL,
    )
    return System(
        dt=1.0,
        process_model=Pump(
            n_species=2,
            inlet_flow=0.01,
            inlet_temperature=300.0,
            inlet_pressure=101325.0,
            inlet_composition=np.array([0.5, 0.5], dtype=np.float64),
            pump_speed=20000.0,
            efficiency=0.75,
        ),
        sensors=[pressure_sensor, actuator_sensor],
        calculations=[],
        control_elements=[pump_speed_element],
        show_progress=False,
    )


class ScalarCvVectorMvProcessModel(ProcessModel):
    temperature: Annotated[
        float, M(type=T.DIFFERENTIAL, unit="K", description="process temperature")
    ] = 300.0
    heater_power_vector: Annotated[
        NDArray[np.float64],
        M(type=T.BOUNDARY, unit="K/s", description="vectorized heating input"),
    ] = Field(default_factory=lambda: np.array([0.0, 0.0], dtype=np.float64))
    ambient_temperature: Annotated[
        float, M(type=T.CONSTANT, unit="K", description="ambient temperature")
    ] = 295.0

    @override
    @staticmethod
    def calculate_algebraic_values(
        y: NDArray[np.float64],
        u: NDArray[np.float64],
        k: NDArray[np.float64],
        y_map: dict[str, ArrayIndex],
        u_map: dict[str, ArrayIndex],
        k_map: dict[str, ArrayIndex],
        algebraic_map: dict[str, ArrayIndex],
        algebraic_size: int,
    ) -> NDArray[np.float64]:
        del y, u, k, y_map, u_map, k_map, algebraic_map
        return np.zeros(algebraic_size, dtype=np.float64)

    @override
    @staticmethod
    def differential_rhs(
        t: float,
        y: NDArray[np.float64],
        u: NDArray[np.float64],
        k: NDArray[np.float64],
        algebraic: NDArray[np.float64],
        y_map: dict[str, ArrayIndex],
        u_map: dict[str, ArrayIndex],
        k_map: dict[str, ArrayIndex],
        algebraic_map: dict[str, ArrayIndex],
    ) -> NDArray[np.float64]:
        del t, u, k, algebraic, u_map, k_map, algebraic_map
        dy = np.zeros_like(y)
        dy[cast(int, y_map["temperature"])] = 0.0
        return dy


def build_scalar_cv_vector_mv_system() -> System:
    process_model = ScalarCvVectorMvProcessModel()
    temperature_sensor = SampledDelayedSensor(
        name="temperature_sensor",
        measurement_tag="temperature",
        alias_tag="temperature",
        unit="K",
        sampling_period=0.0,
        deadtime=0.0,
    )
    vector_heater = ControlElement(
        mv_tag="actuator/heat/heater_power_vector",
        mv_trajectory=Trajectory(y0=np.zeros(2, dtype=np.float64), t0=0.0),
        mv_range=(
            np.zeros(2, dtype=np.float64),
            np.full(2, 20.0, dtype=np.float64),
        ),
        mode=ControllerMode.MANUAL,
    )
    return System(
        dt=1.0,
        process_model=process_model,
        sensors=[temperature_sensor],
        calculations=[],
        control_elements=[vector_heater],
        show_progress=False,
    )


class _CascadeSourceStub:
    def __init__(self, value: float):
        self.value = value
        self.changed_modes: list[ControllerMode] = []

    def change_control_mode(self, mode: ControllerMode | str) -> None:
        self.changed_modes.append(ControllerMode.from_value(mode))

    def update(self, t: float):
        return type("_Result", (), {"data_value": DataValue(time=t, value=self.value, ok=True)})()


def test_reference_mode_manager_auto_cascade_tracking_semantics() -> None:
    manual_source = Trajectory(y0=0.2, t0=0.0)
    auto_reference = Trajectory(y0=1.5, t0=0.0)
    cascade_source: AbstractController = cast(
        AbstractController, cast(object, _CascadeSourceStub(value=2.75))
    )
    mode_manager = ControllerModeManager(
        mode=ControllerMode.AUTO,
        manual_mv_source=manual_source,
        auto_ref_source=auto_reference,
        cascade_ref_source=cascade_source,
        mv_getter=lambda: DataValue(time=0.0, value=0.2, ok=True),
        cv_getter=lambda: DataValue(time=0.0, value=4.0, ok=True),
        reference_getter=lambda: DataValue(time=0.0, value=1.5, ok=True),
        cv_tag="temperature",
    )

    assert mode_manager.get_reference(0.1).value == pytest.approx(1.5)
    _ = mode_manager.change_mode(ControllerMode.CASCADE)
    assert mode_manager.get_reference(0.2).value == pytest.approx(2.75)
    _ = mode_manager.change_mode(ControllerMode.TRACKING)
    assert mode_manager.get_reference(0.3).value == pytest.approx(4.0)


def test_reference_mode_manager_manual_and_auto_transfer_preserve_bumpless_behavior() -> None:
    manual_source = Trajectory(y0=0.4, t0=0.0)
    auto_reference = Trajectory(y0=2.0, t0=0.0)
    cascade_source: AbstractController = cast(
        AbstractController, cast(object, _CascadeSourceStub(value=3.0))
    )
    mode_manager = ControllerModeManager(
        mode=ControllerMode.CASCADE,
        manual_mv_source=manual_source,
        auto_ref_source=auto_reference,
        cascade_ref_source=cascade_source,
        mv_getter=lambda: DataValue(time=1.0, value=0.9, ok=True),
        cv_getter=lambda: DataValue(time=1.0, value=4.0, ok=True),
        reference_getter=lambda: DataValue(time=1.0, value=1.8, ok=True),
        cv_tag="temperature",
    )

    _ = mode_manager.change_mode(ControllerMode.MANUAL)
    assert mode_manager.get_control_action(1.0).value == pytest.approx(0.9)

    _ = mode_manager.change_mode(ControllerMode.AUTO)
    cascade_stub = cast(_CascadeSourceStub, cast(object, cascade_source))
    assert cascade_stub.changed_modes[-1] == ControllerMode.TRACKING
    assert mode_manager.get_reference(1.0).value == pytest.approx(1.8)

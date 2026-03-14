import pytest
from astropy.units import Unit

from modular_simulation.components import (
    ControlElement,
    PIDController,
    SampledDelayedSensor,
    Trajectory,
)
from modular_simulation.components.point import DataValue, Point
from modular_simulation.connection.subsystem_descriptor import Subsystem, SubsystemRuntimeDescriptor
from modular_simulation.framework.system import System
from modular_simulation.measurables.process_model import ProcessModel
from modular_simulation.validation.exceptions import (
    ControllerConfigurationError,
    SensorConfigurationError,
)


def _make_subsystem(thermal_process_model: ProcessModel) -> Subsystem:
    system = System(
        dt=1.0,
        process_model=thermal_process_model,
        sensors=[],
        calculations=[],
        control_elements=[],
        show_progress=False,
    )
    heat_command_point = Point(
        tag="actuator/heat/heater_power",
        type="measured",
        unit=Unit("K/s"),
        description="staged subsystem heat actuator command",
    )
    heat_command_point.data = DataValue(time=system.time, value=0.0, ok=True)
    system.point_registry.add(heat_command_point)
    descriptor = SubsystemRuntimeDescriptor(
        descriptor_id="thermal_subsystem",
        process_id="tank_a",
        inlet_ports=("inlet",),
        outlet_ports=("outlet",),
        publication_map={"temperature": 300.0, "heater_power": 0.0},
        runtime_context=None,
    )
    return Subsystem(descriptor=descriptor, system=system)


def test_subsystem_scoped_installer_and_happy_path_sensor_and_controller_updates(
    thermal_process_model: ProcessModel,
):
    subsystem = _make_subsystem(thermal_process_model)
    sensor = SampledDelayedSensor(
        measurement_tag="temperature",
        alias_tag="temperature.local",
        unit="K",
    )
    controller = PIDController(
        cv_tag="temperature.local",
        cv_range=(200.0, 400.0),
        reference_trajectory=Trajectory(y0=315.0),
        Kp=1.5,
        Ti=4.0,
        period=0.0,
    )
    control_element = ControlElement(
        mv_tag="actuator/heat/heater_power",
        mv_range=(0.0, 25.0),
        mv_trajectory=Trajectory(y0=0.0),
        controller=controller,
    )

    _ = subsystem.add_sensor(sensor)
    _ = subsystem.add_control_element(control_element)

    measurement_count_before = len(sensor.point.history)
    subsystem.step()

    assert getattr(subsystem.system.process_model, "heater_power") == pytest.approx(0.0)
    pending_heat_commands = subsystem.system.consume_pending_heat_actuator_rate_commands()
    assert "actuator/heat/heater_power" in pending_heat_commands
    assert pending_heat_commands["actuator/heat/heater_power"] > 0.0
    assert len(sensor.point.history) > measurement_count_before


def test_subsystem_scoped_installer_and_invalid_tag_for_sensor_raises_configuration_error(
    thermal_process_model: ProcessModel,
):
    subsystem = _make_subsystem(thermal_process_model)
    sensor = SampledDelayedSensor(measurement_tag="foreign.temperature", unit="K")

    with pytest.raises(
        SensorConfigurationError,
        match="cannot resolve local measurement tag",
    ):
        _ = subsystem.add_sensor(sensor)


def test_subsystem_scoped_installer_and_invalid_tag_for_controller_raises_configuration_error(
    thermal_process_model: ProcessModel,
):
    subsystem = _make_subsystem(thermal_process_model)
    control_element = ControlElement(
        mv_tag="actuator/heat/heater_power",
        mv_range=(0.0, 25.0),
        mv_trajectory=Trajectory(y0=0.0),
        controller=PIDController(
            cv_tag="foreign.cv",
            cv_range=(200.0, 400.0),
            reference_trajectory=Trajectory(y0=310.0),
            Kp=1.0,
            Ti=3.0,
            period=0.0,
        ),
    )

    with pytest.raises(
        ControllerConfigurationError,
        match="cannot resolve local control variable tag",
    ):
        _ = subsystem.add_control_element(control_element)

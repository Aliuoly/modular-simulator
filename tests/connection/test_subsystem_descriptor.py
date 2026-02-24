import pytest
from astropy.units import Unit

from modular_simulation.components.point import DataValue, Point, PointRegistry
from modular_simulation.connection.subsystem_descriptor import Subsystem, SubsystemRuntimeDescriptor
from modular_simulation.connection.process_binding import ProcessBinding, BindingError
from modular_simulation.framework.system import System
from modular_simulation.measurables.process_model import ProcessModel
from modular_simulation.validation.exceptions import MeasurableConfigurationError


def test_valid_subsystem_descriptor():
    descriptor = SubsystemRuntimeDescriptor(
        descriptor_id="subsys1",
        process_id="tank_a",
        inlet_ports=("inlet",),
        outlet_ports=("outlet",),
        publication_map={"tank_a/level": 0.0},
        runtime_context={"ctx": 1},
    )
    binding = descriptor.to_binding()
    assert isinstance(binding, ProcessBinding)
    assert getattr(binding, "_inlet_ports") == ["inlet"]
    assert getattr(binding, "_outlet_ports") == ["outlet"]


def test_missing_port_metadata_rejected():
    with pytest.raises(BindingError):
        _ = SubsystemRuntimeDescriptor(
            descriptor_id="subsys2",
            process_id="tank_b",
            inlet_ports=(),
            outlet_ports=(),
            publication_map={"tank_b/level": 0.0},
            runtime_context=None,
        )


def test_namespace_registration_resolves_consistently_for_plant_scoped_lookup() -> None:
    registry = PointRegistry()
    published_point = Point(
        tag="internal_temperature",
        type="measured",
        unit=Unit("K"),
        description="subsystem publication",
    )
    published_point.data = DataValue(time=3.0, value=325.0, ok=True)

    registry.add(
        published_point,
        subsystem_namespace="reactor_train_a",
        published_tag="temperature",
    )

    assert "reactor_train_a/temperature" in registry
    getter = registry.make_converted_data_getter("reactor_train_a/temperature")
    published_value = getter()
    assert published_value.time == 3.0
    assert published_value.value == 325.0
    assert published_value.ok


def test_tag_collision_across_subsystems_raises_explicit_configuration_error() -> None:
    registry = PointRegistry()
    subsystem_a_level = Point(
        tag="level_sensor_a",
        type="measured",
        unit=Unit("m"),
        description="subsystem A level",
    )
    subsystem_b_level = Point(
        tag="level_sensor_b",
        type="measured",
        unit=Unit("m"),
        description="subsystem B level",
    )

    registry.add(subsystem_a_level, subsystem_namespace="tank_a", published_tag="level")

    with pytest.raises(
        MeasurableConfigurationError,
        match=(
            "Published measurement tag collision for 'level': already registered by subsystem "
            "'tank_a', cannot register for subsystem 'tank_b'."
        ),
    ):
        registry.add(subsystem_b_level, subsystem_namespace="tank_b", published_tag="level")


def test_publication_adapter_and_unit_conversion_resolves_process_state_source(
    thermal_process_model: ProcessModel,
) -> None:
    system = System(
        dt=1.0,
        process_model=thermal_process_model,
        sensors=[],
        calculations=[],
        control_elements=[],
        show_progress=False,
    )
    subsystem = Subsystem(
        descriptor=SubsystemRuntimeDescriptor(
            descriptor_id="thermal_subsystem",
            process_id="tank_a",
            inlet_ports=("inlet",),
            outlet_ports=("outlet",),
            publication_map={"temperature": 0.0},
            runtime_context={"publication_units": {"temperature": "mK"}},
        ),
        system=system,
    )

    published_measurements = subsystem.snapshot_published_measurements()
    assert abs(published_measurements["thermal_subsystem/temperature"] - 300000.0) <= 1e-6


def test_publication_adapter_and_unit_mismatch_raises_actionable_error(
    thermal_process_model: ProcessModel,
) -> None:
    system = System(
        dt=1.0,
        process_model=thermal_process_model,
        sensors=[],
        calculations=[],
        control_elements=[],
        show_progress=False,
    )

    with pytest.raises(
        MeasurableConfigurationError,
        match=(
            "Published measurement 'thermal_subsystem/temperature' cannot convert "
            "from source unit 'K' to target unit 'm'"
        ),
    ):
        _ = Subsystem(
            descriptor=SubsystemRuntimeDescriptor(
                descriptor_id="thermal_subsystem",
                process_id="tank_a",
                inlet_ports=("inlet",),
                outlet_ports=("outlet",),
                publication_map={"temperature": 0.0},
                runtime_context={"publication_units": {"temperature": "m"}},
            ),
            system=system,
        )

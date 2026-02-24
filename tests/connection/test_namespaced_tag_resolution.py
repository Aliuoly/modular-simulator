import pytest
from astropy.units import Unit

from modular_simulation.components.point import DataValue, Point, PointRegistry
from modular_simulation.validation.exceptions import MeasurableConfigurationError


def test_namespaced_resolution_no_collision_and_getters():
    registry = PointRegistry()
    p1 = Point(tag="internal_temperature", type="measured", unit=Unit("K"), description="sub1 temp")
    p1.data = DataValue(time=1.0, value=300.0, ok=True)

    p2 = Point(
        tag="internal_temperature_2", type="measured", unit=Unit("K"), description="sub2 temp"
    )
    p2.data = DataValue(time=1.0, value=320.0, ok=True)

    registry.add(p1, subsystem_namespace="sub1", published_tag="temperature")
    registry.add(p2, subsystem_namespace="sub2", published_tag="temperature2")

    assert "sub1/temperature" in registry
    assert "sub2/temperature2" in registry

    getter1 = registry.make_converted_data_getter("sub1/temperature")
    getter2 = registry.make_converted_data_getter("sub2/temperature2")

    val1 = getter1()
    val2 = getter2()
    assert val1.value == 300.0
    assert val2.value == 320.0


def test_invalid_namespace_registration_raises_measurableconfigurationerror():
    registry = PointRegistry()
    p = Point(tag="internal_temperature", type="measured", unit=Unit("K"), description="sub1 temp")
    with pytest.raises(MeasurableConfigurationError, match="must not contain '/'"):
        registry.add(p, subsystem_namespace="tank/sub", published_tag="temperature")


def test_invalid_published_tag_with_slash_raises_measurableconfigurationerror():
    registry = PointRegistry()
    p = Point(tag="internal_temperature", type="measured", unit=Unit("K"), description="sub1 temp")
    with pytest.raises(MeasurableConfigurationError, match="must not contain '/'"):
        registry.add(p, subsystem_namespace="tank", published_tag="temperature/room")


def test_same_namespace_same_published_tag_is_invalid_duplicate_key():
    registry = PointRegistry()
    p1 = Point(tag="temp1", type="measured", unit=Unit("K"), description="t1")
    p2 = Point(tag="temp2", type="measured", unit=Unit("K"), description="t2")

    p1.data = DataValue(time=1.0, value=290.0, ok=True)
    registry.add(p1, subsystem_namespace="subA", published_tag="temperature")
    p2.data = DataValue(time=2.0, value=300.0, ok=True)
    with pytest.raises(ValueError, match="already exists in registry"):
        registry.add(p2, subsystem_namespace="subA", published_tag="temperature")

    assert "subA/temperature" in registry
    getter = registry.make_converted_data_getter("subA/temperature")
    value = getter()
    assert isinstance(value, DataValue)
    assert value.value == 290.0


def test_publication_tag_collision_across_subsystems_raises():
    registry = PointRegistry()
    pA = Point(tag="level_sensor_a", type="measured", unit=Unit("m"), description="subA level")
    pA.data = DataValue(time=1.0, value=1.0, ok=True)
    registry.add(pA, subsystem_namespace="subsystem_a", published_tag="level")

    pB = Point(tag="level_sensor_b", type="measured", unit=Unit("m"), description="subB level")
    pB.data = DataValue(time=2.0, value=2.0, ok=True)
    with pytest.raises(
        MeasurableConfigurationError,
        match=(
            "Published measurement tag collision for 'level': already registered by subsystem 'subsystem_a', cannot register for subsystem 'subsystem_b'."
        ),
    ):
        registry.add(pB, subsystem_namespace="subsystem_b", published_tag="level")

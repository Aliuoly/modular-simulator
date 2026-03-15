# pyright: reportMissingImports=false, reportIncompatibleMethodOverride=false

import numpy as np
import pytest
from numpy.typing import NDArray
from typing import Annotated, Any, cast
from pydantic import Field, ValidationError

from modular_simulation.components import (
    ControlElement,
    ControllerMode,
    PIDController,
    SampledDelayedSensor,
    Trajectory,
)
from modular_simulation.framework.system import (
    CHECKPOINT_SCHEMA_VERSION,
    CHECKPOINT_VERSION_MISMATCH_ERROR_CODE,
    System,
    checkpoint_payload_checksum,
)
from modular_simulation.measurables.process_model import (
    ProcessModel,
    StateMetadata,
    StateType,
)
from modular_simulation.components.sensors import AbstractSensor
from modular_simulation.components.abstract_component import ComponentUpdateResult
from modular_simulation.unit_processes import Pump


class MinimalProcessModel(ProcessModel):
    x: Annotated[float, StateMetadata(StateType.DIFFERENTIAL, "1", "simple state")] = Field(1.0)

    @staticmethod
    def calculate_algebraic_values(
        y: NDArray[np.float64],
        u: NDArray[np.float64],
        k: NDArray[np.float64],
        y_map: dict[str, slice | int],
        u_map: dict[str, slice | int],
        k_map: dict[str, slice | int],
        algebraic_map: dict[str, slice | int],
        algebraic_size: int,
    ) -> NDArray[np.float64]:
        return np.zeros(algebraic_size, dtype=float)

    @staticmethod
    def differential_rhs(
        t: float,
        y: NDArray[np.float64],
        u: NDArray[np.float64],
        k: NDArray[np.float64],
        algebraic: NDArray[np.float64],
        y_map: dict[str, slice | int],
        u_map: dict[str, slice | int],
        k_map: dict[str, slice | int],
        algebraic_map: dict[str, slice | int],
    ) -> NDArray[np.float64]:
        return -y


class MinimalSensor(AbstractSensor):
    def _update(self, t: float) -> ComponentUpdateResult:
        measurement = self._measurement_getter()
        self._point.data = measurement
        return ComponentUpdateResult(data_value=measurement, exceptions=[])


@pytest.fixture()
def minimal_system() -> System:
    model = MinimalProcessModel(x=2.0)
    sensor = MinimalSensor(measurement_tag="x", alias_tag="x_sensor", unit="1")
    return System(
        dt=0.1,
        process_model=model,
        sensors=[sensor],
        calculations=[],
        control_elements=[],
        record_history=False,
        show_progress=False,
    )


def _controller_system() -> System:
    from tests.conftest import ThermalProcessModel

    model = ThermalProcessModel()
    sensor = SampledDelayedSensor(
        name="temperature_sensor",
        measurement_tag="temperature",
        alias_tag="temperature",
        unit="K",
        sampling_period=0.0,
        deadtime=0.0,
    )
    controller = PIDController(
        name="heater_pid",
        cv_tag="temperature",
        cv_range=(250.0, 350.0),
        reference_trajectory=Trajectory(y0=315.0, t0=0.0),
        Kp=5.0,
        Ti=5.0,
        Td=0.0,
    )
    heater = ControlElement(
        mv_tag="actuator/heat/heater_power",
        mv_trajectory=Trajectory(y0=0.0, t0=0.0),
        mv_range=(0.0, 20.0),
        controller=controller,
        mode=ControllerMode.AUTO,
    )
    return System(
        dt=1.0,
        process_model=model,
        sensors=[sensor],
        calculations=[],
        control_elements=[heater],
        record_history=False,
        show_progress=False,
    )


def test_system_save_load_round_trip(minimal_system: System) -> None:
    minimal_system.step(duration=0.3)
    payload = minimal_system.save()
    assert payload["schema_version"] == CHECKPOINT_SCHEMA_VERSION

    restored = System.load(payload)
    restored_model = cast(MinimalProcessModel, restored.process_model)
    original_model = cast(MinimalProcessModel, minimal_system.process_model)

    assert isinstance(restored_model, MinimalProcessModel)
    assert restored.dt == pytest.approx(minimal_system.dt)
    assert restored_model.x == pytest.approx(original_model.x)
    assert restored.time == pytest.approx(minimal_system.time)
    assert isinstance(restored.sensors[0], MinimalSensor)
    assert restored.point_registry[restored.sensors[0].alias_tag].tag == "x_sensor"

    starting_value = restored_model.x
    restored.step(duration=restored.dt)
    expected = starting_value * np.exp(-restored.dt)
    assert restored_model.x == pytest.approx(expected, rel=1e-3)

    update_result = restored.sensors[0].update(restored.time)
    assert update_result.ok


def test_system_load_rejects_schema_mismatch_payload_version(minimal_system: System) -> None:
    minimal_system.step(duration=0.3)
    payload = minimal_system.save()
    legacy_version = CHECKPOINT_SCHEMA_VERSION - 1
    assert legacy_version > 0
    payload["schema_version"] = legacy_version
    payload["integrity_checksum"] = checkpoint_payload_checksum(
        {key: value for key, value in payload.items() if key != "integrity_checksum"}
    )

    with pytest.raises(
        ValueError,
        match=rf"\[{CHECKPOINT_VERSION_MISMATCH_ERROR_CODE}\].*schema_version",
    ):
        System.load(payload)


def test_controller_constructor_sp_trajectory_alias_is_rejected() -> None:
    assert "sp_trajectory" not in PIDController.model_fields

    with pytest.raises(ValidationError, match="sp_trajectory"):
        _ = PIDController.model_validate(
            cast(
                dict[str, Any],
                {
                    "name": "heater_pid",
                    "cv_tag": "temperature",
                    "cv_range": (250.0, 350.0),
                    "sp_trajectory": Trajectory(y0=315.0, t0=0.0),
                    "Kp": 5.0,
                    "Ti": 5.0,
                    "Td": 0.0,
                },
            )
        )


def test_system_load_canonical_payload_with_controller_round_trip() -> None:
    system = _controller_system()
    system.step(duration=1.0)
    payload = system.save()

    restored = System.load(payload)

    assert len(restored.control_elements) == 1
    restored_controller = restored.control_elements[0].controller
    assert isinstance(restored_controller, PIDController)
    assert restored_controller.reference_trajectory is not None


def test_system_load_legacy_payload_rejected_for_controller_sp_trajectory() -> None:
    system = _controller_system()
    system.step(duration=1.0)
    payload = system.save()

    snapshot = payload["snapshot"]
    control_element_payload = snapshot["control_elements"][0]
    controller_payload = control_element_payload["config"]["controller"]
    controller_config = controller_payload["config"]
    controller_state = controller_payload["state"]

    assert "reference_trajectory" in controller_config
    assert "sp_trajectory" not in controller_config
    assert "reference" in controller_state
    assert "sp" not in controller_state
    assert "sp_trajectory" not in PIDController.model_fields

    payload_with_legacy_config = cast(dict[str, Any], payload.copy())
    payload_with_legacy_config["snapshot"] = cast(dict[str, Any], snapshot.copy())
    payload_with_legacy_config["snapshot"]["control_elements"] = list(snapshot["control_elements"])
    legacy_control_element = cast(dict[str, Any], control_element_payload.copy())
    legacy_controller_payload = cast(dict[str, Any], controller_payload.copy())
    legacy_controller_config = cast(dict[str, Any], controller_config.copy())
    legacy_controller_config["sp_trajectory"] = legacy_controller_config.pop("reference_trajectory")
    legacy_controller_payload["config"] = legacy_controller_config
    legacy_control_element["config"] = cast(
        dict[str, Any], control_element_payload["config"].copy()
    )
    legacy_control_element["config"]["controller"] = legacy_controller_payload
    payload_with_legacy_config["snapshot"]["control_elements"][0] = legacy_control_element
    payload_with_legacy_config["integrity_checksum"] = checkpoint_payload_checksum(
        {
            key: value
            for key, value in payload_with_legacy_config.items()
            if key != "integrity_checksum"
        }
    )

    with pytest.raises(ValidationError, match="sp_trajectory"):
        System.load(payload_with_legacy_config)


def test_system_load_mixed_payload_rejected_for_control_element_legacy_key() -> None:
    system = _controller_system()
    system.step(duration=1.0)
    payload = system.save()

    snapshot = payload["snapshot"]
    control_element_payload = snapshot["control_elements"][0]
    control_element_config = cast(dict[str, Any], control_element_payload["config"])

    assert "controller_sp_point_dict" not in ControlElement.model_fields
    assert "controller_sp_point_dict" not in control_element_config

    payload_with_mixed_config = cast(dict[str, Any], payload.copy())
    payload_with_mixed_config["snapshot"] = cast(dict[str, Any], snapshot.copy())
    payload_with_mixed_config["snapshot"]["control_elements"] = list(snapshot["control_elements"])
    mixed_control_element = cast(dict[str, Any], control_element_payload.copy())
    mixed_control_element_config = cast(dict[str, Any], control_element_config.copy())
    mixed_control_element_config["controller_sp_point_dict"] = {}
    mixed_control_element["config"] = mixed_control_element_config
    payload_with_mixed_config["snapshot"]["control_elements"][0] = mixed_control_element
    payload_with_mixed_config["integrity_checksum"] = checkpoint_payload_checksum(
        {
            key: value
            for key, value in payload_with_mixed_config.items()
            if key != "integrity_checksum"
        }
    )

    with pytest.raises(ValidationError, match="controller_sp_point_dict"):
        System.load(payload_with_mixed_config)


def test_system_load_legacy_payload_rejected_for_controller_runtime_sp() -> None:
    system = _controller_system()
    system.step(duration=1.0)
    payload = system.save()

    snapshot = payload["snapshot"]
    control_element_payload = snapshot["control_elements"][0]
    controller_payload = control_element_payload["config"]["controller"]
    controller_state = cast(dict[str, Any], controller_payload["state"])

    assert "reference" in controller_state
    assert "sp" not in controller_state

    payload_with_legacy_state = cast(dict[str, Any], payload.copy())
    payload_with_legacy_state["snapshot"] = cast(dict[str, Any], snapshot.copy())
    payload_with_legacy_state["snapshot"]["control_elements"] = list(snapshot["control_elements"])
    legacy_state_control_element = cast(dict[str, Any], control_element_payload.copy())
    legacy_state_controller_payload = cast(dict[str, Any], controller_payload.copy())
    legacy_controller_state = cast(dict[str, Any], controller_state.copy())
    legacy_controller_state["sp"] = legacy_controller_state.pop("reference")
    legacy_state_controller_payload["state"] = legacy_controller_state
    legacy_state_control_element["config"] = cast(
        dict[str, Any], control_element_payload["config"].copy()
    )
    legacy_state_control_element["config"]["controller"] = legacy_state_controller_payload
    payload_with_legacy_state["snapshot"]["control_elements"][0] = legacy_state_control_element
    payload_with_legacy_state["integrity_checksum"] = checkpoint_payload_checksum(
        {
            key: value
            for key, value in payload_with_legacy_state.items()
            if key != "integrity_checksum"
        }
    )

    with pytest.raises(ValueError, match="field 'sp' is not supported; use 'reference'"):
        System.load(payload_with_legacy_state)


def test_process_model_load_rejects_legacy_pump_pressure_rise_alias() -> None:
    pump = Pump(n_species=2, pump_speed=120000.0)
    payload = pump.save()

    pump_states = cast(dict[str, object], payload["states"])
    assert "pump_speed" in pump_states
    assert "pressure_rise" not in pump_states
    pump_states["pressure_rise"] = pump_states.pop("pump_speed")
    pump_states["inlet_composition"] = np.asarray(
        pump_states["inlet_composition"], dtype=np.float64
    )
    pump_states["outlet_composition"] = np.asarray(
        pump_states["outlet_composition"],
        dtype=np.float64,
    )

    with pytest.raises(ValidationError, match="pressure_rise"):
        ProcessModel.load(payload)

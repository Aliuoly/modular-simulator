import numpy as np
import pytest
from numpy.typing import NDArray
from typing import Annotated, Any, cast, override
from pydantic import Field

from modular_simulation.components import (
    ControlElement,
    ControllerMode,
    PIDController,
    SampledDelayedSensor,
    Trajectory,
)
from modular_simulation.framework.system import System, checkpoint_payload_checksum
from modular_simulation.measurables.process_model import (
    ProcessModel,
    StateMetadata,
    StateType,
)
from modular_simulation.components.sensors import AbstractSensor as SensorBase
from modular_simulation.components.abstract_component import ComponentUpdateResult
from modular_simulation.unit_processes import Pump


class MinimalProcessModel(ProcessModel):
    x: Annotated[float, StateMetadata(StateType.DIFFERENTIAL, "1", "simple state")] = Field(1.0)

    @override
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

    @override
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


class MinimalSensor(SensorBase):
    @override
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
        mv_tag="heater_power",
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

    restored = System.load(payload)
    restored_model = cast(MinimalProcessModel, restored.process_model)
    original_model = cast(MinimalProcessModel, minimal_system.process_model)

    assert isinstance(restored_model, MinimalProcessModel)
    assert restored.dt == pytest.approx(minimal_system.dt)
    assert restored_model.x == pytest.approx(original_model.x)
    assert restored.time == pytest.approx(minimal_system.time)
    assert isinstance(restored.sensors[0], MinimalSensor)
    assert restored.tag_store[restored.sensors[0].alias_tag].tag == "x_sensor"

    starting_value = restored_model.x
    restored.step(duration=restored.dt)
    expected = starting_value * np.exp(-restored.dt)
    assert restored_model.x == pytest.approx(expected, rel=1e-3)

    update_result = restored.sensors[0].update(restored.time)
    assert update_result.ok


def test_controller_constructor_sp_trajectory_alias_warns() -> None:
    with pytest.warns(
        DeprecationWarning,
        match="sp_trajectory is deprecated; use reference_trajectory",
    ):
        controller = cast(
            PIDController,
            PIDController.model_validate(
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
            ),
        )

    assert controller.reference_trajectory is not None
    assert controller.reference_trajectory(0.0) == pytest.approx(315.0)


def test_system_load_accepts_legacy_controller_aliases_with_deterministic_warnings() -> None:
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

    controller_config["sp_trajectory"] = controller_config.pop("reference_trajectory")
    controller_state["sp"] = controller_state.pop("reference")
    payload["integrity_checksum"] = checkpoint_payload_checksum(
        {key: value for key, value in payload.items() if key != "integrity_checksum"}
    )

    with pytest.warns(DeprecationWarning) as recorded:
        restored = System.load(payload)

    assert [str(item.message) for item in recorded] == [
        "sp_trajectory is deprecated; use reference_trajectory",
        "controller runtime state field 'sp' is deprecated; use 'reference'",
    ]
    restored_controller = restored.control_elements[0].controller
    assert restored_controller is not None
    assert restored_controller.reference_trajectory is not None
    assert restored_controller.reference_trajectory(restored.time) == pytest.approx(315.0)


def test_process_model_load_accepts_legacy_pump_pressure_rise_alias_with_warning() -> None:
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

    with pytest.warns(DeprecationWarning, match="pressure_rise is deprecated; use pump_speed"):
        restored = ProcessModel.load(payload)

    restored_pump = cast(Pump, restored)
    assert restored_pump.pump_speed == pytest.approx(120000.0)

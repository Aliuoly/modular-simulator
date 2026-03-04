from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, override
import numpy as np
from astropy.units import Unit
from pydantic import ConfigDict, Field, PrivateAttr
from modular_simulation.validation.exceptions import (
    SensorConfigurationError,
)
from modular_simulation.components.point import Point, DataValue
from modular_simulation.components.abstract_component import (
    AbstractComponent,
    ComponentUpdateResult,
)
from modular_simulation.utils.typing import Seconds
from modular_simulation.components.calculations.point_metadata import PointMetadata, TagType

if TYPE_CHECKING:
    from modular_simulation.framework.system import System


@dataclass(frozen=True)
class SensorRuntimeBindingState:
    measurement_tag: str
    alias_tag: str
    point_raw_tag: str
    point_data: DataValue
    point_history: tuple[DataValue, ...]
    measurement_getter: Any


class AbstractSensor(AbstractComponent):
    """Abstract base class for all sensors in the modular simulation framework.
    All sensors are assumed to have a single configuration field named "measurement_tag",
    representing the tag name of the measured process state.
    """

    measurement_tag: str = Field(..., description="Tag name of the measured process state.")
    alias_tag: str = Field(default="", description="Alias tag name for the sensor output.")
    unit: str = Field(default="", description="The unit of the sensor measurement.")
    description: str = Field(default="", description="Description of the sensor.")

    # Noise and error modeling
    coefficient_of_variance: float = Field(
        default=0.0, ge=0.0, description="Coefficient of variance for measurement noise."
    )
    faulty_probability: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Probability of the sensor being faulty."
    )
    faulty_aware: bool = Field(
        default=True, description="Whether the control system is aware of sensor faults."
    )
    instrument_range: tuple[float, float] = Field(
        default=(-float("inf"), float("inf")), description="Operating range of the sensor."
    )
    random_seed: int | None = Field(default=None, description="Random seed for reproducibility.")

    _point: Point = PrivateAttr()
    _measurement_getter: Any = PrivateAttr()
    _generator: np.random.Generator = PrivateAttr()
    _is_faulty: bool = PrivateAttr(default=False)

    # Timing logic
    _t: Seconds = PrivateAttr(default=-1.0)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @override
    def model_post_init(self, context: Any) -> None:
        if self.alias_tag == "":
            self.alias_tag = self.measurement_tag

        self._generator = np.random.default_rng(self.random_seed)
        resolved_unit = Unit(self.unit)

        # Initialize Point
        self._point = Point(
            tag=self.alias_tag,
            unit=resolved_unit,
            type="measured",
            description=self.description,
            _raw_tag=self.measurement_tag,
        )

    # -------- AbstractComponent Interface --------

    @override
    def _install(self, system: System) -> list[Exception]:
        """Bind the sensor to the system's point registry."""
        exceptions: list[Exception] = []
        try:
            self._measurement_getter = self._resolve_measurement_getter_for_tag(
                system=system,
                measurement_tag=self.measurement_tag,
            )
        except KeyError as e:
            exceptions.append(SensorConfigurationError(str(e)))
        except AttributeError as e:
            # Conversion error or getattr error
            exceptions.append(SensorConfigurationError(f"Failed to access process state: {e}"))
        except Exception as e:  # Catch unit errors etc
            exceptions.append(SensorConfigurationError(f"Configuration error: {e}"))

        if not exceptions:
            # Perform initial measurement
            try:
                # We can't call update() here because it checks _initialized which is not set yet by the base class
                # So we manually call _update
                result = self._update(t=system.time)
                if result.exceptions:
                    exceptions.extend(result.exceptions)
                elif np.isnan(self.point.data.value):
                    exceptions.append(
                        SensorConfigurationError(
                            f"'{self.name}' sensor resulted in nan during commissioning."
                        )
                    )
            except Exception as e:
                exceptions.append(e)

        return exceptions

    def _resolve_measurement_getter_for_tag(self, *, system: System, measurement_tag: str) -> Any:
        normalized_measurement_tag = measurement_tag.strip()
        if not normalized_measurement_tag:
            raise SensorConfigurationError("measurement_tag must be a non-empty string")

        if normalized_measurement_tag in system.process_model.state_metadata_dict:
            metadata = system.process_model.state_metadata_dict[normalized_measurement_tag]
            source_unit = metadata.unit
            target_unit = Unit(self.unit)
            converter = source_unit.get_converter(target_unit)

            def getter() -> DataValue:
                val = getattr(system.process_model, normalized_measurement_tag)
                return DataValue(value=converter(val), time=system.time, ok=True)

            return getter

        return system.point_registry.make_converted_data_getter(
            normalized_measurement_tag,
            Unit(self.unit),
        )

    def capture_runtime_binding_state(self) -> SensorRuntimeBindingState:
        point_data = self._point.data
        point_history = tuple(
            DataValue(time=item.time, value=item.value, ok=item.ok) for item in self._point.history
        )
        return SensorRuntimeBindingState(
            measurement_tag=self.measurement_tag,
            alias_tag=self.alias_tag,
            point_raw_tag=self._point.raw_tag,
            point_data=DataValue(time=point_data.time, value=point_data.value, ok=point_data.ok),
            point_history=point_history,
            measurement_getter=self._measurement_getter,
        )

    def restore_runtime_binding_state(self, state: SensorRuntimeBindingState) -> None:
        self.measurement_tag = state.measurement_tag
        self.alias_tag = state.alias_tag
        self._measurement_getter = state.measurement_getter
        self._point._raw_tag = state.point_raw_tag
        self._point._data = DataValue(
            time=state.point_data.time,
            value=state.point_data.value,
            ok=state.point_data.ok,
        )
        self._point._history = [
            DataValue(time=item.time, value=item.value, ok=item.ok) for item in state.point_history
        ]

    def bind_runtime_signal(self, *, system: System, signal_key: str) -> None:
        normalized_signal_key = signal_key.strip()
        if not normalized_signal_key:
            raise SensorConfigurationError("signal_key must be a non-empty string")

        runtime_state = self.capture_runtime_binding_state()
        try:
            measurement_getter = self._resolve_measurement_getter_for_tag(
                system=system,
                measurement_tag=normalized_signal_key,
            )
            self.measurement_tag = normalized_signal_key
            self._measurement_getter = measurement_getter
            self._point._raw_tag = normalized_signal_key
            update_result = self._update(t=system.time)
            if update_result.exceptions:
                raise update_result.exceptions[0]
            if np.isnan(self.point.data.value):
                raise SensorConfigurationError(
                    f"'{self.name}' sensor resulted in nan during bind operation."
                )
        except Exception:
            self.restore_runtime_binding_state(runtime_state)
            raise

    def unbind_runtime_signal(self, *, system: System) -> None:
        self.measurement_tag = ""

        def getter() -> DataValue:
            return DataValue(value=np.nan, time=system.time, ok=False)

        self._measurement_getter = getter
        self._point._raw_tag = ""
        self._point.data = getter()

    @override
    def _should_update(self, t: Seconds) -> bool:
        # Default behavior: update every step if not overridden
        return True

    @override
    def _update(self, t: Seconds) -> ComponentUpdateResult:
        """Execute the measurement logic."""
        self._t = t
        raw_data = self._measurement_getter()

        # Allow subclass to process the measurement (add noise, delay, etc.)
        measurement = raw_data

        # Layer on fault logic
        if self.faulty_probability > 0:
            self._is_faulty = self._generator.random() < self.faulty_probability

        if self._is_faulty:
            measurement.ok = False

        self._point.data = measurement
        return ComponentUpdateResult(data_value=measurement, exceptions=[])

    @override
    def _get_configuration_dict(self) -> dict[str, Any]:
        return self.model_dump()

    @override
    def _get_runtime_state_dict(self) -> dict[str, Any]:
        return {"t": self._t, "is_faulty": self._is_faulty}

    @classmethod
    @override
    def _load_configuration(cls, data: dict[str, Any]) -> "AbstractSensor":
        return cls(**data)

    @override
    def _load_runtime_state(self, state: dict[str, Any]) -> None:
        self._t = state.get("t", -1.0)
        self._is_faulty = state.get("is_faulty", False)

    # -------- Properties --------

    @property
    def point(self) -> Point:
        return self._point

    @property
    def point_metadata_dict(self) -> dict[str, PointMetadata]:
        return {
            self.measurement_tag: PointMetadata(
                unit=self.unit,
                type=TagType.INPUT,
                description=self.description,
            ),
            self.alias_tag: PointMetadata(
                unit=self.unit,
                type=TagType.OUTPUT,
                description=self.description,
            ),
        }

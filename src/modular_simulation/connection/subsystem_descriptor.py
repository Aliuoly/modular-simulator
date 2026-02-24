from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from astropy.units import Unit, UnitBase, UnitsError

from modular_simulation.components.calculations.abstract_calculation import AbstractCalculation
from modular_simulation.components.control_system.control_element import ControlElement
from modular_simulation.components.sensors.abstract_sensor import AbstractSensor
from modular_simulation.utils.typing import TimeQuantity
from modular_simulation.utils.wrappers import second
from modular_simulation.validation.exceptions import (
    ControllerConfigurationError,
    MeasurableConfigurationError,
    SensorConfigurationError,
)
from .process_binding import ProcessBinding, BindingError

if TYPE_CHECKING:
    from modular_simulation.framework.system import System


@dataclass(frozen=True)
class SubsystemRuntimeDescriptor:
    """Lightweight descriptor binding a subsystem to a process runtime context.

        This object captures the minimal information required for a subsystem
        installer to wire up a local process model/runtime and publish a map of
        measurements that can be consumed by plant-scoped calculations.

        Fields:
    - descriptor_id: unique identifier for this descriptor instance.
    - process_id: target process identifier within the connection network.
    - inlet_ports: ordered list of inlet port names declared by the descriptor.
    - outlet_ports: ordered list of outlet port names declared by the descriptor.
    - publication_map: a map of publication tags to their initial/constant values
      or placeholders for the installer to populate with live data.
    - runtime_context: optional, opaque runtime context for local interpretation by
      installers or validators.
    """

    descriptor_id: str
    process_id: str
    inlet_ports: tuple[str, ...]
    outlet_ports: tuple[str, ...]
    publication_map: Mapping[str, float]
    runtime_context: Mapping[str, object] | None = None

    def __post_init__(self) -> None:
        descriptor_id = cast(object, self.descriptor_id)
        process_id = cast(object, self.process_id)
        publication_map = cast(object, self.publication_map)
        runtime_context = cast(object, self.runtime_context)

        # Basic id validation
        if not isinstance(descriptor_id, str) or not descriptor_id.strip():
            raise BindingError("descriptor_id must be a non-empty string")
        if not isinstance(process_id, str) or not process_id.strip():
            raise BindingError("process_id must be a non-empty string")

        # Ports must be provided and non-empty
        if len(self.inlet_ports) == 0:
            raise BindingError("inlet_ports must be a non-empty sequence of port names")
        if len(self.outlet_ports) == 0:
            raise BindingError("outlet_ports must be a non-empty sequence of port names")
        for p in self.inlet_ports:
            if not isinstance(cast(object, p), str) or not p.strip():
                raise BindingError("inlet_ports contains invalid (empty) port name")
        for p in self.outlet_ports:
            if not isinstance(cast(object, p), str) or not p.strip():
                raise BindingError("outlet_ports contains invalid (empty) port name")

        # Publication map validation
        if not isinstance(publication_map, Mapping):
            raise BindingError("publication_map must be a mapping of string keys to numeric values")
        for key in self.publication_map:
            if not isinstance(cast(object, key), str) or not key.strip():
                raise BindingError("publication_map keys must be non-empty strings")

        # runtime_context may be None
        if runtime_context is not None and not isinstance(runtime_context, Mapping):
            raise BindingError("runtime_context must be a mapping when provided")

    def to_binding(self) -> ProcessBinding:
        """Convert descriptor ports to a ProcessBinding compatible object."""
        return ProcessBinding(
            inlet_ports=list(self.inlet_ports), outlet_ports=list(self.outlet_ports)
        )


class Subsystem:
    def __init__(self, *, descriptor: SubsystemRuntimeDescriptor, system: System) -> None:
        self._descriptor: SubsystemRuntimeDescriptor = descriptor
        self._system: System = system
        self._sensors: list[AbstractSensor] = list(system.sensors)
        self._calculations: list[AbstractCalculation] = list(system.calculations)
        self._control_elements: list[ControlElement] = list(system.control_elements)
        self._published_process_view_tags: set[str] = set()
        self._publication_getter_by_tag: dict[str, Callable[[], float]] = {}
        self._refresh_published_process_view()
        self._refresh_publication_adapter()

    @property
    def descriptor(self) -> SubsystemRuntimeDescriptor:
        return self._descriptor

    @property
    def system(self) -> System:
        return self._system

    @property
    def published_process_view_tags(self) -> tuple[str, ...]:
        return tuple(sorted(self._published_process_view_tags))

    def snapshot_published_measurements(self) -> Mapping[str, float]:
        return {tag: getter() for tag, getter in self._publication_getter_by_tag.items()}

    def add_sensor(self, sensor: AbstractSensor) -> AbstractSensor:
        if sensor.measurement_tag not in self._published_process_view_tags:
            raise SensorConfigurationError(
                f"Subsystem '{self._descriptor.descriptor_id}' cannot resolve local measurement tag "
                + f"'{sensor.measurement_tag}'. Local published process view tags are: "
                + ", ".join(self.published_process_view_tags)
            )

        self._install_component(sensor)
        self._sensors.append(sensor)
        self._refresh_published_process_view()
        self._refresh_publication_adapter()
        return sensor

    def add_control_element(self, control_element: ControlElement) -> ControlElement:
        controller = control_element.controller
        if controller is not None and controller.cv_tag not in self._published_process_view_tags:
            raise ControllerConfigurationError(
                f"Subsystem '{self._descriptor.descriptor_id}' cannot resolve local control variable tag "
                + f"'{controller.cv_tag}'. Local published process view tags are: "
                + ", ".join(self.published_process_view_tags)
            )

        if control_element.mv_tag not in self._published_process_view_tags:
            raise ControllerConfigurationError(
                f"Subsystem '{self._descriptor.descriptor_id}' cannot resolve local manipulated variable tag "
                + f"'{control_element.mv_tag}'. Local published process view tags are: "
                + ", ".join(self.published_process_view_tags)
            )

        self._install_component(control_element)
        self._control_elements.append(control_element)
        self._refresh_published_process_view()
        self._refresh_publication_adapter()
        return control_element

    def run_sensor_phase(self) -> None:
        t = self._system.time
        for sensor in self._sensors:
            if sensor.should_update(t):
                _ = sensor.update(t)

    def run_calculation_phase(self) -> None:
        t = self._system.time
        for calculation in self._calculations:
            if calculation.should_update(t):
                _ = calculation.update(t)

    def run_controller_phase(self) -> None:
        t = self._system.time
        for control_element in self._control_elements:
            if control_element.should_update(t):
                _ = control_element.update(t)

    def run_process_phase(self, duration: float | TimeQuantity | None = None) -> None:
        duration_s = second(duration) if duration is not None else self._system.dt
        self._system.process_model.step(duration_s)

    def step(self, duration: float | TimeQuantity | None = None) -> None:
        self.run_sensor_phase()
        self.run_calculation_phase()
        self.run_controller_phase()
        self.run_process_phase(duration)

    def _install_component(
        self,
        component: AbstractSensor | AbstractCalculation | ControlElement,
    ) -> None:
        error, successful = self._system.add_component(component)
        if successful:
            return
        if error is None:
            raise RuntimeError("subsystem install failed without explicit error")
        raise error

    def _refresh_published_process_view(self) -> None:
        published_tags = set(self._descriptor.publication_map.keys())
        published_tags.update(self._system.process_model.state_list)
        for tag, point in self._system.point_registry.items():
            if point.type == "raw":
                continue
            published_tags.add(tag)
        self._published_process_view_tags = published_tags

    def _refresh_publication_adapter(self) -> None:
        publication_unit_overrides = self._resolve_publication_unit_overrides()
        publication_getter_by_tag: dict[str, Callable[[], float]] = {}

        for published_tag, default_value in self._descriptor.publication_map.items():
            normalized_tag = published_tag.strip()
            if not normalized_tag:
                raise BindingError("publication_map keys must be non-empty strings")

            if "/" in normalized_tag:
                namespace, output_tag = normalized_tag.split("/", 1)
            else:
                namespace = self._descriptor.descriptor_id
                output_tag = normalized_tag

            namespace = namespace.strip()
            output_tag = output_tag.strip()
            if not namespace or not output_tag:
                raise BindingError(
                    "publication_map keys must resolve to '<subsystem>/<published_tag>'"
                )
            if "/" in namespace or "/" in output_tag:
                raise MeasurableConfigurationError(
                    f"Published measurement tag '{normalized_tag}' must follow '<subsystem>/<published_tag>'."
                )

            registration_tag = f"{namespace}/{output_tag}"
            target_unit = publication_unit_overrides.get(normalized_tag)
            if target_unit is None:
                target_unit = publication_unit_overrides.get(registration_tag)

            publication_getter_by_tag[registration_tag] = self._make_publication_value_getter(
                source_tag=output_tag,
                published_tag=registration_tag,
                default_value=default_value,
                target_unit=target_unit,
            )

        self._publication_getter_by_tag = publication_getter_by_tag

    def _make_publication_value_getter(
        self,
        *,
        source_tag: str,
        published_tag: str,
        default_value: float,
        target_unit: UnitBase | None,
    ) -> Callable[[], float]:
        source_point = self._system.point_registry.get(source_tag)
        if source_point is not None:
            source_unit = source_point.unit
            resolved_target_unit = source_unit if target_unit is None else target_unit
            try:
                source_getter = self._system.point_registry.make_converted_data_getter(
                    source_tag,
                    target_unit=resolved_target_unit,
                )
            except UnitsError as exc:
                raise MeasurableConfigurationError(
                    f"Published measurement '{published_tag}' cannot convert from source unit "
                    + f"'{source_unit}' to target unit '{resolved_target_unit}'."
                ) from exc

            def publication_getter() -> float:
                return float(source_getter().value)

            return publication_getter

        state_metadata = self._system.process_model.state_metadata_dict.get(source_tag)
        if state_metadata is not None:
            source_unit = state_metadata.unit
            resolved_target_unit = source_unit if target_unit is None else target_unit
            try:
                source_getter = self._system.process_model.make_converted_getter(
                    source_tag,
                    target_unit=resolved_target_unit,
                )
            except UnitsError as exc:
                raise MeasurableConfigurationError(
                    f"Published measurement '{published_tag}' cannot convert from source unit "
                    + f"'{source_unit}' to target unit '{resolved_target_unit}'."
                ) from exc

            def publication_getter() -> float:
                return float(source_getter())

            return publication_getter

        def fallback_getter() -> float:
            return float(default_value)

        return fallback_getter

    def _resolve_publication_unit_overrides(self) -> dict[str, UnitBase]:
        runtime_context = self._descriptor.runtime_context
        if runtime_context is None:
            return {}

        raw_publication_units = runtime_context.get("publication_units")
        if raw_publication_units is None:
            return {}
        if not isinstance(raw_publication_units, Mapping):
            raise BindingError("runtime_context.publication_units must be a mapping when provided")

        resolved_units: dict[str, UnitBase] = {}
        for raw_tag, raw_unit_spec in cast(Mapping[object, object], raw_publication_units).items():
            if not isinstance(raw_tag, str) or not raw_tag.strip():
                raise BindingError(
                    "runtime_context.publication_units keys must be non-empty strings"
                )
            if not isinstance(raw_unit_spec, (str, UnitBase)):
                raise BindingError(
                    "runtime_context.publication_units values must be astropy units or strings"
                )
            resolved_units[raw_tag.strip()] = (
                raw_unit_spec if isinstance(raw_unit_spec, UnitBase) else Unit(raw_unit_spec)
            )
        return resolved_units


__all__ = ["Subsystem", "SubsystemRuntimeDescriptor"]

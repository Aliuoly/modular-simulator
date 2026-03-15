from __future__ import annotations

# pyright: reportImportCycles=false, reportMissingImports=false

import hashlib
import json
import re
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version as package_version
from importlib import import_module
from pydantic import BaseModel, Field, PrivateAttr, ConfigDict
from typing import Any, Callable, override, TYPE_CHECKING, cast
from collections.abc import Mapping, Sequence
from functools import cached_property
from math import isfinite
import numpy as np
from astropy.units import UnitBase
from modular_simulation.components.control_system.control_element import ControlElement
from modular_simulation.components.control_system.mode_manager import ControlElementModeManager
from modular_simulation.utils.typing import Seconds, StateValue, TimeQuantity
from modular_simulation.components.point import PointRegistry, Point, DataValue

from modular_simulation.utils.wrappers import second
from modular_simulation.measurables.process_model import ProcessModel
from modular_simulation.components.sensors.abstract_sensor import (
    AbstractSensor,
    SensorRuntimeBindingState,
)
from modular_simulation.components.calculations.abstract_calculation import AbstractCalculation
from modular_simulation.components.abstract_component import ComponentDataDict
from modular_simulation.components.control_system.controller_mode import ControllerMode
from modular_simulation.components.control_system.abstract_controller import AbstractController
from modular_simulation.connection.domain_contracts import SensorBinding
from modular_simulation.validation.exceptions import (
    SensorConfigurationError,
    ControllerConfigurationError,
)
import logging
from tqdm import tqdm

if TYPE_CHECKING:
    from modular_simulation.components.control_system.trajectory import Trajectory

logger = logging.getLogger(__name__)


CHECKPOINT_SCHEMA_MARKER = "modular_simulation.system.checkpoint"
CHECKPOINT_SCHEMA_VERSION = 2
CHECKPOINT_PACKAGE_NAME = "modular-simulation"
CHECKPOINT_VERSION_MISMATCH_ERROR_CODE = "CHECKPOINT_VERSION_MISMATCH"
CHECKPOINT_INTEGRITY_MISMATCH_ERROR_CODE = "CHECKPOINT_INTEGRITY_MISMATCH"

_CANONICAL_RUNTIME_ACTUATOR_TAG_PATTERN = re.compile(
    r"^actuator/(valve|pump|heat)/[A-Za-z0-9][A-Za-z0-9._-]*$"
)

_PLAIN_VALVE_PUMP_CONTROL_TAG_RULES: dict[tuple[str, str], str] = {
    ("Pump", "pump_speed"): "actuator/pump/<id>",
    ("Valve", "open_fraction"): "actuator/valve/<id>",
}


@dataclass(frozen=True)
class RuntimeSensorBinding:
    sensor_id: str
    signal_key: str
    process_id: str | None
    port_id: str | None
    line_id: str | None
    metadata: Mapping[str, object]


@dataclass(frozen=True)
class _SensorMutationSnapshot:
    sensors: tuple[AbstractSensor, ...]
    point_registry_points: dict[str, Point]
    measured_points_cache: dict[str, Point] | None
    calculated_points_cache: dict[str, Point] | None
    reference_points_cache: dict[str, Point] | None
    sensor_bindings_by_id: dict[str, RuntimeSensorBinding]
    sensor_state_by_id: dict[str, SensorRuntimeBindingState]


@dataclass(frozen=True)
class RuntimeControllerBinding:
    controller_id: str
    signal_key: str
    actuator_tag: str
    mode: str
    metadata: Mapping[str, object]


@dataclass(frozen=True)
class _RuntimeControllerDefinition:
    controller_id: str
    controller_type: str
    controller_module: str
    controller_config: dict[str, object]
    signal_key: str | None
    actuator_tag: str | None
    mode: str
    metadata: Mapping[str, object]
    active: bool


@dataclass(frozen=True)
class _ControllerMutationSnapshot:
    controller_definitions: dict[str, _RuntimeControllerDefinition]
    controller_bindings: dict[str, RuntimeControllerBinding]
    point_registry_points: dict[str, Point]
    measured_points_cache: dict[str, Point] | None
    calculated_points_cache: dict[str, Point] | None
    reference_points_cache: dict[str, Point] | None


class System(BaseModel):
    """ """

    dt: Seconds
    """
    How often the system's sensors, calculations, and controllers update. "
    The solver takes adaptive 'internal steps' regardless of this value to update the system's states. "
    """
    process_model: ProcessModel
    """
    A container for all constants, state, control, and algebraic variables that can be measured or recorded. "
    """
    sensors: Sequence[AbstractSensor]
    calculations: Sequence[AbstractCalculation]
    control_elements: Sequence[ControlElement]
    solver_options: dict[str, Any] = Field(  # pyright: ignore[reportExplicitAny]
        default_factory=lambda: {"method": "LSODA"},
    )
    record_history: bool = Field(
        default=False,
        description=(
            "Whether or not to historize the underlying measurable_quantities of the system. "
            "The usable_quantities, which are measured or calculation, are always historized regardless. "
        ),
    )
    show_progress: bool = Field(
        default=True,
        description=(
            "Whether or not to show simulation progress when simulating multiple steps at once."
        ),
    )

    _point_registry: PointRegistry = PrivateAttr(default_factory=PointRegistry)
    _history_updaters: list[Callable[[Seconds], None]] = PrivateAttr(default_factory=list)
    _sensor_bindings_by_id: dict[str, RuntimeSensorBinding] = PrivateAttr(default_factory=dict)
    _runtime_controller_definitions: dict[str, _RuntimeControllerDefinition] = PrivateAttr(
        default_factory=dict
    )
    _controller_bindings_by_id: dict[str, RuntimeControllerBinding] = PrivateAttr(
        default_factory=dict
    )
    _pending_heat_actuator_rates: dict[str, float] = PrivateAttr(default_factory=dict)
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")  # pyright: ignore[reportUnannotatedClassAttribute]

    @override
    def model_post_init(self, context: Any) -> None:  # pyright: ignore[reportExplicitAny, reportAny]
        self._validate()

        self.process_model.attach_system(self)

        # Register all process variables in the tag store BEFORE components
        # so that components can find them during their initialization.
        for raw_state_name in self.process_model.state_list:
            metadata = self.process_model.state_metadata_dict[raw_state_name]
            initial_value = getattr(self.process_model, raw_state_name)
            tag_info = Point(
                tag=self.raw_point_tag_for_state(raw_state_name) or raw_state_name,
                unit=metadata.unit,
                type="raw",
                description=metadata.description,
                _raw_tag=raw_state_name,
            )
            # Initialize data immediately so components reading it see valid values
            # cast to StateValue to handle potential type discrepancies or numpy scalars
            val = cast(StateValue, initial_value)
            tag_info.data = DataValue(value=val, time=self.process_model.t, ok=True)
            self._point_registry.add(tag_info)

        # importantly, the order must be
        # 1. sensors, 2. calculations, 3. controllers
        # as calculations depend on sensors, and controllers depend on
        # both sensors and calculations.
        for sensor in self.sensors:
            error, successful = self.add_component(sensor)
            if not successful and error is not None:
                raise error

        # calculations may be defined out of order
        # such that calculation 1 depends on result of calculation 2
        # in such case, the wiring of calculation 1 will FAIL in the first pass.
        # We will try to iteratively resolve calculations for up to NUM_CALCULATION passes.

        attempts = 0
        max_attempts = len(self.calculations)
        resolution_done = False if max_attempts > 0 else True
        pending_calculation_indeces = list(range(len(self.calculations)))
        errors: list[Exception] = []
        while not resolution_done and attempts < max_attempts:
            attempts += 1
            errors.clear()
            for calculation_index in pending_calculation_indeces:
                error, successful = self.add_component(self.calculations[calculation_index])
                if error is not None:
                    errors.append(error)
                if successful:
                    pending_calculation_indeces.remove(calculation_index)
                if successful and error is not None:
                    pass
                if not successful and error is None:
                    pass
            if len(pending_calculation_indeces) == 0:
                resolution_done = True
        if len(errors) > 0:
            raise ExceptionGroup(
                f"{len(pending_calculation_indeces)} out of {len(self.calculations)} calculation(s) could not be resolved: ",
                errors,
            )
        for control_element in self.control_elements:
            error, successful = self.add_component(control_element)
            if not successful and error is not None:
                raise error

        if True:  # Always create updaters to keep TagStore in sync

            def make_history_updater(tag_info: Point) -> Callable[[Seconds], None]:
                process_model = self.process_model
                tag = tag_info.raw_tag

                def updater(time: Seconds):
                    value = cast(StateValue, getattr(process_model, tag))
                    tag_info.data = DataValue(
                        value=value, time=time, ok=True
                    )  # the setter of .data updates Point.history as well

                return updater

            for raw_state_name in self.process_model.state_list:
                # Need to find the point we already added
                metadata = self.process_model.state_metadata_dict[raw_state_name]
                tag = self.raw_point_tag_for_state(raw_state_name) or raw_state_name
                tag_info = self._point_registry.get(tag)

                # Should not be None as we just added it
                if tag_info:
                    self._history_updaters.append(make_history_updater(tag_info))

    def raw_point_tag_for_state(self, raw_state_name: str) -> str | None:
        """Return the canonical PointRegistry tag for a raw process-model state.

        Returns ``None`` when *raw_state_name* is not a known state.
        """
        metadata = self.process_model.state_metadata_dict.get(raw_state_name)
        if metadata is None:
            return None
        return f"(raw, {metadata.type.name})_{raw_state_name}"

    def make_actuator_data_setter(
        self,
        actuator_tag: str,
        *,
        source_unit: UnitBase | None = None,
    ) -> Callable[[DataValue], None]:
        point_tag = self.raw_point_tag_for_state(actuator_tag)
        if point_tag is None:
            point_tag = actuator_tag

        point_setter = self.point_registry.make_converted_data_setter(point_tag, source_unit)

        if actuator_tag.startswith("actuator/heat/"):

            def set_external_heat_actuator_data(data_value: DataValue) -> None:
                value = data_value.value
                if not isinstance(value, (int, float, np.floating)):
                    raise ValueError(
                        f"heat actuator '{actuator_tag}' requires scalar numeric controller output"
                    )
                scalar_value = float(value)
                if not isfinite(scalar_value):
                    raise ValueError(
                        f"heat actuator '{actuator_tag}' requires finite controller output"
                    )
                self._pending_heat_actuator_rates[actuator_tag] = scalar_value
                point_setter(DataValue(time=data_value.time, value=scalar_value, ok=data_value.ok))

            return set_external_heat_actuator_data

        if actuator_tag not in self.process_model.state_metadata_dict:
            return point_setter

        state_setter = self.process_model.make_converted_setter(actuator_tag, source_unit)

        def set_actuator_data(data_value: DataValue) -> None:
            state_setter(data_value.value)
            point_setter(data_value)

        return set_actuator_data

    def consume_pending_heat_actuator_rate_commands(self) -> Mapping[str, float]:
        pending = {
            actuator_tag: self._pending_heat_actuator_rates[actuator_tag]
            for actuator_tag in sorted(self._pending_heat_actuator_rates)
        }
        self._pending_heat_actuator_rates = {}
        return pending

    def _validate(self):
        exception_group: list[Exception] = []
        exception_group.extend(self._validate_sensors_resolvable())
        exception_group.extend(self._validate_controllers_resolvable())

        if len(exception_group) > 0:
            raise ExceptionGroup(
                "errors encountered during usable quantity instantiation:", exception_group
            )

    def _validate_sensors_resolvable(self) -> list[SensorConfigurationError]:
        exception_group: list[SensorConfigurationError] = []
        unavailable_measurement_tags: list[str] = []
        available_measurement_tags = self.process_model.state_list

        for sensor in self.sensors:
            measurement_tag = sensor.measurement_tag
            if measurement_tag not in available_measurement_tags:
                unavailable_measurement_tags.append(measurement_tag)

        if len(unavailable_measurement_tags) > 0:
            exception_group.append(
                SensorConfigurationError(
                    "The following measurement tag(s) are not defined in measurable quantities: "
                    + ", ".join(unavailable_measurement_tags)
                )
            )
        return exception_group

    def _validate_controllers_resolvable(self) -> list[ControllerConfigurationError]:
        exception_group: list[ControllerConfigurationError] = []
        available_ce_tags = self.process_model.boundary_view.state_list
        forbidden_plain_ce_tags: list[str] = []

        for control_element in self.control_elements:
            try:
                self.validate_static_control_element_mv_tag(control_element.mv_tag)
            except ControllerConfigurationError:
                forbidden_plain_ce_tags.append(control_element.mv_tag)

        if len(forbidden_plain_ce_tags) > 0:
            exception_group.append(
                ControllerConfigurationError(
                    "The following controlled variables are not controller-bindable plain valve/pump process tags; "
                    + "use canonical actuator tags instead: "
                    + ", ".join(forbidden_plain_ce_tags)
                )
            )

        improper_ce_tags = [
            c.mv_tag
            for c in self.control_elements
            if c.mv_tag not in available_ce_tags
            and _CANONICAL_RUNTIME_ACTUATOR_TAG_PATTERN.fullmatch(c.mv_tag) is None
        ]

        if len(improper_ce_tags) > 0:
            exception_group.append(
                ControllerConfigurationError(
                    "The following controlled variables are not defined as system control elements:"
                    + ", ".join(improper_ce_tags)
                )
            )
        return exception_group

    def validate_static_control_element_mv_tag(self, mv_tag: str) -> None:
        if _CANONICAL_RUNTIME_ACTUATOR_TAG_PATTERN.fullmatch(mv_tag) is not None:
            return

        expected_canonical_tag = _PLAIN_VALVE_PUMP_CONTROL_TAG_RULES.get(
            (type(self.process_model).__name__, mv_tag)
        )
        if expected_canonical_tag is None:
            return

        raise ControllerConfigurationError(
            f"control element mv_tag '{mv_tag}' is not controller-bindable; "
            + f"use canonical actuator tag '{expected_canonical_tag}'"
        )

    def _update_components(self) -> None:
        """
        Handles the control loop logic before integration.

        This method updates all sensors and controllers based on the current state,
        """
        t = self.time
        for s in self.sensors:
            if s.should_update(t):
                _ = s.update(t)
        for c in self.calculations:
            if c.should_update(t):
                _ = c.update(t)
        for c in self.control_elements:
            if c.should_update(t):
                _ = c.update(t)

    def add_component(
        self, component: AbstractSensor | AbstractCalculation | ControlElement
    ) -> tuple[Exception | None, bool]:
        """
        Adds sensors, calculations, and controllers to the system.
        Performs the necessary wiring and initialization steps to bind
        them to the system.
        """
        error = None
        successful = True
        # for sensor and controller, if an error was raised, it is fatal, so
        # the following code assumes if it returned, we are ok.
        # for calculation, that is a different issue.
        if isinstance(component, AbstractSensor):
            self.point_registry.add(component.point)
            # don't care about sensor lol, only way it fails is if
            # state value is bad, in which case scipy solver will fail later.
            exceptions = component.install(self)
            if not exceptions:
                successful = True
            else:
                error = exceptions[0]
                successful = False
        elif isinstance(component, AbstractCalculation):
            # output tag info available before wiring inputs, but
            # certain calculations have some preprocessing during the wiring stage,
            # such as resolving unit issues. Thus, put it after wiring inputs.
            exceptions = component.install(self)
            if not exceptions:
                self.point_registry.add(component.output_point_dict)
                successful = True
            else:
                error = exceptions[0]
                successful = False
        elif isinstance(component, ControlElement):  # pyright: ignore[reportUnnecessaryIsInstance]
            exceptions = component.install(self)
            if not exceptions:
                self.point_registry.add(component.controller_reference_point_dict)
                successful = True
            else:
                error = exceptions[0]
                successful = False
        return error, successful

    def step(self, duration: Seconds | TimeQuantity | None = None) -> None:
        """
        The main public method to advance the simulation by one time step.

        Performs one integration step by calling the ODE solver.

        """
        show_progress = False
        duration = second(duration) if duration is not None else self.dt
        nsteps = round(duration / self.dt)
        if nsteps > 1:
            if logger.level == logging.NOTSET:
                # dont show progress bar if we are logging.
                show_progress = self.show_progress
        pbar = None
        if show_progress:
            pbar = tqdm(total=nsteps)
        # update sensors, calculations, and controllers
        # and then update the states with single_step()
        # raise RuntimeError(f"DEBUG: Pre-loop. nsteps={nsteps}")
        for _ in range(int(nsteps)):
            self._update_components()
            self.process_model.step(self.dt)
            for updater in self._history_updaters:  # only populated if record history is True
                updater(self.time)
            if pbar:
                _ = pbar.update(1)
        if pbar:
            pbar.close()

    def extend_controller_reference_trajectory(
        self, cv_tag: str, value: StateValue | None = None
    ) -> "Trajectory":
        """
        used to 'extend' the reference trajectory of a controller from the current time onwards.
        If the trajectory has already been defined into the future, the trajectory is trimmed
        back to the current time.

        cv_tag is used to specify which controller

        """
        if cv_tag not in self.controller_dictionary:
            raise ValueError(
                f"Specified cv_tag '{cv_tag}' to extend the trajectory for does not correspond"
                + f" to any defined controllers. Available controller cv_tags are {self.cv_tag_list}."
            )

        controller = self.controller_dictionary[cv_tag]
        if controller.mode != ControllerMode.AUTO:
            logging.info(
                f"Tried to change trajectory of '{controller.cv_tag}' controller but failed - "
                + f"controller must be in AUTO mode, but is {controller.mode.name}. "
            )
        active_trajectory = controller.reference_trajectory
        if active_trajectory is None:
            raise RuntimeError("Somehow the controller has no reference_trajectory. Report bug.")
        if value is None:
            value = active_trajectory(self.time)

        old_value = active_trajectory(self.time)
        _ = active_trajectory.set(t=self.time, value=value)
        new_value = active_trajectory(self.time)
        logger.info(
            "Reference trajectory for '%(tag)s' controller changed at time %(time)0.0f "
            + "from %(old)0.1e to %(new)0.1e",
            {"tag": cv_tag, "time": self.time, "old": old_value, "new": new_value},
        )
        return active_trajectory

    def extend_control_element_mv_trajectory(
        self, mv_tag: str, value: StateValue | None = None
    ) -> "Trajectory":
        """
        used to 'extend' the manipulated variable trajectory of a controller from the current time onwards.
        If the trajectory has already been defined into the future, the trajectory is trimmed
        back to the current time.

        !! Changes the corresponding controller's mode to MANUAL

        mv_tag is used to specify which controller! different from extend_controller_reference_trajectory!

        """
        if mv_tag not in self.control_element_mv_dictionary:
            raise ValueError(
                f"Specified mv_tag '{mv_tag}' to extend the trajectory for does not correspond"
                + f" to any defined control elements. Available mv_tags are {self.mv_tag_list}."
            )

        control_element = self.control_element_mv_dictionary[mv_tag]
        control_element.change_control_mode(ControllerMode.MANUAL)
        active_trajectory = control_element.mv_trajectory
        if active_trajectory is None:
            raise RuntimeError("Somehow the control element has no mv_trajectory. Report bug.")

        if value is None:
            value = active_trajectory(self.time)
        old_value = active_trajectory(self.time)
        _ = active_trajectory.set(t=self.time, value=value)
        new_value = active_trajectory(self.time)
        logger.info(
            "MV trajectory for '%(tag)s' controller changed at time %(time)0.0f "
            + "from %(old)0.1e to %(new)0.1e",
            {"tag": mv_tag, "time": self.time, "old": old_value, "new": new_value},
        )
        return active_trajectory

    def set_controller_mode(self, cv_tag: str, mode: ControllerMode | str) -> ControllerMode:
        """Change the mode of a controller identified by ``cv_tag``."""
        if cv_tag not in self.controller_dictionary:
            raise ValueError(
                f"Specified cv_tag '{cv_tag}' does not correspond to any defined controllers. "
                + f"Available controller cv_tags are {self.cv_tag_list}."
            )
        controller = self.controller_dictionary[cv_tag]
        controller.change_control_mode(mode)
        return controller.mode

    @property
    def sensor_bindings(self) -> dict[str, RuntimeSensorBinding]:
        return dict(self._sensor_bindings_by_id)

    @property
    def controller_bindings(self) -> dict[str, RuntimeControllerBinding]:
        return dict(self._controller_bindings_by_id)

    def apply_sensor_runtime_mutation(
        self,
        *,
        operation: str,
        mutation: Mapping[str, object],
        request_metadata: Mapping[str, object],
    ) -> None:
        del request_metadata
        snapshot = self._capture_sensor_mutation_snapshot()
        try:
            if operation == "create_sensor":
                self._apply_create_sensor_mutation(mutation)
                return
            if operation == "bind_sensor":
                self._apply_bind_sensor_mutation(mutation)
                return
            if operation == "unbind_sensor":
                self._apply_unbind_sensor_mutation(mutation)
                return
            if operation == "remove_sensor":
                self._apply_remove_sensor_mutation(mutation)
                return
            raise ValueError(f"unsupported sensor runtime operation '{operation}'")
        except Exception:
            self._restore_sensor_mutation_snapshot(snapshot)
            raise

    def create_sensor(
        self,
        *,
        sensor_id: str,
        signal_key: str,
        process_id: str | None = None,
        port_id: str | None = None,
        line_id: str | None = None,
        sensor_type: str = "SampledDelayedSensor",
        sensor_module: str = "modular_simulation.components.sensors.sampled_delayed_sensor",
        sensor_config: Mapping[str, object] | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> AbstractSensor:
        mutation: dict[str, object] = {
            "sensor_id": sensor_id,
            "signal_key": signal_key,
            "sensor_type": sensor_type,
            "sensor_module": sensor_module,
        }
        if process_id is not None:
            mutation["process_id"] = process_id
        if port_id is not None:
            mutation["port_id"] = port_id
        if line_id is not None:
            mutation["line_id"] = line_id
        if sensor_config is not None:
            mutation["sensor_config"] = dict(sensor_config)
        if metadata is not None:
            mutation["metadata"] = dict(metadata)
        self.apply_sensor_runtime_mutation(
            operation="create_sensor",
            mutation=mutation,
            request_metadata={},
        )
        return self._find_sensor_by_id(sensor_id)

    def bind_sensor(
        self,
        *,
        sensor_id: str,
        signal_key: str,
        process_id: str | None = None,
        port_id: str | None = None,
        line_id: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> RuntimeSensorBinding:
        mutation: dict[str, object] = {
            "sensor_id": sensor_id,
            "signal_key": signal_key,
        }
        if process_id is not None:
            mutation["process_id"] = process_id
        if port_id is not None:
            mutation["port_id"] = port_id
        if line_id is not None:
            mutation["line_id"] = line_id
        if metadata is not None:
            mutation["metadata"] = dict(metadata)
        self.apply_sensor_runtime_mutation(
            operation="bind_sensor",
            mutation=mutation,
            request_metadata={},
        )
        return self._sensor_bindings_by_id[sensor_id]

    def unbind_sensor(self, *, sensor_id: str) -> None:
        self.apply_sensor_runtime_mutation(
            operation="unbind_sensor",
            mutation={"sensor_id": sensor_id},
            request_metadata={},
        )

    def remove_sensor(self, *, sensor_id: str) -> None:
        self.apply_sensor_runtime_mutation(
            operation="remove_sensor",
            mutation={"sensor_id": sensor_id},
            request_metadata={},
        )

    def create_controller(
        self,
        *,
        controller_id: str,
        controller_type: str,
        controller_module: str,
        controller_config: Mapping[str, object] | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> None:
        mutation: dict[str, object] = {
            "controller_id": controller_id,
            "controller_type": controller_type,
            "controller_module": controller_module,
        }
        if controller_config is not None:
            mutation["controller_config"] = dict(controller_config)
        if metadata is not None:
            mutation["metadata"] = dict(metadata)
        self.apply_controller_runtime_mutation(
            operation="create_controller",
            mutation=mutation,
            request_metadata={},
        )

    def bind_controller_input(self, *, controller_id: str, signal_key: str) -> None:
        self.apply_controller_runtime_mutation(
            operation="bind_controller_input",
            mutation={"controller_id": controller_id, "signal_key": signal_key},
            request_metadata={},
        )

    def bind_controller_output(self, *, controller_id: str, actuator_tag: str) -> None:
        self.apply_controller_runtime_mutation(
            operation="bind_controller_output",
            mutation={"controller_id": controller_id, "actuator_tag": actuator_tag},
            request_metadata={},
        )

    def configure_controller_mode(self, *, controller_id: str, mode: str) -> None:
        self.apply_controller_runtime_mutation(
            operation="configure_controller_mode",
            mutation={"controller_id": controller_id, "mode": mode},
            request_metadata={},
        )

    def activate_controller(self, *, controller_id: str) -> None:
        self.apply_controller_runtime_mutation(
            operation="activate_controller",
            mutation={"controller_id": controller_id},
            request_metadata={},
        )

    def apply_controller_runtime_mutation(
        self,
        *,
        operation: str,
        mutation: Mapping[str, object],
        request_metadata: Mapping[str, object],
    ) -> None:
        del request_metadata
        snapshot = self._capture_controller_mutation_snapshot()
        try:
            if operation == "create_controller":
                self._apply_create_controller_mutation(mutation)
                return
            if operation == "bind_controller_input":
                self._apply_bind_controller_input_mutation(mutation)
                return
            if operation == "bind_controller_output":
                self._apply_bind_controller_output_mutation(mutation)
                return
            if operation == "configure_controller_mode":
                self._apply_configure_controller_mode_mutation(mutation)
                return
            if operation == "activate_controller":
                self._apply_activate_controller_mutation(mutation)
                return
            raise ValueError(f"unsupported controller runtime operation '{operation}'")
        except Exception:
            self._restore_controller_mutation_snapshot(snapshot)
            raise

    def _apply_create_controller_mutation(self, mutation: Mapping[str, object]) -> None:
        controller_id = self._require_non_empty_string(
            mutation, "controller_id", "create_controller"
        )
        if controller_id in self._runtime_controller_definitions:
            raise ValueError(f"controller '{controller_id}' is already defined")

        controller_type = self._require_non_empty_string(
            mutation, "controller_type", "create_controller"
        )
        controller_module = self._require_non_empty_string(
            mutation,
            "controller_module",
            "create_controller",
        )
        controller_config = self._mapping_from_mutation(
            mutation=mutation,
            field_name="controller_config",
            operation="create_controller",
            required=False,
        )
        metadata = self._mapping_from_mutation(
            mutation=mutation,
            field_name="metadata",
            operation="create_controller",
            required=False,
        )
        self._runtime_controller_definitions[controller_id] = _RuntimeControllerDefinition(
            controller_id=controller_id,
            controller_type=controller_type,
            controller_module=controller_module,
            controller_config=controller_config,
            signal_key=None,
            actuator_tag=None,
            mode="auto",
            metadata=metadata,
            active=False,
        )

    def _apply_bind_controller_input_mutation(self, mutation: Mapping[str, object]) -> None:
        controller_id = self._require_non_empty_string(
            mutation,
            "controller_id",
            "bind_controller_input",
        )
        signal_key = self._require_non_empty_string(mutation, "signal_key", "bind_controller_input")
        definition = self._require_controller_definition(controller_id)
        self._ensure_controller_not_active(definition, operation="bind_controller_input")

        self._runtime_controller_definitions[controller_id] = _RuntimeControllerDefinition(
            controller_id=definition.controller_id,
            controller_type=definition.controller_type,
            controller_module=definition.controller_module,
            controller_config=dict(definition.controller_config),
            signal_key=signal_key,
            actuator_tag=definition.actuator_tag,
            mode=definition.mode,
            metadata=dict(definition.metadata),
            active=False,
        )

    def _apply_bind_controller_output_mutation(self, mutation: Mapping[str, object]) -> None:
        controller_id = self._require_non_empty_string(
            mutation,
            "controller_id",
            "bind_controller_output",
        )
        actuator_tag = self._require_non_empty_string(
            mutation,
            "actuator_tag",
            "bind_controller_output",
        )
        definition = self._require_controller_definition(controller_id)
        self._ensure_controller_not_active(definition, operation="bind_controller_output")

        self._runtime_controller_definitions[controller_id] = _RuntimeControllerDefinition(
            controller_id=definition.controller_id,
            controller_type=definition.controller_type,
            controller_module=definition.controller_module,
            controller_config=dict(definition.controller_config),
            signal_key=definition.signal_key,
            actuator_tag=actuator_tag,
            mode=definition.mode,
            metadata=dict(definition.metadata),
            active=False,
        )

    def _apply_configure_controller_mode_mutation(self, mutation: Mapping[str, object]) -> None:
        controller_id = self._require_non_empty_string(
            mutation,
            "controller_id",
            "configure_controller_mode",
        )
        mode = self._require_non_empty_string(mutation, "mode", "configure_controller_mode")
        normalized_mode = mode.lower()
        if normalized_mode not in {"auto", "manual"}:
            raise ValueError(
                "operation 'configure_controller_mode' field 'mode' must be one of ['auto', 'manual']"
            )

        definition = self._require_controller_definition(controller_id)
        self._ensure_controller_not_active(definition, operation="configure_controller_mode")
        self._runtime_controller_definitions[controller_id] = _RuntimeControllerDefinition(
            controller_id=definition.controller_id,
            controller_type=definition.controller_type,
            controller_module=definition.controller_module,
            controller_config=dict(definition.controller_config),
            signal_key=definition.signal_key,
            actuator_tag=definition.actuator_tag,
            mode=normalized_mode,
            metadata=dict(definition.metadata),
            active=False,
        )

    def _apply_activate_controller_mutation(self, mutation: Mapping[str, object]) -> None:
        controller_id = self._require_non_empty_string(
            mutation, "controller_id", "activate_controller"
        )
        definition = self._require_controller_definition(controller_id)
        self._ensure_controller_not_active(definition, operation="activate_controller")

        signal_key = definition.signal_key
        actuator_tag = definition.actuator_tag
        if signal_key is None:
            raise ControllerConfigurationError(
                f"controller '{controller_id}' is missing an input signal binding"
            )
        if actuator_tag is None:
            raise ControllerConfigurationError(
                f"controller '{controller_id}' is missing an actuator binding"
            )
        from modular_simulation.measurables.control_surface_contract import (
            ControlSurfaceContractError,
            validate_runtime_actuator_binding,
        )

        try:
            normalized_actuator_tag = self._normalize_runtime_actuator_tag(actuator_tag)
            validate_runtime_actuator_binding(self.process_model, normalized_actuator_tag)
        except (ControlSurfaceContractError, ValueError) as error:
            raise ControllerConfigurationError(
                f"controller '{controller_id}' cannot bind actuator '{actuator_tag}': {error}"
            ) from error

        signal_point = self.point_registry.get(signal_key)
        if signal_point is None or signal_point.type not in {"measured", "calculated"}:
            raise ControllerConfigurationError(
                f"controller '{controller_id}' input signal '{signal_key}' is unresolved; "
                + "expected a measured or calculated point"
            )

        control_element = self._find_control_element_by_mv_tag(normalized_actuator_tag)
        if control_element is None:
            raise ControllerConfigurationError(
                f"controller '{controller_id}' references unknown actuator '{actuator_tag}'"
            )
        if control_element.controller is not None:
            raise ControllerConfigurationError(
                f"actuator '{actuator_tag}' is already bound to controller '{control_element.controller.cv_tag}'"
            )

        controller = self._instantiate_runtime_controller(
            definition=definition, signal_key=signal_key
        )
        control_mode = ControllerMode.AUTO if definition.mode == "auto" else ControllerMode.MANUAL
        self._attach_controller_to_control_element(
            controller_id=controller_id,
            control_element=control_element,
            controller=controller,
            control_mode=control_mode,
        )

        self._runtime_controller_definitions[controller_id] = _RuntimeControllerDefinition(
            controller_id=definition.controller_id,
            controller_type=definition.controller_type,
            controller_module=definition.controller_module,
            controller_config=dict(definition.controller_config),
            signal_key=definition.signal_key,
            actuator_tag=normalized_actuator_tag,
            mode=definition.mode,
            metadata=dict(definition.metadata),
            active=True,
        )
        self._controller_bindings_by_id[controller_id] = RuntimeControllerBinding(
            controller_id=controller_id,
            signal_key=signal_key,
            actuator_tag=normalized_actuator_tag,
            mode=definition.mode,
            metadata=dict(definition.metadata),
        )

    def _normalize_runtime_actuator_tag(self, actuator_tag: str) -> str:
        if _CANONICAL_RUNTIME_ACTUATOR_TAG_PATTERN.fullmatch(actuator_tag) is None:
            raise ValueError(
                f"actuator '{actuator_tag}' is not controller-bindable; expected canonical actuator namespace tag "
                + "'actuator/valve/<id>', 'actuator/pump/<id>', or 'actuator/heat/<id>'"
            )
        return actuator_tag

    def _instantiate_runtime_controller(
        self,
        *,
        definition: _RuntimeControllerDefinition,
        signal_key: str,
    ) -> AbstractController:
        module = import_module(definition.controller_module)
        controller_class_object = getattr(module, definition.controller_type, None)
        if not isinstance(controller_class_object, type) or not issubclass(
            controller_class_object,
            AbstractController,
        ):
            raise ControllerConfigurationError(
                "create_controller requires a controller class "
                + f"'{definition.controller_type}' in module '{definition.controller_module}'"
            )

        controller_class = cast(type[AbstractController], controller_class_object)
        payload: dict[str, object] = dict(definition.controller_config)
        payload["cv_tag"] = signal_key
        try:
            controller_factory = cast(Any, controller_class)
            return cast(AbstractController, controller_factory.model_validate(payload))
        except Exception as error:
            raise ControllerConfigurationError(
                f"controller '{definition.controller_id}' configuration is invalid: {error}"
            ) from error

    def _attach_controller_to_control_element(
        self,
        *,
        controller_id: str,
        control_element: ControlElement,
        controller: AbstractController,
        control_mode: ControllerMode,
    ) -> None:
        registry_snapshot = self._capture_point_registry_snapshot()
        previous_controller = control_element.controller
        previous_mode = control_element.mode
        previous_mode_manager = control_element._mode_manager
        try:
            installation_errors = controller.install(self)
            if installation_errors:
                raise ControllerConfigurationError(
                    f"controller '{controller_id}' installation failed: {installation_errors[0]}"
                )

            cv_value = self.point_registry[controller.cv_tag].data.value
            mv_value = control_element._mv_point.data.value
            if bool(np.isscalar(cv_value)) != bool(np.isscalar(mv_value)):
                raise ControllerConfigurationError(
                    f"controller '{controller_id}' input/output dimensionality is incompatible with actuator '{control_element.mv_tag}'"
                )

            mv_getter = control_element._mv_point.make_converted_data_getter()
            is_wired = controller.wire_to_element(
                system=self,
                mv_getter=mv_getter,
                mv_range=control_element.mv_range,
                mv_tag=control_element.mv_tag,
                mv_unit=control_element._mv_point.unit,
            )
            if not is_wired:
                raise ControllerConfigurationError(
                    f"controller '{controller_id}' failed to wire to actuator '{control_element.mv_tag}'"
                )

            control_element.controller = controller
            control_element._mode_manager = ControlElementModeManager(
                mode=control_mode,
                manual_mv_source=control_element.mv_trajectory,
                auto_mv_source=controller,
                mv_getter=control_element._mv_point.make_converted_data_getter(),
                mv_tag=control_element.mv_tag,
            )
            control_element.mode = control_mode
            _ = control_element.change_control_mode(control_mode)
            self.point_registry.add(control_element.controller_reference_point_dict)
            self._invalidate_controller_cache()
        except Exception:
            control_element.controller = previous_controller
            control_element.mode = previous_mode
            control_element._mode_manager = previous_mode_manager
            self._restore_point_registry_snapshot(registry_snapshot)
            self._invalidate_controller_cache()
            raise

    def _find_control_element_by_mv_tag(self, mv_tag: str) -> ControlElement | None:
        for control_element in self.control_elements:
            if control_element.mv_tag == mv_tag:
                return control_element
        return None

    def _require_controller_definition(self, controller_id: str) -> _RuntimeControllerDefinition:
        definition = self._runtime_controller_definitions.get(controller_id)
        if definition is None:
            raise ValueError(f"unknown controller '{controller_id}'")
        return definition

    def _ensure_controller_not_active(
        self,
        definition: _RuntimeControllerDefinition,
        *,
        operation: str,
    ) -> None:
        if definition.active:
            raise ValueError(
                f"operation '{operation}' cannot modify active controller '{definition.controller_id}'"
            )

    def _capture_controller_mutation_snapshot(self) -> _ControllerMutationSnapshot:
        return _ControllerMutationSnapshot(
            controller_definitions=dict(self._runtime_controller_definitions),
            controller_bindings=dict(self._controller_bindings_by_id),
            point_registry_points=dict(self._point_registry._points),
            measured_points_cache=(
                None
                if self._point_registry._measured_points is None
                else dict(self._point_registry._measured_points)
            ),
            calculated_points_cache=(
                None
                if self._point_registry._calculated_points is None
                else dict(self._point_registry._calculated_points)
            ),
            reference_points_cache=(
                None
                if self._point_registry._reference_points is None
                else dict(self._point_registry._reference_points)
            ),
        )

    def _restore_controller_mutation_snapshot(
        self,
        snapshot: _ControllerMutationSnapshot,
    ) -> None:
        self._runtime_controller_definitions = dict(snapshot.controller_definitions)
        self._controller_bindings_by_id = dict(snapshot.controller_bindings)
        self._point_registry._points = dict(snapshot.point_registry_points)
        self._point_registry._measured_points = (
            None if snapshot.measured_points_cache is None else dict(snapshot.measured_points_cache)
        )
        self._point_registry._calculated_points = (
            None
            if snapshot.calculated_points_cache is None
            else dict(snapshot.calculated_points_cache)
        )
        self._point_registry._reference_points = (
            None
            if snapshot.reference_points_cache is None
            else dict(snapshot.reference_points_cache)
        )
        self._invalidate_controller_cache()

    def _capture_point_registry_snapshot(
        self,
    ) -> tuple[
        dict[str, Point],
        dict[str, Point] | None,
        dict[str, Point] | None,
        dict[str, Point] | None,
    ]:
        point_registry = self._point_registry
        return (
            dict(point_registry._points),
            None
            if point_registry._measured_points is None
            else dict(point_registry._measured_points),
            None
            if point_registry._calculated_points is None
            else dict(point_registry._calculated_points),
            None
            if point_registry._reference_points is None
            else dict(point_registry._reference_points),
        )

    def _restore_point_registry_snapshot(
        self,
        snapshot: tuple[
            dict[str, Point],
            dict[str, Point] | None,
            dict[str, Point] | None,
            dict[str, Point] | None,
        ],
    ) -> None:
        point_registry = self._point_registry
        point_registry._points = dict(snapshot[0])
        point_registry._measured_points = None if snapshot[1] is None else dict(snapshot[1])
        point_registry._calculated_points = None if snapshot[2] is None else dict(snapshot[2])
        point_registry._reference_points = None if snapshot[3] is None else dict(snapshot[3])

    def _invalidate_controller_cache(self) -> None:
        for cache_field in (
            "controller_dictionary",
            "cv_tag_list",
            "control_element_mv_dictionary",
            "mv_tag_list",
        ):
            if cache_field in self.__dict__:
                object.__delattr__(self, cache_field)

    def _apply_create_sensor_mutation(self, mutation: Mapping[str, object]) -> None:
        sensor_id = self._require_non_empty_string(mutation, "sensor_id", "create_sensor")
        if any(sensor.name == sensor_id for sensor in self.sensors):
            raise ValueError(f"sensor '{sensor_id}' is already installed")

        binding = self._binding_from_mutation(
            mutation=mutation,
            operation="create_sensor",
            sensor_id=sensor_id,
        )
        sensor_type = self._require_non_empty_string(mutation, "sensor_type", "create_sensor")
        sensor_module = self._require_non_empty_string(mutation, "sensor_module", "create_sensor")
        sensor_config = self._mapping_from_mutation(
            mutation=mutation,
            field_name="sensor_config",
            operation="create_sensor",
            required=False,
        )

        sensor_payload = cast(dict[str, Any], dict(sensor_config))
        sensor_payload["name"] = sensor_id
        sensor_payload["measurement_tag"] = binding.signal_key
        sensor_payload.setdefault("alias_tag", sensor_id)

        module = import_module(sensor_module)
        sensor_class_object = getattr(module, sensor_type, None)
        if not isinstance(sensor_class_object, type) or not issubclass(
            sensor_class_object, AbstractSensor
        ):
            raise ValueError(
                f"create_sensor requires a sensor class '{sensor_type}' in module '{sensor_module}'"
            )

        sensor_class = cast(type[AbstractSensor], sensor_class_object)
        sensor = sensor_class(**sensor_payload)
        error, successful = self.add_component(sensor)
        if not successful:
            if error is not None:
                raise error
            raise RuntimeError("sensor installation failed without explicit error")

        self.sensors = (*self.sensors, sensor)
        self._sensor_bindings_by_id[sensor_id] = binding

    def _apply_bind_sensor_mutation(self, mutation: Mapping[str, object]) -> None:
        sensor_id = self._require_non_empty_string(mutation, "sensor_id", "bind_sensor")
        binding = self._binding_from_mutation(
            mutation=mutation,
            operation="bind_sensor",
            sensor_id=sensor_id,
        )
        sensor = self._find_sensor_by_id(sensor_id)
        sensor.bind_runtime_signal(system=self, signal_key=binding.signal_key)
        self._sensor_bindings_by_id[sensor_id] = binding

    def _apply_unbind_sensor_mutation(self, mutation: Mapping[str, object]) -> None:
        sensor_id = self._require_non_empty_string(mutation, "sensor_id", "unbind_sensor")
        sensor = self._find_sensor_by_id(sensor_id)
        sensor.unbind_runtime_signal(system=self)
        self._sensor_bindings_by_id.pop(sensor_id, None)

    def _apply_remove_sensor_mutation(self, mutation: Mapping[str, object]) -> None:
        sensor_id = self._require_non_empty_string(mutation, "sensor_id", "remove_sensor")
        sensor = self._find_sensor_by_id(sensor_id)
        self.sensors = tuple(item for item in self.sensors if item.name != sensor_id)
        self._sensor_bindings_by_id.pop(sensor_id, None)
        self._remove_sensor_point_from_registry(sensor.point.tag)

    def _capture_sensor_mutation_snapshot(self) -> _SensorMutationSnapshot:
        point_registry = self._point_registry
        sensor_state_by_id = {
            sensor.name: sensor.capture_runtime_binding_state() for sensor in self.sensors
        }
        return _SensorMutationSnapshot(
            sensors=tuple(self.sensors),
            point_registry_points=dict(point_registry._points),
            measured_points_cache=(
                None
                if point_registry._measured_points is None
                else dict(point_registry._measured_points)
            ),
            calculated_points_cache=(
                None
                if point_registry._calculated_points is None
                else dict(point_registry._calculated_points)
            ),
            reference_points_cache=(
                None
                if point_registry._reference_points is None
                else dict(point_registry._reference_points)
            ),
            sensor_bindings_by_id=dict(self._sensor_bindings_by_id),
            sensor_state_by_id=sensor_state_by_id,
        )

    def _restore_sensor_mutation_snapshot(self, snapshot: _SensorMutationSnapshot) -> None:
        point_registry = self._point_registry
        self.sensors = snapshot.sensors
        point_registry._points = dict(snapshot.point_registry_points)
        point_registry._measured_points = (
            None if snapshot.measured_points_cache is None else dict(snapshot.measured_points_cache)
        )
        point_registry._calculated_points = (
            None
            if snapshot.calculated_points_cache is None
            else dict(snapshot.calculated_points_cache)
        )
        point_registry._reference_points = (
            None
            if snapshot.reference_points_cache is None
            else dict(snapshot.reference_points_cache)
        )
        self._sensor_bindings_by_id = dict(snapshot.sensor_bindings_by_id)
        for sensor in self.sensors:
            binding_state = snapshot.sensor_state_by_id.get(sensor.name)
            if binding_state is None:
                continue
            sensor.restore_runtime_binding_state(binding_state)

    def _remove_sensor_point_from_registry(self, point_tag: str) -> None:
        point_registry = self._point_registry
        _ = point_registry._points.pop(point_tag, None)
        if point_registry._measured_points is not None:
            _ = point_registry._measured_points.pop(point_tag, None)
        if point_registry._calculated_points is not None:
            _ = point_registry._calculated_points.pop(point_tag, None)

    def _binding_from_mutation(
        self,
        *,
        mutation: Mapping[str, object],
        operation: str,
        sensor_id: str,
    ) -> RuntimeSensorBinding:
        signal_key = self._require_non_empty_string(mutation, "signal_key", operation)
        process_id = self._optional_non_empty_string(mutation, "process_id", operation)
        port_id = self._optional_non_empty_string(mutation, "port_id", operation)
        line_id = self._optional_non_empty_string(mutation, "line_id", operation)
        metadata_mapping = self._mapping_from_mutation(
            mutation=mutation,
            field_name="metadata",
            operation=operation,
            required=False,
        )

        validated = SensorBinding(
            sensor_id=sensor_id,
            signal_key=signal_key,
            process_id=process_id,
            port_id=port_id,
            line_id=line_id,
            metadata=metadata_mapping,
        )
        return RuntimeSensorBinding(
            sensor_id=validated.sensor_id,
            signal_key=validated.signal_key,
            process_id=validated.process_id,
            port_id=validated.port_id,
            line_id=validated.line_id,
            metadata=dict(validated.metadata),
        )

    def _mapping_from_mutation(
        self,
        *,
        mutation: Mapping[str, object],
        field_name: str,
        operation: str,
        required: bool,
    ) -> dict[str, object]:
        value = mutation.get(field_name)
        if value is None:
            if required:
                raise ValueError(f"operation '{operation}' requires mapping field '{field_name}'")
            return {}
        if not isinstance(value, Mapping):
            raise ValueError(f"operation '{operation}' field '{field_name}' must be a mapping")
        return {str(key): item for key, item in value.items()}

    def _find_sensor_by_id(self, sensor_id: str) -> AbstractSensor:
        for sensor in self.sensors:
            if sensor.name == sensor_id:
                return sensor
        raise ValueError(f"unknown sensor '{sensor_id}'")

    def _require_non_empty_string(
        self,
        mutation: Mapping[str, object],
        field_name: str,
        operation: str,
    ) -> str:
        value = mutation.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"operation '{operation}' requires non-empty string field '{field_name}'"
            )
        return value.strip()

    def _optional_non_empty_string(
        self,
        mutation: Mapping[str, object],
        field_name: str,
        operation: str,
    ) -> str | None:
        value = mutation.get(field_name)
        if value is None:
            return None
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"operation '{operation}' optional field '{field_name}' must be non-empty string"
            )
        return value.strip()

    @property
    def point_registry(self) -> PointRegistry:
        return self._point_registry

    @cached_property
    def controller_dictionary(self) -> dict[str, AbstractController]:
        return_dict: dict[str, AbstractController] = {}
        for control_element in self.control_elements:
            controller = control_element.controller
            while controller is not None:
                return_dict.update({controller.cv_tag: controller})
                controller = controller.cascade_controller
        return return_dict

    @cached_property
    def control_element_mv_dictionary(self) -> dict[str, ControlElement]:
        return_dict: dict[str, ControlElement] = {}
        for control_element in self.control_elements:
            return_dict.update({control_element.mv_tag: control_element})
        return return_dict

    @property
    def time(self) -> Seconds:
        return self.process_model.t

    @cached_property
    def cv_tag_list(self) -> list[str]:
        return list(self.controller_dictionary.keys())

    @cached_property
    def mv_tag_list(self) -> list[str]:
        return list(self.control_element_mv_dictionary.keys())

    @property
    def history(self) -> dict[str, list[DataValue]]:
        """Returns historized measurements and calculations."""
        return self._point_registry.history

    def save(self) -> dict[str, Any]:
        """Persist minimal configuration and component snapshots for reconstruction."""

        snapshot: dict[str, object] = {
            "system": {
                "dt": self.dt,
                "solver_options": self.solver_options,
                "record_history": self.record_history,
                "show_progress": self.show_progress,
            },
            "process_model": self.process_model.save(),
            "sensors": [sensor.save() for sensor in self.sensors],
            "calculations": [calc.save() for calc in self.calculations],
            "control_elements": [ce.save() for ce in self.control_elements],
        }

        envelope_without_checksum: dict[str, object] = {
            "schema_marker": CHECKPOINT_SCHEMA_MARKER,
            "schema_version": CHECKPOINT_SCHEMA_VERSION,
            "package_metadata": checkpoint_runtime_package_metadata(),
            "snapshot": snapshot,
        }
        envelope: dict[str, object] = dict(envelope_without_checksum)
        envelope["integrity_checksum"] = checkpoint_payload_checksum(envelope_without_checksum)
        return cast(dict[str, Any], envelope)

    @classmethod
    def load(cls, payload: dict[str, Any]) -> "System":
        """Recreate a system and its components from serialized snapshots."""

        _require_exact_keys(
            "checkpoint payload",
            payload,
            (
                "schema_marker",
                "schema_version",
                "package_metadata",
                "snapshot",
                "integrity_checksum",
            ),
        )
        schema_marker = payload["schema_marker"]
        if schema_marker != CHECKPOINT_SCHEMA_MARKER:
            raise ValueError(
                "invalid system checkpoint payload: field 'schema_marker' does not match expected marker"
            )

        schema_version = payload["schema_version"]
        if schema_version != CHECKPOINT_SCHEMA_VERSION:
            raise ValueError(
                f"[{CHECKPOINT_VERSION_MISMATCH_ERROR_CODE}] invalid system checkpoint payload: field 'schema_version' does not match expected version"
            )

        package_metadata = _require_mapping(payload["package_metadata"], "package_metadata")
        _require_exact_keys(
            "package_metadata",
            package_metadata,
            ("package_name", "package_version"),
        )
        package_name = _require_non_empty_string(
            package_metadata["package_name"],
            "package_metadata.package_name",
        )
        package_version_value = _require_non_empty_string(
            package_metadata["package_version"],
            "package_metadata.package_version",
        )
        runtime_package_metadata = checkpoint_runtime_package_metadata()
        if (
            package_name != runtime_package_metadata["package_name"]
            or package_version_value != runtime_package_metadata["package_version"]
        ):
            raise ValueError(
                f"[{CHECKPOINT_VERSION_MISMATCH_ERROR_CODE}] incompatible system checkpoint: "
                + "checkpoint package metadata does not match runtime package metadata"
            )

        provided_checksum = _require_non_empty_string(
            payload["integrity_checksum"],
            "integrity_checksum",
        )
        checksum_payload = dict(payload)
        _ = checksum_payload.pop("integrity_checksum", None)
        expected_checksum = checkpoint_payload_checksum(checksum_payload)
        if provided_checksum != expected_checksum:
            raise ValueError(
                f"[{CHECKPOINT_INTEGRITY_MISMATCH_ERROR_CODE}] invalid system checkpoint payload: "
                + "field 'integrity_checksum' does not match payload checksum"
            )

        snapshot = _require_mapping(payload["snapshot"], "snapshot")
        _require_exact_keys(
            "snapshot",
            snapshot,
            ("system", "process_model", "sensors", "calculations", "control_elements"),
        )

        system_config = _require_mapping(snapshot["system"], "snapshot.system")
        process_model = ProcessModel.load(cast(dict[str, Any], snapshot["process_model"]))
        sensors: list[AbstractSensor] = []
        for sensor_payload in _require_sequence(snapshot["sensors"], "snapshot.sensors"):
            loaded_sensor = AbstractSensor.load(cast(ComponentDataDict, sensor_payload))
            if not isinstance(loaded_sensor, AbstractSensor):
                raise TypeError("loaded sensor payload did not resolve to AbstractSensor")
            sensors.append(loaded_sensor)

        calculations: list[AbstractCalculation] = []
        for calculation_payload in _require_sequence(
            snapshot["calculations"],
            "snapshot.calculations",
        ):
            loaded_calculation = AbstractCalculation.load(
                cast(ComponentDataDict, calculation_payload)
            )
            if not isinstance(loaded_calculation, AbstractCalculation):
                raise TypeError("loaded calculation payload did not resolve to AbstractCalculation")
            calculations.append(loaded_calculation)

        control_elements: list[ControlElement] = []
        for control_element_payload in _require_sequence(
            snapshot["control_elements"],
            "snapshot.control_elements",
        ):
            loaded_control_element = ControlElement.load(
                cast(ComponentDataDict, control_element_payload)
            )
            if not isinstance(loaded_control_element, ControlElement):
                raise TypeError("loaded control payload did not resolve to ControlElement")
            control_elements.append(loaded_control_element)

        solver_options_value = cast(
            dict[str, Any],
            system_config.get("solver_options", {"method": "LSODA"}),
        )
        record_history_value = cast(bool, system_config.get("record_history", False))
        show_progress_value = cast(bool, system_config.get("show_progress", True))

        return cls(
            dt=cast(Seconds, system_config["dt"]),
            process_model=process_model,
            sensors=sensors,
            calculations=calculations,
            control_elements=control_elements,
            solver_options=solver_options_value,
            record_history=record_history_value,
            show_progress=show_progress_value,
        )


def checkpoint_runtime_package_metadata() -> dict[str, str]:
    return {
        "package_name": CHECKPOINT_PACKAGE_NAME,
        "package_version": _resolve_runtime_package_version(),
    }


def checkpoint_payload_checksum(payload: Mapping[str, object]) -> str:
    canonical_payload = _normalize_payload_for_checksum(payload)
    serialized = json.dumps(
        canonical_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _resolve_runtime_package_version() -> str:
    try:
        return package_version(CHECKPOINT_PACKAGE_NAME)
    except PackageNotFoundError:
        return "0.0.0+unknown"


def _normalize_payload_for_checksum(value: object) -> object:
    if isinstance(value, Mapping):
        typed_mapping = cast(Mapping[object, object], value)
        normalized: dict[str, object] = {}
        for raw_key, raw_value in sorted(
            typed_mapping.items(),
            key=lambda entry: str(entry[0]),
        ):
            normalized[str(raw_key)] = _normalize_payload_for_checksum(raw_value)
        return normalized
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_normalize_payload_for_checksum(item) for item in value]
    return value


def _require_exact_keys(
    context: str,
    payload: Mapping[str, object],
    expected_keys: tuple[str, ...],
) -> None:
    if set(payload.keys()) != set(expected_keys):
        raise ValueError(
            f"invalid system checkpoint payload: field '{context}' keys must be exactly {expected_keys!r}"
        )


def _require_mapping(value: object, field_name: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(
            f"invalid system checkpoint payload: field '{field_name}' must be a mapping"
        )
    typed_mapping = cast(Mapping[object, object], value)
    return {str(key): field_value for key, field_value in typed_mapping.items()}


def _require_sequence(value: object, field_name: str) -> Sequence[object]:
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError(
            f"invalid system checkpoint payload: field '{field_name}' must be a sequence"
        )
    return value


def _require_non_empty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"invalid system checkpoint payload: field '{field_name}' must be a non-empty string"
        )
    return value.strip()

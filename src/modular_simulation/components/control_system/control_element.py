from __future__ import annotations

# pyright: reportImportCycles=false, reportMissingImports=false
from typing import TYPE_CHECKING, Any, override
import numpy as np
from astropy.units import Unit
from dataclasses import asdict
from pydantic import PrivateAttr, ConfigDict, Field
from modular_simulation.components.point import DataValue, Point
from modular_simulation.validation.exceptions import (
    ControlElementConfigurationError,
    ControllerConfigurationError,
)
from modular_simulation.components.abstract_component import (
    AbstractComponent,
    ComponentUpdateResult,
)
from modular_simulation.utils.typing import Seconds, StateValue
from .controller_mode import ControllerMode
from .mode_manager import ControlElementModeManager

from .trajectory import Trajectory
from .abstract_controller import AbstractController
import logging

if TYPE_CHECKING:
    from modular_simulation.framework.system import System

logger = logging.getLogger(__name__)


class ControlElement(AbstractComponent):
    """A control element (e.g. a valve, pump, or heater) that can be controlled by a controller."""

    mv_tag: str = Field(..., description="Tag name of the manipulated variable (MV).")
    mv_trajectory: Trajectory = Field(
        ..., description="A Trajectory instance for manual control of the element."
    )
    mv_range: tuple[StateValue, StateValue] = Field(
        ..., description="The physical range of the manipulated variable."
    )
    controller: AbstractController | None = Field(
        default=None, description="The controller assigned to this element."
    )
    mode: ControllerMode = Field(
        default=ControllerMode.MANUAL,
        description="Initialization mode for the control element (AUTO or MANUAL).",
    )
    period: Seconds = Field(
        default=1e-12, description="The minimum execution period of the control element."
    )

    _mv_point: Point = PrivateAttr()
    _mv_setter: Any = PrivateAttr()
    _mode_manager: ControlElementModeManager = PrivateAttr()
    _last_update_time: Seconds = PrivateAttr(default=float("-inf"))

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="forbid",
        validate_assignment=False,
    )

    # -------- AbstractComponent Interface --------

    @override
    def _install(self, system: System) -> list[Exception]:
        """Bind the control element to the system and wire its controller."""
        exceptions: list[Exception] = []
        try:
            system.validate_static_control_element_mv_tag(self.mv_tag)
        except ControllerConfigurationError as error:
            exceptions.append(ControlElementConfigurationError(str(error)))
            return exceptions

        # Try to find the point in PointRegistry.
        # If it's a process state, System registers it with a specific prefix.
        mv_point = None
        if self.mv_tag in system.process_model.state_metadata_dict:
            prefixed_tag = system.raw_point_tag_for_state(self.mv_tag)
            if prefixed_tag is not None:
                mv_point = system.point_registry.get(prefixed_tag)

        if mv_point is None:
            # Fallback 1: Direct lookup
            mv_point = system.point_registry.get(self.mv_tag)

        if mv_point is None:
            # Fallback 2: Search for suffix match (handling System's internal naming)
            # This handles cases where metadata.type.name might differ or be casing dependent
            possible_matches = [
                t
                for t in system.point_registry
                if t.endswith(f"_{self.mv_tag}") and t.startswith("(raw,")
            ]
            if len(possible_matches) == 1:
                mv_point = system.point_registry.get(possible_matches[0])

        if mv_point is None and self.mv_tag.startswith("actuator/heat/"):
            actuator_id = self.mv_tag.split("/", 2)[2]
            source_state = system.process_model.state_metadata_dict.get(actuator_id)
            inferred_unit = source_state.unit if source_state is not None else Unit("1")
            mv_point = Point(
                tag=self.mv_tag,
                unit=inferred_unit,
                type="raw",
                description=f"runtime heat actuator command '{self.mv_tag}'",
                _raw_tag=self.mv_tag,
            )
            initial_value = self.mv_trajectory(0.0)
            mv_point.data = DataValue(time=system.time, value=initial_value, ok=True)
            system.point_registry.add(mv_point)

        if mv_point is None:
            exceptions.append(
                ControlElementConfigurationError(
                    f"Could not find the manipulated variable '{self.mv_tag}'."
                )
            )
            return exceptions

        self._mv_point = mv_point

        try:
            self._mv_setter = system.make_actuator_data_setter(
                self.mv_tag,
                source_unit=self._mv_point.unit,
            )
        except Exception as e:
            exceptions.append(ControlElementConfigurationError(f"Failed to bind MV setter: {e}"))
            return exceptions

        # Initialize internal state
        if np.isscalar(mv_point.data.value):
            self._is_scalar = True

        # initialize the control element & its controllers (if any)
        if self.controller is not None:
            if "mode" not in self.model_fields_set:
                self.mode = ControllerMode.AUTO

            # Phase 1: Base component commissioning
            controller_exceptions = self.controller.install(system)
            if controller_exceptions:
                exceptions.extend(controller_exceptions)
                return exceptions

            # Phase 2: Element-specific wiring (commissioning)
            mv_getter = mv_point.make_converted_data_getter()
            if not self.controller.wire_to_element(
                system=system,
                mv_getter=mv_getter,
                mv_range=self.mv_range,
                mv_tag=self.mv_tag,
                mv_unit=self._mv_point.unit,
            ):
                exceptions.append(
                    ControllerConfigurationError(
                        f"Controller for '{self.mv_tag}' failed to wire to element."
                    )
                )
                return exceptions
        else:
            # silently force mode to MANUAL in case it was AUTO during commissioning
            self.mode = ControllerMode.MANUAL

        self._mode_manager = ControlElementModeManager(
            mode=self.mode,
            manual_mv_source=self.mv_trajectory,
            auto_mv_source=self.controller,
            mv_getter=mv_point.make_converted_data_getter(),
            mv_tag=self.mv_tag,
        )

        if not exceptions:
            self._initialized = True

        return exceptions

    @override
    def _should_update(self, t: Seconds) -> bool:
        start_time = self._last_update_time
        return t >= (start_time + self.period)

    @override
    def _update(self, t: Seconds) -> ComponentUpdateResult:
        """Run one control update cycle and return result."""
        try:
            # Update internal timer
            self._last_update_time = t

            # Original logic from _control_update moved here
            control_action = self._mode_manager.get_control_action(t)

            if control_action.ok:
                if self._is_scalar:
                    control_action.value = min(
                        max(control_action.value, self.mv_range[0]), self.mv_range[1]
                    )
                else:
                    control_action.value = np.clip(
                        control_action.value, self.mv_range[0], self.mv_range[1]
                    )

            self._mv_setter(control_action)
            return ComponentUpdateResult(data_value=control_action, exceptions=[])
        except Exception as e:
            return ComponentUpdateResult(data_value=self._mv_point.data, exceptions=[e])

    @override
    def _load_runtime_state(self, state: dict[str, Any]) -> None:
        allowed_keys = {"mode", "mv"}
        extra_keys = sorted(set(state) - allowed_keys)
        if extra_keys:
            raise ValueError(
                "control element runtime state has unsupported field(s): "
                + ", ".join(repr(key) for key in extra_keys)
            )
        if "mode" in state:
            self.mode = ControllerMode[state["mode"]]
        if "mv" in state:
            # Optionally restore mv point data if needed, but usually it's driven by PM
            pass

    # -------- Control Logic --------

    def change_control_mode(self, mode: ControllerMode | str) -> None:
        """Change the control mode of the element."""
        mode = ControllerMode.from_value(mode)
        logger.info(
            "'%s' control element mode is changed from %s --> %s",
            self.mv_tag,
            self.mode.name,
            mode.name,
        )
        self.mode = self._mode_manager.change_mode(mode)

    @override
    def _get_configuration_dict(self) -> dict[str, Any]:
        config = self.model_dump(exclude={"controller", "mv_trajectory"})
        config["mv_trajectory"] = self.mv_trajectory.save()
        if self.controller is not None:
            config["controller"] = self.controller.save()
        return config

    @override
    def _get_runtime_state_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode.name,
            "mv": asdict(self._mv_point.data),
        }

    @classmethod
    @override
    def _load_configuration(cls, data: dict[str, Any]) -> "ControlElement":
        config = dict(data)

        # Handle Trajectory
        if "mv_trajectory" in config:
            from .trajectory import Trajectory

            config["mv_trajectory"] = Trajectory.load(config["mv_trajectory"])

        # Handle Controller
        if "controller" in config and config["controller"] is not None:
            from .abstract_controller import AbstractController

            config["controller"] = AbstractController.load(config["controller"])

        return cls(**config)

    # -------- Properties --------

    @property
    def controller_reference_point_dict(self) -> dict[str, Point]:
        if self.controller is None:
            return {}
        return self.controller.reference_point_dict


ControlElement.model_rebuild()

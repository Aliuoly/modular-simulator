from __future__ import annotations

from enum import Enum
import re
from typing import TYPE_CHECKING

from modular_simulation.measurables.process_model import StateType

if TYPE_CHECKING:
    from modular_simulation.measurables.process_model import ProcessModel


class ControlSurfaceCategory(str, Enum):
    PHYSICAL_ACTUATOR = "physical_actuator"
    MEASURED_STATE = "measured_state"
    EXTERNAL_BOUNDARY_CONDITION = "external_boundary_condition"
    CONFIGURED_ABSTRACT_SPECIFICATION = "configured_abstract_specification"


class ControlSurfaceContractError(ValueError):
    pass


_NON_PHYSICAL_OVERRIDES: dict[tuple[str, str], ControlSurfaceCategory] = {
    ("FlashDrum", "imposed_pressure"): ControlSurfaceCategory.EXTERNAL_BOUNDARY_CONDITION,
    (
        "FlashDrum",
        "imposed_temperature",
    ): ControlSurfaceCategory.EXTERNAL_BOUNDARY_CONDITION,
    (
        "ComponentSeparator",
        "configured_split_fraction_targets",
    ): ControlSurfaceCategory.CONFIGURED_ABSTRACT_SPECIFICATION,
}


_NAMESPACED_ACTUATOR_TAG_PATTERN = re.compile(
    r"^actuator/[a-z0-9][a-z0-9_-]*/[A-Za-z0-9][A-Za-z0-9._/-]*$"
)

_CANONICAL_LINE_OWNED_ACTUATOR_GUIDANCE = (
    "expected actuator namespace tag 'actuator/<family>/<id>' for a line-installed control; "
    "install it with `Flowsheet.connect(..., pump=PumpInstall(...))`, `Flowsheet.connect(..., valve=ValveInstall(...))`, "
    "or `Flowsheet.connect(..., heat=HeatInstall(...))`, and use `Flowsheet.add_junction(...)` / `Flowsheet.add_sink(...)` "
    "for mixing, splitting, and product handoff"
)


def get_control_surface_category(
    process_model: ProcessModel, state_name: str
) -> ControlSurfaceCategory:
    override = _NON_PHYSICAL_OVERRIDES.get((type(process_model).__name__, state_name))
    if override is not None:
        return override

    state_type = process_model.state_metadata_dict[state_name].type
    if state_type == StateType.BOUNDARY:
        return ControlSurfaceCategory.EXTERNAL_BOUNDARY_CONDITION
    if state_type in (StateType.DIFFERENTIAL, StateType.ALGEBRAIC):
        return ControlSurfaceCategory.MEASURED_STATE
    if state_type == StateType.CONSTANT:
        return ControlSurfaceCategory.CONFIGURED_ABSTRACT_SPECIFICATION
    return ControlSurfaceCategory.EXTERNAL_BOUNDARY_CONDITION


def resolve_process_state_tag(process_model: ProcessModel, actuator_tag: str) -> str | None:
    del process_model
    if _NAMESPACED_ACTUATOR_TAG_PATTERN.fullmatch(actuator_tag):
        return actuator_tag
    if actuator_tag.startswith("(raw,") and ")_" in actuator_tag:
        candidate_tag = actuator_tag.split(")_", 1)[1]
        if _NAMESPACED_ACTUATOR_TAG_PATTERN.fullmatch(candidate_tag):
            return candidate_tag
    return None


def validate_no_banned_setpoint_names(process_model: ProcessModel) -> None:
    banned_public_names = [
        name for name in process_model.state_list if "setpoint" in name.casefold()
    ]
    if banned_public_names:
        raise ControlSurfaceContractError(
            "public/runtime/persisted state names must not contain 'setpoint': "
            + ", ".join(sorted(banned_public_names))
        )


def validate_boundary_view_has_no_physical_actuators(process_model: ProcessModel) -> None:
    violations: list[str] = []
    for state_name in process_model.boundary_view.state_list:
        category = get_control_surface_category(process_model, state_name)
        if category == ControlSurfaceCategory.PHYSICAL_ACTUATOR:
            violations.append(f"{state_name} ({category.value})")

    if violations:
        raise ControlSurfaceContractError(
            "boundary_view.state_list contains physical actuator surfaces: "
            + ", ".join(sorted(violations))
        )


def validate_runtime_actuator_binding(process_model: ProcessModel, actuator_tag: str) -> None:
    if "setpoint" in actuator_tag.casefold():
        raise ControlSurfaceContractError(
            f"actuator '{actuator_tag}' is banned by contract: names containing 'setpoint' are not controller-bindable"
        )

    resolved_actuator_tag = resolve_process_state_tag(process_model, actuator_tag)
    if resolved_actuator_tag is None:
        raise ControlSurfaceContractError(
            f"actuator '{actuator_tag}' is not controller-bindable; {_CANONICAL_LINE_OWNED_ACTUATOR_GUIDANCE}"
        )

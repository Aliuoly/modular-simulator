from __future__ import annotations

from enum import Enum
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
    ("Splitter", "split_ratios"): ControlSurfaceCategory.CONFIGURED_ABSTRACT_SPECIFICATION,
    (
        "ComponentSeparator",
        "configured_split_fraction_targets",
    ): ControlSurfaceCategory.CONFIGURED_ABSTRACT_SPECIFICATION,
    (
        "ShortcutDistillation",
        "configured_light_key_distillate_recovery_target",
    ): ControlSurfaceCategory.CONFIGURED_ABSTRACT_SPECIFICATION,
    (
        "ShortcutDistillation",
        "configured_heavy_key_bottoms_recovery_target",
    ): ControlSurfaceCategory.CONFIGURED_ABSTRACT_SPECIFICATION,
    (
        "ShortcutDistillation",
        "configured_reflux_ratio_target",
    ): ControlSurfaceCategory.CONFIGURED_ABSTRACT_SPECIFICATION,
    (
        "ShortcutDistillation",
        "configured_minimum_reflux_ratio_factor",
    ): ControlSurfaceCategory.CONFIGURED_ABSTRACT_SPECIFICATION,
}


def get_control_surface_category(
    process_model: ProcessModel, state_name: str
) -> ControlSurfaceCategory:
    override = _NON_PHYSICAL_OVERRIDES.get((type(process_model).__name__, state_name))
    if override is not None:
        return override

    state_type = process_model.state_metadata_dict[state_name].type
    if state_type == StateType.CONTROLLED:
        return ControlSurfaceCategory.PHYSICAL_ACTUATOR
    if state_type in (StateType.DIFFERENTIAL, StateType.ALGEBRAIC):
        return ControlSurfaceCategory.MEASURED_STATE
    return ControlSurfaceCategory.EXTERNAL_BOUNDARY_CONDITION


def resolve_process_state_tag(process_model: ProcessModel, actuator_tag: str) -> str | None:
    if actuator_tag in process_model.state_metadata_dict:
        return actuator_tag
    if actuator_tag.startswith("(raw,") and ")_" in actuator_tag:
        candidate_state_name = actuator_tag.split(")_", 1)[1]
        if candidate_state_name in process_model.state_metadata_dict:
            return candidate_state_name
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


def validate_controlled_view_has_only_physical_actuators(process_model: ProcessModel) -> None:
    violations: list[str] = []
    for state_name in process_model.controlled_view.state_list:
        category = get_control_surface_category(process_model, state_name)
        if category != ControlSurfaceCategory.PHYSICAL_ACTUATOR:
            violations.append(f"{state_name} ({category.value})")

    if violations:
        raise ControlSurfaceContractError(
            "controller-facing controlled_view.state_list contains non-physical surfaces: "
            + ", ".join(sorted(violations))
        )


def validate_runtime_actuator_binding(process_model: ProcessModel, actuator_tag: str) -> None:
    if "setpoint" in actuator_tag.casefold():
        raise ControlSurfaceContractError(
            f"actuator '{actuator_tag}' is banned by contract: names containing 'setpoint' are not controller-bindable"
        )

    resolved_state_name = resolve_process_state_tag(process_model, actuator_tag)
    if resolved_state_name is None:
        return

    category = get_control_surface_category(process_model, resolved_state_name)
    if category != ControlSurfaceCategory.PHYSICAL_ACTUATOR:
        raise ControlSurfaceContractError(
            f"actuator '{actuator_tag}' is not controller-bindable; classified as {category.value}"
        )

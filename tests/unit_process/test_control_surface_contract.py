from __future__ import annotations

import pytest

from modular_simulation.measurables.control_surface_contract import (
    ControlSurfaceCategory,
    get_control_surface_category,
    validate_controlled_view_has_only_physical_actuators,
    validate_no_banned_setpoint_names,
)
from modular_simulation.measurables.process_model import ProcessModel
from modular_simulation.unit_processes import (
    ComponentSeparator,
    ConversionReactor,
    FlashDrum,
    HeaterCooler,
    PFR,
    ShortcutDistillation,
    Splitter,
    Valve,
)


@pytest.mark.parametrize(
    ("process_model", "state_name", "expected_category"),
    (
        (
            FlashDrum(n_species=2),
            "imposed_pressure",
            ControlSurfaceCategory.EXTERNAL_BOUNDARY_CONDITION,
        ),
        (
            FlashDrum(n_species=2),
            "imposed_temperature",
            ControlSurfaceCategory.EXTERNAL_BOUNDARY_CONDITION,
        ),
        (
            PFR(n_species=2),
            "imposed_jacket_temperature",
            ControlSurfaceCategory.EXTERNAL_BOUNDARY_CONDITION,
        ),
        (
            HeaterCooler(n_species=2),
            "external_heat_duty",
            ControlSurfaceCategory.EXTERNAL_BOUNDARY_CONDITION,
        ),
        (
            HeaterCooler(n_species=2),
            "external_outlet_temperature",
            ControlSurfaceCategory.EXTERNAL_BOUNDARY_CONDITION,
        ),
        (
            ConversionReactor(n_species=2),
            "pressure_drop",
            ControlSurfaceCategory.EXTERNAL_BOUNDARY_CONDITION,
        ),
        (
            Splitter(n_outlets=3, n_species=2),
            "split_ratios",
            ControlSurfaceCategory.CONFIGURED_ABSTRACT_SPECIFICATION,
        ),
        (
            ComponentSeparator(n_species=2),
            "configured_split_fraction_targets",
            ControlSurfaceCategory.CONFIGURED_ABSTRACT_SPECIFICATION,
        ),
        (
            ShortcutDistillation(n_species=2, light_key_index=0, heavy_key_index=1),
            "configured_light_key_distillate_recovery_target",
            ControlSurfaceCategory.CONFIGURED_ABSTRACT_SPECIFICATION,
        ),
        (
            ShortcutDistillation(n_species=2, light_key_index=0, heavy_key_index=1),
            "configured_heavy_key_bottoms_recovery_target",
            ControlSurfaceCategory.CONFIGURED_ABSTRACT_SPECIFICATION,
        ),
        (
            ShortcutDistillation(n_species=2, light_key_index=0, heavy_key_index=1),
            "configured_reflux_ratio_target",
            ControlSurfaceCategory.CONFIGURED_ABSTRACT_SPECIFICATION,
        ),
        (
            ShortcutDistillation(n_species=2, light_key_index=0, heavy_key_index=1),
            "configured_minimum_reflux_ratio_factor",
            ControlSurfaceCategory.CONFIGURED_ABSTRACT_SPECIFICATION,
        ),
    ),
)
def test_control_surface_inventory_classification_matches_seed_audit(
    process_model: ProcessModel,
    state_name: str,
    expected_category: ControlSurfaceCategory,
) -> None:
    assert get_control_surface_category(process_model, state_name) == expected_category


def test_shortcut_distillation_no_longer_exposes_legacy_setpoint_names() -> None:
    column = ShortcutDistillation(n_species=2, light_key_index=0, heavy_key_index=1)

    validate_no_banned_setpoint_names(column)
    assert "reflux_ratio_setpoint" not in column.state_list


def test_shortcut_distillation_no_longer_exposes_configured_specs_in_controlled_view() -> None:
    process_model = ShortcutDistillation(n_species=2, light_key_index=0, heavy_key_index=1)

    validate_controlled_view_has_only_physical_actuators(process_model)
    assert "configured_reflux_ratio_target" not in process_model.controlled_view.state_list
    assert "configured_minimum_reflux_ratio_factor" not in process_model.controlled_view.state_list


def test_component_separator_no_longer_exposes_configured_split_fraction_targets_in_controlled_view() -> (
    None
):
    process_model = ComponentSeparator(n_species=2)

    validate_controlled_view_has_only_physical_actuators(process_model)
    assert "configured_split_fraction_targets" not in process_model.controlled_view.state_list


def test_actuator_contract_accepts_physical_valve_surface() -> None:
    valve = Valve(n_species=2)
    validate_controlled_view_has_only_physical_actuators(valve)


def test_heater_cooler_no_longer_exposes_legacy_setpoint_names() -> None:
    heater = HeaterCooler(n_species=2)

    validate_no_banned_setpoint_names(heater)
    assert "duty_setpoint" not in heater.state_list
    assert "target_temperature_setpoint" not in heater.state_list

from __future__ import annotations

import pytest

from modular_simulation.measurables.control_surface_contract import (
    ControlSurfaceContractError,
    ControlSurfaceCategory,
    get_control_surface_category,
    validate_boundary_view_has_no_physical_actuators,
    validate_no_banned_setpoint_names,
    validate_runtime_actuator_binding,
)
from modular_simulation.measurables.process_model import ProcessModel
from modular_simulation.unit_processes import (
    ComponentSeparator,
    ConversionReactor,
    FlashDrum,
    HeaterCooler,
    Mixer,
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
            ControlSurfaceCategory.CONFIGURED_ABSTRACT_SPECIFICATION,
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


def test_shortcut_distillation_no_longer_exposes_configured_specs_in_boundary_view() -> None:
    process_model = ShortcutDistillation(n_species=2, light_key_index=0, heavy_key_index=1)

    validate_boundary_view_has_no_physical_actuators(process_model)
    assert "configured_reflux_ratio_target" not in process_model.boundary_view.state_list
    assert "configured_minimum_reflux_ratio_factor" not in process_model.boundary_view.state_list


def test_component_separator_no_longer_exposes_configured_split_fraction_targets_in_boundary_view() -> (
    None
):
    process_model = ComponentSeparator(n_species=2)

    validate_boundary_view_has_no_physical_actuators(process_model)
    assert "configured_split_fraction_targets" not in process_model.boundary_view.state_list


@pytest.mark.parametrize(
    ("process_model", "state_name"),
    (
        (Mixer(n_inlets=2, n_species=2), "inlet_flows"),
        (Mixer(n_inlets=2, n_species=2), "inlet_temperatures"),
        (Mixer(n_inlets=2, n_species=2), "inlet_pressures"),
        (Mixer(n_inlets=2, n_species=2), "inlet_compositions"),
        (Splitter(n_outlets=2, n_species=2), "inlet_flow"),
        (Splitter(n_outlets=2, n_species=2), "inlet_temperature"),
        (Splitter(n_outlets=2, n_species=2), "inlet_pressure"),
        (Splitter(n_outlets=2, n_species=2), "inlet_composition"),
        (FlashDrum(n_species=2), "inlet_flow"),
        (FlashDrum(n_species=2), "inlet_temperature"),
        (FlashDrum(n_species=2), "inlet_pressure"),
        (FlashDrum(n_species=2), "inlet_composition"),
        (FlashDrum(n_species=2), "imposed_pressure"),
        (FlashDrum(n_species=2), "imposed_temperature"),
        (ConversionReactor(n_species=2), "inlet_flow"),
        (ConversionReactor(n_species=2), "inlet_temperature"),
        (ConversionReactor(n_species=2), "inlet_pressure"),
        (ConversionReactor(n_species=2), "inlet_composition"),
        (ComponentSeparator(n_species=2), "inlet_flow"),
        (ComponentSeparator(n_species=2), "inlet_temperature"),
        (ComponentSeparator(n_species=2), "inlet_pressure"),
        (ComponentSeparator(n_species=2), "inlet_composition"),
        (ShortcutDistillation(n_species=2, light_key_index=0, heavy_key_index=1), "inlet_flow"),
        (
            ShortcutDistillation(n_species=2, light_key_index=0, heavy_key_index=1),
            "inlet_temperature",
        ),
        (
            ShortcutDistillation(n_species=2, light_key_index=0, heavy_key_index=1),
            "inlet_pressure",
        ),
        (
            ShortcutDistillation(n_species=2, light_key_index=0, heavy_key_index=1),
            "inlet_composition",
        ),
    ),
)
def test_non_thermal_unit_inlet_like_surfaces_live_in_boundary_view(
    process_model: ProcessModel,
    state_name: str,
) -> None:
    assert state_name in process_model.boundary_view.state_list
    assert state_name not in process_model.constant_view.state_list


def test_boundary_contract_excludes_physical_valve_surface() -> None:
    valve = Valve(n_species=2)

    validate_boundary_view_has_no_physical_actuators(valve)


def test_heater_cooler_no_longer_exposes_legacy_setpoint_names() -> None:
    heater = HeaterCooler(n_species=2)

    validate_no_banned_setpoint_names(heater)
    assert "duty_setpoint" not in heater.state_list
    assert "target_temperature_setpoint" not in heater.state_list


@pytest.mark.parametrize(
    "actuator_tag",
    ("heater_power", "imposed_pressure", "(raw, CONTROLLED)_heater_power"),
)
def test_runtime_contract_rejects_non_namespaced_actuator_tags(actuator_tag: str) -> None:
    process_model = HeaterCooler(n_species=2)

    with pytest.raises(
        ControlSurfaceContractError,
        match="is not controller-bindable; expected actuator namespace tag 'actuator/<family>/<id>'",
    ):
        validate_runtime_actuator_binding(process_model, actuator_tag)

from __future__ import annotations

from importlib import import_module
from typing import Any


EXPECTED_ITEM_IDS = frozenset(
    {
        "place_heater_cooler",
        "place_flash_drum",
        "place_heat_exchanger",
        "place_component_separator",
        "place_merge_junction_2x1",
        "place_split_junction_1x2",
        "build_process_line",
        "install_line_pump",
        "install_line_valve",
        "install_line_heat_actuator",
        "install_sampled_delayed_sensor",
        "install_pid_controller",
    }
)


EXPECTED_CATALOG = {
    "place_heater_cooler": {
        "title": "Heater/cooler unit",
        "item_kind": "unit_blueprint",
        "apply_kind": "add_process",
        "default_config": {
            "unit_type": "HeaterCooler",
            "unit_module": "modular_simulation.unit_processes.thermal.heater_cooler",
            "constructor_payload": {
                "mode": "temperature",
                "external_outlet_temperature": 325.0,
                "pressure_drop": 0.0,
            },
        },
        "required_user_inputs": ("process_id",),
        "supported_start_ids": (
            "phase1_process_sandbox_v1",
            "heater_flash_tutorial_start_v1",
        ),
        "educational_summary": (
            "single-inlet single-outlet heater/cooler with explicit outlet-temperature boundary"
        ),
    },
    "place_flash_drum": {
        "title": "Flash drum unit",
        "item_kind": "unit_blueprint",
        "apply_kind": "add_process",
        "default_config": {
            "unit_type": "FlashDrum",
            "unit_module": "modular_simulation.unit_processes.separation.flash_drum",
            "constructor_payload": {
                "thermal_mode": "isothermal",
                "imposed_pressure": 101325.0,
                "imposed_temperature": 320.0,
            },
        },
        "required_user_inputs": ("process_id",),
        "supported_start_ids": (
            "phase1_process_sandbox_v1",
            "heater_flash_tutorial_start_v1",
        ),
        "educational_summary": (
            "two-product flash separator with explicit imposed pressure and temperature boundaries"
        ),
    },
    "place_heat_exchanger": {
        "title": "Heat exchanger unit",
        "item_kind": "unit_blueprint",
        "apply_kind": "add_process",
        "default_config": {
            "unit_type": "HeatExchanger",
            "unit_module": "modular_simulation.unit_processes.thermal.heat_exchanger",
            "constructor_payload": {
                "flow_arrangement": "counter",
                "ua": 7500.0,
            },
        },
        "required_user_inputs": ("process_id",),
        "supported_start_ids": ("phase1_process_sandbox_v1",),
        "educational_summary": "counter-current dual-stream heat exchanger with explicit UA parameter",
    },
    "place_component_separator": {
        "title": "Component separator unit",
        "item_kind": "unit_blueprint",
        "apply_kind": "add_process",
        "default_config": {
            "unit_type": "ComponentSeparator",
            "unit_module": "modular_simulation.unit_processes.separation.component_separator",
            "constructor_payload": {"configured_split_fraction_targets": {"mode": "equal_split"}},
        },
        "required_user_inputs": ("process_id",),
        "supported_start_ids": ("phase1_process_sandbox_v1",),
        "educational_summary": (
            "abstract split-fraction separator for material-balance and recovery tradeoff teaching"
        ),
    },
    "place_merge_junction_2x1": {
        "title": "Merge junction (2x1)",
        "item_kind": "junction_blueprint",
        "apply_kind": "add_junction",
        "default_config": {
            "inlet_ports": ("feed_a", "feed_b"),
            "outlet_ports": ("out",),
        },
        "required_user_inputs": ("junction_id",),
        "supported_start_ids": ("phase1_process_sandbox_v1",),
        "educational_summary": (
            "explicit two-inlet merge junction using the canonical junction topology model"
        ),
    },
    "place_split_junction_1x2": {
        "title": "Split junction (1x2)",
        "item_kind": "junction_blueprint",
        "apply_kind": "add_junction",
        "default_config": {
            "inlet_ports": ("in",),
            "outlet_ports": ("product", "recycle"),
        },
        "required_user_inputs": ("junction_id",),
        "supported_start_ids": ("phase1_process_sandbox_v1",),
        "educational_summary": (
            "explicit one-inlet split junction with named product and recycle branches"
        ),
    },
    "build_process_line": {
        "title": "Process line",
        "item_kind": "line",
        "apply_kind": "connect_configure_line",
        "default_config": {
            "radius_m": 0.05,
            "length_m": 1.0,
        },
        "required_user_inputs": ("source", "target"),
        "supported_start_ids": (
            "phase1_process_sandbox_v1",
            "heater_flash_tutorial_start_v1",
        ),
        "educational_summary": (
            "explicit process line with geometry-owned pressure-loss implications"
        ),
    },
    "install_line_pump": {
        "title": "Line pump overlay",
        "item_kind": "line_overlay",
        "apply_kind": "attach_line_pump",
        "default_config": {
            "initial_pump_speed": 80000.0,
        },
        "required_user_inputs": ("line_id", "pump_id"),
        "supported_start_ids": (
            "phase1_process_sandbox_v1",
            "recycle_purge_tutorial_start_v1",
        ),
        "educational_summary": (
            "line-owned hydraulic boost overlay, not a stand-alone unit family"
        ),
    },
    "install_line_valve": {
        "title": "Line valve overlay",
        "item_kind": "line_overlay",
        "apply_kind": "attach_line_valve",
        "default_config": {
            "minimum_open_fraction": 0.0,
            "maximum_open_fraction": 1.0,
            "initial_open_fraction": 1.0,
        },
        "required_user_inputs": ("line_id", "valve_id"),
        "supported_start_ids": (
            "phase1_process_sandbox_v1",
            "recycle_purge_tutorial_start_v1",
        ),
        "educational_summary": (
            "line-owned throttling valve using the existing runtime/control surface"
        ),
    },
    "install_line_heat_actuator": {
        "title": "Line heat-actuator overlay",
        "item_kind": "line_overlay",
        "apply_kind": "attach_line_heat_actuator",
        "default_config": {
            "initial_heat_rate": 0.0,
        },
        "required_user_inputs": ("line_id", "heat_actuator_id"),
        "supported_start_ids": ("phase1_process_sandbox_v1",),
        "educational_summary": (
            "line-owned heat actuator overlay using the explicit heat-actuator substrate"
        ),
    },
    "install_sampled_delayed_sensor": {
        "title": "Sampled delayed sensor",
        "item_kind": "sensor",
        "apply_kind": "create_bind_sensor",
        "default_config": {
            "sensor_type": "SampledDelayedSensor",
            "sensor_module": "modular_simulation.components.sensors.sampled_delayed_sensor",
            "sensor_config": {
                "sampling_period": 0.2,
                "deadtime": 0.0,
            },
        },
        "required_user_inputs": ("sensor_id", "signal_key"),
        "supported_start_ids": (
            "phase1_process_sandbox_v1",
            "reactor_control_tutorial_start_v1",
        ),
        "educational_summary": (
            "sampled and delayed measurement point for instrumentation tutorials and controller feedback"
        ),
    },
    "install_pid_controller": {
        "title": "PID controller",
        "item_kind": "controller",
        "apply_kind": "create_bind_activate_controller",
        "default_config": {
            "controller_type": "PIDController",
            "controller_module": "modular_simulation.components.control_system.controllers",
            "controller_config": {
                "Kp": 1.0,
                "Ti": 5.0,
                "Td": 0.0,
            },
        },
        "required_user_inputs": ("controller_id", "signal_key", "actuator_tag"),
        "supported_start_ids": (
            "phase1_process_sandbox_v1",
            "reactor_control_tutorial_start_v1",
        ),
        "educational_summary": (
            "standard PID controller bound through the existing runtime wiring APIs"
        ),
    },
}


def _build_sandbox_catalog() -> dict[str, Any]:
    """Load the sandbox catalog via any callable that returns a dict keyed by item_id.

    The implementation may name its builder function however it likes; we locate
    it by looking for the first public callable in the module that accepts no
    positional arguments and returns a dict.
    """
    module = import_module("modular_simulation.gameplay.sandbox_catalog")
    for candidate_name in dir(module):
        if candidate_name.startswith("_"):
            continue
        candidate = getattr(module, candidate_name)
        if callable(candidate):
            try:
                result = candidate()
            except TypeError:
                continue
            if isinstance(result, dict):
                return result
    raise RuntimeError(
        "modular_simulation.gameplay.sandbox_catalog exposes no public callable that returns a dict"
    )


def test_sandbox_catalog_contains_exactly_the_frozen_item_ids() -> None:
    catalog = _build_sandbox_catalog()
    assert set(catalog) == EXPECTED_ITEM_IDS


def test_each_catalog_item_matches_the_frozen_record() -> None:
    catalog = _build_sandbox_catalog()
    for item_id, expected in EXPECTED_CATALOG.items():
        item = catalog[item_id]
        assert item.title == expected["title"]
        assert item.item_kind == expected["item_kind"]
        assert item.apply_kind == expected["apply_kind"]
        assert item.default_config == expected["default_config"]
        assert item.required_user_inputs == expected["required_user_inputs"]
        assert item.supported_start_ids == expected["supported_start_ids"]
        assert item.educational_summary == expected["educational_summary"]


def test_catalog_boundaries_exclude_out_of_scope_mechanics() -> None:
    catalog = _build_sandbox_catalog()
    forbidden_tokens = (
        "stand-alone pump",
        "standalone pump",
        "stand-alone valve",
        "standalone valve",
        "arbitrary process factory",
        "tutorial-only mechanic",
    )
    for item in catalog.values():
        blob = " ".join(
            [
                item.item_id,
                item.title,
                item.item_kind,
                item.apply_kind,
                item.educational_summary,
            ]
        ).lower()
        for forbidden in forbidden_tokens:
            assert forbidden not in blob

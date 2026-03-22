from __future__ import annotations

from importlib import import_module
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


EXPECTED_STARTS = {
    "phase1_process_sandbox_v1": {
        "starting_topology_summary": "Two named feeds and two named sinks with no units, junctions, or line overlays preinstalled.",
        "published_signal_ids": (
            "feed_a_draw_mol_s",
            "feed_b_draw_mol_s",
            "product_a_flow_mol_s",
            "product_b_flow_mol_s",
            "heating_steam_duty_W",
            "total_normalized_pump_load",
        ),
        "learner_scaffold": {
            "named_feed_ids": ("feed_a", "feed_b"),
            "named_sink_ids": ("product_a", "product_b"),
            "preinstalled_unit_ids": (),
            "preinstalled_junction_ids": (),
            "preinstalled_line_ids": (),
            "preinstalled_pump_ids": (),
            "preinstalled_valve_ids": (),
            "preinstalled_sensor_ids": (),
            "preinstalled_controller_ids": (),
            "preinstalled_heat_actuator_ids": (),
        },
    },
    "heater_flash_tutorial_start_v1": {
        "starting_topology_summary": "One named feed and two named product sinks with no heater, flash drum, or connecting lines preinstalled.",
        "published_signal_ids": (
            "feed_draw_mol_s",
            "vapor_product_flow_mol_s",
            "liquid_product_flow_mol_s",
            "heating_steam_duty_W",
        ),
        "learner_scaffold": {
            "named_feed_ids": ("feed",),
            "named_sink_ids": ("vapor_product", "liquid_product"),
            "preinstalled_unit_ids": (),
            "preinstalled_junction_ids": (),
            "preinstalled_line_ids": (),
            "preinstalled_pump_ids": (),
            "preinstalled_valve_ids": (),
            "preinstalled_sensor_ids": (),
            "preinstalled_controller_ids": (),
            "preinstalled_heat_actuator_ids": (),
        },
    },
    "reactor_control_tutorial_start_v1": {
        "starting_topology_summary": "Van de Vusse reactor scaffold is preloaded, but reference sensors and controllers are intentionally absent for learner-installed instrumentation.",
        "published_signal_ids": (
            "reactor_temperature_K",
            "product_b_concentration_mol_l",
            "cooling_water_duty_W",
        ),
        "learner_scaffold": {
            "named_feed_ids": (),
            "named_sink_ids": (),
            "preinstalled_unit_ids": ("van_de_vusse_reactor_scaffold",),
            "preinstalled_junction_ids": (),
            "preinstalled_line_ids": (),
            "preinstalled_pump_ids": (),
            "preinstalled_valve_ids": (),
            "preinstalled_sensor_ids": (),
            "preinstalled_controller_ids": (),
            "preinstalled_heat_actuator_ids": (),
        },
    },
    "recycle_purge_tutorial_start_v1": {
        "starting_topology_summary": "Recycle scaffold includes named recycle and purge lines, but leaves purge throttling and recycle pumping to the learner.",
        "published_signal_ids": (
            "fresh_feed_draw_mol_s",
            "liquid_product_flow_mol_s",
            "purge_loss_flow_mol_s",
            "total_normalized_pump_load",
        ),
        "learner_scaffold": {
            "named_feed_ids": (),
            "named_sink_ids": (),
            "preinstalled_unit_ids": (),
            "preinstalled_junction_ids": (),
            "preinstalled_line_ids": ("recycle_line", "purge_line"),
            "preinstalled_pump_ids": (),
            "preinstalled_valve_ids": (),
            "preinstalled_sensor_ids": (),
            "preinstalled_controller_ids": (),
            "preinstalled_heat_actuator_ids": (),
        },
    },
}


def _instantiate_start(start_id: str) -> Any:
    """Instantiate a start by id via whatever callable the starts module exposes.

    The implementation may name its entry-point however it likes; we look for
    a public callable that accepts a ``start_id`` keyword argument.
    """
    module = import_module("modular_simulation.gameplay.starts")
    for candidate_name in dir(module):
        if candidate_name.startswith("_"):
            continue
        candidate = getattr(module, candidate_name)
        if callable(candidate):
            try:
                result = candidate(start_id=start_id)
                return result
            except TypeError:
                continue
    raise RuntimeError(
        "modular_simulation.gameplay.starts exposes no public callable that accepts start_id="
    )


def _extract_seed_instances_by_path(start_instance: Any) -> dict[str, Any]:
    seed_paths = set(start_instance.seed_source_paths)
    for candidate_name in dir(start_instance):
        if candidate_name.startswith("_"):
            continue
        candidate = getattr(start_instance, candidate_name)
        if not isinstance(candidate, dict):
            continue
        if set(candidate.keys()) != seed_paths:
            continue
        if any(value is None for value in candidate.values()):
            continue
        return candidate
    raise AssertionError(
        "start instance exposes no public seed-instance mapping keyed by seed_source_paths"
    )


def _assert_heater_flash_seed(seed_instance: Any) -> None:
    assert "heater" in seed_instance._units
    assert "flash" in seed_instance._units
    assert "feed" in seed_instance._feeds
    assert "vapor_product" in seed_instance._sinks
    assert "liquid_product" in seed_instance._sinks


def _assert_dual_feed_seed(seed_instance: Any) -> None:
    assert "hot_trim" in seed_instance._units
    assert "cold_trim" in seed_instance._units
    assert "exchanger" in seed_instance._units
    assert "hot_feed" in seed_instance._feeds
    assert "cold_feed" in seed_instance._feeds


def _assert_ammonia_recycle_seed(seed_instance: Any) -> None:
    assert "synthesis_mixer" in seed_instance._junctions
    assert "purge_split" in seed_instance._junctions
    assert "fresh_syngas" in seed_instance._feeds
    assert "recycle_line" in seed_instance._line_ids
    assert "recycle_pump" in seed_instance._pump_ids


def _assert_reactor_component_seed(seed_instance: Any) -> None:
    assert len(seed_instance["sensors"]) >= 1
    assert len(seed_instance["calculations"]) >= 1
    assert len(seed_instance["control_elements"]) >= 1


def _assert_reactor_runtime_seed(seed_instance: Any) -> None:
    assert set(seed_instance) == {"normal"}
    assert seed_instance["normal"].process_model.__class__.__name__ == "VanDeVusseProcessModel"


def _assert_learner_scaffold(instance: Any, expected: dict[str, Any]) -> None:
    scaffold = instance.learner_start_scaffold
    assert scaffold.named_feed_ids == expected["named_feed_ids"]
    assert scaffold.named_sink_ids == expected["named_sink_ids"]
    assert scaffold.preinstalled_unit_ids == expected["preinstalled_unit_ids"]
    assert scaffold.preinstalled_junction_ids == expected["preinstalled_junction_ids"]
    assert scaffold.preinstalled_line_ids == expected["preinstalled_line_ids"]
    assert scaffold.preinstalled_pump_ids == expected["preinstalled_pump_ids"]
    assert scaffold.preinstalled_valve_ids == expected["preinstalled_valve_ids"]
    assert scaffold.preinstalled_sensor_ids == expected["preinstalled_sensor_ids"]
    assert scaffold.preinstalled_controller_ids == expected["preinstalled_controller_ids"]
    assert scaffold.preinstalled_heat_actuator_ids == expected["preinstalled_heat_actuator_ids"]


def test_sandbox_and_tutorial_starts_can_each_instantiate_once_with_frozen_contracts() -> None:
    for start_id, expected in EXPECTED_STARTS.items():
        instance = _instantiate_start(start_id)
        assert instance.start_id == start_id
        assert instance.starting_topology_summary == expected["starting_topology_summary"]
        assert instance.published_signal_ids == expected["published_signal_ids"]
        _assert_learner_scaffold(instance, expected["learner_scaffold"])

        seed_instances = _extract_seed_instances_by_path(instance)
        if start_id == "phase1_process_sandbox_v1":
            _assert_heater_flash_seed(
                seed_instances["examples/unit_process_flowsheet/easy_2_heater_flash.py"]
            )
            _assert_dual_feed_seed(
                seed_instances["examples/unit_process_flowsheet/easy_3_dual_feed_heat_exchanger.py"]
            )
        elif start_id == "heater_flash_tutorial_start_v1":
            _assert_heater_flash_seed(
                seed_instances["examples/unit_process_flowsheet/easy_2_heater_flash.py"]
            )
        elif start_id == "reactor_control_tutorial_start_v1":
            assert (
                seed_instances[
                    "examples/van_de_vusse_cstr/process_definition.py"
                ].__class__.__name__
                == "VanDeVusseProcessModel"
            )
            _assert_reactor_component_seed(
                seed_instances["examples/van_de_vusse_cstr/component_definition.py"]
            )
            _assert_reactor_runtime_seed(
                seed_instances["examples/van_de_vusse_cstr/run_simulation.py"]
            )
        elif start_id == "recycle_purge_tutorial_start_v1":
            _assert_ammonia_recycle_seed(
                seed_instances["examples/unit_process_flowsheet/complex_6_ammonia_recycle_loop.py"]
            )

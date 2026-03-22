from __future__ import annotations

from importlib import import_module
from pathlib import Path
import sys
from typing import Any
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


EXPECTED_START_IDS = (
    "phase1_process_sandbox_v1",
    "heater_flash_tutorial_start_v1",
    "reactor_control_tutorial_start_v1",
    "recycle_purge_tutorial_start_v1",
)

EXPECTED_PUBLISHED_SIGNALS = {
    "phase1_process_sandbox_v1": (
        "feed_a_draw_mol_s",
        "feed_b_draw_mol_s",
        "product_a_flow_mol_s",
        "product_b_flow_mol_s",
        "heating_steam_duty_W",
        "total_normalized_pump_load",
    ),
    "heater_flash_tutorial_start_v1": (
        "feed_draw_mol_s",
        "vapor_product_flow_mol_s",
        "liquid_product_flow_mol_s",
        "heating_steam_duty_W",
    ),
    "reactor_control_tutorial_start_v1": (
        "reactor_temperature_K",
        "product_b_concentration_mol_l",
        "cooling_water_duty_W",
    ),
    "recycle_purge_tutorial_start_v1": (
        "fresh_feed_draw_mol_s",
        "liquid_product_flow_mol_s",
        "purge_loss_flow_mol_s",
        "total_normalized_pump_load",
    ),
}

EXPECTED_LEARNER_SCAFFOLDS = {
    "phase1_process_sandbox_v1": {
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
    "heater_flash_tutorial_start_v1": {
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
    "reactor_control_tutorial_start_v1": {
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
    "recycle_purge_tutorial_start_v1": {
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
}


def _build_start_catalog() -> dict[str, Any]:
    """Load the start catalog via any public no-arg callable that returns a dict."""
    module = import_module("modular_simulation.gameplay.start_catalog")
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
        "modular_simulation.gameplay.start_catalog exposes no public callable that returns a dict"
    )


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


def test_each_frozen_start_builder_returns_exact_metadata_contract() -> None:
    catalog = _build_start_catalog()
    for start_id in EXPECTED_START_IDS:
        built_start = _instantiate_start(start_id)
        assert built_start.start_id == start_id
        assert built_start.start_kind == catalog[start_id].start_kind
        assert built_start.title == catalog[start_id].title
        assert built_start.seed_source_paths == catalog[start_id].seed_source_paths
        assert built_start.starting_topology_summary == catalog[start_id].starting_topology_summary
        assert built_start.allowed_item_ids == catalog[start_id].allowed_item_ids


def test_builders_publish_exact_frozen_signal_ids_per_start() -> None:
    for start_id, expected_signal_ids in EXPECTED_PUBLISHED_SIGNALS.items():
        built_start = _instantiate_start(start_id)
        assert built_start.published_signal_ids == expected_signal_ids


def test_builders_expose_learner_facing_scaffold_not_raw_example_state() -> None:
    for start_id, expected_scaffold in EXPECTED_LEARNER_SCAFFOLDS.items():
        built_start = _instantiate_start(start_id)
        scaffold = built_start.learner_start_scaffold
        assert scaffold.named_feed_ids == expected_scaffold["named_feed_ids"]
        assert scaffold.named_sink_ids == expected_scaffold["named_sink_ids"]
        assert scaffold.preinstalled_unit_ids == expected_scaffold["preinstalled_unit_ids"]
        assert scaffold.preinstalled_junction_ids == expected_scaffold["preinstalled_junction_ids"]
        assert scaffold.preinstalled_line_ids == expected_scaffold["preinstalled_line_ids"]
        assert scaffold.preinstalled_pump_ids == expected_scaffold["preinstalled_pump_ids"]
        assert scaffold.preinstalled_valve_ids == expected_scaffold["preinstalled_valve_ids"]
        assert scaffold.preinstalled_sensor_ids == expected_scaffold["preinstalled_sensor_ids"]
        assert (
            scaffold.preinstalled_controller_ids == expected_scaffold["preinstalled_controller_ids"]
        )
        assert (
            scaffold.preinstalled_heat_actuator_ids
            == expected_scaffold["preinstalled_heat_actuator_ids"]
        )


def test_start_builders_are_seed_backed_not_metadata_echo_only() -> None:
    catalog = _build_start_catalog()

    with patch(
        "examples.unit_process_flowsheet.easy_2_heater_flash.run_example",
        side_effect=AssertionError("start builders must not execute seed run_example"),
    ):
        with patch(
            "examples.unit_process_flowsheet.easy_3_dual_feed_heat_exchanger.run_example",
            side_effect=AssertionError("start builders must not execute seed run_example"),
        ):
            with patch(
                "examples.unit_process_flowsheet.complex_6_ammonia_recycle_loop.run_example",
                side_effect=AssertionError("start builders must not execute seed run_example"),
            ):
                with patch(
                    "examples.van_de_vusse_cstr.run_simulation.run_demo",
                    side_effect=AssertionError("start builders must not execute seed run_demo"),
                ):
                    for start_id in EXPECTED_START_IDS:
                        built_start = _instantiate_start(start_id)
                        assert built_start is not catalog[start_id]
                        seed_instances = _extract_seed_instances_by_path(built_start)
                        assert set(seed_instances) == set(catalog[start_id].seed_source_paths)
                        for path, seed_instance in seed_instances.items():
                            assert path in catalog[start_id].seed_source_paths
                            assert seed_instance is not None


def test_start_builders_do_not_shell_out_to_example_scripts() -> None:
    with patch("subprocess.run", side_effect=AssertionError("unexpected shell call")):
        with patch("subprocess.Popen", side_effect=AssertionError("unexpected shell call")):
            for start_id in EXPECTED_START_IDS:
                _instantiate_start(start_id)


def test_start_builder_surface_rejects_unpublished_start_ids() -> None:
    with patch("subprocess.run", side_effect=AssertionError("unexpected shell call")):
        module = import_module("modular_simulation.gameplay.starts")
        # Find the entry-point callable: it must accept start_id= and raise KeyError
        # (not TypeError) for an unknown id.  A callable that raises TypeError does
        # not accept start_id= and therefore does not qualify.
        instantiate = None
        for candidate_name in dir(module):
            if candidate_name.startswith("_"):
                continue
            candidate = getattr(module, candidate_name)
            if not callable(candidate):
                continue
            try:
                candidate(start_id="__probe_unknown__")
            except KeyError:
                # Accepts start_id= and correctly rejects unknown ids — this is our target.
                instantiate = candidate
                break
            except TypeError:
                # Does not accept start_id= — not a qualifying entry point.
                continue
            # If it returned without raising, it accepted an unknown id — not a valid
            # rejection guard; keep searching.
        if instantiate is None:
            raise AssertionError(
                "modular_simulation.gameplay.starts exposes no public callable"
                " that accepts start_id= and raises KeyError for unknown ids"
            )
        # At this point we have confirmed instantiate raises KeyError for unknown ids.
        # Verify the error message references the unknown id.
        try:
            instantiate(start_id="unknown_start_id")
        except KeyError as error:
            assert "unknown_start_id" in str(error)
        else:
            raise AssertionError("expected KeyError for unpublished start id")

"""Seed-backed builders for phase-1 gameplay starts."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Any

from modular_simulation.gameplay.contracts import PlayStartDefinition
from modular_simulation.gameplay.start_catalog import build_start_catalog


@dataclass(frozen=True)
class LearnerStartScaffold:
    named_feed_ids: tuple[str, ...]
    named_sink_ids: tuple[str, ...]
    preinstalled_unit_ids: tuple[str, ...]
    preinstalled_junction_ids: tuple[str, ...]
    preinstalled_line_ids: tuple[str, ...]
    preinstalled_pump_ids: tuple[str, ...]
    preinstalled_valve_ids: tuple[str, ...]
    preinstalled_sensor_ids: tuple[str, ...]
    preinstalled_controller_ids: tuple[str, ...]
    preinstalled_heat_actuator_ids: tuple[str, ...]


@dataclass(frozen=True)
class SeedBackedStart:
    start_id: str
    start_kind: str
    title: str
    seed_source_paths: tuple[str, ...]
    starting_topology_summary: str
    published_signal_ids: tuple[str, ...]
    allowed_item_ids: tuple[str, ...]
    learner_start_scaffold: LearnerStartScaffold
    seed_instances_by_path: dict[str, object]


LEARNER_START_SCAFFOLDS: dict[str, LearnerStartScaffold] = {
    "phase1_process_sandbox_v1": LearnerStartScaffold(
        named_feed_ids=("sweet_wet_gas",),
        named_sink_ids=(
            "separator_gas",
            "unstabilized_condensate",
            "dry_gas",
            "ngl_liquids",
            "stabilized_condensate",
        ),
        preinstalled_unit_ids=(),
        preinstalled_junction_ids=(),
        preinstalled_line_ids=(),
        preinstalled_pump_ids=(),
        preinstalled_valve_ids=(),
        preinstalled_sensor_ids=(),
        preinstalled_controller_ids=(),
        preinstalled_heat_actuator_ids=(),
    ),
    "heater_flash_tutorial_start_v1": LearnerStartScaffold(
        named_feed_ids=("feed",),
        named_sink_ids=("vapor_product", "liquid_product"),
        preinstalled_unit_ids=(),
        preinstalled_junction_ids=(),
        preinstalled_line_ids=(),
        preinstalled_pump_ids=(),
        preinstalled_valve_ids=(),
        preinstalled_sensor_ids=(),
        preinstalled_controller_ids=(),
        preinstalled_heat_actuator_ids=(),
    ),
    "reactor_control_tutorial_start_v1": LearnerStartScaffold(
        named_feed_ids=(),
        named_sink_ids=(),
        preinstalled_unit_ids=("van_de_vusse_reactor_scaffold",),
        preinstalled_junction_ids=(),
        preinstalled_line_ids=(),
        preinstalled_pump_ids=(),
        preinstalled_valve_ids=(),
        preinstalled_sensor_ids=(),
        preinstalled_controller_ids=(),
        preinstalled_heat_actuator_ids=(),
    ),
    "recycle_purge_tutorial_start_v1": LearnerStartScaffold(
        named_feed_ids=(),
        named_sink_ids=(),
        preinstalled_unit_ids=(),
        preinstalled_junction_ids=(),
        preinstalled_line_ids=("recycle_line", "purge_line"),
        preinstalled_pump_ids=(),
        preinstalled_valve_ids=(),
        preinstalled_sensor_ids=(),
        preinstalled_controller_ids=(),
        preinstalled_heat_actuator_ids=(),
    ),
}


def _catalog_entry(start_id: str) -> PlayStartDefinition:
    catalog = build_start_catalog()
    try:
        return catalog[start_id]
    except KeyError as error:
        raise KeyError(f"Unknown start_id: {start_id!r}") from error


def _build_from_metadata(
    definition: PlayStartDefinition, *, seed_instances_by_path: dict[str, object]
) -> SeedBackedStart:
    if set(seed_instances_by_path) != set(definition.seed_source_paths):
        raise ValueError(
            f"seed instance mapping keys must exactly match seed_source_paths for {definition.start_id}"
        )
    return SeedBackedStart(
        start_id=definition.start_id,
        start_kind=definition.start_kind,
        title=definition.title,
        seed_source_paths=definition.seed_source_paths,
        starting_topology_summary=definition.starting_topology_summary,
        published_signal_ids=definition.published_signal_ids,
        allowed_item_ids=definition.allowed_item_ids,
        learner_start_scaffold=LEARNER_START_SCAFFOLDS[definition.start_id],
        seed_instances_by_path=seed_instances_by_path,
    )


def _build_phase1_process_sandbox() -> SeedBackedStart:
    definition = _catalog_entry("phase1_process_sandbox_v1")
    gas_1_module = import_module("examples.unit_process_flowsheet.gas_1_inlet_separator")
    gas_2_module = import_module("examples.unit_process_flowsheet.gas_2_teg_dehydration")
    gas_3_module = import_module(
        "examples.unit_process_flowsheet.gas_3_jt_low_temperature_separation"
    )
    gas_4_module = import_module("examples.unit_process_flowsheet.gas_4_condensate_stabilizer")
    seed_instances_by_path = {
        "examples/unit_process_flowsheet/gas_1_inlet_separator.py": gas_1_module.build_example_flowsheet(
            dt=0.2
        ),
        "examples/unit_process_flowsheet/gas_2_teg_dehydration.py": gas_2_module.build_example_flowsheet(
            dt=0.2
        ),
        "examples/unit_process_flowsheet/gas_3_jt_low_temperature_separation.py": gas_3_module.build_example_flowsheet(
            dt=0.2
        ),
        "examples/unit_process_flowsheet/gas_4_condensate_stabilizer.py": gas_4_module.build_example_flowsheet(
            dt=0.2
        ),
    }
    return _build_from_metadata(definition, seed_instances_by_path=seed_instances_by_path)


def _build_heater_flash_tutorial_start() -> SeedBackedStart:
    definition = _catalog_entry("heater_flash_tutorial_start_v1")
    heater_flash_module = import_module("examples.unit_process_flowsheet.easy_2_heater_flash")
    seed_instances_by_path = {
        "examples/unit_process_flowsheet/easy_2_heater_flash.py": heater_flash_module.build_example_flowsheet(
            dt=0.2
        ),
    }
    return _build_from_metadata(definition, seed_instances_by_path=seed_instances_by_path)


def _build_reactor_control_tutorial_start() -> SeedBackedStart:
    definition = _catalog_entry("reactor_control_tutorial_start_v1")
    process_module = import_module("examples.van_de_vusse_cstr.process_definition")
    component_module = import_module("examples.van_de_vusse_cstr.component_definition")
    run_module = import_module("examples.van_de_vusse_cstr.run_simulation")
    seed_instances_by_path = {
        "examples/van_de_vusse_cstr/process_definition.py": process_module.VanDeVusseProcessModel(),
        "examples/van_de_vusse_cstr/component_definition.py": {
            "sensors": tuple(component_module.sensors),
            "calculations": tuple(component_module.calculations),
            "control_elements": tuple(component_module.control_elements),
        },
        "examples/van_de_vusse_cstr/run_simulation.py": run_module.make_systems(
            record_history=False
        ),
    }
    return _build_from_metadata(definition, seed_instances_by_path=seed_instances_by_path)


def _build_recycle_purge_tutorial_start() -> SeedBackedStart:
    definition = _catalog_entry("recycle_purge_tutorial_start_v1")
    ammonia_module = import_module("examples.unit_process_flowsheet.complex_6_ammonia_recycle_loop")
    seed_instances_by_path = {
        "examples/unit_process_flowsheet/complex_6_ammonia_recycle_loop.py": ammonia_module._build_flowsheet(
            dt=0.2
        ),
    }
    return _build_from_metadata(definition, seed_instances_by_path=seed_instances_by_path)


def build_seed_backed_start(*, start_id: str) -> SeedBackedStart:
    builders: dict[str, Any] = {
        "phase1_process_sandbox_v1": _build_phase1_process_sandbox,
        "heater_flash_tutorial_start_v1": _build_heater_flash_tutorial_start,
        "reactor_control_tutorial_start_v1": _build_reactor_control_tutorial_start,
        "recycle_purge_tutorial_start_v1": _build_recycle_purge_tutorial_start,
    }
    builder = builders.get(start_id)
    if builder is None:
        raise KeyError(f"Unknown start_id: {start_id!r}")
    return builder()

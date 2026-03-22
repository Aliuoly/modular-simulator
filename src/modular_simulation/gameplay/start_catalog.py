"""Phase-1 play-start catalog.

Returns a dict keyed by start_id containing PlayStartDefinition records.
"""

from __future__ import annotations

from modular_simulation.gameplay.contracts import PlayStartDefinition


def build_start_catalog() -> dict[str, PlayStartDefinition]:
    """Return the frozen phase-1 start catalog."""
    entries = [
        PlayStartDefinition(
            start_id="phase1_process_sandbox_v1",
            start_kind="sandbox",
            title="Phase-1 process sandbox",
            seed_source_paths=(
                "examples/unit_process_flowsheet/easy_2_heater_flash.py",
                "examples/unit_process_flowsheet/easy_3_dual_feed_heat_exchanger.py",
            ),
            starting_topology_summary=(
                "Two named feeds and two named sinks with no units, junctions, or line overlays preinstalled."
            ),
            published_signal_ids=(
                "feed_a_draw_mol_s",
                "feed_b_draw_mol_s",
                "product_a_flow_mol_s",
                "product_b_flow_mol_s",
                "heating_steam_duty_W",
                "total_normalized_pump_load",
            ),
            allowed_item_ids=(
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
            ),
        ),
        PlayStartDefinition(
            start_id="heater_flash_tutorial_start_v1",
            start_kind="tutorial_start",
            title="Heater/flash tutorial start",
            seed_source_paths=("examples/unit_process_flowsheet/easy_2_heater_flash.py",),
            starting_topology_summary=(
                "One named feed and two named product sinks with no heater, flash drum, or connecting lines preinstalled."
            ),
            published_signal_ids=(
                "feed_draw_mol_s",
                "vapor_product_flow_mol_s",
                "liquid_product_flow_mol_s",
                "heating_steam_duty_W",
            ),
            allowed_item_ids=(
                "place_heater_cooler",
                "place_flash_drum",
                "build_process_line",
            ),
        ),
        PlayStartDefinition(
            start_id="reactor_control_tutorial_start_v1",
            start_kind="tutorial_start",
            title="Reactor control tutorial start",
            seed_source_paths=(
                "examples/van_de_vusse_cstr/process_definition.py",
                "examples/van_de_vusse_cstr/component_definition.py",
                "examples/van_de_vusse_cstr/run_simulation.py",
            ),
            starting_topology_summary=(
                "Van de Vusse reactor scaffold is preloaded, but reference sensors and controllers are intentionally absent for learner-installed instrumentation."
            ),
            published_signal_ids=(
                "reactor_temperature_K",
                "product_b_concentration_mol_l",
                "cooling_water_duty_W",
            ),
            allowed_item_ids=(
                "install_sampled_delayed_sensor",
                "install_pid_controller",
            ),
        ),
        PlayStartDefinition(
            start_id="recycle_purge_tutorial_start_v1",
            start_kind="tutorial_start",
            title="Recycle/purge tutorial start",
            seed_source_paths=(
                "examples/unit_process_flowsheet/complex_6_ammonia_recycle_loop.py",
            ),
            starting_topology_summary=(
                "Recycle scaffold includes named recycle and purge lines, but leaves purge throttling and recycle pumping to the learner."
            ),
            published_signal_ids=(
                "fresh_feed_draw_mol_s",
                "liquid_product_flow_mol_s",
                "purge_loss_flow_mol_s",
                "total_normalized_pump_load",
            ),
            allowed_item_ids=(
                "install_line_valve",
                "install_line_pump",
            ),
        ),
    ]
    return {entry.start_id: entry for entry in entries}

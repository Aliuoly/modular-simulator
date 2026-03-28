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
            title="Sweet wet gas main sandbox",
            seed_source_paths=(
                "examples/unit_process_flowsheet/gas_1_inlet_separator.py",
                "examples/unit_process_flowsheet/gas_2_teg_dehydration.py",
                "examples/unit_process_flowsheet/gas_3_jt_low_temperature_separation.py",
                "examples/unit_process_flowsheet/gas_4_condensate_stabilizer.py",
            ),
            starting_topology_summary=(
                "One sweet wet gas feed and five named product sinks are present, but no gas-processing units, line overlays, or connecting lines are preinstalled."
            ),
            published_signal_ids=(
                "sweet_wet_gas_draw_mol_s",
                "separator_gas_flow_mol_s",
                "unstabilized_condensate_flow_mol_s",
                "dry_gas_flow_mol_s",
                "ngl_liquids_flow_mol_s",
                "stabilized_condensate_flow_mol_s",
                "heating_steam_duty_W",
                "total_normalized_pump_load",
            ),
            allowed_item_ids=(
                "place_inlet_gas_separator",
                "place_teg_contactor",
                "place_rich_glycol_flash_tank",
                "place_lean_rich_glycol_exchanger",
                "place_teg_regenerator",
                "install_glycol_circulation_pump",
                "place_gas_gas_exchanger",
                "install_jt_valve",
                "place_low_temperature_separator",
                "place_condensate_stabilizer",
                "build_process_line",
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

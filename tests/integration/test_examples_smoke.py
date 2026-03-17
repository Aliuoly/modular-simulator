from __future__ import annotations

from typing import cast

import pytest

from examples.connection_layer.two_tank_reaction_comparison import run_demo as run_two_tank_demo
from examples.dynamic_api_cli.minimal_command_quickstart import run_demo as run_command_demo
from examples.dynamic_api_cli.minimal_control_loop_save_load import (
    run_demo as run_control_and_checkpoint_demo,
)
from examples.unit_process_flowsheet.complex_6_ammonia_recycle_loop import (
    _build_flowsheet as build_ammonia_loop_flowsheet,
    run_example as run_ammonia_loop_example,
)
from examples.unit_process_flowsheet.easy_2_heater_flash import (
    run_example as run_heater_flash_example,
)
from examples.unit_process_flowsheet.easy_3_dual_feed_heat_exchanger import (
    run_example as run_dual_feed_exchanger_example,
)
from examples.van_de_vusse_cstr.run_simulation import run_demo as run_van_de_vusse_demo


def test_quickstart_two_process_command_path_smoke() -> None:
    command_result = run_command_demo()
    command_applied = cast(tuple[str, ...], command_result["command_applied"])
    api_applied = cast(tuple[str, ...], command_result["api_applied"])
    process_ids = cast(tuple[str, ...], command_result["process_ids"])
    assert command_applied == ("rq_0001", "rq_0002")
    assert api_applied == (
        "rq_0003",
        "rq_0004",
        "rq_0005",
        "rq_0006",
    )
    assert "reactor_b" in process_ids
    assert "mix_junction" in process_ids


def test_van_de_vusse_cstr_run_demo_smoke() -> None:
    result = run_van_de_vusse_demo()
    duration_hours = cast(float, result["duration_hours"])
    system_labels = cast(tuple[str, ...], result["system_labels"])
    final_ca = cast(float, result["final_Ca"])
    final_cb = cast(float, result["final_Cb"])
    final_t = cast(float, result["final_T"])
    final_tk = cast(float, result["final_Tk"])
    final_tj_in = cast(float, result["final_Tj_in"])

    assert duration_hours == 120.0
    assert system_labels == ("normal",)
    assert 0.0 <= final_ca < 5.1
    assert 0.0 <= final_cb < 5.1
    assert 0.0 < final_tk < final_t < 300.0
    assert 10.0 <= final_tj_in <= 110.0


def test_valve_sensor_controller_loop_smoke() -> None:
    control_result = run_control_and_checkpoint_demo()
    heater_power = cast(float, control_result["heater_power"])
    heat_actuator_rate = cast(float, control_result["heat_actuator_rate"])
    applied_request_ids = cast(tuple[str, ...], control_result["applied_request_ids"])
    assert heater_power == 0.0
    assert heat_actuator_rate > 0.0
    assert len(applied_request_ids) == 14


def test_save_load_continue_api_and_cli_smoke() -> None:
    result = run_control_and_checkpoint_demo()
    api_round_trip_ok = cast(bool, result["api_round_trip_ok"])
    cli_round_trip_ok = cast(bool, result["cli_round_trip_ok"])
    assert api_round_trip_ok is True
    assert cli_round_trip_ok is True


def test_curated_heater_flash_example_smoke() -> None:
    result = run_heater_flash_example(steps=12, dt=0.2, make_plot=False)
    vapor_fraction = cast(float, result["flash_vapor_fraction"])
    vapor_flow = cast(float, result["estimated_flash_vapor_flow_mol_s"])
    liquid_flow = cast(float, result["flash_liquid_flow_mol_s"])
    assert 0.0 < vapor_fraction < 1.0
    assert vapor_flow > 0.0
    assert liquid_flow >= 0.0


def test_curated_dual_feed_exchanger_example_smoke() -> None:
    result = run_dual_feed_exchanger_example(steps=12, dt=0.2, make_plot=False)
    hot_outlet_temperature = cast(float, result["hot_outlet_temperature_K"])
    cold_outlet_temperature = cast(float, result["cold_outlet_temperature_K"])
    heat_duty = cast(float, result["heat_duty_W"])
    assert hot_outlet_temperature > 0.0
    assert cold_outlet_temperature > 0.0
    assert heat_duty != 0.0


def test_curated_ammonia_recycle_example_smoke() -> None:
    topology_results = build_ammonia_loop_flowsheet(dt=0.2).run(steps=4, dt=0.2)
    recycle_leg = topology_results.get_stream("purge_splitter.outlet_1", "synthesis_mixer.inlet_2")
    assert recycle_leg.flow_rate.shape == (4,)
    with pytest.raises(
        ValueError, match="unknown stream connection 'recycle_return->synthesis_mixer.inlet_2'"
    ):
        _ = topology_results.get_stream("recycle_return", "synthesis_mixer.inlet_2")

    result = run_ammonia_loop_example(steps=60, dt=0.2, make_plot=False)
    recycle_ratio = cast(float, result["recycle_to_fresh_ratio"])
    recycle_flow = cast(float, result["recycle_edge_flow_mol_s"])
    product_purity = cast(float, result["liquid_product_purity"])
    product_flow = cast(float, result["liquid_product_flow_mol_s"])
    assert recycle_flow >= 0.0
    assert recycle_ratio >= 0.0
    assert 0.0 <= product_purity <= 1.0
    assert product_flow >= 0.0


def test_curated_two_tank_comparison_smoke() -> None:
    result = run_two_tank_demo()
    max_abs_error_a = cast(float, result.max_abs_error_a)
    max_abs_error_b = cast(float, result.max_abs_error_b)
    monotonic_decay_a = cast(bool, result.monotonic_decay_a)
    monotonic_decay_b = cast(bool, result.monotonic_decay_b)
    assert max_abs_error_a < 1.0e-6
    assert max_abs_error_b < 1.0e-2
    assert monotonic_decay_a is True
    assert monotonic_decay_b is True

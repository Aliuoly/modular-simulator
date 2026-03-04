from __future__ import annotations

from typing import cast

from examples.dynamic_api_cli.minimal_command_quickstart import run_demo as run_command_demo
from examples.dynamic_api_cli.minimal_control_loop_save_load import (
    run_demo as run_control_and_checkpoint_demo,
)
from examples.dynamic_api_cli.minimal_spec_quickstart import run_demo as run_spec_demo


def test_quickstart_two_process_command_and_spec_paths_smoke() -> None:
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

    spec_result = run_spec_demo()
    diff_add = cast(int, spec_result["diff_add"])
    diff_update = cast(int, spec_result["diff_update"])
    edge_ids = cast(tuple[str, ...], spec_result["edge_ids"])
    spec_process_ids = cast(tuple[str, ...], spec_result["process_ids"])
    assert diff_add >= 1
    assert diff_update >= 1
    assert "edge_0003" in edge_ids
    assert "reactor_b" in spec_process_ids


def test_junction_as_unit_and_valve_sensor_controller_loop_smoke() -> None:
    command_result = run_command_demo()
    process_ids = cast(tuple[str, ...], command_result["process_ids"])
    assert "mix_junction" in process_ids

    control_result = run_control_and_checkpoint_demo()
    heater_power = cast(float, control_result["heater_power"])
    applied_request_ids = cast(tuple[str, ...], control_result["applied_request_ids"])
    assert heater_power > 0.0
    assert len(applied_request_ids) == 13


def test_save_load_continue_api_and_cli_smoke() -> None:
    result = run_control_and_checkpoint_demo()
    api_round_trip_ok = cast(bool, result["api_round_trip_ok"])
    cli_round_trip_ok = cast(bool, result["cli_round_trip_ok"])
    assert api_round_trip_ok is True
    assert cli_round_trip_ok is True

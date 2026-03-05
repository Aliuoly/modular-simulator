from __future__ import annotations

# pyright: reportMissingTypeStubs=false, reportPrivateUsage=false, reportUnknownMemberType=false

import math
import warnings
from typing import cast

import numpy as np
import pytest

from modular_simulation.components import (
    ControlElement,
    ControllerMode,
    PIDController,
    SampledDelayedSensor,
    Trajectory,
)
from modular_simulation.flowsheet import Flowsheet, FlowsheetResults
from modular_simulation.thermodynamics.runtime_context import SimulationRuntimeContext
from modular_simulation.unit_processes import HeaterCooler


def _build_and_run_case(
    *, control_enabled: bool, steps: int = 60
) -> tuple[Flowsheet, FlowsheetResults, SampledDelayedSensor, SimulationRuntimeContext]:
    context = SimulationRuntimeContext.create(species_names=["ethanol", "water"])
    flowsheet = Flowsheet(context=context, dt=0.2)

    controlled_heater = HeaterCooler(mode="temperature", target_temperature_setpoint=328.0)
    downstream_heater = HeaterCooler(mode="duty", duty_setpoint=0.0)
    branch_a_heater = HeaterCooler(mode="duty", duty_setpoint=0.0)
    branch_b_heater = HeaterCooler(mode="duty", duty_setpoint=0.0)

    flowsheet.add_unit("u1", controlled_heater)
    flowsheet.add_unit("u2", downstream_heater)
    flowsheet.add_unit("u3", branch_a_heater)
    flowsheet.add_unit("u4", branch_b_heater)

    flowsheet.add_feed_from_values(
        "feed",
        T=328.0,
        P=180000.0,
        z=(0.55, 0.45),
        flow=6.0,
    )
    flowsheet.chain("feed", "u1", "u2")
    flowsheet.connect("feed", "u3")
    flowsheet.connect("feed", "u4")

    controlled_subsystem = flowsheet._subsystems["u1"]
    sensor = SampledDelayedSensor(
        measurement_tag="outlet_temperature",
        alias_tag="u1_outlet_temperature",
        unit="K",
        sampling_period=0.0,
        deadtime=0.0,
    )
    _ = controlled_subsystem.add_sensor(sensor)

    if control_enabled:
        controller = PIDController(
            cv_tag="u1_outlet_temperature",
            cv_range=(280.0, 450.0),
            sp_trajectory=Trajectory(y0=360.0),
            Kp=4.0,
            Ti=5.0,
            period=0.0,
        )
        control_element = ControlElement(
            mv_tag="target_temperature_setpoint",
            mv_range=(300.0, 390.0),
            mv_trajectory=Trajectory(y0=328.0),
            controller=controller,
            mode=ControllerMode.AUTO,
            period=0.0,
        )
        _ = controlled_subsystem.add_control_element(control_element)

    with warnings.catch_warnings(record=True) as caught_warnings:
        warnings.simplefilter("always")
        _ = flowsheet.compile()
    warning_messages = [str(item.message) for item in caught_warnings]
    assert any("dangling outlet" in message for message in warning_messages)

    results = flowsheet.run(steps=steps)
    _ = sensor.update(flowsheet.get_system("u1").time)
    return flowsheet, results, sensor, context


def test_multi_unit_flowsheet_integration_with_sensor_and_controller() -> None:
    simulation_steps = 60
    baseline_flowsheet, _, _, _ = _build_and_run_case(control_enabled=False, steps=simulation_steps)
    controlled_flowsheet, controlled_results, sensor, context = _build_and_run_case(
        control_enabled=True, steps=simulation_steps
    )

    assert len(controlled_results.step_results) >= 50
    executed_sequence = controlled_results.step_results[
        -1
    ].runtime_step_result.bookkeeping.executed_sequence
    assert "hydraulics_solve" in executed_sequence

    connection_flow_series = {
        "feed->u1": controlled_results.get_stream("feed", "u1").flow_rate,
        "u1->u2": controlled_results.get_stream("u1", "u2").flow_rate,
        "feed->u3": controlled_results.get_stream("feed", "u3").flow_rate,
        "feed->u4": controlled_results.get_stream("feed", "u4").flow_rate,
    }
    feed_reference_flow = controlled_results.get_stream("feed", "u1").flow_rate
    source_mass_reference = {
        "feed->u1": feed_reference_flow,
        "u1->u2": controlled_results.get_unit("u1").state_history["outlet_flow"],
        "feed->u3": feed_reference_flow,
        "feed->u4": feed_reference_flow,
    }
    for connection_key, stream_flow in connection_flow_series.items():
        reference_flow = source_mass_reference[connection_key]
        rel_error = np.abs(stream_flow[1:] - reference_flow[1:]) / np.maximum(
            np.abs(reference_flow[1:]), 1.0e-9
        )
        assert float(np.max(rel_error)) < 1.0e-3

    controlled_u1 = cast(HeaterCooler, controlled_flowsheet.get_unit("u1"))
    assert sensor.point.data.value == pytest.approx(controlled_u1.outlet_temperature, abs=1.0e-9)

    controlled_u2 = cast(HeaterCooler, controlled_flowsheet.get_unit("u2"))
    baseline_u2 = cast(HeaterCooler, baseline_flowsheet.get_unit("u2"))
    assert controlled_u1.target_temperature_setpoint != pytest.approx(328.0, abs=1.0e-9)
    assert abs(controlled_u2.inlet_temperature - baseline_u2.inlet_temperature) > 1.0

    feed_to_u3 = controlled_results.get_stream("feed", "u3")
    feed_to_u4 = controlled_results.get_stream("feed", "u4")
    assert feed_to_u3.flow_rate.shape == (simulation_steps,)
    assert feed_to_u4.flow_rate.shape == (simulation_steps,)

    property_package = context.get_property_package()
    for unit_id in ("u1", "u2", "u3", "u4"):
        outlet = controlled_results.get_unit(unit_id).outlet_streams["outlet"]
        assert outlet.temperature > 0.0
        assert outlet.pressure > 0.0
        assert math.isfinite(outlet.temperature)
        assert math.isfinite(outlet.pressure)
        assert all(math.isfinite(value) for value in outlet.mole_fractions)
        assert sum(outlet.mole_fractions) == pytest.approx(1.0, abs=1.0e-8)
        flash = property_package.flash_tp(
            T=outlet.temperature,
            P=outlet.pressure,
            z=outlet.mole_fractions,
        )
        assert math.isfinite(float(flash.enthalpy_molar))
        assert math.isfinite(float(flash.entropy_molar))

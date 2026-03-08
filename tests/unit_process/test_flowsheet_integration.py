from __future__ import annotations

# pyright: reportMissingTypeStubs=false, reportPrivateUsage=false, reportUnknownMemberType=false

import math
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
from modular_simulation.framework.system import System
from modular_simulation.thermodynamics.runtime_context import SimulationRuntimeContext
from modular_simulation.unit_processes import CSTR, FlashDrum, HeaterCooler, Pump
from modular_simulation.thermodynamics.property_package import PengRobinsonPackage


def _build_and_run_case(
    *, imposed_outlet_temperature: float, steps: int = 60
) -> tuple[Flowsheet, FlowsheetResults, SampledDelayedSensor, SimulationRuntimeContext]:
    context = SimulationRuntimeContext.create(species_names=["ethanol", "water"])
    flowsheet = Flowsheet(context=context, dt=0.2)

    controlled_heater = HeaterCooler(
        mode="temperature", external_outlet_temperature=imposed_outlet_temperature
    )
    downstream_heater = HeaterCooler(mode="duty", external_heat_duty=0.0)
    branch_a_heater = HeaterCooler(mode="duty", external_heat_duty=0.0)
    branch_b_heater = HeaterCooler(mode="duty", external_heat_duty=0.0)

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

    _ = flowsheet.compile()

    results = flowsheet.run(steps=steps)
    _ = sensor.update(flowsheet.get_system("u1").time)
    return flowsheet, results, sensor, context


def test_multi_unit_flowsheet_integration_with_external_heater_boundary() -> None:
    simulation_steps = 60
    baseline_flowsheet, _, _, _ = _build_and_run_case(
        imposed_outlet_temperature=328.0,
        steps=simulation_steps,
    )
    controlled_flowsheet, controlled_results, sensor, context = _build_and_run_case(
        imposed_outlet_temperature=360.0,
        steps=simulation_steps,
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
    assert controlled_u1.external_outlet_temperature == pytest.approx(360.0, abs=1.0e-9)
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


def test_cascade_reference_to_pump_speed_actuator_closes_pressure_loop() -> None:
    pump = Pump(
        n_species=2,
        inlet_flow=0.01,
        inlet_temperature=300.0,
        inlet_pressure=101325.0,
        inlet_composition=np.array([0.5, 0.5], dtype=np.float64),
        pump_speed=20000.0,
        efficiency=0.75,
    )
    pressure_sensor = SampledDelayedSensor(
        measurement_tag="outlet_pressure",
        alias_tag="pump_outlet_pressure",
        unit="Pa",
        sampling_period=0.0,
        deadtime=0.0,
    )
    speed_sensor = SampledDelayedSensor(
        measurement_tag="pump_speed",
        alias_tag="pump_speed_measured",
        unit="Pa",
        sampling_period=0.0,
        deadtime=0.0,
    )

    pressure_controller = PIDController(
        cv_tag="pump_outlet_pressure",
        cv_range=(101325.0, 300000.0),
        reference_trajectory=Trajectory(y0=120000.0),
        Kp=0.07,
        Ti=2.0,
        period=0.0,
        mode=ControllerMode.AUTO,
    )
    speed_controller = PIDController(
        cv_tag="pump_speed_measured",
        cv_range=(0.0, 220000.0),
        reference_trajectory=Trajectory(y0=20000.0),
        cascade_controller=pressure_controller,
        Kp=0.25,
        Ti=1.0,
        period=0.0,
        mode=ControllerMode.CASCADE,
    )

    pump_speed_element = ControlElement(
        mv_tag="pump_speed",
        mv_range=(0.0, 220000.0),
        mv_trajectory=Trajectory(y0=20000.0),
        controller=speed_controller,
        mode=ControllerMode.AUTO,
    )

    system = System(
        dt=0.1,
        process_model=pump,
        sensors=[pressure_sensor, speed_sensor],
        calculations=[],
        control_elements=[pump_speed_element],
        show_progress=False,
    )

    for _ in range(80):
        system.step(duration=0.1)
    first_stage_pressure = float(pump.outlet_pressure)
    first_stage_speed = float(pump.pump_speed)

    _ = system.extend_controller_reference_trajectory("pump_outlet_pressure", value=135000.0)
    for _ in range(80):
        system.step(duration=0.1)

    assert pressure_controller.mode == ControllerMode.AUTO
    assert speed_controller.mode == ControllerMode.CASCADE
    assert pressure_controller.reference_point_dict[
        "pump_outlet_pressure.ref"
    ].data.value == pytest.approx(135000.0, abs=1.0e-6)
    assert first_stage_pressure == pytest.approx(120000.0, rel=0.03)
    assert float(pump.outlet_pressure) > first_stage_pressure + 2000.0
    assert float(pump.pump_speed) > first_stage_speed + 2000.0


def test_cascade_reference_to_cstr_outlet_flow_actuator_controls_volume() -> None:
    reactor = CSTR(
        n_species=2,
        species_names=("A", "B"),
        species_moles=np.array([6.0, 0.0], dtype=np.float64),
        temperature=300.0,
        volume=6.0,
        inlet_flow=1.5,
        outlet_flow=1.2,
        inlet_temperature=300.0,
        inlet_pressure=101325.0,
        inlet_composition=np.array([1.0, 0.0], dtype=np.float64),
    )
    volume_sensor = SampledDelayedSensor(
        measurement_tag="volume",
        alias_tag="reactor_volume",
        unit="L",
        sampling_period=0.0,
        deadtime=0.0,
    )
    outlet_flow_sensor = SampledDelayedSensor(
        measurement_tag="outlet_flow",
        alias_tag="reactor_outlet_flow",
        unit="L/s",
        sampling_period=0.0,
        deadtime=0.0,
    )

    level_controller = PIDController(
        cv_tag="reactor_volume",
        cv_range=(1.0, 20.0),
        reference_trajectory=Trajectory(y0=8.0),
        Kp=0.35,
        Ti=5.0,
        inverted=True,
        period=0.0,
        mode=ControllerMode.AUTO,
    )
    flow_controller = PIDController(
        cv_tag="reactor_outlet_flow",
        cv_range=(0.0, 3.0),
        reference_trajectory=Trajectory(y0=1.2),
        cascade_controller=level_controller,
        Kp=0.8,
        Ti=8.0,
        period=0.0,
        mode=ControllerMode.CASCADE,
    )

    outlet_flow_element = ControlElement(
        mv_tag="outlet_flow",
        mv_range=(0.0, 3.0),
        mv_trajectory=Trajectory(y0=1.2),
        controller=flow_controller,
        mode=ControllerMode.AUTO,
    )
    system = System(
        dt=0.1,
        process_model=reactor,
        sensors=[volume_sensor, outlet_flow_sensor],
        calculations=[],
        control_elements=[outlet_flow_element],
        show_progress=False,
    )

    for _ in range(200):
        system.step(duration=0.1)
    first_stage_volume = float(reactor.volume)
    first_stage_outlet_flow = float(reactor.outlet_flow)

    _ = system.extend_controller_reference_trajectory("reactor_volume", value=10.0)
    for _ in range(200):
        system.step(duration=0.1)

    assert level_controller.mode == ControllerMode.AUTO
    assert flow_controller.mode == ControllerMode.CASCADE
    assert level_controller.reference_point_dict["reactor_volume.ref"].data.value == pytest.approx(
        10.0, abs=1.0e-6
    )
    assert first_stage_volume == pytest.approx(8.0, rel=0.07, abs=0.35)
    assert float(reactor.volume) > first_stage_volume + 1.5
    assert float(reactor.outlet_flow) < first_stage_outlet_flow


def test_flash_imposed_pressure_boundary_changes_phase_split_dynamics() -> None:
    package = PengRobinsonPackage(species_ids=("7732-18-5", "64-17-5"))
    drum = FlashDrum(
        thermal_mode="adiabatic",
        n_species=2,
        inlet_flow=10.0,
        inlet_temperature=345.0,
        inlet_pressure=101325.0,
        inlet_composition=np.array([0.5, 0.5], dtype=np.float64),
        imposed_pressure=101325.0,
        imposed_temperature=355.0,
    )
    drum.set_property_package(package)
    boundary_system = System(
        dt=0.1,
        process_model=drum,
        sensors=[],
        calculations=[],
        control_elements=[],
        show_progress=False,
    )

    for _ in range(30):
        boundary_system.step(duration=0.1)
    high_pressure_vf = float(drum.vapor_fraction)

    drum.imposed_pressure = 85000.0
    for _ in range(30):
        boundary_system.step(duration=0.1)
    low_pressure_vf = float(drum.vapor_fraction)

    assert float(drum.outlet_pressure) == pytest.approx(85000.0, abs=1.0e-9)
    assert high_pressure_vf == pytest.approx(0.0, abs=1.0e-12)
    assert low_pressure_vf > high_pressure_vf

from __future__ import annotations

# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false

import numpy as np
import pytest
from typing import cast

from modular_simulation.components import SampledDelayedSensor
from modular_simulation.connection.topology.unit_process_wiring import (
    create_subsystem_for_unit,
    create_system_for_unit,
)
from modular_simulation.framework.system import System
from modular_simulation.measurables.process_model import StateType
from modular_simulation.thermodynamics.runtime_context import SimulationRuntimeContext
from modular_simulation.thermodynamics.stream import StreamData
from modular_simulation.unit_processes import CSTR, HeaterCooler, Splitter


def test_auto_wrap_heater() -> None:
    heater_for_system = HeaterCooler(
        mode="duty",
        n_species=2,
        inlet_composition=np.array([0.5, 0.5], dtype=np.float64),
    )
    system = create_system_for_unit(unit=heater_for_system, dt=0.2)
    assert isinstance(system, System)
    assert system.process_model is heater_for_system
    assert system.dt == pytest.approx(0.2)
    assert tuple(system.sensors) == ()
    assert tuple(system.calculations) == ()
    assert tuple(system.control_elements) == ()

    runtime_context = SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    heater = HeaterCooler(
        mode="duty",
        n_species=2,
        inlet_composition=np.array([0.5, 0.5], dtype=np.float64),
    )
    subsystem = create_subsystem_for_unit(
        unit=heater,
        unit_id="heater",
        dt=0.1,
        runtime_context=runtime_context,
    )

    assert subsystem.descriptor.descriptor_id == "heater"
    assert subsystem.descriptor.process_id == "heater"
    assert subsystem.descriptor.inlet_ports == heater.ports.inlets
    assert subsystem.descriptor.outlet_ports == heater.ports.outlets

    descriptor_context = dict(subsystem.descriptor.runtime_context or {})
    descriptor_fields = cast(dict[str, str], descriptor_context["descriptor_fields"])
    assert descriptor_fields["inlet_inlet"] == "unit_heater_inlet_inlet"
    assert descriptor_fields["outlet_outlet"] == "unit_heater_outlet_outlet"

    for state_name, metadata in heater.state_metadata_dict.items():
        if metadata.type in {StateType.ALGEBRAIC, StateType.DIFFERENTIAL}:
            assert state_name in subsystem.descriptor.publication_map

    assert getattr(heater, "_property_package", None) is runtime_context.get_property_package()

    cstr = CSTR(
        n_species=2,
        inlet_composition=np.array([0.5, 0.5], dtype=np.float64),
        outlet_composition=np.array([0.5, 0.5], dtype=np.float64),
    )
    cstr_subsystem = create_subsystem_for_unit(
        unit=cstr,
        unit_id="reactor",
        dt=0.1,
        runtime_context=runtime_context,
    )
    differential_states = [
        name
        for name, metadata in cstr.state_metadata_dict.items()
        if metadata.type == StateType.DIFFERENTIAL
    ]
    assert differential_states
    for state_name in differential_states:
        assert state_name in cstr_subsystem.descriptor.publication_map

    splitter = Splitter(n_species=2)
    splitter_subsystem = create_subsystem_for_unit(
        unit=splitter,
        unit_id="splitter",
        dt=0.1,
        runtime_context=runtime_context,
    )
    assert splitter_subsystem.descriptor.process_id == "splitter"


def test_sensor_on_wrapped_unit() -> None:
    heater = HeaterCooler(
        mode="duty",
        n_species=2,
        inlet_composition=np.array([0.5, 0.5], dtype=np.float64),
    )
    subsystem = create_subsystem_for_unit(unit=heater, unit_id="heater_sensor", dt=0.1)

    sensor = SampledDelayedSensor(
        measurement_tag="outlet_temperature",
        alias_tag="heater_sensor.outlet_temperature",
        unit="K",
    )
    _ = subsystem.add_sensor(sensor)

    sample_count_before = len(sensor.point.history)
    subsystem.run_sensor_phase()

    assert sensor.point.data.ok
    assert float(sensor.point.data.value) == pytest.approx(float(heater.outlet_temperature))
    assert len(sensor.point.history) > sample_count_before

    heater.apply_inlet(
        "inlet",
        StreamData(
            temperature=325.0,
            pressure=130000.0,
            mole_fractions=(0.4, 0.6),
            molar_flow_rate=2.0,
        ),
    )
    subsystem.run_process_phase(duration=0.1)
    assert heater.t == pytest.approx(0.1)

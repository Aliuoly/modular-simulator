from __future__ import annotations

# pyright: reportMissingTypeStubs=false

from dataclasses import FrozenInstanceError

import pytest

from modular_simulation.connection.state import MaterialState, PortCondition
from modular_simulation.thermodynamics.stream import (
    PortAttributeMap,
    StreamData,
    default_inlet_map,
    default_outlet_map,
)


def test_stream_data_is_immutable() -> None:
    stream = StreamData(
        temperature=320.0,
        pressure=101325.0,
        mole_fractions=(0.7, 0.3),
        molar_flow_rate=2.0,
    )

    with pytest.raises(FrozenInstanceError):
        setattr(stream, "temperature", 330.0)


def test_stream_data_round_trip_port_condition_preserves_values() -> None:
    condition = PortCondition(
        state=MaterialState(
            pressure=180000.0,
            temperature=410.0,
            mole_fractions=(0.2, 0.3, 0.5),
            species_ids=("7732-18-5", "64-17-5", "67-56-1"),
            phase="vapor",
            enthalpy_molar=24000.0,
            entropy_molar=96.0,
        ),
        species_ids=("7732-18-5", "64-17-5", "67-56-1"),
        through_molar_flow_rate=4.2,
    )

    stream = StreamData.from_port_condition(condition)
    reconstructed_condition = stream.to_port_condition()
    state = stream.to_material_state()
    stream_round_trip = StreamData.from_port_condition(reconstructed_condition)

    assert stream.molar_flow_rate == 4.2
    assert stream.temperature == 410.0
    assert stream.pressure == 180000.0
    assert stream.mole_fractions == (0.2, 0.3, 0.5)
    assert stream.species_ids == ("7732-18-5", "64-17-5", "67-56-1")
    assert stream.phase == "vapor"
    assert stream.enthalpy_molar == 24000.0
    assert stream.entropy_molar == 96.0
    assert stream_round_trip == stream

    assert reconstructed_condition.through_molar_flow_rate == condition.through_molar_flow_rate
    assert reconstructed_condition.macro_step_time_s is None
    assert reconstructed_condition.species_ids == condition.species_ids
    assert reconstructed_condition.state == condition.state

    assert state.pressure == condition.state.pressure
    assert state.temperature == condition.state.temperature
    assert state.mole_fractions == condition.state.mole_fractions
    assert state.species_ids == condition.state.species_ids
    assert state.phase == condition.state.phase
    assert state.enthalpy_molar == condition.state.enthalpy_molar
    assert state.entropy_molar == condition.state.entropy_molar


def test_stream_data_uses_port_species_ids_when_state_ids_absent() -> None:
    condition = PortCondition(
        state=MaterialState(
            pressure=101325.0,
            temperature=298.15,
            mole_fractions=(0.6, 0.4),
        ),
        species_ids=("7732-18-5", "64-17-5"),
        through_molar_flow_rate=1.5,
    )

    stream = StreamData.from_port_condition(condition)
    assert stream.species_ids == ("7732-18-5", "64-17-5")


def test_default_port_attribute_maps_follow_naming_rules() -> None:
    assert default_inlet_map("inlet") == PortAttributeMap(
        flow="inlet_flow",
        temperature="inlet_temperature",
        pressure="inlet_pressure",
        composition="inlet_composition",
    )
    assert default_inlet_map("inlet_2") == PortAttributeMap(
        flow="inlet_2_flow",
        temperature="inlet_2_temperature",
        pressure="inlet_2_pressure",
        composition="inlet_2_composition",
    )
    assert default_outlet_map("outlet") == PortAttributeMap(
        flow="outlet_flow",
        temperature="outlet_temperature",
        pressure="outlet_pressure",
        composition="outlet_composition",
    )
    assert default_outlet_map("distillate") == PortAttributeMap(
        flow="distillate_flow",
        temperature="distillate_temperature",
        pressure="distillate_pressure",
        composition="distillate_composition",
    )

from __future__ import annotations

# pyright: reportMissingTypeStubs=false

import warnings

import pytest

from modular_simulation.flowsheet import Flowsheet
from modular_simulation.thermodynamics.runtime_context import SimulationRuntimeContext
from modular_simulation.thermodynamics.stream import StreamData
from modular_simulation.unit_processes import FlashDrum, HeaterCooler


def test_unbound_inlet() -> None:
    context = SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    flowsheet = Flowsheet(context=context)
    flowsheet.add_unit("heater_1", HeaterCooler(n_species=2))
    flowsheet.add_unit("heater_2", HeaterCooler(n_species=2))
    flowsheet.add_feed_from_values("feed", T=300.0, P=101325.0, z=(0.5, 0.5), flow=1.0)
    flowsheet.connect("feed", "heater_1")

    with pytest.raises(ValueError, match=r"unbound mandatory inlet\(s\): heater_2\.inlet"):
        _ = flowsheet.compile()


def test_ambiguous_port() -> None:
    context = SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    flowsheet = Flowsheet(context=context)
    flowsheet.add_unit("flash", FlashDrum(n_species=2, thermal_mode="isothermal"))
    flowsheet.add_unit("heater", HeaterCooler(n_species=2))

    with pytest.raises(
        ValueError,
        match="ambiguous source endpoint 'flash': available source ports are vapor_outlet, liquid_outlet",
    ):
        flowsheet.connect("flash", "heater")


def test_species_mismatch_missing_species_named() -> None:
    context = SimulationRuntimeContext.create(species_names=["water", "ethanol", "methanol"])
    species_ids = context.species_registry.cas_list
    missing_species_id = species_ids[2]

    flowsheet = Flowsheet(context=context)
    flowsheet.add_unit("heater", HeaterCooler(n_species=3))
    flowsheet.add_feed(
        "feed",
        StreamData(
            temperature=300.0,
            pressure=101325.0,
            mole_fractions=(0.5, 0.5),
            molar_flow_rate=1.0,
            species_ids=(species_ids[0], species_ids[1]),
        ),
    )
    flowsheet.connect("feed", "heater")

    with pytest.raises(ValueError, match="species mismatch") as exc:
        _ = flowsheet.compile()

    assert missing_species_id in str(exc.value)


def test_dangling_outlet_warns() -> None:
    context = SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    flowsheet = Flowsheet(context=context)
    flowsheet.add_unit("heater", HeaterCooler(n_species=2))
    flowsheet.add_feed_from_values("feed", T=300.0, P=101325.0, z=(0.5, 0.5), flow=1.0)
    flowsheet.connect("feed", "heater")

    with pytest.warns(UserWarning, match="dangling outlet"):
        _ = flowsheet.compile()


def test_disconnected_subgraph_warns() -> None:
    context = SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    flowsheet = Flowsheet(context=context)
    flowsheet.add_unit("heater_a", HeaterCooler(n_species=2))
    flowsheet.add_unit("heater_b", HeaterCooler(n_species=2))
    flowsheet.add_feed_from_values("feed_a", T=300.0, P=101325.0, z=(0.5, 0.5), flow=1.0)
    flowsheet.add_feed_from_values("feed_b", T=300.0, P=101325.0, z=(0.5, 0.5), flow=1.0)
    flowsheet.connect("feed_a", "heater_a")
    flowsheet.connect("feed_b", "heater_b")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _ = flowsheet.compile()

    messages = [str(item.message) for item in caught]
    assert any("disconnected topology detected" in message for message in messages)


def test_cycle_warns_without_failing_compile() -> None:
    context = SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    flowsheet = Flowsheet(context=context)
    flowsheet.add_unit("heater_a", HeaterCooler(n_species=2))
    flowsheet.add_unit("heater_b", HeaterCooler(n_species=2))
    flowsheet.add_feed_from_values("feed", T=300.0, P=101325.0, z=(0.5, 0.5), flow=1.0)
    flowsheet.connect("feed", "heater_a")
    flowsheet.connect("heater_a", "heater_b")
    flowsheet.connect("heater_b", "heater_a")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _ = flowsheet.compile()

    messages = [str(item.message) for item in caught]
    assert any("recycle/cycle detected" in message for message in messages)


def test_compile_requires_pressure_boundary_feed() -> None:
    context = SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    flowsheet = Flowsheet(context=context)
    flowsheet.add_unit("heater_a", HeaterCooler(n_species=2))
    flowsheet.add_unit("heater_b", HeaterCooler(n_species=2))
    flowsheet.connect("heater_a", "heater_b")
    flowsheet.connect("heater_b", "heater_a")

    with pytest.raises(ValueError, match="at least one feed boundary is required"):
        _ = flowsheet.compile()

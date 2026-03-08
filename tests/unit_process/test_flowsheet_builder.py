from __future__ import annotations

# pyright: reportMissingTypeStubs=false

import pytest

from modular_simulation.connection.connected_plant_orchestrator import ConnectedPlantOrchestrator
from modular_simulation.flowsheet import Flowsheet
from modular_simulation.thermodynamics.runtime_context import SimulationRuntimeContext
from modular_simulation.unit_processes import FlashDrum, HeatExchanger, HeaterCooler


def test_simple_build_and_run() -> None:
    context = SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    flowsheet = Flowsheet(context=context, dt=0.1)

    heater = HeaterCooler(n_species=2, mode="duty", external_heat_duty=0.0)
    cooler = HeaterCooler(n_species=2, mode="duty", external_heat_duty=0.0)
    flowsheet.add_unit("heater", heater)
    flowsheet.add_unit("cooler", cooler)
    flowsheet.add_feed_from_values(
        "feed",
        T=315.0,
        P=165000.0,
        z=(0.45, 0.55),
        flow=3.5,
    )
    flowsheet.chain("feed", "heater", "cooler")

    assert flowsheet.get_unit("heater") is heater
    assert flowsheet.get_system("heater").process_model is heater

    plant = flowsheet.compile()
    assert isinstance(plant, ConnectedPlantOrchestrator)
    assert flowsheet.compile() is plant

    result = flowsheet.run(steps=2)
    assert len(result.step_results) == 2
    updated_keys = set(result.step_results[-1].runtime_step_result.bookkeeping.updated_port_keys)
    assert "heater.inlet" in updated_keys
    assert "cooler.inlet" in updated_keys


def test_connect_port_inference_ambiguity_lists_ports() -> None:
    context = SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    flowsheet = Flowsheet(context=context)

    flowsheet.add_unit("flash", FlashDrum(n_species=2, thermal_mode="isothermal"))
    flowsheet.add_unit("heater", HeaterCooler(n_species=2))
    flowsheet.add_unit("exchanger", HeatExchanger(n_species=2))
    flowsheet.add_feed_from_values("feed", T=300.0, P=130000.0, z=(0.5, 0.5), flow=2.0)

    with pytest.raises(
        ValueError,
        match=(
            "ambiguous source endpoint 'flash': available source ports are vapor_outlet, liquid_outlet"
        ),
    ):
        flowsheet.connect("flash", "heater")

    with pytest.raises(
        ValueError,
        match=(
            "ambiguous target endpoint 'exchanger': available target ports are hot_inlet, cold_inlet"
        ),
    ):
        flowsheet.connect("feed", "exchanger")

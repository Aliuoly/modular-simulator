from __future__ import annotations

# pyright: reportMissingTypeStubs=false

import pytest

from modular_simulation.connection.runtime.connected_plant_orchestrator import (
    ConnectedPlantOrchestrator,
)
from modular_simulation.flowsheet import Flowsheet, HeatInstall, PumpInstall, ValveInstall
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


def test_junction_sink_and_line_reference_compile_to_explicit_topology() -> None:
    context = SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    flowsheet = Flowsheet(context=context)

    flowsheet.add_unit("heater", HeaterCooler(n_species=2))
    flowsheet.add_feed_from_values("feed", T=305.0, P=130000.0, z=(0.5, 0.5), flow=2.0)
    flowsheet.add_junction("mix", inlet_ports=("fresh",), outlet_ports=("to_heater", "purge"))
    flowsheet.add_sink("product")

    first_line = flowsheet.connect("feed", "mix.fresh")
    second_line = flowsheet.connect(
        "mix.to_heater",
        "heater",
        pump=PumpInstall(initial_pump_speed=120000.0),
        heat=HeatInstall(initial_heat_rate=500.0),
    )
    third_line = flowsheet.connect("mix.purge", "product")

    assert first_line.line_id == "line_0001"
    assert second_line.line_id == "line_0002"
    assert second_line.pump_id == "line_0002__pump"
    assert second_line.heat_actuator_id == "line_0002__heat"
    assert third_line.line_id == "line_0003"

    plant = flowsheet.compile()
    compiled = plant._network.compiled
    assert compiled is not None
    assert tuple(node.junction_id for node in compiled.topology.junction_nodes) == ("mix",)
    assert compiled.topology.junction_nodes[0].inlet_ports == ("fresh",)
    assert compiled.topology.junction_nodes[0].outlet_ports == ("to_heater", "purge")
    assert tuple(boundary.boundary_id for boundary in compiled.topology.boundary_nodes) == (
        "feed",
        "product",
    )


def test_endpoint_validation_and_overlay_rules_are_actionable() -> None:
    context = SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    flowsheet = Flowsheet(context=context)
    flowsheet.add_unit("heater", HeaterCooler(n_species=2))
    flowsheet.add_feed_from_values("feed", T=300.0, P=101325.0, z=(0.5, 0.5), flow=1.0)
    flowsheet.add_junction("split", inlet_ports=("in",), outlet_ports=("a", "b"))
    flowsheet.add_sink("product")

    with pytest.raises(
        ValueError,
        match="ambiguous source endpoint 'split': available source ports are a, b; use explicit '<node_id>.<port_name>' syntax",
    ):
        flowsheet.connect("split", "heater")

    with pytest.raises(ValueError, match="feed 'feed' cannot be used as a connection target"):
        flowsheet.connect("heater", "feed.outlet")

    with pytest.raises(ValueError, match="sink 'product' cannot be used as a connection source"):
        flowsheet.connect("product.inlet", "heater")

    with pytest.raises(
        ValueError,
        match="line 'line_0001' cannot install both pump and valve hydraulic overlays",
    ):
        flowsheet.connect(
            "feed",
            "split.in",
            pump=PumpInstall(),
            valve=ValveInstall(),
        )


def test_valve_install_replacement_path_compiles() -> None:
    """Positive regression: ValveInstall on connect() must produce a line-owned valve
    actuator id and compile to a valid ConnectedPlantOrchestrator.

    This proves the replacement path described in the Valve-wrapper migration guidance
    actually works end-to-end.
    """
    context = SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    flowsheet = Flowsheet(context=context)

    flowsheet.add_unit("heater", HeaterCooler(n_species=2))
    flowsheet.add_feed_from_values("feed", T=305.0, P=165000.0, z=(0.5, 0.5), flow=3.0)
    flowsheet.add_sink("product")

    line_ref = flowsheet.connect(
        "feed",
        "heater",
        valve=ValveInstall(initial_open_fraction=0.75),
    )
    flowsheet.connect("heater", "product")

    # The line reference must expose the auto-generated valve actuator id.
    assert line_ref.valve_id is not None
    assert line_ref.valve_id.startswith("line_")
    assert line_ref.pump_id is None

    # Compiling must succeed - proves the valve replacement path is accepted
    # by the hydraulic system builder.
    plant = flowsheet.compile()
    assert isinstance(plant, ConnectedPlantOrchestrator)


def test_duplicate_node_and_line_owned_ids_fail_early() -> None:
    context = SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    flowsheet = Flowsheet(context=context)
    flowsheet.add_unit("heater", HeaterCooler(n_species=2))
    flowsheet.add_feed_from_values("feed", T=300.0, P=101325.0, z=(0.5, 0.5), flow=1.0)
    flowsheet.add_sink("product")

    with pytest.raises(ValueError, match="node id 'heater' is already registered"):
        flowsheet.add_junction("heater", inlet_ports=("in",), outlet_ports=("out",))

    _ = flowsheet.connect("feed", "heater", line_id="main_line", pump=PumpInstall(id="pump_a"))

    with pytest.raises(ValueError, match="duplicate line id 'main_line' is not allowed"):
        flowsheet.connect("heater", "product", line_id="main_line")

    with pytest.raises(ValueError, match="duplicate pump id 'pump_a' is not allowed"):
        flowsheet.connect("heater", "product", pump=PumpInstall(id="pump_a"))

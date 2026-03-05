from __future__ import annotations

import numpy as np
import pytest

from modular_simulation.connection.connection_layer import TransportAndMixingUpdate
from modular_simulation.connection.hydraulic_solver import HydraulicSolveResult
from modular_simulation.connection.network import ConnectionNetwork
from modular_simulation.connection.thermo_coupling import (
    ThermoBoundaryPropagationConfig,
    ThermoBoundaryPropagationStep,
)
from modular_simulation.thermodynamics.stream import StreamData
from modular_simulation.thermodynamics.runtime_context import SimulationRuntimeContext
from modular_simulation.unit_processes import CSTR, FlashDrum, HeaterCooler


def _hydraulic_result(unknowns: dict[str, float]) -> HydraulicSolveResult:
    return HydraulicSolveResult(
        converged=True,
        iterations=1,
        residual_norm=0.0,
        solution_vector=np.asarray(list(unknowns.values()), dtype=np.float64),
        unknowns=unknowns,
        unknown_index_map={name: index for index, name in enumerate(unknowns.keys())},
        residual_index_map={"r0": 0},
    )


def test_auto_propagation() -> None:
    context = SimulationRuntimeContext.create(species_names=["water", "ethanol"])

    network = ConnectionNetwork()
    network.add_boundary_source("feed")
    network.add_process("heater", inlet_ports=("inlet",), outlet_ports=("outlet",))
    network.add_process("reactor", inlet_ports=("inlet",), outlet_ports=("outlet",))
    feed_edge = network.connect("feed", "heater.inlet")
    heater_to_reactor_edge = network.connect("heater.outlet", "reactor.inlet")
    _ = network.compile()

    heater = HeaterCooler(
        mode="duty",
        n_species=2,
        pressure_drop=0.0,
        inlet_composition=np.array([0.5, 0.5], dtype=np.float64),
    )
    reactor = CSTR(
        n_species=2,
        inlet_composition=np.array([0.5, 0.5], dtype=np.float64),
        outlet_composition=np.array([0.5, 0.5], dtype=np.float64),
    )
    reactor.set_property_package(context.get_property_package())

    feed_stream = StreamData(
        temperature=315.0,
        pressure=180000.0,
        mole_fractions=(0.4, 0.6),
        molar_flow_rate=12.0,
    )

    heater.outlet_flow = 9.0
    heater.outlet_temperature = 355.0
    heater.outlet_pressure = 170000.0
    heater.outlet_composition = np.array([0.2, 0.8], dtype=np.float64)

    step = ThermoBoundaryPropagationStep(
        runtime_context=context,
        config=ThermoBoundaryPropagationConfig(
            stream_port_io_by_node_id={"heater": heater, "reactor": reactor},
            feed_streams_by_boundary_id={"feed": feed_stream},
        ),
    )
    conditions = step(
        network=network,
        hydraulic_result=_hydraulic_result(
            {feed_edge: 12.0, heater_to_reactor_edge: 9.0, "pressure": 101325.0}
        ),
        transport_and_mixing_update=TransportAndMixingUpdate(transport_results={}),
        macro_step_time_s=0.2,
    )

    assert heater.inlet_flow == pytest.approx(feed_stream.molar_flow_rate)
    assert heater.inlet_temperature == pytest.approx(feed_stream.temperature)
    assert heater.inlet_pressure == pytest.approx(feed_stream.pressure)
    assert heater.inlet_composition == pytest.approx(feed_stream.mole_fractions)

    expected_density = (
        context.get_property_package()
        .flash_tp(
            T=heater.outlet_temperature,
            P=heater.outlet_pressure,
            z=(0.2, 0.8),
        )
        .liquid_density
    )
    assert expected_density is not None
    expected_l_s = (
        heater.outlet_flow
        * context.get_property_package().molecular_weight((0.2, 0.8))
        / expected_density
    )

    assert reactor.inlet_flow == pytest.approx(expected_l_s)
    assert reactor.inlet_temperature == pytest.approx(heater.outlet_temperature)
    assert reactor.inlet_pressure == pytest.approx(heater.outlet_pressure)
    assert reactor.inlet_composition == pytest.approx((0.2, 0.8))

    assert conditions["heater.inlet"].through_molar_flow_rate == pytest.approx(12.0)
    assert conditions["reactor.inlet"].through_molar_flow_rate == pytest.approx(9.0)


def test_multi_outlet_routing() -> None:
    context = SimulationRuntimeContext.create(species_names=["water", "ethanol"])

    network = ConnectionNetwork()
    network.add_boundary_source("feed")
    network.add_process(
        "flash",
        inlet_ports=("inlet",),
        outlet_ports=("vapor_outlet", "liquid_outlet"),
    )
    network.add_process("vapor_target", inlet_ports=("inlet",), outlet_ports=("outlet",))
    network.add_process("liquid_target", inlet_ports=("inlet",), outlet_ports=("outlet",))
    feed_edge = network.connect("feed", "flash.inlet")
    vapor_edge = network.connect("flash.vapor_outlet", "vapor_target.inlet")
    liquid_edge = network.connect("flash.liquid_outlet", "liquid_target.inlet")
    _ = network.compile()

    flash = FlashDrum(n_species=2)
    vapor_target = HeaterCooler(
        mode="duty",
        n_species=2,
        pressure_drop=0.0,
        inlet_composition=np.array([0.5, 0.5], dtype=np.float64),
    )
    liquid_target = HeaterCooler(
        mode="duty",
        n_species=2,
        pressure_drop=0.0,
        inlet_composition=np.array([0.5, 0.5], dtype=np.float64),
    )

    flash.vapor_flow = 5.0
    flash.liquid_flow = 7.0
    flash.outlet_temperature = 340.0
    flash.outlet_pressure = 150000.0
    flash.vapor_composition = np.array([0.85, 0.15], dtype=np.float64)
    flash.liquid_composition = np.array([0.1, 0.9], dtype=np.float64)

    step = ThermoBoundaryPropagationStep(
        runtime_context=context,
        config=ThermoBoundaryPropagationConfig(
            stream_port_io_by_node_id={
                "flash": flash,
                "vapor_target": vapor_target,
                "liquid_target": liquid_target,
            },
            feed_streams_by_boundary_id={
                "feed": StreamData(
                    temperature=330.0,
                    pressure=155000.0,
                    mole_fractions=(0.6, 0.4),
                    molar_flow_rate=12.0,
                )
            },
        ),
    )
    conditions = step(
        network=network,
        hydraulic_result=_hydraulic_result(
            {feed_edge: 12.0, vapor_edge: 5.0, liquid_edge: 7.0, "pressure": 101325.0}
        ),
        transport_and_mixing_update=TransportAndMixingUpdate(transport_results={}),
        macro_step_time_s=0.1,
    )

    assert vapor_target.inlet_flow == pytest.approx(5.0)
    assert vapor_target.inlet_temperature == pytest.approx(340.0)
    assert vapor_target.inlet_pressure == pytest.approx(150000.0)
    assert vapor_target.inlet_composition == pytest.approx((0.85, 0.15))

    assert liquid_target.inlet_flow == pytest.approx(7.0)
    assert liquid_target.inlet_temperature == pytest.approx(340.0)
    assert liquid_target.inlet_pressure == pytest.approx(150000.0)
    assert liquid_target.inlet_composition == pytest.approx((0.1, 0.9))

    assert conditions["vapor_target.inlet"].through_molar_flow_rate == pytest.approx(5.0)
    assert conditions["liquid_target.inlet"].through_molar_flow_rate == pytest.approx(7.0)

from __future__ import annotations

from dataclasses import replace
from typing import cast

import numpy as np
import pytest

from modular_simulation.connection.hydraulics.hydraulic_solver import HydraulicTopologyLookup
from modular_simulation.connection.runtime.connection_layer import TransportAndMixingUpdate
from modular_simulation.connection.hydraulics.hydraulic_solver import HydraulicSolveResult
from modular_simulation.connection.topology.network import ConnectionNetwork
from modular_simulation.connection.runtime.thermo_coupling import (
    ThermoBoundaryPropagationConfig,
    ThermoBoundaryPropagationStep,
)
from modular_simulation.connection.domain.state import PortCondition
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


def test_flash_drum_shared_outlet_pressure_ref_uses_compiled_participation_markers() -> None:
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

    compiled = network.compiled
    assert compiled is not None

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

    class _SnapshotStore:
        def __init__(self) -> None:
            self.inlets: dict[tuple[str, str], PortCondition] = {}
            self.outlets: dict[tuple[str, str], PortCondition] = {}

        def record_inlet(self, node_id: str, port_name: str, condition: PortCondition) -> None:
            self.inlets[(node_id, port_name)] = condition

        def record_outlet(self, node_id: str, port_name: str, condition: PortCondition) -> None:
            self.outlets[(node_id, port_name)] = condition

    snapshot_store = _SnapshotStore()
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
            runtime_port_snapshot_store=snapshot_store,
        ),
    )

    class _FlashCompiledHydraulic:
        topology_lookup = HydraulicTopologyLookup(
            line_flow_unknown_by_line={
                feed_edge: feed_edge,
                vapor_edge: vapor_edge,
                liquid_edge: liquid_edge,
            },
            edge_source_pressure_unknown_by_line={
                feed_edge: "pressure__feed_outlet",
            },
            edge_target_pressure_unknown_by_line={
                feed_edge: "pressure__flash_inlet",
                vapor_edge: "pressure__vapor_target_inlet",
                liquid_edge: "pressure__liquid_target_inlet",
            },
            node_pressure_unknown_by_endpoint={
                "feed.outlet": "pressure__feed_outlet",
                "flash.inlet": "pressure__flash_inlet",
                "flash.vapor_outlet": "pressure__flash_outlet",
                "flash.liquid_outlet": "pressure__flash_outlet",
                "vapor_target.inlet": "pressure__vapor_target_inlet",
                "liquid_target.inlet": "pressure__liquid_target_inlet",
            },
            node_pressure_unknown_by_junction={},
            endpoint_role_by_endpoint={
                "flash.inlet": "pressure_state",
                "flash.vapor_outlet": "fixed_pressure_anchor",
                "flash.liquid_outlet": "fixed_pressure_anchor",
                "vapor_target.inlet": "pressure_state",
                "liquid_target.inlet": "pressure_state",
            },
            balancing_group_name_by_endpoint={},
        )

        def resolve_line_flow(
            self, *, line_id: str, hydraulic_result: HydraulicSolveResult
        ) -> float | None:
            value = hydraulic_result.unknowns.get(line_id)
            return None if value is None else float(value)

        def resolve_line_source_pressure(
            self, *, line_id: str, hydraulic_result: HydraulicSolveResult
        ) -> float | None:
            key = self.topology_lookup.edge_source_pressure_unknown_by_line.get(line_id)
            value = None if key is None else hydraulic_result.unknowns.get(key)
            return None if value is None else float(value)

        def resolve_line_target_pressure(
            self, *, line_id: str, hydraulic_result: HydraulicSolveResult
        ) -> float | None:
            key = self.topology_lookup.edge_target_pressure_unknown_by_line.get(line_id)
            value = None if key is None else hydraulic_result.unknowns.get(key)
            return None if value is None else float(value)

        def resolve_endpoint_pressure(
            self, *, endpoint_id: str, hydraulic_result: HydraulicSolveResult
        ) -> float | None:
            key = self.topology_lookup.node_pressure_unknown_by_endpoint.get(endpoint_id)
            value = None if key is None else hydraulic_result.unknowns.get(key)
            return None if value is None else float(value)

        def resolve_junction_pressure(
            self, *, junction_id: str, hydraulic_result: HydraulicSolveResult
        ) -> float | None:
            del junction_id, hydraulic_result
            return None

    network._compiled = replace(compiled, hydraulic=cast(object, _FlashCompiledHydraulic()))

    conditions = step(
        network=network,
        hydraulic_result=_hydraulic_result(
            {
                feed_edge: 12.0,
                vapor_edge: 5.0,
                liquid_edge: 7.0,
                "pressure__feed_outlet": 155000.0,
                "pressure__flash_inlet": 150000.0,
                "pressure__flash_outlet": 147500.0,
                "pressure__vapor_target_inlet": 149000.0,
                "pressure__liquid_target_inlet": 148000.0,
            }
        ),
        transport_and_mixing_update=TransportAndMixingUpdate(transport_results={}),
        macro_step_time_s=0.1,
    )

    vapor_outlet = snapshot_store.outlets[("flash", "vapor_outlet")]
    liquid_outlet = snapshot_store.outlets[("flash", "liquid_outlet")]
    assert vapor_outlet.state.pressure == pytest.approx(147500.0)
    assert liquid_outlet.state.pressure == pytest.approx(147500.0)
    assert vapor_outlet.state.pressure == liquid_outlet.state.pressure

    assert conditions["vapor_target.inlet"].state.pressure == pytest.approx(149000.0)
    assert conditions["liquid_target.inlet"].state.pressure == pytest.approx(148000.0)
    assert vapor_target.inlet_pressure == pytest.approx(149000.0)
    assert liquid_target.inlet_pressure == pytest.approx(148000.0)

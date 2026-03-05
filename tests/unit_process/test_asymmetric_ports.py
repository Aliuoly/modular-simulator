from __future__ import annotations

import numpy as np

from modular_simulation.connection.asymmetric_adapter import (
    AsymmetricPortAdapter,
    ConvergingPortAdapter,
)
from modular_simulation.connection.connection_layer import TransportAndMixingUpdate
from modular_simulation.connection.hydraulic_compile import HydraulicCompileLifecycle
from modular_simulation.connection.hydraulic_solver import (
    HydraulicSolveResult,
    HydraulicSystemDefinition,
    LinearResidualEquation,
)
from modular_simulation.connection.network import ConnectionNetwork
from modular_simulation.connection.process_binding import ProcessBinding
from modular_simulation.connection.thermo_coupling import ThermoBoundaryPropagationStep
from modular_simulation.connection.transport import LagTransportState, LagTransportUpdateResult
from modular_simulation.thermodynamics.runtime_context import SimulationRuntimeContext


def _linear_equation(
    residual_name: str,
    coefficients: dict[str, float],
    *,
    constant: float = 0.0,
) -> LinearResidualEquation:
    return LinearResidualEquation(
        residual_name=residual_name,
        coefficients=coefficients,
        constant=constant,
    )


def _valid_system() -> HydraulicSystemDefinition:
    return HydraulicSystemDefinition(
        equations=(),
        linear_residual_equations=(
            _linear_equation("ref", {"pressure": 1.0}, constant=-5.0),
            _linear_equation("balance", {"pressure": 1.0, "flow": -1.0}),
        ),
    )


def _hydraulic_result(unknowns: dict[str, float]) -> HydraulicSolveResult:
    return HydraulicSolveResult(
        converged=True,
        iterations=2,
        residual_norm=1.0e-10,
        solution_vector=np.asarray(list(unknowns.values()), dtype=np.float64),
        unknowns=unknowns,
        unknown_index_map={name: index for index, name in enumerate(unknowns.keys())},
        residual_index_map={"balance": 0, "ref": 1},
    )


def test_flash_drum_compile() -> None:
    context = SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    network = ConnectionNetwork(
        compile_lifecycle=HydraulicCompileLifecycle(),
        hydraulic_system_builder=lambda topology: _valid_system(),
    )
    network.add_boundary_source("feed")
    network.add_process(
        "flash", inlet_ports=("inlet",), outlet_ports=("vapor_outlet", "liquid_outlet")
    )
    network.add_process("vapor_consumer", inlet_ports=("inlet",), outlet_ports=("outlet",))
    network.add_process("liquid_consumer", inlet_ports=("inlet",), outlet_ports=("outlet",))
    _ = network.connect("feed", "flash.inlet")
    vapor_edge = network.connect("flash.vapor_outlet", "vapor_consumer.inlet")
    liquid_edge = network.connect("flash.liquid_outlet", "liquid_consumer.inlet")

    compiled = network.compile()
    assert compiled.hydraulic is not None
    flash_binding = compiled.process_bindings["flash"]
    assert isinstance(flash_binding, AsymmetricPortAdapter)
    flash_binding.bind_inlets({"inlet": 2.0})
    flash_binding.bind_outlets(
        {
            "vapor_outlet": {"role": "outlet", "flow": 1.4, "composition": (0.8, 0.2)},
            "liquid_outlet": {"role": "outlet", "flow": 0.6, "composition": (0.1, 0.9)},
        }
    )
    flash_binding.validate()

    step = ThermoBoundaryPropagationStep(runtime_context=context)
    conditions = step(
        network=network,
        hydraulic_result=_hydraulic_result(
            {vapor_edge: 1.4, liquid_edge: 0.6, "pressure": 101325.0}
        ),
        transport_and_mixing_update=TransportAndMixingUpdate(
            transport_results={
                vapor_edge: LagTransportUpdateResult(
                    state=LagTransportState(composition=(0.85, 0.15), temperature=345.0),
                    update_fraction=0.5,
                    flow_scale=1.0,
                    flow_sign_changed=False,
                    held_for_near_zero_flow=False,
                ),
                liquid_edge: LagTransportUpdateResult(
                    state=LagTransportState(composition=(0.05, 0.95), temperature=320.0),
                    update_fraction=0.5,
                    flow_scale=1.0,
                    flow_sign_changed=False,
                    held_for_near_zero_flow=False,
                ),
            }
        ),
        macro_step_time_s=0.1,
    )

    assert conditions["vapor_consumer.inlet"].through_molar_flow_rate == 1.4
    assert conditions["liquid_consumer.inlet"].through_molar_flow_rate == 0.6
    assert tuple(conditions["vapor_consumer.inlet"].state.mole_fractions) == (0.85, 0.15)
    assert tuple(conditions["liquid_consumer.inlet"].state.mole_fractions) == (0.05, 0.95)


def test_distillation_compile() -> None:
    context = SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    network = ConnectionNetwork(
        compile_lifecycle=HydraulicCompileLifecycle(),
        hydraulic_system_builder=lambda topology: _valid_system(),
    )
    network.add_boundary_source("feed")
    network.add_process("column", inlet_ports=("inlet",), outlet_ports=("distillate", "bottoms"))
    network.add_process("distillate_consumer", inlet_ports=("inlet",), outlet_ports=("outlet",))
    network.add_process("bottoms_consumer", inlet_ports=("inlet",), outlet_ports=("outlet",))
    _ = network.connect("feed", "column.inlet")
    distillate_edge = network.connect("column.distillate", "distillate_consumer.inlet")
    bottoms_edge = network.connect("column.bottoms", "bottoms_consumer.inlet")

    compiled = network.compile()
    assert compiled.hydraulic is not None
    column_binding = compiled.process_bindings["column"]
    assert isinstance(column_binding, AsymmetricPortAdapter)
    column_binding.bind_inlets({"inlet": 3.0})
    column_binding.bind_outlets(
        {
            "distillate": {"role": "outlet", "flow": 1.1, "composition": (0.9, 0.1)},
            "bottoms": {"role": "outlet", "flow": 1.9, "composition": (0.2, 0.8)},
        }
    )
    column_binding.validate()

    step = ThermoBoundaryPropagationStep(runtime_context=context)
    conditions = step(
        network=network,
        hydraulic_result=_hydraulic_result(
            {distillate_edge: 1.1, bottoms_edge: 1.9, "pressure": 101325.0}
        ),
        transport_and_mixing_update=TransportAndMixingUpdate(
            transport_results={
                distillate_edge: LagTransportUpdateResult(
                    state=LagTransportState(composition=(0.92, 0.08), temperature=360.0),
                    update_fraction=0.5,
                    flow_scale=1.0,
                    flow_sign_changed=False,
                    held_for_near_zero_flow=False,
                ),
                bottoms_edge: LagTransportUpdateResult(
                    state=LagTransportState(composition=(0.18, 0.82), temperature=390.0),
                    update_fraction=0.5,
                    flow_scale=1.0,
                    flow_sign_changed=False,
                    held_for_near_zero_flow=False,
                ),
            }
        ),
        macro_step_time_s=0.1,
    )

    assert conditions["distillate_consumer.inlet"].through_molar_flow_rate == 1.1
    assert conditions["bottoms_consumer.inlet"].through_molar_flow_rate == 1.9


def test_heat_exchanger_uses_standard_equal_port_binding() -> None:
    network = ConnectionNetwork()
    network.add_process(
        "hx",
        inlet_ports=("hot_inlet", "cold_inlet"),
        outlet_ports=("hot_outlet", "cold_outlet"),
    )

    compiled = network.compile()
    assert isinstance(compiled.process_bindings["hx"], ProcessBinding)


def test_mixer_like_multi_inlet_single_outlet_binding_compiles_and_routes() -> None:
    context = SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    network = ConnectionNetwork(
        compile_lifecycle=HydraulicCompileLifecycle(),
        hydraulic_system_builder=lambda topology: _valid_system(),
    )
    network.add_boundary_source("feed_a")
    network.add_boundary_source("feed_b")
    network.add_process("mixer", inlet_ports=("inlet_1", "inlet_2"), outlet_ports=("outlet",))
    network.add_process("consumer", inlet_ports=("inlet",), outlet_ports=("outlet",))
    _ = network.connect("feed_a", "mixer.inlet_1")
    _ = network.connect("feed_b", "mixer.inlet_2")
    product_edge = network.connect("mixer.outlet", "consumer.inlet")

    compiled = network.compile()
    mixer_binding = compiled.process_bindings["mixer"]
    assert isinstance(mixer_binding, ConvergingPortAdapter)

    mixer_binding.set_inlet("inlet_1", 1.25)
    mixer_binding.set_inlet("inlet_2", 0.75)
    mixer_binding.bind_outlets(
        {
            "outlet": {
                "role": "outlet",
                "flow": 2.0,
                "composition": (0.4, 0.6),
            }
        }
    )
    mixer_binding.validate()

    outlet_payload = mixer_binding.get_outlet("outlet")
    assert outlet_payload["outlet_flow"] == 2.0

    step = ThermoBoundaryPropagationStep(runtime_context=context)
    conditions = step(
        network=network,
        hydraulic_result=_hydraulic_result({product_edge: 2.0, "pressure": 101325.0}),
        transport_and_mixing_update=TransportAndMixingUpdate(transport_results={}),
        macro_step_time_s=0.1,
    )

    assert conditions["consumer.inlet"].through_molar_flow_rate == 2.0
    assert tuple(conditions["consumer.inlet"].state.mole_fractions) == (0.4, 0.6)

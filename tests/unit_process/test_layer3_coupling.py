from __future__ import annotations

import math
from dataclasses import replace
import numpy as np
import pytest
from typing import cast

from modular_simulation.connection.runtime.connection_layer import TransportAndMixingUpdate
from modular_simulation.connection.hydraulics.hydraulic_compile import HydraulicCompileLifecycle
from modular_simulation.connection.hydraulics.hydraulic_solver import (
    HydraulicTopologyLookup,
    HydraulicSolveResult,
    HydraulicSystemDefinition,
    LinearResidualEquation,
)
from modular_simulation.connection.topology.network import ConnectionNetwork
from modular_simulation.connection.topology.process_binding import BindingError
from modular_simulation.connection.runtime.runtime import (
    ConnectionRuntimeOrchestrator,
    ConnectionRuntimeStepResult,
)
from modular_simulation.connection.domain.state import MaterialState, PortCondition
from modular_simulation.connection.runtime.thermo_coupling import (
    ThermoBoundaryPropagationConfig,
    ThermoBoundaryPropagationStep,
)
from modular_simulation.connection.domain.transport import (
    LagTransportState,
    LagTransportUpdateResult,
)
from modular_simulation.thermodynamics.property_package import FlashResult, PropertyPackage
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


def _network(runtime: ConnectionRuntimeOrchestrator) -> tuple[ConnectionNetwork, str]:
    network = ConnectionNetwork(
        compile_lifecycle=HydraulicCompileLifecycle(),
        hydraulic_system_builder=lambda topology: _valid_system(),
        runtime_orchestrator=runtime,
    )
    network.add_boundary_source("feed")
    network.add_process("unit_a", inlet_ports=("inlet",), outlet_ports=("outlet",))
    network.add_process("unit_b", inlet_ports=("inlet",), outlet_ports=("outlet",))
    network.add_boundary_sink("product")
    _ = network.connect("feed", "unit_a.inlet")
    edge_a_to_b = network.connect("unit_a.outlet", "unit_b.inlet")
    _ = network.connect("unit_b.outlet", "product")
    _ = network.compile()
    return network, edge_a_to_b


def _hydraulic_result(edge_id: str, edge_flow: float) -> HydraulicSolveResult:
    return HydraulicSolveResult(
        converged=True,
        iterations=2,
        residual_norm=1.0e-10,
        solution_vector=np.asarray([edge_flow, 5.0], dtype=np.float64),
        unknowns={edge_id: edge_flow, "node_pressure": 5.0},
        unknown_index_map={edge_id: 0, "node_pressure": 1},
        residual_index_map={"balance": 0, "ref": 1},
    )


def _transport_update(
    edge_id: str, composition: tuple[float, ...], temperature: float
) -> TransportAndMixingUpdate:
    return TransportAndMixingUpdate(
        transport_results={
            edge_id: LagTransportUpdateResult(
                state=LagTransportState(composition=composition, temperature=temperature),
                update_fraction=0.5,
                flow_scale=1.0,
                flow_sign_changed=False,
                held_for_near_zero_flow=False,
            )
        }
    )


def _network_two_feeds(
    runtime: ConnectionRuntimeOrchestrator,
) -> tuple[ConnectionNetwork, str, str]:
    network = ConnectionNetwork(
        compile_lifecycle=HydraulicCompileLifecycle(),
        hydraulic_system_builder=lambda topology: _valid_system(),
        runtime_orchestrator=runtime,
    )
    network.add_process("unit_a", inlet_ports=("inlet",), outlet_ports=("outlet",))
    network.add_process("unit_c", inlet_ports=("inlet",), outlet_ports=("outlet",))
    network.add_process("unit_b", inlet_ports=("inlet",), outlet_ports=("outlet",))
    network.add_boundary_sink("product")
    edge_feed_1 = network.connect("unit_a.outlet", "unit_b.inlet")
    edge_feed_2 = network.connect("unit_c.outlet", "unit_b.inlet")
    _ = network.connect("unit_b.outlet", "product")
    _ = network.compile()
    return network, edge_feed_1, edge_feed_2


class _QuadraticEnthalpyPackage:
    def flash_tp(self, T: float, P: float, z: tuple[float, ...]) -> FlashResult:
        return FlashResult(
            temperature=T,
            pressure=P,
            vapor_fraction=0.0,
            phase="liquid",
            liquid_composition=z,
            vapor_composition=None,
            enthalpy_molar=T * T,
            entropy_molar=T,
            liquid_density=1000.0,
            vapor_density=None,
            K_values=None,
        )

    def flash_ph(self, P: float, H: float, z: tuple[float, ...]) -> FlashResult:
        temperature = math.sqrt(H)
        return FlashResult(
            temperature=temperature,
            pressure=P,
            vapor_fraction=0.0,
            phase="liquid",
            liquid_composition=z,
            vapor_composition=None,
            enthalpy_molar=H,
            entropy_molar=temperature,
            liquid_density=1000.0,
            vapor_density=None,
            K_values=None,
        )

    def flash_ps(self, P: float, S: float, z: tuple[float, ...]) -> FlashResult:
        return self.flash_tp(T=S, P=P, z=z)

    def enthalpy(self, T: float, P: float, z: tuple[float, ...], phase: str) -> float:
        del P, z, phase
        return T * T

    def entropy(self, T: float, P: float, z: tuple[float, ...], phase: str) -> float:
        del P, z, phase
        return T

    def density(self, T: float, P: float, z: tuple[float, ...], phase: str) -> float:
        del T, P, z, phase
        return 1000.0

    def heat_capacity_cp(self, T: float, P: float, z: tuple[float, ...], phase: str) -> float:
        del T, P, z, phase
        return 1.0

    def molecular_weight(self, z: tuple[float, ...]) -> float:
        return float(sum(z))

    @property
    def species_cas(self) -> tuple[str, ...]:
        return ("7732-18-5", "64-17-5")


def test_auto_propagation_two_units() -> None:
    context = SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    runtime = ConnectionRuntimeOrchestrator(runtime_context=context)
    network, edge_a_to_b = _network(runtime)

    compiled = network.compiled
    assert compiled is not None
    assert compiled.hydraulic is not None
    binding_a = compiled.process_bindings["unit_a"]
    binding_a.bind_inlets({"inlet": 1.5})
    binding_a.bind_outlets(
        {
            "outlet": {
                "role": "outlet",
                "flow": 1.5,
                "composition": (0.25, 0.75),
            }
        }
    )

    step = ThermoBoundaryPropagationStep(runtime_context=context)
    auto_conditions = step(
        network=network,
        hydraulic_result=_hydraulic_result(edge_a_to_b, 1.5),
        transport_and_mixing_update=_transport_update(edge_a_to_b, (0.25, 0.75), 337.0),
        macro_step_time_s=0.2,
    )
    condition = auto_conditions["unit_b.inlet"]
    assert condition.through_molar_flow_rate == pytest.approx(1.5)
    assert condition.state.temperature == pytest.approx(337.0)
    assert condition.state.pressure == pytest.approx(101325.0)
    assert condition.state.mole_fractions == pytest.approx((0.25, 0.75))
    assert condition.state.species_ids == context.species_registry.cas_list
    assert condition.state.phase in {"vapor", "liquid", "two-phase"}
    assert condition.state.enthalpy_molar is not None

    runtime_with_auto = ConnectionRuntimeOrchestrator(
        runtime_context=context,
        hydraulic_solve_step=(
            lambda *, network, macro_step_time_s: _hydraulic_result(edge_a_to_b, 1.5)
        ),
        transport_and_mixing_step=(
            lambda *, network, hydraulic_result, macro_step_time_s: _transport_update(
                edge_a_to_b,
                composition=(0.25, 0.75),
                temperature=337.0,
            )
        ),
    )
    network_with_auto, _ = _network(runtime_with_auto)
    compiled_with_auto = network_with_auto.compiled
    assert compiled_with_auto is not None
    binding_a_auto = compiled_with_auto.process_bindings["unit_a"]
    binding_a_auto.bind_inlets({"inlet": 1.5})
    binding_a_auto.bind_outlets(
        {
            "outlet": {
                "role": "outlet",
                "flow": 1.5,
                "composition": (0.25, 0.75),
            }
        }
    )

    runtime_result = cast(
        ConnectionRuntimeStepResult, network_with_auto.step(macro_step_time_s=0.2)
    )
    assert runtime_result.bookkeeping.updated_port_keys == ("unit_b.inlet",)
    unit_b_binding = cast(object, compiled_with_auto.process_bindings["unit_b"])
    assert getattr(unit_b_binding, "_inlet_bindings")["inlet"] == pytest.approx(1.5)


def test_manual_mode_and_hybrid_override() -> None:
    context = SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    runtime = ConnectionRuntimeOrchestrator(runtime_context=context)
    network, edge_a_to_b = _network(runtime)

    compiled = network.compiled
    assert compiled is not None
    assert compiled.hydraulic is not None
    binding_a = compiled.process_bindings["unit_a"]
    binding_a.bind_inlets({"inlet": 2.0})
    binding_a.bind_outlets(
        {
            "outlet": {
                "role": "outlet",
                "flow": 2.0,
                "composition": (0.7, 0.3),
            }
        }
    )

    manual_port = PortCondition(
        state=MaterialState(
            pressure=111000.0,
            temperature=320.0,
            mole_fractions=(0.6, 0.4),
            species_ids=context.species_registry.cas_list,
            phase="liquid",
        ),
        species_ids=context.species_registry.cas_list,
        through_molar_flow_rate=0.8,
        macro_step_time_s=0.3,
    )

    manual_step = ThermoBoundaryPropagationStep(
        runtime_context=context,
        config=ThermoBoundaryPropagationConfig(
            mode="manual",
            manual_port_conditions={"unit_b.inlet": manual_port},
        ),
    )
    manual_conditions = manual_step(
        network=network,
        hydraulic_result=_hydraulic_result(edge_a_to_b, 2.0),
        transport_and_mixing_update=_transport_update(edge_a_to_b, (0.7, 0.3), 330.0),
        macro_step_time_s=0.3,
    )
    assert manual_conditions == {"unit_b.inlet": manual_port}

    hybrid_step = ThermoBoundaryPropagationStep(
        runtime_context=context,
        config=ThermoBoundaryPropagationConfig(
            mode="hybrid",
            auto_propagate_energy=False,
            manual_override_hook=lambda auto_map: {
                "unit_b.inlet": auto_map["unit_b.inlet"].model_copy(
                    update={"through_molar_flow_rate": 0.8}
                )
            },
        ),
    )
    hybrid_conditions = hybrid_step(
        network=network,
        hydraulic_result=_hydraulic_result(edge_a_to_b, 2.0),
        transport_and_mixing_update=_transport_update(edge_a_to_b, (0.7, 0.3), 330.0),
        macro_step_time_s=0.3,
    )
    assert hybrid_conditions["unit_b.inlet"].through_molar_flow_rate == pytest.approx(0.8)
    assert hybrid_conditions["unit_b.inlet"].state.temperature == pytest.approx(330.0)


def test_runtime_without_context_remains_noop_boundary_behavior() -> None:
    runtime = ConnectionRuntimeOrchestrator(
        hydraulic_solve_step=(
            lambda *, network, macro_step_time_s: _hydraulic_result("edge_0002", 1.0)
        ),
        transport_and_mixing_step=(
            lambda *, network, hydraulic_result, macro_step_time_s: _transport_update(
                "edge_0002",
                (0.5, 0.5),
                315.0,
            )
        ),
    )
    network, _ = _network(runtime)

    result = cast(ConnectionRuntimeStepResult, network.step(macro_step_time_s=0.1))
    assert result.bookkeeping.updated_port_keys == ()


def test_auto_propagation_uses_pressure_signal_and_falls_back_to_default() -> None:
    context = SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    runtime = ConnectionRuntimeOrchestrator(runtime_context=context)
    network, edge_a_to_b = _network(runtime)

    compiled = network.compiled
    assert compiled is not None
    assert compiled.hydraulic is not None
    binding_a = compiled.process_bindings["unit_a"]
    binding_a.bind_inlets({"inlet": 1.0})
    binding_a.bind_outlets(
        {
            "outlet": {
                "role": "outlet",
                "flow": 1.0,
                "composition": (0.4, 0.6),
            }
        }
    )

    step = ThermoBoundaryPropagationStep(runtime_context=context)
    hydraulic_with_pressure = HydraulicSolveResult(
        converged=True,
        iterations=2,
        residual_norm=1.0e-10,
        solution_vector=np.asarray([1.0, 250000.0], dtype=np.float64),
        unknowns={edge_a_to_b: 1.0, "pressure": 250000.0},
        unknown_index_map={edge_a_to_b: 0, "pressure": 1},
        residual_index_map={"balance": 0, "ref": 1},
    )
    signal_conditions = step(
        network=network,
        hydraulic_result=hydraulic_with_pressure,
        transport_and_mixing_update=_transport_update(edge_a_to_b, (0.4, 0.6), 330.0),
        macro_step_time_s=0.1,
    )
    assert signal_conditions["unit_b.inlet"].state.pressure == pytest.approx(250000.0)

    fallback_step = ThermoBoundaryPropagationStep(
        runtime_context=context,
        config=ThermoBoundaryPropagationConfig(default_pressure_pa=123456.0),
    )
    no_signal_conditions = fallback_step(
        network=network,
        hydraulic_result=_hydraulic_result(edge_a_to_b, 1.0),
        transport_and_mixing_update=_transport_update(edge_a_to_b, (0.4, 0.6), 330.0),
        macro_step_time_s=0.1,
    )
    assert no_signal_conditions["unit_b.inlet"].state.pressure == pytest.approx(123456.0)


def test_declared_pressure_coupled_endpoint_requires_compiled_mapping_before_runtime_fallback() -> (
    None
):
    context = SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    runtime = ConnectionRuntimeOrchestrator(runtime_context=context)
    network, edge_a_to_b = _network(runtime)

    compiled = network.compiled
    assert compiled is not None
    assert compiled.hydraulic is not None
    compiled_hydraulic = compiled.hydraulic
    binding_a = compiled.process_bindings["unit_a"]
    binding_a.bind_inlets({"inlet": 1.0})
    binding_a.bind_outlets(
        {
            "outlet": {
                "role": "outlet",
                "flow": 1.0,
                "composition": (0.4, 0.6),
            }
        }
    )

    declared_lookup = HydraulicTopologyLookup(
        line_flow_unknown_by_line={edge_a_to_b: edge_a_to_b},
        edge_source_pressure_unknown_by_line={edge_a_to_b: "pressure__unit_a_outlet"},
        edge_target_pressure_unknown_by_line={edge_a_to_b: "pressure__unit_b_inlet"},
        node_pressure_unknown_by_endpoint={
            "unit_a.outlet": "pressure__unit_a_outlet",
            "unit_b.inlet": "pressure__unit_b_inlet",
        },
        node_pressure_unknown_by_junction={},
        endpoint_role_by_endpoint={
            "unit_a.outlet": "pressure_state",
            "unit_b.inlet": "pressure_state",
        },
        balancing_group_name_by_endpoint={},
    )
    network._compiled = replace(
        compiled,
        hydraulic=replace(
            compiled_hydraulic,
            system=replace(compiled_hydraulic.system, topology_lookup=declared_lookup),
        ),
    )

    step = ThermoBoundaryPropagationStep(runtime_context=context)
    with pytest.raises(BindingError, match="Missing compiled hydraulic pressure mapping"):
        _ = step(
            network=network,
            hydraulic_result=HydraulicSolveResult(
                converged=True,
                iterations=2,
                residual_norm=1.0e-10,
                solution_vector=np.asarray([1.0, 5.0], dtype=np.float64),
                unknowns={edge_a_to_b: 1.0, "pressure": 5.0},
                unknown_index_map={edge_a_to_b: 0, "pressure": 1},
                residual_index_map={"balance": 0, "ref": 1},
            ),
            transport_and_mixing_update=_transport_update(edge_a_to_b, (0.4, 0.6), 330.0),
            macro_step_time_s=0.1,
        )


def test_enthalpy_correct_mixing() -> None:
    base_context = SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    context = SimulationRuntimeContext(
        species_registry=base_context.species_registry,
        property_package=cast(PropertyPackage, _QuadraticEnthalpyPackage()),
        species_context=base_context.species_context,
    )
    runtime = ConnectionRuntimeOrchestrator(runtime_context=context)
    network, edge_feed_1, edge_feed_2 = _network_two_feeds(runtime)

    compiled = network.compiled
    assert compiled is not None
    feed_1_binding = compiled.process_bindings["unit_a"]
    feed_1_binding.bind_inlets({"inlet": 1.0})
    feed_1_binding.bind_outlets(
        {
            "outlet": {
                "role": "outlet",
                "flow": 1.0,
                "composition": (0.5, 0.5),
            }
        }
    )
    feed_2_binding = compiled.process_bindings["unit_c"]
    feed_2_binding.bind_inlets({"inlet": 1.0})
    feed_2_binding.bind_outlets(
        {
            "outlet": {
                "role": "outlet",
                "flow": 1.0,
                "composition": (0.5, 0.5),
            }
        }
    )

    step = ThermoBoundaryPropagationStep(runtime_context=context)
    hydraulic_result = HydraulicSolveResult(
        converged=True,
        iterations=2,
        residual_norm=1.0e-10,
        solution_vector=np.asarray([1.0, 1.0, 5.0], dtype=np.float64),
        unknowns={edge_feed_1: 1.0, edge_feed_2: 1.0, "node_pressure": 5.0},
        unknown_index_map={edge_feed_1: 0, edge_feed_2: 1, "node_pressure": 2},
        residual_index_map={"balance": 0, "ref": 1},
    )
    transport_update = TransportAndMixingUpdate(
        transport_results={
            edge_feed_1: LagTransportUpdateResult(
                state=LagTransportState(composition=(0.5, 0.5), temperature=300.0),
                update_fraction=0.5,
                flow_scale=1.0,
                flow_sign_changed=False,
                held_for_near_zero_flow=False,
            ),
            edge_feed_2: LagTransportUpdateResult(
                state=LagTransportState(composition=(0.5, 0.5), temperature=500.0),
                update_fraction=0.5,
                flow_scale=1.0,
                flow_sign_changed=False,
                held_for_near_zero_flow=False,
            ),
        }
    )
    mixed_conditions = step(
        network=network,
        hydraulic_result=hydraulic_result,
        transport_and_mixing_update=transport_update,
        macro_step_time_s=0.1,
    )
    mixed = mixed_conditions["unit_b.inlet"]

    linear_temperature = (300.0 + 500.0) / 2.0
    enthalpy_temperature = math.sqrt((300.0 * 300.0 + 500.0 * 500.0) / 2.0)

    assert mixed.through_molar_flow_rate == pytest.approx(2.0)
    assert mixed.state.temperature == pytest.approx(enthalpy_temperature)
    assert mixed.state.temperature != pytest.approx(linear_temperature)
    assert mixed.state.enthalpy_molar == pytest.approx(enthalpy_temperature * enthalpy_temperature)


def test_species_projection_propagation() -> None:
    context = SimulationRuntimeContext.create(species_names=["water", "ethanol", "methane"])
    context.species_context.register_subsystem("unit_a", ["ethanol", "water"])
    context.species_context.register_subsystem("unit_b", ["water", "ethanol", "methane"])
    runtime = ConnectionRuntimeOrchestrator(runtime_context=context)
    network, edge_a_to_b = _network(runtime)

    compiled = network.compiled
    assert compiled is not None
    binding_a = compiled.process_bindings["unit_a"]
    binding_a.bind_inlets({"inlet": 1.5})
    binding_a.bind_outlets(
        {
            "outlet": {
                "role": "outlet",
                "flow": 1.5,
                "composition": (0.2, 0.8),
            }
        }
    )

    step = ThermoBoundaryPropagationStep(runtime_context=context)
    auto_conditions = step(
        network=network,
        hydraulic_result=_hydraulic_result(edge_a_to_b, 1.5),
        transport_and_mixing_update=_transport_update(edge_a_to_b, (0.2, 0.8), 337.0),
        macro_step_time_s=0.2,
    )
    condition = auto_conditions["unit_b.inlet"]
    assert condition.state.mole_fractions == pytest.approx((0.8, 0.2, 0.0))
    assert condition.state.species_ids == context.species_registry.cas_list


def test_species_projection_incompatible_sets_raise() -> None:
    context = SimulationRuntimeContext.create(species_names=["water", "ethanol", "methane"])
    context.species_context.register_subsystem("unit_a", ["ethanol", "water"])
    context.species_context.register_subsystem("unit_b", ["water", "methane"])
    runtime = ConnectionRuntimeOrchestrator(runtime_context=context)
    network, edge_a_to_b = _network(runtime)

    compiled = network.compiled
    assert compiled is not None
    binding_a = compiled.process_bindings["unit_a"]
    binding_a.bind_inlets({"inlet": 1.0})
    binding_a.bind_outlets(
        {
            "outlet": {
                "role": "outlet",
                "flow": 1.0,
                "composition": (0.4, 0.6),
            }
        }
    )

    step = ThermoBoundaryPropagationStep(runtime_context=context)
    with pytest.raises(ValueError, match="Incompatible species mapping"):
        _ = step(
            network=network,
            hydraulic_result=_hydraulic_result(edge_a_to_b, 1.0),
            transport_and_mixing_update=_transport_update(edge_a_to_b, (0.4, 0.6), 330.0),
            macro_step_time_s=0.2,
        )

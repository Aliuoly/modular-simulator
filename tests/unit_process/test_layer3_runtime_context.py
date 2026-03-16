# pyright: reportMissingImports=false

from __future__ import annotations

from dataclasses import dataclass

from modular_simulation.connection.runtime.connected_plant_orchestrator import (
    ConnectedPlantOrchestrator,
)
from modular_simulation.connection.topology.network import ConnectionNetwork
from modular_simulation.connection.runtime.runtime import ConnectionRuntimeOrchestrator
from modular_simulation.connection.topology.subsystem_descriptor import SubsystemRuntimeDescriptor
from modular_simulation.thermodynamics import (
    PowerLawRateLaw,
    Reaction,
    ReactionSet,
    SimulationRuntimeContext,
)


@dataclass
class _NoOpSubsystem:
    descriptor: SubsystemRuntimeDescriptor

    def run_sensor_phase(self) -> None:
        return

    def run_calculation_phase(self) -> None:
        return

    def run_controller_phase(self) -> None:
        return

    def run_process_phase(self, duration: float) -> None:
        del duration
        return


def _network(runtime_orchestrator: ConnectionRuntimeOrchestrator) -> ConnectionNetwork:
    network = ConnectionNetwork(runtime_orchestrator=runtime_orchestrator)
    network.add_process("reactor", inlet_ports=("feed",), outlet_ports=("product",))
    network.add_boundary_source("feed_boundary")
    network.add_boundary_sink("product_boundary")
    _ = network.connect("feed_boundary", "reactor.feed")
    _ = network.connect("reactor.product", "product_boundary")
    return network


def test_simulation_runtime_context_factory_creates_thermo_and_reaction_accessors() -> None:
    dehydration = ReactionSet(
        reactions=(
            Reaction(
                name="dehydration",
                stoichiometry={"ethanol": -1.0, "water": 1.0},
                rate_law=PowerLawRateLaw(
                    k_ref=0.3,
                    orders={"ethanol": 1.0},
                ),
            ),
        )
    )

    context = SimulationRuntimeContext.create(
        species_names=["water", "ethanol"],
        eos_model="PR",
        reactions={"reactor_a": dehydration},
    )

    assert context.species_registry.n_species == 2
    assert context.get_property_package() is context.property_package
    assert context.property_package.species_cas == context.species_registry.cas_list
    assert context.get_reactions("reactor_a") is dehydration
    assert context.get_reactions("missing_subsystem").reactions == ()


def test_runtime_orchestrator_runtime_context_defaults_to_none_and_accepts_injection() -> None:
    default_runtime = ConnectionRuntimeOrchestrator()
    assert default_runtime.runtime_context is None

    context = SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    configured_runtime = ConnectionRuntimeOrchestrator(runtime_context=context)
    assert configured_runtime.runtime_context is context


def test_connected_plant_orchestrator_preserves_default_none_and_can_propagate_context() -> None:
    descriptor = SubsystemRuntimeDescriptor(
        descriptor_id="subsystem_a",
        process_id="reactor",
        inlet_ports=("feed",),
        outlet_ports=("product",),
        publication_map={"subsystem_a/temperature": 300.0},
    )
    subsystem = _NoOpSubsystem(descriptor=descriptor)

    runtime = ConnectionRuntimeOrchestrator()
    orchestrator_without_context = ConnectedPlantOrchestrator(
        subsystems=(subsystem,),
        network=_network(runtime),
        runtime_orchestrator=runtime,
    )
    assert orchestrator_without_context.runtime_context is None
    assert runtime.runtime_context is None

    context = SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    orchestrator_with_context = ConnectedPlantOrchestrator(
        subsystems=(subsystem,),
        network=_network(runtime),
        runtime_orchestrator=runtime,
        runtime_context=context,
    )
    assert orchestrator_with_context.runtime_context is context
    assert runtime.runtime_context is context

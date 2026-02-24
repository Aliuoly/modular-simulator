import pytest
from dataclasses import dataclass
from typing import Callable
import numpy as np

from modular_simulation.connection.connected_plant_orchestrator import ConnectedPlantOrchestrator
from modular_simulation.connection.connected_plant_orchestrator import ConnectedPlantPhaseHooks
from modular_simulation.connection.connection_layer import TransportAndMixingUpdate
from modular_simulation.connection.runtime import ConnectionRuntimeOrchestrator
from modular_simulation.connection.network import ConnectionNetwork
from modular_simulation.connection.subsystem_descriptor import SubsystemRuntimeDescriptor
from modular_simulation.validation.exceptions import MeasurableConfigurationError


from modular_simulation.connection.hydraulic_solver import HydraulicSolveResult


def _hydraulic_result() -> HydraulicSolveResult:
    return HydraulicSolveResult(
        converged=True,
        iterations=1,
        residual_norm=1.0e-10,
        solution_vector=np.asarray([1.0, 5.0], dtype=np.float64),
        unknowns={"flow": 1.0, "pressure": 5.0},
        unknown_index_map={"flow": 0, "pressure": 1},
        residual_index_map={"balance": 0, "ref": 1},
    )


@dataclass
class _FakeSubsystem:
    descriptor: SubsystemRuntimeDescriptor
    calls: list[str]
    on_sensor_phase: Callable[[], None] | None = None

    def run_sensor_phase(self) -> None:
        self.calls.append(f"{self.descriptor.descriptor_id}:sensor")
        if self.on_sensor_phase is not None:
            self.on_sensor_phase()

    def run_calculation_phase(self) -> None:
        self.calls.append(f"{self.descriptor.descriptor_id}:calculation")

    def run_controller_phase(self) -> None:
        self.calls.append(f"{self.descriptor.descriptor_id}:controller")

    def run_process_phase(self, duration: float) -> None:
        del duration
        self.calls.append(f"{self.descriptor.descriptor_id}:process")

    def snapshot_published_measurements(self) -> dict[str, float]:
        return dict(self.descriptor.publication_map)


def _network(
    runtime: ConnectionRuntimeOrchestrator, process_ids: tuple[str, ...]
) -> ConnectionNetwork:
    network = ConnectionNetwork(runtime_orchestrator=runtime)
    for process_id in process_ids:
        feed_boundary = f"{process_id}_feed"
        product_boundary = f"{process_id}_product"
        network.add_process(process_id, inlet_ports=("feed",), outlet_ports=("product",))
        network.add_boundary_source(feed_boundary)
        network.add_boundary_sink(product_boundary)
        _ = network.connect(feed_boundary, f"{process_id}.feed")
        _ = network.connect(f"{process_id}.product", product_boundary)
    _ = network.compile()
    return network


def test_cross_subsystem_inputs_resolve_and_compute():
    runtime = ConnectionRuntimeOrchestrator(
        hydraulic_solve_step=lambda *, network, macro_step_time_s: _hydraulic_result(),
        transport_and_mixing_step=(
            lambda *, network, hydraulic_result, macro_step_time_s: TransportAndMixingUpdate(
                transport_results={}
            )
        ),
        boundary_propagation_step=(
            lambda *, network, hydraulic_result, transport_and_mixing_update, macro_step_time_s: {}
        ),
    )
    network = _network(runtime, process_ids=("reactor_a", "reactor_b"))

    subsystem_a = _FakeSubsystem(
        descriptor=SubsystemRuntimeDescriptor(
            descriptor_id="subsys_a",
            process_id="reactor_a",
            inlet_ports=("feed",),
            outlet_ports=("product",),
            publication_map={"subsys_a/temperature_a": 300.0},
        ),
        calls=[],
    )
    subsystem_b = _FakeSubsystem(
        descriptor=SubsystemRuntimeDescriptor(
            descriptor_id="subsys_b",
            process_id="reactor_b",
            inlet_ports=("feed",),
            outlet_ports=("product",),
            publication_map={"subsys_b/temperature_b": 320.0},
        ),
        calls=[],
    )

    orchestrator = ConnectedPlantOrchestrator(
        subsystems=(subsystem_a, subsystem_b),
        network=network,
        runtime_orchestrator=runtime,
        phase_hooks=ConnectedPlantPhaseHooks(),
    )

    orchestrator.add_calculation(
        calculation_id="plant_avg_temp",
        input_tags=("subsys_a/temperature_a", "subsys_b/temperature_b"),
        output_tags=("plant/avg_temperature",),
        evaluate=lambda inputs: {
            "plant/avg_temperature": (
                inputs["subsys_a/temperature_a"] + inputs["subsys_b/temperature_b"]
            )
            / 2.0
        },
    )

    _ = orchestrator.step(macro_step_time_s=1.0)

    assert orchestrator.plant_calculation_outputs["plant/avg_temperature"] == pytest.approx(310.0)


def test_plant_output_collision_with_published_raises():
    runtime = ConnectionRuntimeOrchestrator(
        hydraulic_solve_step=lambda *, network, macro_step_time_s: _hydraulic_result(),
        transport_and_mixing_step=(
            lambda *, network, hydraulic_result, macro_step_time_s: TransportAndMixingUpdate(
                transport_results={}
            )
        ),
        boundary_propagation_step=(
            lambda *, network, hydraulic_result, transport_and_mixing_update, macro_step_time_s: {}
        ),
    )
    network = _network(runtime, process_ids=("reactor_a",))

    subsystem = _FakeSubsystem(
        descriptor=SubsystemRuntimeDescriptor(
            descriptor_id="subsys_runtime",
            process_id="reactor_a",
            inlet_ports=("feed",),
            outlet_ports=("product",),
            publication_map={"subsys_runtime/temperature": 300.0},
        ),
        calls=[],
    )

    orchestrator = ConnectedPlantOrchestrator(
        subsystems=(subsystem,),
        network=network,
        runtime_orchestrator=runtime,
    )

    # This should fail: output tag collides with a published subsystem measurement
    with pytest.raises(ValueError, match="collides with a published subsystem measurement"):
        orchestrator.add_calculation(
            calculation_id="plant_collision_on_output",
            input_tags=("subsys_runtime/temperature",),
            output_tags=("subsys_runtime/temperature",),
            evaluate=lambda inputs: {
                "subsys_runtime/temperature": inputs["subsys_runtime/temperature"]
            },
        )


def test_duplicate_plant_calculation_output_tag_raises():
    runtime = ConnectionRuntimeOrchestrator(
        hydraulic_solve_step=lambda *, network, macro_step_time_s: _hydraulic_result(),
        transport_and_mixing_step=(
            lambda *, network, hydraulic_result, macro_step_time_s: TransportAndMixingUpdate(
                transport_results={}
            )
        ),
        boundary_propagation_step=(
            lambda *, network, hydraulic_result, transport_and_mixing_update, macro_step_time_s: {}
        ),
    )
    network = _network(runtime, process_ids=("reactor",))

    subsystem = _FakeSubsystem(
        descriptor=SubsystemRuntimeDescriptor(
            descriptor_id="subsys_runtime",
            process_id="reactor",
            inlet_ports=("feed",),
            outlet_ports=("product",),
            publication_map={"subsys_runtime/temperature": 300.0},
        ),
        calls=[],
    )

    orchestrator = ConnectedPlantOrchestrator(
        subsystems=(subsystem,),
        network=network,
        runtime_orchestrator=runtime,
    )

    orchestrator.add_calculation(
        calculation_id="calc_one",
        input_tags=("subsys_runtime/temperature",),
        output_tags=("plant/output",),
        evaluate=lambda inputs: {"plant/output": inputs["subsys_runtime/temperature"]},
    )

    with pytest.raises(
        ValueError,
        match=(
            "plant calculation 'calc_two' output tag 'plant/output' collides with an existing plant calculation output"
        ),
    ):
        orchestrator.add_calculation(
            calculation_id="calc_two",
            input_tags=("subsys_runtime/temperature",),
            output_tags=("plant/output",),
            evaluate=lambda inputs: {"plant/output": inputs["subsys_runtime/temperature"]},
        )

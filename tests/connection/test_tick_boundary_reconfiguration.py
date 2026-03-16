from __future__ import annotations

from dataclasses import dataclass

import pytest

from modular_simulation.connection.runtime.connected_plant_orchestrator import (
    ConnectedPlantOrchestrator,
    ConnectedPlantPhaseHooks,
)
from modular_simulation.connection.hydraulics.hydraulic_compile import HydraulicCompileLifecycle
from modular_simulation.connection.hydraulics.hydraulic_solver import (
    HydraulicSystemDefinition,
    LinearResidualEquation,
)
from modular_simulation.connection.topology.network import ConnectionNetwork
from modular_simulation.connection.runtime.runtime import ConnectionRuntimeOrchestrator
from modular_simulation.connection.topology.subsystem_descriptor import SubsystemRuntimeDescriptor


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


def _network(runtime: ConnectionRuntimeOrchestrator) -> ConnectionNetwork:
    network = ConnectionNetwork(
        compile_lifecycle=HydraulicCompileLifecycle(),
        hydraulic_system_builder=lambda topology: _valid_system(),
        runtime_orchestrator=runtime,
    )
    network.add_process("reactor", inlet_ports=("feed",), outlet_ports=("product",))
    network.add_boundary_source("feed_boundary")
    network.add_boundary_sink("product_boundary")
    _ = network.connect("feed_boundary", "reactor.feed")
    _ = network.connect("reactor.product", "product_boundary")
    _ = network.compile()
    return network


def _compiled_boundary_ids(network: ConnectionNetwork) -> tuple[str, ...]:
    compiled = network.compiled
    if compiled is None:
        return ()
    return tuple(sorted(node.boundary_id for node in compiled.topology.boundary_nodes))


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


def _orchestrator(
    runtime: ConnectionRuntimeOrchestrator, network: ConnectionNetwork
) -> ConnectedPlantOrchestrator:
    subsystem = _NoOpSubsystem(
        descriptor=SubsystemRuntimeDescriptor(
            descriptor_id="subsystem_runtime",
            process_id="reactor",
            inlet_ports=("feed",),
            outlet_ports=("product",),
            publication_map={"subsystem_runtime/temperature": 300.0},
        )
    )
    return ConnectedPlantOrchestrator(
        subsystems=(subsystem,),
        network=network,
        runtime_orchestrator=runtime,
    )


def test_reconfiguration_enqueued_during_tick_applies_on_next_barrier() -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)

    enqueue_once = {"done": False}

    def enqueue_during_coupling_hook(macro_step_index: int, simulation_time_s: float) -> None:
        del simulation_time_s
        if enqueue_once["done"] or macro_step_index != 1:
            return
        request_id = network.queue_reconfiguration(
            {
                "operation": "batch_update",
                "mutations": [
                    {"operation": "add_boundary_sink", "boundary_id": "sink_next_tick"},
                    {
                        "operation": "add_connection",
                        "source": "reactor.product",
                        "target": "sink_next_tick",
                    },
                ],
            }
        )
        assert request_id == "rq_0001"
        enqueue_once["done"] = True

    orchestrator = _orchestrator(runtime, network)
    orchestrator = ConnectedPlantOrchestrator(
        subsystems=orchestrator.subsystems,
        network=network,
        runtime_orchestrator=runtime,
        phase_hooks=ConnectedPlantPhaseHooks(
            connection_runtime_coupling=enqueue_during_coupling_hook
        ),
    )

    first_step = orchestrator.step(macro_step_time_s=1.0)
    assert first_step.runtime_step_result.barrier_reconfiguration.applied_request_ids == ()
    assert "sink_next_tick" not in _compiled_boundary_ids(network)
    assert tuple(item.request_id for item in network.queued_reconfigurations) == ("rq_0001",)

    second_step = orchestrator.step(macro_step_time_s=1.0)
    assert second_step.runtime_step_result.barrier_reconfiguration.applied_request_ids == (
        "rq_0001",
    )
    assert second_step.runtime_step_result.barrier_reconfiguration.skipped_request_ids == ()
    assert "sink_next_tick" in _compiled_boundary_ids(network)


def test_fifo_queue_ordering_stays_stable_with_deferred_commands_after_rollback() -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)

    _ = network.queue_reconfiguration(
        {
            "operation": "batch_update",
            "mutations": [
                {
                    "operation": "add_connection",
                    "source": "unknown_source",
                    "target": "reactor.feed",
                }
            ],
        }
    )

    enqueue_once = {"done": False}

    def enqueue_during_coupling_hook(macro_step_index: int, simulation_time_s: float) -> None:
        del simulation_time_s
        if enqueue_once["done"] or macro_step_index != 1:
            return
        rq2 = network.queue_reconfiguration(
            {
                "operation": "add_boundary_sink",
                "boundary_id": "sink_single",
            }
        )
        rq3 = network.queue_reconfiguration(
            {
                "operation": "batch_update",
                "mutations": [
                    {"operation": "add_boundary_sink", "boundary_id": "sink_batch"},
                    {
                        "operation": "add_connection",
                        "source": "reactor.product",
                        "target": "sink_batch",
                    },
                ],
            }
        )
        assert (rq2, rq3) == ("rq_0002", "rq_0003")
        enqueue_once["done"] = True

    orchestrator = _orchestrator(runtime, network)
    orchestrator = ConnectedPlantOrchestrator(
        subsystems=orchestrator.subsystems,
        network=network,
        runtime_orchestrator=runtime,
        phase_hooks=ConnectedPlantPhaseHooks(
            connection_runtime_coupling=enqueue_during_coupling_hook
        ),
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "reconfiguration transaction rollback: request 'rq_0001' mutation 1 failed: "
            "unknown endpoint node 'unknown_source'"
        ),
    ):
        _ = orchestrator.step(macro_step_time_s=1.0)

    assert tuple(item.request_id for item in network.queued_reconfigurations) == (
        "rq_0001",
        "rq_0002",
        "rq_0003",
    )
    assert "sink_single" not in _compiled_boundary_ids(network)
    assert "sink_batch" not in _compiled_boundary_ids(network)

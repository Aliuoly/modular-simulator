from __future__ import annotations

# pyright: reportMissingImports=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pytest

from modular_simulation.connection.runtime.connected_plant_orchestrator import (
    ConnectedPlantOrchestrator,
    ConnectedPlantPhaseHooks,
)
from modular_simulation.connection.runtime.connection_layer import TransportAndMixingUpdate
from modular_simulation.connection.hydraulics.hydraulic_solver import HydraulicSolveResult
from modular_simulation.connection.topology.network import ConnectionNetwork
from modular_simulation.connection.runtime.runtime import (
    CONNECTED_PLANT_PHASE_ORDER,
    ConnectionRuntimeOrchestrator,
)
from modular_simulation.connection.topology.subsystem_descriptor import SubsystemRuntimeDescriptor
from modular_simulation.validation.exceptions import MeasurableConfigurationError


@dataclass
class _FakeSubsystem:
    descriptor: SubsystemRuntimeDescriptor
    calls: list[str]
    on_sensor_phase: Callable[[], None] | None = None
    on_publication_snapshot: Callable[[], dict[str, float]] | None = None

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
        if self.on_publication_snapshot is not None:
            return self.on_publication_snapshot()
        return dict(self.descriptor.publication_map)


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


def _subsystem(descriptor_id: str, process_id: str, calls: list[str]) -> _FakeSubsystem:
    return _subsystem_with_publication_map(
        descriptor_id=descriptor_id,
        process_id=process_id,
        calls=calls,
        publication_map={f"{descriptor_id}/temperature": 300.0},
    )


def _subsystem_with_publication_map(
    *,
    descriptor_id: str,
    process_id: str,
    calls: list[str],
    publication_map: dict[str, float],
) -> _FakeSubsystem:
    return _FakeSubsystem(
        descriptor=SubsystemRuntimeDescriptor(
            descriptor_id=descriptor_id,
            process_id=process_id,
            inlet_ports=("feed",),
            outlet_ports=("product",),
            publication_map=publication_map,
        ),
        calls=calls,
    )


def test_connected_plant_orchestrator_and_init_and_macro_step() -> None:
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

    subsystem_calls: list[str] = []
    subsystem_a = _subsystem("subsystem_a", "reactor_a", subsystem_calls)
    subsystem_b = _subsystem("subsystem_b", "reactor_b", subsystem_calls)

    hook_calls: list[tuple[str, int, float]] = []

    def _hook_for(phase: str) -> Callable[[int, float], None]:
        def _record(macro_step_index: int, simulation_time_s: float) -> None:
            hook_calls.append((phase, macro_step_index, simulation_time_s))

        return _record

    orchestrator = ConnectedPlantOrchestrator(
        subsystems=(subsystem_a, subsystem_b),
        network=network,
        runtime_orchestrator=runtime,
        phase_hooks=ConnectedPlantPhaseHooks(
            subsystem_sensor_update=_hook_for("subsystem_sensor_update"),
            subsystem_calculation_update=_hook_for("subsystem_calculation_update"),
            plant_calculation_update=_hook_for("plant_calculation_update"),
            subsystem_controller_update=_hook_for("subsystem_controller_update"),
            subsystem_process_step=_hook_for("subsystem_process_step"),
            connection_runtime_coupling=_hook_for("connection_runtime_coupling"),
        ),
    )

    init_result = orchestrator.initialize()
    assert orchestrator.initialized
    assert init_result.graph_revision == "graph_rev_0001"
    assert init_result.subsystem_ids == ("subsystem_a", "subsystem_b")
    assert init_result.process_ids == ("reactor_a", "reactor_b")

    step_result = orchestrator.step(macro_step_time_s=1.25)

    assert step_result.phase_order == CONNECTED_PLANT_PHASE_ORDER
    assert step_result.macro_step_index == 1
    assert step_result.simulation_time_s == pytest.approx(1.25)
    assert step_result.graph_revision == "graph_rev_0001"
    assert step_result.runtime_step_result.barrier_reconfiguration.applied_request_ids == ()
    assert subsystem_calls == [
        "subsystem_a:sensor",
        "subsystem_b:sensor",
        "subsystem_a:calculation",
        "subsystem_b:calculation",
        "subsystem_a:controller",
        "subsystem_b:controller",
        "subsystem_a:process",
        "subsystem_b:process",
    ]
    assert hook_calls == [
        ("subsystem_sensor_update", 1, 1.25),
        ("subsystem_calculation_update", 1, 1.25),
        ("plant_calculation_update", 1, 1.25),
        ("subsystem_controller_update", 1, 1.25),
        ("subsystem_process_step", 1, 1.25),
        ("connection_runtime_coupling", 1, 1.25),
    ]


def test_connected_plant_orchestrator_and_runtime_enqueue_deferred_to_barrier_commit_points() -> (
    None
):
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

    enqueue_once = {"done": False}
    subsystem = _subsystem("subsystem_runtime", "reactor", calls=[])

    def _enqueue_reconfiguration() -> None:
        if enqueue_once["done"]:
            return
        request_id = network.queue_reconfiguration(
            {
                "operation": "batch_update",
                "mutations": [
                    {"operation": "add_boundary_sink", "boundary_id": "purge_sink"},
                    {
                        "operation": "add_connection",
                        "source": "reactor.product",
                        "target": "purge_sink",
                    },
                ],
            }
        )
        assert request_id == "rq_0001"
        enqueue_once["done"] = True

    subsystem.on_sensor_phase = _enqueue_reconfiguration

    orchestrator = ConnectedPlantOrchestrator(
        subsystems=(subsystem,),
        network=network,
        runtime_orchestrator=runtime,
    )

    _ = orchestrator.initialize()
    first = orchestrator.step(macro_step_time_s=1.0)
    assert first.runtime_step_result.barrier_reconfiguration.applied_request_ids == ()
    assert "purge_sink" not in network._boundary_specs
    assert tuple(item.request_id for item in network.queued_reconfigurations) == ("rq_0001",)

    second = orchestrator.step(macro_step_time_s=1.0)
    assert second.runtime_step_result.barrier_reconfiguration.applied_request_ids == ("rq_0001",)
    assert second.graph_revision == "graph_rev_0002"
    assert "purge_sink" in network._boundary_specs
    assert network.queued_reconfigurations == ()


def test_connected_plant_add_calculation_resolves_cross_subsystem_published_inputs() -> None:
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

    subsystem_a = _subsystem_with_publication_map(
        descriptor_id="subsystem_a",
        process_id="reactor_a",
        calls=[],
        publication_map={"subsystem_a/temperature_a": 300.0},
    )
    subsystem_b = _subsystem_with_publication_map(
        descriptor_id="subsystem_b",
        process_id="reactor_b",
        calls=[],
        publication_map={"subsystem_b/temperature_b": 320.0},
    )
    orchestrator = ConnectedPlantOrchestrator(
        subsystems=(subsystem_a, subsystem_b),
        network=network,
        runtime_orchestrator=runtime,
    )

    orchestrator.add_calculation(
        calculation_id="plant_average_temperature",
        input_tags=("subsystem_a/temperature_a", "subsystem_b/temperature_b"),
        output_tags=("plant/average_temperature",),
        evaluate=lambda inputs: {
            "plant/average_temperature": (
                inputs["subsystem_a/temperature_a"] + inputs["subsystem_b/temperature_b"]
            )
            / 2.0
        },
    )

    _ = orchestrator.step(macro_step_time_s=1.0)

    assert orchestrator.plant_calculation_outputs["plant/average_temperature"] == pytest.approx(
        310.0
    )


def test_connected_plant_add_calculation_resolves_dependencies_deterministically() -> None:
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

    subsystem_a = _subsystem_with_publication_map(
        descriptor_id="subsystem_a",
        process_id="reactor_a",
        calls=[],
        publication_map={"subsystem_a/temperature_a": 301.0},
    )
    subsystem_b = _subsystem_with_publication_map(
        descriptor_id="subsystem_b",
        process_id="reactor_b",
        calls=[],
        publication_map={"subsystem_b/temperature_b": 305.0},
    )
    orchestrator = ConnectedPlantOrchestrator(
        subsystems=(subsystem_a, subsystem_b),
        network=network,
        runtime_orchestrator=runtime,
    )

    orchestrator.add_calculation(
        calculation_id="consumer_registered_first",
        input_tags=("plant/sum_temperature", "subsystem_a/temperature_a"),
        output_tags=("plant/temperature_delta",),
        evaluate=lambda inputs: {
            "plant/temperature_delta": (
                inputs["plant/sum_temperature"] - inputs["subsystem_a/temperature_a"]
            )
        },
    )
    orchestrator.add_calculation(
        calculation_id="producer_registered_second",
        input_tags=("subsystem_a/temperature_a", "subsystem_b/temperature_b"),
        output_tags=("plant/sum_temperature",),
        evaluate=lambda inputs: {
            "plant/sum_temperature": (
                inputs["subsystem_a/temperature_a"] + inputs["subsystem_b/temperature_b"]
            )
        },
    )

    _ = orchestrator.step(macro_step_time_s=1.0)

    assert orchestrator.plant_calculation_outputs["plant/sum_temperature"] == pytest.approx(606.0)
    assert orchestrator.plant_calculation_outputs["plant/temperature_delta"] == pytest.approx(305.0)


def test_connected_plant_add_calculation_raises_grouped_error_for_unresolved_inputs() -> None:
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

    subsystem = _subsystem_with_publication_map(
        descriptor_id="subsystem_runtime",
        process_id="reactor",
        calls=[],
        publication_map={"subsystem_runtime/temperature": 300.0},
    )
    orchestrator = ConnectedPlantOrchestrator(
        subsystems=(subsystem,),
        network=network,
        runtime_orchestrator=runtime,
    )

    orchestrator.add_calculation(
        calculation_id="unresolved_root",
        input_tags=("subsystem_runtime/missing_temperature",),
        output_tags=("plant/intermediate",),
        evaluate=lambda inputs: {
            "plant/intermediate": inputs["subsystem_runtime/missing_temperature"]
        },
    )
    orchestrator.add_calculation(
        calculation_id="unresolved_dependent",
        input_tags=("plant/intermediate", "plant/unknown"),
        output_tags=("plant/final",),
        evaluate=lambda inputs: {
            "plant/final": inputs["plant/intermediate"] + inputs["plant/unknown"]
        },
    )

    with pytest.raises(ExceptionGroup) as excinfo:
        _ = orchestrator.step(macro_step_time_s=1.0)

    assert (
        str(excinfo.value)
        == "2 out of 2 plant calculation(s) could not be resolved: (2 sub-exceptions)"
    )
    assert [str(error) for error in excinfo.value.exceptions] == [
        "plant calculation 'unresolved_root' could not be resolved; missing inputs: "
        + "subsystem_runtime/missing_temperature; available tags: subsystem_runtime/temperature",
        "plant calculation 'unresolved_dependent' could not be resolved; missing inputs: "
        + "plant/intermediate, plant/unknown; available tags: subsystem_runtime/temperature",
    ]


def test_connected_plant_publication_adapter_and_namespaced_lookup_supports_dynamic_snapshots() -> (
    None
):
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

    subsystem = _subsystem_with_publication_map(
        descriptor_id="subsystem_runtime",
        process_id="reactor",
        calls=[],
        publication_map={"temperature": 300.0},
    )
    next_temperature = {"value": 320.0}

    def _next_publication_snapshot() -> dict[str, float]:
        next_temperature["value"] += 1.0
        return {"temperature": next_temperature["value"]}

    subsystem.on_publication_snapshot = _next_publication_snapshot

    orchestrator = ConnectedPlantOrchestrator(
        subsystems=(subsystem,),
        network=network,
        runtime_orchestrator=runtime,
    )
    orchestrator.add_calculation(
        calculation_id="pass_through_temperature",
        input_tags=("subsystem_runtime/temperature",),
        output_tags=("plant/temperature",),
        evaluate=lambda inputs: {"plant/temperature": inputs["subsystem_runtime/temperature"]},
    )

    _ = orchestrator.step(macro_step_time_s=1.0)

    assert orchestrator.plant_calculation_outputs["plant/temperature"] == pytest.approx(322.0)


def test_connected_plant_publication_adapter_and_collision_policy_is_fail_fast() -> None:
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

    subsystem_a = _subsystem_with_publication_map(
        descriptor_id="subsystem_a",
        process_id="reactor_a",
        calls=[],
        publication_map={"temperature": 300.0},
    )
    subsystem_b = _subsystem_with_publication_map(
        descriptor_id="subsystem_b",
        process_id="reactor_b",
        calls=[],
        publication_map={"temperature": 305.0},
    )

    orchestrator = ConnectedPlantOrchestrator(
        subsystems=(subsystem_a, subsystem_b),
        network=network,
        runtime_orchestrator=runtime,
    )

    with pytest.raises(
        MeasurableConfigurationError,
        match=(
            "Published measurement tag collision for 'temperature': already registered by "
            "subsystem 'subsystem_a', cannot register for subsystem 'subsystem_b'."
        ),
    ):
        orchestrator.add_calculation(
            calculation_id="plant_average_temperature",
            input_tags=("subsystem_a/temperature", "subsystem_b/temperature"),
            output_tags=("plant/average_temperature",),
            evaluate=lambda inputs: {
                "plant/average_temperature": (
                    inputs["subsystem_a/temperature"] + inputs["subsystem_b/temperature"]
                )
                / 2.0
            },
        )

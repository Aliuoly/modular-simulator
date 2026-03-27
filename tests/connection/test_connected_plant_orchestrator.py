from __future__ import annotations

# pyright: reportMissingImports=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

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
from modular_simulation.connection.topology.unit_process_wiring import create_subsystem_for_unit
from modular_simulation.thermodynamics.runtime_context import SimulationRuntimeContext
from modular_simulation.thermodynamics.stream import StreamData
from modular_simulation.unit_processes import StagewiseDistillationColumn


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


def test_connected_plant_calculation_outputs_must_be_numeric() -> None:
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
        calculation_id="non_numeric_output",
        input_tags=("subsystem_runtime/temperature",),
        output_tags=("plant/not_numeric",),
        evaluate=lambda inputs: {"plant/not_numeric": "bad-output"},
    )

    with pytest.raises(ValueError) as excinfo:
        _ = orchestrator.step(macro_step_time_s=1.0)

    assert str(excinfo.value) == (
        "plant calculation 'non_numeric_output' output 'plant/not_numeric' must be numeric"
    )


def test_connected_plant_observables_include_runtime_stagewise_process_state_values() -> None:
    context = SimulationRuntimeContext.create(species_names=["methanol", "ethanol", "water"])

    column = StagewiseDistillationColumn(
        n_species=3,
        active_contact_height_m=6.0,
        shell_diameter_m=1.2,
        feed_stage_indices=(1, 4),
        column_pressure_pa=165000.0,
    )
    subsystem = create_subsystem_for_unit(
        unit=column,
        unit_id="stage_col",
        dt=0.1,
        runtime_context=context,
    )
    cast(StagewiseDistillationColumn, subsystem.system.process_model).attach_system(
        cast(Any, type("_S", (), {"solver_options": {}})())
    )
    column.apply_inlet(
        "feed_1",
        stream=StreamData(
            temperature=350.0,
            pressure=165000.0,
            mole_fractions=(0.7, 0.2, 0.1),
            molar_flow_rate=6.0,
        ),
    )
    column.apply_inlet(
        "feed_2",
        stream=StreamData(
            temperature=340.0,
            pressure=165000.0,
            mole_fractions=(0.1, 0.3, 0.6),
            molar_flow_rate=4.5,
        ),
    )

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
        runtime_context=context,
    )
    network = ConnectionNetwork(runtime_orchestrator=runtime)
    network.add_process(
        "stage_col",
        inlet_ports=subsystem.descriptor.inlet_ports,
        outlet_ports=subsystem.descriptor.outlet_ports,
    )
    network.add_boundary_source("feed_a")
    network.add_boundary_source("feed_b")
    network.add_boundary_sink("dist_prod")
    network.add_boundary_sink("bot_prod")
    _ = network.connect("feed_a", "stage_col.feed_1")
    _ = network.connect("feed_b", "stage_col.feed_2")
    _ = network.connect("stage_col.distillate", "dist_prod")
    _ = network.connect("stage_col.bottoms", "bot_prod")
    _ = network.compile()

    orchestrator = ConnectedPlantOrchestrator(
        subsystems=(subsystem,),
        network=network,
        runtime_orchestrator=runtime,
        runtime_context=context,
    )
    _ = orchestrator.step(macro_step_time_s=0.2)

    process_state_values = network.get_observability_snapshot()["observables"][
        "process_state_values"
    ]
    assert process_state_values["stage_col/column_pressure_pa"] == pytest.approx(
        column.column_pressure_pa
    )
    assert process_state_values["stage_col/active_contact_height_m"] == pytest.approx(
        column.active_contact_height_m
    )
    assert process_state_values["stage_col/shell_diameter_m"] == pytest.approx(
        column.shell_diameter_m
    )
    assert process_state_values["stage_col/distillate_flow_mol_s"] == pytest.approx(
        column.distillate_flow
    )
    assert process_state_values["stage_col/bottoms_flow_mol_s"] == pytest.approx(
        column.bottoms_flow
    )
    assert process_state_values["stage_col/reflux_return_flow_mol_s"] == pytest.approx(
        column.reflux_return_flow
    )
    assert process_state_values["stage_col/distillate_withdrawal_flow_mol_s"] == pytest.approx(
        column.distillate_withdrawal_flow
    )
    assert process_state_values["stage_col/bottoms_withdrawal_flow_mol_s"] == pytest.approx(
        column.bottoms_withdrawal_flow
    )
    assert process_state_values["stage_col/feed_1/flow_mol_s"] == pytest.approx(
        float(column.feed_flows[0])
    )
    assert process_state_values["stage_col/feed_2/flow_mol_s"] == pytest.approx(
        float(column.feed_flows[1])
    )
    assert process_state_values["stage_col/feed_1/stage_index"] == pytest.approx(
        float(column.feed_stage_indices[0])
    )
    assert process_state_values["stage_col/feed_2/stage_index"] == pytest.approx(
        float(column.feed_stage_indices[1])
    )

    cas_ids = context.species_registry.cas_list
    for idx, cas_id in enumerate(cas_ids):
        assert process_state_values[
            f"stage_col/distillate_mole_fraction/{cas_id}"
        ] == pytest.approx(float(column.distillate_composition[idx]))
        assert process_state_values[f"stage_col/bottoms_mole_fraction/{cas_id}"] == pytest.approx(
            float(column.bottoms_composition[idx])
        )
        assert process_state_values[f"stage_col/feed_1/mole_fraction/{cas_id}"] == pytest.approx(
            float(np.asarray(column.feed_compositions, dtype=np.float64).reshape(2, 3)[0, idx])
        )
        assert process_state_values[f"stage_col/feed_2/mole_fraction/{cas_id}"] == pytest.approx(
            float(np.asarray(column.feed_compositions, dtype=np.float64).reshape(2, 3)[1, idx])
        )


def test_connected_plant_stagewise_direct_duty_changes_realized_phase_change_without_breaking_component_conservation() -> (
    None
):
    context = SimulationRuntimeContext.create(species_names=["methanol", "ethanol", "water"])

    def _run_case(
        *, condenser_duty_request_w: float, reboiler_duty_request_w: float
    ) -> StagewiseDistillationColumn:
        column = StagewiseDistillationColumn(
            n_species=3,
            active_contact_height_m=6.0,
            shell_diameter_m=1.2,
            feed_stage_indices=(1, 4),
            column_pressure_pa=165000.0,
        )
        subsystem = create_subsystem_for_unit(
            unit=column,
            unit_id="stage_col",
            dt=0.1,
            runtime_context=context,
        )
        cast(StagewiseDistillationColumn, subsystem.system.process_model).attach_system(
            cast(Any, type("_S", (), {"solver_options": {}})())
        )
        column.apply_inlet(
            "feed_1",
            stream=StreamData(
                temperature=350.0,
                pressure=165000.0,
                mole_fractions=(0.7, 0.2, 0.1),
                molar_flow_rate=6.0,
            ),
        )
        column.apply_inlet(
            "feed_2",
            stream=StreamData(
                temperature=340.0,
                pressure=165000.0,
                mole_fractions=(0.1, 0.3, 0.6),
                molar_flow_rate=4.5,
            ),
        )
        column.condenser_duty_request_W = condenser_duty_request_w
        column.reboiler_duty_request_W = reboiler_duty_request_w

        runtime = ConnectionRuntimeOrchestrator(
            hydraulic_solve_step=lambda *, network, macro_step_time_s: _hydraulic_result(),
            transport_and_mixing_step=(
                lambda *, network, hydraulic_result, macro_step_time_s: TransportAndMixingUpdate(
                    transport_results={}
                )
            ),
            boundary_propagation_step=(
                lambda *,
                network,
                hydraulic_result,
                transport_and_mixing_update,
                macro_step_time_s: {}
            ),
            runtime_context=context,
        )
        network = ConnectionNetwork(runtime_orchestrator=runtime)
        network.add_process(
            "stage_col",
            inlet_ports=subsystem.descriptor.inlet_ports,
            outlet_ports=subsystem.descriptor.outlet_ports,
        )
        network.add_boundary_source("feed_a")
        network.add_boundary_source("feed_b")
        network.add_boundary_sink("dist_prod")
        network.add_boundary_sink("bot_prod")
        _ = network.connect("feed_a", "stage_col.feed_1")
        _ = network.connect("feed_b", "stage_col.feed_2")
        _ = network.connect("stage_col.distillate", "dist_prod")
        _ = network.connect("stage_col.bottoms", "bot_prod")
        _ = network.compile()

        orchestrator = ConnectedPlantOrchestrator(
            subsystems=(subsystem,),
            network=network,
            runtime_orchestrator=runtime,
            runtime_context=context,
        )
        _ = orchestrator.step(macro_step_time_s=0.2)
        return column

    baseline = _run_case(condenser_duty_request_w=0.0, reboiler_duty_request_w=0.0)
    duty_actuated = _run_case(condenser_duty_request_w=-15000.0, reboiler_duty_request_w=12000.0)

    assert duty_actuated.realized_condensed_flow_mol_s > baseline.realized_condensed_flow_mol_s
    assert (
        duty_actuated.realized_reboiler_boilup_flow_mol_s
        > baseline.realized_reboiler_boilup_flow_mol_s
    )
    assert duty_actuated.condenser_duty_W < 0.0
    assert duty_actuated.reboiler_duty_W > 0.0
    assert duty_actuated.realized_condensed_flow_mol_s == pytest.approx(0.5)
    assert duty_actuated.realized_reboiler_boilup_flow_mol_s == pytest.approx(0.4)
    assert duty_actuated.condenser_duty_W == pytest.approx(-15000.0)
    assert duty_actuated.reboiler_duty_W == pytest.approx(12000.0)

    baseline_total_moles = float(
        np.sum(np.asarray(baseline.stage_component_moles, dtype=np.float64))
        + np.sum(np.asarray(baseline.reflux_drum_component_moles, dtype=np.float64))
        + np.sum(np.asarray(baseline.bottoms_sump_component_moles, dtype=np.float64))
    )
    duty_total_moles = float(
        np.sum(np.asarray(duty_actuated.stage_component_moles, dtype=np.float64))
        + np.sum(np.asarray(duty_actuated.reflux_drum_component_moles, dtype=np.float64))
        + np.sum(np.asarray(duty_actuated.bottoms_sump_component_moles, dtype=np.float64))
    )
    assert duty_total_moles == pytest.approx(baseline_total_moles)

    baseline_species_inventory = (
        np.sum(
            np.asarray(baseline.stage_component_moles, dtype=np.float64).reshape(
                baseline.n_stages, baseline.n_species
            ),
            axis=0,
        )
        + np.asarray(baseline.reflux_drum_component_moles, dtype=np.float64)
        + np.asarray(baseline.bottoms_sump_component_moles, dtype=np.float64)
    )
    duty_species_inventory = (
        np.sum(
            np.asarray(duty_actuated.stage_component_moles, dtype=np.float64).reshape(
                duty_actuated.n_stages, duty_actuated.n_species
            ),
            axis=0,
        )
        + np.asarray(duty_actuated.reflux_drum_component_moles, dtype=np.float64)
        + np.asarray(duty_actuated.bottoms_sump_component_moles, dtype=np.float64)
    )
    assert duty_species_inventory == pytest.approx(baseline_species_inventory)


def test_connected_plant_stagewise_reflux_return_and_product_withdrawals_remain_owner_bounded_and_nonnegative() -> (
    None
):
    context = SimulationRuntimeContext.create(species_names=["methanol", "ethanol", "water"])

    column = StagewiseDistillationColumn(
        n_species=3,
        active_contact_height_m=6.0,
        shell_diameter_m=1.2,
        feed_stage_indices=(1, 4),
        column_pressure_pa=165000.0,
        reflux_drum_component_moles=np.array([0.3, 0.2, 0.1], dtype=np.float64),
        bottoms_sump_component_moles=np.array([0.3, 0.2, 0.1], dtype=np.float64),
    )
    subsystem = create_subsystem_for_unit(
        unit=column,
        unit_id="stage_col",
        dt=0.1,
        runtime_context=context,
    )
    cast(StagewiseDistillationColumn, subsystem.system.process_model).attach_system(
        cast(Any, type("_S", (), {"solver_options": {}})())
    )
    column.apply_inlet(
        "feed_1",
        stream=StreamData(
            temperature=350.0,
            pressure=165000.0,
            mole_fractions=(0.7, 0.2, 0.1),
            molar_flow_rate=6.0,
        ),
    )
    column.apply_inlet(
        "feed_2",
        stream=StreamData(
            temperature=340.0,
            pressure=165000.0,
            mole_fractions=(0.1, 0.3, 0.6),
            molar_flow_rate=4.5,
        ),
    )
    column.apply_inlet(
        "reflux_return",
        stream=StreamData(
            temperature=330.0,
            pressure=165000.0,
            mole_fractions=(0.2, 0.3, 0.5),
            molar_flow_rate=1.5,
        ),
    )
    column.condenser_duty_request_W = -9000.0
    column.reboiler_duty_request_W = 6000.0
    column.distillate_withdrawal_flow = 5.0
    column.bottoms_withdrawal_flow = 5.0

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
        runtime_context=context,
    )
    network = ConnectionNetwork(runtime_orchestrator=runtime)
    network.add_process(
        "stage_col",
        inlet_ports=subsystem.descriptor.inlet_ports,
        outlet_ports=subsystem.descriptor.outlet_ports,
    )
    network.add_boundary_source("feed_a")
    network.add_boundary_source("feed_b")
    network.add_boundary_source("reflux_boundary")
    network.add_boundary_sink("dist_prod")
    network.add_boundary_sink("bot_prod")
    network.add_boundary_sink("reflux_sink")
    _ = network.connect("feed_a", "stage_col.feed_1")
    _ = network.connect("feed_b", "stage_col.feed_2")
    _ = network.connect("reflux_boundary", "stage_col.reflux_return")
    _ = network.connect("stage_col.distillate", "dist_prod")
    _ = network.connect("stage_col.bottoms", "bot_prod")
    _ = network.connect("stage_col.reflux_outlet", "reflux_sink")
    _ = network.compile()

    orchestrator = ConnectedPlantOrchestrator(
        subsystems=(subsystem,),
        network=network,
        runtime_orchestrator=runtime,
        runtime_context=context,
    )
    _ = orchestrator.step(macro_step_time_s=0.2)

    assert column.reflux_return_flow == pytest.approx(1.5)
    assert tuple(column.reflux_return_composition) == pytest.approx((0.2, 0.3, 0.5))
    assert 0.0 <= column.distillate_flow <= column.distillate_withdrawal_flow
    assert 0.0 <= column.bottoms_flow <= column.bottoms_withdrawal_flow
    assert column.reflux_outlet_flow >= 0.0
    assert np.min(np.asarray(column.reflux_drum_component_moles, dtype=np.float64)) >= -1.0e-12
    assert np.min(np.asarray(column.bottoms_sump_component_moles, dtype=np.float64)) >= -1.0e-12

    reflux_drum_inventory = np.clip(
        np.asarray(column.reflux_drum_component_moles, dtype=np.float64), 0.0, None
    )
    bottoms_sump_inventory = np.clip(
        np.asarray(column.bottoms_sump_component_moles, dtype=np.float64), 0.0, None
    )
    drum_total = float(np.sum(reflux_drum_inventory))
    sump_total = float(np.sum(bottoms_sump_inventory))
    assert drum_total > 0.0
    assert sump_total > 0.0

    expected_drum_liquid = tuple((reflux_drum_inventory / drum_total).tolist())
    expected_sump_liquid = tuple((bottoms_sump_inventory / sump_total).tolist())
    assert column.get_outlet_stream("reflux_outlet").mole_fractions == pytest.approx(
        expected_drum_liquid
    )
    assert column.get_outlet_stream("distillate").mole_fractions == pytest.approx(
        expected_drum_liquid
    )
    assert column.get_outlet_stream("bottoms").mole_fractions == pytest.approx(expected_sump_liquid)

    process_state_values = network.get_observability_snapshot()["observables"][
        "process_state_values"
    ]
    assert process_state_values["stage_col/reflux_return_flow_mol_s"] == pytest.approx(
        column.reflux_return_flow
    )
    assert process_state_values["stage_col/distillate_withdrawal_flow_mol_s"] == pytest.approx(
        column.distillate_withdrawal_flow
    )
    assert process_state_values["stage_col/bottoms_withdrawal_flow_mol_s"] == pytest.approx(
        column.bottoms_withdrawal_flow
    )

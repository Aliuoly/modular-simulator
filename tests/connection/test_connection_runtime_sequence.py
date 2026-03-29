from __future__ import annotations

# pyright: reportMissingImports=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportUnusedCallResult=false

from dataclasses import dataclass
from dataclasses import replace
from typing import cast

import numpy as np
import pytest

from modular_simulation.connection.runtime.connection_layer import (
    PicardIterationGateConfig,
    TransportAndMixingUpdate,
)
from modular_simulation.connection.runtime.connected_plant_orchestrator import (
    ConnectedPlantOrchestrator,
    ConnectedPlantPhaseHooks,
)
from modular_simulation.connection.hydraulics.hydraulic_compile import HydraulicCompileLifecycle
from modular_simulation.connection.hydraulics.hydraulic_solver import (
    HydraulicSolveResult,
    HydraulicSystemDefinition,
    LinearResidualEquation,
)
from modular_simulation.connection.topology.junction import JunctionMixingResult
from modular_simulation.connection.topology.network import ConnectionNetwork
from modular_simulation.connection.runtime.runtime import (
    CONNECTED_PLANT_PHASE_ORDER,
    ConnectionRuntimeOrchestrator,
    ConnectionRuntimeStepResult,
)
from modular_simulation.connection.domain.state import MaterialState, PortCondition
from modular_simulation.connection.topology.subsystem_descriptor import SubsystemRuntimeDescriptor
from modular_simulation.connection.domain.transport import (
    LagTransportState,
    LagTransportUpdateResult,
)
from modular_simulation.thermodynamics.stream import StreamData


class _DemandLatchBridge:
    def __init__(self) -> None:
        self.applied_inlets: list[tuple[str, StreamData]] = []
        self.requested_outlet_by_port: dict[str, float] = {}

    def apply_inlet(self, port_name: str, stream: StreamData) -> None:
        self.applied_inlets.append((port_name, stream))

    def get_outlet_stream(self, port_name: str) -> StreamData:
        requested = self.requested_outlet_by_port.get(port_name, 0.0)
        return StreamData(
            temperature=300.0,
            pressure=101325.0,
            mole_fractions=(1.0,),
            molar_flow_rate=requested,
        )

    def resolve_outlet_condition(self, port_name: str) -> PortCondition:
        requested = self.requested_outlet_by_port.get(port_name, 0.0)
        return PortCondition(
            state=MaterialState(
                pressure=101325.0,
                temperature=300.0,
                mole_fractions=(1.0,),
            ),
            through_molar_flow_rate=requested,
        )

    def apply_requested_outlet_through_flow_demand(
        self, port_name: str, through_molar_flow_rate: float
    ) -> None:
        self.requested_outlet_by_port[port_name] = through_molar_flow_rate


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
    network.connect("feed_boundary", "reactor.feed")
    network.connect("reactor.product", "product_boundary")
    _ = network.compile()
    return network


def _hydraulic_result(*, edge_flow: float, residual_norm: float = 1.0e-10) -> HydraulicSolveResult:
    return HydraulicSolveResult(
        converged=True,
        iterations=2,
        residual_norm=residual_norm,
        solution_vector=np.asarray([edge_flow, 5.0], dtype=np.float64),
        unknowns={"flow": edge_flow, "pressure": 5.0},
        unknown_index_map={"flow": 0, "pressure": 1},
        residual_index_map={"balance": 0, "ref": 1},
    )


def _material_state(*, pressure: float, temperature: float) -> MaterialState:
    return MaterialState(
        pressure=pressure,
        temperature=temperature,
        mole_fractions=(0.6, 0.4),
    )


def _transport_result(*, held_for_near_zero_flow: bool) -> LagTransportUpdateResult:
    return LagTransportUpdateResult(
        state=LagTransportState(composition=(0.6, 0.4), temperature=315.0),
        update_fraction=0.0 if held_for_near_zero_flow else 0.5,
        flow_scale=0.0 if held_for_near_zero_flow else 1.0,
        flow_sign_changed=False,
        held_for_near_zero_flow=held_for_near_zero_flow,
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


def test_runtime_step_uses_fixed_macro_sequence_and_deterministic_bookkeeping() -> None:
    assert CONNECTED_PLANT_PHASE_ORDER == (
        "subsystem_sensor_update",
        "subsystem_calculation_update",
        "plant_calculation_update",
        "subsystem_controller_update",
        "subsystem_process_step",
        "connection_runtime_coupling",
    )

    call_order: list[str] = []

    def hydraulic_solve_step(
        *,
        network: ConnectionNetwork,
        macro_step_time_s: float,
    ) -> HydraulicSolveResult:
        assert network._compiled is not None
        assert network._compiled.graph_revision == "graph_rev_0001"
        assert macro_step_time_s == pytest.approx(1.25)
        call_order.append("hydraulics_solve")
        return _hydraulic_result(edge_flow=0.8)

    def transport_and_mixing_step(
        *,
        network: ConnectionNetwork,
        hydraulic_result: HydraulicSolveResult,
        macro_step_time_s: float,
    ) -> TransportAndMixingUpdate:
        assert network._compiled is not None
        assert hydraulic_result.unknowns["flow"] == pytest.approx(0.8)
        assert macro_step_time_s == pytest.approx(1.25)
        call_order.append("transport_update")
        return TransportAndMixingUpdate(
            transport_results={
                "edge_main": _transport_result(held_for_near_zero_flow=False),
                "edge_zero": _transport_result(held_for_near_zero_flow=True),
            },
            junction_results={
                "junction_a": JunctionMixingResult(
                    state=_material_state(pressure=101325.0, temperature=315.0),
                    total_incoming_flow_rate=0.0,
                    used_fallback=True,
                )
            },
        )

    def boundary_propagation_step(
        *,
        network: ConnectionNetwork,
        hydraulic_result: HydraulicSolveResult,
        transport_and_mixing_update: TransportAndMixingUpdate,
        macro_step_time_s: float,
    ) -> dict[str, PortCondition]:
        assert network._compiled is not None
        assert hydraulic_result.unknowns["flow"] == pytest.approx(0.8)
        assert "edge_main" in transport_and_mixing_update.transport_results
        assert macro_step_time_s == pytest.approx(1.25)
        call_order.append("boundary_state_propagation")
        return {
            "reactor_inlet": PortCondition(
                state=_material_state(pressure=120000.0, temperature=315.0),
                through_molar_flow_rate=0.8,
            ),
            "feed": PortCondition(
                state=_material_state(pressure=130000.0, temperature=320.0),
                through_molar_flow_rate=0.8,
            ),
        }

    runtime = ConnectionRuntimeOrchestrator(
        hydraulic_solve_step=hydraulic_solve_step,
        transport_and_mixing_step=transport_and_mixing_step,
        boundary_propagation_step=boundary_propagation_step,
    )
    network = _network(runtime)

    result = cast(ConnectionRuntimeStepResult, network.step(macro_step_time_s=1.25))

    assert call_order == [
        "hydraulics_solve",
        "transport_update",
        "boundary_state_propagation",
    ]
    assert result.macro_step_index == 1
    assert result.simulation_time_s == pytest.approx(1.25)
    assert result.graph_revision == "graph_rev_0001"
    assert result.bookkeeping.executed_sequence == (
        "hydraulics_solve",
        "transport_update",
        "boundary_state_propagation",
    )
    assert result.bookkeeping.updated_port_keys == ("feed", "reactor_inlet")
    assert result.bookkeeping.transport_fallback_keys == ("edge_zero",)
    assert result.bookkeeping.junction_fallback_keys == ("junction_a",)
    assert result.bookkeeping.used_fallback
    assert result.barrier_reconfiguration.applied_request_ids == ()
    assert result.barrier_reconfiguration.skipped_request_ids == ()

    probe_outlet = PortCondition(
        state=_material_state(pressure=140000.0, temperature=325.0),
        through_molar_flow_rate=1.1,
    )
    runtime.record_latest_outlet_condition(
        node_id="reactor",
        port_name="product",
        condition=probe_outlet,
    )
    latest_outlet = runtime.get_latest_outlet_condition(node_id="reactor", port_name="product")
    assert latest_outlet == probe_outlet
    latest_outlet_stream = runtime.get_latest_outlet_stream(
        node_id="reactor",
        port_name="product",
    )
    assert latest_outlet_stream is not None
    assert latest_outlet_stream.molar_flow_rate == pytest.approx(1.1)


def test_runtime_step_preserves_picard_gate_metadata_deterministically() -> None:
    boundary_flows = iter((1.0, 0.40, 0.10, 0.1000000001))
    call_counts = {"hydraulics": 0, "transport": 0, "boundary": 0}

    def hydraulic_solve_step(
        *,
        network: ConnectionNetwork,
        macro_step_time_s: float,
    ) -> HydraulicSolveResult:
        del network, macro_step_time_s
        call_counts["hydraulics"] += 1
        return _hydraulic_result(edge_flow=1.0, residual_norm=5.0)

    def transport_and_mixing_step(
        *,
        network: ConnectionNetwork,
        hydraulic_result: HydraulicSolveResult,
        macro_step_time_s: float,
    ) -> TransportAndMixingUpdate:
        del network, hydraulic_result, macro_step_time_s
        call_counts["transport"] += 1
        return TransportAndMixingUpdate(
            transport_results={"edge_main": _transport_result(held_for_near_zero_flow=False)}
        )

    def boundary_propagation_step(
        *,
        network: ConnectionNetwork,
        hydraulic_result: HydraulicSolveResult,
        transport_and_mixing_update: TransportAndMixingUpdate,
        macro_step_time_s: float,
    ) -> dict[str, PortCondition]:
        del network, hydraulic_result, transport_and_mixing_update, macro_step_time_s
        call_counts["boundary"] += 1
        return {
            "inlet": PortCondition(
                state=_material_state(pressure=101325.0, temperature=315.0),
                through_molar_flow_rate=next(boundary_flows),
            )
        }

    runtime = ConnectionRuntimeOrchestrator(
        hydraulic_solve_step=hydraulic_solve_step,
        transport_and_mixing_step=transport_and_mixing_step,
        boundary_propagation_step=boundary_propagation_step,
        picard_gate_config=PicardIterationGateConfig(
            enabled=True,
            residual_threshold=0.1,
            max_iterations=5,
            tolerance=1.0e-6,
        ),
    )
    network = _network(runtime)

    result = cast(ConnectionRuntimeStepResult, network.step(macro_step_time_s=2.0))

    assert call_counts == {"hydraulics": 4, "transport": 4, "boundary": 4}
    assert result.bookkeeping.picard_gate_enabled
    assert result.bookkeeping.picard_iterations_used == 3
    assert result.bookkeeping.picard_converged
    assert result.bookkeeping.picard_last_residual == pytest.approx(1.0e-10)
    assert result.bookkeeping.executed_sequence == (
        "hydraulics_solve",
        "transport_update",
        "boundary_state_propagation",
    )


def test_reconfiguration_commit_rejection_keeps_time_and_active_revision_unchanged() -> None:
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
    before_snapshot = network.save_runtime_snapshot()
    before_revision = network._compiled.graph_revision if network._compiled is not None else None

    with pytest.raises(
        RuntimeError,
        match=(
            "reconfiguration transaction rollback: request 'rq_0001' mutation 1 failed: "
            "unknown endpoint node 'unknown_source'"
        ),
    ):
        _ = network.step(macro_step_time_s=1.0)

    after_snapshot = network.save_runtime_snapshot()
    after_revision = network._compiled.graph_revision if network._compiled is not None else None

    assert after_snapshot == before_snapshot
    assert after_revision == before_revision


def test_connected_plant_step_defers_queue_mutations_enqueued_in_coupling_hook() -> None:
    runtime = ConnectionRuntimeOrchestrator(
        hydraulic_solve_step=(
            lambda *, network, macro_step_time_s: _hydraulic_result(edge_flow=0.8)
        ),
        transport_and_mixing_step=(
            lambda *, network, hydraulic_result, macro_step_time_s: TransportAndMixingUpdate(
                transport_results={}
            )
        ),
        boundary_propagation_step=(
            lambda *, network, hydraulic_result, transport_and_mixing_update, macro_step_time_s: {}
        ),
    )
    network = _network(runtime)

    subsystem = _NoOpSubsystem(
        descriptor=SubsystemRuntimeDescriptor(
            descriptor_id="subsystem_runtime",
            process_id="reactor",
            inlet_ports=("feed",),
            outlet_ports=("product",),
            publication_map={"subsystem_runtime/temperature": 300.0},
        )
    )

    enqueue_once = {"done": False}
    phase_hook_calls: list[tuple[str, int, float]] = []

    def _record_phase_hook(phase_name: str):
        def _record(macro_step_index: int, simulation_time_s: float) -> None:
            phase_hook_calls.append((phase_name, macro_step_index, simulation_time_s))

        return _record

    def enqueue_during_coupling_hook(macro_step_index: int, simulation_time_s: float) -> None:
        phase_hook_calls.append(
            ("connection_runtime_coupling", macro_step_index, simulation_time_s)
        )
        if enqueue_once["done"] or macro_step_index != 1:
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

    orchestrator = ConnectedPlantOrchestrator(
        subsystems=(subsystem,),
        network=network,
        runtime_orchestrator=runtime,
        phase_hooks=ConnectedPlantPhaseHooks(
            subsystem_sensor_update=_record_phase_hook("subsystem_sensor_update"),
            subsystem_calculation_update=_record_phase_hook("subsystem_calculation_update"),
            plant_calculation_update=_record_phase_hook("plant_calculation_update"),
            subsystem_controller_update=_record_phase_hook("subsystem_controller_update"),
            subsystem_process_step=_record_phase_hook("subsystem_process_step"),
            connection_runtime_coupling=enqueue_during_coupling_hook,
        ),
    )

    first_step = orchestrator.step(macro_step_time_s=1.0)
    assert first_step.phase_order == CONNECTED_PLANT_PHASE_ORDER
    assert first_step.macro_step_index == 1
    assert first_step.simulation_time_s == pytest.approx(1.0)
    assert first_step.graph_revision == "graph_rev_0001"
    assert first_step.runtime_step_result.barrier_reconfiguration.applied_request_ids == ()
    assert first_step.runtime_step_result.barrier_reconfiguration.skipped_request_ids == ()
    assert first_step.runtime_step_result.bookkeeping.executed_sequence == (
        "hydraulics_solve",
        "transport_update",
        "boundary_state_propagation",
    )
    assert first_step.runtime_step_result.bookkeeping.updated_port_keys == ()
    assert "purge_sink" not in network._boundary_specs
    assert tuple(item.request_id for item in network.queued_reconfigurations) == ("rq_0001",)

    second_step = orchestrator.step(macro_step_time_s=1.0)
    assert second_step.phase_order == CONNECTED_PLANT_PHASE_ORDER
    assert second_step.macro_step_index == 2
    assert second_step.simulation_time_s == pytest.approx(2.0)
    assert second_step.graph_revision == "graph_rev_0002"
    assert second_step.runtime_step_result.barrier_reconfiguration.applied_request_ids == (
        "rq_0001",
    )
    assert second_step.runtime_step_result.barrier_reconfiguration.skipped_request_ids == ()
    assert second_step.runtime_step_result.bookkeeping.executed_sequence == (
        "hydraulics_solve",
        "transport_update",
        "boundary_state_propagation",
    )
    assert second_step.runtime_step_result.bookkeeping.updated_port_keys == ()
    assert "purge_sink" in network._boundary_specs
    assert phase_hook_calls == [
        ("subsystem_sensor_update", 1, 1.0),
        ("subsystem_calculation_update", 1, 1.0),
        ("plant_calculation_update", 1, 1.0),
        ("subsystem_controller_update", 1, 1.0),
        ("subsystem_process_step", 1, 1.0),
        ("connection_runtime_coupling", 1, 1.0),
        ("subsystem_sensor_update", 2, 2.0),
        ("subsystem_calculation_update", 2, 2.0),
        ("plant_calculation_update", 2, 2.0),
        ("subsystem_controller_update", 2, 2.0),
        ("subsystem_process_step", 2, 2.0),
        ("connection_runtime_coupling", 2, 2.0),
    ]


def test_runtime_add_junction_mutation_compiles_explicit_junction_node() -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)

    request_id = network.queue_reconfiguration(
        {
            "operation": "batch_update",
            "mutations": [
                {
                    "operation": "add_junction",
                    "junction_id": "mixing_junction",
                    "inlet_ports": ["feed_a", "feed_b"],
                    "outlet_ports": ["product_a", "product_b"],
                }
            ],
        }
    )

    assert request_id == "rq_0001"

    result = cast(ConnectionRuntimeStepResult, network.step(macro_step_time_s=0.5))

    assert result.barrier_reconfiguration.applied_request_ids == ("rq_0001",)
    compiled = network.compiled
    assert compiled is not None
    assert tuple(node.process_id for node in compiled.topology.process_nodes) == ("reactor",)
    assert tuple(node.junction_id for node in compiled.topology.junction_nodes) == (
        "mixing_junction",
    )


def test_runtime_step_fails_before_transport_and_boundary_on_non_converged_hydraulics() -> None:
    call_counts = {"transport": 0, "boundary": 0}

    def hydraulic_solve_step(
        *,
        network: ConnectionNetwork,
        macro_step_time_s: float,
    ) -> HydraulicSolveResult:
        del network, macro_step_time_s
        return HydraulicSolveResult(
            converged=False,
            iterations=4,
            residual_norm=9.5,
            solution_vector=np.asarray([0.0, 5.0], dtype=np.float64),
            unknowns={"flow": 0.0, "pressure": 5.0},
            unknown_index_map={"flow": 0, "pressure": 1},
            residual_index_map={"balance": 0, "ref": 1},
        )

    def transport_and_mixing_step(
        *,
        network: ConnectionNetwork,
        hydraulic_result: HydraulicSolveResult,
        macro_step_time_s: float,
    ) -> TransportAndMixingUpdate:
        del network, hydraulic_result, macro_step_time_s
        call_counts["transport"] += 1
        return TransportAndMixingUpdate(transport_results={})

    def boundary_propagation_step(
        *,
        network: ConnectionNetwork,
        hydraulic_result: HydraulicSolveResult,
        transport_and_mixing_update: TransportAndMixingUpdate,
        macro_step_time_s: float,
    ) -> dict[str, PortCondition]:
        del network, hydraulic_result, transport_and_mixing_update, macro_step_time_s
        call_counts["boundary"] += 1
        return {}

    runtime = ConnectionRuntimeOrchestrator(
        hydraulic_solve_step=hydraulic_solve_step,
        transport_and_mixing_step=transport_and_mixing_step,
        boundary_propagation_step=boundary_propagation_step,
    )
    network = _network(runtime)

    with pytest.raises(
        RuntimeError,
        match=(
            "hydraulic solve did not converge; aborting transport update and boundary propagation "
            r"\(iterations=4, residual_norm=9.5\)"
        ),
    ):
        _ = cast(ConnectionRuntimeStepResult, network.step(macro_step_time_s=1.0))

    assert call_counts == {"transport": 0, "boundary": 0}


class _RuntimeBridge:
    def __init__(self, outlet_condition: PortCondition) -> None:
        self._outlet_condition = outlet_condition
        self.inlets: dict[str, StreamData] = {}

    def apply_inlet(self, port_name: str, stream: StreamData) -> None:
        self.inlets[port_name] = stream

    def get_outlet_stream(self, port_name: str) -> StreamData:
        del port_name
        return StreamData.from_port_condition(self._outlet_condition)

    def resolve_outlet_condition(self, port_name: str) -> PortCondition:
        del port_name
        return self._outlet_condition


def test_default_runtime_transport_and_junction_step_is_owner_led_when_bindings_exist() -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = ConnectionNetwork(
        compile_lifecycle=HydraulicCompileLifecycle(),
        hydraulic_system_builder=lambda topology: _valid_system(),
        runtime_orchestrator=runtime,
    )
    network.add_boundary_source("feed_a")
    network.add_boundary_source("feed_b")
    network.add_junction("mix", inlet_ports=("in_a", "in_b"), outlet_ports=("out",))
    network.add_process("reactor", inlet_ports=("feed",), outlet_ports=("product",))
    network.add_boundary_sink("product_boundary")
    network.connect("feed_a", "mix.in_a", edge_id="edge_0001")
    network.connect("feed_b", "mix.in_b", edge_id="edge_0002")
    network.connect("mix.out", "reactor.feed", edge_id="edge_0003")
    network.connect("reactor.product", "product_boundary", edge_id="edge_0004")
    _ = network.compile()

    reactor_bridge = _RuntimeBridge(
        PortCondition(
            state=MaterialState(
                pressure=101000.0,
                temperature=330.0,
                mole_fractions=(0.1, 0.9),
            ),
            through_molar_flow_rate=4.0,
        )
    )
    runtime.bind_stream_port_io(node_id="reactor", stream_port_io=reactor_bridge)
    runtime.set_feed_stream(
        boundary_id="feed_a",
        stream=StreamData.from_port_condition(
            PortCondition(
                state=MaterialState(
                    pressure=120000.0,
                    temperature=300.0,
                    mole_fractions=(0.8, 0.2),
                ),
                through_molar_flow_rate=5.0,
            )
        ),
    )
    runtime.set_feed_stream(
        boundary_id="feed_b",
        stream=StreamData.from_port_condition(
            PortCondition(
                state=MaterialState(
                    pressure=130000.0,
                    temperature=320.0,
                    mole_fractions=(0.4, 0.6),
                ),
                through_molar_flow_rate=3.0,
            )
        ),
    )

    hydraulic_result = HydraulicSolveResult(
        converged=True,
        iterations=2,
        residual_norm=1.0e-10,
        solution_vector=np.asarray([5.0, 3.0, 8.0, 4.0, 0.0], dtype=np.float64),
        unknowns={
            "edge_0001": 5.0,
            "edge_0002": 3.0,
            "edge_0003": 8.0,
            "edge_0004": 4.0,
            "pressure": 5.0,
        },
        unknown_index_map={},
        residual_index_map={},
    )

    class _CompiledHydraulic:
        def resolve_line_flow(
            self, *, line_id: str, hydraulic_result: HydraulicSolveResult
        ) -> float | None:
            value = hydraulic_result.unknowns.get(line_id)
            return None if value is None else float(value)

        def resolve_line_target_pressure(
            self, *, line_id: str, hydraulic_result: HydraulicSolveResult
        ) -> float | None:
            del line_id
            return float(hydraulic_result.unknowns["pressure"])

        def solve(self) -> HydraulicSolveResult:
            raise AssertionError("not used")

    assert network._compiled is not None
    network._compiled = replace(
        network._compiled,
        process_bindings=cast(
            object, {**network._compiled.process_bindings, "reactor": reactor_bridge}
        ),
        hydraulic=cast(object, _CompiledHydraulic()),
    )

    update = runtime._default_transport_and_mixing_step(
        network=network,
        hydraulic_result=hydraulic_result,
        macro_step_time_s=0.25,
    )

    assert tuple(sorted(update.transport_results)) == (
        "edge_0001",
        "edge_0002",
        "edge_0003",
        "edge_0004",
    )
    assert tuple(update.junction_results) == ("mix",)
    junction_result = update.junction_results["mix"]
    assert junction_result.total_incoming_flow_rate == pytest.approx(8.0)
    assert junction_result.state.temperature == pytest.approx(307.5)
    assert junction_result.state.mole_fractions == pytest.approx((0.65, 0.35))
    assert not junction_result.used_fallback


def test_runtime_boundary_application_latches_solved_requested_outlet_demand_for_next_step() -> (
    None
):
    runtime = ConnectionRuntimeOrchestrator()
    network = ConnectionNetwork(
        compile_lifecycle=HydraulicCompileLifecycle(),
        hydraulic_system_builder=lambda topology: _valid_system(),
        runtime_orchestrator=runtime,
    )
    network.add_process("tank", inlet_ports=("inlet",), outlet_ports=("outlet",))
    network.add_boundary_source("feed")
    network.add_boundary_sink("product")
    network.connect("feed", "tank.inlet", edge_id="edge_0001")
    network.connect("tank.outlet", "product", edge_id="edge_0002")
    compiled = network.compile()

    tank_bridge = _DemandLatchBridge()
    runtime.bind_stream_port_io(node_id="tank", stream_port_io=tank_bridge)
    runtime.set_feed_stream(
        boundary_id="feed",
        stream=StreamData(
            temperature=300.0,
            pressure=101325.0,
            mole_fractions=(1.0,),
            molar_flow_rate=2.0,
        ),
    )

    class _ManualHydraulic:
        def __init__(self) -> None:
            self.topology_lookup = type(
                "_Lookup",
                (),
                {
                    "line_flow_unknown_by_line": {
                        "edge_0001": "flow_in",
                        "edge_0002": "flow_out",
                    }
                },
            )()

        def solve(self) -> HydraulicSolveResult:
            return HydraulicSolveResult(
                converged=True,
                iterations=1,
                residual_norm=1.0e-10,
                solution_vector=np.asarray([2.0, 1.25], dtype=np.float64),
                unknowns={"flow_in": 2.0, "flow_out": 1.25},
                unknown_index_map={"flow_in": 0, "flow_out": 1},
                residual_index_map={},
            )

        def resolve_line_flow(
            self, *, line_id: str, hydraulic_result: HydraulicSolveResult
        ) -> float | None:
            key = self.topology_lookup.line_flow_unknown_by_line.get(line_id)
            if key is None:
                return None
            return float(hydraulic_result.unknowns[key])

        def resolve_line_target_pressure(
            self, *, line_id: str, hydraulic_result: HydraulicSolveResult
        ) -> float | None:
            del line_id, hydraulic_result
            return 101325.0

    network._compiled = replace(
        compiled,
        hydraulic=cast(object, _ManualHydraulic()),
        process_bindings={
            **compiled.process_bindings,
            "tank": tank_bridge,
        },
    )

    _ = network.step(macro_step_time_s=1.0)

    assert tank_bridge.requested_outlet_by_port["outlet"] == pytest.approx(1.25)


def test_runtime_latches_zero_requested_outlet_when_hydraulic_flow_is_non_positive() -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = ConnectionNetwork(
        compile_lifecycle=HydraulicCompileLifecycle(),
        hydraulic_system_builder=lambda topology: _valid_system(),
        runtime_orchestrator=runtime,
    )
    network.add_process("tank", inlet_ports=("inlet",), outlet_ports=("outlet",))
    network.add_boundary_source("feed")
    network.add_boundary_sink("product")
    network.connect("feed", "tank.inlet", edge_id="edge_0001")
    network.connect("tank.outlet", "product", edge_id="edge_0002")
    compiled = network.compile()

    tank_bridge = _DemandLatchBridge()
    runtime.bind_stream_port_io(node_id="tank", stream_port_io=tank_bridge)
    runtime.set_feed_stream(
        boundary_id="feed",
        stream=StreamData(
            temperature=300.0,
            pressure=101325.0,
            mole_fractions=(1.0,),
            molar_flow_rate=2.0,
        ),
    )

    class _ManualHydraulic:
        def __init__(self) -> None:
            self.topology_lookup = type(
                "_Lookup",
                (),
                {
                    "line_flow_unknown_by_line": {
                        "edge_0001": "flow_in",
                        "edge_0002": "flow_out",
                    }
                },
            )()

        def solve(self) -> HydraulicSolveResult:
            return HydraulicSolveResult(
                converged=True,
                iterations=1,
                residual_norm=1.0e-10,
                solution_vector=np.asarray([2.0, -0.5], dtype=np.float64),
                unknowns={"flow_in": 2.0, "flow_out": -0.5},
                unknown_index_map={"flow_in": 0, "flow_out": 1},
                residual_index_map={},
            )

        def resolve_line_flow(
            self, *, line_id: str, hydraulic_result: HydraulicSolveResult
        ) -> float | None:
            key = self.topology_lookup.line_flow_unknown_by_line.get(line_id)
            if key is None:
                return None
            return float(hydraulic_result.unknowns[key])

        def resolve_line_target_pressure(
            self, *, line_id: str, hydraulic_result: HydraulicSolveResult
        ) -> float | None:
            del line_id, hydraulic_result
            return 101325.0

    network._compiled = replace(
        compiled,
        hydraulic=cast(object, _ManualHydraulic()),
        process_bindings={
            **compiled.process_bindings,
            "tank": tank_bridge,
        },
    )

    _ = network.step(macro_step_time_s=1.0)

    assert tank_bridge.requested_outlet_by_port["outlet"] == pytest.approx(0.0)

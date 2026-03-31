from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

import numpy as np
import pytest

from modular_simulation.connection.hydraulics.hydraulic_compile import HydraulicCompileLifecycle
from modular_simulation.connection.hydraulics.hydraulic_solver import (
    HydraulicSolveResult,
    HydraulicSystemDefinition,
    LinearResidualEquation,
)
from modular_simulation.connection.runtime.connected_plant_orchestrator import (
    ConnectedPlantOrchestrator,
    ConnectedPlantPhaseHooks,
)
from modular_simulation.connection.runtime.connection_layer import TransportAndMixingUpdate
from modular_simulation.connection.runtime.runtime import ConnectionRuntimeOrchestrator
from modular_simulation.connection.runtime.runtime_persistence import (
    save_runtime_snapshot_contract,
)
from modular_simulation.connection.topology.network import ConnectionNetwork
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


class _FakeHoldingTankProcessModel:
    state_list = (
        "temperature",
        "holdup_component_moles",
        "holdup_temperature",
        "resolved_outlet_flow_mol_s",
        "outlet_composition",
    )

    def __init__(self) -> None:
        self.temperature = 300.0
        self.holdup_component_moles = np.asarray([1.2, 0.8], dtype=np.float64)
        self.holdup_temperature = 300.0
        self.resolved_outlet_flow_mol_s = 0.4
        self.outlet_composition = np.asarray([0.6, 0.4], dtype=np.float64)
        self._holdup_species_ids = ("A", "B")
        self._inlet_species_ids = ("A", "B")
        self._outlet_species_ids = ("A", "B")

    def state_getter(self, state_name: str) -> object:
        return getattr(self, state_name)


@dataclass
class _TransactionalSubsystem:
    descriptor: SubsystemRuntimeDescriptor
    process_model: _FakeHoldingTankProcessModel = field(
        default_factory=_FakeHoldingTankProcessModel
    )
    calls: list[str] = field(default_factory=list)
    process_temperature_delta: float = 15.0
    process_holdup_delta: np.ndarray = field(
        default_factory=lambda: np.asarray([0.2, -0.1], dtype=np.float64)
    )
    on_process_phase: Callable[[], None] | None = None

    def __post_init__(self) -> None:
        self.system = type("_System", (), {"process_model": self.process_model})()

    def run_sensor_phase(self) -> None:
        self.calls.append("sensor")

    def run_calculation_phase(self) -> None:
        self.calls.append("calculation")

    def run_controller_phase(self) -> None:
        self.calls.append("controller")

    def run_process_phase(self, duration: float) -> None:
        del duration
        self.calls.append("process")
        self.process_model.temperature += self.process_temperature_delta
        self.process_model.holdup_temperature = self.process_model.temperature
        self.process_model.holdup_component_moles = (
            self.process_model.holdup_component_moles + self.process_holdup_delta
        )
        self.process_model.outlet_composition = np.clip(
            self.process_model.holdup_component_moles, 0.0, None
        ) / float(np.sum(np.clip(self.process_model.holdup_component_moles, 0.0, None)))
        if self.on_process_phase is not None:
            self.on_process_phase()

    def snapshot_published_measurements(self) -> dict[str, float]:
        return {"temperature": float(self.process_model.temperature)}

    def snapshot_process_state_values(self) -> dict[str, float]:
        return {
            f"{self.descriptor.process_id}/temperature_K": float(self.process_model.temperature),
        }


def _build_runtime() -> ConnectionRuntimeOrchestrator:
    return ConnectionRuntimeOrchestrator(
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


def _build_network(runtime: ConnectionRuntimeOrchestrator) -> ConnectionNetwork:
    network = ConnectionNetwork(
        compile_lifecycle=HydraulicCompileLifecycle(),
        hydraulic_system_builder=lambda topology: _valid_system(),
        runtime_orchestrator=runtime,
    )
    network.add_process("tank", inlet_ports=("feed",), outlet_ports=("product",))
    network.add_boundary_source("feed_boundary")
    network.add_boundary_sink("product_boundary")
    network.connect("feed_boundary", "tank.feed")
    network.connect("tank.product", "product_boundary")
    _ = network.compile()
    return network


def _build_subsystem() -> _TransactionalSubsystem:
    return _TransactionalSubsystem(
        descriptor=SubsystemRuntimeDescriptor(
            descriptor_id="tank_runtime",
            process_id="tank",
            inlet_ports=("feed",),
            outlet_ports=("product",),
            publication_map={"tank_runtime/temperature": 300.0},
        )
    )


def _build_orchestrator(
    *,
    phase_hooks: ConnectedPlantPhaseHooks | None = None,
) -> tuple[
    ConnectionRuntimeOrchestrator,
    ConnectionNetwork,
    _TransactionalSubsystem,
    ConnectedPlantOrchestrator,
]:
    runtime = _build_runtime()
    network = _build_network(runtime)
    subsystem = _build_subsystem()
    orchestrator = ConnectedPlantOrchestrator(
        subsystems=(subsystem,),
        network=network,
        runtime_orchestrator=runtime,
        phase_hooks=phase_hooks,
    )
    _ = orchestrator.initialize()
    return runtime, network, subsystem, orchestrator


def _contract_snapshot(
    *,
    runtime: ConnectionRuntimeOrchestrator,
    network: ConnectionNetwork,
    orchestrator: ConnectedPlantOrchestrator,
) -> Mapping[str, object]:
    return save_runtime_snapshot_contract(
        runtime=runtime,
        network=network,
        process_runtime_state=orchestrator.export_process_runtime_state(),
    )


def test_rejected_candidate_macro_step_restores_pre_step_snapshot_and_public_state() -> None:
    in_flight_snapshots: list[Mapping[str, object]] = []

    runtime: ConnectionRuntimeOrchestrator
    network: ConnectionNetwork
    subsystem: _TransactionalSubsystem
    orchestrator: ConnectedPlantOrchestrator
    runtime, network, subsystem, orchestrator = _build_orchestrator(
        phase_hooks=ConnectedPlantPhaseHooks(
            connection_runtime_coupling=lambda macro_step_index, simulation_time_s: (
                in_flight_snapshots.append(network.get_observability_snapshot()),
                (_ for _ in ()).throw(RuntimeError("candidate macro-step rejected")),
            )[-1]
        )
    )

    before_snapshot = _contract_snapshot(
        runtime=runtime,
        network=network,
        orchestrator=orchestrator,
    )
    before_public_snapshot = network.get_observability_snapshot()

    with pytest.raises(RuntimeError, match="candidate macro-step rejected"):
        _ = orchestrator.step(macro_step_time_s=1.0)

    assert in_flight_snapshots == [before_public_snapshot]
    assert network.get_observability_snapshot() == before_public_snapshot
    assert (
        _contract_snapshot(runtime=runtime, network=network, orchestrator=orchestrator)
        == before_snapshot
    )
    assert subsystem.process_model.temperature == pytest.approx(300.0)
    assert subsystem.process_model.holdup_component_moles.tolist() == pytest.approx([1.2, 0.8])


def test_successful_macro_step_publishes_exactly_one_new_accepted_public_snapshot() -> None:
    runtime, network, subsystem, orchestrator = _build_orchestrator()

    before_public_snapshot = network.get_observability_snapshot()
    in_flight_snapshots: list[Mapping[str, object]] = []
    subsystem.on_process_phase = lambda: in_flight_snapshots.append(
        network.get_observability_snapshot()
    )

    result = orchestrator.step(macro_step_time_s=1.0)

    after_public_snapshot = network.get_observability_snapshot()
    assert result.macro_step_index == 1
    assert in_flight_snapshots == [before_public_snapshot]
    assert after_public_snapshot != before_public_snapshot
    assert after_public_snapshot["runtime"]["macro_step_index"] == 1
    assert after_public_snapshot["observables"]["published_measurements"][
        "tank_runtime/temperature"
    ] == pytest.approx(315.0)
    assert after_public_snapshot["observables"]["process_state_values"][
        "tank/holdup_total_mol"
    ] == pytest.approx(2.1)


def test_second_run_after_rejection_starts_from_restored_last_accepted_state() -> None:
    reject_once = {"armed": True}

    def _reject_then_clear(macro_step_index: int, simulation_time_s: float) -> None:
        del macro_step_index, simulation_time_s
        if reject_once["armed"]:
            reject_once["armed"] = False
            raise RuntimeError("first candidate rejected")

    runtime, network, subsystem, orchestrator = _build_orchestrator(
        phase_hooks=ConnectedPlantPhaseHooks(connection_runtime_coupling=_reject_then_clear)
    )

    with pytest.raises(RuntimeError, match="first candidate rejected"):
        _ = orchestrator.step(macro_step_time_s=1.0)

    accepted = orchestrator.step(macro_step_time_s=1.0)
    public_snapshot = network.get_observability_snapshot()

    assert accepted.macro_step_index == 1
    assert subsystem.process_model.temperature == pytest.approx(315.0)
    assert public_snapshot["observables"]["published_measurements"][
        "tank_runtime/temperature"
    ] == pytest.approx(315.0)
    assert public_snapshot["observables"]["process_state_values"][
        "tank/holdup_total_mol"
    ] == pytest.approx(2.1)

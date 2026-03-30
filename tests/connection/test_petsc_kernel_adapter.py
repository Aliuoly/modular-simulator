from __future__ import annotations

import math
from importlib import import_module
import sys
from types import ModuleType, SimpleNamespace

import numpy as np

from modular_simulation.connection.benchmarking.runnable_candidate_contracts import (
    PHASE5_RUNNABLE_CANDIDATES,
)
from modular_simulation.connection.domain.state import MaterialState, PortCondition
from modular_simulation.connection.hydraulics.hydraulic_compile import HydraulicCompileLifecycle
from modular_simulation.connection.hydraulics.hydraulic_solver import (
    HydraulicSystemDefinition,
    LinearResidualEquation,
)
from modular_simulation.connection.kernel_adapter import (
    KernelCandidateStepRequest,
    KernelDelayStrategy,
    KernelInitializationRequest,
    KernelOptionalCapability,
    KernelWarmStartRequest,
)
from modular_simulation.connection.runtime.runtime import ConnectionRuntimeOrchestrator
from modular_simulation.connection.topology.network import ConnectionNetwork


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


def _port_condition(*, pressure: float, temperature: float, flow_rate: float) -> PortCondition:
    return PortCondition(
        state=MaterialState(
            pressure=pressure,
            temperature=temperature,
            mole_fractions=(0.7, 0.3),
            species_ids=("A", "B"),
        ),
        species_ids=("A", "B"),
        through_molar_flow_rate=flow_rate,
        macro_step_time_s=0.0,
    )


def _seed_transport_runtime_state(runtime: ConnectionRuntimeOrchestrator) -> None:
    runtime.record_latest_inlet_condition(
        node_id="reactor",
        port_name="feed",
        condition=_port_condition(pressure=120000.0, temperature=315.0, flow_rate=1.5),
    )
    runtime.record_latest_outlet_condition(
        node_id="reactor",
        port_name="product",
        condition=_port_condition(pressure=119500.0, temperature=325.0, flow_rate=1.4),
    )
    runtime.restore_transport_runtime_state(
        {
            "edge_states": [
                {
                    "edge_id": "edge_0001",
                    "composition": [0.8, 0.2],
                    "temperature": 315.0,
                }
            ],
            "previous_edge_flow_rates": [{"edge_id": "edge_0001", "flow_rate": 1.25}],
            "junction_states": [
                {
                    "junction_id": "mix",
                    "state": {
                        "pressure": 120000.0,
                        "temperature": 310.0,
                        "mole_fractions": [0.6, 0.4],
                    },
                }
            ],
        }
    )


def _adapter_cls():
    module = import_module("modular_simulation.connection.runtime.petsc_kernel_adapter")
    return module.PetscSnesKernelAdapter


def _install_fake_petsc4py(monkeypatch) -> None:
    petsc4py_module = ModuleType("petsc4py")
    petsc_module = ModuleType("petsc4py.PETSc")

    class _FakeVec:
        def __init__(self, array: np.ndarray) -> None:
            self.array = np.asarray(array, dtype=float)

        def setArray(self, array: np.ndarray) -> None:
            self.array = np.asarray(array, dtype=float)

    class _FakeMat:
        def __init__(self) -> None:
            self.entries: list[tuple[int, int, float]] = []

        def setValues(self, rows, cols, values) -> None:
            for row in rows:
                for col, value in zip(cols, values, strict=True):
                    self.entries.append((int(row), int(col), float(value)))

        def assemble(self) -> None:
            return None

    class _FakeSNES:
        def __init__(self) -> None:
            self._function = None
            self._jacobian = None
            self.solution = None

        def create(self) -> _FakeSNES:
            return self

        def setFunction(self, function, residual_vec) -> None:
            self._function = function
            self._residual_vec = residual_vec

        def setJacobian(self, jacobian, preconditioner, callback) -> None:
            self._jacobian = callback
            self._jacobian_mat = jacobian
            self._preconditioner = preconditioner

        def setFromOptions(self) -> None:
            return None

        def solve(self, rhs, solution_vec) -> None:
            del rhs
            assert self._function is not None
            assert self._jacobian is not None
            residual_vec = _FakeVec(np.zeros_like(solution_vec.array, dtype=float))
            self._function(self, solution_vec, residual_vec)
            jacobian_mat = _FakeMat()
            self._jacobian(self, solution_vec, jacobian_mat, jacobian_mat)
            solution_vec.setArray(solution_vec.array)
            self.solution = solution_vec.array.copy()

    petsc_module.SNES = _FakeSNES
    petsc_module.Vec = _FakeVec
    petsc_module.Mat = _FakeMat
    petsc4py_module.PETSc = petsc_module
    monkeypatch.setitem(sys.modules, "petsc4py", petsc4py_module)
    monkeypatch.setitem(sys.modules, "petsc4py.PETSc", petsc_module)


def test_petsc_adapter_restores_accepted_snapshot_via_existing_restore_path(monkeypatch) -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)
    _seed_transport_runtime_state(runtime)
    accepted_snapshot = network.save_runtime_snapshot()
    restored_snapshots: list[dict[str, object]] = []

    original_restore = network.restore_validated_runtime_snapshot

    def _record_restore(*, snapshot):
        restored_snapshots.append(dict(snapshot))
        original_restore(snapshot=snapshot)

    monkeypatch.setattr(network, "restore_validated_runtime_snapshot", _record_restore)

    adapter = _adapter_cls()(network=network, runtime_orchestrator=runtime)

    initialized = adapter.initialize(
        KernelInitializationRequest(accepted_snapshot=accepted_snapshot)
    )
    warmed = adapter.warm_start(KernelWarmStartRequest(accepted_snapshot=accepted_snapshot))

    assert initialized.initialized is True
    assert warmed.restored is True
    assert restored_snapshots == [dict(accepted_snapshot), dict(accepted_snapshot)]
    assert adapter.delay_semantics.strategy is KernelDelayStrategy.EXTERNAL_TRANSPORT_HISTORY


def test_petsc_adapter_round_trips_transport_history_delay_state() -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)
    _seed_transport_runtime_state(runtime)
    adapter = _adapter_cls()(network=network, runtime_orchestrator=runtime)

    captured = adapter.capture_delay_state()
    runtime.restore_transport_runtime_state({})

    adapter.restore_delay_state(captured)

    assert adapter.capture_delay_state() == captured
    assert captured["transport_runtime_state"]


def test_petsc_adapter_emits_finite_solver_telemetry_and_optional_capabilities(
    monkeypatch,
) -> None:
    _install_fake_petsc4py(monkeypatch)
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)
    adapter = _adapter_cls()(network=network, runtime_orchestrator=runtime)

    result = adapter.evaluate_candidate_step(KernelCandidateStepRequest(macro_step_time_s=0.25))

    assert result.accepted is True
    assert math.isfinite(result.telemetry.residual_eval_cost_s)
    assert math.isfinite(result.telemetry.jacobian_eval_cost_s)
    assert math.isfinite(result.telemetry.linear_solve_cost_s)
    assert {
        KernelOptionalCapability.STATE_VECTOR,
        KernelOptionalCapability.RESIDUAL,
        KernelOptionalCapability.JACOBIAN,
    }.issubset(adapter.supported_optional_capabilities())


def test_petsc_candidate_binding_stays_after_sundials_in_phase5_policy() -> None:
    candidate_ids = tuple(candidate.candidate_id for candidate in PHASE5_RUNNABLE_CANDIDATES)
    implementation_bindings = {
        candidate.candidate_id: candidate.implementation_binding
        for candidate in PHASE5_RUNNABLE_CANDIDATES
    }

    assert candidate_ids == ("disciplined_split", "sundials4py", "petsc4py")
    assert implementation_bindings["petsc4py"] == "petsc4py.PETSc.SNES"
    assert candidate_ids.index("petsc4py") > candidate_ids.index("sundials4py")

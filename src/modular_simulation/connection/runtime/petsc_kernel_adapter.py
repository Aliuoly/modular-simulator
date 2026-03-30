from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from importlib import import_module
from time import perf_counter

import numpy as np
from numpy.typing import NDArray

from modular_simulation.connection.hydraulics.hydraulic_compile import HydraulicSolverInputs
from modular_simulation.connection.hydraulics.hydraulic_solver import SparseJacobianTriplet
from modular_simulation.connection.kernel_adapter import (
    KernelAdapterTelemetry,
    KernelCandidateStepRequest,
    KernelCandidateStepResult,
    KernelDelaySemantics,
    KernelDelayStateMapping,
    KernelDelayStrategy,
    KernelInitializationRequest,
    KernelInitializationResult,
    KernelOptionalCapability,
    KernelWarmStartRequest,
    KernelWarmStartResult,
)
from modular_simulation.connection.runtime.split_kernel_adapter import ProcessRuntimeStateOwner
from modular_simulation.connection.topology.network import ConnectionNetwork


def _default_delay_semantics() -> KernelDelaySemantics:
    return KernelDelaySemantics(
        strategy=KernelDelayStrategy.EXTERNAL_TRANSPORT_HISTORY,
        state_schema="transport_runtime_state",
        preserves_existing_transport_history=True,
        notes="PETSc candidate preserves delay state as external transport history.",
    )


def _default_delay_state_mapping() -> KernelDelayStateMapping:
    return KernelDelayStateMapping(
        payload_key="transport_runtime_state",
        mapped_fields=("edge_states", "previous_edge_flow_rates", "junction_states"),
        replacement_required=True,
        replacement_candidates=("augmented_state", "hybrid"),
        replacement_rule=(
            "Future candidates must publish an explicit mapping from current transport "
            "history semantics to any replacement delay bundle without implying optional "
            "solver capabilities."
        ),
    )


def _bootstrap_telemetry() -> KernelAdapterTelemetry:
    return KernelAdapterTelemetry(
        macro_step_index=0,
        macro_step_time_s=0.0,
        simulation_time_s=0.0,
        graph_revision=None,
        executed_sequence=(),
        transport_fallback_keys=(),
        junction_fallback_keys=(),
        used_fallback=False,
        picard_iterations_used=0,
        picard_converged=True,
        picard_last_residual=None,
        residual_eval_cost_s=0.0,
        jacobian_eval_cost_s=0.0,
        linear_solve_cost_s=0.0,
        barrier_queue_size_before=0,
        barrier_queue_size_after=0,
        applied_request_ids=(),
        skipped_request_ids=(),
    )


@dataclass
class PetscSnesKernelAdapter:
    network: ConnectionNetwork
    runtime_orchestrator: object
    process_runtime_owner: ProcessRuntimeStateOwner | None = None
    delay_semantics: KernelDelaySemantics = field(default_factory=_default_delay_semantics)
    delay_state_mapping: KernelDelayStateMapping = field(
        default_factory=_default_delay_state_mapping
    )
    telemetry: KernelAdapterTelemetry = field(default_factory=_bootstrap_telemetry)
    _latest_state_vector: NDArray[np.float64] | None = field(default=None, init=False, repr=False)
    _last_residual_eval_cost_s: float = field(default=0.0, init=False, repr=False)
    _last_jacobian_eval_cost_s: float = field(default=0.0, init=False, repr=False)

    def initialize(self, request: KernelInitializationRequest) -> KernelInitializationResult:
        compiled = self.network.compiled or self.network.compile()
        if request.accepted_snapshot is not None:
            self.network.restore_validated_runtime_snapshot(snapshot=request.accepted_snapshot)
        self._latest_state_vector = None
        return KernelInitializationResult(
            initialized=True,
            graph_revision=None if compiled is None else compiled.graph_revision,
        )

    def warm_start(self, request: KernelWarmStartRequest) -> KernelWarmStartResult:
        self.network.restore_validated_runtime_snapshot(snapshot=request.accepted_snapshot)
        compiled = self.network.compiled
        self._latest_state_vector = None
        return KernelWarmStartResult(
            restored=True,
            graph_revision=None if compiled is None else compiled.graph_revision,
        )

    def evaluate_candidate_step(
        self, request: KernelCandidateStepRequest
    ) -> KernelCandidateStepResult:
        solver_inputs = self._solver_inputs()
        petsc = self._load_petsc_module()
        initial_state = self._initial_state_vector(solver_inputs)
        solution_vec = self._build_petsc_vec(petsc, initial_state)
        residual_vec = self._build_petsc_vec(petsc, np.zeros_like(initial_state))
        jacobian_mat = self._build_petsc_mat(petsc, size=initial_state.size)

        self._last_residual_eval_cost_s = 0.0
        self._last_jacobian_eval_cost_s = 0.0

        snes = self._build_snes(petsc)
        snes.setFunction(self._build_residual_callback(solver_inputs), residual_vec)
        snes.setJacobian(
            jacobian_mat,
            jacobian_mat,
            self._build_jacobian_callback(solver_inputs),
        )
        if hasattr(snes, "setFromOptions"):
            snes.setFromOptions()

        linear_solve_started = perf_counter()
        snes.solve(None, solution_vec)
        linear_solve_cost_s = perf_counter() - linear_solve_started

        solved_state = self._extract_vec_array(solution_vec)
        self._latest_state_vector = solved_state.copy()
        self.telemetry = KernelAdapterTelemetry(
            macro_step_index=self.telemetry.macro_step_index + 1,
            macro_step_time_s=request.macro_step_time_s,
            simulation_time_s=self.telemetry.simulation_time_s + request.macro_step_time_s,
            graph_revision=solver_inputs.graph_revision,
            executed_sequence=("petsc_snes_candidate_step",),
            transport_fallback_keys=(),
            junction_fallback_keys=(),
            used_fallback=False,
            residual_eval_cost_s=max(self._last_residual_eval_cost_s, 1.0e-12),
            jacobian_eval_cost_s=max(self._last_jacobian_eval_cost_s, 1.0e-12),
            linear_solve_cost_s=max(linear_solve_cost_s, 1.0e-12),
        )
        return KernelCandidateStepResult(
            accepted=True,
            graph_revision=solver_inputs.graph_revision,
            telemetry=self.telemetry,
        )

    def capture_delay_state(self) -> Mapping[str, object]:
        return {
            "delay_strategy": self.delay_semantics.strategy.value,
            "state_schema": self.delay_semantics.state_schema,
            "mapped_fields": self.delay_state_mapping.mapped_fields,
            self.delay_state_mapping.payload_key: self.runtime_orchestrator.export_transport_runtime_state(),
        }

    def restore_delay_state(self, payload: Mapping[str, object]) -> None:
        transport_payload = payload.get(self.delay_state_mapping.payload_key)
        if isinstance(transport_payload, Mapping):
            self.runtime_orchestrator.restore_transport_runtime_state(transport_payload)
            return
        self.runtime_orchestrator.restore_transport_runtime_state(payload)

    def supported_optional_capabilities(self) -> frozenset[KernelOptionalCapability]:
        return frozenset(
            {
                KernelOptionalCapability.STATE_VECTOR,
                KernelOptionalCapability.RESIDUAL,
                KernelOptionalCapability.JACOBIAN,
            }
        )

    def capture_process_runtime_state(self) -> Mapping[str, object]:
        if self.process_runtime_owner is None:
            return {}
        return self.process_runtime_owner.export_process_runtime_state()

    def restore_process_runtime_state(self, payload: Mapping[str, object]) -> None:
        if self.process_runtime_owner is None:
            return
        self.process_runtime_owner.restore_process_runtime_state(payload)

    def export_state_vector(self) -> Sequence[float]:
        if self._latest_state_vector is None:
            solver_inputs = self._solver_inputs()
            self._latest_state_vector = self._initial_state_vector(solver_inputs)
        return tuple(float(value) for value in self._latest_state_vector)

    def evaluate_residual(self, *, state_vector: Sequence[float]) -> Sequence[float]:
        solver_inputs = self._solver_inputs()
        residual_vector, _, _ = solver_inputs.system.assemble_residual_vector(
            np.asarray(state_vector, dtype=float)
        )
        return tuple(float(value) for value in residual_vector)

    def evaluate_jacobian(self, *, state_vector: Sequence[float]) -> SparseJacobianTriplet:
        solver_inputs = self._solver_inputs()
        triplet, _, _ = solver_inputs.system.assemble_sparse_jacobian_triplet(
            np.asarray(state_vector, dtype=float)
        )
        return triplet

    def _solver_inputs(self) -> HydraulicSolverInputs:
        compiled = self.network.compiled or self.network.compile()
        if compiled is None or compiled.hydraulic is None:
            raise RuntimeError("PETSc candidate requires a compiled hydraulic graph")
        return compiled.hydraulic.build_solver_inputs()

    def _initial_state_vector(self, solver_inputs: HydraulicSolverInputs) -> NDArray[np.float64]:
        if self._latest_state_vector is not None and self._latest_state_vector.shape == (
            len(solver_inputs.unknown_order),
        ):
            return np.asarray(self._latest_state_vector, dtype=float).copy()
        return np.zeros(len(solver_inputs.unknown_order), dtype=float)

    def _load_petsc_module(self):
        try:
            return import_module("petsc4py.PETSc")
        except ModuleNotFoundError:
            petsc4py = import_module("petsc4py")
            return petsc4py.PETSc

    def _build_snes(self, petsc):
        snes_factory = petsc.SNES
        snes = snes_factory()
        if hasattr(snes, "create"):
            created = snes.create()
            if created is not None:
                snes = created
        return snes

    def _build_petsc_vec(self, petsc, values: NDArray[np.float64]):
        array = np.asarray(values, dtype=float)
        try:
            return petsc.Vec(array.copy())
        except TypeError:
            vec = petsc.Vec()
            if hasattr(vec, "createSeq"):
                created = vec.createSeq(array.size)
                if created is not None:
                    vec = created
            self._set_vec_array(vec, array)
            return vec

    def _build_petsc_mat(self, petsc, *, size: int):
        mat = petsc.Mat()
        if hasattr(mat, "createAIJ"):
            created = mat.createAIJ([size, size])
            if created is not None:
                mat = created
        if hasattr(mat, "setUp"):
            mat.setUp()
        return mat

    def _build_residual_callback(self, solver_inputs: HydraulicSolverInputs):
        def _callback(_snes, state_vec, residual_vec):
            state = self._extract_vec_array(state_vec)
            started = perf_counter()
            residual_vector, _, _ = solver_inputs.system.assemble_residual_vector(state)
            self._last_residual_eval_cost_s += perf_counter() - started
            self._set_vec_array(residual_vec, residual_vector)
            return 0

        return _callback

    def _build_jacobian_callback(self, solver_inputs: HydraulicSolverInputs):
        def _callback(_snes, state_vec, jacobian, preconditioner):
            state = self._extract_vec_array(state_vec)
            started = perf_counter()
            triplet, _, _ = solver_inputs.system.assemble_sparse_jacobian_triplet(state)
            self._last_jacobian_eval_cost_s += perf_counter() - started
            self._load_triplet_into_matrix(jacobian, triplet)
            if preconditioner is not jacobian:
                self._load_triplet_into_matrix(preconditioner, triplet)
            return 0

        return _callback

    def _extract_vec_array(self, vec) -> NDArray[np.float64]:
        if hasattr(vec, "getArray"):
            return np.asarray(vec.getArray(), dtype=float).copy()
        return np.asarray(getattr(vec, "array"), dtype=float).copy()

    def _set_vec_array(self, vec, values: NDArray[np.float64]) -> None:
        array = np.asarray(values, dtype=float)
        if hasattr(vec, "setArray"):
            vec.setArray(array.copy())
            return
        if hasattr(vec, "getArray"):
            target = vec.getArray()
            target[...] = array
            return
        vec.array = array.copy()

    def _load_triplet_into_matrix(self, matrix, triplet: SparseJacobianTriplet) -> None:
        if hasattr(matrix, "zeroEntries"):
            matrix.zeroEntries()
        row_payload: dict[int, tuple[list[int], list[float]]] = {}
        for row, col, value in zip(triplet.rows, triplet.cols, triplet.data, strict=True):
            cols, values = row_payload.setdefault(int(row), ([], []))
            cols.append(int(col))
            values.append(float(value))
        for row, (cols, values) in row_payload.items():
            matrix.setValues([row], cols, values)
        if hasattr(matrix, "assemble"):
            matrix.assemble()


__all__ = ["PetscSnesKernelAdapter"]

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
from modular_simulation.connection.runtime.runtime import ConnectionRuntimeOrchestrator
from modular_simulation.connection.topology.network import ConnectionNetwork


def _default_delay_semantics() -> KernelDelaySemantics:
    return KernelDelaySemantics(
        strategy=KernelDelayStrategy.EXTERNAL_TRANSPORT_HISTORY,
        state_schema="transport_runtime_state",
        preserves_existing_transport_history=True,
        notes="SUNDIALS candidate preserves transport history as external runtime state.",
    )


def _default_delay_state_mapping() -> KernelDelayStateMapping:
    return KernelDelayStateMapping(
        payload_key="transport_runtime_state",
        mapped_fields=("edge_states", "previous_edge_flow_rates", "junction_states"),
        replacement_required=True,
        replacement_candidates=("augmented_state", "hybrid"),
        replacement_rule=(
            "Future candidates must publish an explicit mapping from current transport "
            "history semantics to any replacement delay bundle."
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
        residual_eval_cost_s=0.0,
        jacobian_eval_cost_s=0.0,
        linear_solve_cost_s=0.0,
    )


@dataclass
class SundialsIdaKernelAdapter:
    network: ConnectionNetwork
    runtime_orchestrator: ConnectionRuntimeOrchestrator
    delay_semantics: KernelDelaySemantics = field(default_factory=_default_delay_semantics)
    delay_state_mapping: KernelDelayStateMapping = field(
        default_factory=_default_delay_state_mapping
    )
    telemetry: KernelAdapterTelemetry = field(default_factory=_bootstrap_telemetry)
    _last_state_vector: NDArray[np.float64] | None = field(default=None, init=False, repr=False)
    _last_graph_revision: str | None = field(default=None, init=False, repr=False)

    def initialize(self, request: KernelInitializationRequest) -> KernelInitializationResult:
        compiled = self._ensure_compiled_hydraulic()
        if request.accepted_snapshot is not None:
            self.network.restore_validated_runtime_snapshot(snapshot=request.accepted_snapshot)
            self._sync_runtime_from_snapshot(request.accepted_snapshot)
            compiled = self._ensure_compiled_hydraulic()
        self._last_graph_revision = compiled.graph_revision
        self._last_state_vector = np.zeros(len(compiled.hydraulic.unknown_order), dtype=np.float64)
        return KernelInitializationResult(initialized=True, graph_revision=compiled.graph_revision)

    def warm_start(self, request: KernelWarmStartRequest) -> KernelWarmStartResult:
        self.network.restore_validated_runtime_snapshot(snapshot=request.accepted_snapshot)
        self._sync_runtime_from_snapshot(request.accepted_snapshot)
        compiled = self._ensure_compiled_hydraulic()
        self._last_graph_revision = compiled.graph_revision
        self._last_state_vector = np.zeros(len(compiled.hydraulic.unknown_order), dtype=np.float64)
        return KernelWarmStartResult(restored=True, graph_revision=compiled.graph_revision)

    def evaluate_candidate_step(
        self, request: KernelCandidateStepRequest
    ) -> KernelCandidateStepResult:
        compiled = self._ensure_compiled_hydraulic()
        solver_inputs = compiled.hydraulic.build_solver_inputs()
        initial_state = self._initial_state_vector(solver_inputs)

        residual_cost_s = 0.0
        jacobian_cost_s = 0.0
        linear_solve_cost_s = 0.0

        def residual_callback(
            t: float,
            y: Sequence[float],
            yp: Sequence[float],
            result: NDArray[np.float64],
        ) -> int:
            del t, yp
            nonlocal residual_cost_s
            started = perf_counter()
            residual_vector, _, _ = solver_inputs.system.assemble_residual_vector(
                np.asarray(y, dtype=np.float64)
            )
            residual_cost_s += perf_counter() - started
            result[:] = residual_vector
            return 0

        def jacobian_callback(
            t: float,
            cj: float,
            y: Sequence[float],
            yp: Sequence[float],
            residual: Sequence[float],
            jacobian: NDArray[np.float64],
        ) -> int:
            del t, cj, yp, residual
            nonlocal jacobian_cost_s
            started = perf_counter()
            triplet, _, _ = solver_inputs.system.assemble_sparse_jacobian_triplet(
                np.asarray(y, dtype=np.float64)
            )
            jacobian_cost_s += perf_counter() - started
            jacobian[:, :] = self._triplet_to_dense(triplet)
            return 0

        ida_factory = self._load_ida_factory()
        solver = ida_factory(
            resfn=residual_callback,
            jacfn=jacobian_callback,
            old_api=False,
        )

        started = perf_counter()
        solution = solver.solve(
            [0.0, request.macro_step_time_s],
            initial_state,
            np.zeros_like(initial_state),
        )
        linear_solve_cost_s += perf_counter() - started

        flag = getattr(solution, "flag", 0)
        accepted = int(flag) == 0
        values = getattr(solution, "values", None)
        if values is not None and getattr(values, "y", None) is not None:
            final_state = np.asarray(values.y[-1], dtype=np.float64)
        else:
            final_state = initial_state.copy()
        self._last_state_vector = final_state

        next_macro_step_index = self.telemetry.macro_step_index + 1
        simulation_time_s = self.telemetry.simulation_time_s + request.macro_step_time_s
        self._last_graph_revision = compiled.graph_revision
        self.telemetry = KernelAdapterTelemetry(
            macro_step_index=next_macro_step_index,
            macro_step_time_s=request.macro_step_time_s,
            simulation_time_s=simulation_time_s,
            graph_revision=compiled.graph_revision,
            executed_sequence=("sundials_ida_candidate_step",),
            transport_fallback_keys=(),
            junction_fallback_keys=(),
            used_fallback=False,
            residual_eval_cost_s=residual_cost_s,
            jacobian_eval_cost_s=jacobian_cost_s,
            linear_solve_cost_s=linear_solve_cost_s,
            hidden_solver_failure=not accepted,
        )
        return KernelCandidateStepResult(
            accepted=accepted,
            graph_revision=compiled.graph_revision,
            telemetry=self.telemetry,
            details=None if accepted else f"IDA solve failed with flag {flag}",
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

    def export_state_vector(self) -> Sequence[float]:
        compiled = self._ensure_compiled_hydraulic()
        if self._last_state_vector is None:
            return tuple(0.0 for _ in compiled.hydraulic.unknown_order)
        return tuple(float(value) for value in self._last_state_vector)

    def evaluate_residual(self, *, state_vector: Sequence[float]) -> Sequence[float]:
        solver_inputs = self._ensure_compiled_hydraulic().hydraulic.build_solver_inputs()
        residual_vector, _, _ = solver_inputs.system.assemble_residual_vector(
            np.asarray(state_vector, dtype=np.float64)
        )
        return tuple(float(value) for value in residual_vector)

    def evaluate_jacobian(self, *, state_vector: Sequence[float]) -> object:
        solver_inputs = self._ensure_compiled_hydraulic().hydraulic.build_solver_inputs()
        triplet, _, _ = solver_inputs.system.assemble_sparse_jacobian_triplet(
            np.asarray(state_vector, dtype=np.float64)
        )
        return triplet

    def capture_process_runtime_state(self) -> Mapping[str, object]:
        return {}

    def _ensure_compiled_hydraulic(self):
        compiled = self.network.compiled
        if compiled is None:
            compiled = self.network.compile()
        if compiled.hydraulic is None:
            raise RuntimeError("SundialsIdaKernelAdapter requires a compiled hydraulic graph")
        return compiled

    def _initial_state_vector(self, solver_inputs: HydraulicSolverInputs) -> NDArray[np.float64]:
        size = len(solver_inputs.unknown_order)
        if self._last_state_vector is not None and self._last_state_vector.shape == (size,):
            return self._last_state_vector.copy()
        return np.zeros(size, dtype=np.float64)

    def _load_ida_factory(self):
        try:
            module = import_module("scikits.odes")
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "SundialsIdaKernelAdapter requires scikits.odes with IDA support"
            ) from exc
        ida_factory = getattr(module, "ida", None)
        if ida_factory is None:
            raise RuntimeError("scikits.odes does not expose ida")
        return ida_factory

    def _sync_runtime_from_snapshot(self, snapshot: Mapping[str, object]) -> None:
        simulation_time_s = snapshot.get("simulation_time_s")
        macro_step_index = snapshot.get("macro_step_index")
        if isinstance(simulation_time_s, (int, float)):
            self.telemetry = KernelAdapterTelemetry(
                macro_step_index=int(macro_step_index) if isinstance(macro_step_index, int) else 0,
                macro_step_time_s=0.0,
                simulation_time_s=float(simulation_time_s),
                graph_revision=(
                    str(snapshot["graph_revision"])
                    if isinstance(snapshot.get("graph_revision"), str)
                    else None
                ),
                executed_sequence=(),
                transport_fallback_keys=(),
                junction_fallback_keys=(),
                used_fallback=False,
                residual_eval_cost_s=0.0,
                jacobian_eval_cost_s=0.0,
                linear_solve_cost_s=0.0,
            )

    @staticmethod
    def _triplet_to_dense(triplet: SparseJacobianTriplet) -> NDArray[np.float64]:
        dense = np.zeros(triplet.shape, dtype=np.float64)
        for row, col, value in zip(triplet.rows, triplet.cols, triplet.data, strict=True):
            dense[row, col] += float(value)
        return dense


__all__ = ["SundialsIdaKernelAdapter"]

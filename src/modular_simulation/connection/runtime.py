from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from importlib import import_module
import json
from math import isfinite
from typing import TYPE_CHECKING, Protocol, cast

from modular_simulation.connection.connection_layer import (
    MacroStepBookkeeping,
    PicardIterationGateConfig,
    TransportAndMixingUpdate,
    run_macro_coupling_step,
)
from modular_simulation.connection.hydraulic_compile import (
    apply_valve_commands_to_compiled_graph,
    solve_compiled_hydraulic_graph,
)
from modular_simulation.connection.hydraulic_solver import HydraulicSolveResult
from modular_simulation.connection.network import (
    ConnectionNetwork,
    QueuedReconfigurationTransaction,
)
from modular_simulation.connection.error_catalog import (
    IDEMPOTENCY_CONFLICT_CODE,
    REVISION_MISMATCH_CODE,
    VALIDATION_FAILURE_CODE,
    DiagnosticValueError,
    DiagnosticRuntimeError,
    coerce_diagnostic_payload,
    diagnostic_value_error,
    revision_details,
)
from modular_simulation.connection.state import PortCondition

if TYPE_CHECKING:
    from modular_simulation.thermodynamics.stream import StreamData, StreamPortIO
    from modular_simulation.thermodynamics.runtime_context import SimulationRuntimeContext

CONNECTED_PLANT_PHASE_ORDER: tuple[str, ...] = (
    "subsystem_sensor_update",
    "subsystem_calculation_update",
    "plant_calculation_update",
    "subsystem_controller_update",
    "subsystem_process_step",
    "connection_runtime_coupling",
)

HOT_INSTALL_STATE_MACHINE: tuple[str, ...] = (
    "Queued",
    "Staged",
    "Applied",
    "Skipped",
    "RolledBack",
)

SENSOR_ONLY_MUTATION_OPERATIONS: frozenset[str] = frozenset(
    {
        "create_sensor",
        "bind_sensor",
        "unbind_sensor",
        "remove_sensor",
    }
)

CONTROLLER_ONLY_MUTATION_OPERATIONS: frozenset[str] = frozenset(
    {
        "create_controller",
        "bind_controller_input",
        "bind_controller_output",
        "configure_controller_mode",
        "activate_controller",
    }
)

SENSOR_MUTATION_FORBIDDEN_FIELDS: frozenset[str] = frozenset(
    {
        "source",
        "target",
        "edge_id",
        "boundary_id",
        "junction_id",
        "inlet_ports",
        "outlet_ports",
        "radius_m",
        "length_m",
        "equation_name",
        "resistance_parameter_name",
        "mode",
        "manual_value",
        "open_fraction",
        "minimum_open_fraction",
        "maximum_open_fraction",
        "initial_open_fraction",
        "valve_id",
    }
)

CONTROLLER_MUTATION_FORBIDDEN_FIELDS: frozenset[str] = frozenset(
    {
        "source",
        "target",
        "edge_id",
        "boundary_id",
        "junction_id",
        "inlet_ports",
        "outlet_ports",
        "radius_m",
        "length_m",
        "equation_name",
        "resistance_parameter_name",
        "open_fraction",
        "minimum_open_fraction",
        "maximum_open_fraction",
        "initial_open_fraction",
        "line_id",
        "valve_id",
    }
)


@dataclass(frozen=True)
class BarrierReconfigurationReport:
    queue_size_before: int
    queue_size_after: int
    applied_request_ids: tuple[str, ...]
    skipped_request_ids: tuple[str, ...]
    graph_revision: str | None


@dataclass(frozen=True)
class ConnectionRuntimeStepResult:
    macro_step_index: int
    macro_step_time_s: float
    simulation_time_s: float
    graph_revision: str | None
    bookkeeping: MacroStepBookkeeping
    barrier_reconfiguration: BarrierReconfigurationReport


@dataclass(frozen=True)
class _ParsedReconfigurationRequest:
    request_id: str
    idempotency_key: str | None
    expected_revision: str | None
    metadata: Mapping[str, object]
    payload_fingerprint: str
    mutations: tuple[Mapping[str, object], ...]


@dataclass(frozen=True)
class _BatchLifecycleContext:
    baseline_graph_revision: str | None
    parsed_requests: tuple[_ParsedReconfigurationRequest, ...]


@dataclass(frozen=True)
class _HydraulicTopologyGuardSnapshot:
    process_specs: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...]
    boundary_specs: tuple[tuple[str, str, str], ...]
    edge_specs: tuple[tuple[str, str, str, str, str], ...]
    line_hydraulic_configs: tuple[
        tuple[
            str,
            str,
            str,
            str,
            float | None,
            float | None,
            float | None,
            str | None,
            float | None,
            float | None,
            float | None,
        ],
        ...,
    ]
    pending_valve_commands: tuple[tuple[str, float], ...]
    compiled_graph_revision: str | None
    compiled_hydraulic_graph_revision: str | None


class RuntimeHydraulicSolveStep(Protocol):
    def __call__(
        self,
        *,
        network: ConnectionNetwork,
        macro_step_time_s: float,
    ) -> HydraulicSolveResult: ...


class RuntimeTransportAndMixingStep(Protocol):
    def __call__(
        self,
        *,
        network: ConnectionNetwork,
        hydraulic_result: HydraulicSolveResult,
        macro_step_time_s: float,
    ) -> TransportAndMixingUpdate: ...


class RuntimeBoundaryPropagationStep(Protocol):
    def __call__(
        self,
        *,
        network: ConnectionNetwork,
        hydraulic_result: HydraulicSolveResult,
        transport_and_mixing_update: TransportAndMixingUpdate,
        macro_step_time_s: float,
    ) -> Mapping[str, PortCondition]: ...


class RuntimeSensorMutationDispatcher(Protocol):
    def __call__(
        self,
        *,
        operation: str,
        mutation: Mapping[str, object],
        request_metadata: Mapping[str, object],
    ) -> None: ...


class RuntimeControllerMutationDispatcher(Protocol):
    def __call__(
        self,
        *,
        operation: str,
        mutation: Mapping[str, object],
        request_metadata: Mapping[str, object],
    ) -> None: ...


class _DestructiveEditPlanLike(Protocol):
    edge_ids_to_detach: tuple[str, ...]


class _InvariantValidatorLike(Protocol):
    def plan_destructive_edit(
        self,
        *,
        network: ConnectionNetwork,
        mutation: Mapping[str, object],
        request_metadata: Mapping[str, object],
    ) -> _DestructiveEditPlanLike | None: ...


class _InvariantValidatorFactory(Protocol):
    def __call__(self) -> _InvariantValidatorLike: ...


class ConnectionRuntimeOrchestrator:
    """Runtime coupling orchestrator with deterministic barrier-commit semantics.

    Contract snapshot:
    - Connected-plant phase order is fixed by ``CONNECTED_PLANT_PHASE_ORDER``.
    - Runtime reconfiguration is a hot-install state machine: ``Queued -> Staged -> Applied``
      and ``Queued -> Staged -> Skipped`` for exact idempotent replay, or
      ``Queued -> Staged -> RolledBack`` on any failure.
    - Requests are applied in deterministic FIFO queue order.
    - Requests queued during a running macro-step are accepted but visible only at the next
      barrier, before the next macro-step executes.
    - Reusing an ``idempotency_key`` with a different payload is rejected as a poison request
      with no state change.
    - Any poison request at queue head strictly blocks following requests in that barrier.
    """

    def __init__(
        self,
        *,
        macro_step_hook: (Callable[[ConnectionNetwork, int, float], None] | None) = None,
        hydraulic_solve_step: RuntimeHydraulicSolveStep | None = None,
        transport_and_mixing_step: RuntimeTransportAndMixingStep | None = None,
        boundary_propagation_step: RuntimeBoundaryPropagationStep | None = None,
        sensor_mutation_dispatcher: RuntimeSensorMutationDispatcher | None = None,
        controller_mutation_dispatcher: RuntimeControllerMutationDispatcher | None = None,
        picard_gate_config: PicardIterationGateConfig | None = None,
        runtime_context: SimulationRuntimeContext | None = None,
    ) -> None:
        self._macro_step_hook: Callable[[ConnectionNetwork, int, float], None] | None = (
            macro_step_hook
        )
        self._hydraulic_solve_step: RuntimeHydraulicSolveStep = (
            hydraulic_solve_step
            if hydraulic_solve_step is not None
            else self._default_hydraulic_solve_step
        )
        self._transport_and_mixing_step: RuntimeTransportAndMixingStep = (
            transport_and_mixing_step
            if transport_and_mixing_step is not None
            else self._default_transport_and_mixing_step
        )
        self._runtime_context: SimulationRuntimeContext | None = runtime_context
        self._use_context_boundary_propagation: bool = boundary_propagation_step is None
        self._stream_port_io_by_node_id: dict[str, StreamPortIO] = {}
        self._feed_streams_by_boundary_id: dict[str, StreamData] = {}
        self._boundary_propagation_step: RuntimeBoundaryPropagationStep = (
            boundary_propagation_step
            if boundary_propagation_step is not None
            else self._default_boundary_propagation_step
        )
        self._refresh_boundary_propagation_step_from_context()
        self._sensor_mutation_dispatcher: RuntimeSensorMutationDispatcher | None = (
            sensor_mutation_dispatcher
        )
        self._controller_mutation_dispatcher: RuntimeControllerMutationDispatcher | None = (
            controller_mutation_dispatcher
        )
        self._picard_gate_config: PicardIterationGateConfig | None = picard_gate_config
        self._simulation_time_s: float = 0.0
        self._macro_step_index: int = 0
        self._macro_step_active: bool = False
        self._committed_idempotency_keys: set[str] = set()
        self._committed_idempotency_payloads: dict[str, str] = {}
        validator_module = import_module("modular_simulation.connection.invariant_validator")
        validator_factory = cast(
            _InvariantValidatorFactory,
            getattr(validator_module, "ConnectionMutationInvariantValidator"),
        )
        self._invariant_validator: _InvariantValidatorLike = validator_factory()

    @property
    def simulation_time_s(self) -> float:
        return self._simulation_time_s

    @property
    def macro_step_index(self) -> int:
        return self._macro_step_index

    @property
    def macro_step_active(self) -> bool:
        return self._macro_step_active

    @property
    def committed_idempotency_keys(self) -> tuple[str, ...]:
        return tuple(sorted(self._committed_idempotency_keys))

    @property
    def runtime_context(self) -> SimulationRuntimeContext | None:
        return self._runtime_context

    def set_runtime_context(self, runtime_context: SimulationRuntimeContext | None) -> None:
        self._runtime_context = runtime_context
        self._refresh_boundary_propagation_step_from_context()

    def bind_stream_port_io(self, *, node_id: str, stream_port_io: StreamPortIO) -> None:
        normalized_node_id = node_id.strip()
        if not normalized_node_id:
            raise ValueError("node_id must be a non-empty string")
        self._stream_port_io_by_node_id[normalized_node_id] = stream_port_io
        self._refresh_boundary_propagation_step_from_context()

    def bind_stream_port_ios(self, *, bindings: Mapping[str, StreamPortIO]) -> None:
        normalized_bindings: dict[str, StreamPortIO] = {}
        for node_id, stream_port_io in bindings.items():
            normalized_node_id = node_id.strip()
            if not normalized_node_id:
                raise ValueError("stream port I/O bindings require non-empty node ids")
            normalized_bindings[normalized_node_id] = stream_port_io
        self._stream_port_io_by_node_id = normalized_bindings
        self._refresh_boundary_propagation_step_from_context()

    def clear_stream_port_io_bindings(self) -> None:
        self._stream_port_io_by_node_id = {}
        self._refresh_boundary_propagation_step_from_context()

    def set_feed_stream(self, *, boundary_id: str, stream: StreamData) -> None:
        normalized_boundary_id = boundary_id.strip()
        if not normalized_boundary_id:
            raise ValueError("boundary_id must be a non-empty string")
        self._feed_streams_by_boundary_id[normalized_boundary_id] = stream
        self._refresh_boundary_propagation_step_from_context()

    def set_feed_streams(self, *, feed_streams: Mapping[str, StreamData]) -> None:
        normalized_feeds: dict[str, StreamData] = {}
        for boundary_id, stream in feed_streams.items():
            normalized_boundary_id = boundary_id.strip()
            if not normalized_boundary_id:
                raise ValueError("feed stream mappings require non-empty boundary ids")
            normalized_feeds[normalized_boundary_id] = stream
        self._feed_streams_by_boundary_id = normalized_feeds
        self._refresh_boundary_propagation_step_from_context()

    def clear_feed_streams(self) -> None:
        self._feed_streams_by_boundary_id = {}
        self._refresh_boundary_propagation_step_from_context()

    def _refresh_boundary_propagation_step_from_context(self) -> None:
        if not self._use_context_boundary_propagation:
            return
        if self._runtime_context is None:
            self._boundary_propagation_step = self._default_boundary_propagation_step
            return
        from modular_simulation.connection.thermo_coupling import (
            ThermoBoundaryPropagationConfig,
            ThermoBoundaryPropagationStep,
        )

        self._boundary_propagation_step = ThermoBoundaryPropagationStep(
            runtime_context=self._runtime_context,
            config=ThermoBoundaryPropagationConfig(
                stream_port_io_by_node_id=dict(self._stream_port_io_by_node_id),
                feed_streams_by_boundary_id=dict(self._feed_streams_by_boundary_id),
            ),
        )

    def set_runtime_state(
        self,
        *,
        simulation_time_s: float,
        macro_step_index: int,
        macro_step_active: bool,
        committed_idempotency_keys: Sequence[str],
    ) -> None:
        self._simulation_time_s = simulation_time_s
        self._macro_step_index = macro_step_index
        self._macro_step_active = macro_step_active
        self._committed_idempotency_keys = {key.strip() for key in committed_idempotency_keys}
        self._committed_idempotency_payloads = {}

    def step(
        self, *, network: ConnectionNetwork, macro_step_time_s: float
    ) -> ConnectionRuntimeStepResult:
        if macro_step_time_s < 0.0 or not isfinite(macro_step_time_s):
            raise ValueError("macro_step_time_s must be finite and non-negative")
        if self._macro_step_active:
            raise RuntimeError(
                "runtime mutation barrier is locked during active macro-step execution"
            )

        barrier_report = self._apply_reconfiguration_batch(network=network)

        self._macro_step_active = True
        try:
            if self._macro_step_hook is not None:
                self._macro_step_hook(
                    network,
                    self._macro_step_index + 1,
                    self._simulation_time_s + macro_step_time_s,
                )

            def _hydraulic_solve(*, macro_step_time_s: float) -> HydraulicSolveResult:
                return self._hydraulic_solve_step(
                    network=network,
                    macro_step_time_s=macro_step_time_s,
                )

            def _transport_update(
                *,
                hydraulic_result: HydraulicSolveResult,
                macro_step_time_s: float,
            ) -> TransportAndMixingUpdate:
                return self._transport_and_mixing_step(
                    network=network,
                    hydraulic_result=hydraulic_result,
                    macro_step_time_s=macro_step_time_s,
                )

            def _boundary_propagation(
                *,
                hydraulic_result: HydraulicSolveResult,
                transport_and_mixing_update: TransportAndMixingUpdate,
                macro_step_time_s: float,
            ) -> Mapping[str, PortCondition]:
                return self._boundary_propagation_step(
                    network=network,
                    hydraulic_result=hydraulic_result,
                    transport_and_mixing_update=transport_and_mixing_update,
                    macro_step_time_s=macro_step_time_s,
                )

            macro_step_result = run_macro_coupling_step(
                macro_step_time_s=macro_step_time_s,
                macro_step_index=self._macro_step_index + 1,
                hydraulic_solve_step=_hydraulic_solve,
                transport_update_step=_transport_update,
                boundary_propagation_step=_boundary_propagation,
                picard_gate_config=self._picard_gate_config,
            )
            self._macro_step_index += 1
            self._simulation_time_s += macro_step_time_s
        finally:
            self._macro_step_active = False

        current_graph_revision = None
        if network.compiled is not None:
            current_graph_revision = str(network.compiled.graph_revision)

        return ConnectionRuntimeStepResult(
            macro_step_index=self._macro_step_index,
            macro_step_time_s=macro_step_time_s,
            simulation_time_s=self._simulation_time_s,
            graph_revision=current_graph_revision,
            bookkeeping=macro_step_result.bookkeeping,
            barrier_reconfiguration=BarrierReconfigurationReport(
                queue_size_before=barrier_report.queue_size_before,
                queue_size_after=barrier_report.queue_size_after,
                applied_request_ids=barrier_report.applied_request_ids,
                skipped_request_ids=barrier_report.skipped_request_ids,
                graph_revision=current_graph_revision,
            ),
        )

    def save_runtime_snapshot(self, *, network: ConnectionNetwork) -> Mapping[str, object]:
        if self._macro_step_active:
            raise RuntimeError(
                "runtime snapshot capture is unavailable during active macro-step execution"
            )
        compiled = network.compiled
        graph_revision = None if compiled is None else str(compiled.graph_revision)
        queue = network.queued_reconfigurations
        return {
            "schema": "connection_runtime_v1",
            "simulation_time_s": self._simulation_time_s,
            "macro_step_index": self._macro_step_index,
            "macro_step_active": self._macro_step_active,
            "graph_revision": graph_revision,
            "queued_request_ids": tuple(item.request_id for item in queue),
            "queued_request_count": len(queue),
            "committed_idempotency_keys": tuple(sorted(self._committed_idempotency_keys)),
        }

    def resume_from_snapshot(
        self, *, network: ConnectionNetwork, snapshot: Mapping[str, object]
    ) -> None:
        schema = snapshot.get("schema")
        if schema != "connection_runtime_v1":
            raise ValueError(
                "invalid runtime snapshot payload: expected field 'schema' == 'connection_runtime_v1'"
            )

        simulation_time = snapshot.get("simulation_time_s")
        if not isinstance(simulation_time, (float, int)):
            raise ValueError(
                "invalid runtime snapshot payload: field 'simulation_time_s' must be finite number"
            )
        simulation_time_s = float(simulation_time)
        if simulation_time_s < 0.0 or not isfinite(simulation_time_s):
            raise ValueError(
                "invalid runtime snapshot payload: field 'simulation_time_s' must be finite number"
            )

        macro_step_index = snapshot.get("macro_step_index")
        if not isinstance(macro_step_index, int) or macro_step_index < 0:
            raise ValueError(
                "invalid runtime snapshot payload: field 'macro_step_index' must be non-negative integer"
            )

        macro_step_active = snapshot.get("macro_step_active")
        if macro_step_active is not False:
            raise ValueError(
                "invalid runtime snapshot payload: field 'macro_step_active' must be false at barrier"
            )

        idempotency_keys = snapshot.get("committed_idempotency_keys", ())
        if isinstance(idempotency_keys, str) or not isinstance(idempotency_keys, Sequence):
            raise ValueError(
                "invalid runtime snapshot payload: field 'committed_idempotency_keys' must be sequence of strings"
            )
        normalized_keys: set[str] = set()
        for key in idempotency_keys:
            if not isinstance(key, str) or not key.strip():
                raise ValueError(
                    "invalid runtime snapshot payload: field 'committed_idempotency_keys' must be sequence of strings"
                )
            normalized_keys.add(key.strip())

        del network
        self._simulation_time_s = simulation_time_s
        self._macro_step_index = macro_step_index
        self._macro_step_active = False
        self._committed_idempotency_keys = normalized_keys

    def _apply_reconfiguration_batch(
        self, *, network: ConnectionNetwork
    ) -> BarrierReconfigurationReport:
        network_snapshot = network.capture_reconfiguration_state()
        queued_requests = network.drain_reconfiguration_queue()
        if not queued_requests:
            compiled = network.compiled
            return BarrierReconfigurationReport(
                queue_size_before=0,
                queue_size_after=0,
                applied_request_ids=(),
                skipped_request_ids=(),
                graph_revision=None if compiled is None else compiled.graph_revision,
            )

        runtime_snapshot = (
            self._simulation_time_s,
            self._macro_step_index,
            set(self._committed_idempotency_keys),
            dict(self._committed_idempotency_payloads),
        )

        applied_request_ids: list[str] = []
        skipped_request_ids: list[str] = []
        try:
            lifecycle_context = self._parse_lifecycle_stage(
                network=network, queued_requests=queued_requests
            )
            self._semantic_validate_lifecycle_stage(lifecycle_context.parsed_requests)
            graph_revision = self._invariant_validate_and_stage_lifecycle(
                network=network,
                lifecycle_context=lifecycle_context,
                applied_request_ids=applied_request_ids,
                skipped_request_ids=skipped_request_ids,
            )

            return BarrierReconfigurationReport(
                queue_size_before=len(queued_requests),
                queue_size_after=0,
                applied_request_ids=tuple(applied_request_ids),
                skipped_request_ids=tuple(skipped_request_ids),
                graph_revision=graph_revision,
            )
        except Exception as error:
            network.restore_reconfiguration_state(network_snapshot)
            self._simulation_time_s = runtime_snapshot[0]
            self._macro_step_index = runtime_snapshot[1]
            self._committed_idempotency_keys = runtime_snapshot[2]
            self._committed_idempotency_payloads = runtime_snapshot[3]
            rollback_message = f"reconfiguration transaction rollback: {error}"
            raise DiagnosticRuntimeError(
                coerce_diagnostic_payload(
                    error=error,
                    default_code=VALIDATION_FAILURE_CODE,
                    message=rollback_message,
                )
            ) from error

    def _parse_lifecycle_stage(
        self,
        *,
        network: ConnectionNetwork,
        queued_requests: Sequence[QueuedReconfigurationTransaction],
    ) -> _BatchLifecycleContext:
        baseline_graph_revision = None
        compiled = network.compiled
        if compiled is not None:
            baseline_graph_revision = str(compiled.graph_revision)

        parsed_requests: list[_ParsedReconfigurationRequest] = []
        for request in queued_requests:
            metadata = dict(request.metadata)
            mutations = tuple(dict(mutation) for mutation in request.mutations)
            parsed_requests.append(
                _ParsedReconfigurationRequest(
                    request_id=request.request_id,
                    idempotency_key=request.idempotency_key,
                    expected_revision=request.expected_revision,
                    metadata=metadata,
                    payload_fingerprint=self._request_payload_fingerprint(
                        metadata=metadata,
                        mutations=mutations,
                    ),
                    mutations=mutations,
                )
            )

        return _BatchLifecycleContext(
            baseline_graph_revision=baseline_graph_revision,
            parsed_requests=tuple(parsed_requests),
        )

    def _semantic_validate_lifecycle_stage(
        self, parsed_requests: Sequence[_ParsedReconfigurationRequest]
    ) -> None:
        for request in parsed_requests:
            for mutation in request.mutations:
                operation_value = mutation.get("operation")
                if not isinstance(operation_value, str) or not operation_value.strip():
                    raise diagnostic_value_error(
                        code=VALIDATION_FAILURE_CODE,
                        message=(
                            f"request '{request.request_id}' has invalid mutation payload: "
                            + "field 'operation' must be non-empty string"
                        ),
                        path="mutations[].operation",
                        hint="set each mutation operation to a non-empty string",
                    )

    def _invariant_validate_and_stage_lifecycle(
        self,
        *,
        network: ConnectionNetwork,
        lifecycle_context: _BatchLifecycleContext,
        applied_request_ids: list[str],
        skipped_request_ids: list[str],
    ) -> str | None:
        has_compile_impact = False
        for request in lifecycle_context.parsed_requests:
            self._validate_expected_revision_invariant(
                request=request,
                baseline_graph_revision=lifecycle_context.baseline_graph_revision,
            )
            should_skip = self._validate_idempotency_invariant(
                request=request,
                skipped_request_ids=skipped_request_ids,
            )
            if should_skip:
                continue

            has_compile_impact = (
                self._stage_mutations_for_request(
                    network=network,
                    request=request,
                )
                or has_compile_impact
            )

            if request.idempotency_key is not None:
                self._committed_idempotency_keys.add(request.idempotency_key)
                self._committed_idempotency_payloads[request.idempotency_key] = (
                    request.payload_fingerprint
                )
            applied_request_ids.append(request.request_id)

        return self._compile_preview_lifecycle_stage(
            network=network, has_applied=has_compile_impact
        )

    def _validate_expected_revision_invariant(
        self,
        *,
        request: _ParsedReconfigurationRequest,
        baseline_graph_revision: str | None,
    ) -> None:
        if request.expected_revision is None:
            return
        if request.expected_revision == baseline_graph_revision:
            return

        actual_revision = baseline_graph_revision
        if actual_revision is None:
            actual_revision = "<none>"
        raise diagnostic_value_error(
            code=REVISION_MISMATCH_CODE,
            message=(
                f"request '{request.request_id}' expected_revision '{request.expected_revision}' "
                + f"does not match active graph revision '{actual_revision}'"
            ),
            path="expected_revision",
            hint="retry with the current graph revision or omit expected_revision",
            revision=revision_details(
                expected=request.expected_revision,
                actual=baseline_graph_revision,
            ),
        )

    def _validate_idempotency_invariant(
        self,
        *,
        request: _ParsedReconfigurationRequest,
        skipped_request_ids: list[str],
    ) -> bool:
        idempotency_key = request.idempotency_key
        if idempotency_key is None or idempotency_key not in self._committed_idempotency_keys:
            return False

        committed_fingerprint = self._committed_idempotency_payloads.get(idempotency_key)
        if committed_fingerprint is None:
            raise diagnostic_value_error(
                code=IDEMPOTENCY_CONFLICT_CODE,
                message=(
                    f"request '{request.request_id}' reuses idempotency_key "
                    + f"'{idempotency_key}' but committed payload is unavailable"
                ),
                path="idempotency_key",
                hint="use a new idempotency_key for changed payloads",
            )
        if committed_fingerprint != request.payload_fingerprint:
            raise diagnostic_value_error(
                code=IDEMPOTENCY_CONFLICT_CODE,
                message=(
                    f"request '{request.request_id}' reuses idempotency_key "
                    + f"'{idempotency_key}' with different payload"
                ),
                path="idempotency_key",
                hint="reuse idempotency_key only with identical metadata and mutations",
            )
        skipped_request_ids.append(request.request_id)
        return True

    def _stage_mutations_for_request(
        self,
        *,
        network: ConnectionNetwork,
        request: _ParsedReconfigurationRequest,
    ) -> bool:
        requires_compile = False
        for mutation_index, mutation in enumerate(request.mutations, start=1):
            try:
                operation = str(mutation.get("operation", "")).strip()
                requires_compile = self._mutation_requires_compile(operation) or requires_compile
                self._apply_mutation(
                    network=network,
                    mutation=mutation,
                    request_metadata=request.metadata,
                )
            except Exception as error:
                raise DiagnosticValueError(
                    coerce_diagnostic_payload(
                        error=error,
                        default_code=VALIDATION_FAILURE_CODE,
                        message=f"request '{request.request_id}' mutation {mutation_index} failed: {error}",
                        path=f"mutations[{mutation_index}]",
                    )
                ) from error
        return requires_compile

    def _mutation_requires_compile(self, operation: str) -> bool:
        if operation == "set_valve_open_fraction":
            return False
        if operation in SENSOR_ONLY_MUTATION_OPERATIONS:
            return False
        if operation in CONTROLLER_ONLY_MUTATION_OPERATIONS:
            return False
        return True

    def _compile_preview_lifecycle_stage(
        self, *, network: ConnectionNetwork, has_applied: bool
    ) -> str | None:
        if not has_applied:
            compiled = network.compiled
            return None if compiled is None else compiled.graph_revision

        try:
            compiled = network.compile()
        except Exception as error:
            raise DiagnosticValueError(
                coerce_diagnostic_payload(
                    error=error,
                    default_code=VALIDATION_FAILURE_CODE,
                    message=f"queued reconfiguration compile validation failed: {error}",
                    path="compile",
                )
            ) from error
        return compiled.graph_revision

    def _request_payload_fingerprint(
        self,
        *,
        metadata: Mapping[str, object],
        mutations: Sequence[Mapping[str, object]],
    ) -> str:
        return json.dumps(
            {
                "metadata": dict(metadata),
                "mutations": [dict(mutation) for mutation in mutations],
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )

    def _apply_mutation(
        self,
        *,
        network: ConnectionNetwork,
        mutation: Mapping[str, object],
        request_metadata: Mapping[str, object],
    ) -> None:
        operation_value = mutation.get("operation")
        if not isinstance(operation_value, str) or not operation_value.strip():
            raise diagnostic_value_error(
                code=VALIDATION_FAILURE_CODE,
                message="invalid mutation payload: field 'operation' must be non-empty string",
                path="operation",
                hint="set operation to a non-empty string",
            )
        operation = operation_value.strip()

        if operation in SENSOR_ONLY_MUTATION_OPERATIONS:
            self._assert_sensor_mutation_zero_resistance_guard(
                operation=operation, mutation=mutation
            )
            if self._sensor_mutation_dispatcher is None:
                raise ValueError(
                    "sensor runtime mutation dispatcher is not configured for sensor operations"
                )
            topology_snapshot = self._capture_hydraulic_topology_guard_snapshot(network)
            self._sensor_mutation_dispatcher(
                operation=operation,
                mutation=mutation,
                request_metadata=request_metadata,
            )
            if self._capture_hydraulic_topology_guard_snapshot(network) != topology_snapshot:
                raise ValueError(
                    f"sensor operation '{operation}' must not mutate hydraulic graph parameters or topology"
                )
            return

        if operation in CONTROLLER_ONLY_MUTATION_OPERATIONS:
            self._assert_controller_mutation_zero_resistance_guard(
                operation=operation,
                mutation=mutation,
            )
            if self._controller_mutation_dispatcher is None:
                raise ValueError(
                    "controller runtime mutation dispatcher is not configured for controller operations"
                )
            topology_snapshot = self._capture_hydraulic_topology_guard_snapshot(network)
            self._controller_mutation_dispatcher(
                operation=operation,
                mutation=mutation,
                request_metadata=request_metadata,
            )
            if self._capture_hydraulic_topology_guard_snapshot(network) != topology_snapshot:
                raise ValueError(
                    f"controller operation '{operation}' must not mutate hydraulic graph parameters or topology"
                )
            return

        destructive_plan = self._invariant_validator.plan_destructive_edit(
            network=network,
            mutation=mutation,
            request_metadata=request_metadata,
        )
        if destructive_plan is not None:
            for dependent_edge_id in destructive_plan.edge_ids_to_detach:
                _ = network.remove_connection(edge_id=dependent_edge_id)

        if operation in {"add_connection", "connect_line"}:
            source = self._require_non_empty_string(mutation, "source", operation)
            target = self._require_non_empty_string(mutation, "target", operation)
            edge_id_value = mutation.get("edge_id", mutation.get("line_id"))
            if edge_id_value is None:
                _ = network.connect(source, target)
                return
            if not isinstance(edge_id_value, str) or not edge_id_value.strip():
                raise ValueError(
                    "operation '{}' optional field 'edge_id' or 'line_id' must be non-empty string".format(
                        operation
                    )
                )
            _ = network.connect(source, target, edge_id=edge_id_value.strip())
            return

        if operation in {"remove_connection", "remove_edge", "disconnect_line", "remove_line"}:
            _ = network.remove_connection(
                edge_id=mutation.get("edge_id", mutation.get("line_id")),
                source=mutation.get("source"),
                target=mutation.get("target"),
            )
            return

        if operation == "rewire_connection":
            edge_id = self._require_non_empty_string(mutation, "edge_id", operation)
            source = self._require_non_empty_string(mutation, "source", operation)
            target = self._require_non_empty_string(mutation, "target", operation)
            network.rewire_connection(edge_id=edge_id, source=source, target=target)
            return

        if operation == "add_boundary_source":
            boundary_id = self._require_non_empty_string(mutation, "boundary_id", operation)
            port_name = mutation.get("port_name", "outlet")
            if not isinstance(port_name, str) or not port_name.strip():
                raise ValueError(
                    "operation 'add_boundary_source' optional field 'port_name' must be non-empty string"
                )
            network.add_boundary_source(boundary_id, port_name=port_name.strip())
            return

        if operation == "add_boundary_sink":
            boundary_id = self._require_non_empty_string(mutation, "boundary_id", operation)
            port_name = mutation.get("port_name", "inlet")
            if not isinstance(port_name, str) or not port_name.strip():
                raise ValueError(
                    "operation 'add_boundary_sink' optional field 'port_name' must be non-empty string"
                )
            network.add_boundary_sink(boundary_id, port_name=port_name.strip())
            return

        if operation in {"remove_boundary", "remove_junction"}:
            removal_boundary_id = mutation.get("boundary_id", mutation.get("junction_id"))
            network.remove_boundary(boundary_id=removal_boundary_id)
            return

        if operation in {"add_process_port", "add_inlet", "add_outlet"}:
            direction: object = mutation.get("direction")
            if operation == "add_inlet":
                direction = "inlet"
            elif operation == "add_outlet":
                direction = "outlet"
            network.add_process_port(
                process_id=mutation.get("process_id"),
                direction=direction,
                port_name=mutation.get("port_name"),
            )
            return

        if operation in {"remove_process_port", "remove_port", "remove_inlet", "remove_outlet"}:
            direction = mutation.get("direction")
            if operation == "remove_inlet":
                direction = "inlet"
            elif operation == "remove_outlet":
                direction = "outlet"
            network.remove_process_port(
                process_id=mutation.get("process_id"),
                direction=direction,
                port_name=mutation.get("port_name"),
            )
            return

        if operation in {"remove_process", "remove_unit", "remove_junction_process"}:
            network.remove_process(process_id=mutation.get("process_id"))
            return

        if operation == "set_valve_open_fraction":
            line_id = self._require_non_empty_string(mutation, "line_id", operation)
            open_fraction = self._require_finite_float(mutation, "open_fraction", operation)
            network.stage_valve_open_fraction_command(
                line_id=line_id,
                open_fraction=open_fraction,
            )
            return

        if operation == "configure_line_geometry":
            line_id = self._require_non_empty_string(mutation, "line_id", operation)
            radius_m = self._require_finite_float(mutation, "radius_m", operation)
            length_m = self._require_finite_float(mutation, "length_m", operation)
            network.configure_line_geometry(
                line_id=line_id,
                radius_m=radius_m,
                length_m=length_m,
                equation_name=mutation.get("equation_name"),
                resistance_parameter_name=mutation.get("resistance_parameter_name"),
            )
            return

        if operation == "configure_line_resistance":
            line_id = self._require_non_empty_string(mutation, "line_id", operation)
            mode = self._require_non_empty_string(mutation, "mode", operation)
            network.configure_line_resistance(
                line_id=line_id,
                mode=mode,
                manual_value=mutation.get("manual_value"),
            )
            return

        if operation == "attach_line_valve":
            line_id = self._require_non_empty_string(mutation, "line_id", operation)
            valve_id = self._require_non_empty_string(mutation, "valve_id", operation)
            network.attach_line_valve(
                line_id=line_id,
                valve_id=valve_id,
                minimum_open_fraction=self._optional_finite_float(
                    mutation=mutation,
                    field_name="minimum_open_fraction",
                    operation=operation,
                    default=0.0,
                ),
                maximum_open_fraction=self._optional_finite_float(
                    mutation=mutation,
                    field_name="maximum_open_fraction",
                    operation=operation,
                    default=1.0,
                ),
                initial_open_fraction=self._optional_finite_float(
                    mutation=mutation,
                    field_name="initial_open_fraction",
                    operation=operation,
                    default=1.0,
                ),
                equation_name=mutation.get("equation_name"),
                resistance_parameter_name=mutation.get("resistance_parameter_name"),
            )
            return

        if operation in {"add_process", "add_unit", "add_junction"}:
            process_id = self._require_non_empty_string(mutation, "process_id", operation)
            inlet_ports = self._require_string_sequence(mutation, "inlet_ports", operation)
            outlet_ports = self._require_string_sequence(mutation, "outlet_ports", operation)
            network.add_process(process_id, inlet_ports=inlet_ports, outlet_ports=outlet_ports)
            return

        raise diagnostic_value_error(
            code=VALIDATION_FAILURE_CODE,
            message=f"unsupported reconfiguration operation '{operation}'",
            path="operation",
            hint="use a supported reconfiguration operation name",
        )

    def _assert_sensor_mutation_zero_resistance_guard(
        self,
        *,
        operation: str,
        mutation: Mapping[str, object],
    ) -> None:
        forbidden_fields = [
            field_name
            for field_name in SENSOR_MUTATION_FORBIDDEN_FIELDS
            if field_name in mutation and mutation.get(field_name) is not None
        ]
        if forbidden_fields:
            raise ValueError(
                "operation '{}' must not include hydraulic/topology fields {}; ".format(
                    operation,
                    sorted(forbidden_fields),
                )
                + "sensor operations are zero-resistance instrumentation updates"
            )

    def _capture_hydraulic_topology_guard_snapshot(
        self,
        network: ConnectionNetwork,
    ) -> _HydraulicTopologyGuardSnapshot:
        process_specs = tuple(
            (
                process_id,
                process_spec.inlet_ports,
                process_spec.outlet_ports,
            )
            for process_id, process_spec in sorted(network._process_specs.items())
        )
        boundary_specs = tuple(
            (
                boundary_id,
                boundary_spec.direction,
                boundary_spec.port_name,
            )
            for boundary_id, boundary_spec in sorted(network._boundary_specs.items())
        )
        edge_specs = tuple(
            (
                edge.edge_id,
                edge.source.node_id,
                edge.source.port_name,
                edge.target.node_id,
                edge.target.port_name,
            )
            for edge in network._edges
        )

        line_hydraulic_configs: list[
            tuple[
                str,
                str,
                str,
                str,
                float | None,
                float | None,
                float | None,
                str | None,
                float | None,
                float | None,
                float | None,
            ]
        ] = []
        for line_id, config in sorted(network._line_hydraulic_configs.items()):
            valve = config.valve
            line_hydraulic_configs.append(
                (
                    line_id,
                    config.equation_name,
                    config.resistance_parameter_name,
                    config.resistance.mode,
                    config.resistance.radius_m,
                    config.resistance.length_m,
                    config.resistance.manual_value,
                    None if valve is None else valve.valve_id,
                    None if valve is None else valve.minimum_open_fraction,
                    None if valve is None else valve.maximum_open_fraction,
                    None if valve is None else valve.initial_open_fraction,
                )
            )

        pending_valve_commands = tuple(sorted(network._pending_valve_open_fractions.items()))
        compiled = network.compiled
        compiled_graph_revision = None if compiled is None else str(compiled.graph_revision)
        compiled_hydraulic_graph_revision = (
            None
            if compiled is None or compiled.hydraulic is None
            else str(compiled.hydraulic.graph_revision)
        )

        return _HydraulicTopologyGuardSnapshot(
            process_specs=process_specs,
            boundary_specs=boundary_specs,
            edge_specs=edge_specs,
            line_hydraulic_configs=tuple(line_hydraulic_configs),
            pending_valve_commands=pending_valve_commands,
            compiled_graph_revision=compiled_graph_revision,
            compiled_hydraulic_graph_revision=compiled_hydraulic_graph_revision,
        )

    def _assert_controller_mutation_zero_resistance_guard(
        self,
        *,
        operation: str,
        mutation: Mapping[str, object],
    ) -> None:
        forbidden_fields = [
            field_name
            for field_name in CONTROLLER_MUTATION_FORBIDDEN_FIELDS
            if field_name in mutation and mutation.get(field_name) is not None
        ]
        if forbidden_fields:
            raise ValueError(
                "operation '{}' must not include hydraulic/topology fields {}; ".format(
                    operation,
                    sorted(forbidden_fields),
                )
                + "controller operations are zero-resistance instrumentation updates"
            )

    def _require_non_empty_string(
        self,
        mutation: Mapping[str, object],
        field_name: str,
        operation: str,
    ) -> str:
        value = mutation.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"operation '{operation}' requires non-empty string field '{field_name}'"
            )
        return value.strip()

    def _require_string_sequence(
        self,
        mutation: Mapping[str, object],
        field_name: str,
        operation: str,
    ) -> tuple[str, ...]:
        value = mutation.get(field_name)
        if isinstance(value, str) or not isinstance(value, Sequence):
            raise ValueError(f"operation '{operation}' requires sequence field '{field_name}'")
        normalized: list[str] = []
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise ValueError(
                    f"operation '{operation}' requires sequence field '{field_name}' with non-empty strings"
                )
            normalized.append(item.strip())
        return tuple(normalized)

    def _require_finite_float(
        self,
        mutation: Mapping[str, object],
        field_name: str,
        operation: str,
    ) -> float:
        value = mutation.get(field_name)
        if isinstance(value, bool) or not isinstance(value, (float, int)):
            raise ValueError(
                f"operation '{operation}' requires finite numeric field '{field_name}'"
            )
        scalar = float(value)
        if not isfinite(scalar):
            raise ValueError(
                f"operation '{operation}' requires finite numeric field '{field_name}'"
            )
        return scalar

    def _optional_finite_float(
        self,
        *,
        mutation: Mapping[str, object],
        field_name: str,
        operation: str,
        default: float,
    ) -> float:
        value = mutation.get(field_name)
        if value is None:
            return default
        if isinstance(value, bool) or not isinstance(value, (float, int)):
            raise ValueError(
                f"operation '{operation}' optional field '{field_name}' must be finite numeric"
            )
        scalar = float(value)
        if not isfinite(scalar):
            raise ValueError(
                f"operation '{operation}' optional field '{field_name}' must be finite numeric"
            )
        return scalar

    def _default_hydraulic_solve_step(
        self,
        *,
        network: ConnectionNetwork,
        macro_step_time_s: float,
    ) -> HydraulicSolveResult:
        del macro_step_time_s
        compiled = network.compiled
        if compiled is None or compiled.hydraulic is None:
            raise RuntimeError(
                "runtime macro-step is unavailable: compiled hydraulic graph is required"
            )

        pending_valve_commands = network.consume_pending_valve_open_fraction_commands()
        hydraulic_graph = compiled.hydraulic
        if pending_valve_commands:
            hydraulic_graph = apply_valve_commands_to_compiled_graph(
                compiled=hydraulic_graph,
                valve_commands=pending_valve_commands,
            )
            network.replace_compiled_hydraulic(hydraulic=hydraulic_graph)

        return solve_compiled_hydraulic_graph(hydraulic_graph)

    def _default_transport_and_mixing_step(
        self,
        *,
        network: ConnectionNetwork,
        hydraulic_result: HydraulicSolveResult,
        macro_step_time_s: float,
    ) -> TransportAndMixingUpdate:
        del network, hydraulic_result, macro_step_time_s
        return TransportAndMixingUpdate(transport_results={})

    def _default_boundary_propagation_step(
        self,
        *,
        network: ConnectionNetwork,
        hydraulic_result: HydraulicSolveResult,
        transport_and_mixing_update: TransportAndMixingUpdate,
        macro_step_time_s: float,
    ) -> Mapping[str, PortCondition]:
        del network, hydraulic_result, transport_and_mixing_update, macro_step_time_s
        return {}


__all__ = [
    "CONNECTED_PLANT_PHASE_ORDER",
    "HOT_INSTALL_STATE_MACHINE",
    "BarrierReconfigurationReport",
    "ConnectionRuntimeOrchestrator",
    "ConnectionRuntimeStepResult",
    "RuntimeBoundaryPropagationStep",
    "RuntimeControllerMutationDispatcher",
    "RuntimeHydraulicSolveStep",
    "RuntimeSensorMutationDispatcher",
    "RuntimeTransportAndMixingStep",
]

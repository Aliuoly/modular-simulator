from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json
from typing import Protocol

from modular_simulation.connection.error_catalog import (
    IDEMPOTENCY_CONFLICT_CODE,
    REVISION_MISMATCH_CODE,
    VALIDATION_FAILURE_CODE,
    DiagnosticRuntimeError,
    DiagnosticValueError,
    coerce_diagnostic_payload,
    diagnostic_value_error,
    revision_details,
)
from modular_simulation.connection.network import (
    ConnectionNetwork,
    QueuedReconfigurationTransaction,
)


@dataclass(frozen=True)
class BarrierReconfigurationReport:
    """Report returned after attempting to apply a batch of reconfiguration requests.

    Responsibility:
        Convey how many requests were present before and after processing, which
        request IDs were applied or skipped, and the resulting graph revision
        (if any). This is a lightweight value object used by callers to inspect
        the outcome of a barrier application without exposing processing internals.
    """

    queue_size_before: int
    queue_size_after: int
    applied_request_ids: tuple[str, ...]
    skipped_request_ids: tuple[str, ...]
    graph_revision: str | None


@dataclass(frozen=True)
class RuntimeBarrierStateSnapshot:
    """Snapshot of runtime barrier-related state owned by the runtime.

    Responsibility:
        Capture the minimal runtime-side state required to rollback or restore
        barrier processing: simulation time, macro-step index, and committed
        idempotency mapping. The processor itself does not mutate these values
        directly but relies on a runtime owner implementing capture/restore.
    """

    simulation_time_s: float
    macro_step_index: int
    committed_idempotency_keys: frozenset[str]
    committed_idempotency_payloads: tuple[tuple[str, str], ...]


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


class _ReconfigurationBarrierRuntimeOwner(Protocol):
    def _capture_barrier_runtime_state(self) -> RuntimeBarrierStateSnapshot: ...

    def _restore_barrier_runtime_state(self, snapshot: RuntimeBarrierStateSnapshot) -> None: ...

    def _is_idempotency_key_committed(self, idempotency_key: str) -> bool: ...

    def _get_committed_idempotency_payload(self, idempotency_key: str) -> str | None: ...

    def _record_committed_idempotency(
        self, *, idempotency_key: str, payload_fingerprint: str
    ) -> None: ...

    def _apply_barrier_mutation(
        self,
        *,
        network: ConnectionNetwork,
        mutation: Mapping[str, object],
        request_metadata: Mapping[str, object],
    ) -> None: ...


class ReconfigurationBarrierProcessor:
    """Processor that applies queued reconfiguration transactions at a barrier.

    Responsibility:
        Own the lifecycle for parsing, semantic and invariant validation,
        staging of mutations, and compile-preview for a drained batch of
        queued reconfiguration transactions. The runtime (runtime owner)
        remains responsible for time/macro-step, idempotency storage,
        save/restore of runtime state, and executing hydraulic solve steps; the
        processor coordinates with that runtime owner but does not own those
        concerns.
    """

    def __init__(self, *, runtime_owner: _ReconfigurationBarrierRuntimeOwner) -> None:
        self._runtime_owner = runtime_owner

    def apply_reconfiguration_batch(
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

        runtime_snapshot = self._runtime_owner._capture_barrier_runtime_state()
        applied_request_ids: list[str] = []
        skipped_request_ids: list[str] = []
        try:
            lifecycle_context = self._parse_lifecycle_stage(
                network=network,
                queued_requests=queued_requests,
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
            self._runtime_owner._restore_barrier_runtime_state(runtime_snapshot)
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
                self._runtime_owner._record_committed_idempotency(
                    idempotency_key=request.idempotency_key,
                    payload_fingerprint=request.payload_fingerprint,
                )
            applied_request_ids.append(request.request_id)

        return self._compile_preview_lifecycle_stage(
            network=network,
            has_applied=has_compile_impact,
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
        if idempotency_key is None or not self._runtime_owner._is_idempotency_key_committed(
            idempotency_key
        ):
            return False

        committed_fingerprint = self._runtime_owner._get_committed_idempotency_payload(
            idempotency_key
        )
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
                self._runtime_owner._apply_barrier_mutation(
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
        if operation == "set_pump_speed":
            return False
        if operation == "set_heat_actuator_rate":
            return False
        if operation == "attach_line_heat_actuator":
            return False
        if operation in {
            "create_sensor",
            "bind_sensor",
            "unbind_sensor",
            "remove_sensor",
        }:
            return False
        if operation in {
            "create_controller",
            "bind_controller_input",
            "bind_controller_output",
            "configure_controller_mode",
            "activate_controller",
        }:
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


__all__ = [
    "BarrierReconfigurationReport",
    "ReconfigurationBarrierProcessor",
    "RuntimeBarrierStateSnapshot",
]

from __future__ import annotations

from collections.abc import Callable, Mapping, MutableMapping, Sequence
from dataclasses import dataclass
from math import isfinite
from typing import Protocol, cast, runtime_checkable

from ..domain.domain_contracts import (
    validate_reconfiguration_request_metadata,
)
from ..domain.error_catalog import (
    COMPATIBILITY_FAILURE_CODE,
    REVISION_MISMATCH_CODE,
    VALIDATION_FAILURE_CODE,
    diagnostic_value_error,
    revision_details,
)
from ..topology.network import (
    ConnectionNetwork,
    QueuedReconfigurationTransaction,
)
from .runtime import ConnectionRuntimeOrchestrator
from .runtime_port_snapshot_store import (
    RuntimePortSnapshotPayload,
    RuntimePortSnapshotStore,
)
from .runtime_snapshot_schema import (
    validate_runtime_checkpoint_envelope,
)
from modular_simulation.framework.system import (
    CHECKPOINT_INTEGRITY_MISMATCH_ERROR_CODE,
    CHECKPOINT_VERSION_MISMATCH_ERROR_CODE,
    checkpoint_payload_checksum,
    checkpoint_runtime_package_metadata,
)

RUNTIME_SNAPSHOT_SCHEMA_MARKER = "connection.runtime.snapshot"
RUNTIME_SNAPSHOT_SCHEMA_VERSION = 3


@dataclass(frozen=True)
class _ValidatedQueuedRequest:
    request_id: str
    idempotency_key: str | None
    expected_revision: str | None
    metadata: dict[str, object]
    mutations: tuple[dict[str, object], ...]


@dataclass(frozen=True)
class ValidatedRuntimeSnapshot:
    simulation_time_s: float
    macro_step_index: int
    graph_revision: str | None
    package_name: str
    package_version: str
    next_edge_index: int
    next_reconfiguration_index: int
    next_revision_index: int
    queued_requests: tuple[_ValidatedQueuedRequest, ...]
    committed_idempotency_keys: tuple[str, ...]
    process_runtime_state: dict[str, object]
    port_condition_store: RuntimePortSnapshotPayload


@runtime_checkable
class _RuntimePortSnapshotStorePersistenceLike(Protocol):
    def snapshot_payload(self) -> RuntimePortSnapshotPayload: ...

    def restore_from_payload(self, payload: Mapping[str, object]) -> None: ...


def save_runtime_snapshot_contract(
    *,
    runtime: ConnectionRuntimeOrchestrator,
    network: ConnectionNetwork,
    process_runtime_state: Mapping[str, object],
) -> dict[str, object]:
    compiled = network.compiled
    graph_revision = None if compiled is None else str(compiled.graph_revision)
    queue_payload: list[dict[str, object]] = []
    for queued in network.queued_reconfigurations:
        queue_payload.append(
            {
                "request_id": queued.request_id,
                "idempotency_key": queued.idempotency_key,
                "expected_revision": queued.expected_revision,
                "metadata": _normalize_mapping_payload(queued.metadata),
                "mutations": [
                    _normalize_mapping_payload(mutation) for mutation in queued.mutations
                ],
            }
        )

    snapshot_payload: dict[str, object] = {
        "runtime": {
            "simulation_time_s": runtime.simulation_time_s,
            "macro_step_index": runtime.macro_step_index,
            "macro_step_active": runtime.macro_step_active,
        },
        "process_runtime_state": _normalize_mapping_payload(process_runtime_state),
        "port_condition_store": _runtime_port_condition_snapshot_payload(runtime),
        "connection_runtime_state": {
            "graph_revision": graph_revision,
            "next_edge_index": network.next_edge_index,
            "next_reconfiguration_index": network.next_reconfiguration_index,
            "next_revision_index": network.next_revision_index,
            "queued_reconfigurations": queue_payload,
            "queued_request_ids": [queued["request_id"] for queued in queue_payload],
            "committed_idempotency_keys": list(runtime.committed_idempotency_keys),
        },
    }

    envelope_without_checksum: dict[str, object] = {
        "schema_marker": RUNTIME_SNAPSHOT_SCHEMA_MARKER,
        "schema_version": RUNTIME_SNAPSHOT_SCHEMA_VERSION,
        "graph_revision": graph_revision,
        "package_metadata": checkpoint_runtime_package_metadata(),
        "snapshot": snapshot_payload,
        "pending_command_journal": queue_payload,
    }

    envelope = dict(envelope_without_checksum)
    envelope["integrity_checksum"] = checkpoint_payload_checksum(envelope_without_checksum)
    return envelope


def validate_runtime_snapshot_contract(snapshot: Mapping[str, object]) -> ValidatedRuntimeSnapshot:
    normalized_snapshot = cast(
        dict[str, object],
        validate_runtime_checkpoint_envelope(snapshot=snapshot).model_dump(
            mode="python", by_alias=True
        ),
    )
    schema_marker = normalized_snapshot["schema_marker"]
    if schema_marker != RUNTIME_SNAPSHOT_SCHEMA_MARKER:
        raise diagnostic_value_error(
            code=VALIDATION_FAILURE_CODE,
            message="invalid runtime snapshot payload: field 'schema_marker' does not match expected marker",
            path="schema_marker",
            hint="load a snapshot generated by the same runtime snapshot contract",
        )

    schema_version = normalized_snapshot["schema_version"]
    if schema_version != RUNTIME_SNAPSHOT_SCHEMA_VERSION:
        raise diagnostic_value_error(
            code=COMPATIBILITY_FAILURE_CODE,
            message="invalid runtime snapshot payload: field 'schema_version' does not match expected version",
            path="schema_version",
            hint="use a snapshot with matching schema_version",
        )

    graph_revision = normalized_snapshot["graph_revision"]
    if graph_revision is not None:
        graph_revision = _require_non_empty_string(graph_revision, "graph_revision")

    package_metadata_section = _require_mapping(
        normalized_snapshot["package_metadata"],
        "package_metadata",
    )
    _require_exact_keys(
        "package_metadata",
        package_metadata_section,
        ("package_name", "package_version"),
    )
    package_name = _require_non_empty_string(
        package_metadata_section["package_name"],
        "package_metadata.package_name",
    )
    package_version = _require_non_empty_string(
        package_metadata_section["package_version"],
        "package_metadata.package_version",
    )

    snapshot_section = _require_mapping(normalized_snapshot["snapshot"], "snapshot")
    _require_exact_keys(
        "snapshot",
        snapshot_section,
        (
            "runtime",
            "process_runtime_state",
            "port_condition_store",
            "connection_runtime_state",
        ),
    )

    runtime_section = _require_mapping(snapshot_section["runtime"], "runtime")
    _require_exact_keys(
        "runtime",
        runtime_section,
        ("simulation_time_s", "macro_step_index", "macro_step_active"),
    )
    simulation_time_s = _require_non_negative_finite_number(
        runtime_section["simulation_time_s"],
        "runtime.simulation_time_s",
    )
    macro_step_index = _require_non_negative_int(
        runtime_section["macro_step_index"],
        "runtime.macro_step_index",
    )
    macro_step_active = runtime_section["macro_step_active"]
    if macro_step_active is not False:
        raise ValueError(
            "invalid runtime snapshot payload: field 'runtime.macro_step_active' must be false at barrier"
        )

    process_runtime_state = _require_mapping(
        snapshot_section["process_runtime_state"],
        "process_runtime_state",
    )
    normalized_process_state = _normalize_mapping_payload(process_runtime_state)
    normalized_port_condition_store = _normalize_port_condition_store_payload(
        snapshot_section["port_condition_store"],
        "port_condition_store",
    )

    connection_section = _require_mapping(
        snapshot_section["connection_runtime_state"],
        "connection_runtime_state",
    )
    _require_exact_keys(
        "connection_runtime_state",
        connection_section,
        (
            "graph_revision",
            "next_edge_index",
            "next_reconfiguration_index",
            "next_revision_index",
            "queued_reconfigurations",
            "queued_request_ids",
            "committed_idempotency_keys",
        ),
    )
    connection_graph_revision = connection_section["graph_revision"]
    if connection_graph_revision is not None:
        connection_graph_revision = _require_non_empty_string(
            connection_graph_revision,
            "connection_runtime_state.graph_revision",
        )
    if connection_graph_revision != graph_revision:
        raise ValueError(
            "invalid runtime snapshot payload: field 'graph_revision' must match "
            + "snapshot connection runtime graph revision"
        )

    next_edge_index = _require_non_negative_int(
        connection_section["next_edge_index"],
        "connection_runtime_state.next_edge_index",
    )
    next_reconfiguration_index = _require_non_negative_int(
        connection_section["next_reconfiguration_index"],
        "connection_runtime_state.next_reconfiguration_index",
    )
    next_revision_index = _require_non_negative_int(
        connection_section["next_revision_index"],
        "connection_runtime_state.next_revision_index",
    )

    committed_idempotency_keys = _require_string_sequence(
        connection_section["committed_idempotency_keys"],
        "connection_runtime_state.committed_idempotency_keys",
    )

    validated_requests = _validate_queued_requests(
        connection_section["queued_reconfigurations"],
        "connection_runtime_state.queued_reconfigurations",
    )
    pending_command_journal = _validate_queued_requests(
        normalized_snapshot["pending_command_journal"],
        "pending_command_journal",
    )
    if validated_requests != pending_command_journal:
        raise ValueError(
            "invalid runtime snapshot payload: field 'pending_command_journal' must match "
            + "connection runtime queued reconfigurations"
        )

    ordered_request_ids = tuple(request.request_id for request in validated_requests)

    queued_request_ids = _require_string_sequence(
        connection_section["queued_request_ids"],
        "connection_runtime_state.queued_request_ids",
    )
    if ordered_request_ids != queued_request_ids:
        raise ValueError(
            "invalid runtime snapshot payload: field 'connection_runtime_state.queued_request_ids' "
            + "must match queued_reconfigurations ordering"
        )

    provided_checksum = _require_non_empty_string(
        normalized_snapshot["integrity_checksum"],
        "integrity_checksum",
    )
    checksum_payload = dict(normalized_snapshot)
    checksum_payload.pop("integrity_checksum", None)
    expected_checksum = checkpoint_payload_checksum(checksum_payload)
    if provided_checksum != expected_checksum:
        raise ValueError(
            f"[{CHECKPOINT_INTEGRITY_MISMATCH_ERROR_CODE}] invalid runtime snapshot payload: "
            + "field 'integrity_checksum' does not match payload checksum"
        )

    return ValidatedRuntimeSnapshot(
        simulation_time_s=simulation_time_s,
        macro_step_index=macro_step_index,
        graph_revision=connection_graph_revision,
        package_name=package_name,
        package_version=package_version,
        next_edge_index=next_edge_index,
        next_reconfiguration_index=next_reconfiguration_index,
        next_revision_index=next_revision_index,
        queued_requests=validated_requests,
        committed_idempotency_keys=committed_idempotency_keys,
        process_runtime_state=normalized_process_state,
        port_condition_store=normalized_port_condition_store,
    )


def _validate_queued_requests(
    queued_reconfiguration_values: object,
    field_name: str,
) -> tuple[_ValidatedQueuedRequest, ...]:
    if isinstance(queued_reconfiguration_values, str) or not isinstance(
        queued_reconfiguration_values,
        Sequence,
    ):
        raise ValueError(
            f"invalid runtime snapshot payload: field '{field_name}' must be a sequence"
        )

    validated_requests: list[_ValidatedQueuedRequest] = []
    for request_index, request in enumerate(queued_reconfiguration_values, start=1):
        request_mapping = _require_mapping(request, field_name + f"[{request_index}]")
        _require_exact_keys(
            f"{field_name}[{request_index}]",
            request_mapping,
            ("request_id", "idempotency_key", "expected_revision", "metadata", "mutations"),
        )
        request_id = _require_non_empty_string(
            request_mapping["request_id"],
            field_name + f"[{request_index}].request_id",
        )

        idempotency_key = request_mapping["idempotency_key"]
        if idempotency_key is not None:
            idempotency_key = _require_non_empty_string(
                idempotency_key,
                field_name + f"[{request_index}].idempotency_key",
            )

        expected_revision = request_mapping["expected_revision"]
        if expected_revision is not None:
            expected_revision = _require_non_empty_string(
                expected_revision,
                field_name + f"[{request_index}].expected_revision",
            )

        metadata = _require_mapping(
            request_mapping["metadata"],
            field_name + f"[{request_index}].metadata",
        )
        normalized_metadata = validate_reconfiguration_request_metadata(
            metadata=_normalize_mapping_payload(metadata)
        ).as_mapping()

        mutations_value = request_mapping["mutations"]
        if isinstance(mutations_value, str) or not isinstance(mutations_value, Sequence):
            raise ValueError(
                f"invalid runtime snapshot payload: field '{field_name}[{request_index}].mutations' "
                + "must be a sequence"
            )

        normalized_mutations: list[dict[str, object]] = []
        for mutation_index, mutation in enumerate(mutations_value, start=1):
            mutation_mapping = _require_mapping(
                mutation,
                field_name + f"[{request_index}].mutations[{mutation_index}]",
            )
            _ = _require_non_empty_string(
                mutation_mapping.get("operation"),
                field_name + f"[{request_index}].mutations[{mutation_index}].operation",
            )
            normalized_mutations.append(_normalize_mapping_payload(mutation_mapping))

        validated_requests.append(
            _ValidatedQueuedRequest(
                request_id=request_id,
                idempotency_key=idempotency_key,
                expected_revision=expected_revision,
                metadata=normalized_metadata,
                mutations=tuple(normalized_mutations),
            )
        )

    return tuple(validated_requests)


def restore_runtime_snapshot_contract(
    *,
    runtime: ConnectionRuntimeOrchestrator,
    network: ConnectionNetwork,
    process_runtime_state_sink: MutableMapping[str, object],
    snapshot: Mapping[str, object],
    process_runtime_validator: Callable[[Mapping[str, object]], Mapping[str, object]] | None = None,
) -> None:
    if runtime.macro_step_active:
        raise RuntimeError(
            "runtime snapshot restore is unavailable during active macro-step execution"
        )

    validated_snapshot = validate_runtime_snapshot_contract(snapshot)
    runtime_package_metadata = checkpoint_runtime_package_metadata()
    if (
        validated_snapshot.package_name != runtime_package_metadata["package_name"]
        or validated_snapshot.package_version != runtime_package_metadata["package_version"]
    ):
        raise diagnostic_value_error(
            code=COMPATIBILITY_FAILURE_CODE,
            message=(
                f"[{CHECKPOINT_VERSION_MISMATCH_ERROR_CODE}] incompatible runtime snapshot payload: "
                + "checkpoint package metadata does not match runtime package metadata"
            ),
            path="package_metadata",
            hint="restore snapshots with matching runtime package metadata",
        )

    current_graph_revision = None if network.compiled is None else network.compiled.graph_revision
    if validated_snapshot.graph_revision != current_graph_revision:
        raise diagnostic_value_error(
            code=REVISION_MISMATCH_CODE,
            message=(
                "invalid runtime snapshot payload: field 'connection_runtime_state.graph_revision' "
                + "must match currently active compiled graph revision"
            ),
            path="connection_runtime_state.graph_revision",
            hint="retry restore onto a runtime with matching active graph revision",
            revision=revision_details(
                expected=validated_snapshot.graph_revision,
                actual=current_graph_revision,
            ),
        )

    normalized_process_state = validated_snapshot.process_runtime_state
    if process_runtime_validator is not None:
        normalized_process_state = _normalize_mapping_payload(
            process_runtime_validator(validated_snapshot.process_runtime_state)
        )

    runtime_backup = (
        runtime.simulation_time_s,
        runtime.macro_step_index,
        runtime.macro_step_active,
        runtime.committed_idempotency_keys,
    )
    queue_backup = tuple(network.queued_reconfigurations)
    edge_index_backup = network.next_edge_index
    reconfiguration_index_backup = network.next_reconfiguration_index
    revision_index_backup = network.next_revision_index
    process_state_backup = dict(process_runtime_state_sink)
    port_condition_store_backup = _runtime_port_condition_snapshot_payload(runtime)

    staged_queue = [
        QueuedReconfigurationTransaction(
            request_id=item.request_id,
            idempotency_key=item.idempotency_key,
            expected_revision=item.expected_revision,
            metadata=item.metadata,
            mutations=item.mutations,
        )
        for item in validated_snapshot.queued_requests
    ]

    try:
        runtime.set_runtime_state(
            simulation_time_s=validated_snapshot.simulation_time_s,
            macro_step_index=validated_snapshot.macro_step_index,
            macro_step_active=False,
            committed_idempotency_keys=validated_snapshot.committed_idempotency_keys,
        )

        network.set_reconfiguration_counters(
            next_edge_index=validated_snapshot.next_edge_index,
            next_reconfiguration_index=validated_snapshot.next_reconfiguration_index,
            next_revision_index=validated_snapshot.next_revision_index,
        )
        network.replace_queued_reconfigurations(staged_queue)

        _restore_runtime_port_condition_snapshot(
            runtime=runtime,
            payload=validated_snapshot.port_condition_store,
        )

        process_runtime_state_sink.clear()
        process_runtime_state_sink.update(normalized_process_state)
    except Exception:
        runtime.set_runtime_state(
            simulation_time_s=runtime_backup[0],
            macro_step_index=runtime_backup[1],
            macro_step_active=runtime_backup[2],
            committed_idempotency_keys=runtime_backup[3],
        )

        network.replace_queued_reconfigurations(queue_backup)
        network.set_reconfiguration_counters(
            next_edge_index=edge_index_backup,
            next_reconfiguration_index=reconfiguration_index_backup,
            next_revision_index=revision_index_backup,
        )

        process_runtime_state_sink.clear()
        process_runtime_state_sink.update(process_state_backup)
        _restore_runtime_port_condition_snapshot(
            runtime=runtime,
            payload=port_condition_store_backup,
        )
        raise


def runtime_replay_state_hash(
    *,
    tick: int,
    runtime: ConnectionRuntimeOrchestrator,
    network: ConnectionNetwork,
    process_runtime_state: Mapping[str, object],
) -> str:
    if tick < 0:
        raise ValueError("deterministic replay hash tick must be a non-negative integer")
    payload = _runtime_replay_hash_payload(
        tick=tick,
        runtime=runtime,
        network=network,
        process_runtime_state=process_runtime_state,
    )
    return checkpoint_payload_checksum(payload)


def verify_runtime_replay_hashes(
    *,
    baseline_hashes: Mapping[int, str],
    replay_hashes: Mapping[int, str],
) -> None:
    baseline_ticks = tuple(sorted(baseline_hashes.keys()))
    replay_ticks = tuple(sorted(replay_hashes.keys()))
    if baseline_ticks != replay_ticks:
        raise ValueError(
            "deterministic replay hash comparison requires identical selected ticks: "
            + f"baseline={baseline_ticks!r}, replay={replay_ticks!r}"
        )

    mismatches: list[str] = []
    for tick in baseline_ticks:
        baseline_hash = baseline_hashes[tick]
        replay_hash = replay_hashes[tick]
        if baseline_hash != replay_hash:
            mismatches.append(f"tick {tick}: baseline={baseline_hash}, replay={replay_hash}")

    if mismatches:
        raise ValueError(
            "deterministic replay hash mismatch detected at selected ticks: "
            + "; ".join(mismatches)
        )


def _runtime_replay_hash_payload(
    *,
    tick: int,
    runtime: ConnectionRuntimeOrchestrator,
    network: ConnectionNetwork,
    process_runtime_state: Mapping[str, object],
) -> dict[str, object]:
    queued_reconfiguration_payload: list[dict[str, object]] = []
    for queued in network.queued_reconfigurations:
        queued_reconfiguration_payload.append(
            {
                "request_id": queued.request_id,
                "idempotency_key": queued.idempotency_key,
                "expected_revision": queued.expected_revision,
                "metadata": _normalize_mapping_payload(queued.metadata),
                "mutations": [
                    _normalize_mapping_payload(mutation) for mutation in queued.mutations
                ],
            }
        )

    compiled = network.compiled
    compiled_topology_payload: dict[str, object] | None = None
    if compiled is not None:
        compiled_topology_payload = {
            "graph_revision": str(compiled.graph_revision),
            "process_nodes": [
                {
                    "process_id": node.process_id,
                    "inlet_ports": list(node.inlet_ports),
                    "outlet_ports": list(node.outlet_ports),
                }
                for node in compiled.topology.process_nodes
            ],
            "boundary_nodes": [
                {
                    "boundary_id": node.boundary_id,
                    "port_name": node.port_name,
                    "direction": node.direction,
                }
                for node in compiled.topology.boundary_nodes
            ],
            "junction_nodes": [
                {
                    "junction_id": node.junction_id,
                    "port_names": list(node.port_names),
                }
                for node in compiled.topology.junction_nodes
            ],
            "edges": [
                {
                    "edge_id": edge.edge_id,
                    "source": {
                        "node_id": edge.source.node_id,
                        "port_name": edge.source.port_name,
                    },
                    "target": {
                        "node_id": edge.target.node_id,
                        "port_name": edge.target.port_name,
                    },
                }
                for edge in compiled.topology.edges
            ],
        }

    return {
        "tick": tick,
        "runtime": {
            "simulation_time_s": runtime.simulation_time_s,
            "macro_step_index": runtime.macro_step_index,
            "macro_step_active": runtime.macro_step_active,
            "committed_idempotency_keys": list(runtime.committed_idempotency_keys),
        },
        "network": {
            "next_edge_index": network.next_edge_index,
            "next_reconfiguration_index": network.next_reconfiguration_index,
            "next_revision_index": network.next_revision_index,
            "compiled_topology": compiled_topology_payload,
            "queued_reconfigurations": queued_reconfiguration_payload,
            "queued_request_ids": [
                queued["request_id"] for queued in queued_reconfiguration_payload
            ],
        },
        "process_runtime_state": _normalize_mapping_payload(process_runtime_state),
        "port_condition_store": _runtime_port_condition_snapshot_payload(runtime),
    }


def _runtime_port_condition_snapshot_payload(
    runtime: ConnectionRuntimeOrchestrator,
) -> RuntimePortSnapshotPayload:
    store = _runtime_port_snapshot_store(runtime)
    return store.snapshot_payload()


def _restore_runtime_port_condition_snapshot(
    *,
    runtime: ConnectionRuntimeOrchestrator,
    payload: Mapping[str, object],
) -> None:
    store = _runtime_port_snapshot_store(runtime)
    store.restore_from_payload(payload)


def _normalize_port_condition_store_payload(
    payload: object,
    field_name: str,
) -> RuntimePortSnapshotPayload:
    payload_mapping = _require_mapping(payload, field_name)
    store = RuntimePortSnapshotStore()
    try:
        store.restore_from_payload(payload_mapping)
    except ValueError as error:
        message = str(error).replace("runtime port snapshot", "runtime snapshot")
        field_token = "invalid runtime snapshot payload: field '"
        if message.startswith(field_token):
            field_path, separator, remainder = message[len(field_token) :].partition("'")
            if separator and not field_path.startswith(field_name + "."):
                message = field_token + f"{field_name}.{field_path}'" + remainder
        raise ValueError(message) from error
    return store.snapshot_payload()


def _runtime_port_snapshot_store(
    runtime: ConnectionRuntimeOrchestrator,
) -> _RuntimePortSnapshotStorePersistenceLike:
    store = getattr(runtime, "_runtime_port_snapshot_store", None)
    if not isinstance(store, _RuntimePortSnapshotStorePersistenceLike):
        raise ValueError(
            "invalid runtime snapshot payload: runtime port snapshot store is unavailable"
        )
    return store


def _require_exact_keys(
    context: str,
    payload: Mapping[str, object],
    expected_keys: tuple[str, ...],
) -> None:
    actual_keys = tuple(payload.keys())
    if set(actual_keys) != set(expected_keys):
        raise ValueError(
            f"invalid runtime snapshot payload: field '{context}' keys must be exactly {expected_keys!r}"
        )


def _require_mapping(value: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(
            f"invalid runtime snapshot payload: field '{field_name}' must be a mapping"
        )
    typed_mapping = cast(Mapping[object, object], value)
    return {str(key): field_value for key, field_value in typed_mapping.items()}


def _require_non_negative_finite_number(value: object, field_name: str) -> float:
    if not isinstance(value, (int, float)):
        raise ValueError(
            f"invalid runtime snapshot payload: field '{field_name}' must be a finite non-negative number"
        )
    normalized = float(value)
    if normalized < 0.0 or not isfinite(normalized):
        raise ValueError(
            f"invalid runtime snapshot payload: field '{field_name}' must be a finite non-negative number"
        )
    return normalized


def _require_non_negative_int(value: object, field_name: str) -> int:
    if not isinstance(value, int) or value < 0:
        raise ValueError(
            f"invalid runtime snapshot payload: field '{field_name}' must be a non-negative integer"
        )
    return value


def _require_non_empty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"invalid runtime snapshot payload: field '{field_name}' must be a non-empty string"
        )
    return value.strip()


def _require_string_sequence(value: object, field_name: str) -> tuple[str, ...]:
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError(
            f"invalid runtime snapshot payload: field '{field_name}' must be a sequence of strings"
        )
    normalized_values: list[str] = []
    for item in value:
        normalized_values.append(_require_non_empty_string(item, field_name))
    return tuple(normalized_values)


def _normalize_mapping_payload(payload: Mapping[str, object]) -> dict[str, object]:
    normalized: dict[str, object] = {}
    for key in sorted(payload.keys()):
        value = payload[key]
        normalized_key = str(key)
        if isinstance(value, Mapping):
            typed_nested_mapping = cast(Mapping[object, object], value)
            nested_mapping = {
                str(nested_key): nested_value
                for nested_key, nested_value in typed_nested_mapping.items()
            }
            normalized[normalized_key] = _normalize_mapping_payload(nested_mapping)
            continue
        if isinstance(value, str):
            normalized[normalized_key] = value
            continue
        if isinstance(value, Sequence):
            normalized[normalized_key] = _normalize_sequence_payload(value)
            continue
        normalized[normalized_key] = value
    return normalized


def _normalize_sequence_payload(payload: Sequence[object]) -> list[object]:
    normalized: list[object] = []
    for value in payload:
        if isinstance(value, Mapping):
            typed_nested_mapping = cast(Mapping[object, object], value)
            nested_mapping = {
                str(nested_key): nested_value
                for nested_key, nested_value in typed_nested_mapping.items()
            }
            normalized.append(_normalize_mapping_payload(nested_mapping))
            continue
        if isinstance(value, str):
            normalized.append(value)
            continue
        if isinstance(value, Sequence):
            normalized.append(_normalize_sequence_payload(value))
            continue
        normalized.append(value)
    return normalized


__all__ = [
    "RUNTIME_SNAPSHOT_SCHEMA_MARKER",
    "RUNTIME_SNAPSHOT_SCHEMA_VERSION",
    "ValidatedRuntimeSnapshot",
    "runtime_replay_state_hash",
    "restore_runtime_snapshot_contract",
    "save_runtime_snapshot_contract",
    "verify_runtime_replay_hashes",
    "validate_runtime_snapshot_contract",
]

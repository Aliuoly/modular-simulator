from __future__ import annotations

from collections.abc import Mapping
from math import isfinite
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from ..domain.domain_contracts import (
    MutationCommand,
    ReconfigurationRequestMetadata,
)


def _non_empty_token(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"field '{field_name}' must be a non-empty string")
    return normalized


def _validation_error_message(error: ValidationError) -> str:
    first_error = error.errors()[0]
    message = str(first_error.get("msg", "invalid runtime snapshot payload"))
    prefix = "Value error, "
    return message[len(prefix) :] if message.startswith(prefix) else message


class LiveRuntimeSnapshotPayload(BaseModel):
    schema_name: str = Field(alias="schema")
    simulation_time_s: float
    macro_step_index: int
    macro_step_active: bool
    graph_revision: str | None = None
    queued_request_ids: tuple[str, ...] = Field(default_factory=tuple)
    queued_request_count: int
    committed_idempotency_keys: tuple[str, ...] = Field(default_factory=tuple)
    transport_runtime_state: dict[str, object] = Field(default_factory=dict)

    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid",
        arbitrary_types_allowed=True,
        populate_by_name=True,
    )

    @field_validator("schema_name")
    @classmethod
    def _validate_schema_name(cls, value: str) -> str:
        if value != "connection_runtime_v1":
            raise ValueError(
                "invalid runtime snapshot payload: expected field 'schema' == 'connection_runtime_v1'"
            )
        return value

    @field_validator("simulation_time_s")
    @classmethod
    def _validate_simulation_time(cls, value: float) -> float:
        if value < 0.0 or not isfinite(value):
            raise ValueError(
                "invalid runtime snapshot payload: field 'simulation_time_s' must be finite number"
            )
        return float(value)

    @field_validator("macro_step_index")
    @classmethod
    def _validate_macro_step_index(cls, value: int) -> int:
        if value < 0:
            raise ValueError(
                "invalid runtime snapshot payload: field 'macro_step_index' must be non-negative integer"
            )
        return value

    @field_validator("macro_step_active")
    @classmethod
    def _validate_macro_step_active(cls, value: bool) -> bool:
        if value is not False:
            raise ValueError(
                "invalid runtime snapshot payload: field 'macro_step_active' must be false at barrier"
            )
        return value

    @field_validator("graph_revision")
    @classmethod
    def _validate_graph_revision(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _non_empty_token(value, field_name="graph_revision")

    @field_validator("queued_request_ids", "committed_idempotency_keys")
    @classmethod
    def _validate_string_tuple(cls, value: tuple[str, ...], info: object) -> tuple[str, ...]:
        field_name = getattr(info, "field_name", "value")
        return tuple(_non_empty_token(item, field_name=field_name) for item in value)

    @field_validator("queued_request_count")
    @classmethod
    def _validate_queue_count(cls, value: int) -> int:
        if value < 0:
            raise ValueError(
                "invalid runtime snapshot payload: field 'queued_request_count' must be non-negative integer"
            )
        return value

    @model_validator(mode="after")
    def _validate_queue_count_matches(self) -> "LiveRuntimeSnapshotPayload":
        if self.queued_request_count != len(self.queued_request_ids):
            raise ValueError(
                "invalid runtime snapshot payload: field 'queued_request_count' must match queued_request_ids length"
            )
        return self


class _RuntimePackageMetadata(BaseModel):
    package_name: str
    package_version: str

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    @field_validator("package_name", "package_version")
    @classmethod
    def _validate_non_empty(cls, value: str, info: object) -> str:
        field_name = getattr(info, "field_name", "value")
        return _non_empty_token(value, field_name=field_name)


class _RuntimeBarrierStatePayload(BaseModel):
    simulation_time_s: float
    macro_step_index: int
    macro_step_active: bool

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    @field_validator("simulation_time_s")
    @classmethod
    def _validate_simulation_time(cls, value: float) -> float:
        if value < 0.0 or not isfinite(value):
            raise ValueError(
                "invalid runtime snapshot payload: field 'runtime.simulation_time_s' must be finite number"
            )
        return float(value)

    @field_validator("macro_step_index")
    @classmethod
    def _validate_macro_step_index(cls, value: int) -> int:
        if value < 0:
            raise ValueError(
                "invalid runtime snapshot payload: field 'runtime.macro_step_index' must be non-negative integer"
            )
        return value

    @field_validator("macro_step_active")
    @classmethod
    def _validate_macro_step_active(cls, value: bool) -> bool:
        if value is not False:
            raise ValueError(
                "invalid runtime snapshot payload: field 'runtime.macro_step_active' must be false at barrier"
            )
        return value


class _QueuedRequestPayload(BaseModel):
    request_id: str
    idempotency_key: str | None = None
    expected_revision: str | None = None
    metadata: ReconfigurationRequestMetadata = Field(default_factory=ReconfigurationRequestMetadata)
    mutations: tuple[MutationCommand, ...]

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    @field_validator("request_id", "idempotency_key", "expected_revision")
    @classmethod
    def _validate_tokens(cls, value: str | None, info: object) -> str | None:
        if value is None:
            return None
        field_name = getattr(info, "field_name", "value")
        return _non_empty_token(value, field_name=field_name)


class _ConnectionRuntimeStatePayload(BaseModel):
    graph_revision: str | None = None
    next_edge_index: int
    next_reconfiguration_index: int
    next_revision_index: int
    queued_reconfigurations: tuple[_QueuedRequestPayload, ...]
    queued_request_ids: tuple[str, ...]
    committed_idempotency_keys: tuple[str, ...]

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    @field_validator("graph_revision")
    @classmethod
    def _validate_graph_revision(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _non_empty_token(value, field_name="connection_runtime_state.graph_revision")

    @field_validator(
        "next_edge_index",
        "next_reconfiguration_index",
        "next_revision_index",
    )
    @classmethod
    def _validate_non_negative_index(cls, value: int, info: object) -> int:
        if value < 0:
            field_name = getattr(info, "field_name", "value")
            raise ValueError(
                f"invalid runtime snapshot payload: field 'connection_runtime_state.{field_name}' must be non-negative integer"
            )
        return value

    @field_validator("queued_request_ids", "committed_idempotency_keys")
    @classmethod
    def _validate_string_tuple(cls, value: tuple[str, ...], info: object) -> tuple[str, ...]:
        field_name = getattr(info, "field_name", "value")
        return tuple(
            _non_empty_token(value=item, field_name=f"connection_runtime_state.{field_name}")
            for item in value
        )


class _RuntimeCheckpointSnapshot(BaseModel):
    runtime: _RuntimeBarrierStatePayload
    process_runtime_state: dict[str, object]
    port_condition_store: dict[str, object]
    connection_runtime_state: _ConnectionRuntimeStatePayload
    transport_runtime_state: dict[str, object] = Field(default_factory=dict)

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", arbitrary_types_allowed=True)


class RuntimeCheckpointEnvelope(BaseModel):
    schema_marker: str
    schema_version: int
    graph_revision: str | None = None
    package_metadata: _RuntimePackageMetadata
    snapshot: _RuntimeCheckpointSnapshot
    pending_command_journal: tuple[_QueuedRequestPayload, ...]
    integrity_checksum: str

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    @field_validator("schema_marker")
    @classmethod
    def _validate_schema_marker(cls, value: str) -> str:
        return _non_empty_token(value, field_name="schema_marker")

    @field_validator("schema_version")
    @classmethod
    def _validate_schema_version(cls, value: int) -> int:
        if value < 0:
            raise ValueError(
                "invalid runtime snapshot payload: field 'schema_version' must be non-negative integer"
            )
        return value

    @field_validator("graph_revision", "integrity_checksum")
    @classmethod
    def _validate_optional_token(cls, value: str | None, info: object) -> str | None:
        if value is None:
            return None
        field_name = getattr(info, "field_name", "value")
        return _non_empty_token(value, field_name=field_name)


def validate_live_runtime_snapshot_payload(*, snapshot: object) -> LiveRuntimeSnapshotPayload:
    if not isinstance(snapshot, Mapping):
        raise ValueError("invalid snapshot payload: expected mapping")
    try:
        return LiveRuntimeSnapshotPayload.model_validate(snapshot)
    except ValidationError as error:
        raise ValueError(_validation_error_message(error)) from error


def validate_runtime_checkpoint_envelope(*, snapshot: object) -> RuntimeCheckpointEnvelope:
    if not isinstance(snapshot, Mapping):
        raise ValueError(
            "invalid runtime snapshot payload: field 'snapshot payload' must be a mapping"
        )
    try:
        return RuntimeCheckpointEnvelope.model_validate(snapshot)
    except ValidationError as error:
        raise ValueError(_validation_error_message(error)) from error


__all__ = [
    "LiveRuntimeSnapshotPayload",
    "RuntimeCheckpointEnvelope",
    "validate_live_runtime_snapshot_payload",
    "validate_runtime_checkpoint_envelope",
]

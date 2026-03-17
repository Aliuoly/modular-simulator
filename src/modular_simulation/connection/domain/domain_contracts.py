from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import ClassVar, Literal, cast

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    ValidationInfo,
    field_validator,
    model_validator,
)

from .node_port_helpers import DirectionalNodePorts, normalize_non_empty_token, normalize_port_ids
from ..topology.topology import (
    ConnectionEdge,
    JunctionNode,
    PortReference,
    ProcessNode,
)


def _validation_error_message(error: ValidationError) -> str:
    first_error = error.errors()[0]
    message = str(first_error.get("msg", "invalid payload"))
    prefix = "Value error, "
    return message[len(prefix) :] if message.startswith(prefix) else message


class Port(BaseModel):
    port_id: str
    direction: Literal["inlet", "outlet"]
    metadata: dict[str, object] = Field(default_factory=dict)

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    @field_validator("port_id")
    @classmethod
    def _validate_port_id(cls, value: str, info: ValidationInfo) -> str:
        del info
        return normalize_non_empty_token(value, field_name="port_id")


class UnitProcess(BaseModel):
    process_id: str
    ports: tuple[Port, ...] = Field(min_length=1)
    metadata: dict[str, object] = Field(default_factory=dict)

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    @field_validator("process_id")
    @classmethod
    def _validate_process_id(cls, value: str, info: ValidationInfo) -> str:
        del info
        return normalize_non_empty_token(value, field_name="process_id")

    @model_validator(mode="after")
    def _validate_unique_ports(self) -> "UnitProcess":
        _ = self.node_ports()
        return self

    def inlet_port_ids(self) -> tuple[str, ...]:
        return tuple(port.port_id for port in self.ports if port.direction == "inlet")

    def outlet_port_ids(self) -> tuple[str, ...]:
        return tuple(port.port_id for port in self.ports if port.direction == "outlet")

    def node_ports(self) -> DirectionalNodePorts:
        return DirectionalNodePorts.build(
            node_id=self.process_id,
            inlet_port_ids=self.inlet_port_ids(),
            outlet_port_ids=self.outlet_port_ids(),
            node_kind="process",
        )

    def as_process_node(self) -> ProcessNode:
        return ProcessNode(
            process_id=self.process_id,
            inlet_ports=self.inlet_port_ids(),
            outlet_ports=self.outlet_port_ids(),
        )


class JunctionProcess(BaseModel):
    junction_id: str
    inlet_port_ids: tuple[str, ...] = Field(min_length=1)
    outlet_port_id: str = "outlet"
    metadata: dict[str, object] = Field(default_factory=dict)

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    @field_validator("junction_id", "outlet_port_id")
    @classmethod
    def _validate_token_fields(cls, value: str, info: ValidationInfo) -> str:
        field_name = info.field_name if info.field_name is not None else "token"
        return normalize_non_empty_token(
            value,
            field_name=field_name,
        )

    @field_validator("inlet_port_ids")
    @classmethod
    def _validate_inlet_port_ids(
        cls, value: tuple[str, ...], info: ValidationInfo
    ) -> tuple[str, ...]:
        del info
        return normalize_port_ids(
            value,
            field_name="inlet_port_ids",
        )

    @model_validator(mode="after")
    def _validate_unique_port_ids(self) -> "JunctionProcess":
        _ = self.node_ports()
        return self

    def node_ports(self) -> DirectionalNodePorts:
        return DirectionalNodePorts.build(
            node_id=self.junction_id,
            inlet_port_ids=self.inlet_port_ids,
            outlet_port_ids=(self.outlet_port_id,),
            node_kind="junction",
        )

    def as_junction_node(self) -> JunctionNode:
        return self.node_ports().as_junction_node()


class ResistanceConfig(BaseModel):
    mode: Literal["derived", "manual_override"] = "derived"
    radius_m: float | None = Field(default=None, gt=0.0)
    length_m: float | None = Field(default=None, gt=0.0)
    manual_value: float | None = Field(default=None, ge=0.0)

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    @model_validator(mode="after")
    def _validate_mode_fields(self) -> "ResistanceConfig":
        if self.radius_m is None or self.length_m is None:
            raise ValueError("resistance configuration requires both 'radius_m' and 'length_m'")

        if self.mode == "derived":
            return self

        if self.manual_value is None:
            raise ValueError("resistance mode 'manual_override' requires field 'manual_value'")
        return self


class ValveConfig(BaseModel):
    valve_id: str
    minimum_open_fraction: float = Field(default=0.0, ge=0.0, le=1.0)
    maximum_open_fraction: float = Field(default=1.0, ge=0.0, le=1.0)
    initial_open_fraction: float = Field(default=1.0, ge=0.0, le=1.0)

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    @field_validator("valve_id")
    @classmethod
    def _validate_valve_id(cls, value: str, info: ValidationInfo) -> str:
        del info
        return normalize_non_empty_token(value, field_name="valve_id")

    @model_validator(mode="after")
    def _validate_ranges(self) -> "ValveConfig":
        if self.minimum_open_fraction > self.maximum_open_fraction:
            raise ValueError(
                "valve open range is invalid: 'minimum_open_fraction' must be <= 'maximum_open_fraction'"
            )
        if not (
            self.minimum_open_fraction <= self.initial_open_fraction <= self.maximum_open_fraction
        ):
            raise ValueError(
                "valve open range is invalid: 'initial_open_fraction' must be within min/max bounds"
            )
        return self


class SensorBinding(BaseModel):
    sensor_id: str
    signal_key: str
    line_id: str | None = None
    process_id: str | None = None
    port_id: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    @field_validator("sensor_id", "signal_key")
    @classmethod
    def _validate_sensor_fields(cls, value: str, info: ValidationInfo) -> str:
        field_name = info.field_name if info.field_name is not None else "token"
        return normalize_non_empty_token(
            value,
            field_name=field_name,
        )

    @model_validator(mode="after")
    def _validate_target(self) -> "SensorBinding":
        has_line_target = self.line_id is not None
        has_process_target = self.process_id is not None or self.port_id is not None
        if has_line_target == has_process_target:
            raise ValueError(
                "sensor binding must target exactly one location: either 'line_id' or ('process_id' and 'port_id')"
            )
        if has_process_target and (self.process_id is None or self.port_id is None):
            raise ValueError(
                "sensor binding process targets must include both 'process_id' and 'port_id'"
            )
        return self


class ControllerBinding(BaseModel):
    controller_id: str
    sensor_id: str
    actuator_line_id: str
    mode: Literal["auto", "manual"] = "auto"
    metadata: dict[str, object] = Field(default_factory=dict)

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    @field_validator("controller_id", "sensor_id", "actuator_line_id")
    @classmethod
    def _validate_controller_fields(cls, value: str, info: ValidationInfo) -> str:
        field_name = info.field_name if info.field_name is not None else "token"
        return normalize_non_empty_token(
            value,
            field_name=field_name,
        )


class ConnectionLine(BaseModel):
    line_id: str
    source_process_id: str
    source_port_id: str
    target_process_id: str
    target_port_id: str
    resistance: ResistanceConfig
    valve: ValveConfig | None = None
    metadata: dict[str, object] = Field(default_factory=dict)

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    @field_validator(
        "line_id",
        "source_process_id",
        "source_port_id",
        "target_process_id",
        "target_port_id",
    )
    @classmethod
    def _validate_connection_fields(cls, value: str, info: ValidationInfo) -> str:
        field_name = info.field_name if info.field_name is not None else "token"
        return normalize_non_empty_token(
            value,
            field_name=field_name,
        )

    @model_validator(mode="after")
    def _validate_endpoints(self) -> "ConnectionLine":
        if (
            self.source_process_id == self.target_process_id
            and self.source_port_id == self.target_port_id
        ):
            raise ValueError(
                "connection line source and target must not reference the same endpoint"
            )
        return self

    def source_reference(self) -> PortReference:
        return PortReference(node_id=self.source_process_id, port_name=self.source_port_id)

    def target_reference(self) -> PortReference:
        return PortReference(node_id=self.target_process_id, port_name=self.target_port_id)

    def as_connection_edge(self) -> ConnectionEdge:
        return ConnectionEdge(
            edge_id=self.line_id,
            source=self.source_reference(),
            target=self.target_reference(),
        )


class MutationCommand(BaseModel):
    operation: str
    command_id: str | None = None

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow", arbitrary_types_allowed=True)

    @field_validator("operation")
    @classmethod
    def _validate_operation(cls, value: str, info: ValidationInfo) -> str:
        del info
        return normalize_non_empty_token(value, field_name="operation")

    @field_validator("command_id")
    @classmethod
    def _validate_command_id(cls, value: str | None, info: ValidationInfo) -> str | None:
        del info
        if value is None:
            return None
        return normalize_non_empty_token(value, field_name="command_id")

    def as_mapping(self) -> dict[str, object]:
        return dict(self.model_dump(mode="python", by_alias=False))


class CommandEnvelope(BaseModel):
    idempotency_key: str | None = None
    expected_revision: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)
    mutations: tuple[MutationCommand, ...] = Field(min_length=1)

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    @field_validator("idempotency_key", "expected_revision")
    @classmethod
    def _validate_optional_tokens(cls, value: str | None, info: ValidationInfo) -> str | None:
        if value is None:
            return None
        field_name = info.field_name if info.field_name is not None else "token"
        return normalize_non_empty_token(
            value,
            field_name=field_name,
        )

    @model_validator(mode="after")
    def _validate_duplicate_command_ids(self) -> "CommandEnvelope":
        command_ids = [
            mutation.command_id for mutation in self.mutations if mutation.command_id is not None
        ]
        duplicates = sorted(
            command_id for command_id, count in Counter(command_ids).items() if count > 1
        )
        if duplicates:
            raise ValueError(f"duplicate mutation command ids are not allowed: {duplicates!r}")
        return self


class ReconfigurationRequestMetadata(BaseModel):
    destructive_edit_mode: Literal["hard_fail", "safe_detach"] = "hard_fail"
    control_dependencies: dict[str, tuple[str, ...]] = Field(default_factory=dict)

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow", arbitrary_types_allowed=True)

    @field_validator("control_dependencies", mode="before")
    @classmethod
    def _validate_control_dependencies(
        cls, value: object, info: ValidationInfo
    ) -> dict[str, tuple[str, ...]]:
        del info
        if value is None:
            return {}
        if not isinstance(value, Mapping):
            raise ValueError(
                "invalid transaction metadata: field 'control_dependencies' must be a mapping"
            )

        normalized_index: dict[str, tuple[str, ...]] = {}
        for raw_target, raw_dependents in cast(Mapping[object, object], value).items():
            if not isinstance(raw_target, str) or not raw_target.strip():
                raise ValueError(
                    "invalid transaction metadata: control dependency keys must be non-empty strings"
                )
            if isinstance(raw_dependents, str) or not isinstance(raw_dependents, Sequence):
                raise ValueError(
                    "invalid transaction metadata: control dependency entries must be sequences"
                )

            normalized_dependents: set[str] = set()
            for dependent in raw_dependents:
                normalized_dependents.add(cls._normalize_control_dependency(dependent))
            normalized_index[raw_target.strip()] = tuple(sorted(normalized_dependents))
        return normalized_index

    @classmethod
    def _normalize_control_dependency(cls, value: object) -> str:
        if isinstance(value, str) and value.strip():
            token = value.strip()
            return token if token.startswith("control:") else f"control:{token}"

        if isinstance(value, Mapping):
            mapping_value = cast(Mapping[object, object], value)
            dependency_id = mapping_value.get("dependency_id", mapping_value.get("id"))
            if not isinstance(dependency_id, str) or not dependency_id.strip():
                raise ValueError(
                    "invalid transaction metadata: control dependency mapping entries "
                    + "must include non-empty string key 'dependency_id' or 'id'"
                )
            dependency_kind = mapping_value.get("kind", "dependency")
            if not isinstance(dependency_kind, str) or not dependency_kind.strip():
                raise ValueError(
                    "invalid transaction metadata: control dependency mapping field 'kind' "
                    + "must be non-empty string when provided"
                )
            return f"control:{dependency_kind.strip()}:{dependency_id.strip()}"

        raise ValueError(
            "invalid transaction metadata: control dependency entries must be strings or mappings"
        )

    def as_mapping(self) -> dict[str, object]:
        payload = dict(self.model_dump(mode="python", by_alias=False))
        payload["control_dependencies"] = {
            target: tuple(dependents) for target, dependents in self.control_dependencies.items()
        }
        return payload


def validate_command_envelope(
    *,
    idempotency_key: str | None,
    expected_revision: str | None,
    metadata: Mapping[str, object],
    mutations: tuple[dict[str, object], ...],
) -> CommandEnvelope:
    return CommandEnvelope(
        idempotency_key=idempotency_key,
        expected_revision=expected_revision,
        metadata={str(key): value for key, value in metadata.items()},
        mutations=tuple(MutationCommand.model_validate(mutation) for mutation in mutations),
    )


def validate_reconfiguration_request_metadata(
    *, metadata: Mapping[str, object]
) -> ReconfigurationRequestMetadata:
    try:
        return ReconfigurationRequestMetadata.model_validate(
            {str(key): value for key, value in metadata.items()}
        )
    except ValidationError as error:
        raise ValueError(_validation_error_message(error)) from error


def validate_reconfiguration_command_envelope(
    *, request: Mapping[object, object]
) -> CommandEnvelope:
    request_mapping = {str(key): value for key, value in request.items()}

    idempotency_key_raw = request_mapping.get("idempotency_key")
    if idempotency_key_raw is None:
        idempotency_key = None
    elif isinstance(idempotency_key_raw, str) and idempotency_key_raw.strip():
        idempotency_key = idempotency_key_raw.strip()
    else:
        raise ValueError(
            "invalid reconfiguration request: optional field 'idempotency_key' must be a non-empty string"
        )

    expected_revision_raw = request_mapping.get("expected_revision")
    if expected_revision_raw is None:
        expected_revision = None
    elif isinstance(expected_revision_raw, str) and expected_revision_raw.strip():
        expected_revision = expected_revision_raw.strip()
    else:
        raise ValueError(
            "invalid reconfiguration request: optional field 'expected_revision' must be a non-empty string"
        )

    metadata_raw = request_mapping.get("metadata")
    if metadata_raw is None:
        metadata_mapping: dict[str, object] = {}
    elif isinstance(metadata_raw, Mapping):
        metadata_mapping = {
            str(key): value for key, value in cast(Mapping[object, object], metadata_raw).items()
        }
    else:
        raise ValueError(
            "invalid reconfiguration request: optional field 'metadata' must be a mapping"
        )
    metadata_model = validate_reconfiguration_request_metadata(metadata=metadata_mapping)

    mutations_field = request_mapping.get("mutations")
    if mutations_field is None:
        mutation_payload = {
            key: value
            for key, value in request_mapping.items()
            if key not in {"idempotency_key", "expected_revision", "metadata", "mutations"}
        }
        if (
            not isinstance(mutation_payload.get("operation"), str)
            or not str(mutation_payload.get("operation")).strip()
        ):
            raise ValueError(
                "invalid reconfiguration request: expected mapping with non-empty string field 'operation'"
            )
        raw_mutations = (mutation_payload,)
    else:
        if isinstance(mutations_field, str) or not isinstance(mutations_field, Sequence):
            raise ValueError(
                "invalid reconfiguration request: field 'mutations' must be a non-empty sequence of mapping objects"
            )
        normalized_mutations: list[dict[str, object]] = []
        for mutation in mutations_field:
            if not isinstance(mutation, Mapping):
                raise ValueError(
                    "invalid reconfiguration request: each mutation must be a mapping with non-empty string field 'operation'"
                )
            normalized_mutations.append(
                {str(key): value for key, value in cast(Mapping[object, object], mutation).items()}
            )
        if not normalized_mutations:
            raise ValueError(
                "invalid reconfiguration request: field 'mutations' must be a non-empty sequence of mapping objects"
            )
        raw_mutations = tuple(normalized_mutations)

    try:
        mutations = tuple(
            MutationCommand.model_validate(mutation).as_mapping() for mutation in raw_mutations
        )
    except ValidationError as error:
        message = _validation_error_message(error)
        if "operation" in message:
            raise ValueError(
                "invalid reconfiguration request: each mutation must be a mapping with non-empty string field 'operation'"
            ) from error
        raise ValueError(message) from error

    return validate_command_envelope(
        idempotency_key=idempotency_key,
        expected_revision=expected_revision,
        metadata=metadata_model.as_mapping(),
        mutations=mutations,
    )


__all__ = [
    "CommandEnvelope",
    "ConnectionLine",
    "ControllerBinding",
    "JunctionProcess",
    "MutationCommand",
    "Port",
    "ReconfigurationRequestMetadata",
    "ResistanceConfig",
    "SensorBinding",
    "UnitProcess",
    "ValveConfig",
    "validate_command_envelope",
    "validate_reconfiguration_command_envelope",
    "validate_reconfiguration_request_metadata",
]

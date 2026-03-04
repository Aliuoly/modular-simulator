from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

from modular_simulation.connection.topology import (
    ConnectionEdge,
    JunctionNode,
    PortReference,
    ProcessNode,
)


def _normalize_non_empty_token(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must be a non-empty string")
    if any(ch.isspace() for ch in normalized):
        raise ValueError(f"{field_name} must not contain whitespace")
    return normalized


class Port(BaseModel):
    port_id: str
    direction: Literal["inlet", "outlet"]
    metadata: dict[str, object] = Field(default_factory=dict)

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    @field_validator("port_id")
    @classmethod
    def _validate_port_id(cls, value: str, info: ValidationInfo) -> str:
        del info
        return _normalize_non_empty_token(value, field_name="port_id")


class UnitProcess(BaseModel):
    process_id: str
    process_kind: Literal["unit", "junction"] = "unit"
    ports: tuple[Port, ...] = Field(min_length=1)
    metadata: dict[str, object] = Field(default_factory=dict)

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    @field_validator("process_id")
    @classmethod
    def _validate_process_id(cls, value: str, info: ValidationInfo) -> str:
        del info
        return _normalize_non_empty_token(value, field_name="process_id")

    @model_validator(mode="after")
    def _validate_unique_ports(self) -> "UnitProcess":
        duplicate_port_ids = sorted(
            port_id
            for port_id, count in Counter(port.port_id for port in self.ports).items()
            if count > 1
        )
        if duplicate_port_ids:
            raise ValueError(
                f"duplicate process port ids are not allowed for '{self.process_id}': {duplicate_port_ids!r}"
            )

        inlet_port_ids = tuple(port.port_id for port in self.ports if port.direction == "inlet")
        outlet_port_ids = tuple(port.port_id for port in self.ports if port.direction == "outlet")
        if not inlet_port_ids:
            raise ValueError(f"process '{self.process_id}' requires at least one inlet port")
        if not outlet_port_ids:
            raise ValueError(f"process '{self.process_id}' requires at least one outlet port")
        return self

    def inlet_port_ids(self) -> tuple[str, ...]:
        return tuple(port.port_id for port in self.ports if port.direction == "inlet")

    def outlet_port_ids(self) -> tuple[str, ...]:
        return tuple(port.port_id for port in self.ports if port.direction == "outlet")

    def as_process_node(self) -> ProcessNode:
        return ProcessNode(
            process_id=self.process_id,
            inlet_ports=self.inlet_port_ids(),
            outlet_ports=self.outlet_port_ids(),
        )

    def as_junction_node(self) -> JunctionNode | None:
        if self.process_kind != "junction":
            return None
        return JunctionNode(
            junction_id=self.process_id,
            port_names=tuple(port.port_id for port in self.ports),
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
        return _normalize_non_empty_token(
            value,
            field_name=field_name,
        )

    @field_validator("inlet_port_ids")
    @classmethod
    def _validate_inlet_port_ids(
        cls, value: tuple[str, ...], info: ValidationInfo
    ) -> tuple[str, ...]:
        del info
        return tuple(
            _normalize_non_empty_token(item, field_name="inlet_port_ids") for item in value
        )

    @model_validator(mode="after")
    def _validate_unique_port_ids(self) -> "JunctionProcess":
        all_port_ids = (*self.inlet_port_ids, self.outlet_port_id)
        duplicates = sorted(
            port_id for port_id, count in Counter(all_port_ids).items() if count > 1
        )
        if duplicates:
            raise ValueError(
                f"duplicate process port ids are not allowed for '{self.junction_id}': {duplicates!r}"
            )
        return self

    def as_unit_process(self) -> UnitProcess:
        return UnitProcess(
            process_id=self.junction_id,
            process_kind="junction",
            ports=tuple(
                [Port(port_id=port_id, direction="inlet") for port_id in self.inlet_port_ids]
                + [Port(port_id=self.outlet_port_id, direction="outlet")]
            ),
            metadata=dict(self.metadata),
        )


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
        return _normalize_non_empty_token(value, field_name="valve_id")

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
        return _normalize_non_empty_token(
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
        return _normalize_non_empty_token(
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
        return _normalize_non_empty_token(
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
        return _normalize_non_empty_token(value, field_name="operation")

    @field_validator("command_id")
    @classmethod
    def _validate_command_id(cls, value: str | None, info: ValidationInfo) -> str | None:
        del info
        if value is None:
            return None
        return _normalize_non_empty_token(value, field_name="command_id")

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
        return _normalize_non_empty_token(
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


__all__ = [
    "CommandEnvelope",
    "ConnectionLine",
    "ControllerBinding",
    "JunctionProcess",
    "MutationCommand",
    "Port",
    "ResistanceConfig",
    "SensorBinding",
    "UnitProcess",
    "ValveConfig",
    "validate_command_envelope",
]

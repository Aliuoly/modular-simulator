from __future__ import annotations

# pyright: reportMissingImports=false

from collections.abc import Mapping
from typing import cast

from pydantic import ValidationError

from ..domain.state import PortCondition

PortConditionPayload = dict[str, object]
PortSnapshotNamespacePayload = dict[str, dict[str, PortConditionPayload]]
RuntimePortSnapshotPayload = dict[str, PortSnapshotNamespacePayload]


class RuntimePortSnapshotStore:
    def __init__(self) -> None:
        self._inlets: dict[str, dict[str, PortCondition]] = {}
        self._outlets: dict[str, dict[str, PortCondition]] = {}

    def record_inlet(self, node_id: str, port_name: str, condition: PortCondition) -> None:
        self._record(
            namespace_store=self._inlets,
            node_id=node_id,
            port_name=port_name,
            condition=condition,
        )

    def record_outlet(self, node_id: str, port_name: str, condition: PortCondition) -> None:
        self._record(
            namespace_store=self._outlets,
            node_id=node_id,
            port_name=port_name,
            condition=condition,
        )

    def get_inlet(self, node_id: str, port_name: str) -> PortCondition | None:
        return self._get(namespace_store=self._inlets, node_id=node_id, port_name=port_name)

    def get_outlet(self, node_id: str, port_name: str) -> PortCondition | None:
        return self._get(namespace_store=self._outlets, node_id=node_id, port_name=port_name)

    def clear(self) -> None:
        self._inlets.clear()
        self._outlets.clear()

    def snapshot_payload(self) -> RuntimePortSnapshotPayload:
        return {
            "inlets": _snapshot_namespace_payload(self._inlets),
            "outlets": _snapshot_namespace_payload(self._outlets),
        }

    def restore_from_payload(self, payload: Mapping[str, object]) -> None:
        payload_mapping = _require_mapping(payload, "payload")
        _require_exact_keys("payload", payload_mapping, ("inlets", "outlets"))

        restored_inlets = _restore_namespace_payload(payload_mapping["inlets"], "inlets")
        restored_outlets = _restore_namespace_payload(payload_mapping["outlets"], "outlets")

        self._inlets = restored_inlets
        self._outlets = restored_outlets

    def _record(
        self,
        *,
        namespace_store: dict[str, dict[str, PortCondition]],
        node_id: str,
        port_name: str,
        condition: PortCondition,
    ) -> None:
        if node_id not in namespace_store:
            namespace_store[node_id] = {}
        namespace_store[node_id][port_name] = _normalize_condition(condition)

    def _get(
        self,
        *,
        namespace_store: Mapping[str, Mapping[str, PortCondition]],
        node_id: str,
        port_name: str,
    ) -> PortCondition | None:
        node_conditions = namespace_store.get(node_id)
        if node_conditions is None:
            return None
        condition = node_conditions.get(port_name)
        if condition is None:
            return None
        return condition.model_copy(deep=True)


def _snapshot_namespace_payload(
    namespace_store: Mapping[str, Mapping[str, PortCondition]],
) -> PortSnapshotNamespacePayload:
    payload: PortSnapshotNamespacePayload = {}
    for node_id in sorted(namespace_store.keys()):
        payload[node_id] = {}
        for port_name in sorted(namespace_store[node_id].keys()):
            payload[node_id][port_name] = cast(
                PortConditionPayload,
                namespace_store[node_id][port_name].model_dump(mode="python"),
            )
    return payload


def _restore_namespace_payload(
    payload: object,
    field_name: str,
) -> dict[str, dict[str, PortCondition]]:
    namespace_mapping = _require_mapping(payload, field_name)
    restored: dict[str, dict[str, PortCondition]] = {}
    for node_id in sorted(namespace_mapping.keys()):
        port_mapping = _require_mapping(namespace_mapping[node_id], f"{field_name}.{node_id}")
        restored[node_id] = {}
        for port_name in sorted(port_mapping.keys()):
            restored[node_id][port_name] = _validate_port_condition_payload(
                port_mapping[port_name],
                field_name=f"{field_name}.{node_id}.{port_name}",
            )
    return restored


def _validate_port_condition_payload(payload: object, *, field_name: str) -> PortCondition:
    payload_mapping = _require_mapping(payload, field_name)
    try:
        return PortCondition.model_validate(payload_mapping)
    except ValidationError as error:
        first_error = error.errors()[0]
        location = ".".join(str(part) for part in first_error.get("loc", ()))
        error_path = field_name if not location else f"{field_name}.{location}"
        message = str(first_error.get("msg", "must be a valid PortCondition payload"))
        prefix = "Value error, "
        if message.startswith(prefix):
            message = message[len(prefix) :]
        raise ValueError(
            f"invalid runtime port snapshot payload: field '{error_path}' is invalid: {message}"
        ) from error


def _require_exact_keys(
    context: str,
    payload: Mapping[str, object],
    expected_keys: tuple[str, ...],
) -> None:
    actual_keys = tuple(payload.keys())
    if set(actual_keys) != set(expected_keys):
        raise ValueError(
            f"invalid runtime port snapshot payload: field '{context}' keys must be exactly {expected_keys!r}"
        )


def _require_mapping(value: object, field_name: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(
            f"invalid runtime port snapshot payload: field '{field_name}' must be a mapping"
        )
    typed_mapping = cast(Mapping[object, object], value)
    return {str(key): field_value for key, field_value in typed_mapping.items()}


def _normalize_condition(condition: PortCondition) -> PortCondition:
    return PortCondition.model_validate(condition.model_dump(mode="python"))


__all__ = ["RuntimePortSnapshotPayload", "RuntimePortSnapshotStore"]

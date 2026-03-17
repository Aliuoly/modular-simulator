from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from ..topology.topology import JunctionNode, ProcessNode


def normalize_non_empty_token(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must be a non-empty string")
    if any(ch.isspace() for ch in normalized):
        raise ValueError(f"{field_name} must not contain whitespace")
    return normalized


def normalize_port_ids(port_ids: tuple[str, ...], *, field_name: str) -> tuple[str, ...]:
    return tuple(normalize_non_empty_token(port_id, field_name=field_name) for port_id in port_ids)


def validate_directional_port_ids(
    *,
    node_id: str,
    inlet_port_ids: tuple[str, ...],
    outlet_port_ids: tuple[str, ...],
    node_kind: str,
) -> None:
    duplicates = sorted(
        port_id
        for port_id, count in Counter((*inlet_port_ids, *outlet_port_ids)).items()
        if count > 1
    )
    if duplicates:
        raise ValueError(
            f"duplicate {node_kind} port ids are not allowed for '{node_id}': {duplicates!r}"
        )
    if not inlet_port_ids:
        raise ValueError(f"{node_kind} '{node_id}' requires at least one inlet port")
    if not outlet_port_ids:
        raise ValueError(f"{node_kind} '{node_id}' requires at least one outlet port")


@dataclass(frozen=True)
class DirectionalNodePorts:
    node_id: str
    inlet_port_ids: tuple[str, ...]
    outlet_port_ids: tuple[str, ...]

    @classmethod
    def build(
        cls,
        *,
        node_id: str,
        inlet_port_ids: tuple[str, ...],
        outlet_port_ids: tuple[str, ...],
        node_kind: str,
    ) -> "DirectionalNodePorts":
        normalized_node_id = normalize_non_empty_token(node_id, field_name=f"{node_kind}_id")
        normalized_inlet_port_ids = normalize_port_ids(
            inlet_port_ids,
            field_name="inlet_port_ids",
        )
        normalized_outlet_port_ids = normalize_port_ids(
            outlet_port_ids,
            field_name="outlet_port_ids",
        )
        validate_directional_port_ids(
            node_id=normalized_node_id,
            inlet_port_ids=normalized_inlet_port_ids,
            outlet_port_ids=normalized_outlet_port_ids,
            node_kind=node_kind,
        )
        return cls(
            node_id=normalized_node_id,
            inlet_port_ids=normalized_inlet_port_ids,
            outlet_port_ids=normalized_outlet_port_ids,
        )

    def all_port_ids(self) -> tuple[str, ...]:
        return (*self.inlet_port_ids, *self.outlet_port_ids)

    def as_junction_node(self) -> JunctionNode:
        return JunctionNode(
            junction_id=self.node_id,
            port_names=self.all_port_ids(),
        )


__all__ = [
    "DirectionalNodePorts",
    "normalize_non_empty_token",
    "normalize_port_ids",
    "validate_directional_port_ids",
]

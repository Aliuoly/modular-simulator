from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias
from collections.abc import Mapping


@dataclass(frozen=True)
class HydraulicScalarStateRef:
    state: str


@dataclass(frozen=True)
class HydraulicIndexedStateRef:
    state: str
    index: int


HydraulicStateRef: TypeAlias = HydraulicScalarStateRef | HydraulicIndexedStateRef


@dataclass(frozen=True)
class HydraulicPortSpec:
    role: Literal["passive", "pressure_state", "fixed_pressure_anchor"]
    pressure_state: HydraulicStateRef | None = None
    fixed_value_state: HydraulicStateRef | None = None


@dataclass(frozen=True)
class HydraulicRelationSpec:
    name: str
    kind: Literal["pressure_drop", "pressure_rise", "pressure_equal"]
    ports: tuple[str, ...]
    parameter_state: HydraulicStateRef | None = None


@dataclass(frozen=True)
class HydraulicBalancingGroupSpec:
    name: str
    ports: tuple[str, ...]


@dataclass(frozen=True)
class HydraulicElementCouplingSpec:
    name: str
    port: str
    ports: tuple[str, str]


@dataclass(frozen=True)
class HydraulicParticipationSpec:
    ports: Mapping[str, HydraulicPortSpec]
    balancing_groups: tuple[HydraulicBalancingGroupSpec, ...] = ()
    relations: tuple[HydraulicRelationSpec, ...] = ()
    element_couplings: tuple[HydraulicElementCouplingSpec, ...] = ()


__all__ = [
    "HydraulicBalancingGroupSpec",
    "HydraulicElementCouplingSpec",
    "HydraulicIndexedStateRef",
    "HydraulicParticipationSpec",
    "HydraulicPortSpec",
    "HydraulicRelationSpec",
    "HydraulicScalarStateRef",
    "HydraulicStateRef",
]

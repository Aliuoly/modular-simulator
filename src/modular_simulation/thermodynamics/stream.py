from __future__ import annotations

# pyright: reportMissingTypeStubs=false

from dataclasses import dataclass
from typing import Protocol

from modular_simulation.connection.domain.state import MaterialState, PortCondition

from .algebraic_process_model import UnitProcessPorts


@dataclass(frozen=True)
class StreamData:
    temperature: float
    pressure: float
    mole_fractions: tuple[float, ...]
    molar_flow_rate: float
    species_ids: tuple[str, ...] | None = None
    phase: str | None = None
    enthalpy_molar: float | None = None
    entropy_molar: float | None = None

    @classmethod
    def from_port_condition(cls, condition: PortCondition) -> StreamData:
        species_ids = condition.state.species_ids
        if species_ids is None:
            species_ids = condition.species_ids
        return cls(
            temperature=condition.state.temperature,
            pressure=condition.state.pressure,
            mole_fractions=tuple(condition.state.mole_fractions),
            molar_flow_rate=condition.through_molar_flow_rate,
            species_ids=species_ids,
            phase=condition.state.phase,
            enthalpy_molar=condition.state.enthalpy_molar,
            entropy_molar=condition.state.entropy_molar,
        )

    def to_material_state(self) -> MaterialState:
        return MaterialState(
            pressure=self.pressure,
            temperature=self.temperature,
            mole_fractions=self.mole_fractions,
            species_ids=self.species_ids,
            phase=self.phase,
            enthalpy_molar=self.enthalpy_molar,
            entropy_molar=self.entropy_molar,
        )

    def to_port_condition(self) -> PortCondition:
        return PortCondition(
            state=self.to_material_state(),
            species_ids=self.species_ids,
            through_molar_flow_rate=self.molar_flow_rate,
        )


@dataclass(frozen=True)
class PortAttributeMap:
    flow: str
    temperature: str
    pressure: str
    composition: str


def _default_port_map(port_name: str) -> PortAttributeMap:
    return PortAttributeMap(
        flow=f"{port_name}_flow",
        temperature=f"{port_name}_temperature",
        pressure=f"{port_name}_pressure",
        composition=f"{port_name}_composition",
    )


def default_inlet_map(port_name: str) -> PortAttributeMap:
    return _default_port_map(port_name)


def default_outlet_map(port_name: str) -> PortAttributeMap:
    return _default_port_map(port_name)


class StreamPortIO(Protocol):
    @property
    def ports(self) -> UnitProcessPorts: ...

    def apply_inlet(
        self,
        port_name: str,
        stream: StreamData,
    ) -> None: ...

    def get_outlet_stream(
        self,
        port_name: str,
    ) -> StreamData: ...


__all__ = [
    "PortAttributeMap",
    "StreamData",
    "StreamPortIO",
    "default_inlet_map",
    "default_outlet_map",
]

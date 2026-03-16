from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, TypeGuard

from ..domain.state import PortCondition

if TYPE_CHECKING:
    from modular_simulation.thermodynamics.stream import StreamData


class ProcessStreamIO(Protocol):
    def apply_inlet(self, port_name: str, stream: StreamData) -> None: ...

    def get_outlet_stream(self, port_name: str) -> StreamData: ...


class ProcessOutletConditionResolver(Protocol):
    def resolve_outlet_condition(self, port_name: str) -> PortCondition: ...


def is_process_outlet_condition_resolver(
    candidate: object | None,
) -> TypeGuard[ProcessOutletConditionResolver]:
    return candidate is not None and callable(getattr(candidate, "resolve_outlet_condition", None))


def resolve_process_outlet_condition(
    candidate: object | None,
    port_name: str,
) -> PortCondition | None:
    if is_process_outlet_condition_resolver(candidate):
        return candidate.resolve_outlet_condition(port_name)
    return None


__all__ = [
    "ProcessOutletConditionResolver",
    "ProcessStreamIO",
    "is_process_outlet_condition_resolver",
    "resolve_process_outlet_condition",
]

from __future__ import annotations

from typing import Protocol, TypeGuard

from modular_simulation.connection.state import PortCondition
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


def _is_process_stream_io(candidate: object | None) -> TypeGuard[ProcessStreamIO]:
    return (
        candidate is not None
        and callable(getattr(candidate, "apply_inlet", None))
        and callable(getattr(candidate, "get_outlet_stream", None))
    )


def resolve_process_outlet_condition(
    candidate: object | None,
    port_name: str,
) -> PortCondition | None:
    if is_process_outlet_condition_resolver(candidate):
        return candidate.resolve_outlet_condition(port_name)
    if _is_process_stream_io(candidate):
        return candidate.get_outlet_stream(port_name).to_port_condition()
    return None


__all__ = [
    "ProcessOutletConditionResolver",
    "ProcessStreamIO",
    "is_process_outlet_condition_resolver",
    "resolve_process_outlet_condition",
]

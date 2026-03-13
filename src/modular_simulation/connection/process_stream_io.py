from __future__ import annotations

from typing import Protocol

from modular_simulation.thermodynamics.stream import StreamData


class ProcessStreamIO(Protocol):
    def apply_inlet(self, port_name: str, stream: StreamData) -> None: ...

    def get_outlet_stream(self, port_name: str) -> StreamData: ...


__all__ = ["ProcessStreamIO"]

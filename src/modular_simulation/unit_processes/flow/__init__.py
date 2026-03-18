from typing import Never

_REMOVED_FLOW_WRAPPER_GUIDANCE: dict[str, str] = {
    "Pump": (
        "`modular_simulation.unit_processes.flow.Pump` was removed from the canonical high-level API. "
        "Use `Flowsheet.connect(source, target, pump=PumpInstall(...))` for pressure boost, "
        "`Flowsheet.connect(..., valve=ValveInstall(...), heat=HeatInstall(...))` for line-installed controls, "
        "and `Flowsheet.add_junction(...)` / `Flowsheet.add_sink(...)` for topology."
    ),
    "Valve": (
        "`modular_simulation.unit_processes.flow.Valve` was removed from the canonical high-level API. "
        "Use `Flowsheet.connect(source, target, valve=ValveInstall(...))` for throttling, "
        "`Flowsheet.connect(..., pump=PumpInstall(...), heat=HeatInstall(...))` for line-installed controls, "
        "and `Flowsheet.add_junction(...)` / `Flowsheet.add_sink(...)` for topology."
    ),
}


def __getattr__(name: str) -> Never:
    if name == "__path__":
        raise AttributeError(name)
    message = _REMOVED_FLOW_WRAPPER_GUIDANCE.get(name)
    if message is not None:
        raise ImportError(message)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__: list[str] = []

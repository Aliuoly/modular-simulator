from typing import Never

_REMOVED_MIXING_WRAPPER_GUIDANCE = {
    "Mixer": (
        "`modular_simulation.unit_processes.mixing.Mixer` was removed from the canonical high-level API. "
        "Use `Flowsheet.add_junction(...)` for mixing and splitting topology, `Flowsheet.add_sink(...)` for product handoff, "
        "and `Flowsheet.connect(..., pump=PumpInstall(...), valve=ValveInstall(...), heat=HeatInstall(...))` for line-installed controls."
    )
}


def __getattr__(name: str) -> Never:
    if name == "__path__":
        raise AttributeError(name)
    message = _REMOVED_MIXING_WRAPPER_GUIDANCE.get(name)
    if message is not None:
        raise ImportError(message)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__: list[str] = []

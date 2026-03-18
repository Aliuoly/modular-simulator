from typing import Never

from .reactors import CSTR, PFR, ConversionReactor
from .separation import ComponentSeparator, FlashDrum, ShortcutDistillation
from .thermal import HeatExchanger, HeaterCooler

_REMOVED_WRAPPER_UNIT_GUIDANCE: dict[str, str] = {
    "Pump": (
        "`Pump` was removed from the canonical high-level unit-process API. "
        "Use `Flowsheet.connect(source, target, pump=PumpInstall(...))` for pressure boost, "
        "`Flowsheet.connect(..., valve=ValveInstall(...), heat=HeatInstall(...))` for line-installed controls, "
        "and `Flowsheet.add_junction(...)` / `Flowsheet.add_sink(...)` for mixing, splitting, and product handoff."
    ),
    "Valve": (
        "`Valve` was removed from the canonical high-level unit-process API. "
        "Use `Flowsheet.connect(source, target, valve=ValveInstall(...))` for throttling, "
        "`Flowsheet.connect(..., pump=PumpInstall(...), heat=HeatInstall(...))` for line-installed controls, "
        "and `Flowsheet.add_junction(...)` / `Flowsheet.add_sink(...)` for mixing, splitting, and product handoff."
    ),
    "Mixer": (
        "`Mixer` was removed from the canonical high-level unit-process API. "
        "Use `Flowsheet.add_junction(...)` for mixing and splitting topology, `Flowsheet.add_sink(...)` for product handoff, "
        "and `Flowsheet.connect(..., pump=PumpInstall(...), valve=ValveInstall(...), heat=HeatInstall(...))` for line-installed controls."
    ),
    "Splitter": (
        "`Splitter` was removed from the canonical high-level unit-process API. "
        "Use `Flowsheet.add_junction(...)` for hydraulic-owned branching, `Flowsheet.add_sink(...)` for product handoff, "
        "and `Flowsheet.connect(..., pump=PumpInstall(...), valve=ValveInstall(...), heat=HeatInstall(...))` for line-installed controls."
    ),
}


def __getattr__(name: str) -> Never:
    if name == "__path__":
        raise AttributeError(name)
    message = _REMOVED_WRAPPER_UNIT_GUIDANCE.get(name)
    if message is not None:
        raise ImportError(message)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "ComponentSeparator",
    "ConversionReactor",
    "CSTR",
    "FlashDrum",
    "HeatExchanger",
    "HeaterCooler",
    "PFR",
    "ShortcutDistillation",
]

from typing import Never

from .component_separator import ComponentSeparator
from .flash_drum import FLASH_DRUM_PORTS, FlashDrum
from .shortcut_distillation import SHORTCUT_DISTILLATION_PORTS, ShortcutDistillation

_REMOVED_SEPARATION_WRAPPER_GUIDANCE = {
    "Splitter": (
        "`modular_simulation.unit_processes.separation.Splitter` was removed from the canonical high-level API. "
        "Use `Flowsheet.add_junction(...)` for hydraulic-owned branching, `Flowsheet.add_sink(...)` for product handoff, "
        "and `Flowsheet.connect(..., pump=PumpInstall(...), valve=ValveInstall(...), heat=HeatInstall(...))` for line-installed controls."
    )
}


def __getattr__(name: str) -> Never:
    if name == "__path__":
        raise AttributeError(name)
    message = _REMOVED_SEPARATION_WRAPPER_GUIDANCE.get(name)
    if message is not None:
        raise ImportError(message)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "ComponentSeparator",
    "FLASH_DRUM_PORTS",
    "FlashDrum",
    "SHORTCUT_DISTILLATION_PORTS",
    "ShortcutDistillation",
]

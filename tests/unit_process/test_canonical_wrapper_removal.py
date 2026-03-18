from __future__ import annotations

from importlib import import_module
import re

import pytest


@pytest.mark.parametrize(
    "module_name",
    (
        "modular_simulation.unit_processes",
        "modular_simulation.unit_processes.flow",
        "modular_simulation.unit_processes.mixing",
        "modular_simulation.unit_processes.separation",
    ),
)
def test_canonical_public_surfaces_do_not_export_removed_wrapper_units(module_name: str) -> None:
    module = import_module(module_name)
    exports = set(getattr(module, "__all__", ()))

    assert {"Pump", "Valve", "Mixer", "Splitter"}.isdisjoint(exports)


@pytest.mark.parametrize(
    ("module_name", "symbol_name", "message_fragment"),
    (
        ("modular_simulation.unit_processes", "Pump", "pump=PumpInstall(...))"),
        ("modular_simulation.unit_processes", "Valve", "valve=ValveInstall(...))"),
        ("modular_simulation.unit_processes", "Mixer", "Flowsheet.add_junction(...)"),
        ("modular_simulation.unit_processes", "Splitter", "Flowsheet.add_junction(...)"),
        ("modular_simulation.unit_processes.flow", "Pump", "pump=PumpInstall(...))"),
        ("modular_simulation.unit_processes.flow", "Valve", "valve=ValveInstall(...))"),
        ("modular_simulation.unit_processes.mixing", "Mixer", "Flowsheet.add_junction(...)"),
        ("modular_simulation.unit_processes.separation", "Splitter", "Flowsheet.add_junction(...)"),
    ),
)
def test_removed_wrapper_unit_imports_raise_actionable_migration_guidance(
    module_name: str,
    symbol_name: str,
    message_fragment: str,
) -> None:
    module = import_module(module_name)

    with pytest.raises(ImportError, match=re.escape(message_fragment)):
        _ = getattr(module, symbol_name)

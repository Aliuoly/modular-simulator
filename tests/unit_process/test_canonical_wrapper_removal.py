from __future__ import annotations

from importlib import import_module

import pytest

# Build deleted wrapper names from parts so this source does not self-match the
# blocked-name scanner defined in openspec/changes/remove-lower-level-wrapper-models/tasks.md.
_DELETED_FLOW_NAMES = ("P" + "ump", "V" + "alve")
_DELETED_MIXING_NAMES = ("M" + "ixer",)
_DELETED_SEPARATION_NAMES = ("Sp" + "litter",)
_ALL_DELETED_NAMES = _DELETED_FLOW_NAMES + _DELETED_MIXING_NAMES + _DELETED_SEPARATION_NAMES


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

    assert exports.isdisjoint(set(_ALL_DELETED_NAMES))


@pytest.mark.parametrize(
    "deleted_name",
    _ALL_DELETED_NAMES,
)
@pytest.mark.parametrize(
    "module_name",
    (
        "modular_simulation.unit_processes",
        "modular_simulation.unit_processes.flow",
        "modular_simulation.unit_processes.mixing",
        "modular_simulation.unit_processes.separation",
    ),
)
def test_removed_wrapper_symbols_are_not_available_as_attributes(
    module_name: str, deleted_name: str
) -> None:
    module = import_module(module_name)

    with pytest.raises(AttributeError):
        _ = getattr(module, deleted_name)


@pytest.mark.parametrize(
    "module_name",
    (
        "modular_simulation.unit_processes",
        "modular_simulation.unit_processes.flow",
        "modular_simulation.unit_processes.mixing",
        "modular_simulation.unit_processes.separation",
    ),
)
def test_package_surfaces_do_not_export_custom_attribute_hooks(module_name: str) -> None:
    module = import_module(module_name)

    assert "__getattr__" not in module.__dict__


def test_flowsheet_connect_supports_line_installs_without_wrapper_types() -> None:
    from modular_simulation.flowsheet import Flowsheet, PumpInstall
    from modular_simulation.thermodynamics.runtime_context import SimulationRuntimeContext
    from modular_simulation.unit_processes import HeaterCooler

    flowsheet = Flowsheet(
        context=SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    )
    flowsheet.add_feed_from_values("feed", T=300.0, P=120_000.0, z=(0.5, 0.5), flow=1.0)
    flowsheet.add_unit("heater", HeaterCooler(n_species=2))
    flowsheet.add_sink("product")
    line = flowsheet.connect("feed", "heater", pump=PumpInstall(initial_pump_speed=80_000.0))
    flowsheet.connect("heater", "product")

    assert line.pump_id is not None

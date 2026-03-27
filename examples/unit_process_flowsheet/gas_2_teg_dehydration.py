"""Gas stage-2 educational proxy: TEG dehydration."""

from __future__ import annotations

from modular_simulation.flowsheet import Flowsheet, PumpInstall
from modular_simulation.thermodynamics.runtime_context import SimulationRuntimeContext
from modular_simulation.unit_processes import (
    ComponentSeparator,
    FlashDrum,
    HeatExchanger,
    StagewiseDistillationColumn,
)


def build_example_flowsheet(*, dt: float = 0.2) -> Flowsheet:
    flowsheet = Flowsheet(
        context=SimulationRuntimeContext.create(species_names=["methane", "n-heptane"]),
        dt=dt,
    )
    flowsheet.add_unit("inlet_separator", FlashDrum(imposed_temperature=305.0))
    flowsheet.add_unit("teg_contactor", ComponentSeparator())
    flowsheet.add_unit("rich_flash", FlashDrum(imposed_temperature=320.0))
    flowsheet.add_unit("lean_rich_exchanger", HeatExchanger(ua=7.5e3))
    flowsheet.add_unit("teg_regenerator", FlashDrum(imposed_temperature=345.0))
    flowsheet.add_feed_from_values("sweet_wet_gas", T=305.0, P=6.0e5, z=(0.85, 0.15), flow=4.0)
    flowsheet.add_feed_from_values("lean_teg", T=325.0, P=2.5e5, z=(0.05, 0.95), flow=1.5)
    flowsheet.add_sink("dry_gas")
    flowsheet.add_sink("rich_teg")
    flowsheet.connect("sweet_wet_gas", "inlet_separator")
    flowsheet.connect("inlet_separator.vapor_outlet", "teg_contactor")
    flowsheet.connect("teg_contactor.outlet_1", "dry_gas")
    flowsheet.connect("teg_contactor.outlet_2", "rich_flash")
    flowsheet.connect("rich_flash.vapor_outlet", "lean_rich_exchanger.hot_inlet")
    flowsheet.connect("lean_teg", "lean_rich_exchanger.cold_inlet")
    flowsheet.connect(
        "lean_rich_exchanger.cold_outlet",
        "teg_regenerator.inlet",
        line_id="glycol_loop",
        pump=PumpInstall(id="glycol_pump", initial_pump_speed=8.0e4),
    )
    flowsheet.connect("teg_regenerator.liquid_outlet", "rich_teg")
    return flowsheet

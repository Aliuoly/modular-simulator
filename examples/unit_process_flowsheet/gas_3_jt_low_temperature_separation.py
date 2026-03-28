"""Gas stage-3 educational proxy: JT low-temperature separation."""

from __future__ import annotations

from modular_simulation.flowsheet import Flowsheet, ValveInstall
from modular_simulation.thermodynamics.runtime_context import SimulationRuntimeContext
from modular_simulation.unit_processes import ComponentSeparator, FlashDrum, HeatExchanger


def build_example_flowsheet(*, dt: float = 0.2) -> Flowsheet:
    flowsheet = Flowsheet(
        context=SimulationRuntimeContext.create(species_names=["methane", "n-heptane"]),
        dt=dt,
    )
    flowsheet.add_unit("inlet_separator", FlashDrum(imposed_temperature=305.0))
    flowsheet.add_unit("teg_contactor", ComponentSeparator())
    flowsheet.add_unit("gas_gas_exchanger", HeatExchanger(ua=9.0e3))
    flowsheet.add_unit("low_temperature_separator", FlashDrum(imposed_temperature=250.0))
    flowsheet.add_feed_from_values("sweet_wet_gas", T=305.0, P=6.0e5, z=(0.85, 0.15), flow=4.0)
    flowsheet.add_feed_from_values("cold_recycle", T=250.0, P=2.5e5, z=(0.98, 0.02), flow=1.0)
    flowsheet.add_sink("ngl_liquids")
    flowsheet.add_sink("separator_liquid")
    flowsheet.add_sink("contactor_liquid")
    flowsheet.add_sink("cold_return")
    flowsheet.add_sink("lts_vapor")
    flowsheet.connect("sweet_wet_gas", "inlet_separator")
    flowsheet.connect("inlet_separator.vapor_outlet", "teg_contactor")
    flowsheet.connect("inlet_separator.liquid_outlet", "separator_liquid")
    flowsheet.connect("teg_contactor.outlet_1", "gas_gas_exchanger.hot_inlet")
    flowsheet.connect("teg_contactor.outlet_2", "contactor_liquid")
    flowsheet.connect("cold_recycle", "gas_gas_exchanger.cold_inlet")
    flowsheet.connect("gas_gas_exchanger.cold_outlet", "cold_return")
    flowsheet.connect(
        "gas_gas_exchanger.hot_outlet",
        "low_temperature_separator",
        line_id="jt_lts_feed",
        valve=ValveInstall(id="jt_valve", initial_open_fraction=1.0),
    )
    flowsheet.connect("low_temperature_separator.vapor_outlet", "lts_vapor")
    flowsheet.connect("low_temperature_separator.liquid_outlet", "ngl_liquids")
    return flowsheet

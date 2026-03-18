"""Canonical flowsheet example: dual-feed heat exchange with explicit branch connections."""

from __future__ import annotations

from modular_simulation.flowsheet import Flowsheet
from modular_simulation.thermodynamics.runtime_context import SimulationRuntimeContext
from modular_simulation.unit_processes import HeatExchanger, HeaterCooler


def _print_report(title: str, report: dict[str, float]) -> None:
    print(title)
    for key, value in report.items():
        print(f"- {key}: {value}")


def run_example(*, steps: int = 30, dt: float = 0.2, make_plot: bool = True) -> dict[str, float]:
    flowsheet = Flowsheet(
        context=SimulationRuntimeContext.create(species_names=["methane", "n-heptane"]),
        dt=dt,
    )

    flowsheet.add_unit(
        "hot_trim", HeaterCooler(mode="temperature", external_outlet_temperature=390.0)
    )
    flowsheet.add_unit(
        "cold_trim", HeaterCooler(mode="temperature", external_outlet_temperature=295.0)
    )
    flowsheet.add_unit("exchanger", HeatExchanger(ua=7.5e3))

    flowsheet.add_feed_from_values("hot_feed", T=382.0, P=1.9e5, z=(0.72, 0.28), flow=3.2)
    flowsheet.add_feed_from_values("cold_feed", T=300.0, P=1.8e5, z=(0.24, 0.76), flow=2.8)
    flowsheet.add_sink("hot_product")
    flowsheet.add_sink("cold_product")

    flowsheet.connect("hot_feed", "hot_trim")
    flowsheet.connect("hot_trim", "exchanger.hot_inlet")
    flowsheet.connect("cold_feed", "cold_trim")
    flowsheet.connect("cold_trim", "exchanger.cold_inlet")
    flowsheet.connect("exchanger.hot_outlet", "hot_product")
    flowsheet.connect("exchanger.cold_outlet", "cold_product")

    results = flowsheet.run(steps=steps, dt=dt)
    exchanger = results.get_unit("exchanger")

    report = {
        "final_time_s": float(results.time_points[-1]),
        "hot_outlet_temperature_K": float(exchanger.outlet_streams["hot_outlet"].temperature),
        "cold_outlet_temperature_K": float(exchanger.outlet_streams["cold_outlet"].temperature),
        "heat_duty_W": float(exchanger.state_history["heat_duty"][-1]),
    }
    _print_report("EASY (3 PROCESSES): DUAL FEED HEAT EXCHANGER", report)

    if make_plot:
        print("- plotting is not implemented for the current canonical flowsheet API")

    return report


if __name__ == "__main__":
    run_example()

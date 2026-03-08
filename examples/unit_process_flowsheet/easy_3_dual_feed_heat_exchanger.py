from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from modular_simulation.flowsheet import Flowsheet
from modular_simulation.unit_processes import HeatExchanger, HeaterCooler


def run_example(*, steps: int = 30, dt: float = 0.2, make_plot: bool = True) -> dict[str, float]:
    flowsheet = cast(Any, Flowsheet).create(dt=dt)

    flowsheet.add_unit(
        "hot_trim", HeaterCooler(mode="temperature", external_outlet_temperature=390.0)
    )
    flowsheet.add_unit(
        "cold_trim", HeaterCooler(mode="temperature", external_outlet_temperature=295.0)
    )
    flowsheet.add_unit("exchanger", HeatExchanger(ua=7.5e3))

    flowsheet.add_feed_from_values("hot_feed", T=382.0, P=1.9e5, z=(0.72, 0.28), flow=3.2)
    flowsheet.add_feed_from_values("cold_feed", T=300.0, P=1.8e5, z=(0.24, 0.76), flow=2.8)

    flowsheet.connect("hot_feed", "hot_trim")
    flowsheet.connect("hot_trim", "exchanger.hot_inlet")
    flowsheet.connect("cold_feed", "cold_trim")
    flowsheet.connect("cold_trim", "exchanger.cold_inlet")

    results = flowsheet.step(steps=steps, dt=dt)
    exchanger = results.get_unit("exchanger")

    report = {
        "final_time_s": float(results.time_points[-1]),
        "hot_outlet_temperature_K": float(exchanger.outlet_streams["hot_outlet"].temperature),
        "cold_outlet_temperature_K": float(exchanger.outlet_streams["cold_outlet"].temperature),
        "heat_duty_W": float(exchanger.state_history["heat_duty"][-1]),
    }
    results.print_report("EASY (3 PROCESSES): DUAL FEED HEAT EXCHANGER", report)

    if make_plot:
        plot_file = results.plot_stream_metric(
            {
                "hot branch": ("hot_trim", "exchanger.hot_inlet"),
                "cold branch": ("cold_trim", "exchanger.cold_inlet"),
            },
            metric="temperature",
            title="easy_3_dual_feed_heat_exchanger: stream temperatures",
            output_path=Path(__file__).with_suffix(".png"),
        )
        if plot_file is not None:
            print(f"- plot_file: {plot_file}")

    return report


if __name__ == "__main__":
    run_example()

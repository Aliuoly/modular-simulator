from __future__ import annotations

from pathlib import Path

from modular_simulation.flowsheet import Flowsheet
from modular_simulation.unit_processes import FlashDrum, HeaterCooler


def run_example(*, steps: int = 36, dt: float = 0.2, make_plot: bool = True) -> dict[str, float]:
    flowsheet = Flowsheet.create(dt=dt)

    flowsheet.add_unit(
        "heater", HeaterCooler(mode="temperature", external_outlet_temperature=355.0)
    )
    flowsheet.add_unit("flash", FlashDrum(imposed_temperature=333.0))
    flowsheet.add_feed_from_values("feed", T=332.0, P=1.7e5, z=(0.58, 0.42), flow=4.0)
    flowsheet.chain("feed", "heater", "flash")

    results = flowsheet.step(steps=steps, dt=dt)
    flash = results.get_unit("flash")
    feed_to_heater = results.get_stream("feed", "heater")
    heater_to_flash = results.get_stream("heater", "flash")
    vapor_fraction_history = flash.state_history.get("vapor_fraction")
    vapor_fraction = (
        float(vapor_fraction_history[-1]) if vapor_fraction_history is not None else 0.0
    )
    estimated_vapor_flow = float(feed_to_heater.flow_rate[-1]) * vapor_fraction

    report = {
        "final_time_s": float(results.time_points[-1]),
        "heater_outlet_temperature_K": float(
            results.get_unit("heater").outlet_streams["outlet"].temperature
        ),
        "feed_to_heater_flow_mol_s": float(feed_to_heater.flow_rate[-1]),
        "heater_to_flash_flow_mol_s": float(heater_to_flash.flow_rate[-1]),
        "flash_vapor_fraction": vapor_fraction,
        "estimated_flash_vapor_flow_mol_s": estimated_vapor_flow,
        "flash_liquid_flow_mol_s": float(flash.outlet_streams["liquid_outlet"].molar_flow_rate),
    }
    results.print_report("EASY (2 PROCESSES): HEATER -> FLASH", report)

    if make_plot:
        plot_file = results.plot_stream_metric(
            {
                "feed to heater": ("feed", "heater"),
                "heater to flash": ("heater", "flash"),
            },
            metric="temperature",
            title="easy_2_heater_flash: stream temperatures",
            output_path=Path(__file__).with_suffix(".png"),
        )
        if plot_file is not None:
            print(f"- plot_file: {plot_file}")

    return report


if __name__ == "__main__":
    run_example()

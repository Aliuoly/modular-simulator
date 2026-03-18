"""Canonical flowsheet example: single-feed heater followed by flash separation."""

from __future__ import annotations

from modular_simulation.flowsheet import Flowsheet
from modular_simulation.thermodynamics.runtime_context import SimulationRuntimeContext
from modular_simulation.unit_processes import FlashDrum, HeaterCooler


def _print_report(title: str, report: dict[str, float]) -> None:
    print(title)
    for key, value in report.items():
        print(f"- {key}: {value}")


def run_example(*, steps: int = 36, dt: float = 0.2, make_plot: bool = True) -> dict[str, float]:
    flowsheet = Flowsheet(
        context=SimulationRuntimeContext.create(species_names=["methane", "n-heptane"]),
        dt=dt,
    )

    flowsheet.add_unit(
        "heater", HeaterCooler(mode="temperature", external_outlet_temperature=355.0)
    )
    flowsheet.add_unit("flash", FlashDrum(imposed_temperature=333.0))
    flowsheet.add_sink("vapor_product")
    flowsheet.add_sink("liquid_product")
    flowsheet.add_feed_from_values("feed", T=332.0, P=1.7e5, z=(0.58, 0.42), flow=4.0)
    flowsheet.chain("feed", "heater", "flash")
    flowsheet.connect("flash.vapor_outlet", "vapor_product")
    flowsheet.connect("flash.liquid_outlet", "liquid_product")

    results = flowsheet.run(steps=steps, dt=dt)
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
    _print_report("EASY (2 PROCESSES): HEATER -> FLASH", report)

    if make_plot:
        print("- plotting is not implemented for the current canonical flowsheet API")

    return report


if __name__ == "__main__":
    run_example()

"""Reference flowsheet example: pressure-driven flash with vapor/liquid separation, junction remixing, and sink handoff."""

from __future__ import annotations

from modular_simulation.flowsheet import Flowsheet
from modular_simulation.thermodynamics.runtime_context import SimulationRuntimeContext
from modular_simulation.unit_processes import FlashDrum, HeaterCooler


def _print_report(title: str, report: dict[str, float]) -> None:
    print(title)
    for key, value in report.items():
        print(f"- {key}: {value}")


def run_example(*, steps: int = 55, dt: float = 0.15, make_plot: bool = True) -> dict[str, float]:
    flowsheet = Flowsheet(
        context=SimulationRuntimeContext.create(species_names=["ethane", "propane"]),
        dt=dt,
    )

    flowsheet.add_unit(
        "preheat", HeaterCooler(mode="temperature", external_outlet_temperature=360.0)
    )
    flowsheet.add_unit(
        "reactor", HeaterCooler(mode="temperature", external_outlet_temperature=370.0)
    )
    flowsheet.add_unit(
        "interstage_cool", HeaterCooler(mode="temperature", external_outlet_temperature=344.0)
    )
    flowsheet.add_unit("flash", FlashDrum(imposed_temperature=334.0))
    flowsheet.add_unit(
        "vapor_trim", HeaterCooler(mode="temperature", external_outlet_temperature=321.0)
    )
    flowsheet.add_unit(
        "liquid_trim", HeaterCooler(mode="temperature", external_outlet_temperature=318.0)
    )
    flowsheet.add_junction(
        "product_mix",
        inlet_ports=("vapor", "liquid"),
        outlet_ports=("to_polish",),
    )
    flowsheet.add_unit(
        "final_polish", HeaterCooler(mode="temperature", external_outlet_temperature=320.0)
    )
    flowsheet.add_sink("product")

    flowsheet.add_feed_from_values("feed", T=343.0, P=2.1e5, z=(0.62, 0.38), flow=4.3)

    flowsheet.chain("feed", "preheat", "reactor", "interstage_cool", "flash")
    flowsheet.connect("flash.vapor_outlet", "vapor_trim")
    flowsheet.connect("flash.liquid_outlet", "liquid_trim")
    flowsheet.connect("vapor_trim", "product_mix.vapor")
    flowsheet.connect("liquid_trim", "product_mix.liquid")
    flowsheet.connect("product_mix.to_polish", "final_polish")
    flowsheet.connect("final_polish", "product")

    results = flowsheet.run(steps=steps, dt=dt)
    flash = results.get_unit("flash")
    product = results.get_stream("product_mix.to_polish", "final_polish")
    feed_to_preheat = results.get_stream("feed", "preheat")
    vapor_fraction_history = flash.state_history.get("vapor_fraction")
    vapor_fraction = (
        float(vapor_fraction_history[-1]) if vapor_fraction_history is not None else 0.0
    )
    estimated_vapor_flow = float(feed_to_preheat.flow_rate[-1]) * vapor_fraction

    report = {
        "final_time_s": float(results.time_points[-1]),
        "feed_to_preheat_flow_mol_s": float(feed_to_preheat.flow_rate[-1]),
        "reactor_outlet_temperature_K": float(
            results.get_unit("reactor").outlet_streams["outlet"].temperature
        ),
        "flash_vapor_fraction": vapor_fraction,
        "estimated_flash_vapor_flow_mol_s": estimated_vapor_flow,
        "flash_liquid_flow_mol_s": float(flash.outlet_streams["liquid_outlet"].molar_flow_rate),
        "mixed_product_temperature_K": float(product.temperature[-1]),
        "final_product_temperature_K": float(
            results.get_unit("final_polish").outlet_streams["outlet"].temperature
        ),
        "mixed_product_flow_mol_s": float(product.flow_rate[-1]),
    }
    _print_report("COMPLEX (8 PROCESSES): FLASH RECOVERY + RECOMBINE TRAIN", report)

    if make_plot:
        print("- plotting is not implemented for the current canonical flowsheet API")

    return report


if __name__ == "__main__":
    run_example()

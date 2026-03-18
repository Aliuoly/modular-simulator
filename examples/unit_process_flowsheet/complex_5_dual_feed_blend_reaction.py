"""Reference flowsheet example: dual-feed blending through a junction and product sink."""

from __future__ import annotations

from modular_simulation.flowsheet import Flowsheet
from modular_simulation.thermodynamics.runtime_context import SimulationRuntimeContext
from modular_simulation.flowsheet import HeatInstall, PumpInstall
from modular_simulation.unit_processes import CSTR, HeaterCooler


def _print_report(title: str, report: dict[str, float]) -> None:
    print(title)
    for key, value in report.items():
        print(f"- {key}: {value}")


def run_example(*, steps: int = 48, dt: float = 0.15, make_plot: bool = True) -> dict[str, float]:
    flowsheet = Flowsheet(
        context=SimulationRuntimeContext.create(species_names=["methane", "n-heptane"]),
        dt=dt,
    )

    flowsheet.add_unit(
        "hot_preheat", HeaterCooler(mode="temperature", external_outlet_temperature=365.0)
    )
    flowsheet.add_unit(
        "cold_preheat", HeaterCooler(mode="temperature", external_outlet_temperature=335.0)
    )
    flowsheet.add_unit("reactor", CSTR())
    flowsheet.add_unit(
        "polisher", HeaterCooler(mode="temperature", external_outlet_temperature=325.0)
    )
    flowsheet.add_junction("blend", inlet_ports=("hot", "cold"), outlet_ports=("to_reactor",))
    flowsheet.add_sink("product")

    flowsheet.add_feed_from_values("feed_a", T=350.0, P=2.0e5, z=(0.8, 0.2), flow=3.0)
    flowsheet.add_feed_from_values("feed_b", T=320.0, P=1.9e5, z=(0.25, 0.75), flow=2.4)

    flowsheet.connect("feed_a", "hot_preheat")
    flowsheet.connect("feed_b", "cold_preheat")
    flowsheet.connect("hot_preheat", "blend.hot")
    flowsheet.connect(
        "cold_preheat",
        "blend.cold",
        heat=HeatInstall(initial_heat_rate=0.0),
    )
    flowsheet.connect(
        "blend.to_reactor",
        "reactor",
        pump=PumpInstall(initial_pump_speed=0.0),
    )
    flowsheet.connect("reactor", "polisher")
    flowsheet.connect("polisher", "product")

    results = flowsheet.run(steps=steps, dt=dt)
    product = results.get_unit("polisher").outlet_streams["outlet"]

    report = {
        "final_time_s": float(results.time_points[-1]),
        "blend_to_reactor_temperature_K": float(
            results.get_stream("blend.to_reactor", "reactor.inlet").temperature[-1]
        ),
        "product_temperature_K": float(product.temperature),
        "product_flow_mol_s": float(product.molar_flow_rate),
    }
    _print_report("COMPLEX (5 PROCESSES): DUAL FEED BLEND + REACTION TRAIN", report)

    if make_plot:
        print("- plotting is not implemented for the current canonical flowsheet API")

    return report


if __name__ == "__main__":
    run_example()

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from modular_simulation.flowsheet import Flowsheet
from modular_simulation.unit_processes import CSTR, HeaterCooler, Mixer


def run_example(*, steps: int = 48, dt: float = 0.15, make_plot: bool = True) -> dict[str, float]:
    flowsheet = cast(Any, Flowsheet).create(dt=dt)

    flowsheet.add_unit(
        "hot_preheat", HeaterCooler(mode="temperature", external_outlet_temperature=365.0)
    )
    flowsheet.add_unit(
        "cold_preheat", HeaterCooler(mode="temperature", external_outlet_temperature=335.0)
    )
    flowsheet.add_unit("blend", Mixer(n_inlets=2))
    flowsheet.add_unit("reactor", CSTR())
    flowsheet.add_unit(
        "polisher", HeaterCooler(mode="temperature", external_outlet_temperature=325.0)
    )

    flowsheet.add_feed_from_values("feed_a", T=350.0, P=2.0e5, z=(0.8, 0.2), flow=3.0)
    flowsheet.add_feed_from_values("feed_b", T=320.0, P=1.9e5, z=(0.25, 0.75), flow=2.4)

    flowsheet.connect("feed_a", "hot_preheat")
    flowsheet.connect("feed_b", "cold_preheat")
    flowsheet.connect("hot_preheat", "blend.inlet_1")
    flowsheet.connect("cold_preheat", "blend.inlet_2")
    flowsheet.chain("blend", "reactor", "polisher")

    results = flowsheet.step(steps=steps, dt=dt)
    product = results.get_unit("polisher").outlet_streams["outlet"]

    report = {
        "final_time_s": float(results.time_points[-1]),
        "blend_outlet_temperature_K": float(
            results.get_unit("blend").outlet_streams["outlet"].temperature
        ),
        "product_temperature_K": float(product.temperature),
        "product_flow_mol_s": float(product.molar_flow_rate),
    }
    results.print_report("COMPLEX (5 PROCESSES): DUAL FEED BLEND + REACTION TRAIN", report)

    if make_plot:
        plot_file = results.plot_stream_metric(
            {
                "feed_a branch": ("hot_preheat", "blend.inlet_1"),
                "feed_b branch": ("cold_preheat", "blend.inlet_2"),
                "reactor outlet": ("reactor", "polisher"),
            },
            metric="temperature",
            title="complex_5_dual_feed_blend_reaction: stream temperatures",
            output_path=Path(__file__).with_suffix(".png"),
        )
        if plot_file is not None:
            print(f"- plot_file: {plot_file}")

    return report


if __name__ == "__main__":
    run_example()

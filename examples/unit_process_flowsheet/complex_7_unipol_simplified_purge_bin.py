from __future__ import annotations

# pyright: reportMissingImports=false

import numpy as np

from modular_simulation.flowsheet import Flowsheet
from modular_simulation.thermodynamics.runtime_context import SimulationRuntimeContext
from modular_simulation.unit_processes import (
    ComponentSeparator,
    HeaterCooler,
    Mixer,
    Splitter,
)


def _create_flowsheet(*, species: tuple[str, ...], dt: float) -> Flowsheet:
    runtime_context = SimulationRuntimeContext.create(species_names=list(species))
    return Flowsheet(context=runtime_context, dt=dt)


def _print_report(title: str, report: dict[str, float]) -> None:
    print(title)
    for key, value in report.items():
        print(f"- {key}: {value}")


def run_example(*, steps: int = 120, dt: float = 0.2, make_plot: bool = True) -> dict[str, float]:
    species = ("ethylene", "propane")
    flowsheet = _create_flowsheet(species=species, dt=dt)
    n_species = len(species)

    flowsheet.add_unit("loop_mixer", Mixer(n_inlets=2, n_species=n_species))
    flowsheet.add_unit(
        "polymerizer",
        HeaterCooler(
            n_species=n_species,
            external_outlet_temperature=365.0,
        ),
    )
    flowsheet.add_unit(
        "resin_disengager",
        ComponentSeparator(
            n_species=n_species,
            configured_split_fraction_targets=np.array([0.05, 0.995], dtype=np.float64),
        ),
    )
    flowsheet.add_unit(
        "gas_purge_splitter",
        Splitter(n_outlets=2, n_species=n_species, split_ratios=np.array([0.82], dtype=np.float64)),
    )
    flowsheet.add_unit(
        "purge_bin",
        HeaterCooler(
            n_species=n_species,
            external_outlet_temperature=345.0,
        ),
    )
    flowsheet.add_unit(
        "resin_product_outlet",
        HeaterCooler(n_species=n_species, external_outlet_temperature=340.0),
    )
    flowsheet.add_unit(
        "recycle_export",
        HeaterCooler(n_species=n_species, external_outlet_temperature=350.0),
    )
    flowsheet.add_unit(
        "purge_export",
        HeaterCooler(n_species=n_species, external_outlet_temperature=350.0),
    )

    flowsheet.add_feed_from_values(
        "fresh_loop_feed",
        T=360.0,
        P=1.9e6,
        z=(0.995, 0.005),
        flow=65.0,
    )
    flowsheet.add_feed_from_values(
        "recycle_gas_return",
        T=355.0,
        P=1.75e6,
        z=(0.97, 0.03),
        flow=45.0,
    )

    flowsheet.connect("fresh_loop_feed", "loop_mixer.inlet_1")
    flowsheet.connect("recycle_gas_return", "loop_mixer.inlet_2")
    flowsheet.chain("loop_mixer", "polymerizer", "resin_disengager")
    flowsheet.connect("resin_disengager.outlet_1", "purge_bin")
    flowsheet.connect("purge_bin", "resin_product_outlet")
    flowsheet.connect("resin_disengager.outlet_2", "gas_purge_splitter")
    flowsheet.connect("gas_purge_splitter.outlet_1", "recycle_export")
    flowsheet.connect("gas_purge_splitter.outlet_2", "purge_export")

    results = flowsheet.run(steps=steps, dt=dt)

    polymerizer_to_separator = results.get_stream("polymerizer", "resin_disengager")
    recycle_to_mixer = results.get_stream("recycle_gas_return", "loop_mixer.inlet_2")
    solids_to_purge_bin = results.get_stream("resin_disengager.outlet_1", "purge_bin")
    purge_bin_to_product = results.get_stream("purge_bin", "resin_product_outlet")
    purge_to_outlet = results.get_stream("gas_purge_splitter.outlet_2", "purge_export")

    reactor_resin_fraction = float(polymerizer_to_separator.composition[-1][1])
    purge_bin_resin_fraction = float(purge_bin_to_product.composition[-1][1])
    resin_smoothing_gap = reactor_resin_fraction - purge_bin_resin_fraction

    report = {
        "final_time_s": float(results.time_points[-1]),
        "reactor_outlet_resin_fraction": reactor_resin_fraction,
        "purge_bin_outlet_resin_fraction": purge_bin_resin_fraction,
        "resin_fraction_gap_due_to_holdup": resin_smoothing_gap,
        "solids_to_purge_bin_flow_mol_s": float(solids_to_purge_bin.flow_rate[-1]),
        "purge_bin_product_flow_mol_s": float(purge_bin_to_product.flow_rate[-1]),
        "recycle_gas_flow_mol_s": float(recycle_to_mixer.flow_rate[-1]),
        "purge_gas_flow_mol_s": float(purge_to_outlet.flow_rate[-1]),
    }
    _print_report("COMPLEX (7 PROCESSES): SIMPLIFIED UNIPOL LOOP + PURGE BIN", report)

    if make_plot:
        print("- plotting is not implemented for the current canonical flowsheet API")

    return report


if __name__ == "__main__":
    _ = run_example()

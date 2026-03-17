"""Canonical advanced flowsheet example: ammonia train with an explicit recycle return edge."""

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


def _build_flowsheet(*, dt: float) -> Flowsheet:
    species = ("hydrogen", "ammonia")
    flowsheet = _create_flowsheet(species=species, dt=dt)
    n_species = len(species)

    flowsheet.add_unit("synthesis_mixer", Mixer(n_inlets=2, n_species=n_species))
    flowsheet.add_unit(
        "ammonia_reactor",
        HeaterCooler(
            n_species=n_species,
            external_outlet_temperature=705.0,
        ),
    )
    flowsheet.add_unit(
        "condenser_separator",
        ComponentSeparator(
            n_species=n_species,
            configured_split_fraction_targets=np.array([0.04, 0.95], dtype=np.float64),
        ),
    )
    flowsheet.add_unit(
        "purge_splitter",
        Splitter(n_outlets=2, n_species=n_species, split_ratios=np.array([0.86], dtype=np.float64)),
    )
    flowsheet.add_unit(
        "liquid_product_outlet",
        HeaterCooler(n_species=n_species, external_outlet_temperature=300.0),
    )
    flowsheet.add_unit(
        "purge_export",
        HeaterCooler(n_species=n_species, external_outlet_temperature=315.0),
    )
    flowsheet.add_feed_from_values(
        "fresh_syngas",
        T=700.0,
        P=1.55e6,
        z=(0.97, 0.03),
        flow=120.0,
    )

    flowsheet.connect("fresh_syngas", "synthesis_mixer.inlet_1")
    flowsheet.chain("synthesis_mixer", "ammonia_reactor", "condenser_separator")
    flowsheet.connect("condenser_separator.outlet_1", "liquid_product_outlet")
    flowsheet.connect("condenser_separator.outlet_2", "purge_splitter")
    flowsheet.connect("purge_splitter.outlet_1", "synthesis_mixer.inlet_2")
    flowsheet.connect("purge_splitter.outlet_2", "purge_export")

    return flowsheet


def _print_report(title: str, report: dict[str, float]) -> None:
    print(title)
    for key, value in report.items():
        print(f"- {key}: {value}")


def run_example(*, steps: int = 3000, dt: float = 0.2, make_plot: bool = True) -> dict[str, float]:
    flowsheet = _build_flowsheet(dt=dt)

    results = flowsheet.run(steps=steps, dt=dt)

    fresh_to_mixer = results.get_stream("fresh_syngas", "synthesis_mixer.inlet_1")
    recycle_to_mixer = results.get_stream("purge_splitter.outlet_1", "synthesis_mixer.inlet_2")
    reactor_to_separator = results.get_stream("ammonia_reactor", "condenser_separator")
    product_to_outlet = results.get_stream("condenser_separator.outlet_1", "liquid_product_outlet")
    purge_to_outlet = results.get_stream("purge_splitter.outlet_2", "purge_export")

    fresh_flow = float(fresh_to_mixer.flow_rate[-1])
    recycle_flow = float(recycle_to_mixer.flow_rate[-1])
    recycle_ratio = recycle_flow / max(1.0e-9, fresh_flow)

    report = {
        "final_time_s": float(results.time_points[-1]),
        "fresh_feed_flow_mol_s": fresh_flow,
        "recycle_edge_flow_mol_s": recycle_flow,
        "recycle_to_fresh_ratio": recycle_ratio,
        "reactor_outlet_product_fraction": float(reactor_to_separator.composition[-1][1]),
        "liquid_product_flow_mol_s": float(product_to_outlet.flow_rate[-1]),
        "liquid_product_purity": float(product_to_outlet.composition[-1][1]),
        "purge_flow_mol_s": float(purge_to_outlet.flow_rate[-1]),
    }
    _print_report("COMPLEX (6 PROCESSES): AMMONIA TRAIN WITH EXPLICIT RECYCLE TOPOLOGY", report)

    if make_plot:
        print("- plotting is not implemented for the current canonical flowsheet API")

    return report


if __name__ == "__main__":
    _ = run_example()

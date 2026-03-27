"""Gas stage-4 educational proxy: condensate stabilizer."""

from __future__ import annotations

from modular_simulation.flowsheet import Flowsheet
from modular_simulation.thermodynamics.runtime_context import SimulationRuntimeContext
from modular_simulation.unit_processes import FlashDrum, StagewiseDistillationColumn


def build_example_flowsheet(*, dt: float = 0.2) -> Flowsheet:
    flowsheet = Flowsheet(
        context=SimulationRuntimeContext.create(species_names=["methane", "n-heptane"]),
        dt=dt,
    )
    flowsheet.add_unit("inlet_separator", FlashDrum(imposed_temperature=305.0))
    flowsheet.add_unit(
        "condensate_stabilizer",
        StagewiseDistillationColumn(
            n_species=2,
            active_contact_height_m=4.0,
            shell_diameter_m=1.0,
            feed_stage_indices=(1,),
        ),
    )
    flowsheet.add_feed_from_values("sweet_wet_gas", T=305.0, P=6.0e5, z=(0.85, 0.15), flow=4.0)
    flowsheet.add_sink("stabilized_condensate")
    flowsheet.connect("sweet_wet_gas", "inlet_separator")
    flowsheet.connect("inlet_separator.liquid_outlet", "condensate_stabilizer.feed_1")
    flowsheet.connect("condensate_stabilizer.bottoms", "stabilized_condensate")
    return flowsheet

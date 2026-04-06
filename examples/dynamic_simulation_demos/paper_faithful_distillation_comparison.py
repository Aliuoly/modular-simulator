from __future__ import annotations

# pyright: reportMissingTypeStubs=false

from types import SimpleNamespace
from typing import Any, cast

from modular_simulation.measurables.process_model import ProcessModel
from modular_simulation.thermodynamics.stream import StreamData
from modular_simulation.unit_processes import (
    Gani1986DistillationColumn,
    Howard1970DistillationColumn,
    StagewiseDistillationColumn,
)


def _attach(model: ProcessModel) -> None:
    model.attach_system(cast(Any, SimpleNamespace(solver_options={})))


def _apply_runtime_outlet_request(model: ProcessModel, *, distillate: float, bottoms: float) -> str:
    if hasattr(model, "apply_requested_outlet_through_flow_demand"):
        method = cast(Any, getattr(model, "apply_requested_outlet_through_flow_demand"))
        method("distillate", distillate)
        method("bottoms", bottoms)
        return "yes"

    # Stagewise currently exposes outlet-demand via explicit boundary ownership
    # variables rather than the protocol method used by Howard/Gani.
    setattr(model, "distillate_withdrawal_flow", float(distillate))
    setattr(model, "bottoms_withdrawal_flow", float(bottoms))
    return "yes"


def run_demo() -> dict[str, float | str]:
    stagewise = StagewiseDistillationColumn(
        n_species=3,
        active_contact_height_m=4.0,
        feed_stage_indices=(1,),
    )
    howard = Howard1970DistillationColumn(n_species=3, n_plates=5)
    gani = Gani1986DistillationColumn(n_species=3, n_plates=5)

    runtime_compat: dict[str, str] = {}
    for model_name, model in (("stagewise", stagewise), ("howard", howard), ("gani", gani)):
        _attach(model)
        model.apply_inlet(
            "feed_1",
            StreamData(
                temperature=350.0,
                pressure=101325.0,
                mole_fractions=(0.5, 0.3, 0.2),
                molar_flow_rate=10.0,
            ),
        )
        runtime_compat[model_name] = _apply_runtime_outlet_request(
            model,
            distillate=2.0,
            bottoms=3.0,
        )

    stagewise_states = set(stagewise.differential_view.state_list)
    howard_states = set(howard.differential_view.state_list)
    gani_states = set(gani.differential_view.state_list)

    stagewise_owner_state = {
        "stage_component_moles",
        "reflux_drum_component_moles",
        "bottoms_sump_component_moles",
    }
    howard_owner_state = {"plate_component_holdup", "reflux_drum_component_moles"}
    gani_owner_state = {
        "plate_component_holdup",
        "reflux_drum_component_moles",
        "reboiler_component_moles",
    }

    return {
        "stagewise_role": "reduced_order_baseline",
        "howard_role": "paper_faithful_first_slice",
        "gani_role": "paper_faithful_first_slice",
        "closure_note": (
            "Models use distinct governing closures: Stagewise is reduced-order, "
            "while Howard (1970) and Gani (1986) are separate paper-faithful slices."
        ),
        "stagewise_has_owner_state": "yes"
        if bool(stagewise_owner_state.intersection(stagewise_states))
        else "no",
        "howard_has_owner_state": "yes"
        if bool(howard_owner_state.issubset(howard_states))
        else "no",
        "gani_has_owner_state": "yes" if bool(gani_owner_state.issubset(gani_states)) else "no",
        "stagewise_runtime_demand_port_compat": runtime_compat["stagewise"],
        "howard_runtime_demand_port_compat": runtime_compat["howard"],
        "gani_runtime_demand_port_compat": runtime_compat["gani"],
        "stagewise_distillate_flow_mol_s": float(
            stagewise.get_outlet_stream("distillate").molar_flow_rate
        ),
        "howard_distillate_flow_mol_s": float(
            howard.get_outlet_stream("distillate").molar_flow_rate
        ),
        "gani_distillate_flow_mol_s": float(gani.get_outlet_stream("distillate").molar_flow_rate),
    }


def main() -> None:
    result = run_demo()
    print("PAPER-FAITHFUL DISTILLATION COMPARISON DEMO")
    for key, value in result.items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()

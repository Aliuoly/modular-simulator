from __future__ import annotations

# pyright: reportMissingTypeStubs=false

import numpy as np

from modular_simulation.framework.system import System
from modular_simulation.measurables.process_model import ProcessModelParams
from modular_simulation.thermodynamics.kinetics import ReactionSet
from modular_simulation.unit_processes import PFR
from modular_simulation.utils.typing import ArrayIndex


def _build_system(model: PFR, dt_s: float) -> System:
    return System(
        dt=dt_s,
        process_model=model,
        sensors=[],
        calculations=[],
        control_elements=[],
        show_progress=False,
    )


def _override_constant(model: PFR, name: str, value: float) -> None:
    value = float(value)
    setattr(model, name, value)
    params: ProcessModelParams | None = getattr(model, "_params", None)
    if params is None:
        return
    index: ArrayIndex | None = params.k_map.get(name)
    if index is None:
        return
    params.k[index] = value


def run_demo(*, dt_s: float = 0.2, horizon_s: float = 90.0) -> dict[str, float]:
    n_cells = 24
    pfr = PFR(
        n_species=2,
        n_cells=n_cells,
        species_names=("A", "B"),
        reaction_set=ReactionSet(reactions=()),
        cell_species_moles=np.tile(np.array([0.45, 0.05], dtype=np.float64), n_cells),
        cell_temperatures=np.full(n_cells, 330.0, dtype=np.float64),
        inlet_flow=1.4,
        inlet_temperature=330.0,
        inlet_pressure=101325.0,
        inlet_composition=np.array([0.9, 0.1], dtype=np.float64),
        total_volume=12.0,
        pressure=101325.0,
        heat_transfer_coeff=160.0,
        jacket_area=6.0,
        imposed_jacket_temperature=330.0,
    )
    system = _build_system(pfr, dt_s)

    n_steps = max(1, int(round(horizon_s / dt_s)))
    step_at = n_steps // 2
    outlet_temperatures: list[float] = []

    for idx in range(n_steps):
        if idx == step_at:
            _override_constant(pfr, "imposed_jacket_temperature", 300.0)
        system.step(duration=dt_s)
        outlet_temperatures.append(float(pfr.outlet_temperature))

    pre_step = outlet_temperatures[max(step_at - 10, 0) : step_at]
    post_step = outlet_temperatures[-10:]
    pre_step_temperature = float(np.mean(pre_step)) if pre_step else float(outlet_temperatures[0])
    post_step_temperature = (
        float(np.mean(post_step)) if post_step else float(outlet_temperatures[-1])
    )

    return {
        "initial_outlet_temperature_k": float(outlet_temperatures[0]),
        "pre_step_outlet_temperature_k": pre_step_temperature,
        "final_outlet_temperature_k": post_step_temperature,
        "temperature_drop_k": pre_step_temperature - post_step_temperature,
        "step_time_s": float(step_at * dt_s),
    }


def main() -> None:
    result = run_demo()
    print("PFR THERMAL STEP DEMO")
    for key, value in result.items():
        print(f"{key}={value:.6f}")


if __name__ == "__main__":
    main()

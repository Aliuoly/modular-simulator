from __future__ import annotations

# pyright: reportMissingTypeStubs=false

import numpy as np
from typing import cast

from modular_simulation.framework.system import System
from modular_simulation.measurables.process_model import ProcessModelParams
from modular_simulation.thermodynamics.kinetics import ReactionSet
from modular_simulation.unit_processes import CSTR
from modular_simulation.utils.typing import ArrayIndex


def _build_system(model: CSTR, dt_s: float) -> System:
    return System(
        dt=dt_s,
        process_model=model,
        sensors=[],
        calculations=[],
        control_elements=[],
        show_progress=False,
    )


def _set_jacket_temperature(model: CSTR, temperature: float) -> None:
    setattr(model, "jacket_temperature", float(temperature))
    params = getattr(model, "_params", None)
    if params is None:
        return
    params = cast(ProcessModelParams, params)
    k_index: ArrayIndex = params.k_map["jacket_temperature"]
    if isinstance(k_index, slice):
        params.k[k_index] = float(temperature)
    else:
        params.k[k_index] = float(temperature)


def run_demo(*, dt_s: float = 0.25, horizon_s: float = 120.0) -> dict[str, float]:
    reactor = CSTR(
        n_species=2,
        species_names=("A", "B"),
        reaction_set=ReactionSet(reactions=()),
        species_moles=np.array([6.0, 0.0], dtype=np.float64),
        temperature=333.0,
        volume=6.0,
        inlet_flow=0.2,
        outlet_flow=0.2,
        inlet_temperature=333.0,
        inlet_pressure=101325.0,
        inlet_composition=np.array([1.0, 0.0], dtype=np.float64),
        heat_transfer_coeff=420.0,
        jacket_area=3.5,
        jacket_temperature=333.0,
    )
    system = _build_system(reactor, dt_s)

    n_steps = max(1, int(round(horizon_s / dt_s)))
    step_at = n_steps // 3
    temperatures: list[float] = []

    for idx in range(n_steps):
        if idx == step_at:
            _set_jacket_temperature(reactor, 288.0)
        system.step(duration=dt_s)
        temperatures.append(float(reactor.temperature))

    baseline_window = temperatures[max(step_at - 8, 0) : step_at]
    final_window = temperatures[-8:]
    baseline_temperature = (
        float(np.mean(baseline_window)) if baseline_window else float(temperatures[0])
    )
    final_temperature = float(np.mean(final_window)) if final_window else float(temperatures[-1])
    post_step_temperatures = temperatures[step_at:]
    min_post_step_temperature = (
        float(min(post_step_temperatures)) if post_step_temperatures else float(temperatures[-1])
    )

    return {
        "initial_temperature_k": float(temperatures[0]),
        "baseline_temperature_k": baseline_temperature,
        "final_temperature_k": final_temperature,
        "temperature_drop_k": max(0.0, baseline_temperature - min_post_step_temperature),
        "step_time_s": float(step_at * dt_s),
    }


def main() -> None:
    result = run_demo()
    print("CSTR THERMAL STEP DEMO")
    for key, value in result.items():
        print(f"{key}={value:.6f}")


if __name__ == "__main__":
    main()

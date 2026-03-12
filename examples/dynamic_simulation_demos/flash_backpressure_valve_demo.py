from __future__ import annotations

# pyright: reportMissingTypeStubs=false

from dataclasses import dataclass
from typing import cast

import numpy as np

from modular_simulation.framework.system import System
from modular_simulation.thermodynamics.property_package import PengRobinsonPackage
from modular_simulation.unit_processes import FlashDrum


@dataclass
class _StubSystem:
    solver_options: dict[str, object]


def _attach(model: FlashDrum) -> None:
    model.attach_system(cast(System, cast(object, _StubSystem(solver_options={}))))


def _pressure_from_open_fraction(open_fraction: float) -> float:
    bounded = min(max(open_fraction, 0.05), 1.0)
    return 95_000.0 + (1.0 - bounded) * 70_000.0


def run_demo(*, dt_s: float = 0.2, horizon_s: float = 60.0) -> dict[str, float]:
    package = PengRobinsonPackage(species_ids=("7732-18-5", "64-17-5"))
    drum = FlashDrum(
        thermal_mode="adiabatic",
        n_species=2,
        inlet_flow=6.0,
        inlet_temperature=355.0,
        inlet_pressure=170_000.0,
        inlet_composition=np.array([0.55, 0.45], dtype=np.float64),
        imposed_pressure=110_000.0,
        imposed_temperature=330.0,
    )
    drum.set_property_package(package)
    _attach(drum)

    n_steps = max(1, int(round(horizon_s / dt_s)))
    step_at = n_steps // 2
    vapor_fraction_before = 0.0

    valve_open_fraction = 0.75
    for idx in range(n_steps):
        if idx == step_at:
            valve_open_fraction = 0.28
        drum.imposed_pressure = _pressure_from_open_fraction(valve_open_fraction)
        drum.step(dt_s)
        if idx == step_at - 1:
            vapor_fraction_before = float(drum.vapor_fraction)

    return {
        "valve_open_fraction_final": float(valve_open_fraction),
        "imposed_pressure_final_pa": float(drum.imposed_pressure),
        "vapor_fraction_before_step": float(vapor_fraction_before),
        "vapor_fraction_after_step": float(drum.vapor_fraction),
        "vapor_fraction_delta": float(drum.vapor_fraction - vapor_fraction_before),
    }


def main() -> None:
    result = run_demo()
    print("FLASH BACKPRESSURE VALVE DEMO")
    for key, value in result.items():
        print(f"{key}={value:.6f}")


if __name__ == "__main__":
    main()

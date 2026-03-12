from __future__ import annotations

# pyright: reportMissingTypeStubs=false

from dataclasses import dataclass
from typing import cast

import numpy as np

from modular_simulation.framework.system import System
from modular_simulation.thermodynamics.kinetics import ReactionSet
from modular_simulation.thermodynamics.property_package import PengRobinsonPackage
from modular_simulation.unit_processes import CSTR, FlashDrum


@dataclass
class _StubSystem:
    solver_options: dict[str, object]


def _build_cstr_system(dt_s: float) -> tuple[CSTR, System]:
    reactor = CSTR(
        n_species=2,
        species_names=("A", "B"),
        reaction_set=ReactionSet(reactions=()),
        species_moles=np.array([7.0, 1.0], dtype=np.float64),
        temperature=342.0,
        volume=8.0,
        inlet_flow=1.1,
        outlet_flow=1.1,
        inlet_temperature=342.0,
        inlet_pressure=180_000.0,
        inlet_composition=np.array([0.62, 0.38], dtype=np.float64),
        heat_transfer_coeff=250.0,
        jacket_area=2.8,
        jacket_temperature=342.0,
    )
    system = System(
        dt=dt_s,
        process_model=reactor,
        sensors=[],
        calculations=[],
        control_elements=[],
        show_progress=False,
    )
    return reactor, system


def _build_flash() -> FlashDrum:
    flash = FlashDrum(
        thermal_mode="adiabatic",
        n_species=2,
        inlet_flow=6.0,
        inlet_temperature=342.0,
        inlet_pressure=170_000.0,
        inlet_composition=np.array([0.62, 0.38], dtype=np.float64),
        imposed_pressure=110_000.0,
        imposed_temperature=334.0,
    )
    flash.set_property_package(PengRobinsonPackage(species_ids=("7732-18-5", "64-17-5")))
    flash.attach_system(cast(System, cast(object, _StubSystem(solver_options={}))))
    return flash


def run_demo(*, dt_s: float = 0.2, horizon_s: float = 80.0) -> dict[str, float]:
    reactor, reactor_system = _build_cstr_system(dt_s)
    flash = _build_flash()

    n_steps = max(1, int(round(horizon_s / dt_s)))
    step_at = n_steps // 2
    pressure_before = float(flash.imposed_pressure)
    vapor_fraction_before = 0.0

    for idx in range(n_steps):
        if idx == step_at:
            flash.imposed_pressure = 145_000.0
            reactor.jacket_temperature = 306.0

        reactor_system.step(duration=dt_s)

        flash.inlet_temperature = float(reactor.temperature)
        flash.inlet_pressure = float(reactor.pressure)
        flash.inlet_composition = np.asarray(reactor.outlet_composition, dtype=np.float64)
        flash.step(dt_s)

        if idx == step_at - 1:
            vapor_fraction_before = float(flash.vapor_fraction)

    return {
        "pressure_before_step_pa": pressure_before,
        "pressure_after_step_pa": float(flash.imposed_pressure),
        "reactor_temperature_final_k": float(reactor.temperature),
        "flash_vapor_fraction_before_step": vapor_fraction_before,
        "flash_vapor_fraction_after_step": float(flash.vapor_fraction),
    }


def main() -> None:
    result = run_demo()
    print("COUPLED CSTR + FLASH PHYSICAL ACTUATOR DEMO")
    for key, value in result.items():
        print(f"{key}={value:.6f}")


if __name__ == "__main__":
    main()

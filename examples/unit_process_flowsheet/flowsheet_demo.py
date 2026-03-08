from __future__ import annotations

# pyright: reportMissingTypeStubs=false, reportUnknownArgumentType=false, reportUnknownMemberType=false
from typing import cast
import modular_simulation.components as c
from modular_simulation.flowsheet import Flowsheet
from modular_simulation.thermodynamics.runtime_context import SimulationRuntimeContext
from modular_simulation.unit_processes import FlashDrum, HeaterCooler


def run_flowsheet_demo(
    *, steps: int = 30, dt: float = 0.2, print_results: bool = True
) -> dict[str, object]:
    if steps <= 0:
        raise ValueError("steps must be positive")
    feed_temperature, feed_flow = 335.0, 4.0
    fs = Flowsheet(
        context=SimulationRuntimeContext.create(species_names=["methane", "n-heptane"]), dt=dt
    )
    heater = HeaterCooler(mode="duty", external_heat_duty=0.0)
    flash = FlashDrum(imposed_temperature=330.0)
    vapor_trim, liquid_trim = HeaterCooler(), HeaterCooler()
    fs.add_unit("heater", heater)
    fs.add_unit("flash", flash)
    fs.add_unit("vapor_trim", vapor_trim)
    fs.add_unit("liquid_trim", liquid_trim)
    fs.add_feed_from_values("feed", T=feed_temperature, P=180000.0, z=(0.55, 0.45), flow=feed_flow)
    fs.chain("feed", "heater", "flash")
    fs.connect("flash.vapor_outlet", "vapor_trim")
    fs.connect("flash.liquid_outlet", "liquid_trim")
    sys = fs.get_system("heater")
    traj = c.Trajectory(y0=0.0)
    sensor = c.SampledDelayedSensor(measurement_tag="outlet_temperature", alias_tag="T", unit="K")
    pid = c.PIDController(cv_tag="T", cv_range=(250.0, 400.0), reference_trajectory=traj, Kp=1.0)
    _ = sys.add_component(sensor)
    _ = sys.add_component(
        c.ControlElement(
            mv_tag="external_heat_duty",
            mv_range=(-1.0, 1.0),
            mv_trajectory=traj,
            controller=pid,
        )
    )
    _ = fs.compile()
    r = fs.run(steps=steps, dt=dt)
    flash_result = r.get_unit("flash")
    vapor_comp = tuple(float(v) for v in flash_result.outlet_streams["vapor_outlet"].mole_fractions)
    liquid_comp = tuple(
        float(v) for v in flash_result.outlet_streams["liquid_outlet"].mole_fractions
    )
    vapor_fraction = float(flash.vapor_fraction)
    vapor_flow = feed_flow * vapor_fraction
    updated_port_keys = tuple(r.step_results[-1].runtime_step_result.bookkeeping.updated_port_keys)
    final_time = float(cast(float, r.time_points[-1]))
    summary: dict[str, object] = {
        "time_s": final_time,
        "feed_temperature": feed_temperature,
        "heater_outlet_temperature": float(
            r.get_unit("heater").outlet_streams["outlet"].temperature
        ),
        "vapor_flow_mol_s": vapor_flow,
        "flash_total_flow": feed_flow,
        "flash_vapor_fraction": vapor_fraction,
        "flash_vapor_composition": vapor_comp,
        "flash_liquid_composition": liquid_comp,
        "last_updated_port_keys": updated_port_keys,
    }
    if print_results:
        print("UNIT PROCESS FLOWSHEET DEMO")
        print("feed -> heater -> flash -> {vapor_trim, liquid_trim}")
        for key, value in (
            ("time_s", final_time),
            ("flash_vapor_fraction", vapor_fraction),
            ("vapor_flow_mol_s", vapor_flow),
            ("flash_total_flow", feed_flow),
        ):
            print(f"{key}: {value:.6g}")
    return summary


if __name__ == "__main__":
    _ = run_flowsheet_demo(print_results=True)

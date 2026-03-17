"""Run the Van de Vusse CSTR example with the new System/ProcessModel API."""

from __future__ import annotations

import logging
from typing import cast

import matplotlib as mpl
import matplotlib.pyplot as plt

from modular_simulation.framework import System
from modular_simulation.plotting import plot_triplet_series
from modular_simulation.utils.wrappers import hour

from examples.van_de_vusse_cstr.component_definition import calculations, control_elements, sensors
from examples.van_de_vusse_cstr.process_definition import VanDeVusseProcessModel


DEFAULT_DURATION_HOURS = 120.0


def make_systems(record_history: bool = False) -> dict[str, System]:
    return {
        "normal": System(
            dt=hour(0.01),
            process_model=VanDeVusseProcessModel(),
            sensors=sensors,
            calculations=calculations,
            control_elements=control_elements,
            record_history=record_history,
            show_progress=False,
        ),
    }


def _run_systems(*, duration_hours: float, record_history: bool = False) -> dict[str, System]:
    systems = make_systems(record_history=record_history)
    for system in systems.values():
        system.step(hour(duration_hours))
    return systems


def _summarize_systems(systems: dict[str, System], *, duration_hours: float) -> dict[str, object]:
    normal_process = cast(VanDeVusseProcessModel, systems["normal"].process_model)
    return {
        "duration_hours": duration_hours,
        "system_labels": tuple(systems),
        "final_Ca": float(normal_process.Ca),
        "final_Cb": float(normal_process.Cb),
        "final_T": float(normal_process.T),
        "final_Tk": float(normal_process.Tk),
        "final_Tj_in": float(normal_process.Tj_in),
    }


def run_demo(duration_hours: float = DEFAULT_DURATION_HOURS) -> dict[str, object]:
    systems = _run_systems(duration_hours=duration_hours)
    return _summarize_systems(systems, duration_hours=duration_hours)


def main() -> dict[str, object]:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    mpl.set_loglevel("warning")

    pv_kwargs = {"linestyle": "-"}
    ref_kwargs = {"linestyle": "--", "alpha": 0.5}

    systems = _run_systems(duration_hours=DEFAULT_DURATION_HOURS, record_history=True)
    for label, system in systems.items():
        history = system.history

        plt.figure(figsize=(12, 10))

        ax = plt.subplot(3, 2, 1)
        plot_triplet_series(
            ax,
            history["T"],
            style="step",
            line_kwargs=pv_kwargs,
            label=label,
        )
        plot_triplet_series(
            ax,
            history["T.ref"],
            style="step",
            line_kwargs=ref_kwargs,
            label=f"Ref {label}",
        )
        plt.title("Reactor Temperature")
        plt.xlabel("Time [h]")
        plt.ylabel("Temperature [°C]")
        plt.grid(True)

        ax = plt.subplot(3, 2, 2)
        plot_triplet_series(
            ax,
            history["Qk"],
            style="step",
            line_kwargs=pv_kwargs,
            label=label,
        )
        plt.title("Jacket Heat Duty")
        plt.xlabel("Time [h]")
        plt.ylabel("Qk [kJ/h]")
        plt.grid(True)

        ax = plt.subplot(3, 2, 3)
        plot_triplet_series(
            ax,
            history["Ca"],
            style="step",
            line_kwargs=pv_kwargs,
            label=label,
        )
        plt.title("Concentration of A")
        plt.xlabel("Time [h]")
        plt.ylabel("[A] [mol/L]")
        plt.grid(True)

        ax = plt.subplot(3, 2, 4)
        plot_triplet_series(
            ax,
            history["Cb"],
            style="step",
            line_kwargs=pv_kwargs,
            label=label,
        )
        plot_triplet_series(
            ax,
            history["Cb.ref"],
            style="step",
            line_kwargs=ref_kwargs,
            label=f"Ref {label}",
        )
        plt.title("Concentration of B")
        plt.xlabel("Time [h]")
        plt.ylabel("[B] [mol/L]")
        plt.grid(True)

        ax = plt.subplot(3, 2, 5)
        plot_triplet_series(
            ax,
            history["Tk"],
            style="step",
            line_kwargs=pv_kwargs,
            label=label,
        )
        plt.title("Jacket Temperature")
        plt.xlabel("Time [h]")
        plt.ylabel("Temperature [°C]")
        plt.grid(True)

        ax = plt.subplot(3, 2, 6)
        plot_triplet_series(
            ax,
            history["Tj_in"],
            style="step",
            line_kwargs=pv_kwargs,
            label=label,
        )
        plt.title("Jacket Inlet Temperature")
        plt.xlabel("Time [h]")
        plt.ylabel("Temperature [°C]")
        plt.grid(True)

        plt.tight_layout()
    plt.show()
    return _summarize_systems(systems, duration_hours=DEFAULT_DURATION_HOURS)


if __name__ == "__main__":
    print(main())

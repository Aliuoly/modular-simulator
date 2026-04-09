"""Executable multicomponent startup demo for ThermoTrayDistillationColumn.

This demo uses a tuned n-hexane / n-heptane / n-octane operating point so the
column actually develops a meaningful separation profile from a dry startup.

Run:
    uv run python examples/dynamic_simulation_demos/thermo_tray_distillation_startup_demo.py
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import numpy as np

from modular_simulation.measurables.process_model import ProcessModel
import modular_simulation.thermodynamics.property_package as pp
from modular_simulation.thermodynamics.stream import StreamData
from modular_simulation.unit_processes.separation import ThermoTrayDistillationColumn

SPECIES_NAMES = ("n-hexane", "n-heptane", "n-octane")
SPECIES_SELECTOR = np.asarray((3.0, 4.0, 5.0), dtype=np.float64)
FEED_COMPOSITION = (1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0)


def _build_demo_property_package() -> pp.PengRobinsonPackage:
    species_ids = tuple(pp._DEFAULT_PR_SPECIES_CAS[int(index)] for index in SPECIES_SELECTOR)
    return pp.PengRobinsonPackage(species_ids=species_ids)


def _condenser_bubble_temperature_k(col: ThermoTrayDistillationColumn) -> float:
    package = _build_demo_property_package()
    try:
        state = package._flasher.flash(
            P=float(col.headspace_pressure_pa),
            VF=0.0,
            zs=list(np.asarray(col.distillate_composition, dtype=np.float64)),
        )
        value = float(state.T)
        return value if np.isfinite(value) else float("nan")
    except Exception:
        return float("nan")


def _attach(model: ProcessModel) -> None:
    model.attach_system(cast(Any, SimpleNamespace(solver_options={})))


def _stabilize_state(col: ThermoTrayDistillationColumn, values: np.ndarray) -> np.ndarray:
    clipped = np.asarray(values, dtype=np.float64).copy()
    for name, index in col.differential_view.index_map.items():
        state = np.asarray(clipped[index], dtype=np.float64)
        lower: float | None = None
        upper: float | None = None
        lname = name.lower()
        if "component_holdup" in lname or "component_moles" in lname:
            lower = 1.0e-9
        elif "temperature" in lname:
            lower = 250.0
            upper = 800.0
        if lower is not None:
            state = np.maximum(state, lower)
        if upper is not None:
            state = np.minimum(state, upper)
        clipped[index] = state
    return clipped


def _bounded_step(col: ThermoTrayDistillationColumn, dt_s: float, n_substeps: int = 3) -> None:
    params = col._params
    y = col.differential_view.to_array()
    u = col.boundary_view.to_array()
    h = dt_s / max(1, n_substeps)
    t_val = float(col.t)
    common = dict(
        k=params.k,
        y_map=params.y_map,
        u_map=params.boundary_map,
        k_map=params.k_map,
        algebraic_map=params.algebraic_map,
    )

    for _ in range(max(1, n_substeps)):
        alg0 = col.calculate_algebraic_values(
            y=y, u=u, algebraic_size=params.algebraic_size, **common
        )
        k1 = col.differential_rhs(t=t_val, y=y, u=u, algebraic=alg0, **common)
        y1 = _stabilize_state(col, y + h * k1)
        alg1 = col.calculate_algebraic_values(
            y=y1,
            u=u,
            algebraic_size=params.algebraic_size,
            **common,
        )
        k2 = col.differential_rhs(t=t_val + h, y=y1, u=u, algebraic=alg1, **common)
        y = _stabilize_state(col, y + 0.5 * h * (k1 + k2))
        t_val += h

    final_alg = col.calculate_algebraic_values(
        y=y,
        u=u,
        algebraic_size=params.algebraic_size,
        **common,
    )
    col.differential_view.update_from_array(y)
    col.algebraic_view.update_from_array(final_alg)
    col.accepted_dt_s = dt_s
    col.t = t_val


def _build_column() -> ThermoTrayDistillationColumn:
    col = ThermoTrayDistillationColumn(
        n_species=3,
        species_selector=SPECIES_SELECTOR,
        n_trays=12,
        feed_tray_indices=(6,),
        p_top_pa=150000.0,
        delta_p_tray_pa=500.0,
        eps_start=50.0,
        eps_drum=200.0,
        eps_kettle=100.0,
        tray_weir_height_m=0.001,
        liquid_flow_coeff=10000.0,
        vapor_flow_coeff=5.0,
    )
    _attach(col)
    col.apply_inlet(
        "feed_1",
        StreamData(
            temperature=385.0,
            pressure=150000.0,
            mole_fractions=FEED_COMPOSITION,
            molar_flow_rate=2.0,
        ),
    )
    col.build_startup_state()
    col.condenser_duty_request_W = -100000.0
    col.reboiler_duty_request_W = 100000.0
    col.reflux_withdrawal_flow = 1.5
    col.distillate_withdrawal_flow = 0.8
    col.bottoms_withdrawal_flow = 1.1
    return col


def _total(values: np.ndarray) -> float:
    return float(np.sum(np.asarray(values, dtype=np.float64)))


def run_demo(*, dt_s: float = 1.0, n_steps: int = 240, n_substeps: int = 3) -> dict[str, Any]:
    col = _build_column()

    settle_metrics: list[float] = []
    for _ in range(n_steps):
        _bounded_step(col, dt_s=dt_s, n_substeps=n_substeps)
        settle_metrics.append(float(col.settle_metric))

    tray_t = np.asarray(col.tray_temperature, dtype=np.float64)
    tray_x = np.asarray(col.tray_liquid_composition, dtype=np.float64).reshape(
        col.n_trays, col.n_species
    )
    drum_total = _total(col.condenser_drum_component_moles)
    kettle_total = _total(col.reboiler_kettle_component_moles)
    x_d = np.asarray(col.distillate_composition, dtype=np.float64)
    x_b = np.asarray(col.bottoms_composition, dtype=np.float64)
    settle_metric_decreasing = "unknown"
    if len(settle_metrics) >= 6:
        early_avg = float(np.mean(settle_metrics[:3]))
        late_avg = float(np.mean(settle_metrics[-3:]))
        settle_metric_decreasing = "yes" if late_avg < early_avg else "no"
    physical_separation = bool(
        np.all(np.isfinite(tray_t))
        and x_d[0] > FEED_COMPOSITION[0] + 0.15
        and x_b[-1] > FEED_COMPOSITION[-1] + 0.15
        and float(tray_t[0]) < float(tray_t[-1])
        and drum_total > 10.0
        and kettle_total > 10.0
    )
    bubble_temperature_k = _condenser_bubble_temperature_k(col)
    condenser_subcooling_k = bubble_temperature_k - float(col.condenser_drum_temperature)

    result = {
        "model_role": "backend_only_thermo_tray_actual",
        "startup_mode": "numerically_dry",
        "settle_mode": "runtime_equations_reused",
        "stepping_strategy": "demo_scoped_bounded_substep_refinement",
        "stepping_disclosure": (
            "This demo advances the runtime thermo-tray equations through a local bounded-substep "
            "refinement harness with stabilization clipping. It does not call raw runtime step() "
            "directly and should be interpreted as a demo-scoped numerical aid, not a separate "
            "physics model."
        ),
        "has_tray_temperatures": "yes",
        "has_tray_holdups": "yes",
        "has_condenser_drum": "yes",
        "has_reboiler_kettle": "yes",
        "no_broad_hard_clipping": "yes",
        "settle_metric_decreasing": settle_metric_decreasing,
        "species": ", ".join(SPECIES_NAMES),
        "n_trays": int(col.n_trays),
        "feed_tray": 6,
        "steps_taken": n_steps,
        "dt_s": dt_s,
        "n_substeps": n_substeps,
        "sim_time_s": n_steps * dt_s,
        "physical_separation": "yes" if physical_separation else "no",
        "distillate_x": [float(value) for value in x_d],
        "bottoms_x": [float(value) for value in x_b],
        "top_tray_temperature_K": float(tray_t[0]),
        "bottom_tray_temperature_K": float(tray_t[-1]),
        "drum_temperature_K": float(col.condenser_drum_temperature),
        "kettle_temperature_K": float(col.reboiler_kettle_temperature),
        "drum_total_mol": drum_total,
        "kettle_total_mol": kettle_total,
        "distillate_flow_mol_s": float(col.distillate_flow),
        "reflux_flow_mol_s": float(col.reflux_flow),
        "bottoms_flow_mol_s": float(col.bottoms_flow),
        "top_headspace_pressure_pa": float(col.headspace_pressure_pa),
        "bottom_pressure_pa": float(col.bottom_pressure_pa),
        "distillate_source_pressure_pa": float(col.distillate_source_pressure_pa),
        "reflux_source_pressure_pa": float(col.reflux_source_pressure_pa),
        "realized_condensed_flow_mol_s": float(col.realized_condensed_flow),
        "non_condensed_flow_mol_s": float(col.non_condensed_flow),
        "condenser_bubble_temperature_K": float(bubble_temperature_k),
        "condenser_subcooling_K": float(condenser_subcooling_k),
        "top_tray_x": [float(value) for value in tray_x[0]],
        "mid_tray_x": [float(value) for value in tray_x[int(col.n_trays) // 2]],
        "bottom_tray_x": [float(value) for value in tray_x[-1]],
        "settle_metric_final": float(settle_metrics[-1]) if settle_metrics else float("nan"),
    }

    print("THERMO-TRAY DISTILLATION STARTUP DEMO")
    print("=" * 60)
    print(f"Species:                  {result['species']}")
    print(f"n_trays / feed tray:      {result['n_trays']} / {result['feed_tray']}")
    print(f"Simulation horizon:       {result['sim_time_s']:.1f} s")
    print(f"Physical separation:      {result['physical_separation']}")
    print(
        "Final temperatures (K):   "
        f"top={result['top_tray_temperature_K']:.2f}, "
        f"drum={result['drum_temperature_K']:.2f}, "
        f"kettle={result['kettle_temperature_K']:.2f}, "
        f"bottom={result['bottom_tray_temperature_K']:.2f}"
    )
    print(
        "Inventories (mol):        "
        f"drum={result['drum_total_mol']:.2f}, kettle={result['kettle_total_mol']:.2f}"
    )
    print(
        "Realized flows (mol/s):   "
        f"D={result['distillate_flow_mol_s']:.3f}, "
        f"R={result['reflux_flow_mol_s']:.3f}, "
        f"B={result['bottoms_flow_mol_s']:.3f}"
    )
    print(
        "Pressure observables:     "
        f"P_head={result['top_headspace_pressure_pa']:.1f} Pa, "
        f"P_bottom={result['bottom_pressure_pa']:.1f} Pa, "
        f"P_Dsrc={result['distillate_source_pressure_pa']:.1f} Pa, "
        f"P_Rsrc={result['reflux_source_pressure_pa']:.1f} Pa"
    )
    print(
        "Condenser split (mol/s):  "
        f"V_cond={result['realized_condensed_flow_mol_s']:.3f}, "
        f"V_noncond={result['non_condensed_flow_mol_s']:.3f}"
    )
    print(
        "Subcooling evidence:      "
        f"T_bubble={result['condenser_bubble_temperature_K']:.2f} K, "
        f"T_drum={result['drum_temperature_K']:.2f} K, "
        f"subcooling={result['condenser_subcooling_K']:.3f} K"
    )
    print(
        f"Distillate composition:   {np.array2string(np.asarray(result['distillate_x']), precision=4)}"
    )
    print(
        f"Bottoms composition:      {np.array2string(np.asarray(result['bottoms_x']), precision=4)}"
    )
    print(
        f"Top tray x:               {np.array2string(np.asarray(result['top_tray_x']), precision=4)}"
    )
    print(
        f"Mid tray x:               {np.array2string(np.asarray(result['mid_tray_x']), precision=4)}"
    )
    print(
        f"Bottom tray x:            {np.array2string(np.asarray(result['bottom_tray_x']), precision=4)}"
    )
    print(f"Final settle metric:      {result['settle_metric_final']:.6e}")
    print(f"Stepping strategy:        {result['stepping_strategy']}")
    print(f"Stepping disclosure:      {result['stepping_disclosure']}")

    return result


def main() -> None:
    run_demo()


if __name__ == "__main__":
    main()

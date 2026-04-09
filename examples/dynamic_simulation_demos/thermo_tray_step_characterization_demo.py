"""Approximate multicomponent step-response characterization for ThermoTray.

This script uses a tuned n-hexane / n-heptane / n-octane operating point that
shows actual separation, then applies a handful of bounded step disturbances and
summarizes both the numeric responses and whether key response directions look
physically reasonable.

Run:
    uv run python examples/dynamic_simulation_demos/thermo_tray_step_characterization_demo.py
"""

from __future__ import annotations

import json
import math
import pathlib
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Callable, cast

import numpy as np

from modular_simulation.measurables.process_model import ProcessModel
import modular_simulation.thermodynamics.property_package as pp
from modular_simulation.thermodynamics.stream import StreamData
from modular_simulation.unit_processes.separation import ThermoTrayDistillationColumn

SPECIES_NAMES = ("n-hexane", "n-heptane", "n-octane")
SPECIES_SELECTOR = np.asarray((3.0, 4.0, 5.0), dtype=np.float64)
BASELINE_FEED_FLOW = 2.0
BASELINE_FEED_TEMPERATURE = 385.0
BASELINE_FEED_PRESSURE = 150000.0
BASELINE_FEED_COMPOSITION = (1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0)
BASELINE_CONDENSER_W = -100000.0
BASELINE_REBOILER_W = 100000.0
BASELINE_REFLUX = 1.5
BASELINE_DISTILLATE = 0.8
BASELINE_BOTTOMS = 1.1


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
        return value if math.isfinite(value) else math.nan
    except Exception:
        return math.nan


def _attach(model: ProcessModel) -> None:
    model.attach_system(cast(Any, SimpleNamespace(solver_options={})))


def _set_feed(
    model: ThermoTrayDistillationColumn,
    *,
    flow: float,
    composition: tuple[float, ...],
    temperature: float = BASELINE_FEED_TEMPERATURE,
    pressure: float = BASELINE_FEED_PRESSURE,
) -> None:
    model.apply_inlet(
        "feed_1",
        StreamData(
            temperature=temperature,
            pressure=pressure,
            mole_fractions=composition,
            molar_flow_rate=flow,
        ),
    )


def _set_duties(
    model: ThermoTrayDistillationColumn,
    *,
    condenser_w: float,
    reboiler_w: float,
) -> None:
    model.condenser_duty_request_W = condenser_w
    model.reboiler_duty_request_W = reboiler_w


def _set_withdrawals(
    model: ThermoTrayDistillationColumn,
    *,
    reflux: float,
    distillate: float,
    bottoms: float,
) -> None:
    model.reflux_withdrawal_flow = reflux
    model.distillate_withdrawal_flow = distillate
    model.bottoms_withdrawal_flow = bottoms


def _safe_float(value: Any) -> float:
    try:
        result = float(value)
        return result if math.isfinite(result) else math.nan
    except Exception:
        return math.nan


def _total(value: Any) -> float:
    return float(np.sum(np.asarray(value, dtype=np.float64)))


def _save_state(col: ThermoTrayDistillationColumn) -> dict[str, Any]:
    return {
        "diff": col.differential_view.to_array().copy(),
        "alg": col.algebraic_view.to_array().copy(),
        "t": float(col.t),
        "settle_hold": float(getattr(col, "_settle_hold_s", 0.0)),
    }


def _restore_state(col: ThermoTrayDistillationColumn, snap: dict[str, Any]) -> None:
    col.differential_view.update_from_array(snap["diff"].copy())
    col.algebraic_view.update_from_array(snap["alg"].copy())
    col.t = float(snap["t"])
    col._settle_hold_s = float(snap["settle_hold"])
    col._last_boundary_snapshot = None


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


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    variable_unit: str
    baseline_value: float
    stepped_value: float
    apply_step: Callable[[ThermoTrayDistillationColumn], None]


def _output_extractors(
    col: ThermoTrayDistillationColumn,
) -> dict[str, Callable[[ThermoTrayDistillationColumn], float]]:
    top = 0
    mid = int(col.n_trays) // 2
    bottom = int(col.n_trays) - 1
    return {
        "distillate_x_light": lambda m: _safe_float(m.distillate_composition[0]),
        "distillate_x_heavy": lambda m: _safe_float(m.distillate_composition[-1]),
        "bottoms_x_light": lambda m: _safe_float(m.bottoms_composition[0]),
        "bottoms_x_heavy": lambda m: _safe_float(m.bottoms_composition[-1]),
        "distillate_flow_mol_s": lambda m: _safe_float(m.distillate_flow),
        "reflux_flow_mol_s": lambda m: _safe_float(m.reflux_flow),
        "bottoms_flow_mol_s": lambda m: _safe_float(m.bottoms_flow),
        "drum_temperature_K": lambda m: _safe_float(m.condenser_drum_temperature),
        "kettle_temperature_K": lambda m: _safe_float(m.reboiler_kettle_temperature),
        "top_tray_temperature_K": lambda m: _safe_float(m.tray_temperature[top]),
        "mid_tray_temperature_K": lambda m: _safe_float(m.tray_temperature[mid]),
        "bottom_tray_temperature_K": lambda m: _safe_float(m.tray_temperature[bottom]),
        "drum_total_mol": lambda m: _total(m.condenser_drum_component_moles),
        "kettle_total_mol": lambda m: _total(m.reboiler_kettle_component_moles),
        "top_tray_liquid_flow_mol_s": lambda m: _safe_float(m.tray_liquid_flow[top]),
        "top_tray_vapor_flow_mol_s": lambda m: _safe_float(m.tray_vapor_flow[top]),
        "top_headspace_pressure_pa": lambda m: _safe_float(m.headspace_pressure_pa),
        "bottom_pressure_pa": lambda m: _safe_float(m.bottom_pressure_pa),
        "realized_condensed_flow_mol_s": lambda m: _safe_float(m.realized_condensed_flow),
        "non_condensed_flow_mol_s": lambda m: _safe_float(m.non_condensed_flow),
        "distillate_source_pressure_pa": lambda m: _safe_float(m.distillate_source_pressure_pa),
        "reflux_source_pressure_pa": lambda m: _safe_float(m.reflux_source_pressure_pa),
        "condenser_bubble_temperature_K": _condenser_bubble_temperature_k,
        "condenser_subcooling_K": lambda m: _safe_float(
            _condenser_bubble_temperature_k(m) - float(m.condenser_drum_temperature)
        ),
    }


def _summarize_signal(
    times: np.ndarray,
    values: np.ndarray,
    step_time: float,
    input_step: float,
) -> dict[str, float | None]:
    pre_mask = times < step_time
    post_mask = times >= step_time
    baseline_vals = values[pre_mask]
    final_vals = values[post_mask]
    bw = baseline_vals[-5:] if baseline_vals.size >= 5 else baseline_vals
    fw = final_vals[-5:] if final_vals.size >= 5 else final_vals
    if bw.size == 0 or fw.size == 0:
        return {
            "baseline": None,
            "final": None,
            "delta": None,
            "gain": None,
            "tau_s": None,
            "settling_time_s": None,
        }

    baseline = float(np.mean(bw))
    final = float(np.mean(fw))
    delta = final - baseline
    gain = delta / input_step if abs(input_step) > 1.0e-12 else math.nan

    tau_s: float | None = None
    if math.isfinite(delta) and abs(delta) > 1.0e-12:
        target = baseline + 0.632 * delta
        sv = values[post_mask]
        st = times[post_mask]
        indices = np.where(sv >= target)[0] if delta > 0.0 else np.where(sv <= target)[0]
        if indices.size > 0:
            tau_s = float(st[int(indices[0])] - step_time)

    settling_time_s: float | None = None
    if math.isfinite(delta) and abs(delta) > 1.0e-12:
        band = 0.02 * abs(delta)
        lo = min(final - band, final + band)
        hi = max(final - band, final + band)
        sv = values[post_mask]
        st = times[post_mask]
        outside = np.where((sv < lo) | (sv > hi))[0]
        if outside.size > 0 and int(outside[-1]) + 1 < len(st):
            settling_time_s = float(st[int(outside[-1]) + 1] - step_time)
        elif outside.size == 0:
            settling_time_s = 0.0

    return {
        "baseline": baseline,
        "final": final,
        "delta": delta,
        "gain": gain,
        "tau_s": tau_s,
        "settling_time_s": settling_time_s,
    }


def _apply_baseline(col: ThermoTrayDistillationColumn) -> None:
    _set_feed(
        col,
        flow=BASELINE_FEED_FLOW,
        composition=BASELINE_FEED_COMPOSITION,
    )
    _set_duties(
        col,
        condenser_w=BASELINE_CONDENSER_W,
        reboiler_w=BASELINE_REBOILER_W,
    )
    _set_withdrawals(
        col,
        reflux=BASELINE_REFLUX,
        distillate=BASELINE_DISTILLATE,
        bottoms=BASELINE_BOTTOMS,
    )


def _build_and_settle(
    dt_s: float = 4.0,
    n_substeps: int = 2,
    max_settle_steps: int = 120,
) -> tuple[ThermoTrayDistillationColumn, dict[str, Any], int]:
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
    _apply_baseline(col)
    col.build_startup_state()

    settle_taken = 0
    for _ in range(max_settle_steps):
        _bounded_step(col, dt_s=dt_s, n_substeps=n_substeps)
        settle_taken += 1

    return col, _save_state(col), settle_taken


def _run_scenario(
    col: ThermoTrayDistillationColumn,
    baseline_snap: dict[str, Any],
    scenario: Scenario,
    *,
    dt_s: float,
    n_substeps: int,
    pre_steps: int,
    post_steps: int,
) -> dict[str, Any]:
    _restore_state(col, baseline_snap)
    _apply_baseline(col)

    extractors = _output_extractors(col)
    times: list[float] = []
    history: dict[str, list[float]] = {name: [] for name in extractors}

    for _ in range(pre_steps):
        _bounded_step(col, dt_s=dt_s, n_substeps=n_substeps)
        times.append(float(col.t))
        for name, ext in extractors.items():
            history[name].append(ext(col))

    step_time = float(col.t)
    scenario.apply_step(col)

    for _ in range(post_steps):
        _bounded_step(col, dt_s=dt_s, n_substeps=n_substeps)
        times.append(float(col.t))
        for name, ext in extractors.items():
            history[name].append(ext(col))

    times_arr = np.asarray(times, dtype=np.float64)
    input_step = scenario.stepped_value - scenario.baseline_value
    summary = {
        name: _summarize_signal(
            times_arr, np.asarray(values, dtype=np.float64), step_time, input_step
        )
        for name, values in history.items()
    }

    return {
        "scenario": scenario.name,
        "description": scenario.description,
        "input_baseline": scenario.baseline_value,
        "input_stepped": scenario.stepped_value,
        "input_step": input_step,
        "variable_unit": scenario.variable_unit,
        "dt_s": dt_s,
        "pre_steps": pre_steps,
        "post_steps": post_steps,
        "post_horizon_s": post_steps * dt_s,
        "step_time_s": step_time,
        "times_s": list(map(float, times_arr.tolist())),
        "history": {name: list(map(float, values)) for name, values in history.items()},
        "summary": summary,
    }


SCENARIOS: list[Scenario] = [
    Scenario(
        name="feed_light_fraction_up",
        description="Increase feed light-key mole fraction from 0.333 to 0.450",
        variable_unit="mole_fraction",
        baseline_value=BASELINE_FEED_COMPOSITION[0],
        stepped_value=0.45,
        apply_step=lambda m: _set_feed(m, flow=BASELINE_FEED_FLOW, composition=(0.45, 0.35, 0.20)),
    ),
    Scenario(
        name="reflux_up",
        description="Increase reflux request from 1.50 to 1.80 mol/s",
        variable_unit="mol/s",
        baseline_value=BASELINE_REFLUX,
        stepped_value=1.8,
        apply_step=lambda m: _set_withdrawals(
            m,
            reflux=1.8,
            distillate=BASELINE_DISTILLATE,
            bottoms=BASELINE_BOTTOMS,
        ),
    ),
    Scenario(
        name="reboiler_duty_up",
        description="Increase reboiler duty from 100 kW to 115 kW",
        variable_unit="W",
        baseline_value=BASELINE_REBOILER_W,
        stepped_value=115000.0,
        apply_step=lambda m: _set_duties(
            m,
            condenser_w=BASELINE_CONDENSER_W,
            reboiler_w=115000.0,
        ),
    ),
    Scenario(
        name="distillate_withdrawal_up",
        description="Increase distillate withdrawal from 0.80 to 0.95 mol/s",
        variable_unit="mol/s",
        baseline_value=BASELINE_DISTILLATE,
        stepped_value=0.95,
        apply_step=lambda m: _set_withdrawals(
            m,
            reflux=BASELINE_REFLUX,
            distillate=0.95,
            bottoms=BASELINE_BOTTOMS,
        ),
    ),
]


EXPECTED_SIGNS: dict[str, dict[str, int]] = {
    "feed_light_fraction_up": {
        "distillate_x_light": 1,
        "bottoms_x_heavy": -1,
    },
    "reflux_up": {
        "distillate_x_light": 1,
        "bottoms_x_heavy": 1,
    },
    "reboiler_duty_up": {
        "kettle_temperature_K": 1,
    },
    "distillate_withdrawal_up": {
        "drum_total_mol": -1,
    },
}


def _evaluate_expectations(results: dict[str, Any]) -> list[dict[str, Any]]:
    evaluations: list[dict[str, Any]] = []
    for scenario in results["scenarios"]:
        expected = EXPECTED_SIGNS.get(scenario["scenario"], {})
        checks = []
        for output_name, expected_sign in expected.items():
            delta = scenario["summary"][output_name]["delta"]
            observed_sign = 0
            if delta is not None and abs(delta) > 1.0e-9:
                observed_sign = 1 if delta > 0.0 else -1
            checks.append(
                {
                    "output": output_name,
                    "expected_sign": expected_sign,
                    "observed_sign": observed_sign,
                    "passes": observed_sign == expected_sign,
                    "delta": delta,
                }
            )
        evaluations.append(
            {
                "scenario": scenario["scenario"],
                "all_pass": all(check["passes"] for check in checks),
                "checks": checks,
            }
        )
    return evaluations


def run_demo(
    *,
    dt_s: float = 4.0,
    n_substeps: int = 2,
    max_settle_steps: int = 200,
    pre_steps: int = 6,
    post_steps: int = 300,
) -> dict[str, Any]:
    print("Building and advancing multicomponent thermo-tray baseline...")
    col, baseline_snap, settle_taken = _build_and_settle(
        dt_s=dt_s,
        n_substeps=n_substeps,
        max_settle_steps=max_settle_steps,
    )
    print(
        f"  Advanced baseline for {settle_taken} bounded steps ({settle_taken * dt_s:.1f} s sim time)"
    )

    scenarios = []
    for scenario in SCENARIOS:
        print(f"  Running scenario: {scenario.name}...")
        scenarios.append(
            _run_scenario(
                col,
                baseline_snap,
                scenario,
                dt_s=dt_s,
                n_substeps=n_substeps,
                pre_steps=pre_steps,
                post_steps=post_steps,
            )
        )

    results = {
        "meta": {
            "model": "ThermoTrayDistillationColumn",
            "species": list(SPECIES_NAMES),
            "species_selector": [int(value) for value in SPECIES_SELECTOR],
            "n_species": 3,
            "n_trays": 12,
            "feed_tray": 6,
            "dt_s": dt_s,
            "n_substeps": n_substeps,
            "settle_steps": settle_taken,
            "settle_time_s": settle_taken * dt_s,
            "pre_steps": pre_steps,
            "post_steps": post_steps,
            "post_horizon_s": post_steps * dt_s,
            "stepping_strategy": "demo_scoped_bounded_substep_refinement",
            "baseline": {
                "feed_flow_mol_s": BASELINE_FEED_FLOW,
                "feed_temperature_K": BASELINE_FEED_TEMPERATURE,
                "feed_pressure_Pa": BASELINE_FEED_PRESSURE,
                "feed_composition": list(BASELINE_FEED_COMPOSITION),
                "condenser_duty_W": BASELINE_CONDENSER_W,
                "reboiler_duty_W": BASELINE_REBOILER_W,
                "reflux_mol_s": BASELINE_REFLUX,
                "distillate_mol_s": BASELINE_DISTILLATE,
                "bottoms_mol_s": BASELINE_BOTTOMS,
            },
            "note": (
                "Approximate characterization on a tuned multicomponent operating point. "
                "The rollout uses bounded substeps and state clipping to keep the step test in "
                "the physically relevant envelope while still exercising the real tray equations."
            ),
            "stepping_disclosure": (
                "This demo uses a local bounded-substep refinement harness with stabilization "
                "clipping to advance runtime thermo-tray equations. It is a demo-scoped numerical "
                "aid and should not be read as raw runtime step() output or a separate physics model."
            ),
        },
        "scenarios": scenarios,
    }
    results["expectation_checks"] = _evaluate_expectations(results)
    return results


def _print_summary(results: dict[str, Any]) -> None:
    meta = results["meta"]
    print()
    print("=" * 88)
    print("THERMO-TRAY MULTICOMPONENT STEP CHARACTERIZATION")
    print("=" * 88)
    print(f"Model:             {meta['model']}")
    print(f"Species:           {', '.join(meta['species'])}")
    print(f"n_trays / feed:    {meta['n_trays']} / {meta['feed_tray']}")
    print(f"dt / substeps:     {meta['dt_s']} s / {meta['n_substeps']}")
    print(f"Settle time:       {meta['settle_time_s']:.1f} s")
    print(f"Post-step horizon: {meta['post_horizon_s']:.1f} s")
    print(f"Note:              {meta['note']}")
    print(f"Stepping:          {meta['stepping_strategy']}")
    print(f"Disclosure:        {meta['stepping_disclosure']}")

    for scenario in results["scenarios"]:
        print("-" * 88)
        print(f"Scenario: {scenario['scenario']}")
        print(f"  {scenario['description']}")
        print(
            f"  Input: {scenario['input_baseline']} -> {scenario['input_stepped']} "
            f"(delta={scenario['input_step']:+.4g} {scenario['variable_unit']})"
        )
        print(
            f"  {'Output':<28s} {'Baseline':>10s} {'Final':>10s} {'Delta':>10s} "
            f"{'Gain':>10s} {'Tau(s)':>8s} {'Tsettle(s)':>10s}"
        )
        print(f"  {'-' * 28} {'-' * 10} {'-' * 10} {'-' * 10} {'-' * 10} {'-' * 8} {'-' * 10}")
        for output_name, summary in scenario["summary"].items():
            baseline = summary["baseline"]
            final = summary["final"]
            delta = summary["delta"]
            gain = summary["gain"]
            tau = summary["tau_s"]
            settling = summary["settling_time_s"]
            print(
                f"  {output_name:<28s} "
                f"{(f'{baseline:.4g}' if baseline is not None else 'N/A'):>10s} "
                f"{(f'{final:.4g}' if final is not None else 'N/A'):>10s} "
                f"{(f'{delta:+.4g}' if delta is not None else 'N/A'):>10s} "
                f"{(f'{gain:.4g}' if gain is not None and math.isfinite(gain) else 'N/A'):>10s} "
                f"{(f'{tau:.2f}' if tau is not None else 'N/A'):>8s} "
                f"{(f'{settling:.1f}' if settling is not None else 'N/A'):>10s}"
            )

    print("-" * 88)
    print("Response-Direction Checks")
    for evaluation in results["expectation_checks"]:
        status = "pass" if evaluation["all_pass"] else "check"
        print(f"  {evaluation['scenario']}: {status}")
        for check in evaluation["checks"]:
            delta = check["delta"]
            delta_text = "N/A" if delta is None else f"{delta:+.4g}"
            print(
                f"    {check['output']}: expected {check['expected_sign']:+d}, "
                f"observed {check['observed_sign']:+d}, delta={delta_text}, "
                f"passes={check['passes']}"
            )
    print("=" * 88)


def _plot_results(results: dict[str, Any], output_dir: pathlib.Path) -> list[str]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    scenarios = results["scenarios"]
    if not scenarios:
        return written

    output_names = list(scenarios[0]["summary"].keys())
    scenario_names = [scenario["scenario"] for scenario in scenarios]
    n_out = len(output_names)
    n_sc = len(scenario_names)
    gain_matrix = np.full((n_out, n_sc), np.nan, dtype=np.float64)
    tau_matrix = np.full((n_out, n_sc), np.nan, dtype=np.float64)
    settling_matrix = np.full((n_out, n_sc), np.nan, dtype=np.float64)

    for column, scenario in enumerate(scenarios):
        for row, output_name in enumerate(output_names):
            summary = scenario["summary"][output_name]
            gain_matrix[row, column] = np.nan if summary["gain"] is None else float(summary["gain"])
            tau_matrix[row, column] = (
                np.nan if summary["tau_s"] is None else float(summary["tau_s"])
            )
            settling_matrix[row, column] = (
                np.nan if summary["settling_time_s"] is None else float(summary["settling_time_s"])
            )

    fig, axes = plt.subplots(1, 3, figsize=(max(11, 2.0 * n_sc + 4), max(7, 0.38 * n_out + 3)))
    for ax, matrix, title in (
        (axes[0], gain_matrix, "Steady-state gain"),
        (axes[1], tau_matrix, "Approx. tau (s)"),
        (axes[2], settling_matrix, "Settling time (s)"),
    ):
        image = ax.imshow(matrix, aspect="auto", cmap="coolwarm")
        ax.set_title(title, fontsize=10)
        ax.set_xticks(range(n_sc))
        ax.set_xticklabels(scenario_names, rotation=45, ha="right", fontsize=8)
        ax.set_yticks(range(n_out))
        ax.set_yticklabels(output_names, fontsize=7)
        fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    fig.suptitle("ThermoTray Multicomponent Gain / Tau / Settling Matrix", fontsize=11)
    fig.tight_layout()
    heatmap_path = output_dir / "thermo_tray_gain_tau_settling_heatmap.png"
    fig.savefig(heatmap_path, dpi=160, bbox_inches="tight")
    written.append(str(heatmap_path))
    plt.close(fig)

    key_outputs = [
        "distillate_x_light",
        "bottoms_x_heavy",
        "drum_temperature_K",
        "kettle_temperature_K",
        "drum_total_mol",
        "kettle_total_mol",
        "top_headspace_pressure_pa",
        "bottom_pressure_pa",
        "realized_condensed_flow_mol_s",
        "non_condensed_flow_mol_s",
        "distillate_source_pressure_pa",
        "reflux_source_pressure_pa",
        "condenser_subcooling_K",
    ]
    fig2, axes2 = plt.subplots(
        len(key_outputs),
        n_sc,
        figsize=(3.8 * n_sc, 2.4 * len(key_outputs)),
        squeeze=False,
    )
    for column, scenario in enumerate(scenarios):
        times = np.asarray(scenario["times_s"], dtype=np.float64)
        step_time = float(scenario["step_time_s"])
        for row, output_name in enumerate(key_outputs):
            ax = axes2[row, column]
            values = np.asarray(scenario["history"][output_name], dtype=np.float64)
            ax.plot(times, values, color="tab:blue", linewidth=1.2)
            ax.axvline(step_time, color="tab:red", linestyle="--", linewidth=0.8)
            ax.set_ylabel(output_name, fontsize=6)
            if row == 0:
                ax.set_title(scenario["scenario"], fontsize=8)
            if row == len(key_outputs) - 1:
                ax.set_xlabel("time (s)", fontsize=7)
            ax.tick_params(labelsize=6)
    fig2.suptitle("ThermoTray Multicomponent Step-Response Pair Grid", fontsize=10, y=1.01)
    fig2.tight_layout()
    response_path = output_dir / "thermo_tray_step_response_matrix.png"
    fig2.savefig(response_path, dpi=160, bbox_inches="tight")
    written.append(str(response_path))
    plt.close(fig2)
    plt.close("all")
    return written


def main() -> None:
    results = run_demo()
    _print_summary(results)

    output_dir = pathlib.Path(".tmp/thermo_tray_step_plots")
    json_path = output_dir / "thermo_tray_step_characterization.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nJSON results written to: {json_path}")

    figure_paths = _plot_results(results, output_dir)
    if figure_paths:
        print("\nStep-response figure artifact(s):")
        for path in figure_paths:
            print(f"  {path}")


if __name__ == "__main__":
    main()

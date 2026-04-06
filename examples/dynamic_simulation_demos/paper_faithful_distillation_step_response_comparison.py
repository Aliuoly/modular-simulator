from __future__ import annotations

# pyright: reportMissingTypeStubs=false

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, cast

import numpy as np

from modular_simulation.measurables.process_model import ArrayIndex, ProcessModel
from modular_simulation.thermodynamics.stream import StreamData
from modular_simulation.unit_processes import (
    Gani1986DistillationColumn,
    Howard1970DistillationColumn,
    StagewiseDistillationColumn,
)


DEFAULT_DURATION_S = 4.0 * 3600.0
DEFAULT_STEP_TIME_S = 1.0 * 3600.0
DEFAULT_DT_S = 300.0
DEFAULT_SUBSTEPS = 5
DEFAULT_OUTPUT_DIR = Path(".tmp/step_response_reports")


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    variable_unit: str
    baseline_value: float
    stepped_value: float
    apply_baseline: Callable[[ProcessModel], None]
    apply_step: Callable[[ProcessModel], None]
    applicable_models: tuple[str, ...]


def _attach(model: ProcessModel) -> None:
    model.attach_system(cast(Any, SimpleNamespace(solver_options={})))


def _set_feed(
    model: ProcessModel,
    *,
    flow: float,
    temperature: float,
    pressure: float,
    composition: tuple[float, float, float],
) -> None:
    model.apply_inlet(
        "feed_1",
        StreamData(
            temperature=float(temperature),
            pressure=float(pressure),
            mole_fractions=composition,
            molar_flow_rate=float(flow),
        ),
    )


def _set_distillate_demand(model: ProcessModel, value: float) -> None:
    value = float(value)
    if hasattr(model, "apply_requested_outlet_through_flow_demand"):
        cast(Any, getattr(model, "apply_requested_outlet_through_flow_demand"))("distillate", value)
    else:
        setattr(model, "distillate_withdrawal_flow", value)


def _set_bottoms_demand(model: ProcessModel, value: float) -> None:
    value = float(value)
    if hasattr(model, "apply_requested_outlet_through_flow_demand"):
        cast(Any, getattr(model, "apply_requested_outlet_through_flow_demand"))("bottoms", value)
    else:
        setattr(model, "bottoms_withdrawal_flow", value)


def _set_stagewise_duties(model: ProcessModel, *, condenser_w: float, reboiler_w: float) -> None:
    setattr(model, "condenser_duty_request_W", float(condenser_w))
    setattr(model, "reboiler_duty_request_W", float(reboiler_w))


def _mid_value(value: Any) -> float:
    arr = np.asarray(value, dtype=np.float64)
    return float(arr[len(arr) // 2])


def _total(value: Any) -> float:
    return float(np.sum(np.asarray(value, dtype=np.float64)))


def _finite_or_nan(value: float) -> float:
    if not math.isfinite(value):
        return math.nan
    return float(value)


def _create_model(model_name: str) -> ProcessModel:
    if model_name == "stagewise":
        model = StagewiseDistillationColumn(
            n_species=3,
            active_contact_height_m=4.0,
            feed_stage_indices=(1,),
        )
        _attach(model)
        _set_stagewise_duties(model, condenser_w=-30000.0, reboiler_w=30000.0)
    elif model_name == "howard":
        model = Howard1970DistillationColumn(n_species=3, n_plates=5)
        _attach(model)
    elif model_name == "gani":
        model = Gani1986DistillationColumn(n_species=3, n_plates=5)
        _attach(model)
    else:
        raise ValueError(f"Unknown model: {model_name}")

    _set_feed(
        model,
        flow=10.0,
        temperature=350.0,
        pressure=101325.0,
        composition=(0.5, 0.3, 0.2),
    )
    _set_distillate_demand(model, 2.0)
    _set_bottoms_demand(model, 3.0)
    return model


SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        name="feed_light_fraction_up",
        description="Increase feed light-key composition from 0.50 to 0.70",
        variable_unit="mole_fraction",
        baseline_value=0.5,
        stepped_value=0.7,
        apply_baseline=lambda m: _set_feed(
            m,
            flow=10.0,
            temperature=350.0,
            pressure=101325.0,
            composition=(0.5, 0.3, 0.2),
        ),
        apply_step=lambda m: _set_feed(
            m,
            flow=10.0,
            temperature=350.0,
            pressure=101325.0,
            composition=(0.7, 0.2, 0.1),
        ),
        applicable_models=("stagewise", "howard", "gani"),
    ),
    Scenario(
        name="feed_flow_up",
        description="Increase feed flow from 10 to 12 mol/s",
        variable_unit="mol_s",
        baseline_value=10.0,
        stepped_value=12.0,
        apply_baseline=lambda m: _set_feed(
            m,
            flow=10.0,
            temperature=350.0,
            pressure=101325.0,
            composition=(0.5, 0.3, 0.2),
        ),
        apply_step=lambda m: _set_feed(
            m,
            flow=12.0,
            temperature=350.0,
            pressure=101325.0,
            composition=(0.5, 0.3, 0.2),
        ),
        applicable_models=("stagewise", "howard", "gani"),
    ),
    Scenario(
        name="distillate_withdrawal_up",
        description="Increase top product withdrawal from 2 to 3 mol/s",
        variable_unit="mol_s",
        baseline_value=2.0,
        stepped_value=3.0,
        apply_baseline=lambda m: _set_distillate_demand(m, 2.0),
        apply_step=lambda m: _set_distillate_demand(m, 3.0),
        applicable_models=("stagewise", "howard", "gani"),
    ),
    Scenario(
        name="bottoms_withdrawal_up",
        description="Increase bottom product withdrawal from 3 to 4 mol/s",
        variable_unit="mol_s",
        baseline_value=3.0,
        stepped_value=4.0,
        apply_baseline=lambda m: _set_bottoms_demand(m, 3.0),
        apply_step=lambda m: _set_bottoms_demand(m, 4.0),
        applicable_models=("stagewise", "howard", "gani"),
    ),
    Scenario(
        name="condenser_duty_more_negative",
        description="Increase top cooling duty magnitude from -30 kW to -45 kW",
        variable_unit="W",
        baseline_value=-30000.0,
        stepped_value=-45000.0,
        apply_baseline=lambda m: _set_stagewise_duties(m, condenser_w=-30000.0, reboiler_w=30000.0),
        apply_step=lambda m: _set_stagewise_duties(m, condenser_w=-45000.0, reboiler_w=30000.0),
        applicable_models=("stagewise",),
    ),
    Scenario(
        name="reboiler_duty_more_positive",
        description="Increase bottom duty from 30 kW to 45 kW",
        variable_unit="W",
        baseline_value=30000.0,
        stepped_value=45000.0,
        apply_baseline=lambda m: _set_stagewise_duties(m, condenser_w=-30000.0, reboiler_w=30000.0),
        apply_step=lambda m: _set_stagewise_duties(m, condenser_w=-30000.0, reboiler_w=45000.0),
        applicable_models=("stagewise",),
    ),
)


def _compute_algebraics(
    model: ProcessModel,
    y: np.ndarray,
    u: np.ndarray,
) -> np.ndarray:
    params = model._params
    return np.asarray(
        model.calculate_algebraic_values(
            y=y,
            u=u,
            k=params.k,
            y_map=params.y_map,
            u_map=params.boundary_map,
            k_map=params.k_map,
            algebraic_map=params.algebraic_map,
            algebraic_size=params.algebraic_size,
        ),
        dtype=np.float64,
    )


def _compute_rhs(
    model: ProcessModel,
    t: float,
    y: np.ndarray,
    u: np.ndarray,
    algebraic: np.ndarray,
) -> np.ndarray:
    params = model._params
    return np.asarray(
        model.differential_rhs(
            t=t,
            y=y,
            u=u,
            k=params.k,
            algebraic=algebraic,
            y_map=params.y_map,
            u_map=params.boundary_map,
            k_map=params.k_map,
            algebraic_map=params.algebraic_map,
        ),
        dtype=np.float64,
    )


def _stabilize_state(model: ProcessModel, y: np.ndarray) -> np.ndarray:
    clipped = np.asarray(y, dtype=np.float64).copy()
    for name, index in model.differential_view.index_map.items():
        values = np.asarray(clipped[index], dtype=np.float64)
        lower: float | None = None
        upper: float | None = None
        lname = name.lower()
        if "component_holdup" in lname or "component_moles" in lname:
            lower = 1.0e-9
        elif "energy_holdup" in lname:
            lower = 1.0e-3
        elif "pressure" in lname:
            lower = 5.0e4
            upper = 5.0e5
        elif "temperature" in lname:
            lower = 250.0
            upper = 800.0
        if lower is not None:
            values = np.maximum(values, lower)
        if upper is not None:
            values = np.minimum(values, upper)
        clipped[index] = values
    return clipped


def _analysis_step(model: ProcessModel, dt_s: float, n_substeps: int) -> None:
    y = model.differential_view.to_array()
    u = model.boundary_view.to_array()
    h = dt_s / max(1, n_substeps)
    t = float(model.t)
    for _ in range(max(1, n_substeps)):
        alg0 = _compute_algebraics(model, y, u)
        k1 = _compute_rhs(model, t, y, u, alg0)
        y1 = _stabilize_state(model, y + h * k1)
        alg1 = _compute_algebraics(model, y1, u)
        k2 = _compute_rhs(model, t + h, y1, u, alg1)
        y = _stabilize_state(model, y + 0.5 * h * (k1 + k2))
        t += h
    final_alg = _compute_algebraics(model, y, u)
    model.differential_view.update_from_array(y)
    model.algebraic_view.update_from_array(final_alg)
    model.t = t


def _output_extractors(model_name: str) -> dict[str, Callable[[ProcessModel], float]]:
    outputs: dict[str, Callable[[ProcessModel], float]] = {
        "distillate_flow_mol_s": lambda m: float(m.get_outlet_stream("distillate").molar_flow_rate),
        "distillate_x_light": lambda m: float(m.get_outlet_stream("distillate").mole_fractions[0]),
        "bottoms_flow_mol_s": lambda m: float(m.get_outlet_stream("bottoms").molar_flow_rate),
        "bottoms_x_heavy": lambda m: float(m.get_outlet_stream("bottoms").mole_fractions[2]),
        "reflux_drum_total_mol": lambda m: _total(getattr(m, "reflux_drum_component_moles")),
    }
    if model_name == "stagewise":
        outputs.update(
            {
                "bottoms_sump_total_mol": lambda m: _total(
                    getattr(m, "bottoms_sump_component_moles")
                ),
                "column_pressure_pa": lambda m: float(getattr(m, "column_pressure_pa")),
                "realized_reboiler_boilup_mol_s": lambda m: float(
                    getattr(m, "realized_reboiler_boilup_flow_mol_s")
                ),
                "realized_condensed_flow_mol_s": lambda m: float(
                    getattr(m, "realized_condensed_flow_mol_s")
                ),
            }
        )
    elif model_name == "howard":
        outputs.update(
            {
                "column_pressure_pa": lambda m: float(getattr(m, "column_pressure_pa")),
                "mid_plate_temperature_K": lambda m: _mid_value(getattr(m, "plate_temperature_K")),
                "mid_plate_liquid_flow_mol_s": lambda m: _mid_value(
                    getattr(m, "plate_liquid_flow_mol_s")
                ),
                "mid_plate_vapor_flow_mol_s": lambda m: _mid_value(
                    getattr(m, "plate_vapor_flow_mol_s")
                ),
            }
        )
    elif model_name == "gani":
        outputs.update(
            {
                "reboiler_total_mol": lambda m: _total(getattr(m, "reboiler_component_moles")),
                "mid_plate_temperature_K": lambda m: _mid_value(getattr(m, "plate_temperature_k")),
                "mid_plate_liquid_flow_mol_s": lambda m: _mid_value(
                    getattr(m, "plate_liquid_flow_mol_s")
                ),
                "mid_plate_vapor_flow_mol_s": lambda m: _mid_value(
                    getattr(m, "plate_vapor_flow_mol_s")
                ),
            }
        )
    return outputs


def _summarize_signal(
    times_s: np.ndarray,
    values: np.ndarray,
    step_time_s: float,
    input_step: float,
) -> dict[str, float | None]:
    pre_mask = times_s < step_time_s
    post_mask = times_s >= step_time_s
    baseline_values = values[pre_mask]
    final_values = values[post_mask]
    baseline_window = baseline_values[-5:] if baseline_values.size >= 5 else baseline_values
    final_window = final_values[-5:] if final_values.size >= 5 else final_values
    if baseline_window.size == 0 or final_window.size == 0:
        return {
            "baseline": None,
            "final": None,
            "delta": None,
            "gain": None,
            "tau_s": None,
        }

    baseline = float(np.mean(baseline_window))
    final = float(np.mean(final_window))
    delta = final - baseline
    gain = delta / input_step if abs(input_step) > 1.0e-12 else math.nan
    tau_s: float | None = None
    if math.isfinite(delta) and abs(delta) > 1.0e-12:
        target = baseline + 0.632 * delta
        search_times = times_s[post_mask]
        search_values = values[post_mask]
        hit_index: np.ndarray
        if delta > 0.0:
            hit_index = np.where(search_values >= target)[0]
        else:
            hit_index = np.where(search_values <= target)[0]
        if hit_index.size > 0:
            tau_s = float(search_times[int(hit_index[0])] - step_time_s)

    return {
        "baseline": _finite_or_nan(baseline),
        "final": _finite_or_nan(final),
        "delta": _finite_or_nan(delta),
        "gain": _finite_or_nan(gain),
        "tau_s": None if tau_s is None else _finite_or_nan(tau_s),
    }


def _run_scenario(
    model_name: str,
    scenario: Scenario,
    *,
    duration_s: float,
    step_time_s: float,
    dt_s: float,
    n_substeps: int,
) -> dict[str, Any]:
    model = _create_model(model_name)
    scenario.apply_baseline(model)
    extractors = _output_extractors(model_name)
    times: list[float] = []
    history: dict[str, list[float]] = {name: [] for name in extractors}
    n_steps = max(1, int(round(duration_s / dt_s)))
    step_index = min(n_steps - 1, max(1, int(round(step_time_s / dt_s))))
    for idx in range(n_steps):
        if idx == step_index:
            scenario.apply_step(model)
        _analysis_step(model, dt_s, n_substeps)
        times.append(float(model.t))
        for output_name, extractor in extractors.items():
            try:
                history[output_name].append(_finite_or_nan(float(extractor(model))))
            except Exception:
                history[output_name].append(math.nan)

    times_arr = np.asarray(times, dtype=np.float64)
    summary: dict[str, Any] = {}
    input_step = float(scenario.stepped_value - scenario.baseline_value)
    for output_name, values in history.items():
        summary[output_name] = _summarize_signal(
            times_arr,
            np.asarray(values, dtype=np.float64),
            float(step_index * dt_s),
            input_step,
        )
    return {
        "scenario": scenario.name,
        "description": scenario.description,
        "model": model_name,
        "duration_s": float(duration_s),
        "step_time_s": float(step_index * dt_s),
        "dt_s": float(dt_s),
        "n_substeps": int(n_substeps),
        "input_baseline": float(scenario.baseline_value),
        "input_stepped": float(scenario.stepped_value),
        "input_step": input_step,
        "times_s": list(map(float, times_arr.tolist())),
        "history": history,
        "summary": summary,
    }


def _scenario_by_name() -> dict[str, Scenario]:
    return {scenario.name: scenario for scenario in SCENARIOS}


def _run_experiment(
    *,
    models: list[str],
    scenarios: list[str],
    duration_s: float,
    step_time_s: float,
    dt_s: float,
    n_substeps: int,
) -> dict[str, Any]:
    scenario_lookup = _scenario_by_name()
    results: dict[str, Any] = {
        "meta": {
            "duration_s": float(duration_s),
            "duration_h": float(duration_s / 3600.0),
            "step_time_s": float(step_time_s),
            "step_time_h": float(step_time_s / 3600.0),
            "dt_s": float(dt_s),
            "n_substeps": int(n_substeps),
            "integrator": "custom_heun_stabilized",
            "note": (
                "Ad hoc analysis integrator using each model's algebraic and RHS functions. "
                "Use for comparative probing, not as a formal verification artifact."
            ),
        },
        "results": {},
    }
    for model_name in models:
        model_results: dict[str, Any] = {}
        for scenario_name in scenarios:
            scenario = scenario_lookup[scenario_name]
            if model_name not in scenario.applicable_models:
                continue
            model_results[scenario_name] = _run_scenario(
                model_name,
                scenario,
                duration_s=duration_s,
                step_time_s=step_time_s,
                dt_s=dt_s,
                n_substeps=n_substeps,
            )
        results["results"][model_name] = model_results
    return results


def _plot_results(results: dict[str, Any], output_dir: Path, show: bool) -> list[str]:
    import matplotlib

    if not show:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    written: list[str] = []
    for model_name, model_results in results["results"].items():
        if not model_results:
            continue
        scenario_names = list(model_results.keys())
        first = next(iter(model_results.values()))
        output_names = list(first["summary"].keys())

        gain_matrix = np.full((len(output_names), len(scenario_names)), np.nan, dtype=np.float64)
        tau_matrix = np.full((len(output_names), len(scenario_names)), np.nan, dtype=np.float64)
        for j, scenario_name in enumerate(scenario_names):
            summary = model_results[scenario_name]["summary"]
            for i, output_name in enumerate(output_names):
                gain = summary[output_name]["gain"]
                tau = summary[output_name]["tau_s"]
                gain_matrix[i, j] = np.nan if gain is None else float(gain)
                tau_matrix[i, j] = np.nan if tau is None else float(tau)

        fig, axes = plt.subplots(
            1, 2, figsize=(max(8, 1.8 * len(scenario_names)), max(8, 0.3 * len(output_names) + 4))
        )
        im0 = axes[0].imshow(gain_matrix, aspect="auto", cmap="coolwarm")
        axes[0].set_title(f"{model_name}: steady-state gain matrix")
        axes[0].set_xticks(range(len(scenario_names)))
        axes[0].set_xticklabels(scenario_names, rotation=45, ha="right")
        axes[0].set_yticks(range(len(output_names)))
        axes[0].set_yticklabels(output_names)
        fig.colorbar(im0, ax=axes[0], fraction=0.046, pad=0.04)

        im1 = axes[1].imshow(tau_matrix, aspect="auto", cmap="viridis")
        axes[1].set_title(f"{model_name}: approximate tau matrix (s)")
        axes[1].set_xticks(range(len(scenario_names)))
        axes[1].set_xticklabels(scenario_names, rotation=45, ha="right")
        axes[1].set_yticks(range(len(output_names)))
        axes[1].set_yticklabels(output_names)
        fig.colorbar(im1, ax=axes[1], fraction=0.046, pad=0.04)
        fig.tight_layout()
        heatmap_path = output_dir / f"{model_name}_gain_tau_matrix.png"
        fig.savefig(heatmap_path, dpi=160, bbox_inches="tight")
        written.append(str(heatmap_path))

        key_outputs = output_names[: min(5, len(output_names))]
        fig2, axes2 = plt.subplots(
            len(key_outputs),
            len(scenario_names),
            figsize=(4.0 * len(scenario_names), 2.5 * len(key_outputs)),
            squeeze=False,
        )
        for col, scenario_name in enumerate(scenario_names):
            payload = model_results[scenario_name]
            times = np.asarray(payload["times_s"], dtype=np.float64)
            step_time_s = float(payload["step_time_s"])
            for row, output_name in enumerate(key_outputs):
                ax = axes2[row, col]
                values = np.asarray(payload["history"][output_name], dtype=np.float64)
                summary = payload["summary"][output_name]
                baseline = summary["baseline"]
                final = summary["final"]
                if (
                    baseline is not None
                    and final is not None
                    and math.isfinite(final - baseline)
                    and abs(final - baseline) > 1.0e-12
                ):
                    norm = (values - float(baseline)) / float(final - baseline)
                    ax.plot(times / 3600.0, norm, linewidth=1.2)
                    ax.set_ylabel(f"{output_name}\n(norm)")
                else:
                    ax.plot(times / 3600.0, values, linewidth=1.2)
                    ax.set_ylabel(output_name)
                ax.axvline(step_time_s / 3600.0, color="tab:red", linestyle="--", linewidth=0.8)
                if row == 0:
                    ax.set_title(scenario_name)
                if row == len(key_outputs) - 1:
                    ax.set_xlabel("time (h)")
        fig2.suptitle(f"{model_name}: normalized step-response matrix", y=1.01)
        fig2.tight_layout()
        response_path = output_dir / f"{model_name}_response_matrix.png"
        fig2.savefig(response_path, dpi=160, bbox_inches="tight")
        written.append(str(response_path))

    if show:
        plt.show()
    else:
        plt.close("all")
    return written


def run_demo(
    *,
    models: list[str] | None = None,
    scenarios: list[str] | None = None,
    duration_s: float = DEFAULT_DURATION_S,
    step_time_s: float = DEFAULT_STEP_TIME_S,
    dt_s: float = DEFAULT_DT_S,
    n_substeps: int = DEFAULT_SUBSTEPS,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    show: bool = True,
) -> dict[str, Any]:
    models = models or ["stagewise", "howard", "gani"]
    scenarios = scenarios or [scenario.name for scenario in SCENARIOS]
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    results = _run_experiment(
        models=models,
        scenarios=scenarios,
        duration_s=duration_s,
        step_time_s=step_time_s,
        dt_s=dt_s,
        n_substeps=n_substeps,
    )
    figure_paths = _plot_results(results, output_path, show=show)
    summary_path = output_path / "paper_faithful_step_response_summary.json"
    summary_path.write_text(json.dumps(results, indent=2))
    return {
        "duration_s": float(duration_s),
        "duration_h": float(duration_s / 3600.0),
        "step_time_s": float(step_time_s),
        "step_time_h": float(step_time_s / 3600.0),
        "dt_s": float(dt_s),
        "n_substeps": int(n_substeps),
        "models": models,
        "scenarios": scenarios,
        "summary_json": str(summary_path),
        "figures": figure_paths,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Paper-faithful distillation dynamic step-response comparison"
    )
    parser.add_argument("--models", nargs="*", default=["stagewise", "howard", "gani"])
    parser.add_argument("--scenarios", nargs="*", default=[scenario.name for scenario in SCENARIOS])
    parser.add_argument("--duration-s", type=float, default=DEFAULT_DURATION_S)
    parser.add_argument("--step-time-s", type=float, default=DEFAULT_STEP_TIME_S)
    parser.add_argument("--dt-s", type=float, default=DEFAULT_DT_S)
    parser.add_argument("--substeps", type=int, default=DEFAULT_SUBSTEPS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-show", action="store_true")
    parser.add_argument("--quick", action="store_true", help="Shorter run for shell validation")
    args = parser.parse_args()

    duration_s = float(args.duration_s)
    step_time_s = float(args.step_time_s)
    dt_s = float(args.dt_s)
    substeps = int(args.substeps)
    scenarios = list(args.scenarios)

    if args.quick:
        duration_s = 1200.0
        step_time_s = 300.0
        dt_s = 60.0
        substeps = 3
        scenarios = [
            name
            for name in scenarios
            if name
            in {"feed_light_fraction_up", "distillate_withdrawal_up", "bottoms_withdrawal_up"}
        ]

    result = run_demo(
        models=list(args.models),
        scenarios=scenarios,
        duration_s=duration_s,
        step_time_s=step_time_s,
        dt_s=dt_s,
        n_substeps=substeps,
        output_dir=args.output_dir,
        show=not args.no_show,
    )
    print("PAPER-FAITHFUL DISTILLATION STEP RESPONSE COMPARISON")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

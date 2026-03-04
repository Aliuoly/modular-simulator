from __future__ import annotations

from pathlib import Path
import argparse
import sys

import matplotlib.pyplot as plt


# Try componentized runner; fallback only on import errors
try:
    from examples.simple_irreversible_energy_balance_system.three_tank_staged_connected_components import (
        run_three_tank_staged_connected_components,
    )
except (ModuleNotFoundError, ImportError):
    from pathlib import Path as _Path

    project_root = _Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.append(str(project_root))
    try:
        from examples.simple_irreversible_energy_balance_system.three_tank_staged_connected_components import (
            run_three_tank_staged_connected_components,
        )
    except (ModuleNotFoundError, ImportError):
        run_three_tank_staged_connected_components = None

# Try import for legacy control path; only import-time errors are tolerated
try:
    from examples.simple_irreversible_energy_balance_system.three_tank_staged_connected_control import (
        run_three_tank_staged_control,
    )  # type: ignore
except (ModuleNotFoundError, ImportError):
    run_three_tank_staged_control = None  # type: ignore


def _extract_series(history: list[dict[str, float]], key: str) -> list[float]:
    return [row[key] for row in history]


def plot_control_objectives(
    *,
    duration_s: float,
    dt_s: float,
    target_b3: float,
    step_time_s: float | None,
    step_target_b3: float | None,
    output_path: Path | None,
    show_plot: bool,
) -> None:
    runner = (
        run_three_tank_staged_connected_components
        if callable(run_three_tank_staged_connected_components)
        else None
    )
    if runner is not None:
        result = runner(
            duration_s=duration_s,
            dt_s=dt_s,
            final_product_target_b_mol_per_l=target_b3,
            step_change_time_s=(step_time_s if step_time_s is not None else 3600.0),
            step_target_b_mol_per_l=(step_target_b3 if step_target_b3 is not None else 5.05),
        )
    elif callable(run_three_tank_staged_control):
        result = run_three_tank_staged_control(
            duration_s=duration_s,
            dt_s=dt_s,
            final_product_target_b_mol_per_l=target_b3,
            step_change_time_s=(step_time_s if step_time_s is not None else 3600.0),
            step_target_b_mol_per_l=(step_target_b3 if step_target_b3 is not None else 5.05),
        )
    else:
        raise RuntimeError("No suitable three-tank staged component runner available for plotting")

    history = result["history"]
    if not isinstance(history, list) or not history:
        raise RuntimeError("example did not return sampled history for plotting")

    # PRE-VALIDATION: verify required keys exist before extracting series
    time_keys_ok = ("time_h" in history[0]) or ("time_s" in history[0])
    required_keys = [
        "v1_l",
        "v2_l",
        "v3_l",
        "b1_mol_per_l",
        "b2_mol_per_l",
        "b3_mol_per_l",
        "open_1_to_2",
        "open_2_to_3",
        "open_product",
        "open_feed_2",
        "open_feed_3",
        "target_b3_sp",
    ]
    missing: list[str] = []
    if history:
        if not time_keys_ok:
            missing.append("time_h or time_s")
        for k in required_keys:
            if k not in history[0]:
                missing.append(k)
    if missing:
        raise RuntimeError("Missing required history keys for plotting: " + ", ".join(missing))

    # Extract time axis
    if "time_h" in history[0]:
        time_h = _extract_series(history, "time_h")
    else:
        time_s = _extract_series(history, "time_s")
        time_h = [t / 3600.0 for t in time_s]

    v1_l = _extract_series(history, "v1_l")
    v2_l = _extract_series(history, "v2_l")
    v3_l = _extract_series(history, "v3_l")

    b1 = _extract_series(history, "b1_mol_per_l")
    b2 = _extract_series(history, "b2_mol_per_l")
    b3 = _extract_series(history, "b3_mol_per_l")

    open_1_to_2 = _extract_series(history, "open_1_to_2")
    open_2_to_3 = _extract_series(history, "open_2_to_3")
    open_product = _extract_series(history, "open_product")
    open_feed_2 = _extract_series(history, "open_feed_2")
    open_feed_3 = _extract_series(history, "open_feed_3")

    v_sp = [900.0] * len(time_h)
    # Directly extract required final B3 SP; this is a required history field
    b3_sp = _extract_series(history, "target_b3_sp")

    step_time_h = (step_time_s / 3600.0) if step_time_s is not None else None

    fig, axes = plt.subplots(4, 2, figsize=(14, 14), sharex=True)
    axes[0, 0].plot(time_h, v1_l, label="PV: Tank 1 volume", linewidth=2.0)
    axes[0, 0].plot(time_h, v_sp, "--", label="SP: Tank 1 volume", linewidth=1.5)
    axes[0, 0].set_ylabel("Volume [L]")
    axes[0, 0].set_title("Tank 1 objective")
    axes[0, 0].grid(True)
    axes[0, 0].legend()
    if step_time_h is not None:
        axes[0, 0].axvline(step_time_h, color="black", linestyle=":", linewidth=1.4)

    axes[0, 1].plot(time_h, open_1_to_2, label="MV: Valve tank1->tank2", linewidth=2.0)
    axes[0, 1].set_ylabel("Open fraction [-]")
    axes[0, 1].set_title("Tank 1 manipulated variable")
    axes[0, 1].set_ylim(0.0, 1.05)
    axes[0, 1].grid(True)
    axes[0, 1].legend()
    if step_time_h is not None:
        axes[0, 1].axvline(step_time_h, color="black", linestyle=":", linewidth=1.4)

    axes[1, 0].plot(time_h, v2_l, label="PV: Tank 2 volume", linewidth=2.0)
    axes[1, 0].plot(time_h, v_sp, "--", label="SP: Tank 2 volume", linewidth=1.5)
    axes[1, 0].set_ylabel("Volume [L]")
    axes[1, 0].set_title("Tank 2 objective")
    axes[1, 0].grid(True)
    axes[1, 0].legend()
    if step_time_h is not None:
        axes[1, 0].axvline(step_time_h, color="black", linestyle=":", linewidth=1.4)

    axes[1, 1].plot(time_h, open_2_to_3, label="MV: Valve tank2->tank3", linewidth=2.0)
    axes[1, 1].plot(time_h, open_feed_2, label="MV: Tank 2 makeup valve", linewidth=1.8)
    axes[1, 1].set_ylabel("Open fraction [-]")
    axes[1, 1].set_title("Tank 2 manipulated variables")
    axes[1, 1].set_ylim(0.0, 1.05)
    axes[1, 1].grid(True)
    axes[1, 1].legend()
    if step_time_h is not None:
        axes[1, 1].axvline(step_time_h, color="black", linestyle=":", linewidth=1.4)

    axes[2, 0].plot(time_h, v3_l, label="PV: Tank 3 volume", linewidth=2.0)
    axes[2, 0].plot(time_h, v_sp, "--", label="SP: Tank 3 volume", linewidth=1.5)
    axes[2, 0].set_ylabel("Volume [L]")
    axes[2, 0].set_title("Tank 3 level objective")
    axes[2, 0].grid(True)
    axes[2, 0].legend()
    if step_time_h is not None:
        axes[2, 0].axvline(step_time_h, color="black", linestyle=":", linewidth=1.4)

    axes[2, 1].plot(time_h, open_product, label="MV: Product valve", linewidth=2.0)
    axes[2, 1].plot(time_h, open_feed_3, label="MV: Tank 3 makeup valve", linewidth=1.8)
    axes[2, 1].set_ylabel("Open fraction [-]")
    axes[2, 1].set_title("Tank 3 manipulated variables")
    axes[2, 1].set_ylim(0.0, 1.05)
    axes[2, 1].grid(True)
    axes[2, 1].legend()
    if step_time_h is not None:
        axes[2, 1].axvline(step_time_h, color="black", linestyle=":", linewidth=1.4)

    axes[3, 0].plot(time_h, b1, label="Tank 1 B", linewidth=1.8)
    axes[3, 0].plot(time_h, b2, label="Tank 2 B", linewidth=1.8)
    axes[3, 0].plot(time_h, b3, label="Tank 3 B", linewidth=2.2)
    axes[3, 0].plot(time_h, b3_sp, "--", label="SP: Final product B", linewidth=1.5)
    axes[3, 0].set_xlabel("Time [h]")
    axes[3, 0].set_ylabel("Concentration [mol/L]")
    axes[3, 0].set_title("Composition progression and final objective")
    axes[3, 0].grid(True)
    if step_time_h is not None:
        axes[3, 0].axvline(
            step_time_h, color="black", linestyle=":", linewidth=1.4, label="SP step"
        )
    axes[3, 0].legend()
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=160)
        print(f"saved plot: {output_path}")

    if show_plot:
        plt.show()
    else:
        plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot PV vs SP and MV for the three-tank staged connected example"
    )
    parser.add_argument("--duration-s", type=float, default=4.0 * 3600.0)
    parser.add_argument("--dt-s", type=float, default=10.0)
    parser.add_argument("--target-b3", type=float, default=4.80)
    parser.add_argument("--step-time-s", type=float, default=2.0 * 3600.0)
    parser.add_argument("--step-target-b3", type=float, default=5.05)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "examples/simple_irreversible_energy_balance_system/three_tank_staged_connected_control.png"
        ),
    )
    parser.add_argument("--show", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    plot_control_objectives(
        duration_s=args.duration_s,
        dt_s=args.dt_s,
        target_b3=args.target_b3,
        step_time_s=args.step_time_s,
        step_target_b3=args.step_target_b3,
        output_path=args.output,
        show_plot=args.show,
    )

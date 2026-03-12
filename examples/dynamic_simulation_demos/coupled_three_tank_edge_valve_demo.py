from __future__ import annotations

# pyright: reportMissingTypeStubs=false

from pathlib import Path
import sys

try:
    from examples.simple_irreversible_energy_balance_system.three_tank_staged_connected_control import (
        run_three_tank_staged_control,
    )
except ModuleNotFoundError:
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.append(str(project_root))
    from examples.simple_irreversible_energy_balance_system.three_tank_staged_connected_control import (
        run_three_tank_staged_control,
    )


def run_demo() -> dict[str, object]:
    summary = run_three_tank_staged_control(
        duration_s=2.0 * 3_600.0,
        dt_s=10.0,
        final_product_target_b_mol_per_l=4.75,
        step_change_time_s=1.0 * 3_600.0,
        step_target_b_mol_per_l=4.35,
    )
    return {
        "target_b3_initial": summary["target_b3_initial"],
        "target_b3_final_sp": summary["target_b3_final_sp"],
        "final_b3": summary["final_b3"],
        "final_valve_openings": summary["final_valve_openings"],
        "queued_valve_request_count": summary["queued_valve_request_count"],
    }


def main() -> None:
    result = run_demo()
    print("COUPLED THREE-TANK EDGE VALVE DEMO")
    for key, value in result.items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()

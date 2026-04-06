from __future__ import annotations

# pyright: reportMissingTypeStubs=false

import argparse
import importlib
import json
from collections.abc import Callable, Mapping
from pathlib import Path
import sys
from typing import cast

project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))


DemoRunner = Callable[[], Mapping[str, object]]

DEMO_TARGETS: dict[str, tuple[str, str]] = {
    "cstr_thermal_step_demo": (
        "examples.dynamic_simulation_demos.cstr_thermal_step_demo",
        "run_demo",
    ),
    "pfr_thermal_step_demo": (
        "examples.dynamic_simulation_demos.pfr_thermal_step_demo",
        "run_demo",
    ),
    "flash_backpressure_valve_demo": (
        "examples.dynamic_simulation_demos.flash_backpressure_valve_demo",
        "run_demo",
    ),
    "coupled_cstr_flash_physical_actuator_demo": (
        "examples.dynamic_simulation_demos.coupled_cstr_flash_physical_actuator_demo",
        "run_demo",
    ),
    "coupled_three_tank_edge_valve_demo": (
        "examples.dynamic_simulation_demos.coupled_three_tank_edge_valve_demo",
        "run_demo",
    ),
    "paper_faithful_distillation_comparison": (
        "examples.dynamic_simulation_demos.paper_faithful_distillation_comparison",
        "run_demo",
    ),
    "shortcut_distillation_reboiler_demo": (
        "examples.dynamic_simulation_demos.shortcut_distillation_reboiler_demo",
        "run_demo",
    ),
}


def _resolve_runner(name: str) -> DemoRunner:
    module_name, function_name = DEMO_TARGETS[name]
    module = importlib.import_module(module_name)
    runner = getattr(module, function_name)
    return cast(DemoRunner, runner)


def run_all(*, selected: str | None = None) -> tuple[dict[str, Mapping[str, object]], list[str]]:
    names = [selected] if selected is not None else list(DEMO_TARGETS)
    results: dict[str, Mapping[str, object]] = {}
    failures: list[str] = []

    for name in names:
        if name not in DEMO_TARGETS:
            failures.append(f"Unknown demo: {name}")
            continue
        try:
            results[name] = _resolve_runner(name)()
        except Exception as exc:
            failures.append(f"{name}: {exc}")

    return results, failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Run dynamic simulation demos.")
    _ = parser.add_argument("--demo", choices=sorted(DEMO_TARGETS), default=None)
    _ = parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    selected_demo = cast(str | None, getattr(args, "demo"))
    emit_json = cast(bool, getattr(args, "as_json"))

    results, failures = run_all(selected=selected_demo)

    if emit_json:
        print(json.dumps({"results": results, "failures": failures}, indent=2, sort_keys=True))
    else:
        for demo_name, payload in results.items():
            print(f"=== {demo_name} ===")
            for key, value in payload.items():
                print(f"{key}={value}")
        if failures:
            print("=== failures ===")
            for failure in failures:
                print(failure)

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

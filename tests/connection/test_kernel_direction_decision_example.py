from __future__ import annotations

import importlib.abc
import importlib.util
from pathlib import Path


def _load_module_from_path(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    loader = spec.loader
    assert isinstance(loader, importlib.abc.Loader)

    import sys

    sys.modules[name] = module
    loader.exec_module(module)
    return module


ROOT = Path(__file__).resolve().parents[2]
decision_path = str(
    ROOT / "examples" / "connection_layer" / "benchmarks" / "kernel_direction_decision.py"
)
decision_module = _load_module_from_path("kernel_direction_decision", decision_path)


def test_run_kernel_direction_decision_returns_expected_top_level_keys() -> None:
    result = decision_module.run_kernel_direction_decision()

    assert isinstance(result, dict)
    assert set(result) == {
        "phase3_report",
        "decision",
        "migration_candidates",
        "roadmap_stages",
    }


def test_run_kernel_direction_decision_freezes_default_direction_and_first_escalation() -> None:
    result = decision_module.run_kernel_direction_decision()
    decision = result["decision"]

    assert decision["default_kernel_direction"] == "hybrid_coupled"
    assert decision["preserve_existing_facades"] is True
    assert decision["recommended_solver_stack"] in {"scipy", "sundials4py"}
    assert decision["recommended_solver_stack"] != "petsc4py"


def test_run_kernel_direction_decision_freezes_migration_candidate_matrix() -> None:
    result = decision_module.run_kernel_direction_decision()
    migration_candidates = result["migration_candidates"]

    assert isinstance(migration_candidates, list)
    assert [row["candidate_id"] for row in migration_candidates] == [
        "disciplined_scipy",
        "sundials4py",
        "petsc4py",
    ]
    for row in migration_candidates:
        assert set(row) == {
            "candidate_id",
            "stability_case",
            "latency_case",
            "deployment_risk",
            "compatibility",
            "phase3_workload_basis",
        }


def test_phase4_docs_freeze_workload_solver_and_facade_language() -> None:
    decision_doc = (ROOT / "docs" / "kernel_direction_decision.md").read_text()
    roadmap_doc = (ROOT / "docs" / "kernel_migration_roadmap.md").read_text()
    combined = decision_doc + "\n" + roadmap_doc

    for required_text in (
        "ammonia_recycle_warm",
        "staged_delay_control_disturbance",
        "checkpoint_restart_reconfigure",
        "disciplined_scipy",
        "sundials4py",
        "petsc4py",
        "PlantBackendSession",
        "CandidateKernelAdapter",
        "later escalation only if benchmarks justify it",
    ):
        assert required_text in combined

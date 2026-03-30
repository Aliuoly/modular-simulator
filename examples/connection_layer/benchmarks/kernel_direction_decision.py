"""Thin Phase 4 wrapper over the Phase 3 benchmark substrate."""

from __future__ import annotations

from dataclasses import asdict

from modular_simulation.connection.benchmarking import (
    KernelProfilingSummary,
    build_kernel_direction_decision,
)

from examples.connection_layer.benchmarks.macro_coupling_benchmark import run_benchmark


_PHASE3_WORKLOAD_BASIS = (
    "ammonia_recycle_warm",
    "staged_delay_control_disturbance",
    "checkpoint_restart_reconfigure",
)


def run_kernel_direction_decision() -> dict[str, object]:
    phase3_report = run_benchmark()
    decision = build_kernel_direction_decision(
        phase3_report,
        profiling_summary=KernelProfilingSummary(solver_core_fraction=None),
    )
    return {
        "phase3_report": phase3_report,
        "decision": asdict(decision),
        "migration_candidates": [
            {
                "candidate_id": "disciplined_scipy",
                "stability_case": "Stay on SciPy when the disciplined baseline clears Phase 3 hard gates without disqualification.",
                "latency_case": "Accept when representative workloads clear minimum_rtf_gate=4.0 and the latency budget fraction.",
                "deployment_risk": "Low because it preserves the current Python runtime and benchmark substrate.",
                "compatibility": "Highest compatibility with PlantBackendSession and the existing CandidateKernelAdapter seam.",
                "phase3_workload_basis": _PHASE3_WORKLOAD_BASIS,
            },
            {
                "candidate_id": "sundials4py",
                "stability_case": "First serious post-SciPy path when solver-core limits block the disciplined baseline on the Phase 3 canon.",
                "latency_case": "Escalate only after profiling shows solver_core_fraction >= 0.5 on representative workloads.",
                "deployment_risk": "Medium because it introduces a new solver binding while keeping a Python-native runtime.",
                "compatibility": "Good fit for preserving PlantBackendSession and CandidateKernelAdapter while swapping the kernel solver layer.",
                "phase3_workload_basis": _PHASE3_WORKLOAD_BASIS,
            },
            {
                "candidate_id": "petsc4py",
                "stability_case": "Later escalation only if benchmarks justify it after both disciplined SciPy and sundials4py remain insufficient.",
                "latency_case": "Reserve for sparse nonlinear solves that need PETSc-level solver composition and preconditioning.",
                "deployment_risk": "High because PETSc adds substantial packaging, operational, and mental-model complexity.",
                "compatibility": "Lower compatibility than sundials4py, so preserve PlantBackendSession and CandidateKernelAdapter as explicit migration seams.",
                "phase3_workload_basis": _PHASE3_WORKLOAD_BASIS,
            },
        ],
        "roadmap_stages": [
            "disciplined_scipy_hardening",
            "hybrid_coupled_default_direction",
            "sundials4py_adapter_spike",
            "petsc4py_later_if_justified",
        ],
    }


__all__ = ["run_kernel_direction_decision"]

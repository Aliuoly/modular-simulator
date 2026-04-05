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
        ],
        "roadmap_stages": [
            "disciplined_scipy_hardening",
            "hybrid_coupled_default_direction",
        ],
    }


__all__ = ["run_kernel_direction_decision"]

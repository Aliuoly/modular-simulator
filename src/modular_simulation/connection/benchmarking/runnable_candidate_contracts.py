from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from modular_simulation.connection.benchmarking.contracts import (
    BenchmarkCandidateConfig,
    BenchmarkWorkloadDefinition,
)


@dataclass(frozen=True)
class RunnableCandidateDefinition:
    candidate_id: str
    candidate_label: str
    candidate_family: str
    implementation_binding: str


PHASE5_RUNNABLE_CANDIDATES: tuple[RunnableCandidateDefinition, ...] = (
    RunnableCandidateDefinition(
        candidate_id="disciplined_split",
        candidate_label="Disciplined split baseline",
        candidate_family="split_baseline",
        implementation_binding="split_kernel_adapter",
    ),
    RunnableCandidateDefinition(
        candidate_id="sundials4py",
        candidate_label="SUNDIALS-backed candidate",
        candidate_family="sundials",
        implementation_binding="scikits.odes.ida",
    ),
    RunnableCandidateDefinition(
        candidate_id="petsc4py",
        candidate_label="PETSc-backed candidate",
        candidate_family="petsc",
        implementation_binding="petsc4py.PETSc.SNES",
    ),
)

PHASE5_RUNNABLE_CANDIDATE_ORDER: tuple[str, ...] = tuple(
    definition.candidate_id for definition in PHASE5_RUNNABLE_CANDIDATES
)


def build_phase5_candidate_configs(
    workloads: Iterable[BenchmarkWorkloadDefinition],
) -> tuple[BenchmarkCandidateConfig, ...]:
    configs: list[BenchmarkCandidateConfig] = []
    for workload in workloads:
        for definition in PHASE5_RUNNABLE_CANDIDATES:
            configs.append(
                BenchmarkCandidateConfig(
                    candidate_id=definition.candidate_id,
                    candidate_label=definition.candidate_label,
                    checkpoint_id=workload.checkpoint_id,
                    tolerance_profile=workload.tolerance_profile,
                    physical_acceptance_profile=workload.physical_acceptance_profile,
                    telemetry_contract_version=workload.telemetry_contract_version,
                    delay_semantics_label=workload.delay_semantics_label,
                    candidate_family=definition.candidate_family,
                )
            )
    return tuple(configs)


__all__ = [
    "PHASE5_RUNNABLE_CANDIDATES",
    "PHASE5_RUNNABLE_CANDIDATE_ORDER",
    "RunnableCandidateDefinition",
    "build_phase5_candidate_configs",
]

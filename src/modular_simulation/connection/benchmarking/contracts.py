from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class BenchmarkScenarioTag(StrEnum):
    WARM_RUN = "warm_run"
    DISTURBANCE = "disturbance"
    RECYCLE_HEAVY = "recycle_heavy"
    CONTROLLER_NETWORK_COUPLING = "controller_network_coupling"
    RESTART_RECONFIGURATION = "restart_reconfiguration"
    DELAY_HEAVY = "delay_heavy"


class BenchmarkDisqualificationReason(StrEnum):
    FALLBACK_USED = "fallback_used"
    PHYSICAL_ACCEPTANCE_FAILURE = "physical_acceptance_failure"
    HIDDEN_SOLVER_FAILURE = "hidden_solver_failure"
    CLIPPING_MASKED_APPARENT_STABILITY = "clipping_masked_apparent_stability"
    HIDDEN_RECOVERY = "hidden_recovery"
    TELEMETRY_CONTRACT_VIOLATION = "telemetry_contract_violation"


@dataclass(frozen=True)
class BenchmarkLatencyBudget:
    headline_rtf_target: float = 100.0
    minimum_rtf_gate: float = 4.0
    accepted_step_p95_fraction_of_step_size: float = 0.25
    use_accepted_steps_only_for_latency_gate: bool = True


@dataclass(frozen=True)
class BenchmarkWorkloadDefinition:
    workload_id: str
    checkpoint_id: str
    tolerance_profile: str
    physical_acceptance_profile: str
    telemetry_contract_version: str
    delay_semantics_label: str
    scenario_tags: tuple[BenchmarkScenarioTag, ...] = ()
    latency_budget: BenchmarkLatencyBudget = field(default_factory=BenchmarkLatencyBudget)
    description: str | None = None


@dataclass(frozen=True)
class BenchmarkCandidateConfig:
    candidate_id: str
    candidate_label: str
    checkpoint_id: str
    tolerance_profile: str
    physical_acceptance_profile: str
    telemetry_contract_version: str
    delay_semantics_label: str
    candidate_family: str | None = None


@dataclass(frozen=True)
class BenchmarkAttemptRecord:
    workload_id: str
    candidate_id: str
    checkpoint_id: str
    tolerance_profile: str
    physical_acceptance_profile: str
    telemetry_contract_version: str
    delay_semantics_label: str
    attempt_outcome: str
    macro_step_index: int
    macro_step_time_s: float
    simulation_time_s: float
    wall_clock_elapsed_s: float
    replay_hash: str
    graph_revision: str | None
    transport_fallback_keys: tuple[str, ...] = ()
    junction_fallback_keys: tuple[str, ...] = ()
    used_fallback: bool = False
    picard_iterations_used: int = 0
    picard_converged: bool = True
    picard_last_residual: float | None = None
    disqualification_reasons: tuple[BenchmarkDisqualificationReason, ...] = ()
    details: str | None = None


@dataclass(frozen=True)
class BenchmarkSummaryRow:
    workload_id: str
    candidate_id: str
    checkpoint_id: str
    tolerance_profile: str
    physical_acceptance_profile: str
    telemetry_contract_version: str
    delay_semantics_label: str
    accepted_attempt_count: int
    rejected_attempt_count: int
    disqualification_reasons: tuple[BenchmarkDisqualificationReason, ...] = ()


__all__ = [
    "BenchmarkAttemptRecord",
    "BenchmarkCandidateConfig",
    "BenchmarkDisqualificationReason",
    "BenchmarkLatencyBudget",
    "BenchmarkScenarioTag",
    "BenchmarkSummaryRow",
    "BenchmarkWorkloadDefinition",
]

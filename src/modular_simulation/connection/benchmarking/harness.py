from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from time import perf_counter

from modular_simulation.connection.benchmarking.contracts import (
    BenchmarkAttemptRecord,
    BenchmarkCandidateConfig,
    BenchmarkDisqualificationReason,
    BenchmarkLatencyBudget,
    BenchmarkWorkloadDefinition,
)
from modular_simulation.connection.benchmarking.telemetry import build_benchmark_attempt_record
from modular_simulation.connection.benchmarking.workloads import BenchmarkCheckpointSeed
from modular_simulation.connection.kernel_adapter import KernelCandidateStepRequest
from modular_simulation.connection.runtime.runtime_persistence import runtime_replay_state_hash


@dataclass
class BenchmarkHarness:
    workload_definition: BenchmarkWorkloadDefinition
    candidate_config: BenchmarkCandidateConfig
    candidate_adapter_factory: Callable[[BenchmarkCheckpointSeed], object]
    latency_budget: BenchmarkLatencyBudget
    macro_step_count: int = 1

    def run(self) -> tuple[BenchmarkAttemptRecord, ...]:
        self._validate_shared_fairness_contract()
        seed = self._build_seed()
        adapter = self.candidate_adapter_factory(seed)

        initialize = getattr(adapter, "initialize")
        initialize(
            type("InitRequest", (), {"accepted_snapshot": seed.checkpoint, "metadata": {}})()
        )

        attempt_records: list[BenchmarkAttemptRecord] = []
        for _ in range(self.macro_step_count):
            step_request = KernelCandidateStepRequest(macro_step_time_s=seed.macro_step_time_s)
            started = perf_counter()
            step_result = adapter.evaluate_candidate_step(step_request)
            elapsed = perf_counter() - started
            attempt_records.append(
                build_benchmark_attempt_record(
                    candidate_step_result=step_result,
                    wall_clock_elapsed_s=elapsed,
                    replay_hash=_build_replay_hash(adapter=adapter, seed=seed),
                    workload_definition=self.workload_definition,
                    candidate_config=self.candidate_config,
                    disqualification_reasons=_disqualification_reasons(step_result=step_result),
                )
            )
        return tuple(attempt_records)

    def _build_seed(self) -> BenchmarkCheckpointSeed:
        checkpoint_builder = self.workload_definition.checkpoint_builder
        if checkpoint_builder is None:
            raise ValueError(
                f"workload {self.workload_definition.workload_id!r} is missing a checkpoint builder"
            )
        seed = checkpoint_builder()
        seed.session.load_checkpoint(seed.checkpoint)
        return seed

    def _validate_shared_fairness_contract(self) -> None:
        expected = (
            self.workload_definition.checkpoint_id,
            self.workload_definition.tolerance_profile,
            self.workload_definition.physical_acceptance_profile,
            self.workload_definition.telemetry_contract_version,
            self.workload_definition.delay_semantics_label,
        )
        candidate = (
            self.candidate_config.checkpoint_id,
            self.candidate_config.tolerance_profile,
            self.candidate_config.physical_acceptance_profile,
            self.candidate_config.telemetry_contract_version,
            self.candidate_config.delay_semantics_label,
        )
        if candidate != expected:
            raise ValueError("candidate and workload must share the shared fairness contract")


def run_candidate_workload(
    *,
    workload_definition: BenchmarkWorkloadDefinition,
    candidate_config: BenchmarkCandidateConfig,
    candidate_adapter_factory: Callable[[BenchmarkCheckpointSeed], object],
    latency_budget: BenchmarkLatencyBudget,
    macro_step_count: int = 1,
) -> tuple[BenchmarkAttemptRecord, ...]:
    harness = BenchmarkHarness(
        workload_definition=workload_definition,
        candidate_config=candidate_config,
        candidate_adapter_factory=candidate_adapter_factory,
        latency_budget=latency_budget,
        macro_step_count=macro_step_count,
    )
    return harness.run()


def benchmark_attempt_records_to_dicts(
    attempt_records: tuple[BenchmarkAttemptRecord, ...] | list[BenchmarkAttemptRecord],
) -> list[dict[str, object]]:
    return [
        {
            **asdict(record),
            "disqualification_reasons": [
                reason.value for reason in record.disqualification_reasons
            ],
        }
        for record in attempt_records
    ]


def _build_replay_hash(*, adapter: object, seed: BenchmarkCheckpointSeed) -> str:
    runtime_orchestrator = getattr(adapter, "runtime_orchestrator", None)
    network = getattr(adapter, "network", getattr(seed.session, "network", None))
    process_state = _capture_process_runtime_state(adapter)
    if runtime_orchestrator is None or network is None:
        return (
            f"{seed.workload_id}:{seed.checkpoint_id}:{len(process_state)}:{seed.macro_step_time_s}"
        )
    try:
        tick = getattr(runtime_orchestrator, "macro_step_index", 0)
        return runtime_replay_state_hash(
            tick=tick,
            runtime=runtime_orchestrator,
            network=network,
            process_runtime_state=process_state,
        )
    except Exception:
        return (
            f"{seed.workload_id}:{seed.checkpoint_id}:{len(process_state)}:{seed.macro_step_time_s}"
        )


def _capture_process_runtime_state(adapter: object) -> Mapping[str, object]:
    capture = getattr(adapter, "capture_process_runtime_state", None)
    if callable(capture):
        payload = capture()
        if isinstance(payload, Mapping):
            return payload
    return {}


def _disqualification_reasons(
    *, step_result: object
) -> tuple[BenchmarkDisqualificationReason, ...]:
    telemetry = getattr(step_result, "telemetry", None)
    if telemetry is not None and getattr(telemetry, "used_fallback", False):
        return (BenchmarkDisqualificationReason.FALLBACK_USED,)
    return ()


__all__ = [
    "BenchmarkHarness",
    "benchmark_attempt_records_to_dicts",
    "run_candidate_workload",
]

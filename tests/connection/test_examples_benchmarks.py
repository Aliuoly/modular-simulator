import math

import importlib.abc
import importlib.util
from pathlib import Path
from types import SimpleNamespace

from modular_simulation.connection.benchmarking.contracts import (
    BenchmarkAttemptRecord,
    BenchmarkCandidateConfig,
    BenchmarkDisqualificationReason,
    BenchmarkLatencyBudget,
)
from modular_simulation.connection.kernel_adapter import (
    KernelAdapterTelemetry,
    KernelCandidateStepResult,
)
from modular_simulation.connection.topology.network import ConnectionNetwork


def _load_module_from_path(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    loader = spec.loader
    assert isinstance(loader, importlib.abc.Loader)
    # Ensure the module is present in sys.modules before executing code that
    # may reference its __name__ for dataclass construction
    import sys

    sys.modules[name] = module
    loader.exec_module(module)
    return module


ROOT = Path(__file__).resolve().parents[2]
split_path = str(ROOT / "examples" / "connection_layer" / "split_reversal_demo.py")
bench_path = str(
    ROOT / "examples" / "connection_layer" / "benchmarks" / "macro_coupling_benchmark.py"
)

split_module = _load_module_from_path("split_reversal_demo", split_path)
bench_module = _load_module_from_path("macro_coupling_benchmark", bench_path)


def test_split_reversal_demo_run_demo_structure():
    results = split_module.run_demo()
    assert isinstance(results, list)
    assert len(results) >= 1
    for item in results:
        assert isinstance(item, tuple)
        assert len(item) == 2
        name, value = item
        assert isinstance(name, str)
        assert isinstance(value, float)
        # Deterministic numeric values should be finite
        assert math.isfinite(value)


def test_macro_coupling_benchmark_run_benchmark_shape():
    result = bench_module.run_benchmark()
    assert isinstance(result, dict)
    # Required keys
    for key in (
        "candidate_rankings",
        "disqualified_candidates",
        "coverage_matrix",
        "headline_rtf_target",
        "minimum_rtf_gate",
        "latency_budget_fraction",
    ):
        assert key in result


def test_macro_coupling_benchmark_wrapper_uses_phase3_harness():
    result = bench_module.run_benchmark()

    assert result["headline_rtf_target"] == 100.0
    assert result["minimum_rtf_gate"] == 4.0
    assert result["latency_budget_fraction"] == 0.25
    assert result["coverage_matrix"][0]["checkpoint_id"].startswith("phase3-")


def test_macro_coupling_benchmark_returns_ranked_and_disqualified_sections():
    result = bench_module.run_benchmark()

    for key in (
        "candidate_rankings",
        "disqualified_candidates",
        "coverage_matrix",
        "headline_rtf_target",
        "minimum_rtf_gate",
        "latency_budget_fraction",
    ):
        assert key in result
    assert isinstance(result["candidate_rankings"], list)
    assert isinstance(result["disqualified_candidates"], list)
    assert {
        row["candidate_id"]
        for row in (*result["candidate_rankings"], *result["disqualified_candidates"])
    } == {"disciplined_split"}


def test_macro_coupling_benchmark_includes_per_workload_rows():
    result = bench_module.run_benchmark()

    assert "candidate_workloads" in result
    for candidate_id in ("disciplined_split",):
        assert candidate_id in result["candidate_workloads"]
        assert len(result["candidate_workloads"][candidate_id]) == 3
        assert {row["workload_id"] for row in result["candidate_workloads"][candidate_id]} == {
            "ammonia_recycle_warm",
            "staged_delay_control_disturbance",
            "checkpoint_restart_reconfigure",
        }


def test_macro_coupling_benchmark_reports_all_phase5_candidate_sections(monkeypatch):
    calls: list[tuple[str, str]] = []

    class _FakeNetwork:
        def _build_kernel_adapter(self):
            calls.append(("split_builder", "disciplined_split"))
            return SimpleNamespace(kind="disciplined_split")

    class _FakeHarness:
        def __init__(
            self,
            *,
            workload_definition,
            candidate_config,
            candidate_adapter_factory,
            latency_budget,
        ):
            self.workload_definition = workload_definition
            self.candidate_config = candidate_config
            self.candidate_adapter_factory = candidate_adapter_factory
            self.latency_budget = latency_budget

        def run(self):
            del self.latency_budget
            seed = SimpleNamespace(
                workload_id=self.workload_definition.workload_id,
                checkpoint_id=self.workload_definition.checkpoint_id,
                macro_step_time_s=1.0,
                session=SimpleNamespace(network=_FakeNetwork()),
            )
            adapter = self.candidate_adapter_factory(seed)
            calls.append((self.candidate_config.candidate_id, adapter.kind))
            return (
                BenchmarkAttemptRecord(
                    workload_id=self.workload_definition.workload_id,
                    candidate_id=self.candidate_config.candidate_id,
                    checkpoint_id=self.workload_definition.checkpoint_id,
                    tolerance_profile=self.workload_definition.tolerance_profile,
                    physical_acceptance_profile=self.workload_definition.physical_acceptance_profile,
                    telemetry_contract_version=self.workload_definition.telemetry_contract_version,
                    delay_semantics_label=self.workload_definition.delay_semantics_label,
                    attempt_outcome="accepted",
                    macro_step_index=1,
                    macro_step_time_s=1.0,
                    simulation_time_s=1.0,
                    wall_clock_elapsed_s=0.02,
                    replay_hash=f"{self.candidate_config.candidate_id}:{self.workload_definition.workload_id}",
                    graph_revision="graph_1",
                    residual_eval_cost_s=0.001,
                    jacobian_eval_cost_s=0.002,
                    linear_solve_cost_s=0.003,
                ),
            )

    monkeypatch.setattr(bench_module, "BenchmarkHarness", _FakeHarness)
    monkeypatch.setattr(bench_module, "BenchmarkLatencyBudget", BenchmarkLatencyBudget)

    result = bench_module.run_benchmark()

    assert set(result["candidate_workloads"]) == {"disciplined_split"}
    assert {row["candidate_id"] for row in result["candidate_rankings"]} == {"disciplined_split"}
    assert result["disqualified_candidates"] == []
    assert ("split_builder", "disciplined_split") in calls
    assert calls.count(("split_builder", "disciplined_split")) == 3


def test_macro_coupling_benchmark_uses_network_kernel_adapter_path(monkeypatch):
    original_builder = ConnectionNetwork._build_kernel_adapter
    calls: list[str] = []

    class _FakeAdapter:
        def __init__(self, network: object) -> None:
            self.network = network
            self.telemetry = KernelAdapterTelemetry(
                macro_step_index=0,
                macro_step_time_s=0.0,
                simulation_time_s=0.0,
                graph_revision="graph_0",
                executed_sequence=(),
                transport_fallback_keys=(),
                junction_fallback_keys=(),
                used_fallback=False,
                residual_eval_cost_s=0.001,
                jacobian_eval_cost_s=0.002,
                linear_solve_cost_s=0.003,
            )

        def initialize(self, request):
            del request
            return SimpleNamespace(initialized=True, graph_revision="graph_0")

        def warm_start(self, request):
            del request
            return SimpleNamespace(restored=True, graph_revision="graph_0")

        def evaluate_candidate_step(self, request):
            self.telemetry = KernelAdapterTelemetry(
                macro_step_index=1,
                macro_step_time_s=request.macro_step_time_s,
                simulation_time_s=request.macro_step_time_s,
                graph_revision="graph_1",
                executed_sequence=("candidate_step",),
                transport_fallback_keys=(),
                junction_fallback_keys=(),
                used_fallback=False,
                residual_eval_cost_s=0.001,
                jacobian_eval_cost_s=0.002,
                linear_solve_cost_s=0.003,
            )
            return KernelCandidateStepResult(
                accepted=True,
                graph_revision="graph_1",
                telemetry=self.telemetry,
                details="accepted",
            )

        def capture_process_runtime_state(self):
            return {}

    def _fake_builder(self):
        calls.append("called")
        return _FakeAdapter(self)

    ConnectionNetwork._build_kernel_adapter = _fake_builder
    try:
        result = bench_module.run_benchmark()
    finally:
        ConnectionNetwork._build_kernel_adapter = original_builder

    assert len(calls) >= 3
    assert "disciplined_split" in result["candidate_workloads"]


def test_macro_coupling_benchmark_preserves_candidate_configs_for_fixed_canon(monkeypatch):
    seen_candidate_configs: list[BenchmarkCandidateConfig] = []

    class _FakeHarness:
        def __init__(
            self,
            *,
            workload_definition,
            candidate_config,
            candidate_adapter_factory,
            latency_budget,
        ):
            del candidate_adapter_factory, latency_budget
            self.workload_definition = workload_definition
            self.candidate_config = candidate_config

        def run(self):
            seen_candidate_configs.append(self.candidate_config)
            return (
                BenchmarkAttemptRecord(
                    workload_id=self.workload_definition.workload_id,
                    candidate_id=self.candidate_config.candidate_id,
                    checkpoint_id=self.workload_definition.checkpoint_id,
                    tolerance_profile=self.workload_definition.tolerance_profile,
                    physical_acceptance_profile=self.workload_definition.physical_acceptance_profile,
                    telemetry_contract_version=self.workload_definition.telemetry_contract_version,
                    delay_semantics_label=self.workload_definition.delay_semantics_label,
                    attempt_outcome="accepted",
                    macro_step_index=1,
                    macro_step_time_s=1.0,
                    simulation_time_s=1.0,
                    wall_clock_elapsed_s=0.01,
                    replay_hash=f"{self.candidate_config.candidate_id}:{self.workload_definition.workload_id}",
                    graph_revision="graph_1",
                    residual_eval_cost_s=0.001,
                    jacobian_eval_cost_s=0.001,
                    linear_solve_cost_s=0.001,
                ),
            )

    monkeypatch.setattr(bench_module, "BenchmarkHarness", _FakeHarness)

    bench_module.run_benchmark()

    assert len(seen_candidate_configs) == 3
    assert {config.candidate_id for config in seen_candidate_configs} == {"disciplined_split"}
    assert {config.checkpoint_id for config in seen_candidate_configs} == {
        "phase3-ammonia-recycle-warm-checkpoint",
        "phase3-staged-delay-control-checkpoint",
        "phase3-restart-reconfigure-checkpoint",
    }


def test_smoke_integration_imports():
    # Ensure both modules load and expose expected callables without error
    demo = split_module.run_demo()
    bench = bench_module.run_benchmark()
    assert isinstance(demo, list)
    assert isinstance(bench, dict)

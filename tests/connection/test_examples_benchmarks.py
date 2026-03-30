import math

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
    assert result["candidate_rankings"][0]["candidate_id"] == "disciplined_split"


def test_smoke_integration_imports():
    # Ensure both modules load and expose expected callables without error
    demo = split_module.run_demo()
    bench = bench_module.run_benchmark()
    assert isinstance(demo, list)
    assert isinstance(bench, dict)

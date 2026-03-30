from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from modular_simulation.connection.benchmarking.workloads import build_phase3_workloads


EXPECTED_CANDIDATE_ORDER = ("disciplined_split", "sundials4py", "petsc4py")
EXPECTED_BINDINGS = {
    "disciplined_split": "split_kernel_adapter",
    "sundials4py": "scikits.odes.ida",
    "petsc4py": "petsc4py.PETSc.SNES",
}
EXPECTED_DEPENDENCIES = ("scikits.odes", "petsc", "petsc4py")


def _load_contract_module():
    try:
        return importlib.import_module(
            "modular_simulation.connection.benchmarking.runnable_candidate_contracts"
        )
    except ModuleNotFoundError as exc:  # pragma: no cover - RED-phase failure path
        pytest.fail(
            "Phase 5 runnable candidate contract module is missing: "
            "modular_simulation.connection.benchmarking.runnable_candidate_contracts"
        )


def test_phase5_candidate_order_is_hard_coded() -> None:
    contract_module = _load_contract_module()

    assert contract_module.PHASE5_RUNNABLE_CANDIDATE_ORDER == EXPECTED_CANDIDATE_ORDER


def test_phase5_candidate_bindings_are_truthful() -> None:
    contract_module = _load_contract_module()
    definitions = {item.candidate_id: item for item in contract_module.PHASE5_RUNNABLE_CANDIDATES}

    assert tuple(definitions) == EXPECTED_CANDIDATE_ORDER
    assert {
        candidate_id: definition.implementation_binding
        for candidate_id, definition in definitions.items()
    } == EXPECTED_BINDINGS


def test_build_phase5_candidate_configs_copies_workload_fairness_fields() -> None:
    contract_module = _load_contract_module()
    workloads = build_phase3_workloads()

    candidate_configs = contract_module.build_phase5_candidate_configs(workloads)

    assert len(candidate_configs) == len(workloads) * len(EXPECTED_CANDIDATE_ORDER)
    for workload_index, workload in enumerate(workloads):
        start = workload_index * len(EXPECTED_CANDIDATE_ORDER)
        end = start + len(EXPECTED_CANDIDATE_ORDER)
        workload_configs = candidate_configs[start:end]
        assert tuple(config.candidate_id for config in workload_configs) == EXPECTED_CANDIDATE_ORDER
        for config in workload_configs:
            assert config.checkpoint_id == workload.checkpoint_id
            assert config.tolerance_profile == workload.tolerance_profile
            assert config.physical_acceptance_profile == workload.physical_acceptance_profile
            assert config.telemetry_contract_version == workload.telemetry_contract_version
            assert config.delay_semantics_label == workload.delay_semantics_label


def test_pyproject_declares_phase5_solver_dependencies() -> None:
    pyproject_text = Path("pyproject.toml").read_text(encoding="utf-8")

    for dependency_name in EXPECTED_DEPENDENCIES:
        assert f'"{dependency_name}"' in pyproject_text

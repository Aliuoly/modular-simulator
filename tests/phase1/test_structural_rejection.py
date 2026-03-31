from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pytest

from modular_simulation.connection.domain.error_catalog import extract_diagnostic_payload
from modular_simulation.connection.domain.phase1_failure_semantics import (
    FailureFamily,
    ScenarioClass,
    StructuralPreStepRejection,
)
from modular_simulation.connection.hydraulics.hydraulic_compile import HydraulicCompileLifecycle
from modular_simulation.connection.hydraulics.hydraulic_solver import (
    HydraulicSystemDefinition,
    HydraulicSolveResult,
    LinearResidualEquation,
)
from modular_simulation.connection.runtime.connected_plant_orchestrator import (
    ConnectedPlantOrchestrator,
)
from modular_simulation.connection.runtime.connection_layer import TransportAndMixingUpdate
from modular_simulation.connection.runtime.runtime import ConnectionRuntimeOrchestrator
from modular_simulation.connection.topology.network import ConnectionNetwork
from modular_simulation.connection.topology.subsystem_descriptor import SubsystemRuntimeDescriptor


def _linear_equation(
    residual_name: str,
    coefficients: dict[str, float],
    *,
    constant: float = 0.0,
) -> LinearResidualEquation:
    return LinearResidualEquation(
        residual_name=residual_name,
        coefficients=coefficients,
        constant=constant,
    )


def _hydraulic_result() -> HydraulicSolveResult:
    return HydraulicSolveResult(
        converged=True,
        iterations=1,
        residual_norm=1.0e-10,
        solution_vector=np.asarray([1.0, 5.0], dtype=np.float64),
        unknowns={"flow": 1.0, "pressure": 5.0},
        unknown_index_map={"flow": 0, "pressure": 1},
        residual_index_map={"balance": 0, "ref": 1},
    )


@dataclass
class _FakeSubsystem:
    descriptor: SubsystemRuntimeDescriptor
    calls: list[str]

    def run_sensor_phase(self) -> None:
        self.calls.append("sensor")

    def run_calculation_phase(self) -> None:
        self.calls.append("calculation")

    def run_controller_phase(self) -> None:
        self.calls.append("controller")

    def run_process_phase(self, duration: float) -> None:
        del duration
        self.calls.append("process")

    def snapshot_published_measurements(self) -> dict[str, float]:
        return {"temperature": 300.0}


def _network(
    *,
    hydraulic_system_builder: Callable[[object], HydraulicSystemDefinition] | None = None,
    runtime: ConnectionRuntimeOrchestrator | None = None,
    transport_calls: list[str] | None = None,
    boundary_calls: list[str] | None = None,
) -> ConnectionNetwork:
    compile_count = {"count": 0}

    def _builder(topology: object) -> HydraulicSystemDefinition:
        compile_count["count"] += 1
        if hydraulic_system_builder is None or compile_count["count"] == 1:
            return HydraulicSystemDefinition(
                equations=(),
                linear_residual_equations=(
                    _linear_equation("ref", {"pressure": 1.0}, constant=-5.0),
                    _linear_equation("balance", {"pressure": 1.0, "flow": -1.0}),
                ),
            )
        return hydraulic_system_builder(topology)

    if runtime is None:

        def _transport_step(*, network, hydraulic_result, macro_step_time_s):
            del network, hydraulic_result, macro_step_time_s
            if transport_calls is None:
                pytest.fail("transport update must not run for structural pre-step rejections")
            transport_calls.append("transport")
            return TransportAndMixingUpdate(transport_results={})

        def _boundary_step(
            *, network, hydraulic_result, transport_and_mixing_update, macro_step_time_s
        ):
            del network, hydraulic_result, transport_and_mixing_update, macro_step_time_s
            if boundary_calls is None:
                pytest.fail("boundary propagation must not run for structural pre-step rejections")
            boundary_calls.append("boundary")
            return {}

        runtime = ConnectionRuntimeOrchestrator(
            hydraulic_solve_step=(
                None
                if hydraulic_system_builder is not None
                else lambda *, network, macro_step_time_s: _hydraulic_result()
            ),
            transport_and_mixing_step=_transport_step,
            boundary_propagation_step=_boundary_step,
        )
    network = ConnectionNetwork(
        compile_lifecycle=(
            HydraulicCompileLifecycle() if hydraulic_system_builder is not None else None
        ),
        hydraulic_system_builder=(_builder if hydraulic_system_builder is not None else None),
        runtime_orchestrator=runtime,
    )
    network.add_process("reactor", inlet_ports=("feed",), outlet_ports=("product",))
    network.add_boundary_source("feed_boundary")
    network.add_boundary_sink("product_boundary")
    _ = network.connect("feed_boundary", "reactor.feed")
    _ = network.connect("reactor.product", "product_boundary")
    _ = network.compile()
    return network


def _subsystem(calls: list[str]) -> _FakeSubsystem:
    return _FakeSubsystem(
        descriptor=SubsystemRuntimeDescriptor(
            descriptor_id="subsystem_runtime",
            process_id="reactor",
            inlet_ports=("feed",),
            outlet_ports=("product",),
            publication_map={"temperature": 300.0},
        ),
        calls=calls,
    )


def _missing_anchor_system(_: object) -> HydraulicSystemDefinition:
    return HydraulicSystemDefinition(
        equations=(),
        linear_residual_equations=(
            _linear_equation("pressure_balance", {"pressure": 1.0, "flow": -1.0}),
            _linear_equation("flow_balance", {"flow": 1.0}),
        ),
    )


def _dof_mismatch_system(_: object) -> HydraulicSystemDefinition:
    return HydraulicSystemDefinition(
        equations=(),
        linear_residual_equations=(
            _linear_equation("pressure_balance", {"pressure": 1.0, "flow": -1.0}),
        ),
    )


def _singular_system(_: object) -> HydraulicSystemDefinition:
    return HydraulicSystemDefinition(
        equations=(),
        linear_residual_equations=(
            _linear_equation("pressure_ref", {"pressure": 1.0}, constant=-5.0),
            _linear_equation("dependent_balance", {"pressure": 1.0, "flow": 0.0}),
        ),
    )


def test_kern_03_structural_rejection_uses_pre_step_structural_family_only(
    phase1_scenario_manifest,
) -> None:
    scenario = next(
        row
        for row in phase1_scenario_manifest
        if row.scenario_class is ScenarioClass.RUNTIME_EDIT_OR_RESTART
    )

    rejection = StructuralPreStepRejection(
        scenario=scenario,
        rejection_family=FailureFamily.STRUCTURAL_INCONSISTENCY,
        rejection_code="HYDRAULIC_STRUCTURE_REJECTED",
        rejection_message="compile barrier rejected an inconsistent hydraulic structure",
    )

    assert rejection.rejection_family is FailureFamily.STRUCTURAL_INCONSISTENCY
    assert rejection.process_phases_entered == ()


def test_kern_03_structural_rejection_blocks_process_phase_entry(
    phase1_scenario_manifest,
) -> None:
    scenario = next(
        row
        for row in phase1_scenario_manifest
        if row.scenario_class is ScenarioClass.RUNTIME_EDIT_OR_RESTART
    )

    with pytest.raises(
        ValueError,
        match="structural pre-step rejection cannot record subsystem process phase entry",
    ):
        StructuralPreStepRejection(
            scenario=scenario,
            rejection_family=FailureFamily.STRUCTURAL_INCONSISTENCY,
            rejection_code="COMPILE_FAILED",
            rejection_message="compile failed before stepping",
            process_phases_entered=("subsystem_process_step",),
        )


@pytest.mark.parametrize(
    ("hydraulic_system_builder", "expected_code", "expected_path", "message_fragment"),
    [
        (
            _missing_anchor_system,
            "STRUCTURAL_PRE_STEP_COMPILE_REJECTION",
            "compile",
            "missing pressure reference",
        ),
        (
            _dof_mismatch_system,
            "STRUCTURAL_PRE_STEP_COMPILE_REJECTION",
            "compile",
            "hydraulic system must be square for compile validation",
        ),
        (
            _singular_system,
            "STRUCTURAL_PRE_STEP_HYDRAULIC_REJECTION",
            "hydraulic.solve",
            "hydraulic Jacobian is singular or underdetermined",
        ),
    ],
)
def test_kern_03_hydraulic_structure_failures_use_explicit_pre_step_structural_payloads(
    hydraulic_system_builder: Callable[[object], HydraulicSystemDefinition],
    expected_code: str,
    expected_path: str,
    message_fragment: str,
) -> None:
    network = _network(hydraulic_system_builder=hydraulic_system_builder)
    _ = network.queue_reconfiguration(
        {
            "operation": "add_boundary_sink",
            "boundary_id": "purge_sink",
        }
    )

    with pytest.raises(RuntimeError) as error:
        _ = network.step(macro_step_time_s=0.25)

    payload = extract_diagnostic_payload(error.value)
    assert payload is not None
    assert payload["code"] == expected_code
    assert payload["path"] == expected_path
    assert payload["failure_family"] == "structural_inconsistency"
    assert payload["rejection_stage"] == "pre_step"
    assert message_fragment in str(payload["message"])


def test_kern_03_destructive_edit_invariant_failures_use_structural_pre_step_payloads() -> None:
    network = _network()
    _ = network.queue_reconfiguration(
        {
            "operation": "batch_update",
            "metadata": {
                "control_dependencies": {
                    "unit:reactor": ["controller:reactor_pid"],
                }
            },
            "mutations": [
                {
                    "operation": "remove_unit",
                    "process_id": "reactor",
                }
            ],
        }
    )

    with pytest.raises(RuntimeError) as error:
        _ = network.step(macro_step_time_s=0.25)

    payload = extract_diagnostic_payload(error.value)
    assert payload is not None
    assert payload["code"] == "STRUCTURAL_PRE_STEP_INVARIANT_REJECTION"
    assert payload["path"] == "metadata.destructive_edit_mode"
    assert payload["failure_family"] == "structural_inconsistency"
    assert payload["rejection_stage"] == "pre_step"
    assert payload["hint"] == (
        "remove or detach listed dependents first, or retry with "
        + "metadata.destructive_edit_mode='safe_detach'"
    )
    assert "DESTRUCTIVE_EDIT_DEPENDENTS" in str(payload["message"])
    assert '"target":"unit:reactor"' in str(payload["message"])


def test_kern_03_barrier_revision_failures_surface_structural_pre_step_payloads() -> None:
    network = _network()
    _ = network.queue_reconfiguration(
        {
            "operation": "add_boundary_sink",
            "boundary_id": "purge_sink",
            "expected_revision": "graph_rev_0999",
        }
    )

    with pytest.raises(RuntimeError) as error:
        _ = network.step(macro_step_time_s=0.25)

    payload = extract_diagnostic_payload(error.value)
    assert payload is not None
    assert payload["code"] == "STRUCTURAL_PRE_STEP_BARRIER_REJECTION"
    assert payload["path"] == "expected_revision"
    assert payload["hint"] == "retry with the current graph revision or omit expected_revision"
    assert payload["revision"] == {
        "expected": "graph_rev_0999",
        "actual": "graph_rev_0001",
    }


def test_kern_03_connected_plant_structural_rejection_blocks_process_transport_and_boundary() -> (
    None
):
    subsystem_calls: list[str] = []
    transport_calls: list[str] = []
    boundary_calls: list[str] = []
    network = _network(transport_calls=transport_calls, boundary_calls=boundary_calls)
    orchestrator = ConnectedPlantOrchestrator(
        subsystems=(_subsystem(subsystem_calls),),
        network=network,
        runtime_orchestrator=network._runtime_orchestrator,
    )
    _ = network.queue_reconfiguration(
        {
            "operation": "batch_update",
            "metadata": {
                "control_dependencies": {
                    "unit:reactor": ["controller:reactor_pid"],
                }
            },
            "mutations": [
                {
                    "operation": "remove_unit",
                    "process_id": "reactor",
                }
            ],
        }
    )

    with pytest.raises(RuntimeError) as error:
        _ = orchestrator.step(macro_step_time_s=0.25)

    payload = extract_diagnostic_payload(error.value)
    assert payload is not None
    assert payload["code"] == "STRUCTURAL_PRE_STEP_INVARIANT_REJECTION"
    assert subsystem_calls == []
    assert transport_calls == []
    assert boundary_calls == []


def test_kern_03_runtime_edit_restart_rejection_stays_at_barrier_after_resume() -> None:
    subsystem_calls: list[str] = []
    transport_calls: list[str] = []
    boundary_calls: list[str] = []
    runtime = ConnectionRuntimeOrchestrator(
        hydraulic_solve_step=lambda *, network, macro_step_time_s: _hydraulic_result(),
        transport_and_mixing_step=lambda *, network, hydraulic_result, macro_step_time_s: (
            transport_calls.append("transport") or TransportAndMixingUpdate(transport_results={})
        ),
        boundary_propagation_step=lambda *,
        network,
        hydraulic_result,
        transport_and_mixing_update,
        macro_step_time_s: (boundary_calls.append("boundary") or {}),
    )
    network = _network(runtime=runtime)
    checkpoint = network.save_runtime_snapshot()
    network.resume_from_snapshot(snapshot=checkpoint)
    orchestrator = ConnectedPlantOrchestrator(
        subsystems=(_subsystem(subsystem_calls),),
        network=network,
        runtime_orchestrator=runtime,
    )
    _ = network.queue_reconfiguration(
        {
            "operation": "batch_update",
            "metadata": {
                "control_dependencies": {
                    "unit:reactor": ["controller:restart_guard"],
                }
            },
            "mutations": [
                {
                    "operation": "remove_unit",
                    "process_id": "reactor",
                }
            ],
        }
    )

    with pytest.raises(RuntimeError) as error:
        _ = orchestrator.step(macro_step_time_s=0.25)

    payload = extract_diagnostic_payload(error.value)
    assert payload is not None
    assert payload["code"] == "STRUCTURAL_PRE_STEP_INVARIANT_REJECTION"
    assert payload["rejection_stage"] == "pre_step"
    assert network.queued_reconfigurations[0].request_id == "rq_0001"
    assert subsystem_calls == []
    assert transport_calls == []
    assert boundary_calls == []

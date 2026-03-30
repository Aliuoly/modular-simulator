from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import pytest

from modular_simulation.connection.kernel_adapter import (
    KernelDelaySemantics,
    KernelDelayStrategy,
    KernelOptionalCapability,
    KernelWarmStartRequest,
    KernelWarmStartResult,
)
from modular_simulation.connection.runtime.kernel_adapter_restore import (
    KernelWarmStartFailure,
    restore_kernel_from_snapshot,
)
from modular_simulation.connection.runtime.runtime_persistence import (
    save_runtime_snapshot_contract,
)
from modular_simulation.connection.runtime.runtime import ConnectionRuntimeOrchestrator
from modular_simulation.connection.topology.network import ConnectionNetwork
from modular_simulation.cli.backend_session import PlantBackendSession
from modular_simulation.connection.hydraulics.hydraulic_compile import HydraulicCompileLifecycle
from modular_simulation.connection.hydraulics.hydraulic_solver import (
    HydraulicSystemDefinition,
    LinearResidualEquation,
)


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


def _valid_system() -> HydraulicSystemDefinition:
    return HydraulicSystemDefinition(
        equations=(),
        linear_residual_equations=(
            _linear_equation("ref", {"pressure": 1.0}, constant=-5.0),
            _linear_equation("balance", {"pressure": 1.0, "flow": -1.0}),
        ),
    )


def _network(runtime: ConnectionRuntimeOrchestrator) -> ConnectionNetwork:
    network = ConnectionNetwork(
        compile_lifecycle=HydraulicCompileLifecycle(),
        hydraulic_system_builder=lambda topology: _valid_system(),
        runtime_orchestrator=runtime,
    )
    network.add_process("reactor", inlet_ports=("feed",), outlet_ports=("product",))
    network.add_boundary_source("feed_boundary")
    network.add_boundary_sink("product_boundary")
    network.connect("feed_boundary", "reactor.feed")
    network.connect("reactor.product", "product_boundary")
    _ = network.compile()
    return network


def _checkpoint_snapshot() -> Mapping[str, object]:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)
    return save_runtime_snapshot_contract(
        runtime=runtime,
        network=network,
        process_runtime_state={"reactor": {"temperature": 345.0}},
    )


@dataclass
class _RecordingAdapter:
    restored: bool = True
    details: str | None = None
    raise_error: Exception | None = None
    last_request: KernelWarmStartRequest | None = None
    capability_checks: int = 0

    @property
    def delay_semantics(self) -> KernelDelaySemantics:
        return KernelDelaySemantics(
            strategy=KernelDelayStrategy.EXTERNAL_TRANSPORT_HISTORY,
            state_schema="transport_runtime_state",
            preserves_existing_transport_history=True,
        )

    @property
    def telemetry(self) -> object:
        raise AssertionError("restore helper must not inspect telemetry for warm start")

    def initialize(self, request: object) -> object:
        raise AssertionError("restore helper must not initialize on warm-start restore")

    def warm_start(self, request: KernelWarmStartRequest) -> KernelWarmStartResult:
        self.last_request = request
        if self.raise_error is not None:
            raise self.raise_error
        graph_revision = request.accepted_snapshot.get("graph_revision")
        if graph_revision is not None and not isinstance(graph_revision, str):
            graph_revision = None
        return KernelWarmStartResult(
            restored=self.restored,
            graph_revision=graph_revision,
            details=self.details,
        )

    def evaluate_candidate_step(self, request: object) -> object:
        raise AssertionError("restore helper must not evaluate a step during warm start")

    def capture_delay_state(self) -> Mapping[str, object]:
        raise AssertionError("restore helper must not capture delay state during warm start")

    def restore_delay_state(self, payload: Mapping[str, object]) -> None:
        raise AssertionError("restore helper must not restore delay state separately")

    def supported_optional_capabilities(self) -> frozenset[KernelOptionalCapability]:
        self.capability_checks += 1
        raise AssertionError("restore helper must not require optional solver capabilities")


def test_restore_kernel_from_snapshot_uses_core_adapter_only() -> None:
    adapter = _RecordingAdapter()

    result = restore_kernel_from_snapshot(
        adapter=adapter,
        snapshot=_checkpoint_snapshot(),
        restore_reason="resume",
    )

    assert result.restored is True
    assert adapter.last_request is not None
    assert adapter.last_request.metadata == {"restore_reason": "resume"}
    assert adapter.last_request.accepted_snapshot["schema"] == "connection_runtime_v1"
    assert adapter.capability_checks == 0


def test_restore_kernel_from_snapshot_accepts_valid_checkpoint_snapshot() -> None:
    adapter = _RecordingAdapter()

    result = restore_kernel_from_snapshot(
        adapter=adapter,
        snapshot=_checkpoint_snapshot(),
        restore_reason="save_load",
    )

    assert result.restored is True
    assert result.graph_revision == "graph_rev_0001"
    assert adapter.last_request is not None
    assert adapter.last_request.accepted_snapshot["queued_request_count"] == 0


def test_restore_kernel_from_snapshot_rejects_unsafe_restore_without_cold_start() -> None:
    adapter = _RecordingAdapter()

    with pytest.raises(KernelWarmStartFailure) as excinfo:
        restore_kernel_from_snapshot(
            adapter=adapter,
            snapshot={"schema": "unsafe"},
            restore_reason="post_edit_recovery",
        )

    assert "post_edit_recovery" in str(excinfo.value)
    assert "invalid runtime snapshot payload" in excinfo.value.failure_reason
    assert adapter.last_request is None


def test_restore_kernel_from_snapshot_surfaces_adapter_failure_reason() -> None:
    adapter = _RecordingAdapter(restored=False, details="graph revision mismatch")

    with pytest.raises(KernelWarmStartFailure) as excinfo:
        restore_kernel_from_snapshot(
            adapter=adapter,
            snapshot=_checkpoint_snapshot(),
            restore_reason="save_load",
        )

    assert excinfo.value.failure_reason == "graph revision mismatch"


def test_backend_session_load_checkpoint_uses_canonical_restore_path() -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)
    session = PlantBackendSession(network=network)

    checkpoint = _checkpoint_snapshot()

    session.load_checkpoint(checkpoint)

    restored_snapshot = network.save_runtime_snapshot()
    assert restored_snapshot["graph_revision"] == checkpoint["graph_revision"]
    assert restored_snapshot["schema"] == "connection_runtime_v1"


def test_post_edit_recovery_uses_canonical_restore_reason() -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)

    checkpoint = _checkpoint_snapshot()

    network.recover_from_checkpoint_after_edit(snapshot=checkpoint)

    restored_snapshot = network.save_runtime_snapshot()
    assert restored_snapshot["graph_revision"] == checkpoint["graph_revision"]
    assert restored_snapshot["queued_request_count"] == 0

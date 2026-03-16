from __future__ import annotations

import pytest

from modular_simulation.connection.domain.error_catalog import (
    REVISION_MISMATCH_CODE,
    VALIDATION_FAILURE_CODE,
    extract_diagnostic_payload,
)
from modular_simulation.connection.hydraulics.hydraulic_compile import HydraulicCompileLifecycle
from modular_simulation.connection.hydraulics.hydraulic_solver import (
    HydraulicSystemDefinition,
    LinearResidualEquation,
)
from modular_simulation.connection.topology.network import ConnectionNetwork
from modular_simulation.connection.domain.reconfiguration_api import (
    DynamicConnectionLineReconfigurationApi,
)
from modular_simulation.connection.runtime.runtime import ConnectionRuntimeOrchestrator


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
    _ = network.connect("feed_boundary", "reactor.feed")
    _ = network.connect("reactor.product", "product_boundary")
    _ = network.compile()
    return network


def _assert_schema(payload: dict[str, object]) -> None:
    assert set(payload) >= {"code", "message", "path", "hint", "revision"}


def test_revision_mismatch_includes_expected_and_actual_revision_details() -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)

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
    _assert_schema(payload)
    assert payload["code"] == REVISION_MISMATCH_CODE
    assert payload["path"] == "expected_revision"
    assert payload["hint"] == "retry with the current graph revision or omit expected_revision"
    assert "expected_revision 'graph_rev_0999'" in str(payload["message"])
    assert payload["revision"] == {
        "expected": "graph_rev_0999",
        "actual": "graph_rev_0001",
    }


def test_invalid_endpoint_direction_uses_validation_failure_payload() -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)
    api = DynamicConnectionLineReconfigurationApi(network=network)

    _ = api.connect_line(
        source="reactor.feed",
        target="feed_boundary.outlet",
        line_id="line_invalid_direction",
    )

    with pytest.raises(RuntimeError) as error:
        _ = network.step(macro_step_time_s=0.25)

    payload = extract_diagnostic_payload(error.value)
    assert payload is not None
    _assert_schema(payload)
    assert payload["code"] == VALIDATION_FAILURE_CODE
    assert payload["path"] == "mutations[1]"

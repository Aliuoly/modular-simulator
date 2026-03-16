from __future__ import annotations

from collections.abc import Mapping

import pytest

from modular_simulation.cli import ModularCli
from modular_simulation.connection.domain.error_catalog import (
    CLI_ARGUMENT_ISSUE_CODE,
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


class _FakeCliNetwork:
    def queue_reconfiguration(self, request: object, /) -> str:
        del request
        return "rq-fake-001"

    def save_runtime_snapshot(self) -> Mapping[str, object]:
        return {}

    def resume_from_snapshot(self, *, snapshot: object) -> None:
        del snapshot


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


def _invalid_direction_payload_from_api() -> dict[str, object]:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)
    api = DynamicConnectionLineReconfigurationApi(network=network)
    _ = api.connect_line(
        source="reactor.feed",
        target="feed_boundary.outlet",
        line_id="line_invalid_direction_api",
    )
    with pytest.raises(RuntimeError) as error:
        _ = network.step(macro_step_time_s=0.25)
    payload = extract_diagnostic_payload(error.value)
    assert payload is not None
    return payload


def _invalid_direction_payload_from_cli() -> dict[str, object]:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)
    cli = ModularCli(network=network)
    _ = cli.connect(
        source="reactor.feed",
        target="feed_boundary.outlet",
        line_id="line_invalid_direction_cli",
    )
    with pytest.raises(RuntimeError) as error:
        _ = network.step(macro_step_time_s=0.25)
    payload = extract_diagnostic_payload(error.value)
    assert payload is not None
    return payload


def _revision_mismatch_payload_from_api() -> dict[str, object]:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)
    api = DynamicConnectionLineReconfigurationApi(network=network)
    _ = api.connect_line(
        source="feed_boundary.outlet",
        target="reactor.feed",
        line_id="line_revision_mismatch_api",
        expected_revision="graph_rev_9999",
    )
    with pytest.raises(RuntimeError) as error:
        _ = network.step(macro_step_time_s=0.25)
    payload = extract_diagnostic_payload(error.value)
    assert payload is not None
    return payload


def _revision_mismatch_payload_from_cli() -> dict[str, object]:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)
    cli = ModularCli(network=network)
    _ = cli.connect(
        source="feed_boundary.outlet",
        target="reactor.feed",
        line_id="line_revision_mismatch_cli",
        expected_revision="graph_rev_9999",
    )
    with pytest.raises(RuntimeError) as error:
        _ = network.step(macro_step_time_s=0.25)
    payload = extract_diagnostic_payload(error.value)
    assert payload is not None
    return payload


def test_api_and_cli_share_same_validation_code_for_invalid_endpoint_direction() -> None:
    api_payload = _invalid_direction_payload_from_api()
    cli_payload = _invalid_direction_payload_from_cli()

    _assert_schema(api_payload)
    _assert_schema(cli_payload)
    assert api_payload["code"] == VALIDATION_FAILURE_CODE
    assert cli_payload["code"] == api_payload["code"]


def test_api_and_cli_share_revision_mismatch_payload_contract() -> None:
    api_payload = _revision_mismatch_payload_from_api()
    cli_payload = _revision_mismatch_payload_from_cli()

    _assert_schema(api_payload)
    _assert_schema(cli_payload)
    assert api_payload["code"] == REVISION_MISMATCH_CODE
    assert cli_payload["code"] == api_payload["code"]
    assert cli_payload["path"] == api_payload["path"] == "expected_revision"
    assert (
        cli_payload["revision"]
        == api_payload["revision"]
        == {
            "expected": "graph_rev_9999",
            "actual": "graph_rev_0001",
        }
    )
    assert str(cli_payload["hint"]).startswith("retry")


def test_cli_argument_errors_use_cli_argument_issue_code() -> None:
    cli = ModularCli(network=_FakeCliNetwork())

    with pytest.raises(ValueError) as error:
        _ = cli.add_port(process_id="u1", port_id="p1", direction="invalid")

    payload = extract_diagnostic_payload(error.value)
    assert payload is not None
    _assert_schema(payload)
    assert payload["code"] == CLI_ARGUMENT_ISSUE_CODE
    assert payload["path"] == "direction"

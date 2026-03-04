from __future__ import annotations

from collections.abc import Mapping
import json
from pathlib import Path

import pytest

from modular_simulation.cli import ModularCli
from modular_simulation.cli.spec_workflow import SpecApplyError
from modular_simulation.connection.hydraulic_compile import HydraulicCompileLifecycle
from modular_simulation.connection.hydraulic_solver import (
    HydraulicSystemDefinition,
    LinearResidualEquation,
)
from modular_simulation.connection.network import ConnectionNetwork
from modular_simulation.connection.runtime import ConnectionRuntimeOrchestrator


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


def _write_spec(*, tmp_path: Path, payload: Mapping[str, object]) -> str:
    spec_path = tmp_path / "spec.json"
    _ = spec_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return str(spec_path)


def test_spec_diff_apply_happy_path_is_deterministic(tmp_path: Path) -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)
    cli = ModularCli(network=network)

    desired_spec = {
        "processes": [
            {
                "process_id": "reactor",
                "inlet_ports": ["feed"],
                "outlet_ports": ["product"],
            }
        ],
        "boundaries": [
            {"boundary_id": "product_boundary", "direction": "sink", "port_name": "inlet"},
            {"boundary_id": "feed_boundary_2", "direction": "source", "port_name": "outlet"},
        ],
        "lines": [
            {
                "line_id": "edge_0002",
                "source": "feed_boundary_2.outlet",
                "target": "product_boundary.inlet",
            },
            {
                "line_id": "edge_0003",
                "source": "reactor.product",
                "target": "reactor.feed",
            },
        ],
    }
    spec_path = _write_spec(tmp_path=tmp_path, payload=desired_spec)

    first_diff = cli.spec_diff(spec_path=spec_path)
    second_diff = cli.spec_diff(spec_path=spec_path)
    assert first_diff == second_diff
    assert first_diff["remove"] == [
        {"operation": "disconnect_line", "line_id": "edge_0001"},
        {"operation": "remove_boundary", "boundary_id": "feed_boundary"},
    ]
    assert first_diff["add"] == [
        {
            "operation": "add_boundary_source",
            "boundary_id": "feed_boundary_2",
            "port_name": "outlet",
        },
        {
            "operation": "connect_line",
            "source": "reactor.product",
            "target": "reactor.feed",
            "line_id": "edge_0003",
        },
    ]
    assert first_diff["update"] == [
        {
            "operation": "rewire_connection",
            "edge_id": "edge_0002",
            "source": "feed_boundary_2.outlet",
            "target": "product_boundary.inlet",
        }
    ]

    apply_result = cli.spec_apply(spec_path=spec_path)
    assert apply_result["diff"] == first_diff
    assert apply_result["queued_request_ids"] == ("rq_0001", "rq_0002", "rq_0003")
    assert apply_result["applied_request_ids"] == ("rq_0001", "rq_0002", "rq_0003")
    assert apply_result["skipped_request_ids"] == ()
    assert apply_result["graph_revision"] == "graph_rev_0002"

    compiled = network.compiled
    assert compiled is not None
    boundary_ids = tuple(node.boundary_id for node in compiled.topology.boundary_nodes)
    assert boundary_ids == ("feed_boundary_2", "product_boundary")
    edge_by_id = {
        edge.edge_id: (
            f"{edge.source.node_id}.{edge.source.port_name}",
            f"{edge.target.node_id}.{edge.target.port_name}",
        )
        for edge in compiled.topology.edges
    }
    assert edge_by_id == {
        "edge_0002": ("feed_boundary_2.outlet", "product_boundary.inlet"),
        "edge_0003": ("reactor.product", "reactor.feed"),
    }
    reactor_node = next(
        node for node in compiled.topology.process_nodes if node.process_id == "reactor"
    )
    assert reactor_node.inlet_ports == ("feed",)
    assert reactor_node.outlet_ports == ("product",)
    assert network.queued_reconfigurations == ()


def test_spec_apply_invalid_spec_rolls_back_without_state_change(tmp_path: Path) -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)
    cli = ModularCli(network=network)

    invalid_spec = {
        "processes": [
            {
                "process_id": "reactor",
                "inlet_ports": ["feed"],
                "outlet_ports": ["product"],
            }
        ],
        "boundaries": [
            {"boundary_id": "feed_boundary", "direction": "source", "port_name": "outlet"},
            {"boundary_id": "product_boundary", "direction": "sink", "port_name": "inlet"},
            {"boundary_id": "purge_boundary", "direction": "sink", "port_name": "inlet"},
        ],
        "lines": [
            {
                "line_id": "edge_0001",
                "source": "feed_boundary.outlet",
                "target": "reactor.feed",
            },
            {
                "line_id": "edge_0002",
                "source": "reactor.product",
                "target": "product_boundary.inlet",
            },
            {
                "line_id": "edge_0003",
                "source": "unknown_source.outlet",
                "target": "purge_boundary.inlet",
            },
        ],
    }
    spec_path = _write_spec(tmp_path=tmp_path, payload=invalid_spec)
    before_snapshot = network.save_runtime_snapshot()

    with pytest.raises(
        SpecApplyError, match="spec apply rollback: reconfiguration transaction rollback"
    ) as error:
        _ = cli.spec_apply(spec_path=spec_path)

    after_snapshot = network.save_runtime_snapshot()
    assert after_snapshot == before_snapshot
    assert network.queued_reconfigurations == ()
    assert error.value.diff["add"] == [
        {
            "operation": "add_boundary_sink",
            "boundary_id": "purge_boundary",
            "port_name": "inlet",
        },
        {
            "operation": "connect_line",
            "source": "unknown_source.outlet",
            "target": "purge_boundary.inlet",
            "line_id": "edge_0003",
        },
    ]

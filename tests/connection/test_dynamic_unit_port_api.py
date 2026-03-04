from __future__ import annotations

import importlib
from collections.abc import Mapping
from typing import cast
from typing import Protocol

import pytest

from modular_simulation.connection.domain_contracts import JunctionProcess, Port, UnitProcess
from modular_simulation.connection.hydraulic_compile import HydraulicCompileLifecycle
from modular_simulation.connection.hydraulic_solver import (
    HydraulicSystemDefinition,
    LinearResidualEquation,
)
from modular_simulation.connection.network import ConnectionNetwork
from modular_simulation.connection.runtime import (
    ConnectionRuntimeOrchestrator,
    ConnectionRuntimeStepResult,
)


class _DynamicUnitPortApi(Protocol):
    def add_unit_process(
        self,
        process: UnitProcess | JunctionProcess,
        *,
        idempotency_key: str | None = None,
        expected_revision: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> str: ...

    def add_junction_process(
        self,
        process: UnitProcess | JunctionProcess,
        *,
        idempotency_key: str | None = None,
        expected_revision: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> str: ...

    def add_port(
        self,
        *,
        process_id: str,
        port: Port,
        idempotency_key: str | None = None,
        expected_revision: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> str: ...

    def add_outlet(
        self,
        *,
        process_id: str,
        port_id: str,
        idempotency_key: str | None = None,
        expected_revision: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> str: ...

    def remove_inlet(
        self,
        *,
        process_id: str,
        port_id: str,
        idempotency_key: str | None = None,
        expected_revision: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> str: ...


class _DynamicUnitPortApiFactory(Protocol):
    def __call__(self, *, network: ConnectionNetwork) -> _DynamicUnitPortApi: ...


def _api(network: ConnectionNetwork) -> _DynamicUnitPortApi:
    module = importlib.import_module("modular_simulation.connection.reconfiguration_api")
    api_factory = cast(
        _DynamicUnitPortApiFactory,
        getattr(module, "DynamicUnitPortReconfigurationApi"),
    )
    return api_factory(network=network)


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


def test_add_unit_and_ports_commit_through_transaction_api() -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)
    api = _api(network)

    add_unit_request = api.add_unit_process(
        UnitProcess(
            process_id="separator",
            ports=(
                Port(port_id="feed", direction="inlet"),
                Port(port_id="product", direction="outlet"),
            ),
        )
    )
    add_recycle_inlet_request = api.add_port(
        process_id="reactor",
        port=Port(port_id="recycle", direction="inlet"),
    )
    add_purge_outlet_request = api.add_outlet(
        process_id="reactor",
        port_id="purge",
    )
    add_junction_request = api.add_junction_process(
        JunctionProcess(
            junction_id="mixing_junction",
            inlet_port_ids=("inlet_a",),
            outlet_port_id="outlet",
        )
    )

    assert (
        add_unit_request,
        add_recycle_inlet_request,
        add_purge_outlet_request,
        add_junction_request,
    ) == ("rq_0001", "rq_0002", "rq_0003", "rq_0004")

    result = cast(ConnectionRuntimeStepResult, network.step(macro_step_time_s=0.25))
    assert result.graph_revision == "graph_rev_0002"
    assert result.barrier_reconfiguration.applied_request_ids == (
        "rq_0001",
        "rq_0002",
        "rq_0003",
        "rq_0004",
    )
    assert result.barrier_reconfiguration.skipped_request_ids == ()

    compiled = network.compiled
    assert compiled is not None
    process_nodes = {node.process_id: node for node in compiled.topology.process_nodes}
    assert process_nodes["separator"].inlet_ports == ("feed",)
    assert process_nodes["separator"].outlet_ports == ("product",)
    assert process_nodes["reactor"].inlet_ports == ("feed", "recycle")
    assert process_nodes["reactor"].outlet_ports == ("product", "purge")
    assert process_nodes["mixing_junction"].inlet_ports == ("inlet_a",)
    assert process_nodes["mixing_junction"].outlet_ports == ("outlet",)
    assert network.queued_reconfigurations == ()


def test_remove_connected_port_fails_without_queue_mutation() -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)
    api = _api(network)
    before_snapshot = network.save_runtime_snapshot()

    with pytest.raises(
        ValueError,
        match=r"cannot remove process endpoint 'reactor.feed': connected edges exist \('edge_0001',\)",
    ):
        _ = api.remove_inlet(process_id="reactor", port_id="feed")

    after_snapshot = network.save_runtime_snapshot()
    assert after_snapshot == before_snapshot
    compiled = network.compiled
    assert compiled is not None
    process_nodes = {node.process_id: node for node in compiled.topology.process_nodes}
    assert process_nodes["reactor"].inlet_ports == ("feed",)
    assert tuple(edge.edge_id for edge in compiled.topology.edges) == ("edge_0001", "edge_0002")
    assert network.queued_reconfigurations == ()

from __future__ import annotations

import pytest
from modular_simulation.connection.topology.topology import (
    BoundaryNode,
    ConnectionEdge,
    JunctionNode,
    PortReference,
    ProcessNode,
    TopologyGraph,
)
from modular_simulation.connection.topology.network import ConnectionNetwork


def _valid_graph() -> TopologyGraph:
    return TopologyGraph(
        process_nodes=(
            ProcessNode(
                process_id="reactor",
                inlet_ports=("feed",),
                outlet_ports=("product",),
            ),
        ),
        boundary_nodes=(
            BoundaryNode(boundary_id="upstream", port_name="outlet", direction="source"),
            BoundaryNode(boundary_id="downstream", port_name="inlet", direction="sink"),
        ),
        junction_nodes=(
            JunctionNode(junction_id="mix", inlet_ports=("inlet",), outlet_ports=("outlet",)),
        ),
        edges=(
            ConnectionEdge(
                edge_id="edge_a",
                source=PortReference(node_id="upstream", port_name="outlet"),
                target=PortReference(node_id="mix", port_name="inlet"),
            ),
            ConnectionEdge(
                edge_id="edge_b",
                source=PortReference(node_id="mix", port_name="outlet"),
                target=PortReference(node_id="reactor", port_name="feed"),
            ),
            ConnectionEdge(
                edge_id="edge_c",
                source=PortReference(node_id="reactor", port_name="product"),
                target=PortReference(node_id="downstream", port_name="inlet"),
            ),
        ),
    )


def test_happy_path_builds_topology_with_deterministic_indexes() -> None:
    graph = _valid_graph()

    assert graph.node_ids == ("downstream", "mix", "reactor", "upstream")
    assert graph.edge_ids == ("edge_a", "edge_b", "edge_c")


def test_unknown_endpoint_reports_deterministic_error_message() -> None:
    with pytest.raises(ValueError) as error:
        _ = TopologyGraph(
            process_nodes=(),
            boundary_nodes=(BoundaryNode(boundary_id="feed", port_name="out", direction="source"),),
            junction_nodes=(),
            edges=(
                ConnectionEdge(
                    edge_id="edge_1",
                    source=PortReference(node_id="feed", port_name="out"),
                    target=PortReference(node_id="unknown", port_name="in"),
                ),
            ),
        )

    assert str(error.value) == (
        "unknown connection endpoints: ['edge_1:target=unknown.in (node not found)']"
    )


def test_duplicate_ids_across_nodes_and_edges_are_rejected_deterministically() -> None:
    with pytest.raises(ValueError) as error:
        _ = TopologyGraph(
            process_nodes=(
                ProcessNode(process_id="shared", inlet_ports=("in",), outlet_ports=("out",)),
            ),
            boundary_nodes=(
                BoundaryNode(boundary_id="shared", port_name="port", direction="source"),
            ),
            junction_nodes=(),
            edges=(
                ConnectionEdge(
                    edge_id="edge_same",
                    source=PortReference(node_id="shared", port_name="out"),
                    target=PortReference(node_id="shared", port_name="port"),
                ),
                ConnectionEdge(
                    edge_id="edge_same",
                    source=PortReference(node_id="shared", port_name="out"),
                    target=PortReference(node_id="shared", port_name="port"),
                ),
            ),
        )

    assert str(error.value) == ("duplicate ids are not allowed: ['edge:edge_same', 'node:shared']")


def test_duplicate_edges_are_rejected_even_with_distinct_edge_ids() -> None:
    with pytest.raises(ValueError) as error:
        _ = TopologyGraph(
            process_nodes=(
                ProcessNode(process_id="unit", inlet_ports=("in",), outlet_ports=("out",)),
            ),
            boundary_nodes=(
                BoundaryNode(boundary_id="feed", port_name="port", direction="source"),
            ),
            junction_nodes=(),
            edges=(
                ConnectionEdge(
                    edge_id="edge_1",
                    source=PortReference(node_id="feed", port_name="port"),
                    target=PortReference(node_id="unit", port_name="in"),
                ),
                ConnectionEdge(
                    edge_id="edge_2",
                    source=PortReference(node_id="feed", port_name="port"),
                    target=PortReference(node_id="unit", port_name="in"),
                ),
            ),
        )

    assert str(error.value) == ("duplicate edges are not allowed: ['feed.port->unit.in']")


def test_invalid_self_link_is_rejected() -> None:
    with pytest.raises(ValueError) as error:
        _ = TopologyGraph(
            process_nodes=(
                ProcessNode(process_id="unit", inlet_ports=("in",), outlet_ports=("out",)),
            ),
            boundary_nodes=(),
            junction_nodes=(),
            edges=(
                ConnectionEdge(
                    edge_id="edge_1",
                    source=PortReference(node_id="unit", port_name="out"),
                    target=PortReference(node_id="unit", port_name="out"),
                ),
            ),
        )

    assert str(error.value) == "invalid self-links are not allowed: ['edge_1:unit.out']"


def test_connection_network_compile_emits_explicit_junction_nodes() -> None:
    network = ConnectionNetwork()
    network.add_process("reactor", inlet_ports=("feed",), outlet_ports=("product",))
    network.add_junction(
        "mix", inlet_ports=("feed_a", "feed_b"), outlet_ports=("product_a", "product_b")
    )
    network.add_boundary_source("upstream_a")
    network.add_boundary_source("upstream_b")
    network.add_boundary_sink("downstream_a")
    network.add_boundary_sink("downstream_b")
    network.connect("upstream_a", "mix.feed_a")
    network.connect("upstream_b", "mix.feed_b")
    network.connect("mix.product_a", "reactor.feed")
    network.connect("reactor.product", "downstream_a")
    network.connect("mix.product_b", "downstream_b")

    compiled = network.compile()

    assert tuple(node.process_id for node in compiled.topology.process_nodes) == ("reactor",)
    assert tuple(node.junction_id for node in compiled.topology.junction_nodes) == ("mix",)
    assert compiled.topology.junction_nodes[0].port_names == (
        "feed_a",
        "feed_b",
        "product_a",
        "product_b",
    )

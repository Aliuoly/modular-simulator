from __future__ import annotations

import pytest

from modular_simulation.connection.hydraulics.pressure_inference import (
    BoundaryEndpoint,
    ProcessPortEndpoint,
    build_topology_endpoint_context,
    describe_endpoint,
    hydrostatic_pressure_from_submerged_head_pa,
    resolve_edge_pressure_deltas_pa,
)
from modular_simulation.connection.topology.topology import (
    BoundaryNode,
    ConnectionEdge,
    PortReference,
    ProcessNode,
    TopologyGraph,
)


def _branching_topology() -> TopologyGraph:
    return TopologyGraph(
        process_nodes=(
            ProcessNode(
                process_id="tank_1",
                inlet_ports=("fresh_in",),
                outlet_ports=("out_bottom", "out_side"),
            ),
            ProcessNode(process_id="tank_2", inlet_ports=("in",), outlet_ports=("out",)),
            ProcessNode(process_id="tank_3", inlet_ports=("in",), outlet_ports=("out",)),
        ),
        boundary_nodes=(
            BoundaryNode(boundary_id="feed", port_name="outlet", direction="source"),
            BoundaryNode(boundary_id="product", port_name="inlet", direction="sink"),
        ),
        junction_nodes=(),
        edges=(
            ConnectionEdge(
                edge_id="line_feed_1",
                source=PortReference(node_id="feed", port_name="outlet"),
                target=PortReference(node_id="tank_1", port_name="fresh_in"),
            ),
            ConnectionEdge(
                edge_id="line_1_to_2",
                source=PortReference(node_id="tank_1", port_name="out_bottom"),
                target=PortReference(node_id="tank_2", port_name="in"),
            ),
            ConnectionEdge(
                edge_id="line_1_to_3",
                source=PortReference(node_id="tank_1", port_name="out_side"),
                target=PortReference(node_id="tank_3", port_name="in"),
            ),
            ConnectionEdge(
                edge_id="line_2_to_product",
                source=PortReference(node_id="tank_2", port_name="out"),
                target=PortReference(node_id="product", port_name="inlet"),
            ),
            ConnectionEdge(
                edge_id="line_3_to_product",
                source=PortReference(node_id="tank_3", port_name="out"),
                target=PortReference(node_id="product", port_name="inlet"),
            ),
        ),
    )


def test_build_topology_endpoint_context_maps_process_and_boundary_directions() -> None:
    topology = _branching_topology()

    context = build_topology_endpoint_context(topology)

    assert context.process_port_directions[("tank_1", "fresh_in")] == "inlet"
    assert context.process_port_directions[("tank_1", "out_bottom")] == "outlet"
    assert context.boundary_directions["feed"] == "source"
    assert context.boundary_directions["product"] == "sink"


def test_describe_endpoint_returns_typed_descriptor_and_rejects_unknown_endpoint() -> None:
    topology = _branching_topology()
    context = build_topology_endpoint_context(topology)

    process_endpoint = describe_endpoint(
        endpoint_context=context,
        node_id="tank_1",
        port_name="out_side",
    )
    boundary_endpoint = describe_endpoint(
        endpoint_context=context,
        node_id="feed",
        port_name="outlet",
    )

    assert process_endpoint == ProcessPortEndpoint(
        process_id="tank_1",
        port_name="out_side",
        direction="outlet",
    )
    assert boundary_endpoint == BoundaryEndpoint(
        boundary_id="feed",
        port_name="outlet",
        direction="source",
    )

    with pytest.raises(KeyError) as error:
        _ = describe_endpoint(
            endpoint_context=context,
            node_id="tank_99",
            port_name="out",
        )
    assert str(error.value) == "\"unknown topology endpoint 'tank_99.out'\""


def test_resolve_edge_pressure_deltas_supports_multi_process_topology() -> None:
    topology = _branching_topology()
    context = build_topology_endpoint_context(topology)

    process_pressures_pa = {
        ("tank_1", "fresh_in"): 110_000.0,
        ("tank_1", "out_bottom"): 114_000.0,
        ("tank_1", "out_side"): 111_500.0,
        ("tank_2", "in"): 108_000.0,
        ("tank_2", "out"): 106_800.0,
        ("tank_3", "in"): 107_300.0,
        ("tank_3", "out"): 106_200.0,
    }
    boundary_pressures_pa = {
        "feed": 140_000.0,
        "product": 101_325.0,
    }

    def _resolver(endpoint: ProcessPortEndpoint | BoundaryEndpoint) -> float:
        if isinstance(endpoint, ProcessPortEndpoint):
            return process_pressures_pa[(endpoint.process_id, endpoint.port_name)]
        return boundary_pressures_pa[endpoint.boundary_id]

    deltas_pa = resolve_edge_pressure_deltas_pa(
        topology=topology,
        endpoint_context=context,
        endpoint_pressure_resolver=_resolver,
    )

    assert deltas_pa == {
        "line_feed_1": 30_000.0,
        "line_1_to_2": 6_000.0,
        "line_1_to_3": 4_200.0,
        "line_2_to_product": 5_475.0,
        "line_3_to_product": 4_875.0,
    }


def test_hydrostatic_pressure_from_submerged_head_clamps_negative_head() -> None:
    pressure_pa = hydrostatic_pressure_from_submerged_head_pa(
        reference_pressure_pa=101_325.0,
        liquid_density_kg_per_m3=1_000.0,
        gravity_m_per_s2=9.81,
        liquid_surface_elevation_m=0.6,
        port_elevation_m=0.9,
    )

    assert pressure_pa == pytest.approx(101_325.0)

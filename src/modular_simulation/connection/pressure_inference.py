from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Callable, Literal, TypeAlias

from modular_simulation.connection.topology import TopologyGraph

ProcessPortDirection: TypeAlias = Literal["inlet", "outlet"]
BoundaryDirection: TypeAlias = Literal["source", "sink"]


@dataclass(frozen=True)
class ProcessPortEndpoint:
    process_id: str
    port_name: str
    direction: ProcessPortDirection


@dataclass(frozen=True)
class BoundaryEndpoint:
    boundary_id: str
    port_name: str
    direction: BoundaryDirection


EndpointDescriptor: TypeAlias = ProcessPortEndpoint | BoundaryEndpoint
EndpointPressureResolver: TypeAlias = Callable[[EndpointDescriptor], float]


@dataclass(frozen=True)
class TopologyEndpointContext:
    process_port_directions: Mapping[tuple[str, str], ProcessPortDirection]
    boundary_directions: Mapping[str, BoundaryDirection]


def build_topology_endpoint_context(topology: TopologyGraph) -> TopologyEndpointContext:
    process_port_directions: dict[tuple[str, str], ProcessPortDirection] = {}
    for node in topology.process_nodes:
        for inlet_port in node.inlet_ports:
            process_port_directions[(node.process_id, inlet_port)] = "inlet"
        for outlet_port in node.outlet_ports:
            process_port_directions[(node.process_id, outlet_port)] = "outlet"
    boundary_directions: dict[str, BoundaryDirection] = {
        node.boundary_id: node.direction for node in topology.boundary_nodes
    }
    return TopologyEndpointContext(
        process_port_directions=MappingProxyType(process_port_directions),
        boundary_directions=MappingProxyType(boundary_directions),
    )


def describe_endpoint(
    *,
    endpoint_context: TopologyEndpointContext,
    node_id: str,
    port_name: str,
) -> EndpointDescriptor:
    process_direction = endpoint_context.process_port_directions.get((node_id, port_name))
    if process_direction is not None:
        return ProcessPortEndpoint(
            process_id=node_id,
            port_name=port_name,
            direction=process_direction,
        )

    boundary_direction = endpoint_context.boundary_directions.get(node_id)
    if boundary_direction is not None:
        return BoundaryEndpoint(
            boundary_id=node_id,
            port_name=port_name,
            direction=boundary_direction,
        )

    raise KeyError(f"unknown topology endpoint '{node_id}.{port_name}'")


def resolve_edge_pressure_deltas_pa(
    *,
    topology: TopologyGraph,
    endpoint_context: TopologyEndpointContext,
    endpoint_pressure_resolver: EndpointPressureResolver,
) -> dict[str, float]:
    edge_deltas_pa: dict[str, float] = {}
    for edge in topology.edges:
        upstream_endpoint = describe_endpoint(
            endpoint_context=endpoint_context,
            node_id=edge.source.node_id,
            port_name=edge.source.port_name,
        )
        downstream_endpoint = describe_endpoint(
            endpoint_context=endpoint_context,
            node_id=edge.target.node_id,
            port_name=edge.target.port_name,
        )
        edge_deltas_pa[edge.edge_id] = endpoint_pressure_resolver(
            upstream_endpoint
        ) - endpoint_pressure_resolver(downstream_endpoint)
    return edge_deltas_pa


def hydrostatic_pressure_from_submerged_head_pa(
    *,
    reference_pressure_pa: float,
    liquid_density_kg_per_m3: float,
    gravity_m_per_s2: float,
    liquid_surface_elevation_m: float,
    port_elevation_m: float,
) -> float:
    submerged_head_m = max(float(liquid_surface_elevation_m) - float(port_elevation_m), 0.0)
    return float(reference_pressure_pa) + (
        float(liquid_density_kg_per_m3) * float(gravity_m_per_s2) * submerged_head_m
    )


__all__ = [
    "BoundaryDirection",
    "BoundaryEndpoint",
    "EndpointDescriptor",
    "EndpointPressureResolver",
    "ProcessPortDirection",
    "ProcessPortEndpoint",
    "TopologyEndpointContext",
    "build_topology_endpoint_context",
    "describe_endpoint",
    "hydrostatic_pressure_from_submerged_head_pa",
    "resolve_edge_pressure_deltas_pa",
]

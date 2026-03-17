from __future__ import annotations

from collections.abc import Mapping
from math import isfinite

from ..domain.state import MaterialState, PortCondition
from ..topology.junction import (
    NEAR_ZERO_INCOMING_FLOW_EPSILON,
    JunctionMixingResult,
    mix_junction_state,
)
from ..topology.topology import TopologyGraph


def mix_junction_runtime_states(
    *,
    topology: TopologyGraph,
    edge_states: Mapping[str, MaterialState],
    edge_flow_rates: Mapping[str, float],
    previous_junction_states: Mapping[str, MaterialState],
    near_zero_incoming_flow_epsilon: float = NEAR_ZERO_INCOMING_FLOW_EPSILON,
) -> dict[str, JunctionMixingResult]:
    edge_by_id = {edge.edge_id: edge for edge in topology.edges}
    results: dict[str, JunctionMixingResult] = {}

    for junction_id in sorted(junction.junction_id for junction in topology.junction_nodes):
        previous_state = previous_junction_states.get(junction_id)
        if previous_state is None:
            raise ValueError(f"missing previous junction state for '{junction_id}'")

        missing_data: list[str] = []
        junction_port_conditions: dict[str, PortCondition] = {}
        for edge_id in sorted(edge_by_id):
            edge = edge_by_id[edge_id]
            local_flow = _classify_local_node_flow(
                edge=edge,
                local_node_id=junction_id,
                solved_line_flow=edge_flow_rates.get(edge_id),
            )
            if local_flow is None:
                continue

            edge_state = edge_states.get(edge_id)
            if edge_state is None:
                missing_data.append(f"{edge_id}:state")
            edge_flow_rate = edge_flow_rates.get(edge_id)
            if edge_flow_rate is None:
                missing_data.append(f"{edge_id}:flow_rate")
            if edge_state is None or edge_flow_rate is None:
                continue

            junction_port_conditions[edge_id] = PortCondition(
                state=edge_state,
                through_molar_flow_rate=local_flow,
            )

        if missing_data:
            details = ", ".join(sorted(missing_data))
            raise ValueError(f"missing runtime edge data for junction '{junction_id}': {details}")

        results[junction_id] = mix_junction_state(
            incoming_port_conditions=junction_port_conditions,
            previous_state=previous_state,
            near_zero_incoming_flow_epsilon=near_zero_incoming_flow_epsilon,
        )

    return results


def _classify_local_node_flow(
    *,
    edge: object,
    local_node_id: str,
    solved_line_flow: float | None,
) -> float | None:
    source = getattr(edge, "source")
    target = getattr(edge, "target")
    source_node_id = getattr(source, "node_id")
    target_node_id = getattr(target, "node_id")
    if source_node_id != local_node_id and target_node_id != local_node_id:
        return None
    if solved_line_flow is None:
        return None
    if not isfinite(solved_line_flow):
        raise ValueError(
            f"solved line flow for edge '{getattr(edge, 'edge_id')}' at node '{local_node_id}' must be finite"
        )

    if target_node_id == local_node_id:
        return float(solved_line_flow)
    return float(-solved_line_flow)


__all__ = ["mix_junction_runtime_states"]

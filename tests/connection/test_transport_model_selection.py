from __future__ import annotations

# pyright: reportMissingImports=false, reportMissingTypeStubs=false, reportUnknownMemberType=false

import inspect

import modular_simulation.connection.transport as transport
import modular_simulation.connection.transport_runtime as transport_runtime

from modular_simulation.connection.transport import (
    LagTransportState,
    LagTransportUpdateResult,
    MVPLagTransportModel,
    TransportModel,
)
from modular_simulation.connection.transport_runtime import TransportRuntime


def test_mvp_lag_model_is_constructed_directly() -> None:
    model = MVPLagTransportModel(lag_time_constant_s=1.2)

    assert model.model == "mvp_lag"
    assert model.lag_time_constant_s == 1.2


def test_mvp_direct_construction_matches_runtime_owned_model_behavior() -> None:
    current = LagTransportState(composition=(0.7, 0.3), temperature=310.0)
    advected = LagTransportState(composition=(0.2, 0.8), temperature=345.0)

    direct_model = MVPLagTransportModel(
        lag_time_constant_s=0.9,
        near_zero_flow_epsilon=1.0e-12,
        flow_smoothing_flow_rate=1.0e-9,
    )
    runtime = TransportRuntime(
        topology=_single_edge_graph(),
        lag_time_constant_s=0.9,
        near_zero_flow_epsilon=1.0e-12,
        flow_smoothing_flow_rate=1.0e-9,
    )

    direct_result = direct_model.update(
        current_state=current,
        advected_state=advected,
        dt=0.1,
        through_molar_flow_rate=0.8,
        previous_through_molar_flow_rate=0.7,
    )
    runtime_result = runtime.step(
        current_edge_states={"edge_main": current},
        advected_edge_states={"edge_main": advected},
        edge_flow_rates={"edge_main": 0.8},
        previous_edge_flow_rates={"edge_main": 0.7},
        dt=0.1,
    )

    assert runtime_result.edge_updates["edge_main"] == direct_result


def test_transport_public_surface_documents_owner_led_api_only() -> None:
    exports = getattr(transport, "__all__", ())

    assert exports == [
        "LagTransportState",
        "LagTransportUpdateResult",
        "MVPLagTransportModel",
        "TransportModel",
    ]
    assert "state" in LagTransportUpdateResult.__dataclass_fields__
    assert hasattr(MVPLagTransportModel, "update")
    assert isinstance(MVPLagTransportModel(lag_time_constant_s=1.0), TransportModel)
    assert "TransportModelSelection" not in exports
    assert "select_transport_model" not in exports
    assert "update_lag_transport_state" not in exports
    assert not hasattr(transport, "TransportModelSelection")
    assert not hasattr(transport, "select_transport_model")
    assert not hasattr(transport, "update_lag_transport_state")


def test_public_transport_surfaces_preserve_owner_distinction() -> None:
    assert "TransportRuntime" in getattr(transport_runtime, "__all__", ())
    assert "TransportRuntimeStepResult" in getattr(transport_runtime, "__all__", ())
    assert hasattr(TransportRuntime, "step")
    assert "update_transport_runtime_states" not in getattr(transport_runtime, "__all__", ())


def test_transport_runtime_signature_stays_owner_led() -> None:
    signature = inspect.signature(TransportRuntime)

    assert tuple(signature.parameters) == (
        "topology",
        "lag_time_constant_s",
        "near_zero_flow_epsilon",
        "flow_smoothing_flow_rate",
    )


def _single_edge_graph():
    from modular_simulation.connection.topology import (
        BoundaryNode,
        ConnectionEdge,
        PortReference,
        TopologyGraph,
    )

    return TopologyGraph(
        process_nodes=(),
        boundary_nodes=(
            BoundaryNode(boundary_id="feed", port_name="outlet", direction="source"),
            BoundaryNode(boundary_id="sink", port_name="inlet", direction="sink"),
        ),
        junction_nodes=(),
        edges=(
            ConnectionEdge(
                edge_id="edge_main",
                source=PortReference(node_id="feed", port_name="outlet"),
                target=PortReference(node_id="sink", port_name="inlet"),
            ),
        ),
    )

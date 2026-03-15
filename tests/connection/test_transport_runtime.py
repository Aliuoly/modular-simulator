from __future__ import annotations

# pyright: reportMissingImports=false, reportMissingTypeStubs=false, reportUnknownMemberType=false

import inspect
from math import isfinite

import modular_simulation.connection.transport_runtime as transport_runtime
from modular_simulation.connection.topology import (
    BoundaryNode,
    ConnectionEdge,
    PortReference,
    TopologyGraph,
)
from modular_simulation.connection.transport import (
    LagTransportState,
    MVPLagTransportModel,
)
from modular_simulation.connection.transport_runtime import TransportRuntime


def _two_edge_graph_unsorted() -> TopologyGraph:
    return TopologyGraph(
        process_nodes=(),
        boundary_nodes=(
            BoundaryNode(boundary_id="feed_a", port_name="outlet", direction="source"),
            BoundaryNode(boundary_id="feed_b", port_name="outlet", direction="source"),
            BoundaryNode(boundary_id="sink_a", port_name="inlet", direction="sink"),
            BoundaryNode(boundary_id="sink_b", port_name="inlet", direction="sink"),
        ),
        junction_nodes=(),
        edges=(
            ConnectionEdge(
                edge_id="edge_b",
                source=PortReference(node_id="feed_b", port_name="outlet"),
                target=PortReference(node_id="sink_b", port_name="inlet"),
            ),
            ConnectionEdge(
                edge_id="edge_a",
                source=PortReference(node_id="feed_a", port_name="outlet"),
                target=PortReference(node_id="sink_a", port_name="inlet"),
            ),
        ),
    )


def _single_edge_graph() -> TopologyGraph:
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


def test_runtime_step_delegates_to_owned_lag_model_with_flow_tracking() -> None:
    graph = _two_edge_graph_unsorted()
    runtime = TransportRuntime(topology=graph, lag_time_constant_s=0.9)
    current_states = {
        "edge_a": LagTransportState(composition=(0.75, 0.25), temperature=305.0),
        "edge_b": LagTransportState(composition=(0.35, 0.65), temperature=315.0),
    }
    advected_states = {
        "edge_a": LagTransportState(composition=(0.10, 0.90), temperature=365.0),
        "edge_b": LagTransportState(composition=(0.95, 0.05), temperature=275.0),
    }
    edge_flow_rates = {
        "edge_a": 0.8,
        "edge_b": -0.4,
    }
    previous_edge_flow_rates = {
        "edge_a": 0.7,
        "edge_b": 0.3,
    }
    model = MVPLagTransportModel(lag_time_constant_s=0.9)

    runtime_result = runtime.step(
        current_edge_states=current_states,
        advected_edge_states=advected_states,
        edge_flow_rates=edge_flow_rates,
        previous_edge_flow_rates=previous_edge_flow_rates,
        dt=0.1,
    )

    assert tuple(runtime_result.edge_updates.keys()) == ("edge_a", "edge_b")
    assert tuple(runtime_result.edge_states.keys()) == ("edge_a", "edge_b")
    assert tuple(runtime_result.previous_edge_flow_rates.keys()) == ("edge_a", "edge_b")

    expected_edge_a = model.update(
        current_state=current_states["edge_a"],
        advected_state=advected_states["edge_a"],
        dt=0.1,
        through_molar_flow_rate=edge_flow_rates["edge_a"],
        previous_through_molar_flow_rate=previous_edge_flow_rates["edge_a"],
    )
    expected_edge_b = model.update(
        current_state=current_states["edge_b"],
        advected_state=advected_states["edge_b"],
        dt=0.1,
        through_molar_flow_rate=edge_flow_rates["edge_b"],
        previous_through_molar_flow_rate=previous_edge_flow_rates["edge_b"],
    )

    assert runtime_result.edge_updates["edge_a"] == expected_edge_a
    assert runtime_result.edge_updates["edge_b"] == expected_edge_b
    assert runtime_result.edge_states["edge_a"] == expected_edge_a.state
    assert runtime_result.edge_states["edge_b"] == expected_edge_b.state
    assert runtime_result.previous_edge_flow_rates == {
        "edge_a": edge_flow_rates["edge_a"],
        "edge_b": edge_flow_rates["edge_b"],
    }


def test_runtime_constructor_stays_lag_parameter_based_and_owns_default_model() -> None:
    signature = inspect.signature(TransportRuntime)
    assert tuple(signature.parameters) == (
        "topology",
        "lag_time_constant_s",
        "near_zero_flow_epsilon",
        "flow_smoothing_flow_rate",
    )

    runtime = TransportRuntime(topology=_single_edge_graph(), lag_time_constant_s=0.8)

    assert isinstance(runtime._model, MVPLagTransportModel)
    assert runtime._model.lag_time_constant_s == 0.8
    assert runtime._model.near_zero_flow_epsilon == runtime.near_zero_flow_epsilon
    assert runtime._model.flow_smoothing_flow_rate == runtime.flow_smoothing_flow_rate


def test_runtime_reversal_and_near_zero_hold_sequence_is_deterministic() -> None:
    graph = _single_edge_graph()
    runtime = TransportRuntime(
        topology=graph,
        lag_time_constant_s=0.8,
        near_zero_flow_epsilon=1.0e-12,
    )
    initial_state = LagTransportState(composition=(0.5, 0.5), temperature=320.0)
    forward_advected = LagTransportState(composition=(0.9, 0.1), temperature=390.0)
    reverse_advected = LagTransportState(composition=(0.1, 0.9), temperature=260.0)

    def run_sequence() -> tuple[tuple[float, tuple[float, ...], float, bool, bool], ...]:
        state = initial_state
        previous_edge_flow_rates: dict[str, float] = {}
        trace: list[tuple[float, tuple[float, ...], float, bool, bool]] = []

        for advected, flow in (
            (forward_advected, 1.0),
            (reverse_advected, -1.0),
            (forward_advected, 1.0e-14),
        ):
            runtime_result = runtime.step(
                current_edge_states={"edge_main": state},
                advected_edge_states={"edge_main": advected},
                edge_flow_rates={"edge_main": flow},
                previous_edge_flow_rates=previous_edge_flow_rates,
                dt=0.05,
            )
            update_result = runtime_result.edge_updates["edge_main"]
            state = runtime_result.edge_states["edge_main"]
            previous_edge_flow_rates = dict(runtime_result.previous_edge_flow_rates)
            trace.append(
                (
                    state.temperature,
                    state.composition,
                    update_result.update_fraction,
                    update_result.flow_sign_changed,
                    update_result.held_for_near_zero_flow,
                )
            )

        return tuple(trace)

    first_trace = run_sequence()
    second_trace = run_sequence()

    assert first_trace == second_trace
    assert not first_trace[0][3]
    assert not first_trace[0][4]
    assert first_trace[1][3]
    assert not first_trace[1][4]
    assert not first_trace[2][3]
    assert first_trace[2][4]
    assert abs(first_trace[2][2]) <= 1.0e-12


def test_runtime_outputs_remain_finite_with_normalized_composition() -> None:
    graph = _two_edge_graph_unsorted()
    runtime = TransportRuntime(topology=graph, lag_time_constant_s=0.7)
    current_states = {
        "edge_a": LagTransportState(composition=(0.8, 0.2), temperature=300.0),
        "edge_b": LagTransportState(composition=(0.2, 0.8), temperature=330.0),
    }
    advected_by_flow_sign = {
        True: {
            "edge_a": LagTransportState(composition=(0.1, 0.9), temperature=380.0),
            "edge_b": LagTransportState(composition=(0.9, 0.1), temperature=260.0),
        },
        False: {
            "edge_a": LagTransportState(composition=(0.95, 0.05), temperature=275.0),
            "edge_b": LagTransportState(composition=(0.05, 0.95), temperature=390.0),
        },
    }

    previous_edge_flow_rates: dict[str, float] = {}
    for step in range(20):
        edge_flow_rates = {
            "edge_a": 0.6 if step % 2 == 0 else -0.6,
            "edge_b": -0.9 if step % 2 == 0 else 0.9,
        }
        advected_states = {
            edge_id: advected_by_flow_sign[edge_flow_rates[edge_id] > 0.0][edge_id]
            for edge_id in edge_flow_rates
        }

        runtime_result = runtime.step(
            current_edge_states=current_states,
            advected_edge_states=advected_states,
            edge_flow_rates=edge_flow_rates,
            previous_edge_flow_rates=previous_edge_flow_rates,
            dt=0.08,
        )
        current_states = dict(runtime_result.edge_states)
        previous_edge_flow_rates = dict(runtime_result.previous_edge_flow_rates)

        for edge_id, update_result in runtime_result.edge_updates.items():
            assert 0.0 <= update_result.update_fraction <= 1.0
            assert all(isfinite(value) for value in update_result.state.composition)
            assert all(0.0 <= value <= 1.0 for value in update_result.state.composition)
            assert abs(sum(update_result.state.composition) - 1.0) <= 1.0e-9
            assert isfinite(update_result.state.temperature)
            assert isfinite(runtime_result.previous_edge_flow_rates[edge_id])


def test_runtime_module_exports_owner_led_api_only() -> None:
    assert "TransportRuntime" in getattr(transport_runtime, "__all__", ())
    assert hasattr(TransportRuntime, "step")
    assert "update_transport_runtime_states" not in getattr(transport_runtime, "__all__", ())

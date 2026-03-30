from __future__ import annotations

from modular_simulation.connection.kernel_adapter import KernelCandidateStepRequest
from modular_simulation.connection.runtime.connection_layer import TransportAndMixingUpdate
from modular_simulation.connection.runtime.runtime import ConnectionRuntimeOrchestrator
from modular_simulation.connection.runtime.split_kernel_adapter import SplitKernelAdapter
from modular_simulation.connection.hydraulics.hydraulic_solver import HydraulicSolveResult
from modular_simulation.connection.topology.network import ConnectionNetwork


def _hydraulic_result() -> HydraulicSolveResult:
    return HydraulicSolveResult(
        converged=True,
        iterations=1,
        residual_norm=1.0e-9,
        solution_vector=[1.0, 5.0],
        unknowns={"flow": 1.0, "pressure": 5.0},
        unknown_index_map={"flow": 0, "pressure": 1},
        residual_index_map={"balance": 0, "ref": 1},
    )


def _make_runtime_fixture() -> tuple[ConnectionNetwork, ConnectionRuntimeOrchestrator]:
    runtime = ConnectionRuntimeOrchestrator(
        hydraulic_solve_step=lambda *, network, macro_step_time_s: _hydraulic_result(),
        transport_and_mixing_step=(
            lambda *, network, hydraulic_result, macro_step_time_s: TransportAndMixingUpdate(
                transport_results={}
            )
        ),
        boundary_propagation_step=(
            lambda *, network, hydraulic_result, transport_and_mixing_update, macro_step_time_s: {}
        ),
    )
    network = ConnectionNetwork(runtime_orchestrator=runtime)
    network.add_process("reactor", inlet_ports=("feed",), outlet_ports=("product",))
    network.add_boundary_source("feed_boundary")
    network.add_boundary_sink("product_boundary")
    _ = network.connect("feed_boundary", "reactor.feed")
    _ = network.connect("reactor.product", "product_boundary")
    _ = network.compile()
    return network, runtime


def _transport_runtime_payload() -> dict[str, object]:
    return {
        "edge_states": [
            {
                "edge_id": "edge_0001",
                "composition": [0.8, 0.2],
                "temperature": 315.0,
            }
        ],
        "previous_edge_flow_rates": [{"edge_id": "edge_0001", "flow_rate": 1.25}],
        "junction_states": [
            {
                "junction_id": "mix",
                "state": {
                    "pressure": 120000.0,
                    "temperature": 310.0,
                    "mole_fractions": [0.6, 0.4],
                },
            }
        ],
    }


def test_split_kernel_delay_semantics_declares_external_transport_history_fields() -> None:
    network, runtime = _make_runtime_fixture()
    adapter = SplitKernelAdapter(network=network, runtime_orchestrator=runtime)

    assert adapter.delay_semantics.strategy.value == "external_transport_history"
    assert adapter.delay_state_mapping.payload_key == "transport_runtime_state"
    assert adapter.delay_state_mapping.mapped_fields == (
        "edge_states",
        "previous_edge_flow_rates",
        "junction_states",
    )


def test_split_kernel_delay_state_round_trip_matches_transport_runtime_payload() -> None:
    network, runtime = _make_runtime_fixture()
    adapter = SplitKernelAdapter(network=network, runtime_orchestrator=runtime)
    runtime.restore_transport_runtime_state(_transport_runtime_payload())

    captured_delay_state = adapter.capture_delay_state()
    expected_transport_runtime_state = runtime.export_transport_runtime_state()

    assert captured_delay_state == {
        "delay_strategy": "external_transport_history",
        "state_schema": "transport_runtime_state",
        "mapped_fields": (
            "edge_states",
            "previous_edge_flow_rates",
            "junction_states",
        ),
        "transport_runtime_state": expected_transport_runtime_state,
    }

    runtime.restore_transport_runtime_state({})
    adapter.restore_delay_state(captured_delay_state)

    assert runtime.export_transport_runtime_state() == expected_transport_runtime_state


def test_split_kernel_delay_mapping_requires_explicit_future_replacement_contract() -> None:
    network, runtime = _make_runtime_fixture()
    adapter = SplitKernelAdapter(network=network, runtime_orchestrator=runtime)

    assert adapter.supported_optional_capabilities() == frozenset()
    assert adapter.delay_state_mapping.replacement_required is True
    assert adapter.delay_state_mapping.replacement_candidates == (
        "augmented_state",
        "hybrid",
    )
    assert "explicit mapping" in adapter.delay_state_mapping.replacement_rule
    assert "optional solver capabilities" in adapter.delay_state_mapping.replacement_rule

    step_result = adapter.evaluate_candidate_step(KernelCandidateStepRequest(macro_step_time_s=0.1))
    assert step_result.accepted is True


def test_resume_from_snapshot_restores_adapter_delay_bundle_shape() -> None:
    network, runtime = _make_runtime_fixture()
    adapter = SplitKernelAdapter(network=network, runtime_orchestrator=runtime)
    runtime.restore_transport_runtime_state(_transport_runtime_payload())

    snapshot = network.save_runtime_snapshot()
    expected_transport_runtime_state = adapter.capture_delay_state()["transport_runtime_state"]

    runtime.restore_transport_runtime_state({})
    network.resume_from_snapshot(snapshot=snapshot)

    assert (
        adapter.capture_delay_state()["transport_runtime_state"] == expected_transport_runtime_state
    )

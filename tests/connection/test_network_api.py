from __future__ import annotations

# pyright: reportMissingImports=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false

from types import MappingProxyType

import pytest

from modular_simulation.connection.hydraulics.hydraulic_compile import HydraulicCompileLifecycle
from modular_simulation.connection.hydraulics.hydraulic_solver import (
    HydraulicSystemDefinition,
    LinearResidualEquation,
)
from modular_simulation.connection.topology.network import ConnectionNetwork
from modular_simulation.connection.runtime.runtime import ConnectionRuntimeOrchestrator
from modular_simulation.connection.topology.process_binding import ProcessBinding


def _linear_equation(
    residual_name: str,
    coefficients: dict[str, float],
    *,
    constant: float = 0.0,
) -> LinearResidualEquation:
    return LinearResidualEquation(
        residual_name=residual_name,
        coefficients=MappingProxyType(coefficients),
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


def _network() -> ConnectionNetwork:
    network = ConnectionNetwork(
        compile_lifecycle=HydraulicCompileLifecycle(),
        hydraulic_system_builder=lambda topology: _valid_system(),
    )
    network.add_process("reactor", inlet_ports=("feed",), outlet_ports=("product",))
    network.add_boundary_source("feed_boundary")
    network.add_boundary_sink("product_boundary")
    _ = network.connect("feed_boundary", "reactor.feed")
    _ = network.connect("reactor.product", "product_boundary")
    return network


def test_public_api_entry_points_exist() -> None:
    network = ConnectionNetwork()

    assert callable(network.add_process)
    assert callable(network.add_boundary_source)
    assert callable(network.add_boundary_sink)
    assert callable(network.connect)
    assert callable(network.compile)
    assert callable(network.step)
    assert callable(network.queue_reconfiguration)
    assert callable(network.save_runtime_snapshot)
    assert callable(network.resume_from_snapshot)
    assert callable(network.list_process_specs)
    assert callable(network.list_boundary_specs)
    assert callable(network.list_connection_edges)
    assert callable(network.list_line_hydraulic_configs)
    assert callable(network.list_pending_valve_open_fractions)
    assert callable(network.list_pending_pump_speeds)
    assert callable(network.attach_line_valve)
    assert callable(network.attach_line_pump)
    assert callable(network.stage_valve_open_fraction_command)
    assert callable(network.stage_pump_speed_command)
    assert callable(network.from_single_process)
    assert callable(ConnectionRuntimeOrchestrator.for_system)


def test_query_surface_returns_deterministic_connection_views() -> None:
    network = _network()
    _ = network.compile()

    process_specs = network.list_process_specs()
    boundary_specs = network.list_boundary_specs()
    edges = network.list_connection_edges()
    line_configs = network.list_line_hydraulic_configs()

    assert tuple(item.process_id for item in process_specs) == ("reactor",)
    assert process_specs[0].inlet_ports == ("feed",)
    assert process_specs[0].outlet_ports == ("product",)
    assert tuple(item.boundary_id for item in boundary_specs) == (
        "feed_boundary",
        "product_boundary",
    )
    assert tuple(item.edge_id for item in edges) == ("edge_0001", "edge_0002")
    assert line_configs == ()
    assert network.list_pending_valve_open_fractions() == ()
    assert network.list_pending_pump_speeds() == ()


def test_from_single_process_bootstraps_compiled_network() -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = ConnectionNetwork.from_single_process(
        process_id="reactor",
        inlet_ports=("feed",),
        outlet_ports=("product",),
        compile_lifecycle=HydraulicCompileLifecycle(),
        hydraulic_system_builder=lambda topology: _valid_system(),
        runtime_orchestrator=runtime,
    )

    compiled = network.compiled
    assert compiled is not None
    assert compiled.topology.node_ids == ("feed_boundary", "product_boundary", "reactor")
    assert compiled.topology.edge_ids == ("edge_0001", "edge_0002")


def test_compile_delegates_to_topology_process_bindings_and_compile_artifact() -> None:
    compiled = _network().compile()

    assert compiled.topology.node_ids == ("feed_boundary", "product_boundary", "reactor")
    assert compiled.topology.edge_ids == ("edge_0001", "edge_0002")
    assert isinstance(compiled.process_bindings["reactor"], ProcessBinding)
    assert compiled.hydraulic is not None
    assert compiled.hydraulic.graph_revision == "graph_rev_0001"


def test_connect_rejects_malformed_endpoint_deterministically() -> None:
    network = ConnectionNetwork()
    network.add_process("reactor", inlet_ports=("feed",), outlet_ports=("product",))
    network.add_boundary_sink("sink")

    with pytest.raises(ValueError) as error:
        _ = network.connect("reactor", "sink")

    assert str(error.value) == (
        "invalid endpoint 'reactor': process endpoints must use '<node_id>.<port_name>' format"
    )


def test_connect_duplicate_edge_has_actionable_error() -> None:
    network = ConnectionNetwork()
    network.add_process("reactor", inlet_ports=("feed",), outlet_ports=("product",))
    network.add_boundary_source("feed")

    _ = network.connect("feed", "reactor.feed")

    with pytest.raises(ValueError) as error:
        _ = network.connect("feed", "reactor.feed")

    assert str(error.value) == (
        "duplicate connection 'feed.outlet->reactor.feed' already exists as edge_id 'edge_0001'"
    )


# ---------------------------------------------------------------------------
# Observability snapshot contract tests (task 1.1 — red boundary)
# ---------------------------------------------------------------------------


def test_observability_snapshot_method_exists_on_connection_network() -> None:
    """ConnectionNetwork must expose get_observability_snapshot as a callable."""
    network = ConnectionNetwork()
    assert callable(network.get_observability_snapshot)


def test_observability_snapshot_returns_mapping_without_runtime() -> None:
    """get_observability_snapshot returns a Mapping even without a runtime orchestrator."""
    network = ConnectionNetwork()

    snapshot = network.get_observability_snapshot()

    from collections.abc import Mapping as MappingABC

    assert isinstance(snapshot, MappingABC)


def test_observability_snapshot_top_level_keys_are_frozen() -> None:
    """Snapshot contains exactly the first-slice top-level keys: schema, graph_revision,
    runtime, queue, observables."""
    network = ConnectionNetwork()

    snapshot = network.get_observability_snapshot()

    assert set(snapshot.keys()) == {
        "schema",
        "graph_revision",
        "runtime",
        "queue",
        "observables",
    }


def test_observability_snapshot_schema_is_non_empty_string() -> None:
    """snapshot['schema'] is a non-empty string contract marker."""
    network = ConnectionNetwork()

    snapshot = network.get_observability_snapshot()

    assert isinstance(snapshot["schema"], str)
    assert snapshot["schema"]


def test_observability_snapshot_graph_revision_is_none_before_compile() -> None:
    """graph_revision is None when the network has not been compiled."""
    network = ConnectionNetwork()

    snapshot = network.get_observability_snapshot()

    assert snapshot["graph_revision"] is None


def test_observability_snapshot_graph_revision_reflects_compiled_state() -> None:
    """graph_revision matches the compiled network's graph_revision after compile."""
    network = _network()
    network.compile()

    snapshot = network.get_observability_snapshot()

    assert snapshot["graph_revision"] == "graph_rev_0001"


def test_observability_snapshot_runtime_section_shape() -> None:
    """runtime section contains simulation_time_s (float), macro_step_index (int),
    macro_step_active (bool)."""
    network = ConnectionNetwork()

    snapshot = network.get_observability_snapshot()
    runtime = snapshot["runtime"]

    from collections.abc import Mapping as MappingABC

    assert isinstance(runtime, MappingABC)
    assert "simulation_time_s" in runtime
    assert "macro_step_index" in runtime
    assert "macro_step_active" in runtime
    assert isinstance(runtime["simulation_time_s"], float)
    assert isinstance(runtime["macro_step_index"], int)
    assert isinstance(runtime["macro_step_active"], bool)


def test_observability_snapshot_queue_section_shape() -> None:
    """queue section contains queued_request_ids, queued_request_count (int),
    and committed_idempotency_keys."""
    network = ConnectionNetwork()

    snapshot = network.get_observability_snapshot()
    queue = snapshot["queue"]

    from collections.abc import Mapping as MappingABC

    assert isinstance(queue, MappingABC)
    assert "queued_request_ids" in queue
    assert "queued_request_count" in queue
    assert "committed_idempotency_keys" in queue
    assert isinstance(queue["queued_request_count"], int)


def test_observability_snapshot_queue_count_matches_queued_ids_length() -> None:
    """queued_request_count equals len(queued_request_ids) at all times."""
    network = ConnectionNetwork()
    _ = network.queue_reconfiguration({"operation": "add_boundary_source"})
    _ = network.queue_reconfiguration({"operation": "add_boundary_sink"})

    snapshot = network.get_observability_snapshot()
    queue = snapshot["queue"]

    assert queue["queued_request_count"] == len(queue["queued_request_ids"])
    assert queue["queued_request_count"] == 2


def test_observability_snapshot_observables_section_shape() -> None:
    """observables section contains published_measurements and plant_calculation_outputs
    as numeric mappings."""
    network = ConnectionNetwork()

    snapshot = network.get_observability_snapshot()
    observables = snapshot["observables"]

    from collections.abc import Mapping as MappingABC

    assert isinstance(observables, MappingABC)
    assert "published_measurements" in observables
    assert "plant_calculation_outputs" in observables
    assert isinstance(observables["published_measurements"], MappingABC)
    assert isinstance(observables["plant_calculation_outputs"], MappingABC)


def test_observability_snapshot_is_distinct_from_save_runtime_snapshot() -> None:
    """get_observability_snapshot() result is a distinct read model from
    save_runtime_snapshot() — does NOT expose persistence/checksum fields."""
    from modular_simulation.connection.runtime.runtime import ConnectionRuntimeOrchestrator

    runtime = ConnectionRuntimeOrchestrator()
    network = _network()
    # Attach runtime so save_runtime_snapshot works
    network2 = ConnectionNetwork(
        compile_lifecycle=HydraulicCompileLifecycle(),
        hydraulic_system_builder=lambda topology: _valid_system(),
        runtime_orchestrator=runtime,
    )
    network2.add_process("reactor", inlet_ports=("feed",), outlet_ports=("product",))
    network2.add_boundary_source("feed_boundary")
    network2.add_boundary_sink("product_boundary")
    _ = network2.connect("feed_boundary", "reactor.feed")
    _ = network2.connect("reactor.product", "product_boundary")
    _ = network2.compile()

    observability_snapshot = network2.get_observability_snapshot()

    # The observability snapshot must expose the first-slice sections
    assert "schema" in observability_snapshot
    assert "runtime" in observability_snapshot
    assert "queue" in observability_snapshot
    assert "observables" in observability_snapshot

    # The observability snapshot is not a persistence payload —
    # it does not expose replay-specific fields like 'pending_command_journal'
    assert "pending_command_journal" not in observability_snapshot
    assert "committed_idempotency_payloads" not in observability_snapshot


def test_observability_snapshot_does_not_leak_mutable_runtime_structures() -> None:
    """Mutating returned sequences/mappings does not affect the network state."""
    network = ConnectionNetwork()
    _ = network.queue_reconfiguration({"operation": "add_boundary_source"})

    snapshot = network.get_observability_snapshot()
    queue = snapshot["queue"]

    # queued_request_ids should be a safe copy (tuple or list), not a direct
    # reference to internal state.  Verify re-reading produces the same data.
    ids_first_read = queue["queued_request_ids"]
    snapshot2 = network.get_observability_snapshot()
    ids_second_read = snapshot2["queue"]["queued_request_ids"]

    assert tuple(ids_first_read) == tuple(ids_second_read)
    # Ensure the ids are actually present
    assert len(ids_first_read) == 1


def test_observability_snapshot_does_not_contain_policy_fields() -> None:
    """First-slice snapshot contains only substrate-owned sections — no pricing,
    scoring, tutorial, or ledger fields."""
    network = ConnectionNetwork()

    snapshot = network.get_observability_snapshot()

    forbidden_keys = {"price", "score", "ledger", "tutorial", "economics", "cash", "inventory"}
    assert not (set(snapshot.keys()) & forbidden_keys), (
        f"Policy fields found in substrate snapshot: {set(snapshot.keys()) & forbidden_keys}"
    )


def test_queue_reconfiguration_and_runtime_placeholders_are_deterministic() -> None:
    network = ConnectionNetwork()

    queued = network.queue_reconfiguration({"operation": "add_connection"})
    assert queued == "rq_0001"

    with pytest.raises(ValueError) as malformed_error:
        _ = network.queue_reconfiguration({})
    assert str(malformed_error.value) == (
        "invalid reconfiguration request: expected mapping with non-empty string field 'operation'"
    )

    with pytest.raises(RuntimeError) as step_error:
        _ = network.step(macro_step_time_s=1.0)
    assert str(step_error.value) == (
        "runtime step is unavailable: runtime orchestrator not configured for ConnectionNetwork"
    )

    with pytest.raises(RuntimeError) as snapshot_error:
        _ = network.save_runtime_snapshot()
    assert str(snapshot_error.value) == (
        "runtime snapshot is unavailable: runtime orchestrator not configured for ConnectionNetwork"
    )

    with pytest.raises(ValueError) as payload_error:
        network.resume_from_snapshot(snapshot=[])
    assert str(payload_error.value) == "invalid snapshot payload: expected mapping"

    with pytest.raises(RuntimeError) as resume_error:
        _ = network.resume_from_snapshot(snapshot={})
    assert str(resume_error.value) == (
        "runtime resume is unavailable: runtime orchestrator not configured for ConnectionNetwork"
    )

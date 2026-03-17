from __future__ import annotations

import pytest

from modular_simulation.connection.domain.domain_contracts import (
    CommandEnvelope,
    ConnectionLine,
    ControllerBinding,
    JunctionProcess,
    MutationCommand,
    Port,
    ResistanceConfig,
    SensorBinding,
    UnitProcess,
    ValveConfig,
)


def test_junction_process_converts_to_junction_node_only() -> None:
    junction = JunctionProcess(
        junction_id="junction_mix_a",
        inlet_port_ids=("inlet_a", "inlet_b"),
        outlet_port_id="outlet",
    )

    as_junction = junction.as_junction_node()
    assert as_junction.junction_id == "junction_mix_a"
    assert as_junction.port_names == ("inlet_a", "inlet_b", "outlet")
    # Verify that DirectionalNodePorts helper does not expose as_process_node
    # to prevent junction identity from being treated as process identity
    node_ports = junction.node_ports()
    assert not hasattr(node_ports, "as_process_node")


def test_shared_node_port_helpers_preserve_unit_and_junction_identities() -> None:
    unit = UnitProcess(
        process_id="reactor_a",
        ports=(
            Port(port_id="feed", direction="inlet"),
            Port(port_id="product", direction="outlet"),
        ),
    )
    junction = JunctionProcess(
        junction_id="mix_a",
        inlet_port_ids=("feed_a", "feed_b"),
        outlet_port_id="product",
    )

    unit_ports = unit.node_ports()
    junction_ports = junction.node_ports()
    process_node = unit.as_process_node()
    junction_node = junction_ports.as_junction_node()

    assert type(unit_ports) is type(junction_ports)
    assert process_node.process_id == "reactor_a"
    assert not hasattr(process_node, "junction_id")
    assert junction_node.junction_id == "mix_a"
    assert not hasattr(junction_node, "process_id")
    assert unit_ports.all_port_ids() == ("feed", "product")
    assert junction_ports.all_port_ids() == ("feed_a", "feed_b", "product")


def test_serialize_and_validate_connection_and_binding_contracts() -> None:
    line = ConnectionLine(
        line_id="line_feed_0001",
        source_process_id="feed_boundary",
        source_port_id="outlet",
        target_process_id="reactor_a",
        target_port_id="feed",
        resistance=ResistanceConfig(mode="derived", radius_m=0.025, length_m=4.5),
        valve=ValveConfig(
            valve_id="valve_feed_0001",
            minimum_open_fraction=0.1,
            maximum_open_fraction=0.9,
            initial_open_fraction=0.5,
        ),
    )
    sensor = SensorBinding(
        sensor_id="sensor_line_feed",
        signal_key="line.flow",
        line_id="line_feed_0001",
    )
    controller = ControllerBinding(
        controller_id="controller_feed",
        sensor_id="sensor_line_feed",
        actuator_line_id="line_feed_0001",
    )

    assert line.as_connection_edge().edge_id == "line_feed_0001"
    assert sensor.model_dump()["line_id"] == "line_feed_0001"
    assert controller.model_dump()["mode"] == "auto"


def test_validate_command_envelope_fields_and_serialize_metadata() -> None:
    envelope = CommandEnvelope(
        idempotency_key="cmd_0001",
        expected_revision="graph_rev_0002",
        metadata={"source": "cli"},
        mutations=(
            MutationCommand.model_validate(
                {
                    "operation": "add_process",
                    "command_id": "cmd_add_process",
                    "process_id": "reactor_b",
                    "inlet_ports": ["feed"],
                    "outlet_ports": ["product"],
                }
            ),
        ),
    )

    assert envelope.idempotency_key == "cmd_0001"
    assert envelope.expected_revision == "graph_rev_0002"
    assert envelope.metadata == {"source": "cli"}
    assert envelope.mutations[0].as_mapping()["command_id"] == "cmd_add_process"


def test_invalid_direction_is_rejected_for_port_contract() -> None:
    with pytest.raises(ValueError, match="direction"):
        _ = Port.model_validate({"port_id": "feed", "direction": "side"})


def test_duplicate_id_is_rejected_for_process_port_ids() -> None:
    with pytest.raises(ValueError, match="duplicate process port ids"):
        _ = UnitProcess(
            process_id="reactor_a",
            ports=(
                Port(port_id="feed", direction="inlet"),
                Port(port_id="feed", direction="outlet"),
            ),
        )


def test_duplicate_id_is_rejected_for_mutation_command_ids() -> None:
    with pytest.raises(ValueError, match="duplicate mutation command ids"):
        _ = CommandEnvelope(
            mutations=(
                MutationCommand.model_validate(
                    {
                        "operation": "add_boundary_sink",
                        "command_id": "cmd_1",
                        "boundary_id": "sink_1",
                    }
                ),
                MutationCommand.model_validate(
                    {
                        "operation": "add_boundary_sink",
                        "command_id": "cmd_1",
                        "boundary_id": "sink_2",
                    }
                ),
            ),
        )

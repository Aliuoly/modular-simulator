from __future__ import annotations

from collections.abc import Mapping
from typing import cast

import pytest

from modular_simulation.cli import ModularCli
from modular_simulation.connection.domain.error_catalog import (
    CLI_ARGUMENT_ISSUE_CODE,
    extract_diagnostic_payload,
)


class _FakeNetwork:
    def __init__(self) -> None:
        self.queued_payloads: list[dict[str, object]] = []
        self.last_snapshot: dict[str, object] = {}

    def queue_reconfiguration(self, payload: object, /) -> str:
        if not isinstance(payload, Mapping):
            raise TypeError("payload must be a mapping")
        typed_payload = {
            str(key): value for key, value in cast(Mapping[object, object], payload).items()
        }
        self.queued_payloads.append(typed_payload)
        return f"rq-fake-{len(self.queued_payloads):03d}"

    def save_runtime_snapshot(self) -> Mapping[str, object]:
        self.last_snapshot = {
            "mock": True,
            "queued_count": len(self.queued_payloads),
        }
        return self.last_snapshot

    def resume_from_snapshot(self, *, snapshot: object) -> None:
        self.last_snapshot = {"loaded": snapshot}


def test_cli_immediate_commands_map_to_expected_backend_payloads() -> None:
    network = _FakeNetwork()
    cli = ModularCli(network=network)

    add_unit_request = cli.add_unit(
        "u1",
        inlet_ports=["feed"],
        outlet_ports=["product"],
        idempotency_key="cli-unit",
        expected_revision="graph_rev_0001",
        metadata={"source": "cli-test"},
    )
    add_port_request = cli.add_port(
        process_id="u1",
        port_id="recycle",
        direction="inlet",
    )
    connect_request = cli.connect(
        source="u1.product",
        target="u2.feed",
        line_id="line1",
    )
    configure_request = cli.configure_line(
        line_id="line1",
        radius_m=0.5,
        length_m=5.0,
    )
    cli.add_sensor(
        sensor_id="s1",
        signal_key="temperature",
        line_id="line1",
        metadata={"domain": "instrumentation"},
    )
    cli.bind_controller(
        controller_id="ctrl1",
        sensor_id="s1",
        actuator_line_id="line2",
        mode="auto",
        metadata={"domain": "control"},
    )

    assert (
        add_unit_request,
        add_port_request,
        connect_request,
        configure_request,
    ) == (
        "rq-fake-001",
        "rq-fake-002",
        "rq-fake-003",
        "rq-fake-004",
    )
    assert network.queued_payloads == [
        {
            "operation": "add_process",
            "process_id": "u1",
            "inlet_ports": ["feed"],
            "outlet_ports": ["product"],
            "idempotency_key": "cli-unit",
            "expected_revision": "graph_rev_0001",
            "metadata": {"source": "cli-test"},
        },
        {
            "operation": "add_inlet",
            "process_id": "u1",
            "direction": "inlet",
            "port_name": "recycle",
        },
        {
            "operation": "connect_line",
            "source": "u1.product",
            "target": "u2.feed",
            "line_id": "line1",
        },
        {
            "operation": "configure_line_geometry",
            "line_id": "line1",
            "radius_m": 0.5,
            "length_m": 5.0,
        },
        {
            "operation": "add_sensor",
            "sensor_id": "s1",
            "signal_key": "temperature",
            "line_id": "line1",
            "metadata": {"domain": "instrumentation"},
        },
        {
            "operation": "bind_controller",
            "controller_id": "ctrl1",
            "sensor_id": "s1",
            "actuator_line_id": "line2",
            "mode": "auto",
            "metadata": {"domain": "control"},
        },
    ]

    snapshot = cli.save()
    assert snapshot == {"mock": True, "queued_count": 6}


def test_cli_tx_commit_maps_pending_mutations_to_single_envelope() -> None:
    network = _FakeNetwork()
    cli = ModularCli(network=network)

    cli.tx_begin()
    _ = cli.add_unit("tx_unit", inlet_ports=["inlet"], outlet_ports=["outlet"])
    _ = cli.add_port(process_id="tx_unit", port_id="purge", direction="outlet")
    _ = cli.connect(
        source="tx_unit.outlet",
        target="sink.inlet",
        line_id="tx_line",
    )
    cli.tx_commit()

    assert len(network.queued_payloads) == 1
    assert network.queued_payloads[0] == {
        "idempotency_key": None,
        "expected_revision": None,
        "metadata": {},
        "mutations": (
            {
                "operation": "add_process",
                "command_id": None,
                "process_id": "tx_unit",
                "inlet_ports": ("inlet",),
                "outlet_ports": ("outlet",),
            },
            {
                "operation": "add_outlet",
                "command_id": None,
                "process_id": "tx_unit",
                "direction": "outlet",
                "port_name": "purge",
            },
            {
                "operation": "connect_line",
                "command_id": None,
                "source": "tx_unit.outlet",
                "target": "sink.inlet",
                "line_id": "tx_line",
            },
        ),
    }


def test_cli_invalid_port_direction_uses_structured_diagnostic_payload() -> None:
    network = _FakeNetwork()
    cli = ModularCli(network=network)

    with pytest.raises(ValueError) as error:
        _ = cli.add_port(process_id="u1", port_id="p1", direction="invalid")

    payload = extract_diagnostic_payload(error.value)
    assert payload is not None
    assert payload["code"] == CLI_ARGUMENT_ISSUE_CODE
    assert payload["path"] == "direction"
    assert payload["hint"] == "use one of: inlet, outlet"

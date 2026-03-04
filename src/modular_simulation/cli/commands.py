from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Literal, Protocol, cast

from modular_simulation.connection.error_catalog import (
    CLI_ARGUMENT_ISSUE_CODE,
    diagnostic_value_error,
)
from modular_simulation.connection.network import ConnectionNetwork
from modular_simulation.connection.domain_contracts import (
    Port,
    UnitProcess,
)
from modular_simulation.connection.reconfiguration_api import (
    DynamicUnitPortReconfigurationApi,
    DynamicConnectionLineReconfigurationApi,
)
from modular_simulation.connection.domain_contracts import (
    validate_command_envelope,
)
from modular_simulation.cli.spec_workflow import apply_spec_delta, compile_spec_delta


class _CliNetworkLike(Protocol):
    def queue_reconfiguration(self, request: object, /) -> str: ...

    def save_runtime_snapshot(self) -> Mapping[str, object]: ...

    def resume_from_snapshot(self, *, snapshot: object) -> None: ...


class ModularCli:
    """Minimal CLI facade exposing a 1:1 mapping to backend envelopes.

    This class keeps a tiny state and routes commands either directly
    to the backend envelopes (immediate mode) or accumulates mutations
    for a simple transaction (tx) mode.
    """

    def __init__(self, network: _CliNetworkLike):
        self._network: _CliNetworkLike = network
        network_for_api = cast(ConnectionNetwork, cast(object, network))
        self._unit_api: DynamicUnitPortReconfigurationApi = DynamicUnitPortReconfigurationApi(
            network=network_for_api
        )
        self._line_api: DynamicConnectionLineReconfigurationApi = (
            DynamicConnectionLineReconfigurationApi(network=network_for_api)
        )
        self._in_tx: bool = False
        self._pending_mutations: list[dict[str, object]] = []

    # --- transaction helpers ---
    def tx_begin(self) -> None:
        self._in_tx = True
        self._pending_mutations = []

    def tx_commit(self) -> None:
        if not self._pending_mutations:
            raise diagnostic_value_error(
                code=CLI_ARGUMENT_ISSUE_CODE,
                message="no mutations to commit",
                path="tx.pending_mutations",
                hint="queue at least one mutation before tx_commit",
            )
        envelope = validate_command_envelope(
            idempotency_key=None,
            expected_revision=None,
            metadata={},
            mutations=tuple(dict(mutation) for mutation in self._pending_mutations),
        )
        payload = envelope.model_dump(mode="python", by_alias=False)
        _ = self._network.queue_reconfiguration(payload)
        self._pending_mutations = []
        self._in_tx = False

    def tx_rollback(self) -> None:
        self._pending_mutations = []
        self._in_tx = False

    # --- command implementations (1:1 mapping) ---
    def add_unit(
        self,
        unit_id: str,
        inlet_ports: Iterable[str],
        outlet_ports: Iterable[str],
        *,
        idempotency_key: str | None = None,
        expected_revision: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ):
        ports = [Port(port_id=p, direction="inlet") for p in inlet_ports] + [
            Port(port_id=p, direction="outlet") for p in outlet_ports
        ]
        unit = UnitProcess(process_id=unit_id, ports=tuple(ports))
        if self._in_tx:
            self._pending_mutations.append(
                {
                    "operation": "add_process",
                    "process_id": unit.process_id,
                    "inlet_ports": unit.inlet_port_ids(),
                    "outlet_ports": unit.outlet_port_ids(),
                }
            )
            return
        return self._unit_api.add_unit_process(
            unit,
            idempotency_key=idempotency_key,
            expected_revision=expected_revision,
            metadata=metadata,
        )

    def add_port(
        self,
        process_id: str,
        port_id: str,
        direction: str,
        *,
        idempotency_key: str | None = None,
        expected_revision: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ):
        if direction not in {"inlet", "outlet"}:
            raise diagnostic_value_error(
                code=CLI_ARGUMENT_ISSUE_CODE,
                message="direction must be 'inlet' or 'outlet'",
                path="direction",
                hint="use one of: inlet, outlet",
            )
        normalized_direction = cast(Literal["inlet", "outlet"], direction)
        port = Port(port_id=port_id, direction=normalized_direction)
        if self._in_tx:
            mutation: dict[str, object] = {
                "operation": f"add_{normalized_direction}",
                "process_id": process_id,
                "direction": normalized_direction,
                "port_name": port_id,
            }
            self._pending_mutations.append(mutation)
            return
        return self._unit_api.add_port(
            process_id=process_id,
            port=port,
            idempotency_key=idempotency_key,
            expected_revision=expected_revision,
            metadata=metadata,
        )

    def connect(
        self,
        source: str,
        target: str,
        line_id: str | None = None,
        *,
        idempotency_key: str | None = None,
        expected_revision: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ):
        if self._in_tx:
            mutation: dict[str, object] = {
                "operation": "connect_line",
                "source": source,
                "target": target,
            }
            if line_id is not None:
                mutation["line_id"] = line_id
            self._pending_mutations.append(mutation)
            return
        return self._line_api.connect_line(
            source=source,
            target=target,
            line_id=line_id,
            idempotency_key=idempotency_key,
            expected_revision=expected_revision,
            metadata=metadata,
        )

    def configure_line(
        self,
        line_id: str,
        radius_m: float,
        length_m: float,
        equation_name: str | None = None,
        resistance_parameter_name: str | None = None,
        *,
        idempotency_key: str | None = None,
        expected_revision: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ):
        if self._in_tx:
            mutation: dict[str, object] = {
                "operation": "configure_line_geometry",
                "line_id": line_id,
                "radius_m": radius_m,
                "length_m": length_m,
            }
            if equation_name is not None:
                mutation["equation_name"] = equation_name
            if resistance_parameter_name is not None:
                mutation["resistance_parameter_name"] = resistance_parameter_name
            self._pending_mutations.append(mutation)
            return
        return self._line_api.configure_line_geometry(
            line_id=line_id,
            radius_m=radius_m,
            length_m=length_m,
            equation_name=equation_name,
            resistance_parameter_name=resistance_parameter_name,
            idempotency_key=idempotency_key,
            expected_revision=expected_revision,
            metadata=metadata,
        )

    def add_sensor(
        self,
        sensor_id: str,
        signal_key: str,
        line_id: str | None = None,
        process_id: str | None = None,
        port_id: str | None = None,
        *,
        metadata: Mapping[str, object] | None = None,
    ) -> None:
        if line_id is None and (process_id is None or port_id is None):
            raise diagnostic_value_error(
                code=CLI_ARGUMENT_ISSUE_CODE,
                message="sensor binding requires either line_id or (process_id and port_id)",
                path="line_id/process_id/port_id",
                hint="provide line_id, or provide both process_id and port_id",
            )
        if self._in_tx:
            mutation: dict[str, object] = {
                "operation": "add_sensor",
                "sensor_id": sensor_id,
                "signal_key": signal_key,
            }
            if line_id is not None:
                mutation["line_id"] = line_id
            else:
                mutation["process_id"] = process_id
                mutation["port_id"] = port_id
            if metadata is not None:
                mutation["metadata"] = dict(metadata)
            self._pending_mutations.append(mutation)
            return
        # Immediate path: build a sensor-binding envelope using a mutation and validate envelope
        immediate_mutation: dict[str, object] = {
            "operation": "add_sensor",
            "sensor_id": sensor_id,
            "signal_key": signal_key,
        }
        if line_id is not None:
            immediate_mutation["line_id"] = line_id
        else:
            immediate_mutation["process_id"] = process_id
            immediate_mutation["port_id"] = port_id
        if metadata is not None:
            immediate_mutation["metadata"] = dict(metadata)
        _ = self._network.queue_reconfiguration(immediate_mutation)

    def bind_controller(
        self,
        controller_id: str,
        sensor_id: str,
        actuator_line_id: str,
        mode: str = "auto",
        *,
        metadata: Mapping[str, object] | None = None,
    ) -> None:
        if self._in_tx:
            mutation: dict[str, object] = {
                "operation": "bind_controller",
                "controller_id": controller_id,
                "sensor_id": sensor_id,
                "actuator_line_id": actuator_line_id,
                "mode": mode,
            }
            self._pending_mutations.append(mutation)
            return
        immediate_mutation: dict[str, object] = {
            "operation": "bind_controller",
            "controller_id": controller_id,
            "sensor_id": sensor_id,
            "actuator_line_id": actuator_line_id,
            "mode": mode,
        }
        if metadata is not None:
            immediate_mutation["metadata"] = dict(metadata)
        _ = self._network.queue_reconfiguration(immediate_mutation)

    def save(self) -> Mapping[str, object]:
        return self._network.save_runtime_snapshot()

    def load(self, snapshot_path: str) -> None:
        # Best-effort: load a JSON/YAML-like snapshot and pass it to the network if supported.
        # Tests provide a minimal fake network; just read the file and attempt to resume if API exists.
        with open(snapshot_path, "r", encoding="utf-8") as fh:
            import json

            payload = cast(object, json.load(fh))
        resume = getattr(self._network, "resume_from_snapshot", None)
        if callable(resume):
            _ = resume(snapshot=payload)
        else:
            raise NotImplementedError(
                "load is not supported by the provided network in this test environment"
            )

    def spec_diff(self, *, spec_path: str) -> Mapping[str, object]:
        if not isinstance(self._network, ConnectionNetwork):
            raise TypeError("spec workflow requires ConnectionNetwork")
        delta = compile_spec_delta(network=self._network, spec_path=spec_path)
        return delta.as_mapping()

    def spec_apply(
        self,
        *,
        spec_path: str,
        macro_step_time_s: float = 0.0,
    ) -> Mapping[str, object]:
        if not isinstance(self._network, ConnectionNetwork):
            raise TypeError("spec workflow requires ConnectionNetwork")
        return apply_spec_delta(
            network=self._network,
            spec_path=spec_path,
            macro_step_time_s=macro_step_time_s,
        )

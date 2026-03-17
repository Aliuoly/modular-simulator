from __future__ import annotations

from collections.abc import Mapping

from ..topology.network import ConnectionNetwork
from .domain_contracts import (
    ConnectionLine,
    JunctionProcess,
    Port,
    UnitProcess,
    ValveConfig,
)
from .error_catalog import (
    VALIDATION_FAILURE_CODE,
    diagnostic_value_error,
)


class DynamicUnitPortReconfigurationApi:
    def __init__(self, *, network: ConnectionNetwork) -> None:
        self._network: ConnectionNetwork = network

    def add_unit_process(
        self,
        process: UnitProcess,
        *,
        idempotency_key: str | None = None,
        expected_revision: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> str:
        payload: dict[str, object] = {
            "operation": "add_process",
            "process_id": process.process_id,
            "inlet_ports": list(process.inlet_port_ids()),
            "outlet_ports": list(process.outlet_port_ids()),
        }
        return self._queue_request(
            payload=payload,
            idempotency_key=idempotency_key,
            expected_revision=expected_revision,
            metadata=metadata,
        )

    def remove_unit_process(
        self,
        *,
        process_id: str,
        idempotency_key: str | None = None,
        expected_revision: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> str:
        payload: dict[str, object] = {
            "operation": "remove_unit",
            "process_id": process_id,
        }
        return self._queue_request(
            payload=payload,
            idempotency_key=idempotency_key,
            expected_revision=expected_revision,
            metadata=metadata,
        )

    def add_junction_process(
        self,
        process: JunctionProcess,
        *,
        idempotency_key: str | None = None,
        expected_revision: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> str:
        payload: dict[str, object] = {
            "operation": "add_junction",
            "junction_id": process.junction_id,
            "inlet_ports": list(process.inlet_port_ids),
            "outlet_ports": [process.outlet_port_id],
        }
        return self._queue_request(
            payload=payload,
            idempotency_key=idempotency_key,
            expected_revision=expected_revision,
            metadata=metadata,
        )

    def remove_junction_process(
        self,
        *,
        process_id: str,
        idempotency_key: str | None = None,
        expected_revision: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> str:
        return self._queue_request(
            payload={
                "operation": "remove_junction",
                "junction_id": process_id,
            },
            idempotency_key=idempotency_key,
            expected_revision=expected_revision,
            metadata=metadata,
        )

    def add_inlet(
        self,
        *,
        process_id: str,
        port_id: str,
        idempotency_key: str | None = None,
        expected_revision: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> str:
        return self._queue_port_operation(
            operation="add_inlet",
            process_id=process_id,
            direction="inlet",
            port_id=port_id,
            idempotency_key=idempotency_key,
            expected_revision=expected_revision,
            metadata=metadata,
        )

    def add_outlet(
        self,
        *,
        process_id: str,
        port_id: str,
        idempotency_key: str | None = None,
        expected_revision: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> str:
        return self._queue_port_operation(
            operation="add_outlet",
            process_id=process_id,
            direction="outlet",
            port_id=port_id,
            idempotency_key=idempotency_key,
            expected_revision=expected_revision,
            metadata=metadata,
        )

    def remove_inlet(
        self,
        *,
        process_id: str,
        port_id: str,
        idempotency_key: str | None = None,
        expected_revision: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> str:
        self._validate_port_not_connected(process_id=process_id, port_id=port_id)
        return self._queue_port_operation(
            operation="remove_inlet",
            process_id=process_id,
            direction="inlet",
            port_id=port_id,
            idempotency_key=idempotency_key,
            expected_revision=expected_revision,
            metadata=metadata,
        )

    def remove_outlet(
        self,
        *,
        process_id: str,
        port_id: str,
        idempotency_key: str | None = None,
        expected_revision: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> str:
        self._validate_port_not_connected(process_id=process_id, port_id=port_id)
        return self._queue_port_operation(
            operation="remove_outlet",
            process_id=process_id,
            direction="outlet",
            port_id=port_id,
            idempotency_key=idempotency_key,
            expected_revision=expected_revision,
            metadata=metadata,
        )

    def add_port(
        self,
        *,
        process_id: str,
        port: Port,
        idempotency_key: str | None = None,
        expected_revision: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> str:
        if port.direction == "inlet":
            return self.add_inlet(
                process_id=process_id,
                port_id=port.port_id,
                idempotency_key=idempotency_key,
                expected_revision=expected_revision,
                metadata=metadata,
            )
        return self.add_outlet(
            process_id=process_id,
            port_id=port.port_id,
            idempotency_key=idempotency_key,
            expected_revision=expected_revision,
            metadata=metadata,
        )

    def remove_port(
        self,
        *,
        process_id: str,
        port: Port,
        idempotency_key: str | None = None,
        expected_revision: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> str:
        if port.direction == "inlet":
            return self.remove_inlet(
                process_id=process_id,
                port_id=port.port_id,
                idempotency_key=idempotency_key,
                expected_revision=expected_revision,
                metadata=metadata,
            )
        return self.remove_outlet(
            process_id=process_id,
            port_id=port.port_id,
            idempotency_key=idempotency_key,
            expected_revision=expected_revision,
            metadata=metadata,
        )

    def _queue_port_operation(
        self,
        *,
        operation: str,
        process_id: str,
        direction: str,
        port_id: str,
        idempotency_key: str | None,
        expected_revision: str | None,
        metadata: Mapping[str, object] | None,
    ) -> str:
        payload: dict[str, object] = {
            "operation": operation,
            "process_id": process_id,
            "direction": direction,
            "port_name": port_id,
        }
        return self._queue_request(
            payload=payload,
            idempotency_key=idempotency_key,
            expected_revision=expected_revision,
            metadata=metadata,
        )

    def _validate_port_not_connected(self, *, process_id: str, port_id: str) -> None:
        connected_edge_ids = self._network.list_incident_edge_ids(
            node_id=process_id, port_name=port_id
        )
        if connected_edge_ids:
            raise diagnostic_value_error(
                code=VALIDATION_FAILURE_CODE,
                message=(
                    f"cannot remove process endpoint '{process_id}.{port_id}': connected edges exist {connected_edge_ids!r}"
                ),
                path=f"{process_id}.{port_id}",
                hint="remove or detach connected edges before removing process ports",
            )

    def _queue_request(
        self,
        *,
        payload: Mapping[str, object],
        idempotency_key: str | None,
        expected_revision: str | None,
        metadata: Mapping[str, object] | None,
    ) -> str:
        request_payload: dict[str, object] = dict(payload)
        if idempotency_key is not None:
            request_payload["idempotency_key"] = idempotency_key
        if expected_revision is not None:
            request_payload["expected_revision"] = expected_revision
        if metadata is not None:
            request_payload["metadata"] = dict(metadata)
        return self._network.queue_reconfiguration(request_payload)


class DynamicConnectionLineReconfigurationApi:
    def __init__(self, *, network: ConnectionNetwork) -> None:
        self._network: ConnectionNetwork = network

    def connect_line(
        self,
        *,
        source: str,
        target: str,
        line_id: str | None = None,
        idempotency_key: str | None = None,
        expected_revision: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> str:
        payload: dict[str, object] = {
            "operation": "connect_line",
            "source": source,
            "target": target,
        }
        if line_id is not None:
            payload["line_id"] = line_id
        return self._queue_request(
            payload=payload,
            idempotency_key=idempotency_key,
            expected_revision=expected_revision,
            metadata=metadata,
        )

    def connect_from_contract(
        self,
        line: ConnectionLine,
        *,
        idempotency_key: str | None = None,
        expected_revision: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> str:
        source = f"{line.source_process_id}.{line.source_port_id}"
        target = f"{line.target_process_id}.{line.target_port_id}"
        return self.connect_line(
            source=source,
            target=target,
            line_id=line.line_id,
            idempotency_key=idempotency_key,
            expected_revision=expected_revision,
            metadata=metadata,
        )

    def disconnect_line(
        self,
        *,
        line_id: str | None = None,
        source: str | None = None,
        target: str | None = None,
        idempotency_key: str | None = None,
        expected_revision: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> str:
        payload: dict[str, object] = {"operation": "disconnect_line"}
        if line_id is not None:
            payload["line_id"] = line_id
        if source is not None:
            payload["source"] = source
        if target is not None:
            payload["target"] = target
        return self._queue_request(
            payload=payload,
            idempotency_key=idempotency_key,
            expected_revision=expected_revision,
            metadata=metadata,
        )

    def configure_line_geometry(
        self,
        *,
        line_id: str,
        radius_m: float,
        length_m: float,
        equation_name: str | None = None,
        resistance_parameter_name: str | None = None,
        idempotency_key: str | None = None,
        expected_revision: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> str:
        payload: dict[str, object] = {
            "operation": "configure_line_geometry",
            "line_id": line_id,
            "radius_m": radius_m,
            "length_m": length_m,
        }
        if equation_name is not None:
            payload["equation_name"] = equation_name
        if resistance_parameter_name is not None:
            payload["resistance_parameter_name"] = resistance_parameter_name
        return self._queue_request(
            payload=payload,
            idempotency_key=idempotency_key,
            expected_revision=expected_revision,
            metadata=metadata,
        )

    def use_derived_resistance(
        self,
        *,
        line_id: str,
        idempotency_key: str | None = None,
        expected_revision: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> str:
        return self._queue_request(
            payload={
                "operation": "configure_line_resistance",
                "line_id": line_id,
                "mode": "derived",
            },
            idempotency_key=idempotency_key,
            expected_revision=expected_revision,
            metadata=metadata,
        )

    def set_manual_resistance(
        self,
        *,
        line_id: str,
        manual_value: float,
        idempotency_key: str | None = None,
        expected_revision: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> str:
        return self._queue_request(
            payload={
                "operation": "configure_line_resistance",
                "line_id": line_id,
                "mode": "manual_override",
                "manual_value": manual_value,
            },
            idempotency_key=idempotency_key,
            expected_revision=expected_revision,
            metadata=metadata,
        )

    def attach_line_valve(
        self,
        *,
        line_id: str,
        valve: ValveConfig,
        equation_name: str | None = None,
        resistance_parameter_name: str | None = None,
        idempotency_key: str | None = None,
        expected_revision: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> str:
        payload: dict[str, object] = {
            "operation": "attach_line_valve",
            "line_id": line_id,
            "valve_id": valve.valve_id,
            "minimum_open_fraction": valve.minimum_open_fraction,
            "maximum_open_fraction": valve.maximum_open_fraction,
            "initial_open_fraction": valve.initial_open_fraction,
        }
        if equation_name is not None:
            payload["equation_name"] = equation_name
        if resistance_parameter_name is not None:
            payload["resistance_parameter_name"] = resistance_parameter_name
        return self._queue_request(
            payload=payload,
            idempotency_key=idempotency_key,
            expected_revision=expected_revision,
            metadata=metadata,
        )

    def set_valve_open_fraction(
        self,
        *,
        actuator_tag: str,
        open_fraction: float,
        idempotency_key: str | None = None,
        expected_revision: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> str:
        return self._queue_request(
            payload={
                "operation": "set_valve_open_fraction",
                "actuator_tag": actuator_tag,
                "open_fraction": open_fraction,
            },
            idempotency_key=idempotency_key,
            expected_revision=expected_revision,
            metadata=metadata,
        )

    def attach_line_pump(
        self,
        *,
        line_id: str,
        pump_id: str,
        initial_pump_speed: float = 0.0,
        equation_name: str | None = None,
        pump_parameter_name: str | None = None,
        idempotency_key: str | None = None,
        expected_revision: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> str:
        payload: dict[str, object] = {
            "operation": "attach_line_pump",
            "line_id": line_id,
            "pump_id": pump_id,
            "initial_pump_speed": initial_pump_speed,
        }
        if equation_name is not None:
            payload["equation_name"] = equation_name
        if pump_parameter_name is not None:
            payload["pump_parameter_name"] = pump_parameter_name
        return self._queue_request(
            payload=payload,
            idempotency_key=idempotency_key,
            expected_revision=expected_revision,
            metadata=metadata,
        )

    def set_pump_speed(
        self,
        *,
        actuator_tag: str,
        pump_speed: float,
        idempotency_key: str | None = None,
        expected_revision: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> str:
        return self._queue_request(
            payload={
                "operation": "set_pump_speed",
                "actuator_tag": actuator_tag,
                "pump_speed": pump_speed,
            },
            idempotency_key=idempotency_key,
            expected_revision=expected_revision,
            metadata=metadata,
        )

    def attach_line_heat_actuator(
        self,
        *,
        line_id: str,
        heat_actuator_id: str,
        initial_heat_rate: float = 0.0,
        idempotency_key: str | None = None,
        expected_revision: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> str:
        return self._queue_request(
            payload={
                "operation": "attach_line_heat_actuator",
                "line_id": line_id,
                "heat_actuator_id": heat_actuator_id,
                "initial_heat_rate": initial_heat_rate,
            },
            idempotency_key=idempotency_key,
            expected_revision=expected_revision,
            metadata=metadata,
        )

    def set_heat_actuator_rate(
        self,
        *,
        actuator_tag: str,
        heat_rate: float,
        idempotency_key: str | None = None,
        expected_revision: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> str:
        return self._queue_request(
            payload={
                "operation": "set_heat_actuator_rate",
                "actuator_tag": actuator_tag,
                "heat_rate": heat_rate,
            },
            idempotency_key=idempotency_key,
            expected_revision=expected_revision,
            metadata=metadata,
        )

    def _queue_request(
        self,
        *,
        payload: Mapping[str, object],
        idempotency_key: str | None,
        expected_revision: str | None,
        metadata: Mapping[str, object] | None,
    ) -> str:
        request_payload: dict[str, object] = dict(payload)
        if idempotency_key is not None:
            request_payload["idempotency_key"] = idempotency_key
        if expected_revision is not None:
            request_payload["expected_revision"] = expected_revision
        if metadata is not None:
            request_payload["metadata"] = dict(metadata)
        return self._network.queue_reconfiguration(request_payload)


__all__ = ["DynamicConnectionLineReconfigurationApi", "DynamicUnitPortReconfigurationApi"]

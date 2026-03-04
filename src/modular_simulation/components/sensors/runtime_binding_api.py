from __future__ import annotations

from collections.abc import Mapping

from modular_simulation.connection.domain_contracts import SensorBinding
from modular_simulation.connection.network import ConnectionNetwork


class SensorRuntimeBindingApi:
    def __init__(self, *, network: ConnectionNetwork) -> None:
        self._network: ConnectionNetwork = network

    def create_sensor(
        self,
        *,
        sensor_id: str,
        signal_key: str,
        process_id: str | None = None,
        port_id: str | None = None,
        line_id: str | None = None,
        sensor_type: str = "SampledDelayedSensor",
        sensor_module: str = "modular_simulation.components.sensors.sampled_delayed_sensor",
        sensor_config: Mapping[str, object] | None = None,
        binding_metadata: Mapping[str, object] | None = None,
        idempotency_key: str | None = None,
        expected_revision: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> str:
        binding = SensorBinding(
            sensor_id=sensor_id,
            signal_key=signal_key,
            process_id=process_id,
            port_id=port_id,
            line_id=line_id,
            metadata={} if binding_metadata is None else dict(binding_metadata),
        )
        payload: dict[str, object] = {
            "operation": "create_sensor",
            "sensor_id": binding.sensor_id,
            "signal_key": binding.signal_key,
            "sensor_type": sensor_type,
            "sensor_module": sensor_module,
            "sensor_config": {} if sensor_config is None else dict(sensor_config),
            "metadata": dict(binding.metadata),
        }
        if binding.process_id is not None:
            payload["process_id"] = binding.process_id
        if binding.port_id is not None:
            payload["port_id"] = binding.port_id
        if binding.line_id is not None:
            payload["line_id"] = binding.line_id
        return self._queue_request(
            payload=payload,
            idempotency_key=idempotency_key,
            expected_revision=expected_revision,
            metadata=metadata,
        )

    def bind_sensor(
        self,
        *,
        sensor_id: str,
        signal_key: str,
        process_id: str | None = None,
        port_id: str | None = None,
        line_id: str | None = None,
        binding_metadata: Mapping[str, object] | None = None,
        idempotency_key: str | None = None,
        expected_revision: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> str:
        binding = SensorBinding(
            sensor_id=sensor_id,
            signal_key=signal_key,
            process_id=process_id,
            port_id=port_id,
            line_id=line_id,
            metadata={} if binding_metadata is None else dict(binding_metadata),
        )
        payload: dict[str, object] = {
            "operation": "bind_sensor",
            "sensor_id": binding.sensor_id,
            "signal_key": binding.signal_key,
            "metadata": dict(binding.metadata),
        }
        if binding.process_id is not None:
            payload["process_id"] = binding.process_id
        if binding.port_id is not None:
            payload["port_id"] = binding.port_id
        if binding.line_id is not None:
            payload["line_id"] = binding.line_id
        return self._queue_request(
            payload=payload,
            idempotency_key=idempotency_key,
            expected_revision=expected_revision,
            metadata=metadata,
        )

    def unbind_sensor(
        self,
        *,
        sensor_id: str,
        idempotency_key: str | None = None,
        expected_revision: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> str:
        return self._queue_request(
            payload={
                "operation": "unbind_sensor",
                "sensor_id": sensor_id,
            },
            idempotency_key=idempotency_key,
            expected_revision=expected_revision,
            metadata=metadata,
        )

    def remove_sensor(
        self,
        *,
        sensor_id: str,
        idempotency_key: str | None = None,
        expected_revision: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> str:
        return self._queue_request(
            payload={
                "operation": "remove_sensor",
                "sensor_id": sensor_id,
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


__all__ = ["SensorRuntimeBindingApi"]

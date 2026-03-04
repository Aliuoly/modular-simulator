from __future__ import annotations

from collections.abc import Mapping

from modular_simulation.connection.network import ConnectionNetwork


class ControllerRuntimeWiringApi:
    def __init__(self, *, network: ConnectionNetwork) -> None:
        self._network: ConnectionNetwork = network

    def create_controller(
        self,
        *,
        controller_id: str,
        controller_type: str,
        controller_module: str,
        controller_config: Mapping[str, object] | None = None,
        metadata: Mapping[str, object] | None = None,
        idempotency_key: str | None = None,
        expected_revision: str | None = None,
    ) -> str:
        payload: dict[str, object] = {
            "operation": "create_controller",
            "controller_id": controller_id,
            "controller_type": controller_type,
            "controller_module": controller_module,
            "controller_config": {} if controller_config is None else dict(controller_config),
        }
        if metadata is not None:
            payload["metadata"] = dict(metadata)
        return self._queue_request(
            payload=payload,
            idempotency_key=idempotency_key,
            expected_revision=expected_revision,
        )

    def bind_controller_input(
        self,
        *,
        controller_id: str,
        signal_key: str,
        idempotency_key: str | None = None,
        expected_revision: str | None = None,
    ) -> str:
        return self._queue_request(
            payload={
                "operation": "bind_controller_input",
                "controller_id": controller_id,
                "signal_key": signal_key,
            },
            idempotency_key=idempotency_key,
            expected_revision=expected_revision,
        )

    def bind_controller_output(
        self,
        *,
        controller_id: str,
        actuator_tag: str,
        idempotency_key: str | None = None,
        expected_revision: str | None = None,
    ) -> str:
        return self._queue_request(
            payload={
                "operation": "bind_controller_output",
                "controller_id": controller_id,
                "actuator_tag": actuator_tag,
            },
            idempotency_key=idempotency_key,
            expected_revision=expected_revision,
        )

    def configure_controller_mode(
        self,
        *,
        controller_id: str,
        mode: str,
        idempotency_key: str | None = None,
        expected_revision: str | None = None,
    ) -> str:
        return self._queue_request(
            payload={
                "operation": "configure_controller_mode",
                "controller_id": controller_id,
                "mode": mode,
            },
            idempotency_key=idempotency_key,
            expected_revision=expected_revision,
        )

    def activate_controller(
        self,
        *,
        controller_id: str,
        idempotency_key: str | None = None,
        expected_revision: str | None = None,
    ) -> str:
        return self._queue_request(
            payload={
                "operation": "activate_controller",
                "controller_id": controller_id,
            },
            idempotency_key=idempotency_key,
            expected_revision=expected_revision,
        )

    def _queue_request(
        self,
        *,
        payload: Mapping[str, object],
        idempotency_key: str | None,
        expected_revision: str | None,
    ) -> str:
        request_payload: dict[str, object] = dict(payload)
        if idempotency_key is not None:
            request_payload["idempotency_key"] = idempotency_key
        if expected_revision is not None:
            request_payload["expected_revision"] = expected_revision
        return self._network.queue_reconfiguration(request_payload)


__all__ = ["ControllerRuntimeWiringApi"]

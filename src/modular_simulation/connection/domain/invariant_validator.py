from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json
from typing import Literal

from ..topology.network import ConnectionNetwork
from .domain_contracts import (
    ReconfigurationRequestMetadata,
    validate_reconfiguration_request_metadata,
)
from .error_catalog import (
    INVARIANT_FAILURE_CODE,
    DiagnosticPayload,
    DiagnosticValueError,
    build_diagnostic_payload,
)

DestructiveEditMode = Literal["hard_fail", "safe_detach"]
RemovalClass = Literal["remove_unit", "remove_port", "remove_edge", "remove_junction"]
DependencyClass = Literal["topology.edge", "control.dependency"]
PolicyDecision = Literal["block", "detach"]

DESTRUCTIVE_EDIT_POLICY_MATRIX: dict[
    RemovalClass, dict[DependencyClass, dict[DestructiveEditMode, PolicyDecision]]
] = {
    "remove_unit": {
        "topology.edge": {"hard_fail": "block", "safe_detach": "detach"},
        "control.dependency": {"hard_fail": "block", "safe_detach": "detach"},
    },
    "remove_port": {
        "topology.edge": {"hard_fail": "block", "safe_detach": "detach"},
        "control.dependency": {"hard_fail": "block", "safe_detach": "detach"},
    },
    "remove_edge": {
        "topology.edge": {"hard_fail": "block", "safe_detach": "detach"},
        "control.dependency": {"hard_fail": "block", "safe_detach": "detach"},
    },
    "remove_junction": {
        "topology.edge": {"hard_fail": "block", "safe_detach": "detach"},
        "control.dependency": {"hard_fail": "block", "safe_detach": "detach"},
    },
}


@dataclass(frozen=True)
class DestructiveEditValidationPlan:
    operation: str
    removal_class: RemovalClass
    target_reference: str
    mode: DestructiveEditMode
    edge_ids_to_detach: tuple[str, ...]


class DestructiveEditInvariantError(DiagnosticValueError):
    payload: DiagnosticPayload

    def __init__(
        self,
        *,
        operation: str,
        removal_class: RemovalClass,
        target_reference: str,
        mode: DestructiveEditMode,
        blocking_dependents: Sequence[str],
    ) -> None:
        detail_payload: dict[str, object] = {
            "legacy_code": "DESTRUCTIVE_EDIT_DEPENDENTS",
            "operation": operation,
            "removal_class": removal_class,
            "target": target_reference,
            "policy_mode": mode,
            "blocking_dependents": tuple(sorted(set(blocking_dependents))),
        }
        hint = (
            "remove or detach listed dependents first, or retry with "
            + "metadata.destructive_edit_mode='safe_detach'"
        )
        message = "destructive edit rejected: " + json.dumps(
            detail_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        )
        payload = build_diagnostic_payload(
            code=INVARIANT_FAILURE_CODE,
            message=message,
            path="metadata.destructive_edit_mode",
            hint=hint,
            revision=None,
        )
        payload["legacy_code"] = "DESTRUCTIVE_EDIT_DEPENDENTS"
        payload["operation"] = operation
        payload["removal_class"] = removal_class
        payload["target"] = target_reference
        payload["policy_mode"] = mode
        payload["blocking_dependents"] = tuple(sorted(set(blocking_dependents)))
        payload["remediation_hint"] = (
            "remove or detach listed dependents first, or retry with "
            + "metadata.destructive_edit_mode='safe_detach'"
        )
        payload["structural_rejection_source"] = "invariant"
        super().__init__(payload)


class ConnectionMutationInvariantValidator:
    _operation_to_removal_class: dict[str, RemovalClass] = {
        "remove_process": "remove_unit",
        "remove_unit": "remove_unit",
        "remove_junction_process": "remove_junction",
        "remove_process_port": "remove_port",
        "remove_port": "remove_port",
        "remove_inlet": "remove_port",
        "remove_outlet": "remove_port",
        "remove_connection": "remove_edge",
        "remove_edge": "remove_edge",
        "disconnect_line": "remove_edge",
        "remove_line": "remove_edge",
        "remove_boundary": "remove_junction",
        "remove_junction": "remove_junction",
    }

    def plan_destructive_edit(
        self,
        *,
        network: ConnectionNetwork,
        mutation: Mapping[str, object],
        request_metadata: Mapping[str, object],
    ) -> DestructiveEditValidationPlan | None:
        operation_value = mutation.get("operation")
        if not isinstance(operation_value, str) or not operation_value.strip():
            raise ValueError("invalid mutation payload: field 'operation' must be non-empty string")

        operation = operation_value.strip()
        removal_class = self._operation_to_removal_class.get(operation)
        if removal_class is None:
            return None

        validated_metadata = validate_reconfiguration_request_metadata(metadata=request_metadata)
        mode = self._resolve_mode(validated_metadata)
        target_reference = self._resolve_target_reference(
            network=network,
            mutation=mutation,
            removal_class=removal_class,
        )

        topology_edges = self._collect_topology_edge_dependents(
            network=network,
            mutation=mutation,
            removal_class=removal_class,
        )
        control_dependents = self._collect_control_dependents(
            network=network,
            mutation=mutation,
            removal_class=removal_class,
            request_metadata=validated_metadata,
            topology_edge_ids=topology_edges,
        )

        blocking_dependents: list[str] = []
        edge_ids_to_detach: list[str] = []
        topology_decision = self._decision(
            removal_class=removal_class,
            dependency_class="topology.edge",
            mode=mode,
        )
        if topology_decision == "block":
            blocking_dependents.extend(f"edge:{edge_id}" for edge_id in topology_edges)
        else:
            edge_ids_to_detach.extend(topology_edges)

        control_decision = self._decision(
            removal_class=removal_class,
            dependency_class="control.dependency",
            mode=mode,
        )
        if control_decision == "block":
            blocking_dependents.extend(control_dependents)

        if blocking_dependents:
            raise DestructiveEditInvariantError(
                operation=operation,
                removal_class=removal_class,
                target_reference=target_reference,
                mode=mode,
                blocking_dependents=blocking_dependents,
            )

        return DestructiveEditValidationPlan(
            operation=operation,
            removal_class=removal_class,
            target_reference=target_reference,
            mode=mode,
            edge_ids_to_detach=tuple(sorted(set(edge_ids_to_detach))),
        )

    def _resolve_mode(
        self, request_metadata: ReconfigurationRequestMetadata
    ) -> DestructiveEditMode:
        mode = request_metadata.destructive_edit_mode
        if mode == "hard_fail":
            return "hard_fail"
        if mode == "safe_detach":
            return "safe_detach"
        raise ValueError(
            "invalid transaction metadata: field 'destructive_edit_mode' "
            + "must be 'hard_fail' or 'safe_detach'"
        )

    def _decision(
        self,
        *,
        removal_class: RemovalClass,
        dependency_class: DependencyClass,
        mode: DestructiveEditMode,
    ) -> PolicyDecision:
        return DESTRUCTIVE_EDIT_POLICY_MATRIX[removal_class][dependency_class][mode]

    def _resolve_target_reference(
        self,
        *,
        network: ConnectionNetwork,
        mutation: Mapping[str, object],
        removal_class: RemovalClass,
    ) -> str:
        del network
        if removal_class == "remove_unit":
            process_id = self._non_empty_string(mutation.get("process_id"))
            return f"unit:{process_id}" if process_id is not None else "unit:<unknown>"
        if removal_class == "remove_port":
            process_id = self._non_empty_string(mutation.get("process_id"))
            port_name = self._non_empty_string(mutation.get("port_name"))
            if process_id is None or port_name is None:
                return "port:<unknown>"
            return f"port:{process_id}.{port_name}"
        if removal_class == "remove_edge":
            edge_id = self._non_empty_string(mutation.get("edge_id"))
            if edge_id is not None:
                return f"edge:{edge_id}"
            source = self._non_empty_string(mutation.get("source"))
            target = self._non_empty_string(mutation.get("target"))
            if source is None or target is None:
                return "edge:<unknown>"
            return f"edge:{source}->{target}"

        junction_id = self._non_empty_string(mutation.get("junction_id"))
        if junction_id is None:
            junction_id = self._non_empty_string(mutation.get("process_id"))
        if junction_id is None:
            junction_id = self._non_empty_string(mutation.get("boundary_id"))
        if junction_id is None:
            return "junction:<unknown>"
        return f"junction:{junction_id}"

    def _collect_topology_edge_dependents(
        self,
        *,
        network: ConnectionNetwork,
        mutation: Mapping[str, object],
        removal_class: RemovalClass,
    ) -> tuple[str, ...]:
        if removal_class == "remove_unit":
            process_id = self._non_empty_string(mutation.get("process_id"))
            if process_id is None:
                return ()
            return network.list_incident_edge_ids(node_id=process_id)

        if removal_class == "remove_port":
            process_id = self._non_empty_string(mutation.get("process_id"))
            port_name = self._non_empty_string(mutation.get("port_name"))
            if process_id is None or port_name is None:
                return ()
            return network.list_incident_edge_ids(node_id=process_id, port_name=port_name)

        if removal_class == "remove_edge":
            return ()

        junction_id = self._non_empty_string(mutation.get("junction_id"))
        if junction_id is None:
            junction_id = self._non_empty_string(mutation.get("process_id"))
        if junction_id is None:
            junction_id = self._non_empty_string(mutation.get("boundary_id"))
        if junction_id is None:
            return ()
        return network.list_incident_edge_ids(node_id=junction_id)

    def _collect_control_dependents(
        self,
        *,
        network: ConnectionNetwork,
        mutation: Mapping[str, object],
        removal_class: RemovalClass,
        request_metadata: ReconfigurationRequestMetadata,
        topology_edge_ids: Sequence[str],
    ) -> tuple[str, ...]:
        control_index = self._control_dependency_index(request_metadata)
        if not control_index:
            return ()

        lookup_keys: set[str] = set()
        if removal_class == "remove_unit":
            process_id = self._non_empty_string(mutation.get("process_id"))
            if process_id is not None:
                lookup_keys.update((f"unit:{process_id}", f"process:{process_id}"))
                process_ports = network.process_ports(process_id=process_id)
                if process_ports is not None:
                    for port_name in process_ports:
                        lookup_keys.add(f"port:{process_id}.{port_name}")
        elif removal_class == "remove_port":
            process_id = self._non_empty_string(mutation.get("process_id"))
            port_name = self._non_empty_string(mutation.get("port_name"))
            if process_id is not None and port_name is not None:
                lookup_keys.add(f"port:{process_id}.{port_name}")
        elif removal_class == "remove_edge":
            edge_id = self._non_empty_string(mutation.get("edge_id"))
            if edge_id is None:
                source = self._non_empty_string(mutation.get("source"))
                target = self._non_empty_string(mutation.get("target"))
                if source is not None and target is not None:
                    edge_id = network.resolve_connection_edge_id(source=source, target=target)
            if edge_id is not None:
                lookup_keys.add(f"edge:{edge_id}")
        else:
            junction_id = self._non_empty_string(mutation.get("junction_id"))
            if junction_id is None:
                junction_id = self._non_empty_string(mutation.get("process_id"))
            if junction_id is None:
                junction_id = self._non_empty_string(mutation.get("boundary_id"))
            if junction_id is not None:
                lookup_keys.update((f"junction:{junction_id}", f"boundary:{junction_id}"))
                junction_ports = network.junction_ports(junction_id=junction_id)
                if junction_ports is not None:
                    for port_name in junction_ports:
                        lookup_keys.add(f"port:{junction_id}.{port_name}")

        lookup_keys.update(f"edge:{edge_id}" for edge_id in topology_edge_ids)
        normalized_dependents: set[str] = set()
        for lookup_key in lookup_keys:
            for item in control_index.get(lookup_key, ()):
                normalized_dependents.add(item)
        return tuple(sorted(normalized_dependents))

    def _control_dependency_index(
        self, request_metadata: ReconfigurationRequestMetadata
    ) -> dict[str, tuple[str, ...]]:
        return {key: tuple(values) for key, values in request_metadata.control_dependencies.items()}

    def _non_empty_string(self, value: object) -> str | None:
        if not isinstance(value, str) or not value.strip():
            return None
        return value.strip()


__all__ = [
    "ConnectionMutationInvariantValidator",
    "DESTRUCTIVE_EDIT_POLICY_MATRIX",
    "DestructiveEditInvariantError",
    "DestructiveEditValidationPlan",
]

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json
from typing import Literal, cast

from modular_simulation.connection.error_catalog import (
    INVARIANT_FAILURE_CODE,
    DiagnosticPayload,
    DiagnosticValueError,
    build_diagnostic_payload,
)
from modular_simulation.connection.network import ConnectionNetwork

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
        super().__init__(payload)


class ConnectionMutationInvariantValidator:
    _operation_to_removal_class: dict[str, RemovalClass] = {
        "remove_process": "remove_unit",
        "remove_unit": "remove_unit",
        "remove_junction_process": "remove_unit",
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

        mode = self._resolve_mode(request_metadata)
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
            request_metadata=request_metadata,
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

    def _resolve_mode(self, request_metadata: Mapping[str, object]) -> DestructiveEditMode:
        raw_mode = request_metadata.get("destructive_edit_mode", "hard_fail")
        if not isinstance(raw_mode, str) or not raw_mode.strip():
            raise ValueError(
                "invalid transaction metadata: field 'destructive_edit_mode' "
                + "must be 'hard_fail' or 'safe_detach'"
            )
        mode = raw_mode.strip()
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

        boundary_id = self._non_empty_string(mutation.get("boundary_id"))
        if boundary_id is None:
            boundary_id = self._non_empty_string(mutation.get("junction_id"))
        if boundary_id is None:
            return "junction:<unknown>"
        return f"junction:{boundary_id}"

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

        boundary_id = self._non_empty_string(mutation.get("boundary_id"))
        if boundary_id is None:
            boundary_id = self._non_empty_string(mutation.get("junction_id"))
        if boundary_id is None:
            return ()
        return network.list_incident_edge_ids(node_id=boundary_id)

    def _collect_control_dependents(
        self,
        *,
        network: ConnectionNetwork,
        mutation: Mapping[str, object],
        removal_class: RemovalClass,
        request_metadata: Mapping[str, object],
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
            boundary_id = self._non_empty_string(mutation.get("boundary_id"))
            if boundary_id is None:
                boundary_id = self._non_empty_string(mutation.get("junction_id"))
            if boundary_id is not None:
                lookup_keys.update((f"junction:{boundary_id}", f"boundary:{boundary_id}"))

        lookup_keys.update(f"edge:{edge_id}" for edge_id in topology_edge_ids)
        normalized_dependents: set[str] = set()
        for lookup_key in lookup_keys:
            for item in control_index.get(lookup_key, ()):
                normalized_dependents.add(item)
        return tuple(sorted(normalized_dependents))

    def _control_dependency_index(
        self, request_metadata: Mapping[str, object]
    ) -> dict[str, tuple[str, ...]]:
        raw_index = request_metadata.get("control_dependencies")
        if raw_index is None:
            return {}
        if not isinstance(raw_index, Mapping):
            raise ValueError(
                "invalid transaction metadata: field 'control_dependencies' must be a mapping"
            )

        dependency_index: dict[str, tuple[str, ...]] = {}
        for raw_target, raw_dependents in cast(Mapping[object, object], raw_index).items():
            if not isinstance(raw_target, str) or not raw_target.strip():
                raise ValueError(
                    "invalid transaction metadata: control dependency keys must be non-empty strings"
                )
            if isinstance(raw_dependents, str) or not isinstance(raw_dependents, Sequence):
                raise ValueError(
                    "invalid transaction metadata: control dependency entries must be sequences"
                )

            normalized_items: set[str] = set()
            for dependent in raw_dependents:
                normalized_items.add(self._normalize_control_dependency(dependent))
            dependency_index[raw_target.strip()] = tuple(sorted(normalized_items))
        return dependency_index

    def _normalize_control_dependency(self, value: object) -> str:
        if isinstance(value, str) and value.strip():
            token = value.strip()
            return token if token.startswith("control:") else f"control:{token}"

        if isinstance(value, Mapping):
            mapping_value = cast(Mapping[object, object], value)
            dependency_id = mapping_value.get("dependency_id", mapping_value.get("id"))
            if not isinstance(dependency_id, str) or not dependency_id.strip():
                raise ValueError(
                    "invalid transaction metadata: control dependency mapping entries "
                    + "must include non-empty string key 'dependency_id' or 'id'"
                )
            dependency_kind = mapping_value.get("kind", "dependency")
            if not isinstance(dependency_kind, str) or not dependency_kind.strip():
                raise ValueError(
                    "invalid transaction metadata: control dependency mapping field 'kind' "
                    + "must be non-empty string when provided"
                )
            return f"control:{dependency_kind.strip()}:{dependency_id.strip()}"

        raise ValueError(
            "invalid transaction metadata: control dependency entries must be strings or mappings"
        )

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

from __future__ import annotations

# pyright: reportMissingTypeStubs=false, reportPrivateUsage=false

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json
from math import isfinite
from typing import Literal, Protocol, cast

from modular_simulation.connection.network import ConnectionNetwork


_Mutation = dict[str, object]


@dataclass(frozen=True)
class _ProcessShape:
    process_id: str
    inlet_ports: tuple[str, ...]
    outlet_ports: tuple[str, ...]


@dataclass(frozen=True)
class _BoundaryShape:
    boundary_id: str
    direction: Literal["source", "sink"]
    port_name: str


@dataclass(frozen=True)
class _LineGeometryShape:
    radius_m: float
    length_m: float
    equation_name: str | None
    resistance_parameter_name: str | None


@dataclass(frozen=True)
class _LineResistanceShape:
    mode: Literal["derived", "manual_override"]
    manual_value: float | None


@dataclass(frozen=True)
class _ValveShape:
    valve_id: str
    minimum_open_fraction: float
    maximum_open_fraction: float
    initial_open_fraction: float


@dataclass(frozen=True)
class _LineShape:
    line_id: str
    source: str
    target: str
    geometry: _LineGeometryShape | None
    resistance: _LineResistanceShape | None
    valve: _ValveShape | None


class _ProcessSpecLike(Protocol):
    inlet_ports: tuple[str, ...]
    outlet_ports: tuple[str, ...]


class _BoundarySpecLike(Protocol):
    direction: Literal["source", "sink"]
    port_name: str


class _PortReferenceLike(Protocol):
    node_id: str
    port_name: str


class _ConnectionEdgeLike(Protocol):
    edge_id: str
    source: _PortReferenceLike
    target: _PortReferenceLike


class _ResistanceConfigLike(Protocol):
    mode: Literal["derived", "manual_override"]
    radius_m: float
    length_m: float
    manual_value: float | None


class _ValveConfigLike(Protocol):
    valve_id: str
    minimum_open_fraction: float
    maximum_open_fraction: float
    initial_open_fraction: float


class _LineHydraulicConfigLike(Protocol):
    equation_name: str
    resistance_parameter_name: str
    resistance: _ResistanceConfigLike
    valve: _ValveConfigLike | None


class _NetworkInternalsLike(Protocol):
    _process_specs: Mapping[str, _ProcessSpecLike]
    _boundary_specs: Mapping[str, _BoundarySpecLike]
    _edges: Sequence[_ConnectionEdgeLike]
    _line_hydraulic_configs: Mapping[str, _LineHydraulicConfigLike]


@dataclass(frozen=True)
class SpecTransactionBatch:
    name: str
    mutations: tuple[_Mutation, ...]


@dataclass(frozen=True)
class SpecDelta:
    add: tuple[_Mutation, ...]
    remove: tuple[_Mutation, ...]
    update: tuple[_Mutation, ...]
    transaction_batches: tuple[SpecTransactionBatch, ...]

    def as_mapping(self) -> dict[str, object]:
        return {
            "add": [dict(item) for item in self.add],
            "remove": [dict(item) for item in self.remove],
            "update": [dict(item) for item in self.update],
            "transaction_batches": [
                {
                    "name": batch.name,
                    "mutations": [dict(mutation) for mutation in batch.mutations],
                }
                for batch in self.transaction_batches
            ],
        }


class SpecApplyError(RuntimeError):
    def __init__(self, message: str, *, diff: Mapping[str, object]) -> None:
        super().__init__(message)
        self.diff: dict[str, object] = dict(diff)


def compile_spec_delta(*, network: ConnectionNetwork, spec_path: str) -> SpecDelta:
    spec_payload = _load_spec_payload(spec_path)
    desired_processes = _parse_desired_processes(spec_payload)
    desired_boundaries = _parse_desired_boundaries(spec_payload)
    desired_lines = _parse_desired_lines(spec_payload)

    current_processes = _current_process_shapes(network)
    current_boundaries = _current_boundary_shapes(network)
    current_lines = _current_line_shapes(network)

    remove_mutations: list[_Mutation] = []
    add_mutations: list[_Mutation] = []
    update_mutations: list[_Mutation] = []

    _compile_line_removals(
        remove_mutations=remove_mutations,
        current_lines=current_lines,
        desired_lines=desired_lines,
    )
    _compile_process_port_removals(
        remove_mutations=remove_mutations,
        current_processes=current_processes,
        desired_processes=desired_processes,
    )
    _compile_process_removals(
        remove_mutations=remove_mutations,
        current_processes=current_processes,
        desired_processes=desired_processes,
    )
    _compile_boundary_removals(
        remove_mutations=remove_mutations,
        current_boundaries=current_boundaries,
        desired_boundaries=desired_boundaries,
    )

    _compile_boundary_additions_or_updates(
        add_mutations=add_mutations,
        update_mutations=update_mutations,
        current_boundaries=current_boundaries,
        desired_boundaries=desired_boundaries,
    )
    _compile_process_additions(
        add_mutations=add_mutations,
        current_processes=current_processes,
        desired_processes=desired_processes,
    )
    _compile_process_port_additions(
        add_mutations=add_mutations,
        current_processes=current_processes,
        desired_processes=desired_processes,
    )
    _compile_line_additions(
        add_mutations=add_mutations,
        current_lines=current_lines,
        desired_lines=desired_lines,
    )
    _compile_line_endpoint_updates(
        update_mutations=update_mutations,
        current_lines=current_lines,
        desired_lines=desired_lines,
    )
    _compile_line_configuration_updates(
        update_mutations=update_mutations,
        current_lines=current_lines,
        desired_lines=desired_lines,
    )

    batches: list[SpecTransactionBatch] = []
    if remove_mutations:
        batches.append(SpecTransactionBatch(name="remove", mutations=tuple(remove_mutations)))
    if add_mutations:
        batches.append(SpecTransactionBatch(name="add", mutations=tuple(add_mutations)))
    if update_mutations:
        batches.append(SpecTransactionBatch(name="update", mutations=tuple(update_mutations)))

    return SpecDelta(
        add=tuple(add_mutations),
        remove=tuple(remove_mutations),
        update=tuple(update_mutations),
        transaction_batches=tuple(batches),
    )


def _load_spec_payload(spec_path: str) -> Mapping[str, object]:
    with open(spec_path, "r", encoding="utf-8") as stream:
        payload = cast(object, json.load(stream))
    if not isinstance(payload, Mapping):
        raise ValueError("spec payload must be a mapping")
    mapping_payload = cast(Mapping[object, object], payload)
    return {str(key): value for key, value in mapping_payload.items()}


def _parse_desired_processes(spec_payload: Mapping[str, object]) -> dict[str, _ProcessShape]:
    raw_processes = spec_payload.get("processes", ())
    process_items = _require_mapping_sequence(raw_processes, field_name="processes")
    desired: dict[str, _ProcessShape] = {}
    for index, process_payload in enumerate(process_items, start=1):
        process_id = _require_non_empty_string(
            process_payload.get("process_id"),
            field_name=f"processes[{index}].process_id",
        )
        if process_id in desired:
            raise ValueError(f"duplicate process id '{process_id}' in spec payload")
        inlet_ports = _normalize_port_names(
            process_payload.get("inlet_ports", ()),
            field_name=f"processes[{index}].inlet_ports",
        )
        outlet_ports = _normalize_port_names(
            process_payload.get("outlet_ports", ()),
            field_name=f"processes[{index}].outlet_ports",
        )
        desired[process_id] = _ProcessShape(
            process_id=process_id,
            inlet_ports=inlet_ports,
            outlet_ports=outlet_ports,
        )
    return desired


def _parse_desired_boundaries(spec_payload: Mapping[str, object]) -> dict[str, _BoundaryShape]:
    raw_boundaries = spec_payload.get("boundaries", ())
    boundary_items = _require_mapping_sequence(raw_boundaries, field_name="boundaries")
    desired: dict[str, _BoundaryShape] = {}
    for index, boundary_payload in enumerate(boundary_items, start=1):
        boundary_id = _require_non_empty_string(
            boundary_payload.get("boundary_id"),
            field_name=f"boundaries[{index}].boundary_id",
        )
        if boundary_id in desired:
            raise ValueError(f"duplicate boundary id '{boundary_id}' in spec payload")
        direction = _require_boundary_direction(
            boundary_payload.get("direction"),
            field_name=f"boundaries[{index}].direction",
        )
        default_port_name = "outlet" if direction == "source" else "inlet"
        port_name = _require_non_empty_string(
            boundary_payload.get("port_name", default_port_name),
            field_name=f"boundaries[{index}].port_name",
        )
        desired[boundary_id] = _BoundaryShape(
            boundary_id=boundary_id,
            direction=direction,
            port_name=port_name,
        )
    return desired


def _parse_desired_lines(spec_payload: Mapping[str, object]) -> dict[str, _LineShape]:
    raw_lines = spec_payload.get("lines", ())
    line_items = _require_mapping_sequence(raw_lines, field_name="lines")
    desired: dict[str, _LineShape] = {}
    for index, line_payload in enumerate(line_items, start=1):
        line_id = _require_non_empty_string(
            line_payload.get("line_id"),
            field_name=f"lines[{index}].line_id",
        )
        if line_id in desired:
            raise ValueError(f"duplicate line id '{line_id}' in spec payload")
        source = _require_non_empty_string(
            line_payload.get("source"),
            field_name=f"lines[{index}].source",
        )
        target = _require_non_empty_string(
            line_payload.get("target"),
            field_name=f"lines[{index}].target",
        )
        geometry = _parse_line_geometry(line_payload.get("geometry"), line_index=index)
        resistance = _parse_line_resistance(line_payload.get("resistance"), line_index=index)
        valve = _parse_line_valve(line_payload.get("valve"), line_index=index)
        desired[line_id] = _LineShape(
            line_id=line_id,
            source=source,
            target=target,
            geometry=geometry,
            resistance=resistance,
            valve=valve,
        )
    return desired


def _parse_line_geometry(value: object, *, line_index: int) -> _LineGeometryShape | None:
    if value is None:
        return None
    payload = _require_mapping(value, field_name=f"lines[{line_index}].geometry")
    radius_m = _require_finite_float(
        payload.get("radius_m"), f"lines[{line_index}].geometry.radius_m"
    )
    length_m = _require_finite_float(
        payload.get("length_m"), f"lines[{line_index}].geometry.length_m"
    )
    equation_name_value = payload.get("equation_name")
    equation_name = (
        None
        if equation_name_value is None
        else _require_non_empty_string(
            equation_name_value,
            field_name=f"lines[{line_index}].geometry.equation_name",
        )
    )
    resistance_parameter_name_value = payload.get("resistance_parameter_name")
    resistance_parameter_name = (
        None
        if resistance_parameter_name_value is None
        else _require_non_empty_string(
            resistance_parameter_name_value,
            field_name=f"lines[{line_index}].geometry.resistance_parameter_name",
        )
    )
    return _LineGeometryShape(
        radius_m=radius_m,
        length_m=length_m,
        equation_name=equation_name,
        resistance_parameter_name=resistance_parameter_name,
    )


def _parse_line_resistance(value: object, *, line_index: int) -> _LineResistanceShape | None:
    if value is None:
        return None
    payload = _require_mapping(value, field_name=f"lines[{line_index}].resistance")
    mode_value = _require_non_empty_string(
        payload.get("mode"),
        field_name=f"lines[{line_index}].resistance.mode",
    )
    if mode_value not in {"derived", "manual_override"}:
        raise ValueError(
            f"lines[{line_index}].resistance.mode must be 'derived' or 'manual_override'"
        )
    mode = cast(Literal["derived", "manual_override"], mode_value)
    manual_value_raw = payload.get("manual_value")
    manual_value = None
    if mode == "manual_override":
        manual_value = _require_finite_float(
            manual_value_raw,
            field_name=f"lines[{line_index}].resistance.manual_value",
        )
    return _LineResistanceShape(mode=mode, manual_value=manual_value)


def _parse_line_valve(value: object, *, line_index: int) -> _ValveShape | None:
    if value is None:
        return None
    payload = _require_mapping(value, field_name=f"lines[{line_index}].valve")
    return _ValveShape(
        valve_id=_require_non_empty_string(
            payload.get("valve_id"),
            field_name=f"lines[{line_index}].valve.valve_id",
        ),
        minimum_open_fraction=_require_finite_float(
            payload.get("minimum_open_fraction", 0.0),
            field_name=f"lines[{line_index}].valve.minimum_open_fraction",
        ),
        maximum_open_fraction=_require_finite_float(
            payload.get("maximum_open_fraction", 1.0),
            field_name=f"lines[{line_index}].valve.maximum_open_fraction",
        ),
        initial_open_fraction=_require_finite_float(
            payload.get("initial_open_fraction", 1.0),
            field_name=f"lines[{line_index}].valve.initial_open_fraction",
        ),
    )


def _current_process_shapes(network: ConnectionNetwork) -> dict[str, _ProcessShape]:
    network_view = cast(_NetworkInternalsLike, cast(object, network))
    raw_mapping = network_view._process_specs
    shapes: dict[str, _ProcessShape] = {}
    for process_id in sorted(raw_mapping.keys()):
        spec = raw_mapping[process_id]
        inlet_ports = tuple(spec.inlet_ports)
        outlet_ports = tuple(spec.outlet_ports)
        shapes[process_id] = _ProcessShape(
            process_id=process_id,
            inlet_ports=tuple(sorted(inlet_ports)),
            outlet_ports=tuple(sorted(outlet_ports)),
        )
    return shapes


def _current_boundary_shapes(network: ConnectionNetwork) -> dict[str, _BoundaryShape]:
    network_view = cast(_NetworkInternalsLike, cast(object, network))
    raw_mapping = network_view._boundary_specs
    shapes: dict[str, _BoundaryShape] = {}
    for boundary_id in sorted(raw_mapping.keys()):
        spec = raw_mapping[boundary_id]
        shapes[boundary_id] = _BoundaryShape(
            boundary_id=boundary_id,
            direction=spec.direction,
            port_name=spec.port_name,
        )
    return shapes


def _current_line_shapes(network: ConnectionNetwork) -> dict[str, _LineShape]:
    network_view = cast(_NetworkInternalsLike, cast(object, network))
    edges = network_view._edges
    line_configs = network_view._line_hydraulic_configs

    line_by_id: dict[str, _LineShape] = {}
    for edge in sorted(edges, key=lambda item: item.edge_id):
        line_id = edge.edge_id
        source = f"{edge.source.node_id}.{edge.source.port_name}"
        target = f"{edge.target.node_id}.{edge.target.port_name}"

        geometry: _LineGeometryShape | None = None
        resistance: _LineResistanceShape | None = None
        valve: _ValveShape | None = None
        config = line_configs.get(line_id)
        if config is not None:
            resistance_config = config.resistance
            geometry = _LineGeometryShape(
                radius_m=resistance_config.radius_m,
                length_m=resistance_config.length_m,
                equation_name=config.equation_name,
                resistance_parameter_name=config.resistance_parameter_name,
            )
            resistance = _LineResistanceShape(
                mode=resistance_config.mode,
                manual_value=resistance_config.manual_value,
            )
            valve_config = config.valve
            if valve_config is not None:
                valve = _ValveShape(
                    valve_id=valve_config.valve_id,
                    minimum_open_fraction=valve_config.minimum_open_fraction,
                    maximum_open_fraction=valve_config.maximum_open_fraction,
                    initial_open_fraction=valve_config.initial_open_fraction,
                )

        line_by_id[line_id] = _LineShape(
            line_id=line_id,
            source=source,
            target=target,
            geometry=geometry,
            resistance=resistance,
            valve=valve,
        )
    return line_by_id


def _compile_line_removals(
    *,
    remove_mutations: list[_Mutation],
    current_lines: Mapping[str, _LineShape],
    desired_lines: Mapping[str, _LineShape],
) -> None:
    for line_id in sorted(set(current_lines.keys()) - set(desired_lines.keys())):
        remove_mutations.append({"operation": "disconnect_line", "line_id": line_id})


def _compile_process_port_removals(
    *,
    remove_mutations: list[_Mutation],
    current_processes: Mapping[str, _ProcessShape],
    desired_processes: Mapping[str, _ProcessShape],
) -> None:
    for process_id in sorted(set(current_processes.keys()) & set(desired_processes.keys())):
        current = current_processes[process_id]
        desired = desired_processes[process_id]
        for port_name in sorted(set(current.inlet_ports) - set(desired.inlet_ports)):
            remove_mutations.append(
                {
                    "operation": "remove_inlet",
                    "process_id": process_id,
                    "port_name": port_name,
                }
            )
        for port_name in sorted(set(current.outlet_ports) - set(desired.outlet_ports)):
            remove_mutations.append(
                {
                    "operation": "remove_outlet",
                    "process_id": process_id,
                    "port_name": port_name,
                }
            )


def _compile_process_removals(
    *,
    remove_mutations: list[_Mutation],
    current_processes: Mapping[str, _ProcessShape],
    desired_processes: Mapping[str, _ProcessShape],
) -> None:
    for process_id in sorted(set(current_processes.keys()) - set(desired_processes.keys())):
        remove_mutations.append({"operation": "remove_unit", "process_id": process_id})


def _compile_boundary_removals(
    *,
    remove_mutations: list[_Mutation],
    current_boundaries: Mapping[str, _BoundaryShape],
    desired_boundaries: Mapping[str, _BoundaryShape],
) -> None:
    for boundary_id in sorted(set(current_boundaries.keys()) - set(desired_boundaries.keys())):
        remove_mutations.append({"operation": "remove_boundary", "boundary_id": boundary_id})


def _compile_boundary_additions_or_updates(
    *,
    add_mutations: list[_Mutation],
    update_mutations: list[_Mutation],
    current_boundaries: Mapping[str, _BoundaryShape],
    desired_boundaries: Mapping[str, _BoundaryShape],
) -> None:
    for boundary_id in sorted(set(desired_boundaries.keys()) - set(current_boundaries.keys())):
        boundary = desired_boundaries[boundary_id]
        operation = "add_boundary_source" if boundary.direction == "source" else "add_boundary_sink"
        add_mutations.append(
            {
                "operation": operation,
                "boundary_id": boundary.boundary_id,
                "port_name": boundary.port_name,
            }
        )

    for boundary_id in sorted(set(desired_boundaries.keys()) & set(current_boundaries.keys())):
        current = current_boundaries[boundary_id]
        desired = desired_boundaries[boundary_id]
        if current == desired:
            continue
        update_mutations.append({"operation": "remove_boundary", "boundary_id": boundary_id})
        update_mutations.append(
            {
                "operation": "add_boundary_source"
                if desired.direction == "source"
                else "add_boundary_sink",
                "boundary_id": desired.boundary_id,
                "port_name": desired.port_name,
            }
        )


def _compile_process_additions(
    *,
    add_mutations: list[_Mutation],
    current_processes: Mapping[str, _ProcessShape],
    desired_processes: Mapping[str, _ProcessShape],
) -> None:
    for process_id in sorted(set(desired_processes.keys()) - set(current_processes.keys())):
        desired = desired_processes[process_id]
        add_mutations.append(
            {
                "operation": "add_process",
                "process_id": desired.process_id,
                "inlet_ports": list(desired.inlet_ports),
                "outlet_ports": list(desired.outlet_ports),
            }
        )


def _compile_process_port_additions(
    *,
    add_mutations: list[_Mutation],
    current_processes: Mapping[str, _ProcessShape],
    desired_processes: Mapping[str, _ProcessShape],
) -> None:
    for process_id in sorted(set(current_processes.keys()) & set(desired_processes.keys())):
        current = current_processes[process_id]
        desired = desired_processes[process_id]
        for port_name in sorted(set(desired.inlet_ports) - set(current.inlet_ports)):
            add_mutations.append(
                {
                    "operation": "add_inlet",
                    "process_id": process_id,
                    "port_name": port_name,
                }
            )
        for port_name in sorted(set(desired.outlet_ports) - set(current.outlet_ports)):
            add_mutations.append(
                {
                    "operation": "add_outlet",
                    "process_id": process_id,
                    "port_name": port_name,
                }
            )


def _compile_line_additions(
    *,
    add_mutations: list[_Mutation],
    current_lines: Mapping[str, _LineShape],
    desired_lines: Mapping[str, _LineShape],
) -> None:
    for line_id in sorted(set(desired_lines.keys()) - set(current_lines.keys())):
        desired = desired_lines[line_id]
        add_mutations.append(
            {
                "operation": "connect_line",
                "source": desired.source,
                "target": desired.target,
                "line_id": desired.line_id,
            }
        )


def _compile_line_endpoint_updates(
    *,
    update_mutations: list[_Mutation],
    current_lines: Mapping[str, _LineShape],
    desired_lines: Mapping[str, _LineShape],
) -> None:
    for line_id in sorted(set(current_lines.keys()) & set(desired_lines.keys())):
        current = current_lines[line_id]
        desired = desired_lines[line_id]
        if current.source == desired.source and current.target == desired.target:
            continue
        update_mutations.append(
            {
                "operation": "rewire_connection",
                "edge_id": line_id,
                "source": desired.source,
                "target": desired.target,
            }
        )


def _compile_line_configuration_updates(
    *,
    update_mutations: list[_Mutation],
    current_lines: Mapping[str, _LineShape],
    desired_lines: Mapping[str, _LineShape],
) -> None:
    for line_id in sorted(desired_lines.keys()):
        desired = desired_lines[line_id]
        current = current_lines.get(line_id)

        if desired.geometry is not None and (
            current is None or desired.geometry != current.geometry
        ):
            update_mutations.append(
                {
                    "operation": "configure_line_geometry",
                    "line_id": line_id,
                    "radius_m": desired.geometry.radius_m,
                    "length_m": desired.geometry.length_m,
                    "equation_name": desired.geometry.equation_name,
                    "resistance_parameter_name": desired.geometry.resistance_parameter_name,
                }
            )

        if desired.resistance is not None and (
            current is None or desired.resistance != current.resistance
        ):
            mutation: _Mutation = {
                "operation": "configure_line_resistance",
                "line_id": line_id,
                "mode": desired.resistance.mode,
            }
            if desired.resistance.mode == "manual_override":
                mutation["manual_value"] = desired.resistance.manual_value
            update_mutations.append(mutation)

        if desired.valve is not None and (current is None or desired.valve != current.valve):
            update_mutations.append(
                {
                    "operation": "attach_line_valve",
                    "line_id": line_id,
                    "valve_id": desired.valve.valve_id,
                    "minimum_open_fraction": desired.valve.minimum_open_fraction,
                    "maximum_open_fraction": desired.valve.maximum_open_fraction,
                    "initial_open_fraction": desired.valve.initial_open_fraction,
                }
            )


def _require_mapping(value: object, *, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping")
    typed_value = cast(Mapping[object, object], value)
    return {str(key): item for key, item in typed_value.items()}


def _require_mapping_sequence(
    value: object, *, field_name: str
) -> tuple[Mapping[str, object], ...]:
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError(f"{field_name} must be a sequence of mapping values")
    normalized: list[Mapping[str, object]] = []
    for index, item in enumerate(value, start=1):
        normalized.append(_require_mapping(item, field_name=f"{field_name}[{index}]"))
    return tuple(normalized)


def _require_non_empty_string(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _require_boundary_direction(value: object, *, field_name: str) -> Literal["source", "sink"]:
    token = _require_non_empty_string(value, field_name=field_name)
    if token not in {"source", "sink"}:
        raise ValueError(f"{field_name} must be 'source' or 'sink'")
    return cast(Literal["source", "sink"], token)


def _normalize_port_names(value: object, *, field_name: str) -> tuple[str, ...]:
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError(f"{field_name} must be a sequence of strings")
    normalized: list[str] = []
    for index, token in enumerate(value, start=1):
        normalized.append(_require_non_empty_string(token, field_name=f"{field_name}[{index}]"))
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{field_name} contains duplicate values")
    return tuple(sorted(normalized))


def _require_finite_float(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a finite number")
    scalar = float(value)
    if not isfinite(scalar):
        raise ValueError(f"{field_name} must be a finite number")
    return scalar


__all__ = [
    "SpecApplyError",
    "SpecDelta",
    "SpecTransactionBatch",
    "compile_spec_delta",
]

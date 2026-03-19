from __future__ import annotations

# pyright: reportMissingTypeStubs=false, reportArgumentType=false, reportReturnType=false

from collections.abc import Mapping
from dataclasses import dataclass, field
from math import isclose, isfinite
from types import MappingProxyType
from typing import TYPE_CHECKING, Literal, cast
import warnings
import numpy as np
from numpy.typing import NDArray

from modular_simulation.connection.runtime.connected_plant_orchestrator import (
    ConnectedPlantOrchestrator,
    ConnectedPlantStepResult,
)
from modular_simulation.connection.domain.node_port_helpers import DirectionalNodePorts
from modular_simulation.connection.hydraulics.hydraulic_compile import HydraulicCompileLifecycle
from modular_simulation.connection.hydraulics.hydraulic_element import (
    CanonicalNodePressureHydraulicElement,
    HydraulicElement,
    PipeHydraulicElement,
    resolve_hydraulic_element,
)
from modular_simulation.connection.hydraulics.hydraulic_solver import (
    ElementEquation,
    HydraulicPressureAnchorMetadata,
    HydraulicSystemDefinition,
    HydraulicTopologyLookup,
    LinearResidualEquation,
)
from modular_simulation.connection.topology.network import ConnectionNetwork
from modular_simulation.connection.runtime.process_stream_io import ProcessStreamIO
from modular_simulation.connection.runtime.runtime import ConnectionRuntimeOrchestrator
from modular_simulation.connection.topology.subsystem_descriptor import Subsystem
from modular_simulation.connection.topology.unit_process_wiring import create_subsystem_for_unit
from modular_simulation.thermodynamics.algebraic_process_model import UnitProcessPorts
from modular_simulation.thermodynamics.stream import StreamData

if TYPE_CHECKING:
    from modular_simulation.measurables.process_model import ProcessModel
    from modular_simulation.framework.system import System
    from modular_simulation.connection.topology.topology import TopologyGraph
    from modular_simulation.thermodynamics.runtime_context import SimulationRuntimeContext

from modular_simulation.measurables.process_model import StateType


@dataclass(frozen=True)
class FlowsheetResults:
    time_points: NDArray[np.float64]
    units: dict[str, UnitResult]
    streams: dict[str, StreamHistory]
    step_results: tuple[ConnectedPlantStepResult, ...] = field(default_factory=tuple)

    def get_unit(self, unit_id: str) -> UnitResult:
        normalized_unit_id = unit_id.strip()
        unit_result = self.units.get(normalized_unit_id)
        if unit_result is None:
            available = ", ".join(sorted(self.units))
            raise ValueError(f"unknown unit '{normalized_unit_id}'. Available units: {available}")
        return unit_result

    def get_stream(self, source: str, target: str) -> StreamHistory:
        requested_source = source.strip()
        requested_target = target.strip()
        stream_key = f"{requested_source}->{requested_target}"
        stream_history = self.streams.get(stream_key)
        if stream_history is not None:
            return stream_history

        matches: list[str] = []
        for connection_key in sorted(self.streams):
            source_key, _, target_key = connection_key.partition("->")
            source_matches = source_key == requested_source or (
                "." not in requested_source and source_key.startswith(f"{requested_source}.")
            )
            target_matches = target_key == requested_target or (
                "." not in requested_target and target_key.startswith(f"{requested_target}.")
            )
            if source_matches and target_matches:
                matches.append(connection_key)

        if len(matches) == 1:
            return self.streams[matches[0]]
        if len(matches) > 1:
            options = ", ".join(matches)
            raise ValueError(
                f"ambiguous stream connection '{stream_key}'. Matching connections: {options}"
            )

        available = ", ".join(sorted(self.streams))
        raise ValueError(
            f"unknown stream connection '{stream_key}'. Available connections: {available}"
        )

    def summary(self) -> str:
        n_steps = int(self.time_points.size)
        final_time_s = float(cast("float", self.time_points[-1])) if n_steps else 0.0
        lines = [
            (
                f"FlowsheetResults(steps={n_steps}, final_time_s={final_time_s:.6g}, "
                + f"units={len(self.units)}, streams={len(self.streams)})"
            ),
            "Units:",
        ]

        for unit_id in sorted(self.units):
            unit_result = self.units[unit_id]
            lines.append(
                f"- {unit_id}: outlets={len(unit_result.outlet_streams)}, "
                + f"state_traces={len(unit_result.state_history)}"
            )

        lines.append("Streams:")
        for connection_key in sorted(self.streams):
            stream_history = self.streams[connection_key]
            if stream_history.flow_rate.size == 0:
                lines.append(f"- {connection_key}: no samples")
                continue
            lines.append(
                f"- {connection_key}: flow={float(cast('float', stream_history.flow_rate[-1])):.6g} mol/s, "
                + f"T={float(cast('float', stream_history.temperature[-1])):.6g} K, "
                + f"P={float(cast('float', stream_history.pressure[-1])):.6g} Pa"
            )

        return "\n".join(lines)


@dataclass(frozen=True)
class UnitResult:
    unit_id: str
    outlet_streams: dict[str, StreamData]
    state_history: dict[str, NDArray[np.float64]]


@dataclass(frozen=True)
class StreamHistory:
    flow_rate: NDArray[np.float64]
    temperature: NDArray[np.float64]
    pressure: NDArray[np.float64]
    composition: NDArray[np.float64]


def _line_installed_pump_pressure_rise_curve(flow_rate: float, pump_speed: float) -> float:
    del flow_rate
    return pump_speed


def _line_installed_pump_pressure_rise_derivative(flow_rate: float, pump_speed: float) -> float:
    del flow_rate, pump_speed
    return 0.0


@dataclass(frozen=True)
class JunctionDefinition:
    junction_id: str
    inlet_ports: tuple[str, ...]
    outlet_ports: tuple[str, ...]


@dataclass(frozen=True)
class SinkDefinition:
    sink_id: str
    port_name: str


@dataclass(frozen=True)
class PumpInstall:
    id: str | None = None
    initial_pump_speed: float = 0.0


@dataclass(frozen=True)
class ValveInstall:
    id: str | None = None
    minimum_open_fraction: float = 0.0
    maximum_open_fraction: float = 1.0
    initial_open_fraction: float = 1.0


@dataclass(frozen=True)
class HeatInstall:
    id: str | None = None
    initial_heat_rate: float = 0.0


@dataclass(frozen=True)
class LineReference:
    line_id: str
    pump_id: str | None = None
    valve_id: str | None = None
    heat_actuator_id: str | None = None


@dataclass(frozen=True)
class _EndpointReference:
    compile_endpoint: str
    display_endpoint: str
    node_id: str
    port_name: str
    node_kind: Literal["unit", "feed", "junction", "sink"]


@dataclass(frozen=True)
class _ConnectionSpec:
    source: str
    target: str
    display_source: str
    display_target: str
    line_id: str
    radius_m: float
    length_m: float
    pump: PumpInstall | None = None
    valve: ValveInstall | None = None
    heat: HeatInstall | None = None


@dataclass(frozen=True)
class _ResolvedConnection:
    source_node_id: str
    source_port_name: str
    source_node_kind: Literal["unit", "feed", "junction", "sink"]
    target_node_id: str
    target_port_name: str
    target_node_kind: Literal["unit", "feed", "junction", "sink"]


@dataclass(frozen=True)
class _HydraulicNodeCompileSpec:
    node_key: str
    topology_label: str
    pressure_unknown_name: str
    endpoint_ids: tuple[str, ...]
    anchor_pressure_pa: float | None


@dataclass(frozen=True)
class _UnitFlowBalanceEquationCandidate:
    residual_name: str
    coefficients: Mapping[str, float]


@dataclass(frozen=True)
class _UnitPressureRelation:
    inlet_port_name: str
    outlet_port_name: str
    pressure_drop_pa: float


class Flowsheet:
    def __init__(self, context: SimulationRuntimeContext, dt: float = 0.1):
        if not isfinite(dt) or dt <= 0.0:
            raise ValueError("dt must be finite and positive")

        self._context: SimulationRuntimeContext = context
        self._dt: float = float(dt)
        self._units: dict[str, ProcessModel] = {}
        self._user_declared_fields_by_unit_object_id: dict[int, frozenset[str]] = {}
        self._user_declared_field_values_by_unit_object_id: dict[int, Mapping[str, object]] = {}
        self._feeds: dict[str, StreamData] = {}
        self._junctions: dict[str, JunctionDefinition] = {}
        self._sinks: dict[str, SinkDefinition] = {}
        self._connections: list[_ConnectionSpec] = []
        self._subsystems: dict[str, Subsystem] = {}
        self._compiled_plant: ConnectedPlantOrchestrator | None = None
        self._dirty: bool = True
        self._next_generated_line_index: int = 1
        self._line_ids: set[str] = set()
        self._pump_ids: set[str] = set()
        self._valve_ids: set[str] = set()
        self._heat_actuator_ids: set[str] = set()

    def add_unit(self, unit_id: str, unit: ProcessModel) -> None:
        normalized_unit_id = self._normalize_node_id(unit_id=unit_id, field_name="unit_id")
        self._assert_available_node_id(node_id=normalized_unit_id)
        model_fields_set = getattr(unit, "model_fields_set", None)
        if isinstance(model_fields_set, set):
            explicit_fields = frozenset(model_fields_set)
            self._user_declared_fields_by_unit_object_id[id(unit)] = explicit_fields
            snapshot_values: dict[str, object] = {}
            for field_name in explicit_fields:
                try:
                    raw_value = getattr(unit, field_name)
                except Exception:
                    continue
                if isinstance(raw_value, np.ndarray):
                    snapshot_values[field_name] = np.asarray(raw_value, dtype=float).copy()
                else:
                    snapshot_values[field_name] = raw_value
            self._user_declared_field_values_by_unit_object_id[id(unit)] = MappingProxyType(
                snapshot_values
            )
        else:
            self._user_declared_fields_by_unit_object_id[id(unit)] = frozenset()
            self._user_declared_field_values_by_unit_object_id[id(unit)] = MappingProxyType({})
        self._units[normalized_unit_id] = unit
        self._subsystems[normalized_unit_id] = create_subsystem_for_unit(
            unit=unit,
            unit_id=normalized_unit_id,
            dt=self._dt,
            runtime_context=self._context,
        )
        self._mark_dirty()

    def add_feed(self, feed_id: str, stream: StreamData) -> None:
        normalized_feed_id = self._normalize_node_id(unit_id=feed_id, field_name="feed_id")
        self._assert_available_node_id(node_id=normalized_feed_id)
        self._feeds[normalized_feed_id] = stream
        self._mark_dirty()

    def add_junction(
        self,
        junction_id: str,
        *,
        inlet_ports: tuple[str, ...],
        outlet_ports: tuple[str, ...],
    ) -> None:
        normalized_ports = DirectionalNodePorts.build(
            node_id=junction_id,
            inlet_port_ids=tuple(inlet_ports),
            outlet_port_ids=tuple(outlet_ports),
            node_kind="junction",
        )
        self._assert_available_node_id(node_id=normalized_ports.node_id)
        self._junctions[normalized_ports.node_id] = JunctionDefinition(
            junction_id=normalized_ports.node_id,
            inlet_ports=normalized_ports.inlet_port_ids,
            outlet_ports=normalized_ports.outlet_port_ids,
        )
        self._mark_dirty()

    def add_sink(self, sink_id: str, *, port_name: str = "inlet") -> None:
        normalized_sink_id = self._normalize_node_id(unit_id=sink_id, field_name="sink_id")
        self._assert_available_node_id(node_id=normalized_sink_id)
        normalized_port_name = self._normalize_port_name(
            port_name=port_name, field_name="port_name"
        )
        self._sinks[normalized_sink_id] = SinkDefinition(
            sink_id=normalized_sink_id,
            port_name=normalized_port_name,
        )
        self._mark_dirty()

    def add_feed_from_values(
        self,
        feed_id: str,
        *,
        T: float,
        P: float,
        z: tuple[float, ...],
        flow: float,
    ) -> None:
        self.add_feed(
            feed_id=feed_id,
            stream=StreamData(
                temperature=float(T),
                pressure=float(P),
                mole_fractions=tuple(float(value) for value in z),
                molar_flow_rate=float(flow),
            ),
        )

    def connect(
        self,
        source: str,
        target: str,
        *,
        line_id: str | None = None,
        radius_m: float = 1.0,
        length_m: float = 1.0,
        pump: PumpInstall | None = None,
        valve: ValveInstall | None = None,
        heat: HeatInstall | None = None,
    ) -> LineReference:
        source_reference: _EndpointReference = self._normalize_endpoint(
            endpoint=source, role="source"
        )
        target_reference: _EndpointReference = self._normalize_endpoint(
            endpoint=target, role="target"
        )
        resolved_line_id = self._reserve_line_id(line_id)
        radius_scalar = self._require_positive_finite_scalar(value=radius_m, field_name="radius_m")
        length_scalar = self._require_positive_finite_scalar(value=length_m, field_name="length_m")

        pump_install = self._normalize_pump_install(pump=pump, line_id=resolved_line_id)
        valve_install = self._normalize_valve_install(valve=valve, line_id=resolved_line_id)
        heat_install = self._normalize_heat_install(heat=heat, line_id=resolved_line_id)
        self._validate_line_overlay_selection(
            line_id=resolved_line_id,
            pump=pump_install,
            valve=valve_install,
            heat=heat_install,
        )

        self._connections.append(
            _ConnectionSpec(
                source=source_reference.compile_endpoint,
                target=target_reference.compile_endpoint,
                display_source=source_reference.display_endpoint,
                display_target=target_reference.display_endpoint,
                line_id=resolved_line_id,
                radius_m=radius_scalar,
                length_m=length_scalar,
                pump=pump_install,
                valve=valve_install,
                heat=heat_install,
            )
        )
        self._mark_dirty()
        return LineReference(
            line_id=resolved_line_id,
            pump_id=None if pump_install is None else pump_install.id,
            valve_id=None if valve_install is None else valve_install.id,
            heat_actuator_id=None if heat_install is None else heat_install.id,
        )

    def chain(self, *unit_ids: str) -> None:
        if len(unit_ids) < 2:
            raise ValueError("chain requires at least two node ids")
        for index in range(len(unit_ids) - 1):
            self.connect(unit_ids[index], unit_ids[index + 1])

    def compile(self) -> ConnectedPlantOrchestrator:
        if not self._dirty and self._compiled_plant is not None:
            return self._compiled_plant

        self._validate_compile_configuration()

        runtime = ConnectionRuntimeOrchestrator(runtime_context=self._context)
        runtime.bind_stream_port_ios(bindings=cast("Mapping[str, ProcessStreamIO]", self._units))
        runtime.set_feed_streams(feed_streams=self._feeds)

        network = ConnectionNetwork(
            compile_lifecycle=HydraulicCompileLifecycle(),
            hydraulic_system_builder=self._build_hydraulic_system,
            runtime_orchestrator=runtime,
        )

        for unit_id, subsystem in self._subsystems.items():
            network.add_process(
                unit_id,
                inlet_ports=subsystem.descriptor.inlet_ports,
                outlet_ports=subsystem.descriptor.outlet_ports,
            )
        for feed_id in self._feeds:
            network.add_boundary_source(feed_id)
        for junction in self._junctions.values():
            network.add_junction(
                junction.junction_id,
                inlet_ports=junction.inlet_ports,
                outlet_ports=junction.outlet_ports,
            )
        for sink in self._sinks.values():
            network.add_boundary_sink(sink.sink_id, port_name=sink.port_name)
        for connection in self._connections:
            network.connect(connection.source, connection.target, edge_id=connection.line_id)
            self._configure_connection_line(
                network=network,
                connection=connection,
            )

        _ = network.compile()
        plant = ConnectedPlantOrchestrator(
            subsystems=tuple(self._subsystems.values()),
            network=network,
            runtime_orchestrator=runtime,
            runtime_context=self._context,
        )

        self._compiled_plant = plant
        self._dirty = False
        return plant

    def _validate_compile_configuration(self) -> None:
        resolved_connections = self._resolved_connections_for_validation()
        self._validate_pressure_boundary_presence(resolved_connections=resolved_connections)
        self._validate_mandatory_inlets(resolved_connections=resolved_connections)
        self._validate_species_compatibility(resolved_connections=resolved_connections)
        self._warn_dangling_outlets(resolved_connections=resolved_connections)
        self._warn_on_topology_issues(resolved_connections=resolved_connections)

    def _validate_pressure_boundary_presence(
        self, *, resolved_connections: tuple[_ResolvedConnection, ...]
    ) -> None:
        if self._feeds:
            return
        connected_process_ports = {
            (connection.target_node_id, connection.target_port_name)
            for connection in resolved_connections
        }
        connected_process_ports.update(
            (connection.source_node_id, connection.source_port_name)
            for connection in resolved_connections
            if connection.source_node_kind in {"unit", "junction"}
        )
        if any(
            self._resolve_hydraulic_anchor_pressure(
                node_id=node_id,
                port_name=port_name,
                topology=None,
            )
            is not None
            for node_id, port_name in sorted(connected_process_ports)
        ):
            return
        raise ValueError(
            "flowsheet compile validation failed: at least one feed boundary is required "
            + "unless an explicit unit-port pressure declaration anchors pressure and material flow"
        )

    def _resolved_connections_for_validation(self) -> tuple[_ResolvedConnection, ...]:
        resolved: list[_ResolvedConnection] = []
        for connection in self._connections:
            source_node_id, source_port_name = self._split_explicit_endpoint(connection.source)
            target_node_id, target_port_name = self._split_explicit_endpoint(connection.target)
            resolved.append(
                _ResolvedConnection(
                    source_node_id=source_node_id,
                    source_port_name=source_port_name,
                    source_node_kind=self._node_kind(node_id=source_node_id),
                    target_node_id=target_node_id,
                    target_port_name=target_port_name,
                    target_node_kind=self._node_kind(node_id=target_node_id),
                )
            )
        return tuple(resolved)

    def _validate_mandatory_inlets(
        self, *, resolved_connections: tuple[_ResolvedConnection, ...]
    ) -> None:
        connected_inlets = {
            (connection.target_node_id, connection.target_port_name)
            for connection in resolved_connections
        }
        unbound_inlets: list[str] = []
        for unit_id in sorted(self._units):
            for inlet_port in self._available_unit_ports(unit_id=unit_id, role="target"):
                if (unit_id, inlet_port) in connected_inlets:
                    continue
                unbound_inlets.append(f"{unit_id}.{inlet_port}")

        if unbound_inlets:
            listed_inlets = ", ".join(unbound_inlets)
            raise ValueError(
                "flowsheet compile validation failed: unbound mandatory inlet(s): "
                + f"{listed_inlets}. Connect each inlet to a feed or upstream unit."
            )

    def _validate_species_compatibility(
        self, *, resolved_connections: tuple[_ResolvedConnection, ...]
    ) -> None:
        registry = self._context.species_registry
        global_species_ids = tuple(registry.cas_list)
        global_species_set = set(global_species_ids)
        cas_to_name = {item.cas: item.name for item in registry.species}

        node_species_by_id: dict[str, set[str] | None] = {}
        for feed_id in sorted(self._feeds):
            stream = self._feeds[feed_id]
            if stream.species_ids is not None:
                if len(stream.species_ids) != len(stream.mole_fractions):
                    raise ValueError(
                        "flowsheet compile validation failed: "
                        + f"feed '{feed_id}' species metadata length mismatch "
                        + f"(species_ids={len(stream.species_ids)}, mole_fractions={len(stream.mole_fractions)})."
                    )
                unknown_species = tuple(
                    species_id
                    for species_id in stream.species_ids
                    if species_id not in global_species_set
                )
                if unknown_species:
                    unknown_list = ", ".join(
                        self._format_species_label(cas=species_id, cas_to_name=cas_to_name)
                        for species_id in sorted(set(unknown_species))
                    )
                    raise ValueError(
                        "flowsheet compile validation failed: "
                        + f"feed '{feed_id}' declares species outside runtime registry: {unknown_list}"
                    )
                node_species_by_id[feed_id] = set(stream.species_ids)
                continue

            if len(stream.mole_fractions) != len(global_species_ids):
                raise ValueError(
                    "flowsheet compile validation failed: "
                    + f"feed '{feed_id}' does not provide species_ids and has mole fraction length "
                    + f"{len(stream.mole_fractions)}, expected {len(global_species_ids)} for runtime registry alignment"
                )
            node_species_by_id[feed_id] = set(global_species_ids)

        for unit_id in sorted(self._units):
            node_species_by_id[unit_id] = self._resolve_node_species_ids(
                node_id=unit_id,
                cas_to_name=cas_to_name,
                global_species_ids=global_species_ids,
            )

        for connection in resolved_connections:
            target_species = node_species_by_id.get(connection.target_node_id)
            source_species = node_species_by_id.get(connection.source_node_id)
            if target_species is None or source_species is None:
                continue

            missing_species = sorted(target_species - source_species)
            if not missing_species:
                continue

            missing_list = ", ".join(
                self._format_species_label(cas=species_id, cas_to_name=cas_to_name)
                for species_id in missing_species
            )
            raise ValueError(
                "flowsheet compile validation failed: species mismatch on connection "
                + f"'{connection.source_node_id}.{connection.source_port_name}->"
                + f"{connection.target_node_id}.{connection.target_port_name}'. "
                + f"Target inlet '{connection.target_node_id}.{connection.target_port_name}' "
                + f"requires missing species: {missing_list}"
            )

    def _resolve_node_species_ids(
        self,
        *,
        node_id: str,
        cas_to_name: Mapping[str, str],
        global_species_ids: tuple[str, ...],
    ) -> set[str] | None:
        unit = self._units[node_id]

        species_names = getattr(unit, "species_names", None)
        if isinstance(species_names, tuple) and species_names:
            resolved_species: list[str] = []
            unknown_species: list[str] = []
            for raw_name in cast("tuple[object, ...]", species_names):
                normalized_name = str(raw_name).strip()
                if not normalized_name:
                    continue
                try:
                    species_index = self._context.species_registry.index_of(normalized_name)
                    resolved_species.append(global_species_ids[species_index])
                except ValueError:
                    unknown_species.append(normalized_name)
            if unknown_species:
                missing_list = ", ".join(sorted(set(unknown_species)))
                raise ValueError(
                    "flowsheet compile validation failed: "
                    + f"unit '{node_id}' declares species not present in runtime registry: "
                    + missing_list
                )
            if resolved_species:
                return set(resolved_species)

        n_species_value = getattr(unit, "n_species", None)
        if isinstance(n_species_value, (int, float)) and isfinite(float(n_species_value)):
            n_species = int(round(float(n_species_value)))
            if n_species > len(global_species_ids):
                available_list = ", ".join(
                    self._format_species_label(cas=cas, cas_to_name=cas_to_name)
                    for cas in global_species_ids
                )
                raise ValueError(
                    "flowsheet compile validation failed: "
                    + f"unit '{node_id}' expects {n_species} species but runtime registry provides "
                    + f"{len(global_species_ids)} ({available_list})"
                )
            if n_species == len(global_species_ids):
                return set(global_species_ids)
        return None

    def _format_species_label(self, *, cas: str, cas_to_name: Mapping[str, str]) -> str:
        common_name = cas_to_name.get(cas)
        if common_name is None:
            return cas
        return f"{common_name} ({cas})"

    def _warn_dangling_outlets(
        self, *, resolved_connections: tuple[_ResolvedConnection, ...]
    ) -> None:
        connected_outlets = {
            (connection.source_node_id, connection.source_port_name)
            for connection in resolved_connections
            if connection.source_node_kind in {"unit", "junction"}
        }
        dangling_outlets: list[str] = []
        for unit_id in sorted(self._units):
            for outlet_port in self._available_unit_ports(unit_id=unit_id, role="source"):
                if (unit_id, outlet_port) in connected_outlets:
                    continue
                dangling_outlets.append(f"{unit_id}.{outlet_port}")
        for junction_id in sorted(self._junctions):
            for outlet_port in self._available_junction_ports(
                junction_id=junction_id, role="source"
            ):
                if (junction_id, outlet_port) in connected_outlets:
                    continue
                dangling_outlets.append(f"{junction_id}.{outlet_port}")

        if not dangling_outlets:
            return
        warning_list = ", ".join(dangling_outlets)
        warnings.warn(
            "flowsheet compile validation warning: dangling outlet(s) with no downstream "
            + f"connection: {warning_list}",
            stacklevel=2,
        )

    def _warn_on_topology_issues(
        self, *, resolved_connections: tuple[_ResolvedConnection, ...]
    ) -> None:
        node_ids = set(self._units) | set(self._feeds) | set(self._junctions) | set(self._sinks)
        undirected_neighbors: dict[str, set[str]] = {node_id: set() for node_id in node_ids}
        directed_neighbors: dict[str, set[str]] = {node_id: set() for node_id in node_ids}

        for connection in resolved_connections:
            source_node_id = connection.source_node_id
            target_node_id = connection.target_node_id
            undirected_neighbors[source_node_id].add(target_node_id)
            undirected_neighbors[target_node_id].add(source_node_id)
            directed_neighbors[source_node_id].add(target_node_id)

        components: list[tuple[str, ...]] = []
        remaining_nodes = set(node_ids)
        while remaining_nodes:
            root = min(remaining_nodes)
            frontier = [root]
            visited: set[str] = set()
            while frontier:
                node_id = frontier.pop()
                if node_id in visited:
                    continue
                visited.add(node_id)
                frontier.extend(sorted(undirected_neighbors[node_id] - visited))
            components.append(tuple(sorted(visited)))
            remaining_nodes -= visited

        if len(components) > 1:
            component_text = " | ".join(
                "{" + ", ".join(component) + "}" for component in components
            )
            warnings.warn(
                "flowsheet compile validation warning: disconnected topology detected with "
                + f"{len(components)} subgraphs: {component_text}",
                stacklevel=2,
            )

        all_cycles = self._find_all_directed_cycles(directed_neighbors=directed_neighbors)
        if not all_cycles:
            return

        self._reject_invalid_recycle_loops(cycles=all_cycles)

    def _find_all_directed_cycles(
        self, *, directed_neighbors: dict[str, set[str]]
    ) -> list[tuple[str, ...]]:
        """Find all elementary directed cycles in the graph, deduplicated by canonical rotation.

        Uses a complete start-node DFS enumerator: for each node *s* (in sorted
        order), depth-first enumerate all simple cycles that return to *s*,
        only traversing neighbors with node id >= *s* so each cycle is emitted
        exactly once under its minimum node.  Uses a path list and *on_path*
        set with no blocked-set or suppression — this is obviously complete
        for the small graphs encountered in flowsheet topologies.
        """
        all_raw_cycles: list[tuple[str, ...]] = []

        for start_node in sorted(directed_neighbors):
            # DFS from start_node; only follow nodes >= start_node to avoid
            # double-counting cycles already enumerated from earlier start nodes.
            path: list[str] = [start_node]
            on_path: set[str] = {start_node}

            def _dfs(node: str) -> None:
                for neighbor in sorted(directed_neighbors.get(node, set())):
                    if neighbor < start_node:
                        continue  # skip nodes below start — those cycles were already found
                    if neighbor == start_node:
                        # Found a cycle: path contains the route back to start
                        all_raw_cycles.append(tuple((*path, start_node)))
                    elif neighbor not in on_path:
                        path.append(neighbor)
                        on_path.add(neighbor)
                        _dfs(neighbor)
                        on_path.remove(neighbor)
                        path.pop()

            _dfs(start_node)

        return self._deduplicate_cycles(all_raw_cycles)

    @staticmethod
    def _normalize_cycle(cycle: tuple[str, ...]) -> tuple[str, ...]:
        """Normalize a cycle to its lexicographically smallest rotation.

        Input cycle has the form (a, b, c, a) — last element repeats first.
        Output is the same form under the rotation that starts with the
        lexicographic minimum node.
        """
        body = cycle[:-1]
        if not body:
            return cycle
        min_idx = min(range(len(body)), key=lambda i: body[i])
        rotated_body = body[min_idx:] + body[:min_idx]
        return (*rotated_body, rotated_body[0])

    @staticmethod
    def _deduplicate_cycles(
        raw_cycles: list[tuple[str, ...]],
    ) -> list[tuple[str, ...]]:
        """Deduplicate cycles under canonical rotation, returning sorted unique cycles."""
        seen: set[tuple[str, ...]] = set()
        unique: list[tuple[str, ...]] = []
        for cycle in raw_cycles:
            normalized = Flowsheet._normalize_cycle(cycle)
            if normalized not in seen:
                seen.add(normalized)
                unique.append(normalized)
        unique.sort(key=lambda c: " -> ".join(c))
        return unique

    def _reject_invalid_recycle_loops(self, *, cycles: list[tuple[str, ...]]) -> None:
        """Raise a diagnostic ValueError for any directed cycles that lack a supported
        positive line-installed pump boost on their edges.

        When multiple connections exist between the same node pair (port-distinct
        parallel lines), each combination of edges forms a distinct cycle that
        must be checked independently.
        """
        from itertools import product as cartesian_product

        from modular_simulation.connection.domain.error_catalog import (
            DiagnosticValueError,
            build_diagnostic_payload,
        )

        # Build a multi-edge lookup: (source_node_id, target_node_id) -> list[_ConnectionSpec]
        edge_connections: dict[tuple[str, str], list[_ConnectionSpec]] = {}
        for connection in self._connections:
            source_node_id, _ = self._split_explicit_endpoint(connection.source)
            target_node_id, _ = self._split_explicit_endpoint(connection.target)
            edge_connections.setdefault((source_node_id, target_node_id), []).append(connection)

        invalid_loop_paths: list[str] = []
        for cycle in cycles:
            body = cycle[:-1]
            # Collect all connection options for each edge in this cycle.
            edge_options: list[list[_ConnectionSpec]] = []
            cycle_viable = True
            for i in range(len(body)):
                edge_key = (body[i], body[(i + 1) % len(body)])
                connections = edge_connections.get(edge_key, [])
                if not connections:
                    cycle_viable = False
                    break
                edge_options.append(connections)

            if not cycle_viable:
                continue

            # Determine whether any of the node-pair edges has parallel connections
            # (port-distinct parallel lines).  Used below to decide whether to
            # include concrete line-id identity in the diagnostic.
            has_parallel_edges = any(len(opts) > 1 for opts in edge_options)

            # For each concrete combination of edges, check pump validity.
            for edge_combo in cartesian_product(*edge_options):
                has_positive_boost = any(
                    conn.pump is not None and conn.pump.initial_pump_speed > 0.0
                    for conn in edge_combo
                )
                if not has_positive_boost:
                    node_path = " -> ".join(cycle)
                    if has_parallel_edges:
                        # Include the line IDs of the offending concrete combination so
                        # the user can distinguish the invalid path from pumped siblings.
                        combo_line_ids = ", ".join(conn.line_id for conn in edge_combo)
                        loop_path = f"{node_path} [lines: {combo_line_ids}]"
                    else:
                        loop_path = node_path
                    invalid_loop_paths.append(loop_path)
                    break  # One invalid combination is enough to report this cycle

        if not invalid_loop_paths:
            return

        invalid_loop_paths.sort()
        # Deduplicate identical loop path strings (can arise from normalization).
        seen_paths: list[str] = []
        for path in invalid_loop_paths:
            if path not in seen_paths:
                seen_paths.append(path)
        invalid_loop_paths = seen_paths

        if len(invalid_loop_paths) == 1:
            message = (
                f"flowsheet compile validation failed: recycle loop {invalid_loop_paths[0]} "
                f"has no positive line-installed pressure boost on any edge"
            )
        else:
            loop_descriptions = "; ".join(invalid_loop_paths)
            message = (
                f"flowsheet compile validation failed: {len(invalid_loop_paths)} recycle loops "
                f"have no positive line-installed pressure boost on any edge: {loop_descriptions}"
            )

        raise DiagnosticValueError(
            build_diagnostic_payload(
                code="INVALID_RECYCLE_LOOP",
                message=message,
                path="Flowsheet.compile",
                hint="Add a pump or pressure-boosting stage on the recycle path with a strictly positive initial_pump_speed",
            )
        )

    def run(self, steps: int, dt: float | None = None) -> FlowsheetResults:
        if steps < 0:
            raise ValueError("steps must be non-negative")
        macro_dt = self._dt if dt is None else float(dt)
        if not isfinite(macro_dt) or macro_dt <= 0.0:
            raise ValueError("macro-step dt must be finite and positive")

        plant = self.compile()
        step_results: list[ConnectedPlantStepResult] = []
        unit_state_trace_values: dict[str, dict[str, list[object]]] = {
            unit_id: {state_name: [] for state_name in unit.state_list}
            for unit_id, unit in self._units.items()
        }
        stream_trace_values: dict[str, dict[str, list[object]]] = {
            f"{connection.display_source}->{connection.display_target}": {
                "flow_rate": [],
                "temperature": [],
                "pressure": [],
                "composition": [],
            }
            for connection in self._connections
        }

        for _ in range(steps):
            step_result = plant.step(macro_step_time_s=macro_dt)
            step_results.append(step_result)

            for unit_id, unit in self._units.items():
                for state_name in unit.state_list:
                    state_value = cast("object", getattr(unit, state_name))
                    unit_state_trace_values[unit_id][state_name].append(state_value)

            for connection in self._connections:
                stream_key = f"{connection.display_source}->{connection.display_target}"
                stream = self._stream_snapshot_for_connection(connection=connection)
                stream_trace_values[stream_key]["flow_rate"].append(float(stream.molar_flow_rate))
                stream_trace_values[stream_key]["temperature"].append(float(stream.temperature))
                stream_trace_values[stream_key]["pressure"].append(float(stream.pressure))
                stream_trace_values[stream_key]["composition"].append(
                    tuple(float(value) for value in stream.mole_fractions)
                )

        return FlowsheetResults(
            step_results=tuple(step_results),
            time_points=np.asarray(
                [result.simulation_time_s for result in step_results],
                dtype=np.float64,
            ),
            units=self._build_unit_results(state_trace_values=unit_state_trace_values),
            streams=self._build_stream_histories(trace_values=stream_trace_values),
        )

    def _stream_snapshot_for_connection(self, connection: _ConnectionSpec) -> StreamData:
        source_node_id, source_port_name = self._split_explicit_endpoint(connection.source)
        if source_node_id in self._feeds:
            return self._feeds[source_node_id]

        runtime_stream = self._runtime_outlet_stream_snapshot(
            node_id=source_node_id,
            port_name=source_port_name,
        )
        if runtime_stream is not None:
            return runtime_stream

        target_node_id, target_port_name = self._split_explicit_endpoint(connection.target)
        plant = self._compiled_plant
        if plant is not None:
            inlet_condition = plant.runtime_orchestrator.get_latest_inlet_condition(
                node_id=target_node_id,
                port_name=target_port_name,
            )
            if inlet_condition is not None:
                return StreamData.from_port_condition(inlet_condition)

            source_inlet_condition = plant.runtime_orchestrator.get_latest_inlet_condition(
                node_id=source_node_id,
                port_name=source_port_name,
            )
            if source_inlet_condition is not None:
                return StreamData.from_port_condition(source_inlet_condition)

        return self._require_runtime_outlet_stream_snapshot(
            node_id=source_node_id,
            port_name=source_port_name,
        )

    def _build_unit_results(
        self,
        *,
        state_trace_values: Mapping[str, Mapping[str, list[object]]],
    ) -> dict[str, UnitResult]:
        unit_results: dict[str, UnitResult] = {}
        for unit_id in self._units:
            outlet_streams = {
                port_name: self._require_runtime_outlet_stream_snapshot(
                    node_id=unit_id,
                    port_name=port_name,
                )
                for port_name in self._available_unit_ports(unit_id=unit_id, role="source")
            }
            unit_results[unit_id] = UnitResult(
                unit_id=unit_id,
                outlet_streams=outlet_streams,
                state_history=self._extract_state_history(
                    unit_id=unit_id,
                    state_samples=state_trace_values.get(unit_id, {}),
                ),
            )
        return unit_results

    def _runtime_outlet_stream_snapshot(self, *, node_id: str, port_name: str) -> StreamData | None:
        plant = self._compiled_plant
        if plant is None:
            return None

        outlet_condition = plant.runtime_orchestrator.get_latest_outlet_condition(
            node_id=node_id,
            port_name=port_name,
        )
        if outlet_condition is None:
            return None
        return StreamData.from_port_condition(outlet_condition)

    def _require_runtime_outlet_stream_snapshot(
        self, *, node_id: str, port_name: str
    ) -> StreamData:
        runtime_stream = self._runtime_outlet_stream_snapshot(node_id=node_id, port_name=port_name)
        if runtime_stream is not None:
            return runtime_stream
        raise RuntimeError(
            "missing runtime-owned outlet snapshot for "
            + f"'{node_id}.{port_name}'; run at least one step before requesting flowsheet stream snapshots/results"
        )

    def _extract_state_history(
        self,
        *,
        unit_id: str,
        state_samples: Mapping[str, list[object]],
    ) -> dict[str, NDArray[np.float64]]:
        process_model = self._subsystems[unit_id].system.process_model

        history_by_state: dict[str, NDArray[np.float64]] = {}
        for state_name in process_model.state_list:
            state_values = state_samples.get(state_name, [])
            try:
                history_by_state[state_name] = np.asarray(state_values, dtype=np.float64)
            except ValueError as error:
                raise ValueError(
                    f"inconsistent history shape for unit '{unit_id}' state '{state_name}'"
                ) from error
        return history_by_state

    def _build_stream_histories(
        self,
        *,
        trace_values: Mapping[str, Mapping[str, list[object]]],
    ) -> dict[str, StreamHistory]:
        stream_histories: dict[str, StreamHistory] = {}
        for stream_key, trace_data in trace_values.items():
            composition_rows = cast("list[tuple[float, ...]]", trace_data["composition"])
            if not composition_rows:
                composition_array = np.zeros((0, 0), dtype=np.float64)
            else:
                n_species = len(composition_rows[0])
                if any(len(row) != n_species for row in composition_rows):
                    raise ValueError(
                        f"inconsistent composition history shape for stream '{stream_key}'"
                    )
                composition_array = np.asarray(composition_rows, dtype=np.float64)

            stream_histories[stream_key] = StreamHistory(
                flow_rate=np.asarray(trace_data["flow_rate"], dtype=np.float64),
                temperature=np.asarray(trace_data["temperature"], dtype=np.float64),
                pressure=np.asarray(trace_data["pressure"], dtype=np.float64),
                composition=composition_array,
            )
        return stream_histories

    def get_unit(self, unit_id: str) -> ProcessModel:
        normalized_unit_id = self._normalize_node_id(unit_id=unit_id, field_name="unit_id")
        unit = self._units.get(normalized_unit_id)
        if unit is None:
            raise ValueError(f"unknown unit '{normalized_unit_id}'")
        return unit

    def get_system(self, unit_id: str) -> System:
        normalized_unit_id = self._normalize_node_id(unit_id=unit_id, field_name="unit_id")
        subsystem = self._subsystems.get(normalized_unit_id)
        if subsystem is None:
            raise ValueError(f"unknown unit '{normalized_unit_id}'")
        return subsystem.system

    def _build_hydraulic_system(self, topology: TopologyGraph) -> HydraulicSystemDefinition:
        equations: list[ElementEquation] = []
        linear_residual_equations: list[LinearResidualEquation] = []
        pressure_anchor_metadata: list[HydraulicPressureAnchorMetadata] = []
        node_specs_by_key = self._build_hydraulic_node_specs(topology=topology)
        line_flow_unknown_by_line: dict[str, str] = {}
        edge_source_pressure_unknown_by_line: dict[str, str] = {}
        edge_target_pressure_unknown_by_line: dict[str, str] = {}
        node_pressure_unknown_by_endpoint: dict[str, str] = {}
        node_pressure_unknown_by_junction: dict[str, str] = {}

        for edge in sorted(topology.edges, key=lambda item: item.edge_id):
            source_key = self._hydraulic_node_key(
                node_id=edge.source.node_id,
                port_name=edge.source.port_name,
                topology=topology,
            )
            target_key = self._hydraulic_node_key(
                node_id=edge.target.node_id,
                port_name=edge.target.port_name,
                topology=topology,
            )
            source_node_spec = node_specs_by_key[source_key]
            target_node_spec = node_specs_by_key[target_key]

            element = CanonicalNodePressureHydraulicElement(
                wrapped=self._resolve_hydraulic_element_for_connection(
                    line_id=edge.edge_id,
                    source_node_id=edge.source.node_id,
                    source_port_name=edge.source.port_name,
                )
            )
            parameters = self._resolve_element_parameters(
                source_node_id=edge.source.node_id,
                source_port_name=edge.source.port_name,
                target_node_id=edge.target.node_id,
                line_id=edge.edge_id,
                element=element.wrapped,
            )
            equations.append(
                ElementEquation(
                    name=edge.edge_id,
                    element=element,
                    inputs=MappingProxyType({}),
                    parameters=parameters,
                    unknown_name_map=MappingProxyType(
                        {
                            "flow_rate": edge.edge_id,
                            "upstream_pressure": source_node_spec.pressure_unknown_name,
                            "downstream_pressure": target_node_spec.pressure_unknown_name,
                        }
                    ),
                    residual_name_map=MappingProxyType(
                        {"head_balance": f"{edge.edge_id}_head_balance"}
                    ),
                )
            )
            line_flow_unknown_by_line[edge.edge_id] = edge.edge_id
            edge_source_pressure_unknown_by_line[edge.edge_id] = (
                source_node_spec.pressure_unknown_name
            )
            edge_target_pressure_unknown_by_line[edge.edge_id] = (
                target_node_spec.pressure_unknown_name
            )

        incidence_by_node_key: dict[str, list[tuple[str, float]]] = {
            node_key: [] for node_key in node_specs_by_key
        }
        for edge in sorted(topology.edges, key=lambda item: item.edge_id):
            source_key = self._hydraulic_node_key(
                node_id=edge.source.node_id,
                port_name=edge.source.port_name,
                topology=topology,
            )
            target_key = self._hydraulic_node_key(
                node_id=edge.target.node_id,
                port_name=edge.target.port_name,
                topology=topology,
            )
            incidence_by_node_key[source_key].append((edge.edge_id, -1.0))
            incidence_by_node_key[target_key].append((edge.edge_id, 1.0))

        self._append_inferred_unit_hydraulic_relations(
            topology=topology,
            node_specs_by_key=node_specs_by_key,
            incidence_by_node_key=incidence_by_node_key,
            linear_residual_equations=linear_residual_equations,
        )

        for node_key in sorted(node_specs_by_key):
            node_spec = node_specs_by_key[node_key]
            incidence_count = len(incidence_by_node_key[node_key])
            for endpoint_id in node_spec.endpoint_ids:
                node_pressure_unknown_by_endpoint[endpoint_id] = node_spec.pressure_unknown_name
            if node_key.startswith("junction:"):
                node_pressure_unknown_by_junction[node_key.removeprefix("junction:")] = (
                    node_spec.pressure_unknown_name
                )

            if node_key.startswith("process:") and incidence_count > 1:
                node_id, port_name = node_key.removeprefix("process:").split(".", maxsplit=1)
                if not self._process_port_supports_direct_multi_edge_balancing(
                    node_id=node_id,
                    port_name=port_name,
                    incidence_count=incidence_count,
                ):
                    raise ValueError(
                        "direct unit-port fan-in/fan-out is illegal at {}: {} incident lines attach to one unit port; add an explicit junction or use a unit model that declares the required hydraulic balancing semantics".format(
                            node_spec.topology_label,
                            incidence_count,
                        )
                    )

            if node_spec.anchor_pressure_pa is not None and incidence_count > 1:
                raise ValueError(
                    "over-constrained hydraulic boundary conditions at {}: {} incident lines share one anchored hydraulic node; add an explicit junction or remove the fixed-pressure anchor".format(
                        node_spec.topology_label,
                        incidence_count,
                    )
                )

            needs_mass_balance = incidence_count > 1 or node_key.startswith("junction:")
            if needs_mass_balance:
                coefficients = {
                    line_id: coefficient for line_id, coefficient in incidence_by_node_key[node_key]
                }
                linear_residual_equations.append(
                    LinearResidualEquation(
                        residual_name=f"{node_spec.pressure_unknown_name}__mass_balance",
                        coefficients=MappingProxyType(coefficients),
                        constant=0.0,
                    )
                )

            anchor_pressure_pa = node_spec.anchor_pressure_pa
            if anchor_pressure_pa is not None:
                residual_name = f"{node_spec.pressure_unknown_name}__anchor"
                linear_residual_equations.append(
                    LinearResidualEquation(
                        residual_name=residual_name,
                        coefficients=MappingProxyType({node_spec.pressure_unknown_name: 1.0}),
                        constant=-anchor_pressure_pa,
                    )
                )
                pressure_anchor_metadata.append(
                    HydraulicPressureAnchorMetadata(
                        pressure_unknown_name=node_spec.pressure_unknown_name,
                        residual_name=residual_name,
                        pressure_value=anchor_pressure_pa,
                        topology_label=node_spec.topology_label,
                    )
                )

        topology_lookup = HydraulicTopologyLookup(
            line_flow_unknown_by_line=MappingProxyType(
                dict(sorted(line_flow_unknown_by_line.items()))
            ),
            edge_source_pressure_unknown_by_line=MappingProxyType(
                dict(sorted(edge_source_pressure_unknown_by_line.items()))
            ),
            edge_target_pressure_unknown_by_line=MappingProxyType(
                dict(sorted(edge_target_pressure_unknown_by_line.items()))
            ),
            node_pressure_unknown_by_endpoint=MappingProxyType(
                dict(sorted(node_pressure_unknown_by_endpoint.items()))
            ),
            node_pressure_unknown_by_junction=MappingProxyType(
                dict(sorted(node_pressure_unknown_by_junction.items()))
            ),
        )
        return HydraulicSystemDefinition(
            equations=tuple(equations),
            linear_residual_equations=tuple(linear_residual_equations),
            topology_lookup=topology_lookup,
            pressure_anchor_metadata=tuple(pressure_anchor_metadata),
        )

    def _configure_edge_hydraulic_actuator_state(
        self,
        *,
        network: ConnectionNetwork,
        line_id: str,
        source_endpoint: str,
    ) -> None:
        if "." not in source_endpoint:
            return

        source_node_id, source_port_name = self._split_explicit_endpoint(source_endpoint)
        source_unit = self._units.get(source_node_id)
        if source_unit is None:
            return

        element = self._resolve_hydraulic_element(
            source_node_id=source_node_id,
            source_port_name=source_port_name,
            target_node_id=source_node_id,
        )
        bootstrap = element.line_bootstrap(
            source_unit=source_unit,
            source_node_id=source_node_id,
            source_port_name=source_port_name,
            line_id=line_id,
        )
        if bootstrap is None:
            return

        geometry = bootstrap.geometry
        if geometry is not None:
            network.configure_line_geometry(
                line_id=line_id,
                radius_m=geometry.radius_m,
                length_m=geometry.length_m,
                equation_name=line_id,
                resistance_parameter_name=geometry.resistance_parameter_name,
            )

        resistance = bootstrap.resistance
        if resistance is not None:
            network.configure_line_resistance(
                line_id=line_id,
                mode=resistance.mode,
                manual_value=resistance.manual_value,
            )

        valve = bootstrap.valve
        if valve is not None:
            network.attach_line_valve(
                line_id=line_id,
                valve_id=valve.valve_id,
                minimum_open_fraction=valve.minimum_open_fraction,
                maximum_open_fraction=valve.maximum_open_fraction,
                initial_open_fraction=valve.initial_open_fraction,
                equation_name=line_id,
                resistance_parameter_name=valve.resistance_parameter_name,
            )

        pump = bootstrap.pump
        if pump is not None:
            network.attach_line_pump(
                line_id=line_id,
                pump_id=pump.pump_id,
                initial_pump_speed=pump.initial_pump_speed,
                equation_name=line_id,
                pump_parameter_name=pump.pump_parameter_name,
            )

    def _resolve_hydraulic_element(
        self, *, source_node_id: str, source_port_name: str, target_node_id: str
    ) -> HydraulicElement:
        del target_node_id
        return self._resolve_hydraulic_element_for_connection(
            line_id=None,
            source_node_id=source_node_id,
            source_port_name=source_port_name,
        )

    def _resolve_hydraulic_element_for_connection(
        self,
        *,
        line_id: str | None,
        source_node_id: str,
        source_port_name: str,
    ) -> HydraulicElement:
        connection = None if line_id is None else self._connection_by_line_id(line_id)
        if connection is not None and connection.pump is not None:
            return self._line_installed_pump_element()
        if connection is not None and connection.valve is not None:
            return self._line_installed_valve_element()
        return resolve_hydraulic_element(
            source_unit=self._units.get(source_node_id),
            source_node_id=source_node_id,
            source_port_name=source_port_name,
        )

    def _line_installed_pump_element(self) -> HydraulicElement:
        from modular_simulation.connection.hydraulics.hydraulic_element import PumpHydraulicElement

        return cast(
            HydraulicElement,
            PumpHydraulicElement(
                dp_curve=_line_installed_pump_pressure_rise_curve,
                d_dp_d_mdot=_line_installed_pump_pressure_rise_derivative,
            ),
        )

    def _line_installed_valve_element(self) -> HydraulicElement:
        from modular_simulation.connection.hydraulics.hydraulic_element import ValveHydraulicElement

        return cast(HydraulicElement, ValveHydraulicElement())

    def _connection_by_line_id(self, line_id: str) -> _ConnectionSpec | None:
        for connection in self._connections:
            if connection.line_id == line_id:
                return connection
        return None

    def _resolve_element_parameters(
        self,
        *,
        line_id: str | None,
        element: HydraulicElement,
        source_node_id: str,
        source_port_name: str,
        target_node_id: str,
    ) -> Mapping[str, float]:
        connection = None if line_id is None else self._connection_by_line_id(line_id)
        if connection is not None and connection.pump is not None:
            return MappingProxyType({"pump_speed": connection.pump.initial_pump_speed})
        if connection is not None and connection.valve is not None:
            return MappingProxyType({"valve_resistance": 1.0, "delta": 1.0e-6})
        return element.default_parameters(
            source_unit=self._units.get(source_node_id),
            source_node_id=source_node_id,
            source_port_name=source_port_name,
            target_unit=self._units.get(target_node_id),
            target_node_id=target_node_id,
        )

    def _build_hydraulic_node_specs(
        self, *, topology: TopologyGraph
    ) -> dict[str, _HydraulicNodeCompileSpec]:
        endpoint_ids_by_key: dict[str, set[str]] = {}
        connected_process_ids: set[str] = set()
        for edge in sorted(topology.edges, key=lambda item: item.edge_id):
            for endpoint in (edge.source, edge.target):
                node_key = self._hydraulic_node_key(
                    node_id=endpoint.node_id,
                    port_name=endpoint.port_name,
                    topology=topology,
                )
                endpoint_ids_by_key.setdefault(node_key, set()).add(
                    f"{endpoint.node_id}.{endpoint.port_name}"
                )
                if endpoint.node_id in self._units:
                    connected_process_ids.add(endpoint.node_id)

        for process_node in topology.process_nodes:
            if process_node.process_id not in connected_process_ids:
                continue
            for outlet_port in process_node.outlet_ports:
                endpoint_id = f"{process_node.process_id}.{outlet_port}"
                node_key = self._hydraulic_node_key(
                    node_id=process_node.process_id,
                    port_name=outlet_port,
                    topology=topology,
                )
                endpoint_ids_by_key.setdefault(node_key, set()).add(endpoint_id)

        specs: dict[str, _HydraulicNodeCompileSpec] = {}
        for node_key in sorted(endpoint_ids_by_key):
            pressure_unknown_name = self._pressure_unknown_name(node_key=node_key)
            endpoint_ids = tuple(sorted(endpoint_ids_by_key[node_key]))

            if node_key.startswith("junction:"):
                junction_id = node_key.removeprefix("junction:")
                specs[node_key] = _HydraulicNodeCompileSpec(
                    node_key=node_key,
                    topology_label=f"junction:{junction_id}",
                    pressure_unknown_name=pressure_unknown_name,
                    endpoint_ids=endpoint_ids,
                    anchor_pressure_pa=None,
                )
                continue

            endpoint_id = endpoint_ids[0]
            node_id, port_name = endpoint_id.split(".", maxsplit=1)
            anchor_pressure = self._resolve_hydraulic_anchor_pressure(
                node_id=node_id,
                port_name=port_name,
                topology=topology,
            )
            if anchor_pressure is None and self._is_implicit_terminal_outlet_anchor(
                node_id=node_id,
                port_name=port_name,
                topology=topology,
            ):
                anchor_pressure = 101325.0
            specs[node_key] = _HydraulicNodeCompileSpec(
                node_key=node_key,
                topology_label=endpoint_id,
                pressure_unknown_name=pressure_unknown_name,
                endpoint_ids=endpoint_ids,
                anchor_pressure_pa=anchor_pressure,
            )
        return specs

    def _is_implicit_terminal_outlet_anchor(
        self, *, node_id: str, port_name: str, topology: TopologyGraph
    ) -> bool:
        if node_id not in self._units:
            return False
        if port_name not in self._available_unit_ports(unit_id=node_id, role="source"):
            return False
        return not any(
            edge.source.node_id == node_id and edge.source.port_name == port_name
            for edge in topology.edges
        )

    def _hydraulic_node_key(self, *, node_id: str, port_name: str, topology: TopologyGraph) -> str:
        if any(junction.junction_id == node_id for junction in topology.junction_nodes):
            return f"junction:{node_id}"
        if any(boundary.boundary_id == node_id for boundary in topology.boundary_nodes):
            return f"boundary:{node_id}.{port_name}"
        return f"process:{node_id}.{port_name}"

    def _pressure_unknown_name(self, *, node_key: str) -> str:
        sanitized = "".join(
            character if character.isalnum() else "_" for character in node_key.strip()
        ).strip("_")
        return f"pressure__{sanitized}"

    def _resolve_hydraulic_anchor_pressure(
        self, *, node_id: str, port_name: str, topology: TopologyGraph | None
    ) -> float | None:
        if topology is not None and any(
            boundary.boundary_id == node_id for boundary in topology.boundary_nodes
        ):
            return self._boundary_pressure(node_id=node_id)
        return self._process_port_pressure(node_id=node_id, port_name=port_name)

    def _boundary_pressure(self, *, node_id: str) -> float:
        feed_stream = self._feeds.get(node_id)
        if feed_stream is not None:
            return float(feed_stream.pressure)
        return 101325.0

    def _process_port_pressure(self, *, node_id: str, port_name: str) -> float | None:
        unit = self._units.get(node_id)
        if unit is None:
            return None

        outlet_ports = self._available_unit_ports(unit_id=node_id, role="source")
        inlet_ports = self._available_unit_ports(unit_id=node_id, role="target")

        if port_name in outlet_ports:
            for attribute_name in self._pressure_attribute_candidates(
                port_name=port_name,
                role="source",
            ):
                value = self._explicit_pressure_attribute_value(
                    unit=unit,
                    attribute_name=attribute_name,
                )
                if value is not None:
                    return value
            for attribute_name in self._pressure_vector_attribute_candidates(role="source"):
                value = self._explicit_pressure_vector_value(
                    unit=unit,
                    attribute_name=attribute_name,
                    port_name=port_name,
                    ordered_ports=outlet_ports,
                )
                if value is not None:
                    return value

        if port_name in inlet_ports:
            for attribute_name in self._pressure_attribute_candidates(
                port_name=port_name,
                role="target",
            ):
                value = self._explicit_pressure_attribute_value(
                    unit=unit,
                    attribute_name=attribute_name,
                )
                if value is not None:
                    return value
            for attribute_name in self._pressure_vector_attribute_candidates(role="target"):
                value = self._explicit_pressure_vector_value(
                    unit=unit,
                    attribute_name=attribute_name,
                    port_name=port_name,
                    ordered_ports=inlet_ports,
                )
                if value is not None:
                    return value

        return None

    def _pressure_attribute_candidates(
        self, *, port_name: str, role: Literal["source", "target"]
    ) -> tuple[str, ...]:
        stripped_suffix = "_outlet" if role == "source" else "_inlet"
        stripped_port_name = port_name.removesuffix(stripped_suffix)
        candidates = [f"{port_name}_pressure"]
        if stripped_port_name and stripped_port_name != port_name:
            candidates.append(f"{stripped_port_name}_pressure")
        candidates.append("outlet_pressure" if role == "source" else "inlet_pressure")
        return tuple(dict.fromkeys(candidates))

    def _pressure_vector_attribute_candidates(
        self, *, role: Literal["source", "target"]
    ) -> tuple[str, ...]:
        return ("outlet_pressures",) if role == "source" else ("inlet_pressures",)

    def _explicit_pressure_attribute_value(
        self, *, unit: ProcessModel, attribute_name: str
    ) -> float | None:
        if not self._pressure_attribute_was_explicitly_declared(
            unit=unit,
            attribute_name=attribute_name,
        ):
            return None
        raw_value = self._explicit_declared_field_value(unit=unit, attribute_name=attribute_name)
        return self._pressure_value_from_object(raw_value)

    def _explicit_pressure_vector_value(
        self,
        *,
        unit: ProcessModel,
        attribute_name: str,
        port_name: str,
        ordered_ports: tuple[str, ...],
    ) -> float | None:
        if not self._pressure_attribute_was_explicitly_declared(
            unit=unit,
            attribute_name=attribute_name,
        ):
            return None
        raw_vector = self._explicit_declared_field_value(unit=unit, attribute_name=attribute_name)
        return self._pressure_vector_object_value(
            raw_vector=raw_vector,
            port_name=port_name,
            ordered_ports=ordered_ports,
        )

    def _explicit_declared_field_value(self, *, unit: ProcessModel, attribute_name: str) -> object:
        snapshots = self._user_declared_field_values_by_unit_object_id.get(id(unit))
        if snapshots is not None and attribute_name in snapshots:
            return snapshots[attribute_name]
        return getattr(unit, attribute_name, None)

    def _pressure_attribute_was_explicitly_declared(
        self, *, unit: ProcessModel, attribute_name: str
    ) -> bool:
        if not self._field_was_explicitly_declared(unit=unit, attribute_name=attribute_name):
            return False
        state_metadata = unit.state_metadata_dict.get(attribute_name)
        if state_metadata is None:
            return False
        return state_metadata.type in {StateType.BOUNDARY, StateType.ALGEBRAIC}

    def _field_was_explicitly_declared(self, *, unit: ProcessModel, attribute_name: str) -> bool:
        explicit_fields = self._user_declared_fields_by_unit_object_id.get(id(unit))
        if explicit_fields is None:
            model_fields_set = getattr(unit, "model_fields_set", None)
            if not isinstance(model_fields_set, set):
                return False
            explicit_fields = frozenset(model_fields_set)
        return attribute_name in explicit_fields

    def _pressure_attribute_value(self, *, unit: ProcessModel, attribute_name: str) -> float | None:
        value = getattr(unit, attribute_name, None)
        return self._pressure_value_from_object(value)

    def _pressure_value_from_object(self, value: object) -> float | None:
        if isinstance(value, (int, float)) and isfinite(float(value)) and float(value) > 0.0:
            return float(value)
        return None

    def _pressure_vector_value(
        self,
        *,
        unit: ProcessModel,
        attribute_name: str,
        port_name: str,
        ordered_ports: tuple[str, ...],
    ) -> float | None:
        raw_vector = getattr(unit, attribute_name, None)
        return self._pressure_vector_object_value(
            raw_vector=raw_vector,
            port_name=port_name,
            ordered_ports=ordered_ports,
        )

    def _pressure_vector_object_value(
        self,
        *,
        raw_vector: object,
        port_name: str,
        ordered_ports: tuple[str, ...],
    ) -> float | None:
        if raw_vector is None or port_name not in ordered_ports:
            return None
        try:
            vector = np.asarray(raw_vector, dtype=float).reshape(-1)
        except Exception:
            return None
        port_index = ordered_ports.index(port_name)
        if port_index >= vector.size:
            return None
        value = float(vector[port_index])
        if isfinite(value) and value > 0.0:
            return value
        return None

    def _append_inferred_unit_hydraulic_relations(
        self,
        *,
        topology: TopologyGraph,
        node_specs_by_key: Mapping[str, _HydraulicNodeCompileSpec],
        incidence_by_node_key: Mapping[str, list[tuple[str, float]]],
        linear_residual_equations: list[LinearResidualEquation],
    ) -> None:
        self._append_inferred_unit_flow_balance_equations(
            topology=topology,
            incidence_by_node_key=incidence_by_node_key,
            linear_residual_equations=linear_residual_equations,
        )
        self._append_inferred_unit_pressure_relation_equations(
            topology=topology,
            node_specs_by_key=node_specs_by_key,
            linear_residual_equations=linear_residual_equations,
        )

    def _append_inferred_unit_flow_balance_equations(
        self,
        *,
        topology: TopologyGraph,
        incidence_by_node_key: Mapping[str, list[tuple[str, float]]],
        linear_residual_equations: list[LinearResidualEquation],
    ) -> None:
        candidates: list[_UnitFlowBalanceEquationCandidate] = []
        for unit_id in sorted(self._units):
            for group_index, port_group in enumerate(
                self._infer_unit_flow_balance_groups(unit_id=unit_id),
                start=1,
            ):
                coefficients: dict[str, float] = {}
                connected_port_count = 0
                for port_name in port_group:
                    node_key = self._hydraulic_node_key(
                        node_id=unit_id,
                        port_name=port_name,
                        topology=topology,
                    )
                    incidences = incidence_by_node_key.get(node_key, [])
                    if incidences:
                        connected_port_count += 1
                    for line_id, coefficient in incidences:
                        coefficients[line_id] = coefficients.get(line_id, 0.0) + coefficient
                normalized_coefficients = {
                    line_id: coefficient
                    for line_id, coefficient in sorted(coefficients.items())
                    if coefficient != 0.0
                }
                if connected_port_count <= 1 or not normalized_coefficients:
                    continue
                candidates.append(
                    _UnitFlowBalanceEquationCandidate(
                        residual_name=(f"unit__{unit_id}__flow_balance__{group_index:02d}"),
                        coefficients=MappingProxyType(normalized_coefficients),
                    )
                )

        for candidate in self._prune_redundant_unit_flow_balance_equations(candidates):
            linear_residual_equations.append(
                LinearResidualEquation(
                    residual_name=candidate.residual_name,
                    coefficients=candidate.coefficients,
                    constant=0.0,
                )
            )

    def _prune_redundant_unit_flow_balance_equations(
        self,
        candidates: tuple[_UnitFlowBalanceEquationCandidate, ...]
        | list[_UnitFlowBalanceEquationCandidate],
    ) -> tuple[_UnitFlowBalanceEquationCandidate, ...]:
        if len(candidates) <= 1:
            return tuple(candidates)

        line_to_candidate_indexes: dict[str, set[int]] = {}
        for index, candidate in enumerate(candidates):
            for line_id in candidate.coefficients:
                line_to_candidate_indexes.setdefault(line_id, set()).add(index)

        adjacency: dict[int, set[int]] = {index: set() for index in range(len(candidates))}
        for indexes in line_to_candidate_indexes.values():
            for index in indexes:
                adjacency[index].update(other for other in indexes if other != index)

        visited: set[int] = set()
        omitted_indexes: set[int] = set()
        for start_index in range(len(candidates)):
            if start_index in visited:
                continue
            stack = [start_index]
            component_indexes: set[int] = set()
            while stack:
                current_index = stack.pop()
                if current_index in visited:
                    continue
                visited.add(current_index)
                component_indexes.add(current_index)
                stack.extend(sorted(adjacency[current_index] - visited))

            component_line_ids = {
                line_id
                for candidate_index in component_indexes
                for line_id in candidates[candidate_index].coefficients
            }
            if not component_line_ids:
                continue

            is_closed_component = all(
                len(line_to_candidate_indexes[line_id] & component_indexes) == 2
                for line_id in component_line_ids
            )
            if not is_closed_component:
                continue

            omitted_indexes.add(max(component_indexes))

        return tuple(
            candidate for index, candidate in enumerate(candidates) if index not in omitted_indexes
        )

    def _append_inferred_unit_pressure_relation_equations(
        self,
        *,
        topology: TopologyGraph,
        node_specs_by_key: Mapping[str, _HydraulicNodeCompileSpec],
        linear_residual_equations: list[LinearResidualEquation],
    ) -> None:
        for unit_id in sorted(self._units):
            for relation_index, relation in enumerate(
                self._infer_unit_pressure_relations(unit_id=unit_id),
                start=1,
            ):
                inlet_key = self._hydraulic_node_key(
                    node_id=unit_id,
                    port_name=relation.inlet_port_name,
                    topology=topology,
                )
                outlet_key = self._hydraulic_node_key(
                    node_id=unit_id,
                    port_name=relation.outlet_port_name,
                    topology=topology,
                )
                inlet_node_spec = node_specs_by_key.get(inlet_key)
                outlet_node_spec = node_specs_by_key.get(outlet_key)
                if inlet_node_spec is None or outlet_node_spec is None:
                    continue

                self._validate_unit_pressure_relation_anchor_consistency(
                    unit_id=unit_id,
                    relation=relation,
                    inlet_node_spec=inlet_node_spec,
                    outlet_node_spec=outlet_node_spec,
                )
                if (
                    inlet_node_spec.anchor_pressure_pa is not None
                    and outlet_node_spec.anchor_pressure_pa is not None
                ):
                    continue

                linear_residual_equations.append(
                    LinearResidualEquation(
                        residual_name=(f"unit__{unit_id}__pressure_relation__{relation_index:02d}"),
                        coefficients=MappingProxyType(
                            {
                                inlet_node_spec.pressure_unknown_name: 1.0,
                                outlet_node_spec.pressure_unknown_name: -1.0,
                            }
                        ),
                        constant=-relation.pressure_drop_pa,
                    )
                )

    def _infer_unit_flow_balance_groups(self, *, unit_id: str) -> tuple[tuple[str, ...], ...]:
        inlet_ports = self._available_unit_ports(unit_id=unit_id, role="target")
        outlet_ports = self._available_unit_ports(unit_id=unit_id, role="source")
        if not inlet_ports or not outlet_ports:
            return ()

        pairwise_groups = self._infer_pairwise_unit_flow_balance_groups(
            unit_id=unit_id,
            inlet_ports=inlet_ports,
            outlet_ports=outlet_ports,
        )
        if pairwise_groups:
            return pairwise_groups

        if len(inlet_ports) == 1 or len(outlet_ports) == 1:
            combined_group = tuple((*inlet_ports, *outlet_ports))
            if all(
                self._port_exposes_flow_metadata(
                    unit_id=unit_id,
                    port_name=port_name,
                    role="target" if port_name in inlet_ports else "source",
                )
                for port_name in combined_group
            ):
                return (combined_group,)
        return ()

    def _infer_pairwise_unit_flow_balance_groups(
        self,
        *,
        unit_id: str,
        inlet_ports: tuple[str, ...],
        outlet_ports: tuple[str, ...],
    ) -> tuple[tuple[str, ...], ...]:
        if len(inlet_ports) != len(outlet_ports) or len(inlet_ports) <= 1:
            return ()

        inlet_by_prefix: dict[str, str] = {}
        for port_name in inlet_ports:
            prefix = self._paired_port_prefix(port_name=port_name, suffix="_inlet")
            if prefix is None or prefix in inlet_by_prefix:
                return ()
            inlet_by_prefix[prefix] = port_name

        outlet_by_prefix: dict[str, str] = {}
        for port_name in outlet_ports:
            prefix = self._paired_port_prefix(port_name=port_name, suffix="_outlet")
            if prefix is None or prefix in outlet_by_prefix:
                return ()
            outlet_by_prefix[prefix] = port_name

        if set(inlet_by_prefix) != set(outlet_by_prefix):
            return ()

        groups: list[tuple[str, ...]] = []
        for prefix in sorted(inlet_by_prefix):
            inlet_port_name = inlet_by_prefix[prefix]
            outlet_port_name = outlet_by_prefix[prefix]
            if not self._port_exposes_flow_metadata(
                unit_id=unit_id,
                port_name=inlet_port_name,
                role="target",
            ) or not self._port_exposes_flow_metadata(
                unit_id=unit_id,
                port_name=outlet_port_name,
                role="source",
            ):
                return ()
            groups.append((inlet_port_name, outlet_port_name))
        return tuple(groups)

    def _paired_port_prefix(self, *, port_name: str, suffix: str) -> str | None:
        if not port_name.endswith(suffix):
            return None
        prefix = port_name.removesuffix(suffix).strip("_")
        if not prefix:
            return None
        return prefix

    def _port_exposes_flow_metadata(
        self,
        *,
        unit_id: str,
        port_name: str,
        role: Literal["source", "target"],
    ) -> bool:
        unit = self._units[unit_id]
        expected_state_type = StateType.ALGEBRAIC if role == "source" else StateType.BOUNDARY
        for attribute_name in self._flow_attribute_candidates(
            unit_id=unit_id,
            port_name=port_name,
            role=role,
        ):
            metadata = unit.state_metadata_dict.get(attribute_name)
            if metadata is not None and metadata.type == expected_state_type:
                return True
        return False

    def _flow_attribute_candidates(
        self,
        *,
        unit_id: str,
        port_name: str,
        role: Literal["source", "target"],
    ) -> tuple[str, ...]:
        stripped_suffix = "_outlet" if role == "source" else "_inlet"
        stripped_port_name = port_name.removesuffix(stripped_suffix)
        ordered_ports = self._available_unit_ports(unit_id=unit_id, role=role)
        candidates = [f"{port_name}_flow"]
        if stripped_port_name and stripped_port_name != port_name:
            candidates.append(f"{stripped_port_name}_flow")
        if role == "source":
            candidates.append("outlet_flow")
            if len(ordered_ports) > 1:
                candidates.append("outlet_flows")
        else:
            candidates.append("inlet_flow")
            if len(ordered_ports) > 1:
                candidates.append("inlet_flows")
        return tuple(dict.fromkeys(candidates))

    def _infer_unit_pressure_relations(self, *, unit_id: str) -> tuple[_UnitPressureRelation, ...]:
        unit = self._units[unit_id]
        inlet_ports = self._available_unit_ports(unit_id=unit_id, role="target")
        outlet_ports = self._available_unit_ports(unit_id=unit_id, role="source")
        if not inlet_ports or not outlet_ports:
            return ()

        pressure_drop_value = self._infer_unit_pressure_drop_value(unit=unit)

        pairwise_relations = self._infer_pairwise_unit_pressure_relations(
            unit_id=unit_id,
            inlet_ports=inlet_ports,
            outlet_ports=outlet_ports,
            pressure_drop_value=pressure_drop_value,
        )
        if pairwise_relations:
            return pairwise_relations

        if len(inlet_ports) != 1:
            return ()

        inlet_port_name = inlet_ports[0]
        if not self._port_exposes_pressure_metadata(
            unit_id=unit_id,
            port_name=inlet_port_name,
            role="target",
        ):
            return ()

        relations: list[_UnitPressureRelation] = []
        for outlet_port_name in outlet_ports:
            if not self._outlet_port_supports_pipe_pressure_relation(
                unit_id=unit_id,
                outlet_port_name=outlet_port_name,
            ):
                return ()
            relations.append(
                _UnitPressureRelation(
                    inlet_port_name=inlet_port_name,
                    outlet_port_name=outlet_port_name,
                    pressure_drop_pa=pressure_drop_value,
                )
            )
        return tuple(relations)

    def _infer_pairwise_unit_pressure_relations(
        self,
        *,
        unit_id: str,
        inlet_ports: tuple[str, ...],
        outlet_ports: tuple[str, ...],
        pressure_drop_value: float,
    ) -> tuple[_UnitPressureRelation, ...]:
        if len(inlet_ports) != len(outlet_ports) or len(inlet_ports) <= 1:
            return ()

        inlet_by_prefix: dict[str, str] = {}
        for port_name in inlet_ports:
            prefix = self._paired_port_prefix(port_name=port_name, suffix="_inlet")
            if prefix is None or prefix in inlet_by_prefix:
                return ()
            inlet_by_prefix[prefix] = port_name

        outlet_by_prefix: dict[str, str] = {}
        for port_name in outlet_ports:
            prefix = self._paired_port_prefix(port_name=port_name, suffix="_outlet")
            if prefix is None or prefix in outlet_by_prefix:
                return ()
            outlet_by_prefix[prefix] = port_name

        if set(inlet_by_prefix) != set(outlet_by_prefix):
            return ()

        relations: list[_UnitPressureRelation] = []
        for prefix in sorted(inlet_by_prefix):
            inlet_port_name = inlet_by_prefix[prefix]
            outlet_port_name = outlet_by_prefix[prefix]
            if not self._port_exposes_pressure_metadata(
                unit_id=unit_id,
                port_name=inlet_port_name,
                role="target",
            ) or not self._outlet_port_supports_pipe_pressure_relation(
                unit_id=unit_id,
                outlet_port_name=outlet_port_name,
            ):
                return ()
            relations.append(
                _UnitPressureRelation(
                    inlet_port_name=inlet_port_name,
                    outlet_port_name=outlet_port_name,
                    pressure_drop_pa=pressure_drop_value,
                )
            )
        return tuple(relations)

    def _infer_unit_pressure_drop_value(self, *, unit: ProcessModel) -> float:
        pressure_drop_value = 0.0
        metadata = unit.state_metadata_dict.get("pressure_drop")
        if metadata is not None and metadata.type == StateType.CONSTANT:
            pressure_drop = getattr(unit, "pressure_drop", None)
            if isinstance(pressure_drop, (int, float)):
                candidate_value = float(pressure_drop)
                if isfinite(candidate_value) and candidate_value >= 0.0:
                    pressure_drop_value = candidate_value
        return pressure_drop_value

    def _port_exposes_pressure_metadata(
        self,
        *,
        unit_id: str,
        port_name: str,
        role: Literal["source", "target"],
    ) -> bool:
        unit = self._units[unit_id]
        expected_state_type = StateType.ALGEBRAIC if role == "source" else StateType.BOUNDARY
        for attribute_name in self._pressure_attribute_candidates(port_name=port_name, role=role):
            metadata = unit.state_metadata_dict.get(attribute_name)
            if metadata is not None and metadata.type == expected_state_type:
                return True
            if (
                role == "source"
                and attribute_name == "outlet_pressure"
                and isinstance(getattr(type(unit), attribute_name, None), property)
            ):
                value = self._pressure_attribute_value(unit=unit, attribute_name=attribute_name)
                if value is not None:
                    return True
        return False

    def _outlet_port_supports_pipe_pressure_relation(
        self, *, unit_id: str, outlet_port_name: str
    ) -> bool:
        if not self._port_exposes_pressure_metadata(
            unit_id=unit_id,
            port_name=outlet_port_name,
            role="source",
        ):
            return False
        outlet_element = self._resolve_hydraulic_element(
            source_node_id=unit_id,
            source_port_name=outlet_port_name,
            target_node_id=unit_id,
        )
        return isinstance(outlet_element, PipeHydraulicElement)

    def _validate_unit_pressure_relation_anchor_consistency(
        self,
        *,
        unit_id: str,
        relation: _UnitPressureRelation,
        inlet_node_spec: _HydraulicNodeCompileSpec,
        outlet_node_spec: _HydraulicNodeCompileSpec,
    ) -> None:
        inlet_anchor = inlet_node_spec.anchor_pressure_pa
        outlet_anchor = outlet_node_spec.anchor_pressure_pa
        if inlet_anchor is None or outlet_anchor is None:
            return
        observed_pressure_drop = inlet_anchor - outlet_anchor
        if isclose(
            observed_pressure_drop,
            relation.pressure_drop_pa,
            rel_tol=1.0e-9,
            abs_tol=1.0e-9,
        ):
            return
        raise ValueError(
            "conflicting unit hydraulic boundary conditions for '{}': explicit anchors {}={} Pa and {}={} Pa conflict with inferred pressure_drop={} Pa; remove one fixed-pressure declaration or add an explicit junction/unit model with the intended hydraulic semantics".format(
                unit_id,
                inlet_node_spec.topology_label,
                inlet_anchor,
                outlet_node_spec.topology_label,
                outlet_anchor,
                relation.pressure_drop_pa,
            )
        )

    def _process_port_supports_direct_multi_edge_balancing(
        self,
        *,
        node_id: str,
        port_name: str,
        incidence_count: int,
    ) -> bool:
        del node_id, port_name
        return incidence_count <= 1

    def _source_pressure(self, *, node_id: str, port_name: str) -> float:
        feed_stream = self._feeds.get(node_id)
        if feed_stream is not None:
            return float(feed_stream.pressure)

        source_unit = self._units.get(node_id)
        if source_unit is not None:
            getter = getattr(source_unit, "get_outlet_stream", None)
            if callable(getter):
                stream = getter(port_name)
                if (
                    isinstance(stream, StreamData)
                    and isfinite(stream.pressure)
                    and stream.pressure > 0.0
                ):
                    return float(stream.pressure)
        return 101325.0

    def _target_pressure(self, *, node_id: str, port_name: str) -> float:
        target_unit = self._units.get(node_id)
        if target_unit is None:
            return 101325.0

        candidate_fields = (f"{port_name}_pressure", "inlet_pressure")
        for field_name in candidate_fields:
            value = getattr(target_unit, field_name, None)
            if isinstance(value, (int, float)) and isfinite(float(value)) and float(value) > 0.0:
                return float(value)
        return 101325.0

    def _configure_connection_line(
        self,
        *,
        network: ConnectionNetwork,
        connection: _ConnectionSpec,
    ) -> None:
        network.configure_line_geometry(
            line_id=connection.line_id,
            radius_m=connection.radius_m,
            length_m=connection.length_m,
            equation_name=connection.line_id,
            resistance_parameter_name=self._resistance_parameter_name_for_connection(connection),
        )

        if connection.pump is None and connection.valve is None and connection.heat is None:
            self._configure_edge_hydraulic_actuator_state(
                network=network,
                line_id=connection.line_id,
                source_endpoint=connection.source,
            )

        if connection.pump is not None:
            network.attach_line_pump(
                line_id=connection.line_id,
                pump_id=connection.pump.id,
                initial_pump_speed=connection.pump.initial_pump_speed,
                equation_name=connection.line_id,
                pump_parameter_name="pump_speed",
            )

        if connection.valve is not None:
            network.attach_line_valve(
                line_id=connection.line_id,
                valve_id=connection.valve.id,
                minimum_open_fraction=connection.valve.minimum_open_fraction,
                maximum_open_fraction=connection.valve.maximum_open_fraction,
                initial_open_fraction=connection.valve.initial_open_fraction,
                equation_name=connection.line_id,
                resistance_parameter_name="valve_resistance",
            )

        if connection.heat is not None:
            network.attach_line_heat_actuator(
                line_id=connection.line_id,
                heat_actuator_id=connection.heat.id,
                initial_heat_rate=connection.heat.initial_heat_rate,
            )

    def _resistance_parameter_name_for_connection(self, connection: _ConnectionSpec) -> str:
        source_node_id, source_port_name = self._split_explicit_endpoint(connection.source)
        base_element = self._resolve_hydraulic_element_for_connection(
            line_id=connection.line_id,
            source_node_id=source_node_id,
            source_port_name=source_port_name,
        )
        if connection.pump is not None:
            return "pump_speed"
        if connection.valve is not None:
            return "valve_resistance"
        parameter_names = base_element.parameter_spec.names
        if parameter_names:
            return parameter_names[0]
        return "pipe_resistance"

    def _reserve_line_id(self, line_id: str | None) -> str:
        if line_id is not None:
            normalized_line_id = self._normalize_identifier(value=line_id, field_name="line_id")
            self._assert_unique_identifier(
                value=normalized_line_id,
                existing_ids=self._line_ids,
                kind="line",
            )
            self._line_ids.add(normalized_line_id)
            return normalized_line_id

        while True:
            candidate = f"line_{self._next_generated_line_index:04d}"
            self._next_generated_line_index += 1
            if candidate in self._line_ids:
                continue
            self._line_ids.add(candidate)
            return candidate

    def _normalize_pump_install(
        self, *, pump: PumpInstall | None, line_id: str
    ) -> PumpInstall | None:
        if pump is None:
            return None
        initial_speed = self._require_finite_scalar(
            value=pump.initial_pump_speed,
            field_name="pump.initial_pump_speed",
        )
        pump_id = self._reserve_generated_or_explicit_identifier(
            explicit_id=pump.id,
            generated_id=f"{line_id}__pump",
            existing_ids=self._pump_ids,
            kind="pump",
        )
        return PumpInstall(id=pump_id, initial_pump_speed=initial_speed)

    def _normalize_valve_install(
        self, *, valve: ValveInstall | None, line_id: str
    ) -> ValveInstall | None:
        if valve is None:
            return None
        minimum = self._require_finite_scalar(
            value=valve.minimum_open_fraction,
            field_name="valve.minimum_open_fraction",
        )
        maximum = self._require_finite_scalar(
            value=valve.maximum_open_fraction,
            field_name="valve.maximum_open_fraction",
        )
        initial = self._require_finite_scalar(
            value=valve.initial_open_fraction,
            field_name="valve.initial_open_fraction",
        )
        if minimum > maximum:
            raise ValueError(
                "valve install is invalid: minimum_open_fraction must be <= maximum_open_fraction"
            )
        if initial < minimum or initial > maximum:
            raise ValueError(
                "valve install is invalid: initial_open_fraction must be within min/max bounds"
            )
        valve_id = self._reserve_generated_or_explicit_identifier(
            explicit_id=valve.id,
            generated_id=f"{line_id}__valve",
            existing_ids=self._valve_ids,
            kind="valve",
        )
        return ValveInstall(
            id=valve_id,
            minimum_open_fraction=minimum,
            maximum_open_fraction=maximum,
            initial_open_fraction=initial,
        )

    def _normalize_heat_install(
        self, *, heat: HeatInstall | None, line_id: str
    ) -> HeatInstall | None:
        if heat is None:
            return None
        initial_rate = self._require_finite_scalar(
            value=heat.initial_heat_rate,
            field_name="heat.initial_heat_rate",
        )
        heat_id = self._reserve_generated_or_explicit_identifier(
            explicit_id=heat.id,
            generated_id=f"{line_id}__heat",
            existing_ids=self._heat_actuator_ids,
            kind="heat actuator",
        )
        return HeatInstall(id=heat_id, initial_heat_rate=initial_rate)

    def _validate_line_overlay_selection(
        self,
        *,
        line_id: str,
        pump: PumpInstall | None,
        valve: ValveInstall | None,
        heat: HeatInstall | None,
    ) -> None:
        del heat
        if pump is not None and valve is not None:
            raise ValueError(
                f"line '{line_id}' cannot install both pump and valve hydraulic overlays"
            )

    def _reserve_generated_or_explicit_identifier(
        self,
        *,
        explicit_id: str | None,
        generated_id: str,
        existing_ids: set[str],
        kind: str,
    ) -> str:
        resolved_id = generated_id
        if explicit_id is not None:
            resolved_id = self._normalize_identifier(value=explicit_id, field_name=f"{kind}_id")
        self._assert_unique_identifier(value=resolved_id, existing_ids=existing_ids, kind=kind)
        existing_ids.add(resolved_id)
        return resolved_id

    def _normalize_identifier(self, *, value: str, field_name: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError(f"{field_name} must be a non-empty string")
        return normalized

    def _assert_unique_identifier(self, *, value: str, existing_ids: set[str], kind: str) -> None:
        if value in existing_ids:
            raise ValueError(f"duplicate {kind} id '{value}' is not allowed")

    def _require_finite_scalar(self, *, value: float, field_name: str) -> float:
        scalar = float(value)
        if not isfinite(scalar):
            raise ValueError(f"{field_name} must be finite")
        return scalar

    def _require_positive_finite_scalar(self, *, value: float, field_name: str) -> float:
        scalar = self._require_finite_scalar(value=value, field_name=field_name)
        if scalar <= 0.0:
            raise ValueError(f"{field_name} must be positive")
        return scalar

    def _normalize_endpoint(
        self, *, endpoint: str, role: Literal["source", "target"]
    ) -> _EndpointReference:
        if not endpoint.strip():
            raise ValueError(f"{role} endpoint must be a non-empty string")
        normalized = endpoint.strip()

        if "." in normalized:
            node_id, port_name = self._split_explicit_endpoint(normalized)
            node_kind = self._node_kind(node_id=node_id)
            if node_kind is None:
                raise ValueError(f"unknown node '{node_id}' in endpoint '{normalized}'")
            compile_port_name = self._validate_explicit_node_port(
                node_id=node_id,
                port_name=port_name,
                role=role,
                original_endpoint=normalized,
                node_kind=node_kind,
            )
            return _EndpointReference(
                compile_endpoint=f"{node_id}.{compile_port_name}",
                display_endpoint=f"{node_id}.{port_name}",
                node_id=node_id,
                port_name=compile_port_name,
                node_kind=node_kind,
            )

        node_kind = self._node_kind(node_id=normalized)
        if node_kind is None:
            raise ValueError(f"unknown {role} endpoint '{normalized}'")

        ports = self._available_node_ports(node_id=normalized, role=role, node_kind=node_kind)
        if len(ports) != 1:
            available = ", ".join(ports)
            raise ValueError(
                f"ambiguous {role} endpoint '{normalized}': available {role} ports are {available}; use explicit '<node_id>.<port_name>' syntax"
            )
        port_name = ports[0]
        return _EndpointReference(
            compile_endpoint=f"{normalized}.{port_name}",
            display_endpoint=normalized,
            node_id=normalized,
            port_name=port_name,
            node_kind=node_kind,
        )

    def _validate_explicit_node_port(
        self,
        *,
        node_id: str,
        port_name: str,
        role: Literal["source", "target"],
        original_endpoint: str,
        node_kind: Literal["unit", "feed", "junction", "sink"],
    ) -> str:
        if node_kind == "feed":
            if port_name != "outlet":
                raise ValueError(
                    f"invalid {role} endpoint '{original_endpoint}': available {role} ports are outlet"
                )
            if role != "source":
                raise ValueError(f"feed '{node_id}' cannot be used as a connection target")
            return "outlet"
        if node_kind == "sink":
            sink_port_name = self._sinks[node_id].port_name
            if port_name != sink_port_name:
                raise ValueError(
                    f"invalid {role} endpoint '{original_endpoint}': available {role} ports are {sink_port_name}"
                )
            if role != "target":
                raise ValueError(f"sink '{node_id}' cannot be used as a connection source")
            return sink_port_name

        ports = self._available_node_ports(node_id=node_id, role=role, node_kind=node_kind)
        if port_name in ports:
            return port_name
        available = ", ".join(ports)
        raise ValueError(
            f"invalid {role} endpoint '{original_endpoint}': available {role} ports are {available}"
        )

    def _available_node_ports(
        self,
        *,
        node_id: str,
        role: Literal["source", "target"],
        node_kind: Literal["unit", "feed", "junction", "sink"],
    ) -> tuple[str, ...]:
        if node_kind == "unit":
            return self._available_unit_ports(unit_id=node_id, role=role)
        if node_kind == "feed":
            if role == "target":
                raise ValueError(f"feed '{node_id}' cannot be used as a connection target")
            return ("outlet",)
        if node_kind == "sink":
            if role == "source":
                raise ValueError(f"sink '{node_id}' cannot be used as a connection source")
            return (self._sinks[node_id].port_name,)
        return self._available_junction_ports(junction_id=node_id, role=role)

    def _available_junction_ports(
        self, *, junction_id: str, role: Literal["source", "target"]
    ) -> tuple[str, ...]:
        junction = self._junctions[junction_id]
        return junction.outlet_ports if role == "source" else junction.inlet_ports

    def _normalize_port_name(self, *, port_name: str, field_name: str) -> str:
        normalized = port_name.strip()
        if not normalized:
            raise ValueError(f"{field_name} must be a non-empty string")
        return normalized

    def _node_kind(self, *, node_id: str) -> Literal["unit", "feed", "junction", "sink"] | None:
        if node_id in self._units:
            return "unit"
        if node_id in self._feeds:
            return "feed"
        if node_id in self._junctions:
            return "junction"
        if node_id in self._sinks:
            return "sink"
        return None

    def _available_unit_ports(
        self, *, unit_id: str, role: Literal["source", "target"]
    ) -> tuple[str, ...]:
        unit = self._units[unit_id]
        ports = getattr(unit, "ports", None)
        if not isinstance(ports, UnitProcessPorts):
            raise ValueError(f"unit '{unit_id}' does not expose a ports declaration")
        port_names = tuple(ports.outlets if role == "source" else ports.inlets)
        if not port_names:
            raise ValueError(f"unit '{unit_id}' does not declare any {role} ports")
        return port_names

    def _split_explicit_endpoint(self, endpoint: str) -> tuple[str, str]:
        node_id, _, port_name = endpoint.partition(".")
        normalized_node_id = node_id.strip()
        normalized_port_name = port_name.strip()
        if not normalized_node_id or not normalized_port_name or "." in normalized_port_name:
            raise ValueError(
                f"invalid endpoint '{endpoint}': expected '<node_id>.<port_name>' format"
            )
        return normalized_node_id, normalized_port_name

    def _normalize_node_id(self, *, unit_id: str, field_name: str) -> str:
        if not unit_id.strip():
            raise ValueError(f"{field_name} must be a non-empty string")
        return unit_id.strip()

    def _assert_available_node_id(self, *, node_id: str) -> None:
        if self._node_kind(node_id=node_id) is not None:
            raise ValueError(f"node id '{node_id}' is already registered")

    def _mark_dirty(self) -> None:
        self._compiled_plant = None
        self._dirty = True


__all__ = [
    "Flowsheet",
    "FlowsheetResults",
    "HeatInstall",
    "JunctionDefinition",
    "LineReference",
    "PumpInstall",
    "SinkDefinition",
    "StreamHistory",
    "UnitResult",
    "ValveInstall",
]

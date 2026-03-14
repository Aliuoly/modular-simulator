from __future__ import annotations

# pyright: reportMissingTypeStubs=false, reportArgumentType=false, reportReturnType=false

from collections.abc import Mapping
from dataclasses import dataclass, field
from math import isfinite
from types import MappingProxyType
from typing import TYPE_CHECKING, Literal, cast
import warnings
import numpy as np
from numpy.typing import NDArray

from modular_simulation.connection.connected_plant_orchestrator import (
    ConnectedPlantOrchestrator,
    ConnectedPlantStepResult,
)
from modular_simulation.connection.hydraulic_compile import HydraulicCompileLifecycle
from modular_simulation.connection.hydraulic_element import (
    PipeHydraulicElement,
    PumpHydraulicElement,
    ValveHydraulicElement,
)
from modular_simulation.connection.hydraulic_solver import (
    ElementEquation,
    HydraulicSystemDefinition,
)
from modular_simulation.connection.network import ConnectionNetwork
from modular_simulation.connection.process_stream_io import ProcessStreamIO
from modular_simulation.connection.runtime import ConnectionRuntimeOrchestrator
from modular_simulation.connection.subsystem_descriptor import Subsystem
from modular_simulation.connection.unit_process_wiring import create_subsystem_for_unit
from modular_simulation.thermodynamics.hydraulic_adapters import (
    DEFAULT_HYDRAULIC_DELTA,
    default_pipe_hydraulic_parameters,
    default_pipe_resistance_for_unit,
    default_pump_hydraulic_parameters,
)
from modular_simulation.thermodynamics.algebraic_process_model import UnitProcessPorts
from modular_simulation.thermodynamics.stream import StreamData

if TYPE_CHECKING:
    from modular_simulation.measurables.process_model import ProcessModel
    from modular_simulation.framework.system import System
    from modular_simulation.connection.topology import TopologyGraph
    from modular_simulation.thermodynamics.runtime_context import SimulationRuntimeContext


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


@dataclass(frozen=True)
class _ConnectionSpec:
    source: str
    target: str


@dataclass(frozen=True)
class _ResolvedConnection:
    source_node_id: str
    source_port_name: str
    source_is_feed: bool
    target_node_id: str
    target_port_name: str


class Flowsheet:
    def __init__(self, context: SimulationRuntimeContext, dt: float = 0.1):
        if not isfinite(dt) or dt <= 0.0:
            raise ValueError("dt must be finite and positive")

        self._context: SimulationRuntimeContext = context
        self._dt: float = float(dt)
        self._units: dict[str, ProcessModel] = {}
        self._feeds: dict[str, StreamData] = {}
        self._connections: list[_ConnectionSpec] = []
        self._subsystems: dict[str, Subsystem] = {}
        self._compiled_plant: ConnectedPlantOrchestrator | None = None
        self._dirty: bool = True

    def add_unit(self, unit_id: str, unit: ProcessModel) -> None:
        normalized_unit_id = self._normalize_node_id(unit_id=unit_id, field_name="unit_id")
        self._assert_available_node_id(node_id=normalized_unit_id)
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

    def connect(self, source: str, target: str) -> None:
        normalized_source = self._normalize_endpoint(endpoint=source, role="source")
        normalized_target = self._normalize_endpoint(endpoint=target, role="target")
        self._connections.append(
            _ConnectionSpec(source=normalized_source, target=normalized_target)
        )
        self._mark_dirty()

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
        for connection in self._connections:
            line_id = network.connect(connection.source, connection.target)
            self._configure_edge_hydraulic_actuator_state(
                network=network,
                line_id=line_id,
                source_endpoint=connection.source,
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
        self._validate_pressure_boundary_presence()
        resolved_connections = self._resolved_connections_for_validation()
        self._validate_mandatory_inlets(resolved_connections=resolved_connections)
        self._validate_species_compatibility(resolved_connections=resolved_connections)
        self._warn_dangling_outlets(resolved_connections=resolved_connections)
        self._warn_on_topology_issues(resolved_connections=resolved_connections)

    def _validate_pressure_boundary_presence(self) -> None:
        if self._feeds:
            return
        raise ValueError(
            "flowsheet compile validation failed: at least one feed boundary is required "
            + "to anchor pressure and material flow"
        )

    def _resolved_connections_for_validation(self) -> tuple[_ResolvedConnection, ...]:
        resolved: list[_ResolvedConnection] = []
        for connection in self._connections:
            source_node_id: str
            source_port_name: str
            source_is_feed = "." not in connection.source
            if source_is_feed:
                source_node_id = connection.source
                source_port_name = "outlet"
            else:
                source_node_id, source_port_name = self._split_explicit_endpoint(connection.source)

            target_node_id, target_port_name = self._split_explicit_endpoint(connection.target)
            resolved.append(
                _ResolvedConnection(
                    source_node_id=source_node_id,
                    source_port_name=source_port_name,
                    source_is_feed=source_is_feed,
                    target_node_id=target_node_id,
                    target_port_name=target_port_name,
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
            if not connection.source_is_feed
        }
        dangling_outlets: list[str] = []
        for unit_id in sorted(self._units):
            for outlet_port in self._available_unit_ports(unit_id=unit_id, role="source"):
                if (unit_id, outlet_port) in connected_outlets:
                    continue
                dangling_outlets.append(f"{unit_id}.{outlet_port}")

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
        node_ids = set(self._units) | set(self._feeds)
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

        cycle = self._find_directed_cycle(directed_neighbors=directed_neighbors)
        if cycle is None:
            return
        cycle_path = " -> ".join(cycle)
        warnings.warn(
            "flowsheet compile validation warning: recycle/cycle detected in topology "
            + f"({cycle_path}); convergence handling is not enabled in compile-time validation",
            stacklevel=2,
        )

    def _find_directed_cycle(
        self, *, directed_neighbors: Mapping[str, set[str]]
    ) -> tuple[str, ...] | None:
        visiting: set[str] = set()
        visited: set[str] = set()
        stack: list[str] = []

        def dfs(node_id: str) -> tuple[str, ...] | None:
            visiting.add(node_id)
            stack.append(node_id)
            for neighbor in sorted(directed_neighbors[node_id]):
                if neighbor in visited:
                    continue
                if neighbor in visiting:
                    cycle_start = stack.index(neighbor)
                    return tuple((*stack[cycle_start:], neighbor))
                cycle = dfs(neighbor)
                if cycle is not None:
                    return cycle
            _ = stack.pop()
            visiting.remove(node_id)
            visited.add(node_id)
            return None

        for node_id in sorted(directed_neighbors):
            if node_id in visited:
                continue
            cycle = dfs(node_id)
            if cycle is not None:
                return cycle
        return None

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
            f"{connection.source}->{connection.target}": {
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
                stream_key = f"{connection.source}->{connection.target}"
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
        if "." not in connection.source:
            return self._feeds[connection.source]

        source_node_id, source_port_name = self._split_explicit_endpoint(connection.source)
        source_unit = cast("ProcessStreamIO", cast("object", self._units[source_node_id]))
        return source_unit.get_outlet_stream(source_port_name)

    def _build_unit_results(
        self,
        *,
        state_trace_values: Mapping[str, Mapping[str, list[object]]],
    ) -> dict[str, UnitResult]:
        unit_results: dict[str, UnitResult] = {}
        for unit_id, unit in self._units.items():
            outlet_streams = {
                port_name: cast("ProcessStreamIO", cast("object", unit)).get_outlet_stream(
                    port_name
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
        for edge in sorted(topology.edges, key=lambda item: item.edge_id):
            element = self._resolve_hydraulic_element(
                source_node_id=edge.source.node_id,
                source_port_name=edge.source.port_name,
                target_node_id=edge.target.node_id,
            )
            parameters = self._resolve_element_parameters(
                element=element,
                source_node_id=edge.source.node_id,
                source_port_name=edge.source.port_name,
                target_node_id=edge.target.node_id,
            )
            equations.append(
                ElementEquation(
                    name=edge.edge_id,
                    element=element,
                    inputs=MappingProxyType(
                        {
                            "upstream_pressure": self._source_pressure(
                                node_id=edge.source.node_id,
                                port_name=edge.source.port_name,
                            ),
                            "downstream_pressure": self._target_pressure(
                                node_id=edge.target.node_id,
                                port_name=edge.target.port_name,
                            ),
                        }
                    ),
                    parameters=parameters,
                    unknown_name_map=MappingProxyType({"flow_rate": edge.edge_id}),
                    residual_name_map=MappingProxyType(
                        {"head_balance": f"{edge.edge_id}_head_balance"}
                    ),
                )
            )
        return HydraulicSystemDefinition(equations=tuple(equations))

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
        if isinstance(element, PumpHydraulicElement):
            pump_speed = self._resolve_pump_hydraulic_seed_value(
                source_node_id=source_node_id,
                source_port_name=source_port_name,
            )
            network.configure_line_geometry(
                line_id=line_id,
                radius_m=1.0,
                length_m=1.0,
                equation_name=line_id,
                resistance_parameter_name="pump_speed",
            )
            network.attach_line_pump(
                line_id=line_id,
                pump_id=f"{line_id}__pump",
                initial_pump_speed=pump_speed,
                equation_name=line_id,
                pump_parameter_name="pump_speed",
            )
            return

        if isinstance(element, ValveHydraulicElement):
            valve_parameters = self._resolve_valve_hydraulic_seed_values(
                source_node_id=source_node_id,
                source_port_name=source_port_name,
            )
            resistance_when_open = 1.0 / (valve_parameters["cv"] * valve_parameters["cv"])
            network.configure_line_geometry(
                line_id=line_id,
                radius_m=1.0,
                length_m=1.0,
                equation_name=line_id,
                resistance_parameter_name="valve_resistance",
            )
            network.configure_line_resistance(
                line_id=line_id,
                mode="manual_override",
                manual_value=resistance_when_open,
            )
            network.attach_line_valve(
                line_id=line_id,
                valve_id=f"{line_id}__valve",
                minimum_open_fraction=valve_parameters["minimum_open_fraction"],
                maximum_open_fraction=valve_parameters["maximum_open_fraction"],
                initial_open_fraction=valve_parameters["open_fraction"],
                equation_name=line_id,
                resistance_parameter_name="valve_resistance",
            )

    def _resolve_pump_hydraulic_seed_value(
        self, *, source_node_id: str, source_port_name: str
    ) -> float:
        parameter_getter = self._resolve_hydraulic_parameter_getter(source_node_id=source_node_id)
        parameters = parameter_getter(source_port_name)
        if isinstance(parameters, Mapping) and "pump_speed" in parameters:
            return float(parameters["pump_speed"])
        raise ValueError(
            f"unit '{source_node_id}' returned invalid pump hydraulic parameters for port '{source_port_name}'"
        )

    def _resolve_valve_hydraulic_seed_values(
        self, *, source_node_id: str, source_port_name: str
    ) -> dict[str, float]:
        parameter_getter = self._try_resolve_hydraulic_parameter_getter(
            source_node_id=source_node_id
        )
        if parameter_getter is None:
            return {
                "cv": 1.0,
                "open_fraction": 1.0,
                "minimum_open_fraction": 0.0,
                "maximum_open_fraction": 1.0,
            }

        parameters = parameter_getter(source_port_name)
        if not isinstance(parameters, Mapping):
            raise ValueError(
                f"unit '{source_node_id}' returned invalid valve hydraulic parameters for port '{source_port_name}'"
            )
        cv_raw = parameters.get("cv", parameters.get("Cv", 1.0))
        open_fraction_raw = parameters.get("open_fraction", 1.0)
        minimum_open_fraction_raw = parameters.get("minimum_open_fraction", 0.0)
        maximum_open_fraction_raw = parameters.get("maximum_open_fraction", 1.0)
        return {
            "cv": float(cv_raw),
            "open_fraction": float(open_fraction_raw),
            "minimum_open_fraction": float(minimum_open_fraction_raw),
            "maximum_open_fraction": float(maximum_open_fraction_raw),
        }

    def _resolve_hydraulic_parameter_getter(self, *, source_node_id: str):
        parameter_getter = self._try_resolve_hydraulic_parameter_getter(
            source_node_id=source_node_id
        )
        if parameter_getter is None:
            raise ValueError(
                f"unit '{source_node_id}' must implement hydraulic_parameters_for_port(port_name) "
                + "for pump hydraulic elements"
            )
        return parameter_getter

    def _try_resolve_hydraulic_parameter_getter(self, *, source_node_id: str):
        source_unit = self._units.get(source_node_id)
        if source_unit is None:
            return None
        parameter_getter = getattr(source_unit, "hydraulic_parameters_for_port", None)
        if not callable(parameter_getter):
            return None
        return parameter_getter

    def _resolve_hydraulic_element(
        self, *, source_node_id: str, source_port_name: str, target_node_id: str
    ) -> object:
        source_unit = self._units.get(source_node_id)
        if source_unit is None:
            del target_node_id
            return PipeHydraulicElement()

        to_hydraulic_element = getattr(source_unit, "to_hydraulic_element", None)
        if not callable(to_hydraulic_element):
            raise ValueError(
                f"unit '{source_node_id}' does not implement to_hydraulic_element(port_name)"
            )
        return to_hydraulic_element(source_port_name)

    def _resolve_element_parameters(
        self,
        *,
        element: object,
        source_node_id: str,
        source_port_name: str,
        target_node_id: str,
    ) -> Mapping[str, float]:
        del source_port_name
        if isinstance(element, PumpHydraulicElement):
            return MappingProxyType(default_pump_hydraulic_parameters(pump_speed=0.0))

        if isinstance(element, ValveHydraulicElement):
            return MappingProxyType(
                {
                    "valve_resistance": 1.0,
                    "delta": DEFAULT_HYDRAULIC_DELTA,
                }
            )

        if isinstance(element, PipeHydraulicElement):
            source_unit = self._units.get(source_node_id)
            target_unit = self._units.get(target_node_id)
            fallback_unit = source_unit if source_unit is not None else target_unit
            if fallback_unit is None:
                resistance = 5.0e3
            else:
                resistance = default_pipe_resistance_for_unit(
                    unit_name=type(fallback_unit).__name__
                )
            return MappingProxyType(default_pipe_hydraulic_parameters(resistance=resistance))

        parameter_spec = getattr(element, "parameter_spec", None)
        raw_parameter_names = getattr(parameter_spec, "names", ())
        parameter_names = tuple(
            str(name) for name in cast("tuple[object, ...]", raw_parameter_names)
        )
        return MappingProxyType({name: 1.0 for name in parameter_names})

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

    def _normalize_endpoint(self, *, endpoint: str, role: Literal["source", "target"]) -> str:
        if not endpoint.strip():
            raise ValueError(f"{role} endpoint must be a non-empty string")
        normalized = endpoint.strip()

        if "." in normalized:
            node_id, port_name = self._split_explicit_endpoint(normalized)
            if node_id in self._feeds:
                raise ValueError(
                    f"{role} endpoint '{normalized}' is invalid: feed boundaries do not take explicit ports"
                )
            if node_id not in self._units:
                raise ValueError(f"unknown unit '{node_id}' in endpoint '{normalized}'")
            self._validate_explicit_unit_port(
                unit_id=node_id,
                port_name=port_name,
                role=role,
                original_endpoint=normalized,
            )
            return f"{node_id}.{port_name}"

        if role == "source" and normalized in self._feeds:
            return normalized
        if role == "target" and normalized in self._feeds:
            raise ValueError(f"feed '{normalized}' cannot be used as a connection target")
        if normalized not in self._units:
            raise ValueError(f"unknown {role} endpoint '{normalized}'")

        ports = self._available_unit_ports(unit_id=normalized, role=role)
        if len(ports) == 1:
            return f"{normalized}.{ports[0]}"

        available = ", ".join(ports)
        raise ValueError(
            f"ambiguous {role} endpoint '{normalized}': available {role} ports are {available}"
        )

    def _validate_explicit_unit_port(
        self,
        *,
        unit_id: str,
        port_name: str,
        role: Literal["source", "target"],
        original_endpoint: str,
    ) -> None:
        ports = self._available_unit_ports(unit_id=unit_id, role=role)
        if port_name in ports:
            return
        available = ", ".join(ports)
        raise ValueError(
            f"invalid {role} endpoint '{original_endpoint}': available {role} ports are {available}"
        )

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
                f"invalid endpoint '{endpoint}': expected '<unit_id>.<port_name>' format"
            )
        return normalized_node_id, normalized_port_name

    def _normalize_node_id(self, *, unit_id: str, field_name: str) -> str:
        if not unit_id.strip():
            raise ValueError(f"{field_name} must be a non-empty string")
        return unit_id.strip()

    def _assert_available_node_id(self, *, node_id: str) -> None:
        if node_id in self._units or node_id in self._feeds:
            raise ValueError(f"node id '{node_id}' is already registered")

    def _mark_dirty(self) -> None:
        self._compiled_plant = None
        self._dirty = True


__all__ = ["Flowsheet", "FlowsheetResults", "UnitResult", "StreamHistory"]

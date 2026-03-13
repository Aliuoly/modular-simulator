from __future__ import annotations

# pyright: reportMissingTypeStubs=false

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import isfinite
from types import MappingProxyType
from typing import Literal, Protocol, cast

from modular_simulation.connection.hydraulic_compile import (
    CompiledHydraulicGraph,
    CompiledValveHydraulicState,
    HydraulicCompileLifecycle,
    compile_valve_hydraulic_state,
    resolve_line_resistance,
)
from modular_simulation.connection.asymmetric_adapter import (
    AsymmetricPortAdapter,
    ConvergingPortAdapter,
    build_process_binding,
)
from modular_simulation.connection.domain_contracts import (
    ResistanceConfig,
    ValveConfig,
    validate_command_envelope,
)
from modular_simulation.connection.error_catalog import (
    VALIDATION_FAILURE_CODE,
    diagnostic_value_error,
)
from modular_simulation.connection.hydraulic_solver import (
    ElementEquation,
    HydraulicSystemDefinition,
)
from modular_simulation.connection.process_binding import ProcessBinding
from modular_simulation.connection.topology import (
    BoundaryNode,
    ConnectionEdge,
    PortReference,
    ProcessNode,
    TopologyGraph,
)


@dataclass(frozen=True)
class CompiledConnectionNetwork:
    graph_revision: str
    topology: TopologyGraph
    process_bindings: Mapping[str, ProcessBinding | AsymmetricPortAdapter | ConvergingPortAdapter]
    hydraulic: CompiledHydraulicGraph | None


@dataclass(frozen=True)
class NetworkProcessSpec:
    process_id: str
    inlet_ports: tuple[str, ...]
    outlet_ports: tuple[str, ...]


@dataclass(frozen=True)
class NetworkBoundarySpec:
    boundary_id: str
    direction: Literal["source", "sink"]
    port_name: str


@dataclass(frozen=True)
class NetworkLineHydraulicConfig:
    line_id: str
    equation_name: str
    resistance_parameter_name: str
    resistance_mode: Literal["derived", "manual_override"]
    radius_m: float | None
    length_m: float | None
    manual_value: float | None
    valve_id: str | None
    minimum_open_fraction: float | None
    maximum_open_fraction: float | None
    initial_open_fraction: float | None


@dataclass(frozen=True)
class _BoundarySpec:
    boundary_id: str
    direction: Literal["source", "sink"]
    port_name: str


@dataclass(frozen=True)
class _ProcessSpec:
    process_id: str
    inlet_ports: tuple[str, ...]
    outlet_ports: tuple[str, ...]


@dataclass(frozen=True)
class _LineHydraulicConfig:
    line_id: str
    equation_name: str
    resistance_parameter_name: str
    resistance: ResistanceConfig
    valve: ValveConfig | None


@dataclass(frozen=True)
class _QueuedReconfigurationTransaction:
    request_id: str
    idempotency_key: str | None
    expected_revision: str | None
    metadata: dict[str, object]
    mutations: tuple[dict[str, object], ...]


QueuedReconfigurationTransaction = _QueuedReconfigurationTransaction


@dataclass(frozen=True)
class _NetworkReconfigurationState:
    process_specs: dict[str, _ProcessSpec]
    boundary_specs: dict[str, _BoundarySpec]
    edges: list[ConnectionEdge]
    line_hydraulic_configs: dict[str, _LineHydraulicConfig]
    edge_lookup: dict[tuple[str, str, str, str], str]
    next_edge_index: int
    next_reconfiguration_index: int
    next_revision_index: int
    queued_reconfigurations: list[QueuedReconfigurationTransaction]
    pending_valve_open_fractions: dict[str, float]
    compiled: CompiledConnectionNetwork | None


class _HydraulicSystemBuilder(Protocol):
    def __call__(self, topology: TopologyGraph) -> HydraulicSystemDefinition: ...


class _RuntimeOrchestrator(Protocol):
    def step(self, *, network: "ConnectionNetwork", macro_step_time_s: float) -> object: ...

    def save_runtime_snapshot(self, *, network: "ConnectionNetwork") -> Mapping[str, object]: ...

    def resume_from_snapshot(
        self, *, network: "ConnectionNetwork", snapshot: Mapping[str, object]
    ) -> None: ...


class ConnectionNetwork:
    @classmethod
    def from_single_process(
        cls,
        *,
        process_id: str,
        inlet_ports: Sequence[str],
        outlet_ports: Sequence[str],
        compile_lifecycle: HydraulicCompileLifecycle | None = None,
        hydraulic_system_builder: _HydraulicSystemBuilder | None = None,
        runtime_orchestrator: _RuntimeOrchestrator | None = None,
        source_boundary_id: str = "feed_boundary",
        sink_boundary_id: str = "product_boundary",
        source_boundary_port_name: str = "outlet",
        sink_boundary_port_name: str = "inlet",
        source_process_port_name: str | None = None,
        sink_process_port_name: str | None = None,
        compile_network: bool = True,
    ) -> "ConnectionNetwork":
        network = cls(
            compile_lifecycle=compile_lifecycle,
            hydraulic_system_builder=hydraulic_system_builder,
            runtime_orchestrator=runtime_orchestrator,
        )
        network.add_process(
            process_id,
            inlet_ports=inlet_ports,
            outlet_ports=outlet_ports,
        )
        network.add_boundary_source(source_boundary_id, port_name=source_boundary_port_name)
        network.add_boundary_sink(sink_boundary_id, port_name=sink_boundary_port_name)

        process_spec = network._process_specs[process_id]
        if not process_spec.inlet_ports:
            raise ValueError("from_single_process requires at least one inlet port")
        if not process_spec.outlet_ports:
            raise ValueError("from_single_process requires at least one outlet port")

        source_port_name = (
            network._normalize_port_name(source_process_port_name)
            if source_process_port_name is not None
            else process_spec.inlet_ports[0]
        )
        sink_port_name = (
            network._normalize_port_name(sink_process_port_name)
            if sink_process_port_name is not None
            else process_spec.outlet_ports[0]
        )

        _ = network.connect(source_boundary_id, f"{process_id}.{source_port_name}")
        _ = network.connect(f"{process_id}.{sink_port_name}", sink_boundary_id)
        if compile_network:
            _ = network.compile()
        return network

    def __init__(
        self,
        *,
        compile_lifecycle: HydraulicCompileLifecycle | None = None,
        hydraulic_system_builder: _HydraulicSystemBuilder | None = None,
        runtime_orchestrator: _RuntimeOrchestrator | None = None,
    ):
        self._compile_lifecycle: HydraulicCompileLifecycle | None = compile_lifecycle
        self._hydraulic_system_builder: _HydraulicSystemBuilder | None = hydraulic_system_builder
        self._runtime_orchestrator: _RuntimeOrchestrator | None = runtime_orchestrator

        self._process_specs: dict[str, _ProcessSpec] = {}
        self._boundary_specs: dict[str, _BoundarySpec] = {}
        self._edges: list[ConnectionEdge] = []
        self._line_hydraulic_configs: dict[str, _LineHydraulicConfig] = {}
        self._edge_lookup: dict[tuple[str, str, str, str], str] = {}
        self._next_edge_index: int = 1
        self._next_reconfiguration_index: int = 1
        self._next_revision_index: int = 1
        self._queued_reconfigurations: list[QueuedReconfigurationTransaction] = []
        self._pending_valve_open_fractions: dict[str, float] = {}
        self._compiled: CompiledConnectionNetwork | None = None

    def add_process(
        self,
        process_id: str,
        *,
        inlet_ports: Sequence[str],
        outlet_ports: Sequence[str],
    ) -> None:
        self._validate_node_id(process_id)
        self._ensure_node_id_is_available(process_id)

        normalized_inlets = self._normalize_port_names(
            node_id=process_id,
            port_names=inlet_ports,
            role="inlet",
        )
        normalized_outlets = self._normalize_port_names(
            node_id=process_id,
            port_names=outlet_ports,
            role="outlet",
        )
        self._process_specs[process_id] = _ProcessSpec(
            process_id=process_id,
            inlet_ports=normalized_inlets,
            outlet_ports=normalized_outlets,
        )

    def add_boundary_source(self, boundary_id: str, *, port_name: str = "outlet") -> None:
        self._add_boundary(boundary_id=boundary_id, direction="source", port_name=port_name)

    def add_boundary_sink(self, boundary_id: str, *, port_name: str = "inlet") -> None:
        self._add_boundary(boundary_id=boundary_id, direction="sink", port_name=port_name)

    def connect(self, source: str, target: str, *, edge_id: str | None = None) -> str:
        source_ref = self._parse_endpoint(source)
        target_ref = self._parse_endpoint(target)
        self._validate_connection_directions(source_ref=source_ref, target_ref=target_ref)

        edge_key = (
            source_ref.node_id,
            source_ref.port_name,
            target_ref.node_id,
            target_ref.port_name,
        )
        existing_edge_id = self._edge_lookup.get(edge_key)
        if existing_edge_id is not None:
            edge_name = (
                f"{source_ref.node_id}.{source_ref.port_name}"
                f"->{target_ref.node_id}.{target_ref.port_name}"
            )
            raise ValueError(
                f"duplicate connection '{edge_name}' already exists as edge_id '{existing_edge_id}'"
            )

        selected_edge_id = edge_id or f"edge_{self._next_edge_index:04d}"
        self._validate_edge_id(selected_edge_id)
        if any(existing.edge_id == selected_edge_id for existing in self._edges):
            raise ValueError(f"duplicate edge id '{selected_edge_id}' is not allowed")

        self._edges.append(
            ConnectionEdge(
                edge_id=selected_edge_id,
                source=source_ref,
                target=target_ref,
            )
        )
        self._edge_lookup[edge_key] = selected_edge_id
        self._next_edge_index += 1
        return selected_edge_id

    def process_ports(self, *, process_id: str) -> tuple[str, ...] | None:
        spec = self._process_specs.get(process_id)
        if spec is None:
            return None
        return (*spec.inlet_ports, *spec.outlet_ports)

    def list_process_specs(self) -> tuple[NetworkProcessSpec, ...]:
        return tuple(
            NetworkProcessSpec(
                process_id=spec.process_id,
                inlet_ports=tuple(spec.inlet_ports),
                outlet_ports=tuple(spec.outlet_ports),
            )
            for spec in sorted(self._process_specs.values(), key=lambda item: item.process_id)
        )

    def list_boundary_specs(self) -> tuple[NetworkBoundarySpec, ...]:
        return tuple(
            NetworkBoundarySpec(
                boundary_id=spec.boundary_id,
                direction=spec.direction,
                port_name=spec.port_name,
            )
            for spec in sorted(self._boundary_specs.values(), key=lambda item: item.boundary_id)
        )

    def list_connection_edges(self) -> tuple[ConnectionEdge, ...]:
        return tuple(sorted(self._edges, key=lambda item: item.edge_id))

    def list_line_hydraulic_configs(self) -> tuple[NetworkLineHydraulicConfig, ...]:
        return tuple(
            NetworkLineHydraulicConfig(
                line_id=config.line_id,
                equation_name=config.equation_name,
                resistance_parameter_name=config.resistance_parameter_name,
                resistance_mode=config.resistance.mode,
                radius_m=config.resistance.radius_m,
                length_m=config.resistance.length_m,
                manual_value=config.resistance.manual_value,
                valve_id=None if config.valve is None else config.valve.valve_id,
                minimum_open_fraction=(
                    None if config.valve is None else config.valve.minimum_open_fraction
                ),
                maximum_open_fraction=(
                    None if config.valve is None else config.valve.maximum_open_fraction
                ),
                initial_open_fraction=(
                    None if config.valve is None else config.valve.initial_open_fraction
                ),
            )
            for config in sorted(
                self._line_hydraulic_configs.values(), key=lambda item: item.line_id
            )
        )

    def list_pending_valve_open_fractions(self) -> tuple[tuple[str, float], ...]:
        return tuple(
            (line_id, self._pending_valve_open_fractions[line_id])
            for line_id in sorted(self._pending_valve_open_fractions)
        )

    def list_incident_edge_ids(
        self, *, node_id: str, port_name: str | None = None
    ) -> tuple[str, ...]:
        if port_name is None:
            return tuple(
                sorted(
                    edge.edge_id
                    for edge in self._edges
                    if edge.source.node_id == node_id or edge.target.node_id == node_id
                )
            )

        return tuple(
            sorted(
                edge.edge_id
                for edge in self._edges
                if (edge.source.node_id, edge.source.port_name) == (node_id, port_name)
                or (edge.target.node_id, edge.target.port_name) == (node_id, port_name)
            )
        )

    def resolve_connection_edge_id(
        self,
        *,
        edge_id: str | None = None,
        source: str | None = None,
        target: str | None = None,
    ) -> str | None:
        if edge_id is not None:
            normalized_edge_id = edge_id.strip()
            if not normalized_edge_id:
                return None
            for edge in self._edges:
                if edge.edge_id == normalized_edge_id:
                    return normalized_edge_id
            return None

        if source is None or target is None:
            return None
        normalized_source = source.strip()
        normalized_target = target.strip()
        if not normalized_source or not normalized_target:
            return None

        try:
            source_ref = self._parse_endpoint(normalized_source)
            target_ref = self._parse_endpoint(normalized_target)
        except Exception:
            return None

        edge_key = (
            source_ref.node_id,
            source_ref.port_name,
            target_ref.node_id,
            target_ref.port_name,
        )
        return self._edge_lookup.get(edge_key)

    def compile(self) -> CompiledConnectionNetwork:
        topology = TopologyGraph(
            process_nodes=tuple(
                ProcessNode(
                    process_id=spec.process_id,
                    inlet_ports=spec.inlet_ports,
                    outlet_ports=spec.outlet_ports,
                )
                for spec in sorted(self._process_specs.values(), key=lambda item: item.process_id)
            ),
            boundary_nodes=tuple(
                BoundaryNode(
                    boundary_id=spec.boundary_id,
                    port_name=spec.port_name,
                    direction=spec.direction,
                )
                for spec in sorted(self._boundary_specs.values(), key=lambda item: item.boundary_id)
            ),
            junction_nodes=(),
            edges=tuple(self._edges),
        )

        bindings: dict[str, ProcessBinding | AsymmetricPortAdapter | ConvergingPortAdapter] = {
            spec.process_id: build_process_binding(
                process_id=spec.process_id,
                inlet_ports=spec.inlet_ports,
                outlet_ports=spec.outlet_ports,
            )
            for spec in sorted(self._process_specs.values(), key=lambda item: item.process_id)
        }

        graph_revision = f"graph_rev_{self._next_revision_index:04d}"
        self._next_revision_index += 1

        hydraulic: CompiledHydraulicGraph | None = None
        if self._compile_lifecycle is not None or self._hydraulic_system_builder is not None:
            if self._compile_lifecycle is None or self._hydraulic_system_builder is None:
                raise RuntimeError(
                    "hydraulic compile delegation requires both compile_lifecycle and hydraulic_system_builder"
                )
            system = self._hydraulic_system_builder(topology)
            system_for_compile, valve_state_by_line = self._apply_line_hydraulic_configurations(
                system=system
            )
            hydraulic = self._compile_lifecycle.compile(
                system=system_for_compile,
                graph_revision=graph_revision,
                valve_state_by_line=valve_state_by_line or None,
            )

        self._compiled = CompiledConnectionNetwork(
            graph_revision=graph_revision,
            topology=topology,
            process_bindings=bindings,
            hydraulic=hydraulic,
        )
        return self._compiled

    @property
    def compiled(self) -> CompiledConnectionNetwork | None:
        return self._compiled

    @property
    def queued_reconfigurations(self) -> tuple[QueuedReconfigurationTransaction, ...]:
        return tuple(self._queued_reconfigurations)

    @property
    def next_edge_index(self) -> int:
        return self._next_edge_index

    @property
    def next_reconfiguration_index(self) -> int:
        return self._next_reconfiguration_index

    @property
    def next_revision_index(self) -> int:
        return self._next_revision_index

    def set_reconfiguration_counters(
        self,
        *,
        next_edge_index: int,
        next_reconfiguration_index: int,
        next_revision_index: int,
    ) -> None:
        self._next_edge_index = next_edge_index
        self._next_reconfiguration_index = next_reconfiguration_index
        self._next_revision_index = next_revision_index

    def replace_queued_reconfigurations(
        self,
        queued_reconfigurations: Sequence[QueuedReconfigurationTransaction],
    ) -> None:
        self._queued_reconfigurations = list(queued_reconfigurations)

    def stage_valve_open_fraction_command(self, *, line_id: str, open_fraction: float) -> None:
        if not line_id.strip():
            raise ValueError("line_id must be a non-empty string")
        if not isfinite(open_fraction):
            raise ValueError("open_fraction must be finite")

        compiled = self._compiled
        if compiled is None or compiled.hydraulic is None:
            raise ValueError("cannot stage valve command without compiled hydraulic graph")

        _ = compiled.hydraulic.with_valve_commands({line_id: open_fraction})
        self._pending_valve_open_fractions[line_id] = float(open_fraction)

    def consume_pending_valve_open_fraction_commands(self) -> Mapping[str, float]:
        pending = {
            line_id: self._pending_valve_open_fractions[line_id]
            for line_id in sorted(self._pending_valve_open_fractions)
        }
        self._pending_valve_open_fractions = {}
        return pending

    def replace_compiled_hydraulic(self, *, hydraulic: CompiledHydraulicGraph) -> None:
        compiled = self._compiled
        if compiled is None:
            raise RuntimeError("cannot replace hydraulic graph before topology compile")
        self._compiled = CompiledConnectionNetwork(
            graph_revision=compiled.graph_revision,
            topology=compiled.topology,
            process_bindings=compiled.process_bindings,
            hydraulic=hydraulic,
        )

    def step(self, *, macro_step_time_s: float) -> object:
        if self._runtime_orchestrator is None:
            raise RuntimeError(
                "runtime step is unavailable: runtime orchestrator not configured for ConnectionNetwork"
            )
        return self._runtime_orchestrator.step(network=self, macro_step_time_s=macro_step_time_s)

    def queue_reconfiguration(self, request: object) -> str:
        if not isinstance(request, Mapping):
            raise diagnostic_value_error(
                code=VALIDATION_FAILURE_CODE,
                message="invalid reconfiguration request: expected mapping with non-empty string field 'operation'",
                path="operation",
                hint="provide a mapping request payload containing a non-empty string operation",
            )
        request_mapping = cast(Mapping[object, object], request)
        operation = request_mapping.get("operation")
        if not isinstance(operation, str) or not operation.strip():
            raise diagnostic_value_error(
                code=VALIDATION_FAILURE_CODE,
                message="invalid reconfiguration request: expected mapping with non-empty string field 'operation'",
                path="operation",
                hint="provide a mapping request payload containing a non-empty string operation",
            )

        idempotency_key_raw = request_mapping.get("idempotency_key")
        idempotency_key: str | None
        if idempotency_key_raw is None:
            idempotency_key = None
        elif isinstance(idempotency_key_raw, str) and idempotency_key_raw.strip():
            idempotency_key = idempotency_key_raw.strip()
        else:
            raise diagnostic_value_error(
                code=VALIDATION_FAILURE_CODE,
                message="invalid reconfiguration request: optional field 'idempotency_key' must be a non-empty string",
                path="idempotency_key",
                hint="remove idempotency_key or provide a non-empty string",
            )

        expected_revision_raw = request_mapping.get("expected_revision")
        expected_revision: str | None
        if expected_revision_raw is None:
            expected_revision = None
        elif isinstance(expected_revision_raw, str) and expected_revision_raw.strip():
            expected_revision = expected_revision_raw.strip()
        else:
            raise diagnostic_value_error(
                code=VALIDATION_FAILURE_CODE,
                message="invalid reconfiguration request: optional field 'expected_revision' must be a non-empty string",
                path="expected_revision",
                hint="remove expected_revision or provide a non-empty string",
            )

        metadata_raw = request_mapping.get("metadata")
        metadata: dict[str, object]
        if metadata_raw is None:
            metadata = {}
        elif isinstance(metadata_raw, Mapping):
            metadata_mapping = cast(Mapping[object, object], metadata_raw)
            metadata = {str(key): value for key, value in metadata_mapping.items()}
        else:
            raise diagnostic_value_error(
                code=VALIDATION_FAILURE_CODE,
                message="invalid reconfiguration request: optional field 'metadata' must be a mapping",
                path="metadata",
                hint="provide metadata as a mapping of key/value pairs",
            )

        mutations_field = request_mapping.get("mutations")
        mutations: tuple[dict[str, object], ...]
        if mutations_field is None:
            mutations = (self._normalize_reconfiguration_mutation(request_mapping),)
        else:
            if isinstance(mutations_field, str) or not isinstance(mutations_field, Sequence):
                raise diagnostic_value_error(
                    code=VALIDATION_FAILURE_CODE,
                    message="invalid reconfiguration request: field 'mutations' must be a non-empty sequence of mapping objects",
                    path="mutations",
                    hint="provide at least one mutation mapping with a non-empty operation",
                )
            normalized_mutations: list[dict[str, object]] = []
            for mutation in mutations_field:
                if not isinstance(mutation, Mapping):
                    raise diagnostic_value_error(
                        code=VALIDATION_FAILURE_CODE,
                        message="invalid reconfiguration request: each mutation must be a mapping with non-empty string field 'operation'",
                        path="mutations",
                        hint="each mutation must be a mapping object",
                    )
                normalized_mutations.append(
                    self._normalize_reconfiguration_mutation(
                        cast(Mapping[object, object], mutation)
                    )
                )
            if not normalized_mutations:
                raise diagnostic_value_error(
                    code=VALIDATION_FAILURE_CODE,
                    message="invalid reconfiguration request: field 'mutations' must be a non-empty sequence of mapping objects",
                    path="mutations",
                    hint="provide at least one mutation mapping with a non-empty operation",
                )
            mutations = tuple(normalized_mutations)

        envelope = validate_command_envelope(
            idempotency_key=idempotency_key,
            expected_revision=expected_revision,
            metadata=metadata,
            mutations=mutations,
        )

        request_id = f"rq_{self._next_reconfiguration_index:04d}"
        self._next_reconfiguration_index += 1
        self._queued_reconfigurations.append(
            QueuedReconfigurationTransaction(
                request_id=request_id,
                idempotency_key=envelope.idempotency_key,
                expected_revision=envelope.expected_revision,
                metadata=dict(envelope.metadata),
                mutations=tuple(mutation.as_mapping() for mutation in envelope.mutations),
            )
        )
        return request_id

    def save_runtime_snapshot(self) -> Mapping[str, object]:
        if self._runtime_orchestrator is None:
            raise RuntimeError(
                "runtime snapshot is unavailable: runtime orchestrator not configured for ConnectionNetwork"
            )
        return self._runtime_orchestrator.save_runtime_snapshot(network=self)

    def resume_from_snapshot(self, *, snapshot: object) -> None:
        if not isinstance(snapshot, Mapping):
            raise ValueError("invalid snapshot payload: expected mapping")
        snapshot_mapping = cast(Mapping[str, object], snapshot)
        if self._runtime_orchestrator is None:
            raise RuntimeError(
                "runtime resume is unavailable: runtime orchestrator not configured for ConnectionNetwork"
            )
        self._runtime_orchestrator.resume_from_snapshot(network=self, snapshot=snapshot_mapping)

    def remove_boundary(self, *, boundary_id: object) -> None:
        self._remove_boundary(boundary_id=boundary_id)

    def remove_process(self, *, process_id: object) -> None:
        self._remove_process(process_id=process_id)

    def add_process_port(
        self,
        *,
        process_id: object,
        direction: object,
        port_name: object,
    ) -> None:
        self._add_process_port(process_id=process_id, direction=direction, port_name=port_name)

    def remove_process_port(
        self,
        *,
        process_id: object,
        direction: object,
        port_name: object,
    ) -> None:
        self._remove_process_port(process_id=process_id, direction=direction, port_name=port_name)

    def remove_connection(
        self,
        *,
        edge_id: object | None = None,
        source: object | None = None,
        target: object | None = None,
    ) -> str:
        return self._remove_connection(edge_id=edge_id, source=source, target=target)

    def rewire_connection(self, *, edge_id: object, source: object, target: object) -> None:
        self._rewire_connection(edge_id=edge_id, source=source, target=target)

    def configure_line_geometry(
        self,
        *,
        line_id: object,
        radius_m: object,
        length_m: object,
        equation_name: object | None = None,
        resistance_parameter_name: object | None = None,
    ) -> None:
        normalized_line_id = self._normalize_line_id(line_id)
        self._assert_line_exists(normalized_line_id)

        radius_scalar = self._require_positive_finite_float(
            value=radius_m,
            error_message="configure_line_geometry field 'radius_m' must be a finite positive number",
        )
        length_scalar = self._require_positive_finite_float(
            value=length_m,
            error_message="configure_line_geometry field 'length_m' must be a finite positive number",
        )

        previous = self._line_hydraulic_configs.get(normalized_line_id)
        resolved_equation_name = (
            previous.equation_name
            if previous is not None
            else self._default_equation_name_for_line(normalized_line_id)
        )
        resolved_parameter_name = (
            previous.resistance_parameter_name if previous is not None else "pipe_resistance"
        )
        resistance_mode: Literal["derived", "manual_override"] = "derived"
        manual_value: float | None = None
        valve: ValveConfig | None = None
        if previous is not None:
            resistance_mode = previous.resistance.mode
            manual_value = previous.resistance.manual_value
            valve = previous.valve

        if equation_name is not None:
            resolved_equation_name = self._require_non_empty_string_value(
                value=equation_name,
                error_message="configure_line_geometry optional field 'equation_name' must be a non-empty string",
            )
        if resistance_parameter_name is not None:
            resolved_parameter_name = self._require_non_empty_string_value(
                value=resistance_parameter_name,
                error_message=(
                    "configure_line_geometry optional field "
                    + "'resistance_parameter_name' must be a non-empty string"
                ),
            )

        resistance = ResistanceConfig(
            mode=resistance_mode,
            radius_m=radius_scalar,
            length_m=length_scalar,
            manual_value=manual_value,
        )
        self._line_hydraulic_configs[normalized_line_id] = _LineHydraulicConfig(
            line_id=normalized_line_id,
            equation_name=resolved_equation_name,
            resistance_parameter_name=resolved_parameter_name,
            resistance=resistance,
            valve=valve,
        )

    def configure_line_resistance(
        self,
        *,
        line_id: object,
        mode: object,
        manual_value: object | None = None,
    ) -> None:
        normalized_line_id = self._normalize_line_id(line_id)
        self._assert_line_exists(normalized_line_id)

        previous = self._line_hydraulic_configs.get(normalized_line_id)
        if previous is None:
            raise ValueError(
                "configure_line_resistance requires line geometry to be configured first"
            )

        if not isinstance(mode, str) or mode.strip() not in {"derived", "manual_override"}:
            raise ValueError(
                "configure_line_resistance field 'mode' must be 'derived' or 'manual_override'"
            )
        normalized_mode = cast(Literal["derived", "manual_override"], mode.strip())

        resolved_manual_value: float | None = None
        if normalized_mode == "manual_override":
            resolved_manual_value = self._require_non_negative_finite_float(
                value=manual_value,
                error_message=(
                    "configure_line_resistance field 'manual_value' must be a finite "
                    + "non-negative number when mode is 'manual_override'"
                ),
            )

        resistance = ResistanceConfig(
            mode=normalized_mode,
            radius_m=previous.resistance.radius_m,
            length_m=previous.resistance.length_m,
            manual_value=resolved_manual_value,
        )
        self._line_hydraulic_configs[normalized_line_id] = _LineHydraulicConfig(
            line_id=normalized_line_id,
            equation_name=previous.equation_name,
            resistance_parameter_name=previous.resistance_parameter_name,
            resistance=resistance,
            valve=previous.valve,
        )

    def attach_line_valve(
        self,
        *,
        line_id: object,
        valve_id: object,
        minimum_open_fraction: object = 0.0,
        maximum_open_fraction: object = 1.0,
        initial_open_fraction: object = 1.0,
        equation_name: object | None = None,
        resistance_parameter_name: object | None = None,
    ) -> None:
        normalized_line_id = self._normalize_line_id(line_id)
        self._assert_line_exists(normalized_line_id)

        previous = self._line_hydraulic_configs.get(normalized_line_id)
        if previous is None:
            raise ValueError("attach_line_valve requires line geometry to be configured first")

        normalized_valve_id = self._require_non_empty_string_value(
            value=valve_id,
            error_message="attach_line_valve field 'valve_id' must be a non-empty string",
        )
        minimum_scalar = self._require_finite_float(
            value=minimum_open_fraction,
            error_message="attach_line_valve field 'minimum_open_fraction' must be finite number",
        )
        maximum_scalar = self._require_finite_float(
            value=maximum_open_fraction,
            error_message="attach_line_valve field 'maximum_open_fraction' must be finite number",
        )
        initial_scalar = self._require_finite_float(
            value=initial_open_fraction,
            error_message="attach_line_valve field 'initial_open_fraction' must be finite number",
        )

        resolved_equation_name = previous.equation_name
        if equation_name is not None:
            resolved_equation_name = self._require_non_empty_string_value(
                value=equation_name,
                error_message="attach_line_valve optional field 'equation_name' must be a non-empty string",
            )

        resolved_parameter_name = previous.resistance_parameter_name
        if resistance_parameter_name is not None:
            resolved_parameter_name = self._require_non_empty_string_value(
                value=resistance_parameter_name,
                error_message=(
                    "attach_line_valve optional field 'resistance_parameter_name' "
                    + "must be a non-empty string"
                ),
            )
        elif previous.valve is None:
            resolved_parameter_name = "valve_resistance"

        valve = ValveConfig(
            valve_id=normalized_valve_id,
            minimum_open_fraction=minimum_scalar,
            maximum_open_fraction=maximum_scalar,
            initial_open_fraction=initial_scalar,
        )
        self._line_hydraulic_configs[normalized_line_id] = _LineHydraulicConfig(
            line_id=normalized_line_id,
            equation_name=resolved_equation_name,
            resistance_parameter_name=resolved_parameter_name,
            resistance=previous.resistance,
            valve=valve,
        )

    def capture_reconfiguration_state(self) -> _NetworkReconfigurationState:
        return self._capture_reconfiguration_state()

    def restore_reconfiguration_state(self, state: _NetworkReconfigurationState) -> None:
        self._restore_reconfiguration_state(state)

    def drain_reconfiguration_queue(self) -> tuple[QueuedReconfigurationTransaction, ...]:
        return self._drain_reconfiguration_queue()

    def _add_boundary(
        self,
        *,
        boundary_id: str,
        direction: Literal["source", "sink"],
        port_name: str,
    ) -> None:
        self._validate_node_id(boundary_id)
        self._ensure_node_id_is_available(boundary_id)
        normalized_port = self._normalize_port_name(port_name)
        self._boundary_specs[boundary_id] = _BoundarySpec(
            boundary_id=boundary_id,
            direction=direction,
            port_name=normalized_port,
        )

    def _remove_process(self, *, process_id: object) -> None:
        if not isinstance(process_id, str) or not process_id.strip():
            raise ValueError("remove_process requires non-empty string field 'process_id'")
        process_id = process_id.strip()
        if process_id not in self._process_specs:
            raise ValueError(f"unknown process '{process_id}'")

        incident_edges = tuple(
            sorted(
                edge.edge_id
                for edge in self._edges
                if edge.source.node_id == process_id or edge.target.node_id == process_id
            )
        )
        if incident_edges:
            raise ValueError(
                f"cannot remove process '{process_id}': connected edges exist {incident_edges!r}"
            )

        del self._process_specs[process_id]

    def _remove_boundary(self, *, boundary_id: object) -> None:
        if not isinstance(boundary_id, str) or not boundary_id.strip():
            raise ValueError("remove_boundary requires non-empty string field 'boundary_id'")
        boundary_id = boundary_id.strip()
        if boundary_id not in self._boundary_specs:
            raise ValueError(f"unknown boundary '{boundary_id}'")

        incident_edges = tuple(
            sorted(
                edge.edge_id
                for edge in self._edges
                if edge.source.node_id == boundary_id or edge.target.node_id == boundary_id
            )
        )
        if incident_edges:
            raise ValueError(
                f"cannot remove boundary '{boundary_id}': connected edges exist {incident_edges!r}"
            )
        del self._boundary_specs[boundary_id]

    def _add_process_port(
        self,
        *,
        process_id: object,
        direction: object,
        port_name: object,
    ) -> None:
        if not isinstance(process_id, str) or not process_id.strip():
            raise ValueError("add_process_port requires non-empty string field 'process_id'")
        process_id = process_id.strip()
        spec = self._process_specs.get(process_id)
        if spec is None:
            raise ValueError(f"unknown process '{process_id}'")

        if not isinstance(direction, str) or direction not in ("inlet", "outlet"):
            raise ValueError(
                "add_process_port requires field 'direction' to be 'inlet' or 'outlet'"
            )
        normalized_port_name = self._normalize_port_name(port_name)

        known_ports = set(spec.inlet_ports) | set(spec.outlet_ports)
        if normalized_port_name in known_ports:
            raise ValueError(
                f"duplicate process endpoint '{process_id}.{normalized_port_name}' is not allowed"
            )

        if direction == "inlet":
            self._process_specs[process_id] = _ProcessSpec(
                process_id=spec.process_id,
                inlet_ports=(*spec.inlet_ports, normalized_port_name),
                outlet_ports=spec.outlet_ports,
            )
            return

        self._process_specs[process_id] = _ProcessSpec(
            process_id=spec.process_id,
            inlet_ports=spec.inlet_ports,
            outlet_ports=(*spec.outlet_ports, normalized_port_name),
        )

    def _remove_process_port(
        self,
        *,
        process_id: object,
        direction: object,
        port_name: object,
    ) -> None:
        if not isinstance(process_id, str) or not process_id.strip():
            raise ValueError("remove_process_port requires non-empty string field 'process_id'")
        process_id = process_id.strip()
        spec = self._process_specs.get(process_id)
        if spec is None:
            raise ValueError(f"unknown process '{process_id}'")

        if not isinstance(direction, str) or direction not in ("inlet", "outlet"):
            raise ValueError(
                "remove_process_port requires field 'direction' to be 'inlet' or 'outlet'"
            )
        normalized_port_name = self._normalize_port_name(port_name)
        target_ports = spec.inlet_ports if direction == "inlet" else spec.outlet_ports
        if normalized_port_name not in target_ports:
            raise ValueError(
                f"unknown process endpoint '{process_id}.{normalized_port_name}' for direction '{direction}'"
            )

        incident_edges = tuple(
            sorted(
                edge.edge_id
                for edge in self._edges
                if (edge.source.node_id, edge.source.port_name)
                == (process_id, normalized_port_name)
                or (edge.target.node_id, edge.target.port_name)
                == (process_id, normalized_port_name)
            )
        )
        if incident_edges:
            raise ValueError(
                f"cannot remove process endpoint '{process_id}.{normalized_port_name}': connected edges exist {incident_edges!r}"
            )

        if direction == "inlet":
            updated_inlets = tuple(
                item for item in spec.inlet_ports if item != normalized_port_name
            )
            self._process_specs[process_id] = _ProcessSpec(
                process_id=spec.process_id,
                inlet_ports=updated_inlets,
                outlet_ports=spec.outlet_ports,
            )
            return

        updated_outlets = tuple(item for item in spec.outlet_ports if item != normalized_port_name)
        self._process_specs[process_id] = _ProcessSpec(
            process_id=spec.process_id,
            inlet_ports=spec.inlet_ports,
            outlet_ports=updated_outlets,
        )

    def _remove_connection(
        self,
        *,
        edge_id: object | None = None,
        source: object | None = None,
        target: object | None = None,
    ) -> str:
        if edge_id is not None:
            if not isinstance(edge_id, str) or not edge_id.strip():
                raise ValueError("remove_connection field 'edge_id' must be a non-empty string")
            normalized_edge_id = edge_id.strip()
            for index, edge in enumerate(self._edges):
                if edge.edge_id != normalized_edge_id:
                    continue
                del self._edges[index]
                edge_key = (
                    edge.source.node_id,
                    edge.source.port_name,
                    edge.target.node_id,
                    edge.target.port_name,
                )
                _ = self._edge_lookup.pop(edge_key, None)
                _ = self._line_hydraulic_configs.pop(normalized_edge_id, None)
                return normalized_edge_id
            raise ValueError(f"unknown connection edge_id '{normalized_edge_id}'")

        if source is None or target is None:
            raise ValueError(
                "remove_connection requires either field 'edge_id' or both fields 'source' and 'target'"
            )

        source_ref = self._parse_endpoint(source)
        target_ref = self._parse_endpoint(target)
        edge_key = (
            source_ref.node_id,
            source_ref.port_name,
            target_ref.node_id,
            target_ref.port_name,
        )
        existing_edge_id = self._edge_lookup.get(edge_key)
        if existing_edge_id is None:
            edge_name = (
                f"{source_ref.node_id}.{source_ref.port_name}"
                f"->{target_ref.node_id}.{target_ref.port_name}"
            )
            raise ValueError(f"unknown connection '{edge_name}'")

        for index, edge in enumerate(self._edges):
            if edge.edge_id != existing_edge_id:
                continue
            del self._edges[index]
            _ = self._edge_lookup.pop(edge_key, None)
            _ = self._line_hydraulic_configs.pop(existing_edge_id, None)
            return existing_edge_id

        raise ValueError(f"unknown connection edge_id '{existing_edge_id}'")

    def _rewire_connection(
        self,
        *,
        edge_id: object,
        source: object,
        target: object,
    ) -> None:
        if not isinstance(edge_id, str) or not edge_id.strip():
            raise ValueError("rewire_connection field 'edge_id' must be a non-empty string")
        normalized_edge_id = edge_id.strip()
        if not isinstance(source, str) or not source.strip():
            raise ValueError("rewire_connection field 'source' must be a non-empty string")
        if not isinstance(target, str) or not target.strip():
            raise ValueError("rewire_connection field 'target' must be a non-empty string")
        normalized_source = source.strip()
        normalized_target = target.strip()

        original_index: int | None = None
        original_edge: ConnectionEdge | None = None
        for index, edge in enumerate(self._edges):
            if edge.edge_id == normalized_edge_id:
                original_index = index
                original_edge = edge
                break
        if original_index is None or original_edge is None:
            raise ValueError(f"unknown connection edge_id '{normalized_edge_id}'")

        original_key = (
            original_edge.source.node_id,
            original_edge.source.port_name,
            original_edge.target.node_id,
            original_edge.target.port_name,
        )
        del self._edges[original_index]
        _ = self._edge_lookup.pop(original_key, None)
        try:
            _ = self.connect(normalized_source, normalized_target, edge_id=normalized_edge_id)
        except Exception:
            self._edges.insert(original_index, original_edge)
            self._edge_lookup[original_key] = normalized_edge_id
            raise

    def _capture_reconfiguration_state(self) -> _NetworkReconfigurationState:
        return _NetworkReconfigurationState(
            process_specs=dict(self._process_specs),
            boundary_specs=dict(self._boundary_specs),
            edges=list(self._edges),
            line_hydraulic_configs=dict(self._line_hydraulic_configs),
            edge_lookup=dict(self._edge_lookup),
            next_edge_index=self._next_edge_index,
            next_reconfiguration_index=self._next_reconfiguration_index,
            next_revision_index=self._next_revision_index,
            queued_reconfigurations=list(self._queued_reconfigurations),
            pending_valve_open_fractions=dict(self._pending_valve_open_fractions),
            compiled=self._compiled,
        )

    def _restore_reconfiguration_state(self, state: _NetworkReconfigurationState) -> None:
        self._process_specs = dict(state.process_specs)
        self._boundary_specs = dict(state.boundary_specs)
        self._edges = list(state.edges)
        self._line_hydraulic_configs = dict(state.line_hydraulic_configs)
        self._edge_lookup = dict(state.edge_lookup)
        self._next_edge_index = state.next_edge_index
        self._next_reconfiguration_index = state.next_reconfiguration_index
        self._next_revision_index = state.next_revision_index
        self._queued_reconfigurations = list(state.queued_reconfigurations)
        self._pending_valve_open_fractions = dict(state.pending_valve_open_fractions)
        self._compiled = state.compiled

    def _drain_reconfiguration_queue(self) -> tuple[QueuedReconfigurationTransaction, ...]:
        queue = tuple(self._queued_reconfigurations)
        self._queued_reconfigurations = []
        return queue

    def _apply_line_hydraulic_configurations(
        self, *, system: HydraulicSystemDefinition
    ) -> tuple[HydraulicSystemDefinition, Mapping[str, CompiledValveHydraulicState]]:
        if not self._line_hydraulic_configs:
            return system, {}

        equations = list(system.equations)
        equation_name_to_index: dict[str, int] = {}
        for index, equation in enumerate(equations):
            if equation.name in equation_name_to_index:
                raise ValueError(
                    "line configuration requires unique equation names; duplicate {!r}".format(
                        equation.name
                    )
                )
            equation_name_to_index[equation.name] = index

        valve_state_by_line: dict[str, CompiledValveHydraulicState] = {}
        for line_id in sorted(self._line_hydraulic_configs):
            self._assert_line_exists(line_id)
            config = self._line_hydraulic_configs[line_id]
            resolved_resistance = resolve_line_resistance(
                line_id=line_id,
                resistance=config.resistance,
            )

            equation_index = equation_name_to_index.get(config.equation_name)
            if equation_index is None:
                raise ValueError(
                    "line {!r} references unknown hydraulic equation {!r}".format(
                        line_id,
                        config.equation_name,
                    )
                )
            equation = equations[equation_index]
            parameter_name = config.resistance_parameter_name
            if parameter_name not in equation.element.parameter_spec.names:
                raise ValueError(
                    "line {!r} references unsupported resistance parameter {!r} for equation {!r}".format(
                        line_id,
                        parameter_name,
                        equation.name,
                    )
                )

            if config.valve is not None:
                valve_state_by_line[line_id] = compile_valve_hydraulic_state(
                    line_id=line_id,
                    equation_name=config.equation_name,
                    resolved_resistance=resolved_resistance,
                    valve=config.valve,
                    resistance_parameter_name=parameter_name,
                )
                continue

            updated_parameters = dict(equation.parameters)
            updated_parameters[parameter_name] = resolved_resistance.active_value
            equations[equation_index] = ElementEquation(
                name=equation.name,
                element=equation.element,
                inputs=equation.inputs,
                parameters=MappingProxyType(updated_parameters),
                unknown_name_map=equation.unknown_name_map,
                residual_name_map=equation.residual_name_map,
            )

        return (
            HydraulicSystemDefinition(
                equations=tuple(equations),
                linear_residual_equations=system.linear_residual_equations,
                unknown_order=system.unknown_order,
                residual_order=system.residual_order,
            ),
            valve_state_by_line,
        )

    def _normalize_reconfiguration_mutation(
        self, request_mapping: Mapping[object, object]
    ) -> dict[str, object]:
        operation = request_mapping.get("operation")
        if not isinstance(operation, str) or not operation.strip():
            raise ValueError(
                "invalid reconfiguration request: each mutation must be a mapping with non-empty string field 'operation'"
            )
        return {str(key): value for key, value in request_mapping.items()}

    def _parse_endpoint(self, endpoint: object) -> PortReference:
        if not isinstance(endpoint, str) or not endpoint.strip():
            raise ValueError("invalid endpoint: expected non-empty string")

        normalized_endpoint = endpoint.strip()
        parts = normalized_endpoint.split(".")
        if len(parts) == 2:
            node_id = parts[0].strip()
            port_name = parts[1].strip()
            if not node_id or not port_name:
                raise ValueError(
                    f"invalid endpoint '{endpoint}': expected '<node_id>.<port_name>' format"
                )
            node_kind = self._node_kind(node_id)
            if node_kind is None:
                raise ValueError(f"unknown endpoint node '{node_id}'")
            self._assert_port_exists(node_id=node_id, port_name=port_name)
            return PortReference(node_id=node_id, port_name=port_name)

        if len(parts) != 1:
            raise ValueError(
                f"invalid endpoint '{endpoint}': expected '<node_id>.<port_name>' or '<boundary_id>'"
            )

        node_id = parts[0].strip()
        if not node_id:
            raise ValueError(
                f"invalid endpoint '{endpoint}': expected '<node_id>.<port_name>' or '<boundary_id>'"
            )

        node_kind = self._node_kind(node_id)
        if node_kind is None:
            raise ValueError(f"unknown endpoint node '{node_id}'")
        if node_kind == "process":
            raise ValueError(
                f"invalid endpoint '{endpoint}': process endpoints must use '<process_id>.<port_name>' format"
            )
        boundary = self._boundary_specs[node_id]
        return PortReference(node_id=node_id, port_name=boundary.port_name)

    def _assert_port_exists(self, *, node_id: str, port_name: str) -> None:
        process_spec = self._process_specs.get(node_id)
        if process_spec is not None:
            known_ports = set(process_spec.inlet_ports) | set(process_spec.outlet_ports)
            if port_name not in known_ports:
                raise ValueError(
                    f"unknown process endpoint '{node_id}.{port_name}': available ports are {sorted(known_ports)!r}"
                )
            return

        boundary_spec = self._boundary_specs.get(node_id)
        if boundary_spec is not None and port_name != boundary_spec.port_name:
            raise ValueError(
                f"unknown boundary endpoint '{node_id}.{port_name}': expected port '{boundary_spec.port_name}'"
            )

    def _node_kind(self, node_id: str) -> str | None:
        if node_id in self._process_specs:
            return "process"
        if node_id in self._boundary_specs:
            return "boundary"
        return None

    def _endpoint_direction(self, *, node_id: str, port_name: str) -> Literal["inlet", "outlet"]:
        process_spec = self._process_specs.get(node_id)
        if process_spec is not None:
            if port_name in process_spec.inlet_ports:
                return "inlet"
            if port_name in process_spec.outlet_ports:
                return "outlet"
            raise ValueError(f"unknown process endpoint '{node_id}.{port_name}'")

        boundary_spec = self._boundary_specs.get(node_id)
        if boundary_spec is not None:
            if port_name != boundary_spec.port_name:
                raise ValueError(
                    f"unknown boundary endpoint '{node_id}.{port_name}': expected port '{boundary_spec.port_name}'"
                )
            if boundary_spec.direction == "source":
                return "outlet"
            return "inlet"

        raise ValueError(f"unknown endpoint node '{node_id}'")

    def _validate_connection_directions(
        self, *, source_ref: PortReference, target_ref: PortReference
    ) -> None:
        source_direction = self._endpoint_direction(
            node_id=source_ref.node_id,
            port_name=source_ref.port_name,
        )
        target_direction = self._endpoint_direction(
            node_id=target_ref.node_id,
            port_name=target_ref.port_name,
        )
        if source_direction == "outlet" and target_direction == "inlet":
            return

        edge_name = (
            f"{source_ref.node_id}.{source_ref.port_name}"
            + f"->{target_ref.node_id}.{target_ref.port_name}"
        )
        raise diagnostic_value_error(
            code=VALIDATION_FAILURE_CODE,
            message="invalid endpoint direction for connection {!r}: source direction {!r} and target direction {!r} are incompatible".format(
                edge_name,
                source_direction,
                target_direction,
            ),
            path="source/target",
            hint="connect outlet endpoints to inlet endpoints",
        )

    def _normalize_line_id(self, line_id: object) -> str:
        if not isinstance(line_id, str) or not line_id.strip():
            raise ValueError("line_id must be a non-empty string")
        return line_id.strip()

    def _line_exists(self, line_id: str) -> bool:
        return any(edge.edge_id == line_id for edge in self._edges)

    def _assert_line_exists(self, line_id: str) -> None:
        if self._line_exists(line_id):
            return
        raise ValueError(f"unknown line '{line_id}'")

    def _default_equation_name_for_line(self, line_id: str) -> str:
        return f"eq_{line_id}"

    def _require_non_empty_string_value(self, *, value: object, error_message: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(error_message)
        return value.strip()

    def _require_finite_float(self, *, value: object, error_message: str) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(error_message)
        scalar = float(value)
        if not isfinite(scalar):
            raise ValueError(error_message)
        return scalar

    def _require_positive_finite_float(self, *, value: object, error_message: str) -> float:
        scalar = self._require_finite_float(value=value, error_message=error_message)
        if scalar <= 0.0:
            raise ValueError(error_message)
        return scalar

    def _require_non_negative_finite_float(self, *, value: object, error_message: str) -> float:
        scalar = self._require_finite_float(value=value, error_message=error_message)
        if scalar < 0.0:
            raise ValueError(error_message)
        return scalar

    def _validate_node_id(self, node_id: object) -> None:
        if not isinstance(node_id, str) or not node_id.strip():
            raise ValueError("node id must be a non-empty string")

    def _validate_edge_id(self, edge_id: object) -> None:
        if not isinstance(edge_id, str) or not edge_id.strip():
            raise ValueError("edge id must be a non-empty string")

    def _ensure_node_id_is_available(self, node_id: str) -> None:
        if self._node_kind(node_id) is not None:
            raise ValueError(f"duplicate node id '{node_id}' is not allowed")

    def _normalize_port_names(
        self,
        *,
        node_id: str,
        port_names: Sequence[str],
        role: str,
    ) -> tuple[str, ...]:
        normalized = tuple(self._normalize_port_name(port_name) for port_name in port_names)
        duplicates = sorted(
            {port_name for port_name in normalized if normalized.count(port_name) > 1}
        )
        if duplicates:
            raise ValueError(
                f"duplicate {role} ports for process '{node_id}' are not allowed: {duplicates!r}"
            )
        return normalized

    def _normalize_port_name(self, port_name: object) -> str:
        if not isinstance(port_name, str) or not port_name.strip():
            raise ValueError("port name must be a non-empty string")
        return port_name.strip()


__all__ = [
    "CompiledConnectionNetwork",
    "ConnectionNetwork",
    "NetworkBoundarySpec",
    "NetworkLineHydraulicConfig",
    "NetworkProcessSpec",
    "QueuedReconfigurationTransaction",
]

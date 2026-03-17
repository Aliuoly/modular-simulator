from __future__ import annotations

# pyright: reportMissingImports=false

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from math import isfinite
from typing import TYPE_CHECKING, Literal, Protocol, cast

import numpy as np
from numpy.typing import NDArray

from ..domain.state import MaterialState, PortCondition
from ..hydraulics.hydraulic_compile import CompiledHydraulicGraph
from ..hydraulics.hydraulic_solver import HydraulicSolveResult
from ..topology.junction import (
    NEAR_ZERO_INCOMING_FLOW_EPSILON,
    JunctionMixingResult,
    mix_junction_state,
    mix_junction_state_with_enthalpy,
)
from ..topology.process_binding import BindingError
from ..topology.topology import ConnectionEdge
from .connection_layer import TransportAndMixingUpdate
from .process_stream_io import (
    ProcessStreamIO,
    resolve_process_outlet_condition,
)
from modular_simulation.thermodynamics.stream import StreamData
from modular_simulation.thermodynamics.species import SpeciesProjection

if TYPE_CHECKING:
    from ..topology.network import ConnectionNetwork
    from modular_simulation.thermodynamics.property_package import PropertyPackage
    from modular_simulation.thermodynamics.runtime_context import SimulationRuntimeContext


ManualOverrideHook = Callable[[Mapping[str, PortCondition]], Mapping[str, PortCondition]]


class RuntimePortSnapshotStore(Protocol):
    def record_inlet(self, node_id: str, port_name: str, condition: PortCondition) -> None: ...

    def record_outlet(self, node_id: str, port_name: str, condition: PortCondition) -> None: ...


@dataclass(frozen=True)
class ThermoBoundaryPropagationConfig:
    mode: Literal["auto", "manual", "hybrid"] = "auto"
    auto_propagate_species: bool = True
    auto_propagate_energy: bool = True
    default_pressure_pa: float = 101325.0
    default_temperature_k: float = 298.15
    default_phase_hint: str | None = "liquid"
    stream_port_io_by_node_id: Mapping[str, ProcessStreamIO] | None = None
    feed_streams_by_boundary_id: Mapping[str, StreamData] | None = None
    runtime_port_snapshot_store: RuntimePortSnapshotStore | None = None
    manual_port_conditions: Mapping[str, PortCondition] | None = None
    manual_override_hook: ManualOverrideHook | None = None

    def __post_init__(self) -> None:
        if self.mode not in {"auto", "manual", "hybrid"}:
            raise ValueError("mode must be one of 'auto', 'manual', or 'hybrid'")
        if not isfinite(self.default_pressure_pa) or self.default_pressure_pa <= 0.0:
            raise ValueError("default_pressure_pa must be finite and positive")
        if not isfinite(self.default_temperature_k) or self.default_temperature_k <= 0.0:
            raise ValueError("default_temperature_k must be finite and positive")


class ThermoBoundaryPropagationStep:
    def __init__(
        self,
        *,
        runtime_context: SimulationRuntimeContext,
        config: ThermoBoundaryPropagationConfig | None = None,
    ) -> None:
        self._runtime_context: SimulationRuntimeContext = runtime_context
        self._config: ThermoBoundaryPropagationConfig = (
            config if config is not None else ThermoBoundaryPropagationConfig()
        )

    def __call__(
        self,
        *,
        network: ConnectionNetwork,
        hydraulic_result: HydraulicSolveResult,
        transport_and_mixing_update: TransportAndMixingUpdate,
        macro_step_time_s: float,
    ) -> Mapping[str, PortCondition]:
        auto_conditions: dict[str, PortCondition] = {}
        if self._config.mode in {"auto", "hybrid"}:
            auto_conditions = self._build_auto_conditions(
                network=network,
                hydraulic_result=hydraulic_result,
                transport_and_mixing_update=transport_and_mixing_update,
                macro_step_time_s=macro_step_time_s,
            )

        manual_overrides = self._resolve_manual_overrides(auto_conditions)
        if self._config.mode == "manual":
            return manual_overrides
        if self._config.mode == "hybrid":
            merged = dict(auto_conditions)
            merged.update(manual_overrides)
            return merged
        return auto_conditions

    def _build_auto_conditions(
        self,
        *,
        network: ConnectionNetwork,
        hydraulic_result: HydraulicSolveResult,
        transport_and_mixing_update: TransportAndMixingUpdate,
        macro_step_time_s: float,
    ) -> dict[str, PortCondition]:
        compiled = network.compiled
        if compiled is None:
            return {}

        conditions: dict[str, PortCondition] = {}
        property_package: PropertyPackage | None = getattr(
            self._runtime_context, "property_package", None
        )
        species_ids = self._runtime_context.species_registry.cas_list
        transport_results = transport_and_mixing_update.transport_results
        junction_results = transport_and_mixing_update.junction_results
        incoming_conditions_by_target: dict[str, list[PortCondition]] = {}
        target_bindings: dict[str, tuple[str, object, str]] = {}
        target_stream_port_ios: dict[str, ProcessStreamIO] = {}
        edge_by_id = {edge.edge_id: edge for edge in compiled.topology.edges}

        for edge in sorted(compiled.topology.edges, key=lambda item: item.edge_id):
            provider_node_id = edge.source.node_id
            provider_port_name = edge.source.port_name
            receiver_node_id = edge.target.node_id
            receiver_port_name = edge.target.port_name
            resolved_hydraulic_flow = self._resolve_hydraulic_flow(
                edge_id=edge.edge_id,
                compiled_hydraulic=compiled.hydraulic,
                hydraulic_result=hydraulic_result,
            )
            if resolved_hydraulic_flow is not None and resolved_hydraulic_flow < 0.0:
                provider_node_id = edge.target.node_id
                provider_port_name = edge.target.port_name
                receiver_node_id = edge.source.node_id
                receiver_port_name = edge.source.port_name

            provider_binding = compiled.process_bindings.get(provider_node_id)
            receiver_binding = compiled.process_bindings.get(receiver_node_id)

            provider_projection = self._lookup_projection(provider_node_id)
            receiver_projection = self._lookup_projection(receiver_node_id)
            stream_condition = self._build_stream_port_condition(
                edge_id=edge.edge_id,
                source_node_id=provider_node_id,
                target_node_id=receiver_node_id,
                source_port_name=provider_port_name,
                target_port_name=receiver_port_name,
                compiled_hydraulic=compiled.hydraulic,
                hydraulic_result=hydraulic_result,
                macro_step_time_s=macro_step_time_s,
                source_binding=provider_binding,
                source_projection=provider_projection,
                target_projection=receiver_projection,
                global_species_ids=species_ids,
            )
            if stream_condition is not None:
                target_key = f"{receiver_node_id}.{receiver_port_name}"
                incoming_conditions_by_target.setdefault(target_key, []).append(stream_condition)
                if receiver_binding is not None:
                    target_bindings[target_key] = (
                        receiver_node_id,
                        receiver_binding,
                        receiver_port_name,
                    )
                target_stream_port_io = self._resolve_stream_port_io(
                    node_id=receiver_node_id,
                    binding=receiver_binding,
                )
                if target_stream_port_io is not None:
                    target_stream_port_ios[target_key] = target_stream_port_io
                continue

            if provider_binding is None and provider_node_id in compiled.process_bindings:
                continue
            if receiver_binding is None and receiver_node_id in compiled.process_bindings:
                continue

            outlet_payload = (
                self._safe_get_outlet_payload(provider_binding, provider_port_name)
                if provider_binding is not None
                else None
            )
            transport_result = transport_results.get(edge.edge_id)
            state = self._build_material_state(
                edge_id=edge.edge_id,
                source_node_id=provider_node_id,
                target_node_id=receiver_node_id,
                compiled_hydraulic=compiled.hydraulic,
                hydraulic_result=hydraulic_result,
                property_package=property_package,
                species_ids=species_ids,
                source_projection=provider_projection,
                outlet_payload=outlet_payload,
                transport_result=transport_result,
            )
            outgoing_junction_state = self._resolve_outgoing_junction_state(
                edge=edge,
                provider_node_id=provider_node_id,
                provider_port_name=provider_port_name,
                edge_by_id=edge_by_id,
                compiled_hydraulic=compiled.hydraulic,
                hydraulic_result=hydraulic_result,
                junction_results=junction_results,
            )
            if outgoing_junction_state is not None:
                state = outgoing_junction_state
            if state is None:
                continue

            receiver_pressure = self._resolve_endpoint_hydraulic_pressure(
                edge=edge,
                edge_id=edge.edge_id,
                node_id=receiver_node_id,
                port_name=receiver_port_name,
                compiled_hydraulic=compiled.hydraulic,
                hydraulic_result=hydraulic_result,
            )
            if receiver_pressure is not None:
                state = MaterialState(
                    pressure=receiver_pressure,
                    temperature=state.temperature,
                    mole_fractions=state.mole_fractions,
                    species_ids=state.species_ids,
                    phase=state.phase,
                    enthalpy_molar=state.enthalpy_molar,
                    entropy_molar=state.entropy_molar,
                )

            if self._config.auto_propagate_species:
                state = self._project_state_for_target(
                    edge_id=edge.edge_id,
                    source_node_id=provider_node_id,
                    target_node_id=receiver_node_id,
                    state=state,
                    source_projection=provider_projection,
                    target_projection=receiver_projection,
                    global_species_ids=species_ids,
                )

            flow_rate = self._resolve_flow_rate(
                edge_id=edge.edge_id,
                compiled_hydraulic=compiled.hydraulic,
                hydraulic_result=hydraulic_result,
                outlet_payload=outlet_payload,
            )
            target_key = f"{receiver_node_id}.{receiver_port_name}"
            condition = PortCondition(
                state=state,
                species_ids=state.species_ids,
                through_molar_flow_rate=flow_rate,
                macro_step_time_s=macro_step_time_s,
            )

            incoming_conditions_by_target.setdefault(target_key, []).append(condition)
            if receiver_binding is not None:
                target_bindings[target_key] = (
                    receiver_node_id,
                    receiver_binding,
                    receiver_port_name,
                )

        self._record_all_process_outlet_snapshots(
            network=network,
            macro_step_time_s=macro_step_time_s,
        )

        for target_key in sorted(incoming_conditions_by_target):
            incoming_conditions = incoming_conditions_by_target[target_key]
            if not incoming_conditions:
                continue

            mixed_result = self._mix_target_port_conditions(
                incoming_conditions=incoming_conditions,
                property_package=property_package,
            )
            mixed_state = mixed_result.state
            conditions[target_key] = PortCondition(
                state=mixed_state,
                species_ids=mixed_state.species_ids,
                through_molar_flow_rate=mixed_result.total_incoming_flow_rate,
                macro_step_time_s=macro_step_time_s,
            )

            target_node_id, target_port_name = target_key.rsplit(".", maxsplit=1)
            runtime_port_snapshot_store = self._config.runtime_port_snapshot_store
            if runtime_port_snapshot_store is not None:
                runtime_port_snapshot_store.record_inlet(
                    node_id=target_node_id,
                    port_name=target_port_name,
                    condition=conditions[target_key],
                )

            target_binding_tuple = target_bindings.get(target_key)
            if target_binding_tuple is not None:
                _, target_binding, _ = target_binding_tuple
                set_inlet = getattr(target_binding, "set_inlet", None)
                if not callable(set_inlet):
                    pass
                else:
                    try:
                        set_inlet(target_port_name, mixed_result.total_incoming_flow_rate)
                    except BindingError:
                        pass

            target_stream_port_io = target_stream_port_ios.get(target_key)
            if target_stream_port_io is None:
                continue

            target_stream_port_io.apply_inlet(
                target_port_name,
                StreamData.from_port_condition(conditions[target_key]),
            )

        return conditions

    def _record_all_process_outlet_snapshots(
        self,
        *,
        network: ConnectionNetwork,
        macro_step_time_s: float,
    ) -> None:
        runtime_port_snapshot_store = self._config.runtime_port_snapshot_store
        if runtime_port_snapshot_store is None:
            return

        compiled = network.compiled
        if compiled is None:
            return

        connected_source_ports = {
            (edge.source.node_id, edge.source.port_name) for edge in compiled.topology.edges
        }

        for process_node in sorted(
            compiled.topology.process_nodes, key=lambda item: item.process_id
        ):
            source_node_id = process_node.process_id
            source_binding = compiled.process_bindings.get(source_node_id)
            for source_port_name in process_node.outlet_ports:
                if (source_node_id, source_port_name) in connected_source_ports:
                    continue
                source_condition = self._resolve_source_outlet_condition(
                    source_node_id=source_node_id,
                    source_port_name=source_port_name,
                    source_binding=source_binding,
                    allow_binding_payload_fallback=True,
                )
                if source_condition is None:
                    continue

                state = source_condition.state
                runtime_port_snapshot_store.record_outlet(
                    node_id=source_node_id,
                    port_name=source_port_name,
                    condition=PortCondition(
                        state=state,
                        species_ids=state.species_ids,
                        through_molar_flow_rate=float(source_condition.through_molar_flow_rate),
                        macro_step_time_s=macro_step_time_s,
                    ),
                )

    def _build_stream_port_condition(
        self,
        *,
        edge_id: str,
        source_node_id: str,
        target_node_id: str,
        source_port_name: str,
        target_port_name: str,
        compiled_hydraulic: CompiledHydraulicGraph | None,
        hydraulic_result: HydraulicSolveResult,
        macro_step_time_s: float,
        source_binding: object | None,
        source_projection: SpeciesProjection | None,
        target_projection: SpeciesProjection | None,
        global_species_ids: tuple[str, ...],
    ) -> PortCondition | None:
        source_condition = self._resolve_source_outlet_condition(
            source_node_id=source_node_id,
            source_port_name=source_port_name,
            source_binding=source_binding,
        )
        if source_condition is None:
            return None

        state = source_condition.state
        if self._config.auto_propagate_species:
            state = self._project_state_for_target(
                edge_id=edge_id,
                source_node_id=source_node_id,
                target_node_id=target_node_id,
                state=state,
                source_projection=source_projection,
                target_projection=target_projection,
                global_species_ids=global_species_ids,
            )

        flow_rate = self._resolve_hydraulic_flow(
            edge_id=edge_id,
            compiled_hydraulic=compiled_hydraulic,
            hydraulic_result=hydraulic_result,
        )
        if flow_rate is None and source_binding is not None:
            return None
        if flow_rate is None:
            flow_rate = float(source_condition.through_molar_flow_rate)
        else:
            flow_rate = abs(flow_rate)

        target_state = state
        hydraulic_pressure = self._resolve_endpoint_hydraulic_pressure(
            edge=None,
            edge_id=edge_id,
            node_id=target_node_id,
            port_name=target_port_name,
            compiled_hydraulic=compiled_hydraulic,
            hydraulic_result=hydraulic_result,
        )
        if hydraulic_pressure is not None:
            target_state = MaterialState(
                pressure=hydraulic_pressure,
                temperature=state.temperature,
                mole_fractions=state.mole_fractions,
                species_ids=state.species_ids,
                phase=state.phase,
                enthalpy_molar=state.enthalpy_molar,
                entropy_molar=state.entropy_molar,
            )

        resolved_condition = PortCondition(
            state=target_state,
            species_ids=target_state.species_ids,
            through_molar_flow_rate=flow_rate,
            macro_step_time_s=macro_step_time_s,
        )

        runtime_port_snapshot_store = self._config.runtime_port_snapshot_store
        if runtime_port_snapshot_store is not None:
            runtime_port_snapshot_store.record_outlet(
                node_id=source_node_id,
                port_name=source_port_name,
                condition=PortCondition(
                    state=state,
                    species_ids=state.species_ids,
                    through_molar_flow_rate=flow_rate,
                    macro_step_time_s=macro_step_time_s,
                ),
            )

        return resolved_condition

    def _resolve_source_outlet_condition(
        self,
        *,
        source_node_id: str,
        source_port_name: str,
        source_binding: object | None,
        allow_binding_payload_fallback: bool = False,
    ) -> PortCondition | None:
        feed_streams = self._config.feed_streams_by_boundary_id
        if feed_streams is not None:
            boundary_stream = feed_streams.get(source_node_id)
            if boundary_stream is not None:
                return boundary_stream.to_port_condition()

        configured_bindings = self._config.stream_port_io_by_node_id
        candidates: list[object | None] = []
        if configured_bindings is not None:
            candidates.append(configured_bindings.get(source_node_id))
        candidates.append(source_binding)

        seen_candidate_ids: set[int] = set()
        saw_process_source = False
        saw_payload_binding = False
        for candidate in candidates:
            if candidate is None:
                continue
            saw_process_source = True
            candidate_id = id(candidate)
            if candidate_id in seen_candidate_ids:
                continue
            seen_candidate_ids.add(candidate_id)
            resolved_condition = resolve_process_outlet_condition(candidate, source_port_name)
            if resolved_condition is not None:
                return resolved_condition

            if self._supports_outlet_payload(candidate):
                saw_payload_binding = True
                if allow_binding_payload_fallback:
                    payload_condition = self._resolve_binding_payload_outlet_condition(
                        binding=candidate,
                        port_name=source_port_name,
                    )
                    if payload_condition is not None:
                        return payload_condition

        if saw_process_source and saw_payload_binding and allow_binding_payload_fallback:
            raise BindingError(
                "Missing resolvable outlet condition for process source "
                + f"'{source_node_id}.{source_port_name}'; source must implement "
                + "resolve_outlet_condition(port_name) or expose a bound get_outlet(port_name) "
                + "payload with composition."
            )

        if saw_process_source and saw_payload_binding:
            return None

        if saw_process_source:
            raise BindingError(
                "Missing canonical outlet condition for process source "
                + f"'{source_node_id}.{source_port_name}'; source must implement "
                + "resolve_outlet_condition(port_name)."
            )
        return None

    def _resolve_stream_port_io(
        self,
        *,
        node_id: str,
        binding: object | None,
    ) -> ProcessStreamIO | None:
        configured_bindings = self._config.stream_port_io_by_node_id
        if configured_bindings is not None:
            configured_binding = configured_bindings.get(node_id)
            if self._is_stream_port_io(configured_binding):
                return cast("ProcessStreamIO", configured_binding)

        if self._is_stream_port_io(binding):
            return cast("ProcessStreamIO", binding)
        return None

    def _is_stream_port_io(self, candidate: object | None) -> bool:
        if candidate is None:
            return False
        return callable(getattr(candidate, "apply_inlet", None)) and callable(
            getattr(candidate, "get_outlet_stream", None)
        )

    def _mix_target_port_conditions(
        self,
        *,
        incoming_conditions: list[PortCondition],
        property_package: PropertyPackage | None,
    ) -> JunctionMixingResult:
        if len(incoming_conditions) == 1:
            condition = incoming_conditions[0]
            return JunctionMixingResult(
                state=condition.state,
                total_incoming_flow_rate=condition.through_molar_flow_rate,
                used_fallback=False,
            )

        if property_package is None:
            incoming_by_edge = {
                f"incoming_{index:04d}": incoming_condition
                for index, incoming_condition in enumerate(incoming_conditions)
            }
            return mix_junction_state(
                incoming_port_conditions=incoming_by_edge,
                previous_state=incoming_conditions[0].state,
                near_zero_incoming_flow_epsilon=NEAR_ZERO_INCOMING_FLOW_EPSILON,
            )

        return mix_junction_state_with_enthalpy(
            incoming_states=incoming_conditions,
            property_package=property_package,
            near_zero_incoming_flow_epsilon=NEAR_ZERO_INCOMING_FLOW_EPSILON,
        )

    def _build_material_state(
        self,
        *,
        edge_id: str,
        source_node_id: str,
        target_node_id: str,
        compiled_hydraulic: CompiledHydraulicGraph | None,
        hydraulic_result: HydraulicSolveResult,
        property_package: PropertyPackage | None,
        species_ids: tuple[str, ...],
        source_projection: SpeciesProjection | None,
        outlet_payload: Mapping[str, object] | None,
        transport_result: object,
    ) -> MaterialState | None:
        composition: tuple[float, ...] | None = None
        temperature: float | None = None

        if transport_result is not None:
            state = getattr(transport_result, "state", None)
            if state is not None:
                raw_composition = getattr(state, "composition", None)
                raw_temperature = getattr(state, "temperature", None)
                if (
                    isinstance(raw_composition, tuple)
                    and raw_composition
                    and all(isinstance(item, (float, int)) for item in raw_composition)
                ):
                    composition = tuple(float(item) for item in raw_composition)
                if isinstance(raw_temperature, (float, int)) and isfinite(float(raw_temperature)):
                    temperature = float(raw_temperature)

        if composition is None and outlet_payload is not None:
            raw_composition = outlet_payload.get("composition")
            if isinstance(raw_composition, tuple) and raw_composition:
                composition = tuple(float(item) for item in raw_composition)

        if composition is None:
            return None

        resolved_composition = self._resolve_source_composition(
            edge_id=edge_id,
            source_node_id=source_node_id,
            composition=composition,
            source_projection=source_projection,
            global_species_ids=species_ids,
        )

        if temperature is None:
            temperature = self._config.default_temperature_k

        pressure = self._resolve_pressure(
            edge_id=edge_id,
            compiled_hydraulic=compiled_hydraulic,
            hydraulic_result=hydraulic_result,
            outlet_payload=outlet_payload,
            transport_result=transport_result,
        )
        phase = self._config.default_phase_hint
        enthalpy_molar: float | None = None
        entropy_molar: float | None = None

        if property_package is not None and len(resolved_composition) == len(species_ids):
            flash_state = property_package.flash_tp(temperature, pressure, resolved_composition)
            if self._config.auto_propagate_species:
                phase = flash_state.phase
            if self._config.auto_propagate_energy:
                enthalpy_phase = flash_state.phase if phase is None else phase
                enthalpy_molar = property_package.enthalpy(
                    temperature,
                    pressure,
                    resolved_composition,
                    enthalpy_phase,
                )
                entropy_molar = property_package.entropy(
                    temperature,
                    pressure,
                    resolved_composition,
                    enthalpy_phase,
                )

        propagated_species_ids: tuple[str, ...] | None = None
        if self._config.auto_propagate_species and len(species_ids) == len(resolved_composition):
            propagated_species_ids = species_ids

        return MaterialState(
            pressure=pressure,
            temperature=temperature,
            mole_fractions=resolved_composition,
            species_ids=propagated_species_ids,
            phase=phase,
            enthalpy_molar=enthalpy_molar,
            entropy_molar=entropy_molar,
        )

    def _lookup_projection(self, node_id: str) -> SpeciesProjection | None:
        species_context = getattr(self._runtime_context, "species_context", None)
        if species_context is None:
            return None
        get_projection = getattr(species_context, "get_projection", None)
        if not callable(get_projection):
            return None
        try:
            return cast(SpeciesProjection, get_projection(node_id))
        except KeyError:
            return None

    def _resolve_source_composition(
        self,
        *,
        edge_id: str,
        source_node_id: str,
        composition: tuple[float, ...],
        source_projection: SpeciesProjection | None,
        global_species_ids: tuple[str, ...],
    ) -> tuple[float, ...]:
        if source_projection is None:
            return composition

        if len(composition) == source_projection.n_global:
            return composition
        if len(composition) == source_projection.n_local:
            projected = source_projection.to_global(composition)
            return tuple(float(value) for value in projected)

        raise ValueError(
            "Incompatible source species vector for "
            f"edge '{edge_id}' from '{source_node_id}': got length {len(composition)} but expected "
            f"{source_projection.n_local} (local) or {source_projection.n_global} (global) based on "
            f"runtime species registry size {len(global_species_ids)}."
        )

    def _project_state_for_target(
        self,
        *,
        edge_id: str,
        source_node_id: str,
        target_node_id: str,
        state: MaterialState,
        source_projection: SpeciesProjection | None,
        target_projection: SpeciesProjection | None,
        global_species_ids: tuple[str, ...],
    ) -> MaterialState:
        if target_projection is None:
            return state

        global_composition = self._state_to_global_composition(
            edge_id=edge_id,
            source_node_id=source_node_id,
            state=state,
            source_projection=source_projection,
            global_species_ids=global_species_ids,
        )
        projected = target_projection.to_local(global_composition)
        dropped = float(np.sum(global_composition) - np.sum(projected))
        if dropped > 1.0e-12:
            dropped_species = tuple(
                global_species_ids[index]
                for index in range(len(global_species_ids))
                if index not in set(target_projection.global_to_local.tolist())
                and global_composition[index] > 1.0e-12
            )
            raise ValueError(
                "Incompatible species mapping for "
                f"edge '{edge_id}' from '{source_node_id}' to '{target_node_id}': target species set "
                "would drop non-zero source composition for "
                f"{dropped_species}."
            )

        target_species_ids = tuple(
            global_species_ids[int(index)] for index in target_projection.global_to_local
        )
        return MaterialState(
            pressure=state.pressure,
            temperature=state.temperature,
            mole_fractions=tuple(float(value) for value in projected),
            species_ids=target_species_ids,
            phase=state.phase,
            enthalpy_molar=state.enthalpy_molar,
            entropy_molar=state.entropy_molar,
        )

    def _state_to_global_composition(
        self,
        *,
        edge_id: str,
        source_node_id: str,
        state: MaterialState,
        source_projection: SpeciesProjection | None,
        global_species_ids: tuple[str, ...],
    ) -> NDArray[np.float64]:
        composition = np.asarray(state.mole_fractions, dtype=float)
        n_global = len(global_species_ids)
        if composition.shape == (n_global,):
            return composition
        if source_projection is not None and composition.shape == (source_projection.n_local,):
            return source_projection.to_global(composition)
        raise ValueError(
            "Incompatible source species metadata for "
            f"edge '{edge_id}' from '{source_node_id}': cannot project vector length "
            f"{composition.shape[0]} into global registry length {n_global}."
        )

    def _resolve_pressure(
        self,
        *,
        edge_id: str,
        compiled_hydraulic: CompiledHydraulicGraph | None,
        hydraulic_result: HydraulicSolveResult,
        outlet_payload: Mapping[str, object] | None,
        transport_result: object,
    ) -> float:
        hydraulic_pressure = self._resolve_hydraulic_pressure(
            edge_id=edge_id,
            compiled_hydraulic=compiled_hydraulic,
            hydraulic_result=hydraulic_result,
        )
        if hydraulic_pressure is not None:
            return hydraulic_pressure

        outlet_pressure = self._pressure_from_outlet_payload(outlet_payload)
        if outlet_pressure is not None:
            return outlet_pressure

        transport_pressure = self._pressure_from_transport_state(transport_result)
        if transport_pressure is not None:
            return transport_pressure

        return self._config.default_pressure_pa

    def _pressure_from_outlet_payload(
        self,
        outlet_payload: Mapping[str, object] | None,
    ) -> float | None:
        if outlet_payload is None:
            return None
        for key in ("pressure", "pressure_pa"):
            value = outlet_payload.get(key)
            if isinstance(value, (float, int)) and isfinite(float(value)) and float(value) > 0.0:
                return float(value)
        state_value = outlet_payload.get("state")
        if isinstance(state_value, Mapping):
            state_pressure = state_value.get("pressure")
            if (
                isinstance(state_pressure, (float, int))
                and isfinite(float(state_pressure))
                and float(state_pressure) > 0.0
            ):
                return float(state_pressure)
        return None

    def _pressure_from_transport_state(self, transport_result: object) -> float | None:
        state = getattr(transport_result, "state", None)
        if state is None:
            return None
        state_pressure = getattr(state, "pressure", None)
        if (
            isinstance(state_pressure, (float, int))
            and isfinite(float(state_pressure))
            and float(state_pressure) > 0.0
        ):
            return float(state_pressure)
        return None

    def _resolve_hydraulic_pressure(
        self,
        *,
        edge_id: str,
        compiled_hydraulic: CompiledHydraulicGraph | None,
        hydraulic_result: HydraulicSolveResult,
    ) -> float | None:
        if compiled_hydraulic is not None:
            pressure = compiled_hydraulic.resolve_line_target_pressure(
                line_id=edge_id,
                hydraulic_result=hydraulic_result,
            )
            if pressure is not None and pressure > 0.0:
                return pressure
        return None

    def _resolve_flow_rate(
        self,
        *,
        edge_id: str,
        compiled_hydraulic: CompiledHydraulicGraph | None,
        hydraulic_result: HydraulicSolveResult,
        outlet_payload: Mapping[str, object] | None,
    ) -> float:
        if compiled_hydraulic is not None:
            hydraulic_flow = self._resolve_hydraulic_flow(
                edge_id=edge_id,
                compiled_hydraulic=compiled_hydraulic,
                hydraulic_result=hydraulic_result,
            )
            if hydraulic_flow is not None:
                return abs(hydraulic_flow)

            topology_lookup = compiled_hydraulic.topology_lookup
            if edge_id in topology_lookup.line_flow_unknown_by_line:
                return 0.0

        hydraulic_flow = self._resolve_hydraulic_flow(
            edge_id=edge_id,
            compiled_hydraulic=compiled_hydraulic,
            hydraulic_result=hydraulic_result,
        )
        if hydraulic_flow is not None:
            return hydraulic_flow

        if outlet_payload is None:
            return 0.0

        fallback = outlet_payload.get("outlet_flow")
        if isinstance(fallback, (float, int)) and isfinite(float(fallback)):
            return abs(float(fallback))
        fallback = outlet_payload.get("flow")
        if isinstance(fallback, (float, int)) and isfinite(float(fallback)):
            return abs(float(fallback))
        return 0.0

    def _resolve_endpoint_hydraulic_pressure(
        self,
        *,
        edge: ConnectionEdge | None = None,
        edge_id: str,
        node_id: str,
        port_name: str,
        compiled_hydraulic: CompiledHydraulicGraph | None,
        hydraulic_result: HydraulicSolveResult,
    ) -> float | None:
        if compiled_hydraulic is None:
            return None
        endpoint_pressure = compiled_hydraulic.resolve_endpoint_pressure(
            endpoint_id=f"{node_id}.{port_name}",
            hydraulic_result=hydraulic_result,
        )
        if endpoint_pressure is not None and endpoint_pressure > 0.0:
            return endpoint_pressure

        line_source_pressure = compiled_hydraulic.resolve_line_source_pressure(
            line_id=edge_id,
            hydraulic_result=hydraulic_result,
        )
        line_target_pressure = compiled_hydraulic.resolve_line_target_pressure(
            line_id=edge_id,
            hydraulic_result=hydraulic_result,
        )
        if edge is not None:
            if edge.source.node_id == node_id and edge.source.port_name == port_name:
                if line_source_pressure is not None and line_source_pressure > 0.0:
                    return line_source_pressure
                if line_target_pressure is not None and line_target_pressure > 0.0:
                    return line_target_pressure
                return None
            if edge.target.node_id == node_id and edge.target.port_name == port_name:
                if line_target_pressure is not None and line_target_pressure > 0.0:
                    return line_target_pressure
                if line_source_pressure is not None and line_source_pressure > 0.0:
                    return line_source_pressure
                return None
        if line_target_pressure is not None and line_target_pressure > 0.0:
            return line_target_pressure
        if line_source_pressure is not None and line_source_pressure > 0.0:
            return line_source_pressure
        return None

    def _resolve_outgoing_junction_state(
        self,
        *,
        edge: ConnectionEdge,
        provider_node_id: str,
        provider_port_name: str,
        edge_by_id: Mapping[str, ConnectionEdge],
        compiled_hydraulic: CompiledHydraulicGraph | None,
        hydraulic_result: HydraulicSolveResult,
        junction_results: Mapping[str, JunctionMixingResult],
    ) -> MaterialState | None:
        provider_junction_result = junction_results.get(provider_node_id)
        if provider_junction_result is None:
            return None
        local_flow = self._classify_local_node_flow(
            edge=edge,
            local_node_id=provider_node_id,
            compiled_hydraulic=compiled_hydraulic,
            hydraulic_result=hydraulic_result,
        )
        if local_flow is None or local_flow >= 0.0:
            return None

        pressure = self._resolve_source_node_pressure(
            edge=edge,
            node_id=provider_node_id,
            port_name=provider_port_name,
            edge_by_id=edge_by_id,
            compiled_hydraulic=compiled_hydraulic,
            hydraulic_result=hydraulic_result,
        )
        if pressure is None:
            return provider_junction_result.state
        return MaterialState(
            pressure=pressure,
            temperature=provider_junction_result.state.temperature,
            mole_fractions=provider_junction_result.state.mole_fractions,
            species_ids=provider_junction_result.state.species_ids,
            phase=provider_junction_result.state.phase,
            enthalpy_molar=provider_junction_result.state.enthalpy_molar,
            entropy_molar=provider_junction_result.state.entropy_molar,
        )

    def _resolve_source_node_pressure(
        self,
        *,
        edge: ConnectionEdge,
        node_id: str,
        port_name: str,
        edge_by_id: Mapping[str, ConnectionEdge],
        compiled_hydraulic: CompiledHydraulicGraph | None,
        hydraulic_result: HydraulicSolveResult,
    ) -> float | None:
        if compiled_hydraulic is None:
            return None
        junction_pressure = compiled_hydraulic.resolve_junction_pressure(
            junction_id=node_id,
            hydraulic_result=hydraulic_result,
        )
        if junction_pressure is not None and junction_pressure > 0.0:
            return junction_pressure

        endpoint_id = f"{node_id}.{port_name}"
        endpoint_pressure = compiled_hydraulic.resolve_endpoint_pressure(
            endpoint_id=endpoint_id,
            hydraulic_result=hydraulic_result,
        )
        if endpoint_pressure is not None and endpoint_pressure > 0.0:
            return endpoint_pressure

        for candidate_edge in edge_by_id.values():
            if candidate_edge.source.node_id == node_id:
                pressure = compiled_hydraulic.resolve_line_source_pressure(
                    line_id=candidate_edge.edge_id,
                    hydraulic_result=hydraulic_result,
                )
                if pressure is not None and pressure > 0.0:
                    return pressure
            if candidate_edge.target.node_id == node_id:
                pressure = compiled_hydraulic.resolve_line_target_pressure(
                    line_id=candidate_edge.edge_id,
                    hydraulic_result=hydraulic_result,
                )
                if pressure is not None and pressure > 0.0:
                    return pressure
        return None

    def _classify_local_node_flow(
        self,
        *,
        edge: ConnectionEdge,
        local_node_id: str,
        compiled_hydraulic: CompiledHydraulicGraph | None,
        hydraulic_result: HydraulicSolveResult,
    ) -> float | None:
        solved_line_flow = self._resolve_hydraulic_flow(
            edge_id=edge.edge_id,
            compiled_hydraulic=compiled_hydraulic,
            hydraulic_result=hydraulic_result,
        )
        if solved_line_flow is None:
            return None
        if edge.target.node_id == local_node_id:
            return solved_line_flow
        if edge.source.node_id == local_node_id:
            return -solved_line_flow
        return None

    def _resolve_hydraulic_flow(
        self,
        *,
        edge_id: str,
        compiled_hydraulic: CompiledHydraulicGraph | None,
        hydraulic_result: HydraulicSolveResult,
    ) -> float | None:
        if compiled_hydraulic is not None:
            flow = compiled_hydraulic.resolve_line_flow(
                line_id=edge_id,
                hydraulic_result=hydraulic_result,
            )
            if flow is not None:
                return flow
        return None

    def _safe_get_outlet_payload(
        self,
        binding: object,
        outlet_port: str,
    ) -> Mapping[str, object] | None:
        getter = getattr(binding, "get_outlet", None)
        if not callable(getter):
            return None
        try:
            raw = getter(outlet_port)
        except BindingError:
            return None
        if isinstance(raw, Mapping):
            return cast(Mapping[str, object], raw)
        return None

    def _supports_outlet_payload(self, candidate: object | None) -> bool:
        return candidate is not None and callable(getattr(candidate, "get_outlet", None))

    def _resolve_binding_payload_outlet_condition(
        self,
        *,
        binding: object,
        port_name: str,
    ) -> PortCondition | None:
        outlet_payload = self._safe_get_outlet_payload(binding, port_name)
        if outlet_payload is None:
            return None

        raw_composition = outlet_payload.get("composition")
        if not isinstance(raw_composition, tuple) or not raw_composition:
            return None

        composition = tuple(float(item) for item in raw_composition)
        state_payload = outlet_payload.get("state")
        nested_state = state_payload if isinstance(state_payload, Mapping) else None

        temperature = self._float_from_payload(
            outlet_payload,
            "temperature",
            nested=nested_state,
            nested_key="temperature",
        )
        if temperature is None:
            temperature = self._config.default_temperature_k

        pressure = self._pressure_from_outlet_payload(outlet_payload)
        if pressure is None:
            pressure = self._config.default_pressure_pa

        phase = self._str_from_payload(
            outlet_payload,
            "phase",
            nested=nested_state,
            nested_key="phase",
        )

        return PortCondition(
            state=MaterialState(
                pressure=pressure,
                temperature=temperature,
                mole_fractions=composition,
                species_ids=None,
                phase=phase,
                enthalpy_molar=self._float_from_payload(
                    outlet_payload,
                    "enthalpy_molar",
                    nested=nested_state,
                    nested_key="enthalpy_molar",
                ),
                entropy_molar=self._float_from_payload(
                    outlet_payload,
                    "entropy_molar",
                    nested=nested_state,
                    nested_key="entropy_molar",
                ),
            ),
            species_ids=None,
            through_molar_flow_rate=self._flow_from_outlet_payload(outlet_payload),
            macro_step_time_s=None,
        )

    def _float_from_payload(
        self,
        payload: Mapping[str, object],
        key: str,
        *,
        nested: Mapping[str, object] | None = None,
        nested_key: str | None = None,
    ) -> float | None:
        value = payload.get(key)
        if isinstance(value, (float, int)) and isfinite(float(value)):
            return float(value)
        if nested is None or nested_key is None:
            return None
        nested_value = nested.get(nested_key)
        if isinstance(nested_value, (float, int)) and isfinite(float(nested_value)):
            return float(nested_value)
        return None

    def _str_from_payload(
        self,
        payload: Mapping[str, object],
        key: str,
        *,
        nested: Mapping[str, object] | None = None,
        nested_key: str | None = None,
    ) -> str | None:
        value = payload.get(key)
        if isinstance(value, str):
            return value
        if nested is None or nested_key is None:
            return None
        nested_value = nested.get(nested_key)
        if isinstance(nested_value, str):
            return nested_value
        return None

    def _flow_from_outlet_payload(self, outlet_payload: Mapping[str, object]) -> float:
        fallback = outlet_payload.get("outlet_flow")
        if isinstance(fallback, (float, int)) and isfinite(float(fallback)):
            return float(fallback)
        fallback = outlet_payload.get("flow")
        if isinstance(fallback, (float, int)) and isfinite(float(fallback)):
            return abs(float(fallback))
        return 0.0

    def _resolve_manual_overrides(
        self,
        auto_conditions: Mapping[str, PortCondition],
    ) -> dict[str, PortCondition]:
        resolved: dict[str, PortCondition] = {}
        if self._config.manual_port_conditions is not None:
            resolved.update(self._config.manual_port_conditions)

        hook = self._config.manual_override_hook
        if hook is not None:
            resolved.update(hook(dict(auto_conditions)))
        return resolved


__all__ = [
    "ThermoBoundaryPropagationConfig",
    "ThermoBoundaryPropagationStep",
]

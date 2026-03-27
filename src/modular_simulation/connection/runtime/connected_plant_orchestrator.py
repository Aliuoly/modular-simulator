from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from numbers import Real
from typing import TYPE_CHECKING, Protocol, TypeAlias, cast

from ..topology.network import (
    ConnectionNetwork,
    QueuedReconfigurationTransaction,
)
from ..topology.subsystem_descriptor import SubsystemRuntimeDescriptor
from .runtime import (
    CONNECTED_PLANT_PHASE_ORDER,
    ConnectionRuntimeOrchestrator,
    ConnectionRuntimeStepResult,
)
from modular_simulation.validation.exceptions import MeasurableConfigurationError

if TYPE_CHECKING:
    from modular_simulation.thermodynamics.runtime_context import SimulationRuntimeContext


PlantCalculationEvaluator: TypeAlias = Callable[[Mapping[str, float]], Mapping[str, float]]


class SubsystemPhaseRuntime(Protocol):
    @property
    def descriptor(self) -> SubsystemRuntimeDescriptor: ...

    def run_sensor_phase(self) -> None: ...

    def run_calculation_phase(self) -> None: ...

    def run_controller_phase(self) -> None: ...

    def run_process_phase(self, duration: float) -> None: ...


class _ProcessStateProjectionProvider(Protocol):
    def snapshot_process_state_values(self) -> Mapping[str, float]: ...


@dataclass(frozen=True)
class ConnectedPlantInitializationResult:
    graph_revision: str | None
    subsystem_ids: tuple[str, ...]
    process_ids: tuple[str, ...]


@dataclass(frozen=True)
class ConnectedPlantStepResult:
    macro_step_index: int
    simulation_time_s: float
    graph_revision: str | None
    phase_order: tuple[str, ...]
    runtime_step_result: ConnectionRuntimeStepResult


@dataclass(frozen=True)
class ConnectedPlantPhaseHooks:
    subsystem_sensor_update: Callable[[int, float], None] | None = None
    subsystem_calculation_update: Callable[[int, float], None] | None = None
    plant_calculation_update: Callable[[int, float], None] | None = None
    subsystem_controller_update: Callable[[int, float], None] | None = None
    subsystem_process_step: Callable[[int, float], None] | None = None
    connection_runtime_coupling: Callable[[int, float], None] | None = None


@dataclass(frozen=True)
class _PlantCalculationDefinition:
    calculation_id: str
    input_tags: tuple[str, ...]
    output_tags: tuple[str, ...]
    evaluate: PlantCalculationEvaluator


class ConnectedPlantOrchestrator:
    def __init__(
        self,
        *,
        subsystems: Sequence[SubsystemPhaseRuntime],
        network: ConnectionNetwork,
        runtime_orchestrator: ConnectionRuntimeOrchestrator,
        phase_hooks: ConnectedPlantPhaseHooks | None = None,
        runtime_context: SimulationRuntimeContext | None = None,
    ) -> None:
        self._subsystems: tuple[SubsystemPhaseRuntime, ...] = tuple(subsystems)
        self._network: ConnectionNetwork = network
        self._runtime_orchestrator: ConnectionRuntimeOrchestrator = runtime_orchestrator
        self._runtime_context: SimulationRuntimeContext | None = (
            runtime_context
            if runtime_context is not None
            else self._runtime_orchestrator.runtime_context
        )
        self._runtime_orchestrator.set_runtime_context(self._runtime_context)
        self._runtime_orchestrator.set_observability_provider(self)
        self._phase_hooks: ConnectedPlantPhaseHooks = (
            phase_hooks if phase_hooks is not None else ConnectedPlantPhaseHooks()
        )
        self._plant_calculations: tuple[_PlantCalculationDefinition, ...] = ()
        self._plant_calculation_outputs: dict[str, float] = {}
        self._initialized: bool = False
        self._macro_step_active: bool = False

    @property
    def initialized(self) -> bool:
        return self._initialized

    @property
    def macro_step_active(self) -> bool:
        return self._macro_step_active

    @property
    def subsystems(self) -> tuple[SubsystemPhaseRuntime, ...]:
        return self._subsystems

    @property
    def plant_calculation_outputs(self) -> Mapping[str, float]:
        return dict(self._plant_calculation_outputs)

    def get_observability_observables(self) -> Mapping[str, Mapping[str, float]]:
        return {
            "published_measurements": self._snapshot_published_measurement_map(),
            "plant_calculation_outputs": dict(self._plant_calculation_outputs),
            "process_state_values": self._snapshot_process_state_values(),
        }

    def _snapshot_process_state_values(self) -> dict[str, float]:
        process_state_values: dict[str, float] = {}
        for subsystem in self._subsystems:
            snapshotter = getattr(subsystem, "snapshot_process_state_values", None)
            if snapshotter is None:
                continue
            snapshot = cast(
                _ProcessStateProjectionProvider, subsystem
            ).snapshot_process_state_values()
            process_state_values.update(dict(snapshot))
        return process_state_values

    @property
    def runtime_context(self) -> SimulationRuntimeContext | None:
        return self._runtime_context

    @property
    def runtime_orchestrator(self) -> ConnectionRuntimeOrchestrator:
        return self._runtime_orchestrator

    def add_calculation(
        self,
        *,
        calculation_id: str,
        input_tags: Sequence[str],
        output_tags: Sequence[str],
        evaluate: PlantCalculationEvaluator,
    ) -> None:
        if self._macro_step_active:
            raise RuntimeError("cannot install plant calculations during an active macro-step")

        normalized_calculation_id = calculation_id.strip()
        if not normalized_calculation_id:
            raise ValueError("plant calculation id must be a non-empty string")

        existing_ids = {calculation.calculation_id for calculation in self._plant_calculations}
        if normalized_calculation_id in existing_ids:
            raise ValueError(
                f"plant calculation '{normalized_calculation_id}' is already registered"
            )

        normalized_inputs = self._normalize_tag_sequence(input_tags, field_name="input_tags")
        normalized_outputs = self._normalize_tag_sequence(output_tags, field_name="output_tags")

        if len(set(normalized_outputs)) != len(normalized_outputs):
            raise ValueError(
                f"plant calculation '{normalized_calculation_id}' output tags must be unique"
            )

        published_tags = set(self._snapshot_published_measurement_map().keys())
        existing_output_tags = {
            tag for definition in self._plant_calculations for tag in definition.output_tags
        }
        for output_tag in normalized_outputs:
            if output_tag in published_tags:
                raise ValueError(
                    f"plant calculation '{normalized_calculation_id}' output tag '{output_tag}' "
                    + "collides with a published subsystem measurement"
                )
            if output_tag in existing_output_tags:
                raise ValueError(
                    f"plant calculation '{normalized_calculation_id}' output tag '{output_tag}' "
                    + "collides with an existing plant calculation output"
                )

        self._plant_calculations = (
            *self._plant_calculations,
            _PlantCalculationDefinition(
                calculation_id=normalized_calculation_id,
                input_tags=normalized_inputs,
                output_tags=normalized_outputs,
                evaluate=evaluate,
            ),
        )

    def initialize(self) -> ConnectedPlantInitializationResult:
        compiled = self._network.compiled
        if compiled is None:
            compiled = self._network.compile()

        process_topology = {
            node.process_id: (tuple(node.inlet_ports), tuple(node.outlet_ports))
            for node in compiled.topology.process_nodes
        }

        descriptor_ids: list[str] = []
        process_ids: list[str] = []
        for subsystem in self._subsystems:
            descriptor = subsystem.descriptor
            descriptor_ids.append(descriptor.descriptor_id)
            process_ids.append(descriptor.process_id)

            process_ports = process_topology.get(descriptor.process_id)
            if process_ports is None:
                raise ValueError(
                    f"subsystem '{descriptor.descriptor_id}' references unknown process "
                    + f"'{descriptor.process_id}'"
                )
            if process_ports[0] != descriptor.inlet_ports:
                raise ValueError(
                    f"subsystem '{descriptor.descriptor_id}' inlet ports {descriptor.inlet_ports!r} "
                    + f"do not match process '{descriptor.process_id}' inlet ports {process_ports[0]!r}"
                )
            if process_ports[1] != descriptor.outlet_ports:
                raise ValueError(
                    f"subsystem '{descriptor.descriptor_id}' outlet ports {descriptor.outlet_ports!r} "
                    + f"do not match process '{descriptor.process_id}' outlet ports {process_ports[1]!r}"
                )

        if len(set(descriptor_ids)) != len(descriptor_ids):
            raise ValueError("subsystem descriptor ids must be unique")
        if len(set(process_ids)) != len(process_ids):
            raise ValueError("subsystem process ids must be unique")

        self._initialized = True
        return ConnectedPlantInitializationResult(
            graph_revision=compiled.graph_revision,
            subsystem_ids=tuple(descriptor_ids),
            process_ids=tuple(process_ids),
        )

    def step(self, *, macro_step_time_s: float) -> ConnectedPlantStepResult:
        if not self._initialized:
            _ = self.initialize()
        if self._macro_step_active:
            raise RuntimeError("connected-plant macro-step is already active")

        macro_step_index = self._runtime_orchestrator.macro_step_index + 1
        simulation_time_s = self._runtime_orchestrator.simulation_time_s + macro_step_time_s
        queue_snapshot = self._network.queued_reconfigurations

        self._macro_step_active = True
        try:
            self._run_phase(
                phase_name="subsystem_sensor_update",
                macro_step_index=macro_step_index,
                simulation_time_s=simulation_time_s,
                phase_step=lambda subsystem: subsystem.run_sensor_phase(),
            )
            self._run_phase(
                phase_name="subsystem_calculation_update",
                macro_step_index=macro_step_index,
                simulation_time_s=simulation_time_s,
                phase_step=lambda subsystem: subsystem.run_calculation_phase(),
            )
            self._run_phase(
                phase_name="plant_calculation_update",
                macro_step_index=macro_step_index,
                simulation_time_s=simulation_time_s,
                phase_step=None,
            )
            self._run_plant_calculations()
            self._run_phase(
                phase_name="subsystem_controller_update",
                macro_step_index=macro_step_index,
                simulation_time_s=simulation_time_s,
                phase_step=lambda subsystem: subsystem.run_controller_phase(),
            )
            self._run_phase(
                phase_name="subsystem_process_step",
                macro_step_index=macro_step_index,
                simulation_time_s=simulation_time_s,
                phase_step=lambda subsystem: subsystem.run_process_phase(macro_step_time_s),
            )

            self._run_phase_hook(
                phase_name="connection_runtime_coupling",
                macro_step_index=macro_step_index,
                simulation_time_s=simulation_time_s,
            )
            queued_for_current_barrier, deferred_until_next_barrier = self._split_queue_by_snapshot(
                queue_snapshot=queue_snapshot,
                queued_now=self._network.queued_reconfigurations,
            )
            self._network.replace_queued_reconfigurations(queued_for_current_barrier)
            try:
                runtime_step_result = self._runtime_orchestrator.step(
                    network=self._network,
                    macro_step_time_s=macro_step_time_s,
                )
            finally:
                if deferred_until_next_barrier:
                    post_step_queue = self._network.queued_reconfigurations
                    self._network.replace_queued_reconfigurations(
                        self._merge_fifo_queue(
                            post_step_queue=post_step_queue,
                            deferred_until_next_barrier=deferred_until_next_barrier,
                        )
                    )
        finally:
            self._macro_step_active = False

        return ConnectedPlantStepResult(
            macro_step_index=runtime_step_result.macro_step_index,
            simulation_time_s=runtime_step_result.simulation_time_s,
            graph_revision=runtime_step_result.graph_revision,
            phase_order=CONNECTED_PLANT_PHASE_ORDER,
            runtime_step_result=runtime_step_result,
        )

    def _run_phase(
        self,
        *,
        phase_name: str,
        macro_step_index: int,
        simulation_time_s: float,
        phase_step: Callable[[SubsystemPhaseRuntime], None] | None,
    ) -> None:
        self._run_phase_hook(
            phase_name=phase_name,
            macro_step_index=macro_step_index,
            simulation_time_s=simulation_time_s,
        )
        if phase_step is None:
            return
        for subsystem in self._subsystems:
            phase_step(subsystem)

    def _run_plant_calculations(self) -> None:
        if not self._plant_calculations:
            self._plant_calculation_outputs = {}
            return

        published_measurements = self._snapshot_published_measurement_map()
        resolution_order = self._resolve_plant_calculation_order(
            published_tag_set=set(published_measurements.keys())
        )

        available_inputs: dict[str, float] = dict(published_measurements)
        next_outputs: dict[str, float] = {}
        for calculation_index in resolution_order:
            calculation = self._plant_calculations[calculation_index]
            calculation_inputs = {tag: available_inputs[tag] for tag in calculation.input_tags}
            calculated_outputs = calculation.evaluate(calculation_inputs)
            self._validate_calculation_outputs(
                calculation=calculation,
                calculated_outputs=calculated_outputs,
            )
            for output_tag in calculation.output_tags:
                output_value = calculated_outputs[output_tag]
                next_outputs[output_tag] = output_value
                available_inputs[output_tag] = output_value

        self._plant_calculation_outputs = next_outputs

    def _resolve_plant_calculation_order(self, *, published_tag_set: set[str]) -> tuple[int, ...]:
        pending_indices = list(range(len(self._plant_calculations)))
        resolved_indices: list[int] = []
        available_tags = set(published_tag_set)
        max_attempts = len(self._plant_calculations)
        attempts = 0

        while pending_indices and attempts < max_attempts:
            attempts += 1
            did_resolve_in_attempt = False

            for index in tuple(pending_indices):
                calculation = self._plant_calculations[index]
                missing_inputs = [
                    input_tag
                    for input_tag in calculation.input_tags
                    if input_tag not in available_tags
                ]
                if missing_inputs:
                    continue

                pending_indices.remove(index)
                resolved_indices.append(index)
                available_tags.update(calculation.output_tags)
                did_resolve_in_attempt = True

            if not did_resolve_in_attempt:
                break

        if pending_indices:
            errors: list[Exception] = []
            sorted_available_tags = ", ".join(sorted(available_tags))
            for index in pending_indices:
                calculation = self._plant_calculations[index]
                missing_inputs = sorted(
                    {
                        input_tag
                        for input_tag in calculation.input_tags
                        if input_tag not in available_tags
                    }
                )
                errors.append(
                    ValueError(
                        f"plant calculation '{calculation.calculation_id}' could not be resolved; "
                        + f"missing inputs: {', '.join(missing_inputs)}; "
                        + f"available tags: {sorted_available_tags}"
                    )
                )

            raise ExceptionGroup(
                f"{len(pending_indices)} out of {len(self._plant_calculations)} "
                + "plant calculation(s) could not be resolved:",
                errors,
            )

        return tuple(resolved_indices)

    def _snapshot_published_measurement_map(self) -> dict[str, float]:
        published_measurements: dict[str, float] = {}
        tag_owner_map: dict[str, str] = {}
        published_tag_owner_map: dict[str, str] = {}
        for subsystem in self._subsystems:
            descriptor = subsystem.descriptor
            raw_publications = self._snapshot_subsystem_publications(subsystem)
            for raw_tag, value in raw_publications.items():
                tag = self._normalize_publication_tag(
                    descriptor_id=descriptor.descriptor_id,
                    raw_tag=raw_tag,
                )
                existing_owner = tag_owner_map.get(tag)
                if existing_owner is not None and existing_owner != descriptor.descriptor_id:
                    raise ValueError(
                        f"published measurement tag '{tag}' is defined by both subsystem "
                        + f"'{existing_owner}' and subsystem '{descriptor.descriptor_id}'"
                    )

                namespace, published_tag = tag.split("/", 1)
                existing_published_tag_owner = published_tag_owner_map.get(published_tag)
                if (
                    existing_published_tag_owner is not None
                    and existing_published_tag_owner != namespace
                ):
                    raise MeasurableConfigurationError(
                        f"Published measurement tag collision for '{published_tag}': "
                        + f"already registered by subsystem '{existing_published_tag_owner}', "
                        + f"cannot register for subsystem '{namespace}'."
                    )

                published_tag_owner_map[published_tag] = namespace
                tag_owner_map[tag] = descriptor.descriptor_id
                published_measurements[tag] = value

        return published_measurements

    def _snapshot_subsystem_publications(
        self, subsystem: SubsystemPhaseRuntime
    ) -> Mapping[str, float]:
        publication_snapshotter = getattr(subsystem, "snapshot_published_measurements", None)
        if publication_snapshotter is None:
            return subsystem.descriptor.publication_map

        snapshot_object = cast(Callable[[], object], publication_snapshotter)()
        if not isinstance(snapshot_object, Mapping):
            raise ValueError(
                f"subsystem '{subsystem.descriptor.descriptor_id}' publication snapshot must be a mapping"
            )

        snapshot: dict[str, float] = {}
        for raw_tag, raw_value in cast(Mapping[object, object], snapshot_object).items():
            if not isinstance(raw_tag, str) or not raw_tag.strip():
                raise ValueError(
                    f"subsystem '{subsystem.descriptor.descriptor_id}' publication snapshot keys "
                    + "must be non-empty strings"
                )
            if not isinstance(raw_value, Real):
                raise ValueError(
                    f"subsystem '{subsystem.descriptor.descriptor_id}' publication snapshot value "
                    + f"for tag '{raw_tag}' must be numeric"
                )
            snapshot[raw_tag] = float(raw_value)
        return snapshot

    def _normalize_publication_tag(self, *, descriptor_id: str, raw_tag: str) -> str:
        normalized_tag = raw_tag.strip()
        if not normalized_tag:
            raise ValueError("published measurement tags must be non-empty strings")

        if "/" not in normalized_tag:
            return f"{descriptor_id}/{normalized_tag}"

        namespace, output_tag = normalized_tag.split("/", 1)
        namespace = namespace.strip()
        output_tag = output_tag.strip()
        if not namespace or not output_tag:
            raise ValueError(
                f"published measurement tag '{raw_tag}' must resolve to '<subsystem>/<published_tag>'"
            )
        if "/" in namespace or "/" in output_tag:
            raise ValueError(
                f"published measurement tag '{raw_tag}' must resolve to '<subsystem>/<published_tag>'"
            )
        return f"{namespace}/{output_tag}"

    def _validate_calculation_outputs(
        self,
        *,
        calculation: _PlantCalculationDefinition,
        calculated_outputs: Mapping[str, float],
    ) -> None:
        expected_tags = set(calculation.output_tags)
        actual_tags = set(calculated_outputs.keys())
        if actual_tags != expected_tags:
            missing_tags = sorted(expected_tags - actual_tags)
            unexpected_tags = sorted(actual_tags - expected_tags)
            details: list[str] = []
            if missing_tags:
                details.append(f"missing outputs: {', '.join(missing_tags)}")
            if unexpected_tags:
                details.append(f"unexpected outputs: {', '.join(unexpected_tags)}")
            raise ValueError(
                f"plant calculation '{calculation.calculation_id}' returned an invalid output map; "
                + "; ".join(details)
            )
        for output_tag in calculation.output_tags:
            output_value = calculated_outputs[output_tag]
            if not isinstance(output_value, Real):
                raise ValueError(
                    f"plant calculation '{calculation.calculation_id}' output '{output_tag}' must be numeric"
                )

    def _normalize_tag_sequence(self, tags: Sequence[str], *, field_name: str) -> tuple[str, ...]:
        normalized_tags = tuple(tag.strip() for tag in tags)
        if not normalized_tags:
            raise ValueError(f"{field_name} must contain at least one tag")
        if any(not tag for tag in normalized_tags):
            raise ValueError(f"{field_name} must not contain empty tags")
        return normalized_tags

    def _run_phase_hook(
        self, *, phase_name: str, macro_step_index: int, simulation_time_s: float
    ) -> None:
        phase_hook_map: Mapping[str, Callable[[int, float], None] | None] = {
            "subsystem_sensor_update": self._phase_hooks.subsystem_sensor_update,
            "subsystem_calculation_update": self._phase_hooks.subsystem_calculation_update,
            "plant_calculation_update": self._phase_hooks.plant_calculation_update,
            "subsystem_controller_update": self._phase_hooks.subsystem_controller_update,
            "subsystem_process_step": self._phase_hooks.subsystem_process_step,
            "connection_runtime_coupling": self._phase_hooks.connection_runtime_coupling,
        }
        hook = phase_hook_map.get(phase_name)
        if hook is not None:
            hook(macro_step_index, simulation_time_s)

    def _split_queue_by_snapshot(
        self,
        *,
        queue_snapshot: Sequence[QueuedReconfigurationTransaction],
        queued_now: Sequence[QueuedReconfigurationTransaction],
    ) -> tuple[
        tuple[QueuedReconfigurationTransaction, ...], tuple[QueuedReconfigurationTransaction, ...]
    ]:
        snapshot_ids = {item.request_id for item in queue_snapshot}
        current_barrier: list[QueuedReconfigurationTransaction] = []
        deferred: list[QueuedReconfigurationTransaction] = []
        for queued in queued_now:
            if queued.request_id in snapshot_ids:
                current_barrier.append(queued)
                continue
            deferred.append(queued)
        return tuple(current_barrier), tuple(deferred)

    def _merge_fifo_queue(
        self,
        *,
        post_step_queue: Sequence[QueuedReconfigurationTransaction],
        deferred_until_next_barrier: Sequence[QueuedReconfigurationTransaction],
    ) -> tuple[QueuedReconfigurationTransaction, ...]:
        merged = (*post_step_queue, *deferred_until_next_barrier)
        return tuple(sorted(merged, key=self._queue_request_fifo_key))

    def _queue_request_fifo_key(self, queued: QueuedReconfigurationTransaction) -> tuple[int, str]:
        request_id = queued.request_id
        prefix, _, counter_text = request_id.partition("_")
        if prefix == "rq" and counter_text.isdigit():
            return int(counter_text), request_id
        return (2**31 - 1, request_id)


__all__ = [
    "ConnectedPlantInitializationResult",
    "ConnectedPlantOrchestrator",
    "ConnectedPlantPhaseHooks",
    "ConnectedPlantStepResult",
    "SubsystemPhaseRuntime",
]

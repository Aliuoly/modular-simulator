from __future__ import annotations

# pyright: reportMissingTypeStubs=false

from collections.abc import Mapping
from numbers import Real
from typing import TYPE_CHECKING

import numpy as np

from .subsystem_descriptor import (
    Subsystem,
    SubsystemRuntimeDescriptor,
)
from modular_simulation.framework.system import System
from modular_simulation.measurables.process_model import ProcessModel, StateType
from modular_simulation.thermodynamics.algebraic_process_model import UnitProcessPorts

if TYPE_CHECKING:
    from modular_simulation.thermodynamics.runtime_context import SimulationRuntimeContext


def create_system_for_unit(unit: ProcessModel, dt: float) -> System:
    return System(
        dt=float(dt),
        process_model=unit,
        sensors=(),
        calculations=(),
        control_elements=(),
    )


def create_subsystem_for_unit(
    unit: ProcessModel,
    unit_id: str,
    dt: float,
    runtime_context: SimulationRuntimeContext | None = None,
) -> Subsystem:
    _inject_property_package_if_available(unit=unit, runtime_context=runtime_context)
    inlet_ports, outlet_ports = _ports_for_unit(unit)

    descriptor = SubsystemRuntimeDescriptor(
        descriptor_id=unit_id,
        process_id=unit_id,
        inlet_ports=inlet_ports,
        outlet_ports=outlet_ports,
        publication_map=_derive_publication_map(unit),
        runtime_context=_derive_descriptor_runtime_context(
            unit_id=unit_id,
            inlet_ports=inlet_ports,
            outlet_ports=outlet_ports,
            runtime_context=runtime_context,
        ),
    )
    system = create_system_for_unit(unit=unit, dt=dt)
    subsystem = Subsystem(descriptor=descriptor, system=system)
    _bind_process_state_projection(
        subsystem=subsystem,
        unit=unit,
        unit_id=unit_id,
        runtime_context=runtime_context,
    )
    _stabilize_publication_adapter_for_non_scalar_states(
        subsystem=subsystem,
        unit=unit,
        unit_id=unit_id,
    )
    return subsystem


def _ports_for_unit(unit: ProcessModel) -> tuple[tuple[str, ...], tuple[str, ...]]:
    ports = getattr(unit, "ports", None)
    if not isinstance(ports, UnitProcessPorts):
        raise ValueError(f"{type(unit).__name__} does not expose a 'ports' declaration")

    inlet_ports = tuple(ports.inlets)
    outlet_ports = tuple(ports.outlets)
    if not inlet_ports or not outlet_ports:
        raise ValueError(
            f"{type(unit).__name__} must declare at least one inlet and one outlet port"
        )
    return inlet_ports, outlet_ports


def _derive_publication_map(unit: ProcessModel) -> dict[str, float]:
    publication_map: dict[str, float] = {}
    for state_name, metadata in unit.state_metadata_dict.items():
        if metadata.type not in {StateType.ALGEBRAIC, StateType.DIFFERENTIAL}:
            continue
        publication_map[state_name] = _default_publication_value(unit=unit, state_name=state_name)
    return publication_map


def _default_publication_value(unit: ProcessModel, state_name: str) -> float:
    value = unit.state_getter(state_name)
    if isinstance(value, Real):
        return float(value)
    return 0.0


def _derive_descriptor_runtime_context(
    *,
    unit_id: str,
    inlet_ports: tuple[str, ...],
    outlet_ports: tuple[str, ...],
    runtime_context: SimulationRuntimeContext | None,
) -> Mapping[str, object]:
    descriptor_fields: dict[str, str] = {}
    for port_name in inlet_ports:
        descriptor_fields[f"inlet_{port_name}"] = f"unit_{unit_id}_inlet_{port_name}"
    for port_name in outlet_ports:
        descriptor_fields[f"outlet_{port_name}"] = f"unit_{unit_id}_outlet_{port_name}"

    context_payload: dict[str, object] = {
        "descriptor_fields": descriptor_fields,
        "unit_id": unit_id,
    }
    if runtime_context is not None:
        context_payload["simulation_runtime_context"] = runtime_context
    return context_payload


def _inject_property_package_if_available(
    *,
    unit: ProcessModel,
    runtime_context: SimulationRuntimeContext | None,
) -> None:
    if runtime_context is None:
        return

    setter = getattr(unit, "set_property_package", None)
    if not callable(setter):
        return
    _ = setter(runtime_context.get_property_package())


def _bind_process_state_projection(
    *,
    subsystem: Subsystem,
    unit: ProcessModel,
    unit_id: str,
    runtime_context: SimulationRuntimeContext | None,
) -> None:
    def _snapshot_process_state_values() -> dict[str, float]:
        unit_type_name = type(unit).__name__
        if unit_type_name == "StagewiseDistillationColumn":
            return _snapshot_stagewise_distillation_state_values(
                unit=unit,
                unit_id=unit_id,
                runtime_context=runtime_context,
            )
        return {}

    setattr(subsystem, "snapshot_process_state_values", _snapshot_process_state_values)


def _stabilize_publication_adapter_for_non_scalar_states(
    *,
    subsystem: Subsystem,
    unit: ProcessModel,
    unit_id: str,
) -> None:
    publication_getter_by_tag = getattr(subsystem, "_publication_getter_by_tag", None)
    if not isinstance(publication_getter_by_tag, dict):
        return

    for state_name, metadata in unit.state_metadata_dict.items():
        if metadata.type not in {StateType.ALGEBRAIC, StateType.DIFFERENTIAL}:
            continue
        if isinstance(unit.state_getter(state_name), Real):
            continue

        registration_tag = f"{unit_id}/{state_name}"
        if registration_tag not in publication_getter_by_tag:
            continue

        default_value = _default_publication_value(unit=unit, state_name=state_name)

        def _fallback_publication_getter(value: float = default_value) -> float:
            return float(value)

        publication_getter_by_tag[registration_tag] = _fallback_publication_getter


def _snapshot_stagewise_distillation_state_values(
    *,
    unit: ProcessModel,
    unit_id: str,
    runtime_context: SimulationRuntimeContext | None,
) -> dict[str, float]:
    stage_moles = np.asarray(getattr(unit, "stage_component_moles"), dtype=np.float64).reshape(-1)
    reflux_drum_moles = np.asarray(
        getattr(unit, "reflux_drum_component_moles"), dtype=np.float64
    ).reshape(-1)
    bottoms_sump_moles = np.asarray(
        getattr(unit, "bottoms_sump_component_moles"), dtype=np.float64
    ).reshape(-1)
    feed_flows = np.asarray(getattr(unit, "feed_flows"), dtype=np.float64).reshape(-1)
    feed_temperatures = np.asarray(getattr(unit, "feed_temperatures"), dtype=np.float64).reshape(-1)
    feed_pressures = np.asarray(getattr(unit, "feed_pressures"), dtype=np.float64).reshape(-1)
    feed_compositions = np.asarray(getattr(unit, "feed_compositions"), dtype=np.float64).reshape(-1)
    feed_stage_indices = np.asarray(getattr(unit, "feed_stage_indices"), dtype=np.float64).reshape(
        -1
    )
    distillate_composition = np.asarray(
        getattr(unit, "distillate_composition"), dtype=np.float64
    ).reshape(-1)
    bottoms_composition = np.asarray(
        getattr(unit, "bottoms_composition"), dtype=np.float64
    ).reshape(-1)

    n_species = int(getattr(unit, "n_species"))
    n_stages = int(getattr(unit, "n_stages"))
    n_feeds = int(getattr(unit, "n_feeds"))
    stage_matrix = stage_moles.reshape(n_stages, n_species)
    feed_matrix = feed_compositions.reshape(n_feeds, n_species)

    scalar_projection: dict[str, float] = {
        f"{unit_id}/column_pressure_pa": float(getattr(unit, "column_pressure_pa")),
        f"{unit_id}/active_contact_height_m": float(getattr(unit, "active_contact_height_m")),
        f"{unit_id}/shell_diameter_m": float(getattr(unit, "shell_diameter_m")),
        f"{unit_id}/distillate_flow_mol_s": float(getattr(unit, "distillate_flow")),
        f"{unit_id}/bottoms_flow_mol_s": float(getattr(unit, "bottoms_flow")),
        f"{unit_id}/reflux_return_flow_mol_s": float(getattr(unit, "reflux_return_flow")),
        f"{unit_id}/distillate_withdrawal_flow_mol_s": float(
            getattr(unit, "distillate_withdrawal_flow")
        ),
        f"{unit_id}/bottoms_withdrawal_flow_mol_s": float(getattr(unit, "bottoms_withdrawal_flow")),
        f"{unit_id}/reflux_outlet_flow_mol_s": float(getattr(unit, "reflux_outlet_flow")),
        f"{unit_id}/condenser_duty_W": float(getattr(unit, "condenser_duty_W")),
        f"{unit_id}/reboiler_duty_W": float(getattr(unit, "reboiler_duty_W")),
        f"{unit_id}/condenser_duty_request_W": float(getattr(unit, "condenser_duty_request_W")),
        f"{unit_id}/reboiler_duty_request_W": float(getattr(unit, "reboiler_duty_request_W")),
        f"{unit_id}/realized_condensed_flow_mol_s": float(
            getattr(unit, "realized_condensed_flow_mol_s")
        ),
        f"{unit_id}/realized_reboiler_boilup_flow_mol_s": float(
            getattr(unit, "realized_reboiler_boilup_flow_mol_s")
        ),
        f"{unit_id}/reflux_drum_holdup_mol": float(np.sum(reflux_drum_moles)),
        f"{unit_id}/bottoms_sump_holdup_mol": float(np.sum(bottoms_sump_moles)),
    }

    if runtime_context is not None:
        cas_ids = tuple(runtime_context.species_registry.cas_list)
    else:
        cas_ids = tuple(str(index) for index in range(n_species))

    for species_index, cas_id in enumerate(cas_ids[:n_species]):
        scalar_projection[f"{unit_id}/distillate_mole_fraction/{cas_id}"] = float(
            distillate_composition[species_index]
        )
        scalar_projection[f"{unit_id}/bottoms_mole_fraction/{cas_id}"] = float(
            bottoms_composition[species_index]
        )
        scalar_projection[f"{unit_id}/reflux_drum_component_moles/{cas_id}"] = float(
            reflux_drum_moles[species_index]
        )
        scalar_projection[f"{unit_id}/bottoms_sump_component_moles/{cas_id}"] = float(
            bottoms_sump_moles[species_index]
        )

    selected_stage_indices: set[int] = {0, max(0, n_stages - 1)}
    for feed_stage_index in feed_stage_indices:
        selected_stage_indices.add(
            int(np.clip(round(float(feed_stage_index)) - 1, 0, n_stages - 1))
        )

    for stage_index_zero_based in sorted(selected_stage_indices):
        stage_label = stage_index_zero_based + 1
        stage_inventory = np.clip(stage_matrix[stage_index_zero_based], 0.0, None)
        stage_total = float(np.sum(stage_inventory))
        if stage_total <= 0.0:
            stage_x = np.full(n_species, 1.0 / float(n_species), dtype=np.float64)
        else:
            stage_x = stage_inventory / stage_total
        for species_index, cas_id in enumerate(cas_ids[:n_species]):
            scalar_projection[f"{unit_id}/stage_{stage_label}/mole_fraction/{cas_id}"] = float(
                stage_x[species_index]
            )

    for feed_index in range(n_feeds):
        feed_label = feed_index + 1
        scalar_projection[f"{unit_id}/feed_{feed_label}/flow_mol_s"] = float(feed_flows[feed_index])
        scalar_projection[f"{unit_id}/feed_{feed_label}/temperature_K"] = float(
            feed_temperatures[feed_index]
        )
        scalar_projection[f"{unit_id}/feed_{feed_label}/pressure_pa"] = float(
            feed_pressures[feed_index]
        )
        scalar_projection[f"{unit_id}/feed_{feed_label}/stage_index"] = float(
            feed_stage_indices[feed_index]
        )
        for species_index, cas_id in enumerate(cas_ids[:n_species]):
            scalar_projection[f"{unit_id}/feed_{feed_label}/mole_fraction/{cas_id}"] = float(
                feed_matrix[feed_index, species_index]
            )

    return scalar_projection


__all__ = ["create_subsystem_for_unit", "create_system_for_unit"]

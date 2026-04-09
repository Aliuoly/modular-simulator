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
import modular_simulation.thermodynamics.property_package as pp

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
    if type(unit).__name__ == "HoldingTank":
        # Holding-tank physical reads are exposed via observability
        # process_state_values, not published_measurements.
        return {}

    publication_map: dict[str, float] = {}
    for state_name, metadata in unit.state_metadata_dict.items():
        if metadata.type not in {StateType.ALGEBRAIC, StateType.DIFFERENTIAL}:
            continue
        value = unit.state_getter(state_name)
        if not isinstance(value, (int, float)):
            # Skip non-scalar states (e.g. ndarray composition vectors).
            # Array-shaped states are surfaced via process_state_values, not
            # published_measurements, so omitting them here is correct and
            # prevents float(ndarray) TypeError after species-dimension widening.
            continue
        publication_map[state_name] = float(value)
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
        if unit_type_name in {
            "ThermoTrayDistillationColumn",
            "ThermoTrayDistillationColumnTotalCondenser",
        }:
            return _snapshot_thermo_tray_distillation_state_values(
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

    liquid_cp_j_per_mol_k = 120.0
    reference_temperature_k = 298.15
    shell_diameter_m = max(1.0e-9, float(getattr(unit, "shell_diameter_m")))
    area_m2 = np.pi * 0.25 * shell_diameter_m * shell_diameter_m
    vapor_space_height_m = max(0.15, 0.2 * float(getattr(unit, "tray_spacing_m")))
    vapor_volume_m3 = max(1.0e-4, area_m2 * vapor_space_height_m)
    r_gas_j_per_mol_k = 8.314462618

    min_sum = 1.0e-12
    drum_total_moles = max(min_sum, float(np.sum(np.clip(reflux_drum_moles, 0.0, None))))
    sump_total_moles = max(min_sum, float(np.sum(np.clip(bottoms_sump_moles, 0.0, None))))
    drum_temperature_k = float(
        np.clip(
            reference_temperature_k
            + float(getattr(unit, "reflux_drum_internal_energy_J"))
            / (drum_total_moles * liquid_cp_j_per_mol_k),
            250.0,
            700.0,
        )
    )
    sump_temperature_k = float(
        np.clip(
            reference_temperature_k
            + float(getattr(unit, "bottoms_sump_internal_energy_J"))
            / (sump_total_moles * liquid_cp_j_per_mol_k),
            250.0,
            700.0,
        )
    )
    top_pressure_pa = (
        r_gas_j_per_mol_k
        * drum_temperature_k
        * max(1.0e-9, float(getattr(unit, "top_vapor_holdup_mol")))
        / vapor_volume_m3
    )
    bottom_pressure_pa = (
        r_gas_j_per_mol_k
        * sump_temperature_k
        * max(1.0e-9, float(getattr(unit, "bottom_vapor_holdup_mol")))
        / vapor_volume_m3
    )

    scalar_projection: dict[str, float] = {
        f"{unit_id}/column_pressure_pa": float(getattr(unit, "column_pressure_pa")),
        f"{unit_id}/top_pressure_pa": float(top_pressure_pa),
        f"{unit_id}/bottom_pressure_pa": float(bottom_pressure_pa),
        f"{unit_id}/active_contact_height_m": float(getattr(unit, "active_contact_height_m")),
        f"{unit_id}/shell_diameter_m": float(getattr(unit, "shell_diameter_m")),
        f"{unit_id}/distillate_flow_mol_s": float(getattr(unit, "distillate_flow")),
        f"{unit_id}/bottoms_flow_mol_s": float(getattr(unit, "bottoms_flow")),
        f"{unit_id}/distillate_temperature_K": float(getattr(unit, "distillate_temperature")),
        f"{unit_id}/bottoms_temperature_K": float(getattr(unit, "bottoms_temperature")),
        f"{unit_id}/internal_liquid_traffic_mol_s": float(
            max(0.0, float(getattr(unit, "representative_internal_liquid_traffic_mol_s")))
        ),
        f"{unit_id}/internal_vapor_traffic_mol_s": float(
            max(0.0, float(getattr(unit, "representative_internal_vapor_traffic_mol_s")))
        ),
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


def _snapshot_thermo_tray_distillation_state_values(
    *,
    unit: ProcessModel,
    unit_id: str,
    runtime_context: SimulationRuntimeContext | None,
) -> dict[str, float]:
    tray_holdup = np.asarray(getattr(unit, "tray_component_holdup"), dtype=np.float64).reshape(-1)
    drum_moles = np.asarray(
        getattr(unit, "condenser_drum_component_moles"), dtype=np.float64
    ).reshape(-1)
    kettle_moles = np.asarray(
        getattr(unit, "reboiler_kettle_component_moles"), dtype=np.float64
    ).reshape(-1)
    feed_flows = np.asarray(getattr(unit, "feed_flows"), dtype=np.float64).reshape(-1)
    feed_temperatures = np.asarray(getattr(unit, "feed_temperatures"), dtype=np.float64).reshape(-1)
    feed_pressures = np.asarray(getattr(unit, "feed_pressures"), dtype=np.float64).reshape(-1)
    feed_compositions = np.asarray(getattr(unit, "feed_compositions"), dtype=np.float64).reshape(-1)
    feed_tray_indices = np.asarray(getattr(unit, "feed_tray_indices"), dtype=np.float64).reshape(-1)
    distillate_composition = np.asarray(
        getattr(unit, "distillate_composition"), dtype=np.float64
    ).reshape(-1)
    bottoms_composition = np.asarray(
        getattr(unit, "bottoms_composition"), dtype=np.float64
    ).reshape(-1)

    n_species = int(getattr(unit, "n_species"))
    n_trays = int(getattr(unit, "n_trays"))
    n_feeds = int(getattr(unit, "n_feeds"))
    tray_matrix = tray_holdup.reshape(n_trays, n_species)
    feed_matrix = feed_compositions.reshape(n_feeds, n_species)

    headspace_pressure = float(getattr(unit, "headspace_pressure_pa"))
    bottom_pressure = float(getattr(unit, "bottom_pressure_pa"))
    bubble_temperature_k = _thermo_tray_bubble_temperature_k(unit)
    drum_temperature_k = float(getattr(unit, "condenser_drum_temperature"))
    subcooling_k = bubble_temperature_k - drum_temperature_k

    scalar_projection: dict[str, float] = {
        f"{unit_id}/column_pressure_pa": headspace_pressure,
        f"{unit_id}/top_pressure_pa": headspace_pressure,
        f"{unit_id}/headspace_pressure_pa": headspace_pressure,
        f"{unit_id}/bottom_pressure_pa": bottom_pressure,
        f"{unit_id}/distillate_flow_mol_s": float(getattr(unit, "distillate_flow")),
        f"{unit_id}/bottoms_flow_mol_s": float(getattr(unit, "bottoms_flow")),
        f"{unit_id}/distillate_temperature_K": float(getattr(unit, "distillate_temperature")),
        f"{unit_id}/bottoms_temperature_K": float(getattr(unit, "bottoms_temperature")),
        f"{unit_id}/condenser_drum_temperature_K": drum_temperature_k,
        f"{unit_id}/condenser_bubble_temperature_K": bubble_temperature_k,
        f"{unit_id}/condenser_subcooling_K": subcooling_k,
        f"{unit_id}/reflux_drum_holdup_mol": float(np.sum(drum_moles)),
        f"{unit_id}/bottoms_sump_holdup_mol": float(np.sum(kettle_moles)),
        f"{unit_id}/realized_condensed_flow_mol_s": float(getattr(unit, "realized_condensed_flow")),
        f"{unit_id}/non_condensed_flow_mol_s": float(getattr(unit, "non_condensed_flow")),
        f"{unit_id}/distillate_source_pressure_pa": float(
            getattr(unit, "distillate_source_pressure_pa")
        ),
        f"{unit_id}/reflux_source_pressure_pa": float(getattr(unit, "reflux_source_pressure_pa")),
        f"{unit_id}/distillate_withdrawal_flow_mol_s": float(
            getattr(unit, "distillate_withdrawal_flow")
        ),
        f"{unit_id}/bottoms_withdrawal_flow_mol_s": float(getattr(unit, "bottoms_withdrawal_flow")),
        f"{unit_id}/condenser_duty_request_W": float(getattr(unit, "condenser_duty_request_W")),
        f"{unit_id}/reboiler_duty_request_W": float(getattr(unit, "reboiler_duty_request_W")),
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

    selected_trays: set[int] = {0, max(0, n_trays - 1)}
    for feed_tray_index in feed_tray_indices:
        selected_trays.add(int(np.clip(round(float(feed_tray_index)) - 1, 0, n_trays - 1)))

    for tray_index_zero_based in sorted(selected_trays):
        tray_label = tray_index_zero_based + 1
        tray_inventory = np.clip(tray_matrix[tray_index_zero_based], 0.0, None)
        tray_total = float(np.sum(tray_inventory))
        if tray_total <= 0.0:
            tray_x = np.full(n_species, 1.0 / float(n_species), dtype=np.float64)
        else:
            tray_x = tray_inventory / tray_total
        for species_index, cas_id in enumerate(cas_ids[:n_species]):
            scalar_projection[f"{unit_id}/stage_{tray_label}/mole_fraction/{cas_id}"] = float(
                tray_x[species_index]
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
            feed_tray_indices[feed_index]
        )
        for species_index, cas_id in enumerate(cas_ids[:n_species]):
            scalar_projection[f"{unit_id}/feed_{feed_label}/mole_fraction/{cas_id}"] = float(
                feed_matrix[feed_index, species_index]
            )

    return scalar_projection


def _thermo_tray_bubble_temperature_k(unit: ProcessModel) -> float:
    selector = tuple(
        int(value) for value in np.asarray(getattr(unit, "species_selector"), dtype=np.float64)
    )
    species_ids = tuple(pp._DEFAULT_PR_SPECIES_CAS[index] for index in selector)
    package = pp.PengRobinsonPackage(species_ids=species_ids)
    try:
        state = package._flasher.flash(
            P=float(getattr(unit, "headspace_pressure_pa")),
            VF=0.0,
            zs=list(np.asarray(getattr(unit, "distillate_composition"), dtype=np.float64)),
        )
        return float(state.T)
    except Exception:
        return float(getattr(unit, "condenser_drum_temperature"))


__all__ = ["create_subsystem_for_unit", "create_system_for_unit"]

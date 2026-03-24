from __future__ import annotations

# pyright: reportMissingTypeStubs=false

from collections.abc import Mapping
from typing import TYPE_CHECKING

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
    return Subsystem(descriptor=descriptor, system=system)


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
        value = unit.state_getter(state_name)
        if not isinstance(value, (int, float)):
            # Skip non-scalar states (e.g. ndarray composition vectors).
            # Array-shaped states are surfaced via process_state_values, not
            # published_measurements, so omitting them here is correct and
            # prevents float(ndarray) TypeError after species-dimension widening.
            continue
        publication_map[state_name] = float(value)
    return publication_map


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


__all__ = ["create_subsystem_for_unit", "create_system_for_unit"]

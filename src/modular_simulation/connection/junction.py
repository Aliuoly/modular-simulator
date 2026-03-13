from __future__ import annotations

import warnings
from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite
from typing import TYPE_CHECKING, Final

import numpy as np

from modular_simulation.connection.state import MaterialState, PortCondition
from modular_simulation.thermodynamics.species import SpeciesProjection

if TYPE_CHECKING:
    from modular_simulation.thermodynamics.property_package import PropertyPackage

NEAR_ZERO_INCOMING_FLOW_EPSILON: Final[float] = 1.0e-12


@dataclass(frozen=True)
class JunctionMixingResult:
    state: MaterialState
    total_incoming_flow_rate: float
    used_fallback: bool


def mix_junction_state(
    *,
    incoming_port_conditions: Mapping[str, PortCondition],
    previous_state: MaterialState,
    near_zero_incoming_flow_epsilon: float = NEAR_ZERO_INCOMING_FLOW_EPSILON,
) -> JunctionMixingResult:
    if near_zero_incoming_flow_epsilon <= 0.0:
        raise ValueError("near_zero_incoming_flow_epsilon must be positive")
    if not isfinite(near_zero_incoming_flow_epsilon):
        raise ValueError("near_zero_incoming_flow_epsilon must be finite")

    if not incoming_port_conditions:
        return JunctionMixingResult(
            state=previous_state,
            total_incoming_flow_rate=0.0,
            used_fallback=True,
        )

    aligned_incoming = _align_incoming_to_canonical_species(
        incoming_port_conditions=incoming_port_conditions,
        previous_state=previous_state,
    )
    composition_len = len(next(iter(aligned_incoming.values())).state.mole_fractions)
    incoming_contributions: list[tuple[float, MaterialState]] = []

    for edge_id in sorted(aligned_incoming):
        port = aligned_incoming[edge_id]
        flow = port.through_molar_flow_rate
        if not isfinite(flow):
            raise ValueError("through_molar_flow_rate must be finite")
        if len(port.state.mole_fractions) != composition_len:
            raise ValueError("incoming and previous_state mole fraction lengths must match")
        if flow > 0.0:
            incoming_contributions.append((flow, port.state))

    total_incoming_flow_rate = sum(flow for flow, _ in incoming_contributions)
    if total_incoming_flow_rate <= near_zero_incoming_flow_epsilon:
        return JunctionMixingResult(
            state=previous_state,
            total_incoming_flow_rate=total_incoming_flow_rate,
            used_fallback=True,
        )

    mixed_pressure = (
        sum(flow * state.pressure for flow, state in incoming_contributions)
        / total_incoming_flow_rate
    )
    mixed_temperature = (
        sum(flow * state.temperature for flow, state in incoming_contributions)
        / total_incoming_flow_rate
    )
    mixed_mole_fractions = tuple(
        sum(flow * state.mole_fractions[index] for flow, state in incoming_contributions)
        / total_incoming_flow_rate
        for index in range(composition_len)
    )

    mixed_state = MaterialState(
        pressure=mixed_pressure,
        temperature=mixed_temperature,
        mole_fractions=mixed_mole_fractions,
        species_ids=incoming_contributions[0][1].species_ids,
    )
    return JunctionMixingResult(
        state=mixed_state,
        total_incoming_flow_rate=total_incoming_flow_rate,
        used_fallback=False,
    )


def mix_junction_state_with_enthalpy(
    incoming_states: list[PortCondition],
    property_package: PropertyPackage,
    *,
    near_zero_incoming_flow_epsilon: float = NEAR_ZERO_INCOMING_FLOW_EPSILON,
) -> JunctionMixingResult:
    if not incoming_states:
        raise ValueError("incoming_states must contain at least one PortCondition")

    incoming_by_edge = {
        f"incoming_{index:04d}": incoming_state
        for index, incoming_state in enumerate(incoming_states)
    }
    linear_result = mix_junction_state(
        incoming_port_conditions=incoming_by_edge,
        previous_state=incoming_states[0].state,
        near_zero_incoming_flow_epsilon=near_zero_incoming_flow_epsilon,
    )
    if linear_result.used_fallback:
        return linear_result

    incoming_contributions = [
        (port.through_molar_flow_rate, port.state)
        for port in incoming_states
        if port.through_molar_flow_rate > 0.0
    ]
    if not incoming_contributions:
        return JunctionMixingResult(
            state=linear_result.state,
            total_incoming_flow_rate=linear_result.total_incoming_flow_rate,
            used_fallback=True,
        )

    enthalpy_values: list[tuple[float, float]] = []
    for flow, state in incoming_contributions:
        enthalpy_molar = state.enthalpy_molar
        if not isinstance(enthalpy_molar, (float, int)):
            return JunctionMixingResult(
                state=linear_result.state,
                total_incoming_flow_rate=linear_result.total_incoming_flow_rate,
                used_fallback=True,
            )
        enthalpy_value = float(enthalpy_molar)
        if not isfinite(enthalpy_value):
            return JunctionMixingResult(
                state=linear_result.state,
                total_incoming_flow_rate=linear_result.total_incoming_flow_rate,
                used_fallback=True,
            )
        enthalpy_values.append((flow, enthalpy_value))

    mixed_enthalpy = (
        sum(flow * enthalpy for flow, enthalpy in enthalpy_values)
        / linear_result.total_incoming_flow_rate
    )

    try:
        flash_state = property_package.flash_ph(
            P=linear_result.state.pressure,
            H=mixed_enthalpy,
            z=linear_result.state.mole_fractions,
        )
    except Exception as exc:
        warnings.warn(
            f"Flash calculation failed during junction mixing (P={linear_result.state.pressure}, "
            f"H={mixed_enthalpy}): {exc!r}. Falling back to linear mixing.",
            RuntimeWarning,
            stacklevel=2,
        )
        return JunctionMixingResult(
            state=linear_result.state,
            total_incoming_flow_rate=linear_result.total_incoming_flow_rate,
            used_fallback=True,
        )

    species_ids = linear_result.state.species_ids

    mixed_state = MaterialState(
        pressure=linear_result.state.pressure,
        temperature=flash_state.temperature,
        mole_fractions=linear_result.state.mole_fractions,
        species_ids=species_ids,
        phase=flash_state.phase,
        enthalpy_molar=flash_state.enthalpy_molar,
        entropy_molar=flash_state.entropy_molar,
    )
    return JunctionMixingResult(
        state=mixed_state,
        total_incoming_flow_rate=linear_result.total_incoming_flow_rate,
        used_fallback=False,
    )


def _align_incoming_to_canonical_species(
    *, incoming_port_conditions: Mapping[str, PortCondition], previous_state: MaterialState
) -> dict[str, PortCondition]:
    if not incoming_port_conditions:
        return {}

    canonical_species_ids = _canonical_species_ids(
        incoming_port_conditions=incoming_port_conditions,
        previous_state=previous_state,
    )
    if canonical_species_ids is None:
        return dict(incoming_port_conditions)

    aligned: dict[str, PortCondition] = {}
    for edge_id, port in incoming_port_conditions.items():
        aligned_state = _align_state_to_species_ids(
            edge_id=edge_id,
            state=port.state,
            canonical_species_ids=canonical_species_ids,
        )
        aligned[edge_id] = PortCondition(
            state=aligned_state,
            species_ids=aligned_state.species_ids,
            through_molar_flow_rate=port.through_molar_flow_rate,
            macro_step_time_s=port.macro_step_time_s,
        )
    return aligned


def _canonical_species_ids(
    *, incoming_port_conditions: Mapping[str, PortCondition], previous_state: MaterialState
) -> tuple[str, ...] | None:
    if previous_state.species_ids is not None:
        return previous_state.species_ids
    for edge_id in sorted(incoming_port_conditions):
        species_ids = incoming_port_conditions[edge_id].state.species_ids
        if species_ids is not None:
            return species_ids
    return None


def _align_state_to_species_ids(
    *, edge_id: str, state: MaterialState, canonical_species_ids: tuple[str, ...]
) -> MaterialState:
    source_species_ids = state.species_ids
    source_fractions = np.asarray(state.mole_fractions, dtype=float)
    if source_species_ids is None:
        if source_fractions.shape != (len(canonical_species_ids),):
            raise ValueError(
                f"Incoming stream '{edge_id}' has no species_ids metadata and length "
                f"{source_fractions.shape[0]} does not match canonical length {len(canonical_species_ids)}."
            )
        return MaterialState(
            pressure=state.pressure,
            temperature=state.temperature,
            mole_fractions=tuple(float(value) for value in source_fractions),
            species_ids=canonical_species_ids,
            phase=state.phase,
            enthalpy_molar=state.enthalpy_molar,
            entropy_molar=state.entropy_molar,
        )

    if source_species_ids == canonical_species_ids:
        return state

    canonical_index = {species_id: index for index, species_id in enumerate(canonical_species_ids)}
    source_set = set(source_species_ids)
    canonical_set = set(canonical_species_ids)
    extra_species = tuple(sorted(source_set - canonical_set))
    if extra_species:
        raise ValueError(
            f"Incoming stream '{edge_id}' species {extra_species} are not present in canonical set "
            f"{canonical_species_ids}; explicit projection would drop species."
        )

    local_to_global = np.array(
        [canonical_index[species_id] for species_id in source_species_ids], dtype=np.int64
    )
    projection = SpeciesProjection(
        global_to_local=np.array([], dtype=np.int64),
        local_to_global=local_to_global,
        n_local=len(source_species_ids),
        n_global=len(canonical_species_ids),
    )
    aligned = projection.to_global(source_fractions)
    return MaterialState(
        pressure=state.pressure,
        temperature=state.temperature,
        mole_fractions=tuple(float(value) for value in aligned),
        species_ids=canonical_species_ids,
        phase=state.phase,
        enthalpy_molar=state.enthalpy_molar,
        entropy_molar=state.entropy_molar,
    )


__all__ = [
    "JunctionMixingResult",
    "mix_junction_state",
    "mix_junction_state_with_enthalpy",
]

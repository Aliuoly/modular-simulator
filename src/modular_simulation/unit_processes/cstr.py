from __future__ import annotations

# pyright: reportMissingTypeStubs=false, reportAny=false, reportExplicitAny=false

from dataclasses import dataclass
from math import isfinite
from typing import Annotated, Any, cast, override

import numpy as np
from numpy.typing import NDArray
from pydantic import PrivateAttr

from modular_simulation.measurables.process_model import ProcessModel
from modular_simulation.measurables.process_model import StateMetadata as M
from modular_simulation.measurables.process_model import StateType as T
from modular_simulation.thermodynamics.algebraic_process_model import SINGLE_IO, UnitProcessPorts
from modular_simulation.thermodynamics.kinetics import ReactionSet
from modular_simulation.utils.typing import ArrayIndex

_MIN_VOLUME = 1.0e-9
_MIN_COMPOSITION_SUM = 1.0e-12
_COMPOSITION_TOL = 1.0e-8


def _coerce_vector(
    value: NDArray[np.float64], *, expected_size: int, name: str, default: float
) -> NDArray[np.float64]:
    vector = np.asarray(value, dtype=np.float64).reshape(-1)
    if vector.size == 0:
        return np.full(expected_size, default, dtype=np.float64)
    if vector.size != expected_size:
        raise ValueError(f"{name} length mismatch: expected {expected_size}, got {vector.size}.")
    return vector


def _validate_composition(composition: NDArray[np.float64], *, name: str) -> None:
    if not np.all(np.isfinite(composition)):
        raise ValueError(f"{name} must contain only finite values.")
    if np.any(composition < 0.0):
        raise ValueError(f"{name} must contain non-negative values.")
    if abs(float(np.sum(composition)) - 1.0) > _COMPOSITION_TOL:
        raise ValueError(f"{name} must sum to 1.0.")


@dataclass(frozen=True)
class _KineticsBinding:
    reaction_set: ReactionSet
    species_names: tuple[str, ...]


_KINETICS_REGISTRY: dict[int, _KineticsBinding] = {}


class CSTR(ProcessModel):
    species_moles: Annotated[
        NDArray[np.float64],
        M(type=T.DIFFERENTIAL, unit="mol", description="species moles by species index"),
    ] = np.zeros(0, dtype=np.float64)
    temperature: Annotated[
        float,
        M(type=T.DIFFERENTIAL, unit="K", description="reactor temperature"),
    ] = 298.15
    volume: Annotated[
        float,
        M(type=T.DIFFERENTIAL, unit="L", description="reactor liquid volume"),
    ] = 1.0

    inlet_flow: Annotated[
        float,
        M(type=T.CONTROLLED, unit="L/s", description="inlet volumetric flow rate"),
    ] = 0.0
    inlet_temperature: Annotated[
        float,
        M(type=T.CONTROLLED, unit="K", description="inlet temperature"),
    ] = 298.15
    inlet_pressure: Annotated[
        float,
        M(type=T.CONTROLLED, unit="Pa", description="inlet pressure"),
    ] = 101325.0
    inlet_composition: Annotated[
        NDArray[np.float64],
        M(type=T.CONTROLLED, unit="", description="inlet mole fractions by species index"),
    ] = np.zeros(0, dtype=np.float64)

    n_species: Annotated[int, M(type=T.CONSTANT, unit="", description="number of species")] = 2
    reactor_volume: Annotated[
        float,
        M(type=T.CONSTANT, unit="L", description="reactor volume setpoint"),
    ] = 1.0
    pressure: Annotated[
        float,
        M(type=T.CONSTANT, unit="Pa", description="reactor pressure"),
    ] = 101325.0
    volumetric_heat_capacity: Annotated[
        float,
        M(type=T.CONSTANT, unit="J/(L*K)", description="bulk volumetric heat capacity"),
    ] = 4180.0
    heat_transfer_coeff: Annotated[
        float,
        M(type=T.CONSTANT, unit="W/(m^2*K)", description="jacket heat transfer coefficient"),
    ] = 0.0
    jacket_area: Annotated[
        float,
        M(type=T.CONSTANT, unit="m^2", description="jacket heat transfer area"),
    ] = 0.0
    jacket_temperature: Annotated[
        float,
        M(type=T.CONSTANT, unit="K", description="jacket temperature"),
    ] = 298.15
    level_control_gain: Annotated[
        float,
        M(type=T.CONSTANT, unit="1/s", description="outlet flow level-control gain"),
    ] = 10.0
    reaction_heat_coeffs: Annotated[
        NDArray[np.float64],
        M(
            type=T.CONSTANT,
            unit="J/mol",
            description="species-wise reaction heat coefficients used as -V*dot(coeffs, net_rates)",
        ),
    ] = np.zeros(0, dtype=np.float64)
    model_instance_id: Annotated[
        float,
        M(type=T.CONSTANT, unit="", description="module-level kinetics registry key"),
    ] = 0.0

    outlet_composition: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="", description="outlet mole fractions by species index"),
    ] = np.zeros(0, dtype=np.float64)
    outlet_temperature: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="K", description="outlet temperature"),
    ] = 298.15
    outlet_flow: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="L/s", description="outlet volumetric flow rate"),
    ] = 0.0
    concentrations: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="mol/L", description="reactor species concentrations"),
    ] = np.zeros(0, dtype=np.float64)

    _reaction_set: ReactionSet = PrivateAttr(default_factory=lambda: ReactionSet(reactions=()))
    _species_names: tuple[str, ...] = PrivateAttr(default_factory=tuple)

    def __init__(self, **data: Any) -> None:
        reaction_set = data.pop("reaction_set", None)
        species_names = data.pop("species_names", None)
        super().__init__(**data)

        self._reaction_set = (
            cast(ReactionSet, reaction_set)
            if reaction_set is not None
            else ReactionSet(reactions=())
        )

        if species_names is None:
            self._species_names = tuple(f"species_{index + 1}" for index in range(self.n_species))
        else:
            normalized = tuple(str(name).strip() for name in cast(tuple[str, ...], species_names))
            if len(normalized) != self.n_species:
                raise ValueError(
                    "species_names length mismatch: "
                    + f"expected {self.n_species}, got {len(normalized)}."
                )
            if any(not name for name in normalized):
                raise ValueError("species_names entries must be non-empty strings.")
            self._species_names = normalized

    @override
    def model_post_init(self, context: object) -> None:
        super().model_post_init(context)

        if self.n_species <= 0:
            raise ValueError("n_species must be a positive integer.")
        if not isfinite(self.reactor_volume) or self.reactor_volume <= 0.0:
            raise ValueError("reactor_volume must be finite and positive.")
        if not isfinite(self.volume) or self.volume <= 0.0:
            raise ValueError("volume must be finite and positive.")
        if not isfinite(self.volumetric_heat_capacity) or self.volumetric_heat_capacity <= 0.0:
            raise ValueError("volumetric_heat_capacity must be finite and positive.")
        if not isfinite(self.level_control_gain) or self.level_control_gain < 0.0:
            raise ValueError("level_control_gain must be finite and non-negative.")
        if not isfinite(self.heat_transfer_coeff) or self.heat_transfer_coeff < 0.0:
            raise ValueError("heat_transfer_coeff must be finite and non-negative.")
        if not isfinite(self.jacket_area) or self.jacket_area < 0.0:
            raise ValueError("jacket_area must be finite and non-negative.")

        self.species_moles = _coerce_vector(
            self.species_moles,
            expected_size=self.n_species,
            name="species_moles",
            default=0.0,
        )
        self.inlet_composition = _coerce_vector(
            self.inlet_composition,
            expected_size=self.n_species,
            name="inlet_composition",
            default=1.0 / float(self.n_species),
        )
        self.outlet_composition = _coerce_vector(
            self.outlet_composition,
            expected_size=self.n_species,
            name="outlet_composition",
            default=1.0 / float(self.n_species),
        )
        self.concentrations = _coerce_vector(
            self.concentrations,
            expected_size=self.n_species,
            name="concentrations",
            default=0.0,
        )
        self.reaction_heat_coeffs = _coerce_vector(
            self.reaction_heat_coeffs,
            expected_size=self.n_species,
            name="reaction_heat_coeffs",
            default=0.0,
        )

        _validate_composition(self.inlet_composition, name="inlet_composition")

        if self.model_instance_id <= 0.0:
            self.model_instance_id = float(id(self))

    @property
    def ports(self) -> UnitProcessPorts:
        return SINGLE_IO

    def set_reaction_set(
        self,
        reaction_set: ReactionSet,
        *,
        species_names: tuple[str, ...] | None = None,
    ) -> None:
        self._reaction_set = reaction_set
        if species_names is not None:
            normalized = tuple(str(name).strip() for name in species_names)
            if len(normalized) != self.n_species:
                raise ValueError(
                    "species_names length mismatch: "
                    + f"expected {self.n_species}, got {len(normalized)}."
                )
            if any(not name for name in normalized):
                raise ValueError("species_names entries must be non-empty strings.")
            self._species_names = normalized

        _KINETICS_REGISTRY[int(round(self.model_instance_id))] = _KineticsBinding(
            reaction_set=self._reaction_set,
            species_names=self._species_names,
        )

    @override
    def attach_system(self, system: Any) -> None:
        super().attach_system(system)
        _KINETICS_REGISTRY[int(round(self.model_instance_id))] = _KineticsBinding(
            reaction_set=self._reaction_set,
            species_names=self._species_names,
        )

    @staticmethod
    @override
    def calculate_algebraic_values(
        y: NDArray[np.float64],
        u: NDArray[np.float64],
        k: NDArray[np.float64],
        y_map: dict[str, ArrayIndex],
        u_map: dict[str, ArrayIndex],
        k_map: dict[str, ArrayIndex],
        algebraic_map: dict[str, ArrayIndex],
        algebraic_size: int,
    ) -> NDArray[np.float64]:
        n_species = int(round(float(k[k_map["n_species"]])))
        if n_species <= 0:
            raise ValueError("n_species must be positive.")

        species_moles = np.asarray(y[y_map["species_moles"]], dtype=np.float64).reshape(-1)
        if species_moles.size != n_species:
            raise ValueError(
                f"species_moles length mismatch: expected {n_species}, got {species_moles.size}."
            )

        volume = max(_MIN_VOLUME, float(y[y_map["volume"]]))
        inlet_flow = max(0.0, float(u[u_map["inlet_flow"]]))
        level_gain = max(0.0, float(k[k_map["level_control_gain"]]))
        volume_setpoint = max(_MIN_VOLUME, float(k[k_map["reactor_volume"]]))
        outlet_flow = max(0.0, inlet_flow + level_gain * (volume - volume_setpoint))

        concentrations = species_moles / volume
        total_moles = float(np.sum(np.clip(species_moles, 0.0, None)))
        if total_moles <= _MIN_COMPOSITION_SUM:
            outlet_composition = np.full(n_species, 1.0 / float(n_species), dtype=np.float64)
        else:
            outlet_composition = np.clip(species_moles, 0.0, None) / total_moles

        result = np.zeros(algebraic_size, dtype=np.float64)
        result[algebraic_map["outlet_composition"]] = outlet_composition
        result[algebraic_map["outlet_temperature"]] = float(y[y_map["temperature"]])
        result[algebraic_map["outlet_flow"]] = outlet_flow
        result[algebraic_map["concentrations"]] = concentrations
        return result

    @staticmethod
    @override
    def differential_rhs(
        t: float,
        y: NDArray[np.float64],
        u: NDArray[np.float64],
        k: NDArray[np.float64],
        algebraic: NDArray[np.float64],
        y_map: dict[str, ArrayIndex],
        u_map: dict[str, ArrayIndex],
        k_map: dict[str, ArrayIndex],
        algebraic_map: dict[str, ArrayIndex],
    ) -> NDArray[np.float64]:
        del t, algebraic

        n_species = int(round(float(k[k_map["n_species"]])))
        if n_species <= 0:
            raise ValueError("n_species must be positive.")

        species_moles = np.asarray(y[y_map["species_moles"]], dtype=np.float64).reshape(-1)
        if species_moles.size != n_species:
            raise ValueError(
                f"species_moles length mismatch: expected {n_species}, got {species_moles.size}."
            )

        inlet_composition = np.asarray(u[u_map["inlet_composition"]], dtype=np.float64).reshape(-1)
        if inlet_composition.size != n_species:
            raise ValueError(
                "inlet_composition length mismatch: "
                + f"expected {n_species}, got {inlet_composition.size}."
            )

        volume = max(_MIN_VOLUME, float(y[y_map["volume"]]))
        temperature = float(y[y_map["temperature"]])
        inlet_flow = max(0.0, float(u[u_map["inlet_flow"]]))
        inlet_temperature = float(u[u_map["inlet_temperature"]])

        level_gain = max(0.0, float(k[k_map["level_control_gain"]]))
        volume_setpoint = max(_MIN_VOLUME, float(k[k_map["reactor_volume"]]))
        outlet_flow = max(0.0, inlet_flow + level_gain * (volume - volume_setpoint))

        concentrations = species_moles / volume
        model_instance_id = int(round(float(k[k_map["model_instance_id"]])))
        kinetics = _KINETICS_REGISTRY.get(model_instance_id)

        net_rates = np.zeros(n_species, dtype=np.float64)
        if kinetics is not None:
            concentration_map = {
                species_name: float(concentrations[index])
                for index, species_name in enumerate(kinetics.species_names)
            }
            rates_by_name = kinetics.reaction_set.net_rates(concentration_map, temperature)
            for index, species_name in enumerate(kinetics.species_names):
                net_rates[index] = float(rates_by_name.get(species_name, 0.0))

        dn_dt = (
            inlet_flow * inlet_composition + (net_rates * volume) - (outlet_flow * concentrations)
        )

        dV_dt = inlet_flow - outlet_flow

        heat_capacity = max(1.0e-12, float(k[k_map["volumetric_heat_capacity"]]))
        reaction_heat_coeffs = np.asarray(
            k[k_map["reaction_heat_coeffs"]], dtype=np.float64
        ).reshape(-1)
        if reaction_heat_coeffs.size != n_species:
            raise ValueError(
                "reaction_heat_coeffs length mismatch: "
                + f"expected {n_species}, got {reaction_heat_coeffs.size}."
            )

        reaction_heat = -volume * float(np.dot(reaction_heat_coeffs, net_rates))
        ua = max(0.0, float(k[k_map["heat_transfer_coeff"]])) * max(
            0.0, float(k[k_map["jacket_area"]])
        )
        jacket_temperature = float(k[k_map["jacket_temperature"]])
        jacket_heat = ua * (jacket_temperature - temperature)

        denominator = heat_capacity * volume
        dT_dt = (
            inlet_flow * heat_capacity * (inlet_temperature - temperature)
            + reaction_heat
            + jacket_heat
        ) / max(1.0e-12, denominator)

        dy = np.zeros_like(y)
        dy[y_map["species_moles"]] = dn_dt
        dy[y_map["temperature"]] = dT_dt
        dy[y_map["volume"]] = dV_dt
        return dy


__all__ = ["CSTR"]

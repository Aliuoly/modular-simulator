from __future__ import annotations

# pyright: reportMissingTypeStubs=false, reportAny=false, reportExplicitAny=false

from typing import Annotated, Any, override

import numpy as np
from numpy.typing import NDArray

from modular_simulation.measurables.process_model import StateMetadata as M
from modular_simulation.measurables.process_model import StateType as T
from modular_simulation.thermodynamics.algebraic_process_model import (
    AlgebraicProcessModel,
    UnitProcessPorts,
)
from modular_simulation.utils.typing import ArrayIndex

_RATIO_TOL = 1.0e-12
_COMPOSITION_TOL = 1.0e-8


def _vector_from_state(values: NDArray[np.float64], index: ArrayIndex) -> NDArray[np.float64]:
    return np.asarray(values[index], dtype=np.float64).reshape(-1)


def _coerce_vector(
    value: NDArray[np.float64],
    *,
    expected_size: int,
    name: str,
    default: float = 0.0,
) -> NDArray[np.float64]:
    vector = np.asarray(value, dtype=np.float64).reshape(-1)
    if vector.size == 0:
        return np.full(expected_size, default, dtype=np.float64)
    if vector.size != expected_size:
        raise ValueError(f"{name} length mismatch: expected {expected_size}, got {vector.size}.")
    return vector


def _validate_nonnegative_finite(vector: NDArray[np.float64], *, name: str) -> None:
    if not np.all(np.isfinite(vector)):
        raise ValueError(f"{name} must contain only finite values.")
    if np.any(vector < 0.0):
        raise ValueError(f"{name} must contain non-negative values.")


def _validate_composition(composition: NDArray[np.float64], *, name: str) -> None:
    _validate_nonnegative_finite(composition, name=name)
    if abs(float(np.sum(composition)) - 1.0) > _COMPOSITION_TOL:
        raise ValueError(f"{name} must sum to 1.0.")


def _validate_split_ratios(split_ratios: NDArray[np.float64]) -> NDArray[np.float64]:
    _validate_nonnegative_finite(split_ratios, name="split_ratios")
    ratio_sum = float(np.sum(split_ratios))
    if ratio_sum > 1.0 + _RATIO_TOL:
        raise ValueError("split_ratios sum must be <= 1.0.")
    return np.concatenate((split_ratios, np.array([1.0 - ratio_sum], dtype=np.float64)))


class Splitter(AlgebraicProcessModel):
    n_outlets: Annotated[int, M(type=T.CONSTANT, unit="", description="number of outlet ports")] = 2
    n_species: Annotated[int, M(type=T.CONSTANT, unit="", description="number of species")] = 2

    inlet_flow: Annotated[
        float,
        M(type=T.CONTROLLED, unit="mol/s", description="inlet molar flow rate"),
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
        M(type=T.CONTROLLED, unit="", description="inlet composition vector by species index"),
    ] = np.zeros(0, dtype=np.float64)
    split_ratios: Annotated[
        NDArray[np.float64],
        M(
            type=T.CONTROLLED,
            unit="",
            description="N-1 split ratios; final ratio computed as 1-sum(split_ratios)",
        ),
    ] = np.zeros(0, dtype=np.float64)

    outlet_flows: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="mol/s", description="outlet flow vector by outlet index"),
    ] = np.zeros(0, dtype=np.float64)
    outlet_temperatures: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="K", description="outlet temperatures by outlet index"),
    ] = np.zeros(0, dtype=np.float64)
    outlet_pressures: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="Pa", description="outlet pressures by outlet index"),
    ] = np.zeros(0, dtype=np.float64)
    outlet_compositions: Annotated[
        NDArray[np.float64],
        M(
            type=T.ALGEBRAIC,
            unit="",
            description="flattened outlet composition matrix with shape (n_outlets, n_species)",
        ),
    ] = np.zeros(0, dtype=np.float64)

    @override
    def model_post_init(self, context: Any) -> None:
        super().model_post_init(context)
        if self.n_outlets <= 0:
            raise ValueError("n_outlets must be a positive integer.")
        if self.n_species <= 0:
            raise ValueError("n_species must be a positive integer.")

        self.inlet_composition = _coerce_vector(
            self.inlet_composition,
            expected_size=self.n_species,
            name="inlet_composition",
            default=1.0 / float(self.n_species),
        )
        self.split_ratios = _coerce_vector(
            self.split_ratios,
            expected_size=max(self.n_outlets - 1, 0),
            name="split_ratios",
            default=0.0,
        )
        self.outlet_flows = _coerce_vector(
            self.outlet_flows,
            expected_size=self.n_outlets,
            name="outlet_flows",
        )
        self.outlet_temperatures = _coerce_vector(
            self.outlet_temperatures,
            expected_size=self.n_outlets,
            name="outlet_temperatures",
            default=self.inlet_temperature,
        )
        self.outlet_pressures = _coerce_vector(
            self.outlet_pressures,
            expected_size=self.n_outlets,
            name="outlet_pressures",
            default=self.inlet_pressure,
        )
        self.outlet_compositions = _coerce_vector(
            self.outlet_compositions,
            expected_size=self.n_outlets * self.n_species,
            name="outlet_compositions",
            default=1.0 / float(self.n_species),
        )

        if not np.isfinite(self.inlet_flow) or self.inlet_flow < 0.0:
            raise ValueError("inlet_flow must be finite and non-negative.")
        if not np.isfinite(self.inlet_temperature):
            raise ValueError("inlet_temperature must be finite.")
        if not np.isfinite(self.inlet_pressure):
            raise ValueError("inlet_pressure must be finite.")
        _validate_composition(self.inlet_composition, name="inlet_composition")
        _ = _validate_split_ratios(self.split_ratios)

    @property
    def ports(self) -> UnitProcessPorts:
        return UnitProcessPorts(
            inlets=("inlet",),
            outlets=tuple(f"outlet_{index + 1}" for index in range(self.n_outlets)),
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
        del y, y_map

        n_outlets = int(round(float(k[k_map["n_outlets"]])))
        n_species = int(round(float(k[k_map["n_species"]])))
        if n_outlets <= 0:
            raise ValueError("n_outlets must be positive.")
        if n_species <= 0:
            raise ValueError("n_species must be positive.")

        inlet_flow = float(u[u_map["inlet_flow"]])
        inlet_temperature = float(u[u_map["inlet_temperature"]])
        inlet_pressure = float(u[u_map["inlet_pressure"]])
        inlet_composition = _vector_from_state(u, u_map["inlet_composition"])
        split_ratios = _vector_from_state(u, u_map["split_ratios"])

        if not np.isfinite(inlet_flow) or inlet_flow < 0.0:
            raise ValueError("inlet_flow must be finite and non-negative.")
        if not np.isfinite(inlet_temperature):
            raise ValueError("inlet_temperature must be finite.")
        if not np.isfinite(inlet_pressure):
            raise ValueError("inlet_pressure must be finite.")

        if inlet_composition.size != n_species:
            raise ValueError(
                f"inlet_composition length mismatch: expected {n_species}, got {inlet_composition.size}."
            )
        expected_ratio_size = max(n_outlets - 1, 0)
        if split_ratios.size != expected_ratio_size:
            raise ValueError(
                f"split_ratios length mismatch: expected {expected_ratio_size}, got {split_ratios.size}."
            )

        _validate_composition(inlet_composition, name="inlet_composition")
        full_split = _validate_split_ratios(split_ratios)

        outlet_flows = inlet_flow * full_split
        outlet_temperatures = np.full(n_outlets, inlet_temperature, dtype=np.float64)
        outlet_pressures = np.full(n_outlets, inlet_pressure, dtype=np.float64)
        outlet_compositions = np.tile(inlet_composition, n_outlets)

        result = np.zeros(algebraic_size, dtype=np.float64)
        result[algebraic_map["outlet_flows"]] = outlet_flows
        result[algebraic_map["outlet_temperatures"]] = outlet_temperatures
        result[algebraic_map["outlet_pressures"]] = outlet_pressures
        result[algebraic_map["outlet_compositions"]] = outlet_compositions
        return result


__all__ = ["Splitter"]

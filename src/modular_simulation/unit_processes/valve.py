from __future__ import annotations

# pyright: reportMissingTypeStubs=false

from math import isfinite
from typing import Annotated, cast, override

import numpy as np
from numpy.typing import NDArray
from pydantic import PrivateAttr

from modular_simulation.connection.hydraulic_compile import calculate_effective_valve_resistance
from modular_simulation.connection.hydraulic_element import (
    ValveHydraulicElement,
    smooth_signed_quadratic_flow_term,
)
from modular_simulation.measurables.process_model import StateMetadata as M
from modular_simulation.measurables.process_model import StateType as T
from modular_simulation.thermodynamics.algebraic_process_model import (
    AlgebraicProcessModel,
    SINGLE_IO,
    UnitProcessPorts,
)
from modular_simulation.thermodynamics.property_package import PropertyPackage
from modular_simulation.utils.typing import ArrayIndex, Seconds

_COMPOSITION_TOL = 1.0e-8
_TINY_POSITIVE_PRESSURE = 1.0e-9


def _coerce_vector(
    value: NDArray[np.float64], *, expected_size: int, name: str, default: float
) -> NDArray[np.float64]:
    vector = np.asarray(value, dtype=np.float64).reshape(-1)
    if vector.size == 0:
        return np.full(expected_size, default, dtype=np.float64)
    if vector.size != expected_size:
        raise ValueError(f"{name} length mismatch: expected {expected_size}, got {vector.size}.")
    return vector


def _vector_from_state(values: NDArray[np.float64], index: ArrayIndex) -> NDArray[np.float64]:
    return np.asarray(values[index], dtype=np.float64).reshape(-1)


def _validate_composition(composition: NDArray[np.float64], *, name: str) -> None:
    if not np.all(np.isfinite(composition)):
        raise ValueError(f"{name} must contain only finite values.")
    if np.any(composition < 0.0):
        raise ValueError(f"{name} must contain non-negative values.")
    if abs(float(np.sum(composition)) - 1.0) > _COMPOSITION_TOL:
        raise ValueError(f"{name} must sum to 1.0.")


class Valve(AlgebraicProcessModel):
    n_species: Annotated[int, M(type=T.CONSTANT, unit="", description="number of species")] = 2
    Cv: Annotated[
        float,
        M(type=T.CONSTANT, unit="", description="valve flow coefficient (m^3/s/sqrt(Pa))"),
    ] = 1.0
    minimum_open_fraction: Annotated[
        float,
        M(type=T.CONSTANT, unit="", description="minimum allowed valve opening"),
    ] = 0.0
    maximum_open_fraction: Annotated[
        float,
        M(type=T.CONSTANT, unit="", description="maximum allowed valve opening"),
    ] = 1.0
    delta: Annotated[
        float,
        M(type=T.CONSTANT, unit="m^3/s", description="smooth flow regularization parameter"),
    ] = 1.0e-6
    min_relative_open_fraction: Annotated[
        float,
        M(type=T.CONSTANT, unit="", description="minimum throttling fraction floor"),
    ] = 1.0e-3

    inlet_flow: Annotated[
        float,
        M(type=T.CONTROLLED, unit="m^3/s", description="inlet volumetric flow rate"),
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
    open_fraction: Annotated[
        float,
        M(type=T.CONTROLLED, unit="", description="instantaneous valve opening fraction"),
    ] = 1.0

    outlet_flow: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="m^3/s", description="outlet volumetric flow rate"),
    ] = 0.0
    outlet_pressure: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="Pa", description="outlet pressure after throttling"),
    ] = 101325.0
    outlet_temperature: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="K", description="outlet temperature"),
    ] = 298.15
    outlet_composition: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="", description="outlet composition vector by species index"),
    ] = np.zeros(0, dtype=np.float64)
    outlet_enthalpy: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="J/mol", description="outlet molar enthalpy"),
    ] = 0.0

    _property_package: PropertyPackage | None = PrivateAttr(default=None)
    _hydraulic_element: ValveHydraulicElement = PrivateAttr(default_factory=ValveHydraulicElement)

    @override
    def model_post_init(self, context: object) -> None:
        super().model_post_init(context)
        if self.n_species <= 0:
            raise ValueError("n_species must be a positive integer.")

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

        if not isfinite(self.inlet_flow) or self.inlet_flow < 0.0:
            raise ValueError("inlet_flow must be finite and non-negative.")
        if not isfinite(self.inlet_temperature):
            raise ValueError("inlet_temperature must be finite.")
        if not isfinite(self.inlet_pressure) or self.inlet_pressure <= 0.0:
            raise ValueError("inlet_pressure must be finite and positive.")
        if not isfinite(self.open_fraction):
            raise ValueError("open_fraction must be finite.")
        if not isfinite(self.Cv) or self.Cv <= 0.0:
            raise ValueError("Cv must be finite and positive.")
        if not isfinite(self.delta) or self.delta <= 0.0:
            raise ValueError("delta must be finite and positive.")
        if not isfinite(self.minimum_open_fraction) or not isfinite(self.maximum_open_fraction):
            raise ValueError("valve open range must be finite.")
        if self.minimum_open_fraction > self.maximum_open_fraction:
            raise ValueError("valve open range is invalid: minimum must be <= maximum.")
        if (
            self.open_fraction < self.minimum_open_fraction
            or self.open_fraction > self.maximum_open_fraction
        ):
            raise ValueError("open_fraction must be within configured min/max bounds.")
        if not isfinite(self.min_relative_open_fraction) or self.min_relative_open_fraction <= 0.0:
            raise ValueError("min_relative_open_fraction must be finite and positive.")

        _validate_composition(self.inlet_composition, name="inlet_composition")

    @property
    def ports(self) -> UnitProcessPorts:
        return SINGLE_IO

    def set_property_package(self, package: PropertyPackage | None) -> None:
        self._property_package = package

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

        n_species = int(round(float(k[k_map["n_species"]])))
        if n_species <= 0:
            raise ValueError("n_species must be positive.")

        inlet_flow = float(u[u_map["inlet_flow"]])
        inlet_temperature = float(u[u_map["inlet_temperature"]])
        inlet_pressure = float(u[u_map["inlet_pressure"]])
        inlet_composition = _vector_from_state(u, u_map["inlet_composition"])
        open_fraction = float(u[u_map["open_fraction"]])

        cv_value = float(k[k_map["Cv"]])
        minimum_open_fraction = float(k[k_map["minimum_open_fraction"]])
        maximum_open_fraction = float(k[k_map["maximum_open_fraction"]])
        delta = float(k[k_map["delta"]])
        min_relative_open_fraction = float(k[k_map["min_relative_open_fraction"]])

        if not isfinite(inlet_flow) or inlet_flow < 0.0:
            raise ValueError("inlet_flow must be finite and non-negative.")
        if not isfinite(inlet_temperature):
            raise ValueError("inlet_temperature must be finite.")
        if not isfinite(inlet_pressure) or inlet_pressure <= 0.0:
            raise ValueError("inlet_pressure must be finite and positive.")
        if not isfinite(open_fraction):
            raise ValueError("open_fraction must be finite.")
        if not isfinite(cv_value) or cv_value <= 0.0:
            raise ValueError("Cv must be finite and positive.")
        if not isfinite(delta) or delta <= 0.0:
            raise ValueError("delta must be finite and positive.")
        if not isfinite(min_relative_open_fraction) or min_relative_open_fraction <= 0.0:
            raise ValueError("min_relative_open_fraction must be finite and positive.")
        if inlet_composition.size != n_species:
            raise ValueError(
                f"inlet_composition length mismatch: expected {n_species}, got {inlet_composition.size}."
            )

        _validate_composition(inlet_composition, name="inlet_composition")

        resistance_when_open = 1.0 / (cv_value * cv_value)
        effective_resistance = calculate_effective_valve_resistance(
            resistance_when_open=resistance_when_open,
            open_fraction=open_fraction,
            minimum_open_fraction=minimum_open_fraction,
            maximum_open_fraction=maximum_open_fraction,
            min_relative_open_fraction=min_relative_open_fraction,
        )

        flow_term = smooth_signed_quadratic_flow_term(m_dot=inlet_flow, delta=delta)
        outlet_pressure = max(
            inlet_pressure - effective_resistance * flow_term, _TINY_POSITIVE_PRESSURE
        )

        result = np.zeros(algebraic_size, dtype=np.float64)
        result[algebraic_map["outlet_flow"]] = inlet_flow
        result[algebraic_map["outlet_pressure"]] = outlet_pressure
        result[algebraic_map["outlet_temperature"]] = inlet_temperature
        result[algebraic_map["outlet_composition"]] = inlet_composition
        result[algebraic_map["outlet_enthalpy"]] = 0.0
        return result

    @override
    def step(self, dt: Seconds) -> None:
        super().step(dt)

        package = self._property_package
        if package is None:
            return

        composition_array = np.asarray(self.inlet_composition, dtype=np.float64)
        z = tuple(cast(list[float], composition_array.tolist()))

        flash_in = package.flash_tp(
            T=float(self.inlet_temperature),
            P=float(self.inlet_pressure),
            z=z,
        )
        inlet_enthalpy = float(flash_in.enthalpy_molar)

        flash_out = package.flash_ph(
            P=max(float(self.outlet_pressure), _TINY_POSITIVE_PRESSURE),
            H=inlet_enthalpy,
            z=z,
        )
        self.outlet_temperature = float(flash_out.temperature)
        self.outlet_enthalpy = float(flash_out.enthalpy_molar)


__all__ = ["Valve"]

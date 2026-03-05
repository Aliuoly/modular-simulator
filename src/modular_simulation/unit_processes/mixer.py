from __future__ import annotations

# pyright: reportMissingTypeStubs=false

from math import isfinite
from typing import Annotated, Any, ClassVar, override

import numpy as np
from numpy.typing import NDArray
from pydantic import PrivateAttr

from modular_simulation.measurables.process_model import StateMetadata as M
from modular_simulation.measurables.process_model import StateType as T
from modular_simulation.thermodynamics.algebraic_process_model import (
    AlgebraicProcessModel,
    UnitProcessPorts,
)
from modular_simulation.thermodynamics.hydraulic_adapters import pipe_hydraulic_element_for_outlet
from modular_simulation.thermodynamics.property_package import PropertyPackage
from modular_simulation.thermodynamics.stream import (
    PortAttributeMap,
    StreamData,
    default_inlet_map,
    default_outlet_map,
)
from modular_simulation.utils.typing import ArrayIndex, Seconds

_FLOW_EPSILON = 1.0e-12
_COMPOSITION_TOL = 1.0e-8


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


def _validate_vector(
    vector: NDArray[np.float64], *, name: str, allow_negative: bool = False
) -> None:
    if not np.all(np.isfinite(vector)):
        raise ValueError(f"{name} must contain only finite values.")
    if not allow_negative and np.any(vector < 0.0):
        raise ValueError(f"{name} must contain non-negative values.")


def _coerce_composition_matrix(
    value: NDArray[np.float64], *, n_inlets: int, n_species: int
) -> NDArray[np.float64]:
    matrix = np.asarray(value, dtype=np.float64).reshape(-1)
    expected_size = n_inlets * n_species
    if matrix.size == 0:
        default_row = np.full(n_species, 1.0 / float(n_species), dtype=np.float64)
        return np.tile(default_row, n_inlets)
    if matrix.size != expected_size:
        raise ValueError(
            "inlet_compositions length mismatch: " + f"expected {expected_size}, got {matrix.size}."
        )
    return matrix


def _validate_composition_rows(matrix: NDArray[np.float64], *, n_species: int, name: str) -> None:
    if not np.all(np.isfinite(matrix)):
        raise ValueError(f"{name} must contain only finite values.")
    if np.any(matrix < 0.0):
        raise ValueError(f"{name} must contain non-negative values.")

    row_sums = np.sum(matrix, axis=1)
    if np.any(np.abs(row_sums - 1.0) > _COMPOSITION_TOL):
        raise ValueError(f"Each {name} row must sum to 1.0.")
    if matrix.shape[1] != n_species:
        raise ValueError(
            f"{name} species width mismatch: expected {n_species}, got {matrix.shape[1]}."
        )


def _vector_from_state(values: NDArray[np.float64], index: ArrayIndex) -> NDArray[np.float64]:
    return np.asarray(values[index], dtype=np.float64).reshape(-1)


class Mixer(AlgebraicProcessModel):
    _OUTLET_MAP: ClassVar[dict[str, PortAttributeMap]] = {"outlet": default_outlet_map("outlet")}

    n_inlets: Annotated[int, M(type=T.CONSTANT, unit="", description="number of inlet ports")] = 2
    n_species: Annotated[int, M(type=T.CONSTANT, unit="", description="number of species")] = 2

    inlet_flows: Annotated[
        NDArray[np.float64],
        M(type=T.CONTROLLED, unit="mol/s", description="inlet molar flow rates by inlet index"),
    ] = np.zeros(0, dtype=np.float64)
    inlet_temperatures: Annotated[
        NDArray[np.float64],
        M(type=T.CONTROLLED, unit="K", description="inlet temperatures by inlet index"),
    ] = np.zeros(0, dtype=np.float64)
    inlet_pressures: Annotated[
        NDArray[np.float64],
        M(type=T.CONTROLLED, unit="Pa", description="inlet pressures by inlet index"),
    ] = np.zeros(0, dtype=np.float64)
    inlet_compositions: Annotated[
        NDArray[np.float64],
        M(
            type=T.CONTROLLED,
            unit="",
            description="flattened inlet composition matrix with shape (n_inlets, n_species)",
        ),
    ] = np.zeros(0, dtype=np.float64)

    outlet_flow: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="mol/s", description="outlet molar flow rate"),
    ] = 0.0
    outlet_temperature: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="K", description="outlet temperature"),
    ] = 0.0
    outlet_pressure: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="Pa", description="outlet pressure without pressure-drop model"),
    ] = 0.0
    outlet_composition: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="", description="outlet composition vector by species index"),
    ] = np.zeros(0, dtype=np.float64)

    _property_package: PropertyPackage | None = PrivateAttr(default=None)

    @override
    def model_post_init(self, context: Any) -> None:
        super().model_post_init(context)
        if self.n_inlets <= 0:
            raise ValueError("n_inlets must be a positive integer.")
        if self.n_species <= 0:
            raise ValueError("n_species must be a positive integer.")

        self.inlet_flows = _coerce_vector(
            self.inlet_flows,
            expected_size=self.n_inlets,
            name="inlet_flows",
        )
        self.inlet_temperatures = _coerce_vector(
            self.inlet_temperatures,
            expected_size=self.n_inlets,
            name="inlet_temperatures",
            default=298.15,
        )
        self.inlet_pressures = _coerce_vector(
            self.inlet_pressures,
            expected_size=self.n_inlets,
            name="inlet_pressures",
            default=101325.0,
        )
        self.inlet_compositions = _coerce_composition_matrix(
            self.inlet_compositions,
            n_inlets=self.n_inlets,
            n_species=self.n_species,
        )
        self.outlet_composition = _coerce_vector(
            self.outlet_composition,
            expected_size=self.n_species,
            name="outlet_composition",
            default=1.0 / float(self.n_species),
        )

        _validate_vector(self.inlet_flows, name="inlet_flows")
        _validate_vector(self.inlet_temperatures, name="inlet_temperatures")
        _validate_vector(self.inlet_pressures, name="inlet_pressures")
        inlet_comp_matrix = self.inlet_compositions.reshape(self.n_inlets, self.n_species)
        _validate_composition_rows(
            inlet_comp_matrix, n_species=self.n_species, name="inlet_compositions"
        )

    @property
    def ports(self) -> UnitProcessPorts:
        return UnitProcessPorts(
            inlets=tuple(f"inlet_{index + 1}" for index in range(self.n_inlets)),
            outlets=("outlet",),
        )

    def set_property_package(self, package: PropertyPackage | None) -> None:
        self._property_package = package

    @staticmethod
    def _dynamic_inlet_map(port_name: str) -> PortAttributeMap:
        return default_inlet_map(port_name)

    def _resolve_inlet_index(self, port_name: str) -> int:
        valid_ports = self.ports.inlets
        if port_name not in valid_ports:
            allowed_ports = ", ".join(valid_ports)
            raise ValueError(
                f"Invalid inlet port '{port_name}' for {type(self).__name__}. "
                + f"Provided port: {port_name}. Allowed inlet ports: {allowed_ports}."
            )
        return int(port_name.removeprefix("inlet_")) - 1

    def _validate_outlet_port(self, port_name: str) -> None:
        valid_ports = self.ports.outlets
        if port_name not in valid_ports:
            allowed_ports = ", ".join(valid_ports)
            raise ValueError(
                f"Invalid outlet port '{port_name}' for {type(self).__name__}. "
                + f"Provided port: {port_name}. Allowed outlet ports: {allowed_ports}."
            )

    def apply_inlet(self, port_name: str, stream: StreamData) -> None:
        port_map = self._dynamic_inlet_map(port_name)
        inlet_index = self._resolve_inlet_index(port_name)

        self.inlet_flows[inlet_index] = float(stream.molar_flow_rate)
        self.inlet_temperatures[inlet_index] = float(stream.temperature)
        self.inlet_pressures[inlet_index] = float(stream.pressure)

        composition = np.asarray(stream.mole_fractions, dtype=np.float64).reshape(-1)
        if composition.size != self.n_species:
            raise ValueError(
                f"{port_map.composition} length mismatch: expected {self.n_species}, "
                + f"got {composition.size}."
            )
        _validate_composition_rows(
            composition.reshape(1, self.n_species),
            n_species=self.n_species,
            name=port_map.composition,
        )
        composition_matrix = np.asarray(self.inlet_compositions, dtype=np.float64).reshape(
            self.n_inlets, self.n_species
        )
        composition_matrix[inlet_index] = composition
        self.inlet_compositions = composition_matrix.reshape(-1)

    def get_outlet_stream(self, port_name: str) -> StreamData:
        self._validate_outlet_port(port_name)
        port_map = self._OUTLET_MAP[port_name]
        composition = tuple(
            float(value)
            for value in np.asarray(getattr(self, port_map.composition), dtype=np.float64)
        )
        return StreamData(
            temperature=float(getattr(self, port_map.temperature)),
            pressure=float(getattr(self, port_map.pressure)),
            mole_fractions=composition,
            molar_flow_rate=float(getattr(self, port_map.flow)),
        )

    def to_hydraulic_element(self, port_name: str):
        return pipe_hydraulic_element_for_outlet(
            unit_name=type(self).__name__,
            port_name=port_name,
            allowed_outlet_ports=self.ports.outlets,
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

        n_inlets = int(round(float(k[k_map["n_inlets"]])))
        n_species = int(round(float(k[k_map["n_species"]])))
        if n_inlets <= 0:
            raise ValueError("n_inlets must be positive.")
        if n_species <= 0:
            raise ValueError("n_species must be positive.")

        inlet_flows = _vector_from_state(u, u_map["inlet_flows"])
        inlet_temperatures = _vector_from_state(u, u_map["inlet_temperatures"])
        inlet_pressures = _vector_from_state(u, u_map["inlet_pressures"])
        inlet_compositions_flat = _vector_from_state(u, u_map["inlet_compositions"])

        if inlet_flows.size != n_inlets:
            raise ValueError(
                f"inlet_flows length mismatch: expected {n_inlets}, got {inlet_flows.size}."
            )
        if inlet_temperatures.size != n_inlets:
            raise ValueError(
                "inlet_temperatures length mismatch: "
                + f"expected {n_inlets}, got {inlet_temperatures.size}."
            )
        if inlet_pressures.size != n_inlets:
            raise ValueError(
                f"inlet_pressures length mismatch: expected {n_inlets}, got {inlet_pressures.size}."
            )

        expected_comp_size = n_inlets * n_species
        if inlet_compositions_flat.size != expected_comp_size:
            raise ValueError(
                "inlet_compositions length mismatch: "
                + f"expected {expected_comp_size}, got {inlet_compositions_flat.size}."
            )

        _validate_vector(inlet_flows, name="inlet_flows")
        _validate_vector(inlet_temperatures, name="inlet_temperatures")
        _validate_vector(inlet_pressures, name="inlet_pressures")
        inlet_compositions = inlet_compositions_flat.reshape(n_inlets, n_species)
        _validate_composition_rows(
            inlet_compositions, n_species=n_species, name="inlet_compositions"
        )

        outlet_flow = float(np.sum(inlet_flows))
        if outlet_flow > _FLOW_EPSILON:
            outlet_temperature = float(np.dot(inlet_flows, inlet_temperatures) / outlet_flow)
            outlet_composition = (
                np.sum(inlet_compositions * inlet_flows[:, np.newaxis], axis=0) / outlet_flow
            )
        else:
            outlet_temperature = float(np.mean(inlet_temperatures))
            outlet_composition = inlet_compositions[0].copy()

        outlet_pressure = float(np.min(inlet_pressures))
        result = np.zeros(algebraic_size, dtype=np.float64)
        result[algebraic_map["outlet_flow"]] = outlet_flow
        result[algebraic_map["outlet_temperature"]] = outlet_temperature
        result[algebraic_map["outlet_pressure"]] = outlet_pressure
        result[algebraic_map["outlet_composition"]] = outlet_composition
        return result

    @override
    def step(self, dt: Seconds) -> None:
        super().step(dt)

        package = self._property_package
        if package is None:
            return

        if self.outlet_flow <= _FLOW_EPSILON:
            return

        flows = np.asarray(self.inlet_flows, dtype=np.float64)
        positive_mask = flows > 0.0
        if not np.any(positive_mask):
            return

        temperatures = np.asarray(self.inlet_temperatures, dtype=np.float64)
        pressures = np.asarray(self.inlet_pressures, dtype=np.float64)
        compositions = np.asarray(self.inlet_compositions, dtype=np.float64).reshape(
            self.n_inlets, self.n_species
        )

        try:
            weighted_enthalpy = 0.0
            total_positive_flow = float(np.sum(flows[positive_mask]))

            for index in np.flatnonzero(positive_mask):
                flash = package.flash_tp(
                    T=float(temperatures[index]),
                    P=float(pressures[index]),
                    z=tuple(float(value) for value in compositions[index]),
                )
                enthalpy = float(flash.enthalpy_molar)
                if not isfinite(enthalpy):
                    return
                weighted_enthalpy += float(flows[index]) * enthalpy

            mixed_enthalpy = weighted_enthalpy / total_positive_flow
            flash_out = package.flash_ph(
                P=float(self.outlet_pressure),
                H=mixed_enthalpy,
                z=tuple(
                    float(value) for value in np.asarray(self.outlet_composition, dtype=np.float64)
                ),
            )
            self.outlet_temperature = float(flash_out.temperature)
        except Exception:
            return


__all__ = ["Mixer"]

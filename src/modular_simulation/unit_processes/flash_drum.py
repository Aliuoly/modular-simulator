from __future__ import annotations

# pyright: reportMissingTypeStubs=false

from math import isfinite
from typing import Annotated, ClassVar, Literal, cast, override

import numpy as np
from numpy.typing import NDArray
from pydantic import PrivateAttr, field_validator

from modular_simulation.measurables.process_model import StateMetadata as M
from modular_simulation.measurables.process_model import StateType as T
from modular_simulation.thermodynamics.algebraic_process_model import (
    AlgebraicProcessModel,
    UnitProcessPorts,
)
from modular_simulation.thermodynamics.hydraulic_adapters import pipe_hydraulic_element_for_outlet
from modular_simulation.thermodynamics.property_package import PropertyPackage
from modular_simulation.thermodynamics.stream import PortAttributeMap, StreamData
from modular_simulation.utils.typing import ArrayIndex, Seconds

_FLOW_EPSILON = 1.0e-12
_COMPOSITION_TOL = 1.0e-8
_TINY_POSITIVE_PRESSURE = 1.0e-9
_PHASE_FRACTION_EPS = 1.0e-9

_MODE_ADIABATIC = 0.0
_MODE_ISOTHERMAL = 1.0

FLASH_DRUM_PORTS = UnitProcessPorts(("inlet",), ("vapor_outlet", "liquid_outlet"))


def _normalize_mode(mode: str) -> Literal["adiabatic", "isothermal"]:
    normalized = mode.strip().casefold()
    if normalized not in {"adiabatic", "isothermal"}:
        raise ValueError("thermal_mode must be either 'adiabatic' or 'isothermal'.")
    return cast(Literal["adiabatic", "isothermal"], normalized)


def _mode_from_selector(selector: float) -> Literal["adiabatic", "isothermal"]:
    if abs(selector - _MODE_ADIABATIC) < 0.5:
        return "adiabatic"
    if abs(selector - _MODE_ISOTHERMAL) < 0.5:
        return "isothermal"
    raise ValueError("thermal_mode selector must encode either adiabatic or isothermal mode.")


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


def _normalize_composition(
    composition: tuple[float, ...] | None, fallback: NDArray[np.float64]
) -> NDArray[np.float64]:
    if composition is None:
        return fallback.copy()

    vector = np.asarray(composition, dtype=np.float64).reshape(-1)
    if vector.size != fallback.size:
        return fallback.copy()
    if not np.all(np.isfinite(vector)):
        return fallback.copy()
    vector = np.clip(vector, 0.0, None)
    total = float(np.sum(vector))
    if total <= _FLOW_EPSILON:
        return fallback.copy()
    return vector / total


class FlashDrum(AlgebraicProcessModel):
    _INLET_MAP: ClassVar[dict[str, PortAttributeMap]] = {
        "inlet": PortAttributeMap(
            flow="inlet_flow",
            temperature="inlet_temperature",
            pressure="inlet_pressure",
            composition="inlet_composition",
        )
    }
    _OUTLET_MAP: ClassVar[dict[str, PortAttributeMap]] = {
        "vapor_outlet": PortAttributeMap(
            flow="vapor_flow",
            temperature="outlet_temperature",
            pressure="outlet_pressure",
            composition="vapor_composition",
        ),
        "liquid_outlet": PortAttributeMap(
            flow="liquid_flow",
            temperature="outlet_temperature",
            pressure="outlet_pressure",
            composition="liquid_composition",
        ),
    }

    thermal_mode: Annotated[
        float | Literal["adiabatic", "isothermal"],
        M(type=T.CONSTANT, unit="", description="thermal mode selector: 0=adiabatic, 1=isothermal"),
    ] = _MODE_ISOTHERMAL
    n_species: Annotated[int, M(type=T.CONSTANT, unit="", description="number of species")] = 2

    inlet_flow: Annotated[
        float,
        M(type=T.BOUNDARY, unit="mol/s", description="inlet molar flow rate"),
    ] = 0.0
    inlet_temperature: Annotated[
        float,
        M(type=T.BOUNDARY, unit="K", description="inlet temperature"),
    ] = 298.15
    inlet_pressure: Annotated[
        float,
        M(type=T.BOUNDARY, unit="Pa", description="inlet pressure"),
    ] = 101325.0
    inlet_composition: Annotated[
        NDArray[np.float64],
        M(type=T.BOUNDARY, unit="", description="inlet composition vector by species index"),
    ] = np.zeros(0, dtype=np.float64)
    imposed_pressure: Annotated[
        float,
        M(type=T.BOUNDARY, unit="Pa", description="externally imposed flash pressure boundary"),
    ] = 101325.0
    imposed_temperature: Annotated[
        float,
        M(
            type=T.BOUNDARY,
            unit="K",
            description="externally imposed isothermal flash temperature boundary",
        ),
    ] = 298.15

    outlet_temperature: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="K", description="flash outlet temperature"),
    ] = 298.15
    vapor_fraction: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="", description="vapor fraction in flash drum"),
    ] = 0.0
    vapor_flow: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="mol/s", description="vapor outlet molar flow"),
    ] = 0.0
    liquid_flow: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="mol/s", description="liquid outlet molar flow"),
    ] = 0.0
    vapor_composition: Annotated[
        NDArray[np.float64],
        M(
            type=T.ALGEBRAIC,
            unit="",
            description="vapor outlet composition vector by species index",
        ),
    ] = np.zeros(0, dtype=np.float64)
    liquid_composition: Annotated[
        NDArray[np.float64],
        M(
            type=T.ALGEBRAIC,
            unit="",
            description="liquid outlet composition vector by species index",
        ),
    ] = np.zeros(0, dtype=np.float64)

    _property_package: PropertyPackage | None = PrivateAttr(default=None)

    @field_validator("thermal_mode", mode="before")
    @classmethod
    def _parse_mode(cls, value: object) -> float:
        if isinstance(value, str):
            normalized = _normalize_mode(value)
            return _MODE_ADIABATIC if normalized == "adiabatic" else _MODE_ISOTHERMAL
        if not isinstance(value, (int, float)):
            raise ValueError("thermal_mode must be either 'adiabatic' or 'isothermal'.")
        numeric_mode = float(value)
        normalized = _mode_from_selector(numeric_mode)
        return _MODE_ADIABATIC if normalized == "adiabatic" else _MODE_ISOTHERMAL

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
        self.vapor_composition = _coerce_vector(
            self.vapor_composition,
            expected_size=self.n_species,
            name="vapor_composition",
            default=1.0 / float(self.n_species),
        )
        self.liquid_composition = _coerce_vector(
            self.liquid_composition,
            expected_size=self.n_species,
            name="liquid_composition",
            default=1.0 / float(self.n_species),
        )

        if not isfinite(self.inlet_flow) or self.inlet_flow < 0.0:
            raise ValueError("inlet_flow must be finite and non-negative.")
        if not isfinite(self.inlet_temperature):
            raise ValueError("inlet_temperature must be finite.")
        if not isfinite(self.inlet_pressure) or self.inlet_pressure <= 0.0:
            raise ValueError("inlet_pressure must be finite and positive.")
        if not isfinite(self.imposed_pressure) or self.imposed_pressure <= 0.0:
            raise ValueError("imposed_pressure must be finite and positive.")
        if not isfinite(self.imposed_temperature):
            raise ValueError("imposed_temperature must be finite.")

        _validate_composition(self.inlet_composition, name="inlet_composition")

    @property
    def ports(self) -> UnitProcessPorts:
        return FLASH_DRUM_PORTS

    def set_property_package(self, package: PropertyPackage | None) -> None:
        self._property_package = package

    @property
    def outlet_pressure(self) -> float:
        return float(self.imposed_pressure)

    @outlet_pressure.setter
    def outlet_pressure(self, value: float) -> None:
        self.imposed_pressure = float(value)

    def apply_inlet(self, port_name: str, stream: StreamData) -> None:
        if port_name not in self.ports.inlets:
            valid_ports = ", ".join(self.ports.inlets)
            raise ValueError(
                f"Invalid inlet port '{port_name}' for {type(self).__name__}. Valid inlet ports: {valid_ports}."
            )

        port_map = self._INLET_MAP[port_name]
        setattr(self, port_map.flow, float(stream.molar_flow_rate))
        setattr(self, port_map.temperature, float(stream.temperature))
        setattr(self, port_map.pressure, float(stream.pressure))
        setattr(self, port_map.composition, np.asarray(stream.mole_fractions, dtype=np.float64))

    def get_outlet_stream(self, port_name: str) -> StreamData:
        if port_name not in self.ports.outlets:
            valid_ports = ", ".join(self.ports.outlets)
            raise ValueError(
                f"Invalid outlet port '{port_name}' for {type(self).__name__}. Valid outlet ports: {valid_ports}."
            )

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

        n_species = int(round(float(k[k_map["n_species"]])))
        if n_species <= 0:
            raise ValueError("n_species must be positive.")

        mode = _mode_from_selector(float(k[k_map["thermal_mode"]]))
        inlet_flow = float(u[u_map["inlet_flow"]])
        inlet_temperature = float(u[u_map["inlet_temperature"]])
        inlet_pressure = float(u[u_map["inlet_pressure"]])
        inlet_composition = _vector_from_state(u, u_map["inlet_composition"])
        flash_pressure = float(u[u_map["imposed_pressure"]])
        flash_temperature = float(u[u_map["imposed_temperature"]])

        if not isfinite(inlet_flow) or inlet_flow < 0.0:
            raise ValueError("inlet_flow must be finite and non-negative.")
        if not isfinite(inlet_temperature):
            raise ValueError("inlet_temperature must be finite.")
        if not isfinite(inlet_pressure) or inlet_pressure <= 0.0:
            raise ValueError("inlet_pressure must be finite and positive.")
        if not isfinite(flash_pressure) or flash_pressure <= 0.0:
            raise ValueError("imposed_pressure must be finite and positive.")
        if not isfinite(flash_temperature):
            raise ValueError("imposed_temperature must be finite.")
        if inlet_composition.size != n_species:
            raise ValueError(
                f"inlet_composition length mismatch: expected {n_species}, got {inlet_composition.size}."
            )

        _validate_composition(inlet_composition, name="inlet_composition")

        outlet_temperature = flash_temperature if mode == "isothermal" else inlet_temperature
        vapor_fraction = 0.0

        result = np.zeros(algebraic_size, dtype=np.float64)
        result[algebraic_map["outlet_temperature"]] = outlet_temperature
        result[algebraic_map["vapor_fraction"]] = vapor_fraction
        result[algebraic_map["vapor_flow"]] = inlet_flow * vapor_fraction
        result[algebraic_map["liquid_flow"]] = inlet_flow * (1.0 - vapor_fraction)
        result[algebraic_map["vapor_composition"]] = inlet_composition
        result[algebraic_map["liquid_composition"]] = inlet_composition
        return result

    @override
    def step(self, dt: Seconds) -> None:
        super().step(dt)

        package = self._property_package
        if package is None:
            return

        mode = _mode_from_selector(float(self.thermal_mode))
        z_array = np.asarray(self.inlet_composition, dtype=np.float64)
        z = tuple(cast(list[float], z_array.tolist()))

        outlet_pressure = max(float(self.imposed_pressure), _TINY_POSITIVE_PRESSURE)
        if mode == "isothermal":
            flash = package.flash_tp(
                T=float(self.imposed_temperature),
                P=outlet_pressure,
                z=z,
            )
        else:
            inlet_flash = package.flash_tp(
                T=float(self.inlet_temperature),
                P=max(float(self.inlet_pressure), _TINY_POSITIVE_PRESSURE),
                z=z,
            )
            flash = package.flash_ph(
                P=outlet_pressure,
                H=float(inlet_flash.enthalpy_molar),
                z=z,
            )

        vf = float(flash.vapor_fraction)
        if vf < _PHASE_FRACTION_EPS:
            vf = 0.0
        elif vf > 1.0 - _PHASE_FRACTION_EPS:
            vf = 1.0
        vf = min(max(vf, 0.0), 1.0)

        liquid_comp = _normalize_composition(flash.liquid_composition, z_array)
        vapor_comp = _normalize_composition(flash.vapor_composition, z_array)

        if vf <= _PHASE_FRACTION_EPS:
            vapor_comp = z_array.copy()
        if (1.0 - vf) <= _PHASE_FRACTION_EPS:
            liquid_comp = z_array.copy()

        inlet_flow = float(self.inlet_flow)
        self.vapor_fraction = vf
        self.vapor_flow = inlet_flow * vf
        self.liquid_flow = inlet_flow * (1.0 - vf)
        self.vapor_composition = vapor_comp
        self.liquid_composition = liquid_comp
        self.outlet_temperature = float(flash.temperature)


__all__ = ["FLASH_DRUM_PORTS", "FlashDrum"]

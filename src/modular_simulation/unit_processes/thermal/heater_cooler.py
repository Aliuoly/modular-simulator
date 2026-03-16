from __future__ import annotations

# pyright: reportMissingTypeStubs=false, reportMissingImports=false

from math import isfinite
from typing import Annotated, ClassVar, Literal, cast, override

import numpy as np
from numpy.typing import NDArray
from pydantic import PrivateAttr, field_validator

from modular_simulation.measurables.process_model import StateMetadata as M
from modular_simulation.measurables.process_model import StateType as T
from modular_simulation.thermodynamics.algebraic_process_model import (
    AlgebraicProcessModel,
    SINGLE_IO,
    UnitProcessPorts,
)
from modular_simulation.thermodynamics.hydraulic_adapters import pipe_hydraulic_element_for_outlet
from modular_simulation.thermodynamics.stream import PortAttributeMap, StreamData
from modular_simulation.thermodynamics.property_package import PropertyPackage
from modular_simulation.utils.typing import ArrayIndex, Seconds

_FLOW_EPSILON = 1.0e-12
_DUTY_EPSILON = 1.0e-12
_COMPOSITION_TOL = 1.0e-8
_TINY_POSITIVE_PRESSURE = 1.0e-9

_MODE_DUTY = 0.0
_MODE_TEMPERATURE = 1.0


def _normalize_mode(mode: str) -> Literal["duty", "temperature"]:
    normalized = mode.strip().casefold()
    if normalized not in {"duty", "temperature"}:
        raise ValueError("mode must be either 'duty' or 'temperature'.")
    return cast(Literal["duty", "temperature"], normalized)


def _mode_from_selector(selector: float) -> Literal["duty", "temperature"]:
    if abs(selector - _MODE_DUTY) < 0.5:
        return "duty"
    if abs(selector - _MODE_TEMPERATURE) < 0.5:
        return "temperature"
    raise ValueError("mode_selector must encode either duty or temperature mode.")


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


class HeaterCooler(AlgebraicProcessModel):
    _INLET_MAP: ClassVar[dict[str, PortAttributeMap]] = {
        "inlet": PortAttributeMap(
            flow="inlet_flow",
            temperature="inlet_temperature",
            pressure="inlet_pressure",
            composition="inlet_composition",
        )
    }
    _OUTLET_MAP: ClassVar[dict[str, PortAttributeMap]] = {
        "outlet": PortAttributeMap(
            flow="outlet_flow",
            temperature="outlet_temperature",
            pressure="outlet_pressure",
            composition="outlet_composition",
        )
    }
    _WELL_MIXED_EXTERNAL_HEAT_BOUNDARIES: ClassVar[tuple[str, ...]] = (
        "external_heat_duty",
        "external_outlet_temperature",
    )

    mode: Annotated[
        float | Literal["duty", "temperature"],
        M(type=T.CONSTANT, unit="", description="mode selector: 0=duty, 1=temperature"),
    ] = _MODE_DUTY

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
    pressure_drop: Annotated[
        float,
        M(type=T.CONSTANT, unit="Pa", description="fixed hydraulic pressure drop across the unit"),
    ] = 0.0
    external_heat_duty: Annotated[
        float,
        M(
            type=T.BOUNDARY,
            unit="W",
            description="well-mixed external heat-duty boundary used in direct-duty mode",
        ),
    ] = 0.0
    external_outlet_temperature: Annotated[
        float,
        M(
            type=T.BOUNDARY,
            unit="K",
            description="well-mixed external outlet-temperature boundary used in direct-temperature mode",
        ),
    ] = 298.15

    outlet_flow: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="mol/s", description="outlet molar flow rate"),
    ] = 0.0
    outlet_pressure: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="Pa", description="outlet pressure after pressure drop"),
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
    duty: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="W", description="calculated heat duty"),
    ] = 0.0

    _property_package: PropertyPackage | None = PrivateAttr(default=None)

    @field_validator("mode", mode="before")
    @classmethod
    def _parse_mode(cls, value: object) -> float:
        if isinstance(value, str):
            normalized = _normalize_mode(value)
            return _MODE_DUTY if normalized == "duty" else _MODE_TEMPERATURE
        if not isinstance(value, (int, float)):
            raise ValueError("mode must be either 'duty' or 'temperature'.")
        numeric_mode = float(value)
        normalized = _mode_from_selector(numeric_mode)
        return _MODE_DUTY if normalized == "duty" else _MODE_TEMPERATURE

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
        if not isfinite(self.pressure_drop) or self.pressure_drop < 0.0:
            raise ValueError("pressure_drop must be finite and non-negative.")
        if not isfinite(self.external_heat_duty):
            raise ValueError("external_heat_duty must be finite.")
        if not isfinite(self.external_outlet_temperature):
            raise ValueError("external_outlet_temperature must be finite.")

        _validate_composition(self.inlet_composition, name="inlet_composition")

    @property
    def ports(self) -> UnitProcessPorts:
        return SINGLE_IO

    def set_property_package(self, package: PropertyPackage | None) -> None:
        self._property_package = package

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

        mode = _mode_from_selector(float(k[k_map["mode"]]))
        inlet_flow = float(u[u_map["inlet_flow"]])
        inlet_temperature = float(u[u_map["inlet_temperature"]])
        inlet_pressure = float(u[u_map["inlet_pressure"]])
        inlet_composition = _vector_from_state(u, u_map["inlet_composition"])
        pressure_drop = float(k[k_map["pressure_drop"]])
        external_heat_duty = float(u[u_map["external_heat_duty"]])
        external_outlet_temperature = float(u[u_map["external_outlet_temperature"]])

        if not isfinite(inlet_flow) or inlet_flow < 0.0:
            raise ValueError("inlet_flow must be finite and non-negative.")
        if not isfinite(inlet_temperature):
            raise ValueError("inlet_temperature must be finite.")
        if not isfinite(inlet_pressure) or inlet_pressure <= 0.0:
            raise ValueError("inlet_pressure must be finite and positive.")
        if not isfinite(pressure_drop) or pressure_drop < 0.0:
            raise ValueError("pressure_drop must be finite and non-negative.")
        if not isfinite(external_heat_duty):
            raise ValueError("external_heat_duty must be finite.")
        if not isfinite(external_outlet_temperature):
            raise ValueError("external_outlet_temperature must be finite.")
        if inlet_composition.size != n_species:
            raise ValueError(
                f"inlet_composition length mismatch: expected {n_species}, got {inlet_composition.size}."
            )

        _validate_composition(inlet_composition, name="inlet_composition")

        outlet_pressure = max(inlet_pressure - pressure_drop, _TINY_POSITIVE_PRESSURE)
        if (
            mode == "duty"
            and inlet_flow <= _FLOW_EPSILON
            and abs(external_heat_duty) > _DUTY_EPSILON
        ):
            raise ValueError(
                "duty mode requires positive inlet_flow when external_heat_duty is non-zero."
            )

        outlet_temperature = inlet_temperature if mode == "duty" else external_outlet_temperature
        duty = external_heat_duty if mode == "duty" else 0.0

        result = np.zeros(algebraic_size, dtype=np.float64)
        result[algebraic_map["outlet_flow"]] = inlet_flow
        result[algebraic_map["outlet_pressure"]] = outlet_pressure
        result[algebraic_map["outlet_temperature"]] = outlet_temperature
        result[algebraic_map["outlet_composition"]] = inlet_composition
        result[algebraic_map["outlet_enthalpy"]] = 0.0
        result[algebraic_map["duty"]] = duty
        return result

    @override
    def step(self, dt: Seconds) -> None:
        super().step(dt)

        package = self._property_package
        if package is None:
            return

        mode = _mode_from_selector(float(self.mode))

        composition_array = np.asarray(self.inlet_composition, dtype=np.float64)
        z = tuple(cast(list[float], composition_array.tolist()))
        inlet_pressure = float(self.inlet_pressure)
        outlet_pressure = max(inlet_pressure - float(self.pressure_drop), _TINY_POSITIVE_PRESSURE)
        inlet_flow = float(self.inlet_flow)

        flash_in = package.flash_tp(T=float(self.inlet_temperature), P=inlet_pressure, z=z)
        h_in = float(flash_in.enthalpy_molar)

        if inlet_flow <= _FLOW_EPSILON:
            if mode == "duty" and abs(float(self.external_heat_duty)) > _DUTY_EPSILON:
                raise ValueError(
                    "duty mode requires positive inlet_flow when external_heat_duty is non-zero."
                )

            if mode == "temperature":
                flash_out = package.flash_tp(
                    T=float(self.external_outlet_temperature),
                    P=outlet_pressure,
                    z=z,
                )
                self.outlet_temperature = float(flash_out.temperature)
                self.outlet_enthalpy = float(flash_out.enthalpy_molar)
            else:
                self.outlet_temperature = float(self.inlet_temperature)
                self.outlet_enthalpy = h_in
            self.duty = 0.0
            self.outlet_flow = inlet_flow
            self.outlet_pressure = outlet_pressure
            self.outlet_composition = np.asarray(self.inlet_composition, dtype=np.float64)
            return

        if mode == "duty":
            target_enthalpy = h_in + float(self.external_heat_duty) / inlet_flow
            flash_out = package.flash_ph(P=outlet_pressure, H=target_enthalpy, z=z)
        else:
            flash_out = package.flash_tp(
                T=float(self.external_outlet_temperature),
                P=outlet_pressure,
                z=z,
            )

        h_out = float(flash_out.enthalpy_molar)
        self.outlet_flow = inlet_flow
        self.outlet_pressure = outlet_pressure
        self.outlet_temperature = float(flash_out.temperature)
        self.outlet_composition = np.asarray(self.inlet_composition, dtype=np.float64)
        self.outlet_enthalpy = h_out
        self.duty = inlet_flow * (h_out - h_in)


__all__ = ["HeaterCooler"]

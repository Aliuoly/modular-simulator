from __future__ import annotations

# pyright: reportMissingTypeStubs=false, reportUnknownArgumentType=false, reportUnknownVariableType=false, reportArgumentType=false, reportImplicitStringConcatenation=false

from collections.abc import Mapping, Sequence
from math import isfinite
from typing import Annotated, Any, ClassVar, Literal, cast, override

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
from modular_simulation.thermodynamics.property_package import PropertyPackage
from modular_simulation.thermodynamics.stream import PortAttributeMap, StreamData
from modular_simulation.utils.typing import ArrayIndex, Seconds

_FLOW_EPSILON = 1.0e-12
_COMPOSITION_TOL = 1.0e-8
_TINY_POSITIVE_PRESSURE = 1.0e-9
_STOICH_TOL = 1.0e-12

_MODE_ADIABATIC = 0.0
_MODE_ISOTHERMAL = 1.0


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


def _build_label_index(n_species: int, species_order: Sequence[str] | None) -> dict[str, int]:
    label_index: dict[str, int] = {}
    if species_order is not None:
        if len(species_order) != n_species:
            raise ValueError(
                "species_order length must match n_species when configuring conversions by name."
            )
        for index, label in enumerate(species_order):
            normalized = str(label).strip()
            if not normalized:
                raise ValueError("species_order entries must be non-empty strings.")
            if normalized in label_index:
                raise ValueError(f"Duplicate species label '{normalized}' in species_order.")
            label_index[normalized] = index
        return label_index

    for index in range(n_species):
        label_index[str(index)] = index
        label_index[f"species_{index + 1}"] = index
    return label_index


def _resolve_species_index(label_index: Mapping[str, int], raw_key: object, n_species: int) -> int:
    if isinstance(raw_key, (int, np.integer)):
        index = int(raw_key)
    else:
        key = str(raw_key).strip()
        if key in label_index:
            return int(label_index[key])

        if key.startswith("species_"):
            suffix = key[len("species_") :]
            if suffix.isdigit():
                one_based = int(suffix) - 1
                if 0 <= one_based < n_species:
                    return one_based

        if key.isdigit():
            index = int(key)
        else:
            raise ValueError(
                f"Unknown species key '{raw_key}'. Provide species_order for named conversions."
            )

    if index < 0 or index >= n_species:
        raise ValueError(f"Species index {index} out of bounds for n_species={n_species}.")
    return index


def _validate_conversion_fractions(conversion_fractions: NDArray[np.float64]) -> None:
    if not np.all(np.isfinite(conversion_fractions)):
        raise ValueError("conversion_fractions must contain only finite values.")
    for index, value in enumerate(conversion_fractions):
        if value < 0.0 or value > 1.0:
            raise ValueError(
                f"Invalid conversion at species index {index}: {value}. "
                "Conversion must be within [0, 1]."
            )


def _coerce_reaction_configuration(
    *,
    n_species: int,
    conversions: object,
    stoichiometry: object,
    species_order: Sequence[str] | None,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    label_index = _build_label_index(n_species, species_order)
    conversion_fractions = np.zeros(n_species, dtype=np.float64)

    if conversions is None:
        pass
    elif isinstance(conversions, Mapping):
        for species_key, raw_value in conversions.items():
            species_index = _resolve_species_index(label_index, species_key, n_species)
            conversion_fractions[species_index] = float(raw_value)
    else:
        vector = np.asarray(conversions, dtype=np.float64).reshape(-1)
        if vector.size != n_species:
            raise ValueError(
                "conversions length mismatch: " + f"expected {n_species}, got {vector.size}."
            )
        conversion_fractions = vector

    _validate_conversion_fractions(conversion_fractions)

    stoichiometric_matrix = np.zeros((n_species, n_species), dtype=np.float64)
    if stoichiometry is None:
        pass
    elif isinstance(stoichiometry, Mapping):
        numeric_values = all(
            isinstance(value, (int, float, np.floating, np.integer))
            for value in stoichiometry.values()
        )
        if numeric_values:
            active_indices = np.flatnonzero(conversion_fractions > 0.0)
            if active_indices.size != 1:
                raise ValueError(
                    "Single reaction stoichiometry mapping requires exactly one converted species."
                )
            basis_index = int(active_indices[0])
            for species_key, coefficient in stoichiometry.items():
                species_index = _resolve_species_index(label_index, species_key, n_species)
                stoichiometric_matrix[species_index, basis_index] = float(coefficient)
        else:
            for basis_key, mapping in stoichiometry.items():
                if not isinstance(mapping, Mapping):
                    raise ValueError(
                        "stoichiometry must map each basis species to a species-coefficient mapping."
                    )
                basis_index = _resolve_species_index(label_index, basis_key, n_species)
                for species_key, coefficient in mapping.items():
                    species_index = _resolve_species_index(label_index, species_key, n_species)
                    stoichiometric_matrix[species_index, basis_index] = float(coefficient)
    else:
        matrix = np.asarray(stoichiometry, dtype=np.float64)
        if matrix.shape == (n_species, n_species):
            stoichiometric_matrix = matrix
        else:
            flat_matrix = matrix.reshape(-1)
            if flat_matrix.size != n_species * n_species:
                raise ValueError(
                    "stoichiometry length mismatch: "
                    + f"expected {n_species * n_species}, got {flat_matrix.size}."
                )
            stoichiometric_matrix = flat_matrix.reshape(n_species, n_species)

    for species_index, conversion in enumerate(conversion_fractions):
        if conversion <= 0.0:
            continue
        if not np.any(np.abs(stoichiometric_matrix[:, species_index]) > _STOICH_TOL):
            stoichiometric_matrix[species_index, species_index] = -1.0

        basis_coefficient = float(stoichiometric_matrix[species_index, species_index])
        if basis_coefficient >= -_STOICH_TOL:
            raise ValueError(
                "Stoichiometry for converted species index "
                + f"{species_index} must include a negative basis coefficient."
            )

    return conversion_fractions, stoichiometric_matrix


def _apply_conversions(
    *,
    inlet_component_flows: NDArray[np.float64],
    conversion_fractions: NDArray[np.float64],
    stoichiometric_matrix: NDArray[np.float64],
) -> NDArray[np.float64]:
    component_changes = np.zeros_like(inlet_component_flows)

    for species_index, conversion in enumerate(conversion_fractions):
        if conversion <= 0.0:
            continue

        basis_coefficient = float(stoichiometric_matrix[species_index, species_index])
        if basis_coefficient >= -_STOICH_TOL:
            raise ValueError(
                "Stoichiometry for converted species index "
                + f"{species_index} must include a negative basis coefficient."
            )

        consumed = float(inlet_component_flows[species_index]) * float(conversion)
        reaction_extent = consumed / (-basis_coefficient)
        component_changes += stoichiometric_matrix[:, species_index] * reaction_extent

    outlet_component_flows = inlet_component_flows + component_changes
    if np.any(outlet_component_flows < -_STOICH_TOL):
        raise ValueError(
            "Configured conversions and stoichiometry consume more moles than available for at least one species."
        )
    return np.clip(outlet_component_flows, 0.0, None)


class ConversionReactor(AlgebraicProcessModel):
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

    thermal_mode: Annotated[
        float | Literal["adiabatic", "isothermal"],
        M(type=T.CONSTANT, unit="", description="thermal mode selector: 0=adiabatic, 1=isothermal"),
    ] = _MODE_ADIABATIC
    n_species: Annotated[int, M(type=T.CONSTANT, unit="", description="number of species")] = 2
    pressure_drop: Annotated[
        float,
        M(
            type=T.CONSTANT,
            unit="Pa",
            description="fixed hydraulic pressure drop across the reactor",
        ),
    ] = 0.0
    conversion_fractions: Annotated[
        NDArray[np.float64],
        M(
            type=T.CONSTANT,
            unit="",
            description="conversion fraction vector by species index, bounded in [0, 1]",
        ),
    ] = np.zeros(0, dtype=np.float64)
    stoichiometric_matrix: Annotated[
        NDArray[np.float64],
        M(
            type=T.CONSTANT,
            unit="",
            description="flattened stoichiometric matrix (n_species x n_species), columns keyed by converted species",
        ),
    ] = np.zeros(0, dtype=np.float64)

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

    outlet_flow: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="mol/s", description="outlet molar flow rate"),
    ] = 0.0
    outlet_temperature: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="K", description="outlet temperature"),
    ] = 298.15
    outlet_pressure: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="Pa", description="outlet pressure after pressure drop"),
    ] = 101325.0
    outlet_composition: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="", description="outlet composition vector by species index"),
    ] = np.zeros(0, dtype=np.float64)
    outlet_enthalpy: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="J/mol", description="outlet molar enthalpy"),
    ] = 0.0

    _property_package: PropertyPackage | None = PrivateAttr(default=None)

    def __init__(self, **data: Any) -> None:
        raw_conversions = data.pop("conversions", None)
        raw_stoichiometry = data.pop("stoichiometry", None)
        raw_species_order = data.pop("species_order", None)

        if raw_conversions is not None and "conversion_fractions" in data:
            raise ValueError("Provide either 'conversions' or 'conversion_fractions', not both.")
        if raw_stoichiometry is not None and "stoichiometric_matrix" in data:
            raise ValueError("Provide either 'stoichiometry' or 'stoichiometric_matrix', not both.")

        if raw_conversions is not None or raw_stoichiometry is not None:
            n_species = int(data.get("n_species", 2))
            species_order = (
                tuple(str(value) for value in raw_species_order)
                if raw_species_order is not None
                else None
            )
            conversion_fractions, stoichiometric_matrix = _coerce_reaction_configuration(
                n_species=n_species,
                conversions=raw_conversions,
                stoichiometry=raw_stoichiometry,
                species_order=species_order,
            )
            data["conversion_fractions"] = conversion_fractions
            data["stoichiometric_matrix"] = stoichiometric_matrix.reshape(-1)

        super().__init__(**data)

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
        if not isfinite(self.pressure_drop) or self.pressure_drop < 0.0:
            raise ValueError("pressure_drop must be finite and non-negative.")

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
        self.conversion_fractions = _coerce_vector(
            self.conversion_fractions,
            expected_size=self.n_species,
            name="conversion_fractions",
            default=0.0,
        )
        self.stoichiometric_matrix = _coerce_vector(
            self.stoichiometric_matrix,
            expected_size=self.n_species * self.n_species,
            name="stoichiometric_matrix",
            default=0.0,
        )

        _validate_conversion_fractions(np.asarray(self.conversion_fractions, dtype=np.float64))
        _validate_composition(
            np.asarray(self.inlet_composition, dtype=np.float64), name="inlet_composition"
        )

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

        inlet_flow = float(u[u_map["inlet_flow"]])
        inlet_temperature = float(u[u_map["inlet_temperature"]])
        inlet_pressure = float(u[u_map["inlet_pressure"]])
        inlet_composition = _vector_from_state(u, u_map["inlet_composition"])
        pressure_drop = float(k[k_map["pressure_drop"]])

        conversion_fractions = _vector_from_state(k, k_map["conversion_fractions"])
        stoichiometric_flat = _vector_from_state(k, k_map["stoichiometric_matrix"])

        if not isfinite(inlet_flow) or inlet_flow < 0.0:
            raise ValueError("inlet_flow must be finite and non-negative.")
        if not isfinite(inlet_temperature):
            raise ValueError("inlet_temperature must be finite.")
        if not isfinite(inlet_pressure) or inlet_pressure <= 0.0:
            raise ValueError("inlet_pressure must be finite and positive.")
        if not isfinite(pressure_drop) or pressure_drop < 0.0:
            raise ValueError("pressure_drop must be finite and non-negative.")
        if inlet_composition.size != n_species:
            raise ValueError(
                f"inlet_composition length mismatch: expected {n_species}, got {inlet_composition.size}."
            )
        if conversion_fractions.size != n_species:
            raise ValueError(
                "conversion_fractions length mismatch: "
                + f"expected {n_species}, got {conversion_fractions.size}."
            )
        if stoichiometric_flat.size != n_species * n_species:
            raise ValueError(
                "stoichiometric_matrix length mismatch: "
                + f"expected {n_species * n_species}, got {stoichiometric_flat.size}."
            )

        _validate_composition(inlet_composition, name="inlet_composition")
        _validate_conversion_fractions(conversion_fractions)

        stoichiometric_matrix = stoichiometric_flat.reshape(n_species, n_species)
        inlet_component_flows = inlet_flow * inlet_composition
        outlet_component_flows = _apply_conversions(
            inlet_component_flows=inlet_component_flows,
            conversion_fractions=conversion_fractions,
            stoichiometric_matrix=stoichiometric_matrix,
        )

        outlet_flow = float(np.sum(outlet_component_flows))
        if outlet_flow <= _FLOW_EPSILON:
            outlet_composition = inlet_composition
            outlet_flow = 0.0
        else:
            outlet_composition = outlet_component_flows / outlet_flow

        outlet_pressure = max(inlet_pressure - pressure_drop, _TINY_POSITIVE_PRESSURE)

        result = np.zeros(algebraic_size, dtype=np.float64)
        result[algebraic_map["outlet_flow"]] = outlet_flow
        result[algebraic_map["outlet_temperature"]] = inlet_temperature
        result[algebraic_map["outlet_pressure"]] = outlet_pressure
        result[algebraic_map["outlet_composition"]] = outlet_composition
        result[algebraic_map["outlet_enthalpy"]] = 0.0
        return result

    @override
    def step(self, dt: Seconds) -> None:
        super().step(dt)

        package = self._property_package
        if package is None:
            if _mode_from_selector(float(self.thermal_mode)) == "isothermal":
                self.outlet_temperature = float(self.inlet_temperature)
            return

        inlet_z = tuple(
            float(value) for value in np.asarray(self.inlet_composition, dtype=np.float64)
        )
        outlet_z = tuple(
            float(value) for value in np.asarray(self.outlet_composition, dtype=np.float64)
        )

        inlet_flash = package.flash_tp(
            T=float(self.inlet_temperature),
            P=float(self.inlet_pressure),
            z=inlet_z,
        )
        inlet_enthalpy = float(inlet_flash.enthalpy_molar)

        if _mode_from_selector(float(self.thermal_mode)) == "isothermal":
            outlet_flash = package.flash_tp(
                T=float(self.inlet_temperature),
                P=max(float(self.outlet_pressure), _TINY_POSITIVE_PRESSURE),
                z=outlet_z,
            )
            self.outlet_temperature = float(self.inlet_temperature)
            self.outlet_enthalpy = float(outlet_flash.enthalpy_molar)
            return

        outlet_flash = package.flash_ph(
            P=max(float(self.outlet_pressure), _TINY_POSITIVE_PRESSURE),
            H=inlet_enthalpy,
            z=outlet_z,
        )
        self.outlet_temperature = float(outlet_flash.temperature)
        self.outlet_enthalpy = float(outlet_flash.enthalpy_molar)


__all__ = ["ConversionReactor"]

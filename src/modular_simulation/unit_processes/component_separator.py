from __future__ import annotations

# pyright: reportMissingTypeStubs=false

from collections.abc import Mapping, Sequence
from math import isfinite
from typing import Annotated, cast, override

import numpy as np
from numpy.typing import NDArray

from modular_simulation.measurables.process_model import StateMetadata as M
from modular_simulation.measurables.process_model import StateType as T
from modular_simulation.thermodynamics.algebraic_process_model import (
    AlgebraicProcessModel,
    DUAL_OUTLET,
    UnitProcessPorts,
)
from modular_simulation.utils.typing import ArrayIndex

_FLOW_EPSILON = 1.0e-12
_COMPOSITION_TOL = 1.0e-8


def _vector_from_state(values: NDArray[np.float64], index: ArrayIndex) -> NDArray[np.float64]:
    return np.asarray(values[index], dtype=np.float64).reshape(-1)


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


def _validate_split_fractions(split_fractions: NDArray[np.float64]) -> None:
    if not np.all(np.isfinite(split_fractions)):
        raise ValueError("split_fractions must contain only finite values.")
    if np.any(split_fractions < 0.0) or np.any(split_fractions > 1.0):
        raise ValueError("split_fractions must stay within [0, 1].")


def _build_label_index(n_species: int, species_order: Sequence[str] | None) -> dict[str, int]:
    label_index: dict[str, int] = {}
    if species_order is not None:
        if len(species_order) != n_species:
            raise ValueError("species_order length must match n_species.")
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
    if isinstance(raw_key, int):
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
                f"Unknown species key '{raw_key}'. Provide species_order for named split_fractions."
            )

    if index < 0 or index >= n_species:
        raise ValueError(f"Species index {index} out of bounds for n_species={n_species}.")
    return index


def _coerce_split_fractions(
    *,
    n_species: int,
    split_fractions: object,
    species_order: Sequence[str] | None,
) -> NDArray[np.float64]:
    if split_fractions is None:
        return np.zeros(n_species, dtype=np.float64)

    if isinstance(split_fractions, Mapping):
        label_index = _build_label_index(n_species, species_order)
        split_vector = np.zeros(n_species, dtype=np.float64)
        split_mapping = cast(Mapping[object, object], split_fractions)
        for species_key, raw_value in split_mapping.items():
            species_index = _resolve_species_index(label_index, species_key, n_species)
            if not isinstance(raw_value, (int, float)):
                raise ValueError("split_fractions values must be numeric.")
            split_vector[species_index] = float(raw_value)
        _validate_split_fractions(split_vector)
        return split_vector

    split_vector = np.asarray(split_fractions, dtype=np.float64).reshape(-1)
    if split_vector.size != n_species:
        raise ValueError(
            f"split_fractions length mismatch: expected {n_species}, got {split_vector.size}."
        )
    _validate_split_fractions(split_vector)
    return split_vector


class ComponentSeparator(AlgebraicProcessModel):
    n_species: Annotated[int, M(type=T.CONSTANT, unit="", description="number of species")] = 2
    split_fractions: Annotated[
        NDArray[np.float64],
        M(
            type=T.CONSTANT,
            unit="",
            description="species-wise split fraction to outlet_1 (remainder goes to outlet_2)",
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

    outlet_1_flow: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="mol/s", description="outlet_1 molar flow rate"),
    ] = 0.0
    outlet_2_flow: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="mol/s", description="outlet_2 molar flow rate"),
    ] = 0.0
    outlet_1_temperature: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="K", description="outlet_1 temperature"),
    ] = 298.15
    outlet_2_temperature: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="K", description="outlet_2 temperature"),
    ] = 298.15
    outlet_1_pressure: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="Pa", description="outlet_1 pressure"),
    ] = 101325.0
    outlet_2_pressure: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="Pa", description="outlet_2 pressure"),
    ] = 101325.0
    outlet_1_composition: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="", description="outlet_1 composition vector by species index"),
    ] = np.zeros(0, dtype=np.float64)
    outlet_2_composition: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="", description="outlet_2 composition vector by species index"),
    ] = np.zeros(0, dtype=np.float64)

    def __init__(self, **data: object) -> None:
        raw_species_order = data.pop("species_order", None)
        raw_split_fractions = data.get("split_fractions", None)

        if raw_split_fractions is not None and isinstance(raw_split_fractions, Mapping):
            raw_n_species = data.get("n_species", 2)
            if not isinstance(raw_n_species, (int, float)):
                raise ValueError("n_species must be numeric when split_fractions is a mapping.")
            n_species = int(raw_n_species)
            split_mapping = cast(Mapping[object, object], raw_split_fractions)
            typed_species_order: tuple[str, ...] | None
            if raw_species_order is None:
                typed_species_order = None
            elif isinstance(raw_species_order, Sequence) and not isinstance(
                raw_species_order, (str, bytes)
            ):
                typed_species_order = tuple(str(value) for value in raw_species_order)
            else:
                raise ValueError("species_order must be a sequence of species labels.")

            species_order = typed_species_order
            data["split_fractions"] = _coerce_split_fractions(
                n_species=n_species,
                split_fractions=split_mapping,
                species_order=species_order,
            )

        super().__init__(**data)  # pyright: ignore[reportArgumentType]

    @override
    def model_post_init(self, context: object) -> None:
        super().model_post_init(context)
        if self.n_species <= 0:
            raise ValueError("n_species must be a positive integer.")
        if not isfinite(self.inlet_flow) or self.inlet_flow < 0.0:
            raise ValueError("inlet_flow must be finite and non-negative.")
        if not isfinite(self.inlet_temperature):
            raise ValueError("inlet_temperature must be finite.")
        if not isfinite(self.inlet_pressure) or self.inlet_pressure <= 0.0:
            raise ValueError("inlet_pressure must be finite and positive.")

        self.split_fractions = _coerce_split_fractions(
            n_species=self.n_species,
            split_fractions=self.split_fractions,
            species_order=None,
        )
        self.inlet_composition = _coerce_vector(
            self.inlet_composition,
            expected_size=self.n_species,
            name="inlet_composition",
            default=1.0 / float(self.n_species),
        )
        self.outlet_1_composition = _coerce_vector(
            self.outlet_1_composition,
            expected_size=self.n_species,
            name="outlet_1_composition",
            default=1.0 / float(self.n_species),
        )
        self.outlet_2_composition = _coerce_vector(
            self.outlet_2_composition,
            expected_size=self.n_species,
            name="outlet_2_composition",
            default=1.0 / float(self.n_species),
        )

        _validate_composition(
            np.asarray(self.inlet_composition, dtype=np.float64), name="inlet_composition"
        )
        _validate_split_fractions(np.asarray(self.split_fractions, dtype=np.float64))

    @property
    def ports(self) -> UnitProcessPorts:
        return DUAL_OUTLET

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
        split_fractions = _vector_from_state(k, k_map["split_fractions"])

        if not isfinite(inlet_flow) or inlet_flow < 0.0:
            raise ValueError("inlet_flow must be finite and non-negative.")
        if not isfinite(inlet_temperature):
            raise ValueError("inlet_temperature must be finite.")
        if not isfinite(inlet_pressure) or inlet_pressure <= 0.0:
            raise ValueError("inlet_pressure must be finite and positive.")
        if inlet_composition.size != n_species:
            raise ValueError(
                f"inlet_composition length mismatch: expected {n_species}, got {inlet_composition.size}."
            )
        if split_fractions.size != n_species:
            raise ValueError(
                f"split_fractions length mismatch: expected {n_species}, got {split_fractions.size}."
            )

        _validate_composition(inlet_composition, name="inlet_composition")
        _validate_split_fractions(split_fractions)

        inlet_component_flows = inlet_flow * inlet_composition
        outlet_1_component_flows = inlet_component_flows * split_fractions
        outlet_2_component_flows = inlet_component_flows * (1.0 - split_fractions)

        outlet_1_flow = float(np.sum(outlet_1_component_flows))
        outlet_2_flow = float(np.sum(outlet_2_component_flows))

        if outlet_1_flow > _FLOW_EPSILON:
            outlet_1_composition = outlet_1_component_flows / outlet_1_flow
        else:
            outlet_1_composition = inlet_composition.copy()

        if outlet_2_flow > _FLOW_EPSILON:
            outlet_2_composition = outlet_2_component_flows / outlet_2_flow
        else:
            outlet_2_composition = inlet_composition.copy()

        result = np.zeros(algebraic_size, dtype=np.float64)
        result[algebraic_map["outlet_1_flow"]] = outlet_1_flow
        result[algebraic_map["outlet_2_flow"]] = outlet_2_flow
        result[algebraic_map["outlet_1_temperature"]] = inlet_temperature
        result[algebraic_map["outlet_2_temperature"]] = inlet_temperature
        result[algebraic_map["outlet_1_pressure"]] = inlet_pressure
        result[algebraic_map["outlet_2_pressure"]] = inlet_pressure
        result[algebraic_map["outlet_1_composition"]] = outlet_1_composition
        result[algebraic_map["outlet_2_composition"]] = outlet_2_composition
        return result


__all__ = ["ComponentSeparator"]

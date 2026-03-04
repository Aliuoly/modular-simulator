from __future__ import annotations

# pyright: reportMissingTypeStubs=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownMemberType=false

from dataclasses import dataclass, field
from difflib import get_close_matches
from functools import lru_cache

import numpy as np
from chemicals import CAS_from_any, MW, Pc, Tc, omega, search_chemical
from numpy.typing import NDArray


@dataclass(frozen=True)
class Species:
    cas: str
    name: str
    formula: str
    mw: float
    tc: float
    pc: float
    omega: float


def _normalize_identifier(identifier: str) -> str:
    normalized = identifier.strip()
    if not normalized:
        raise ValueError("Species identifier cannot be empty.")
    return normalized


def _build_resolution_error(identifier: str, error: Exception) -> ValueError:
    formula_like = (
        bool(identifier) and any(char.isdigit() for char in identifier) and "-" not in identifier
    )
    guidance = "Use a common name (e.g., 'water') or a CAS number (e.g., '7732-18-5')."
    if formula_like:
        guidance = (
            "Formula-only lookup can be ambiguous. Prefer a common name or CAS number "
            "for deterministic resolution."
        )
    return ValueError(
        f"Unable to resolve species '{identifier}'. {guidance} chemicals lookup error: {error}"
    )


def _as_float(value: object, property_name: str, cas: str) -> float:
    if isinstance(value, (int, float, np.floating)) and not isinstance(value, bool):
        return float(value)
    raise ValueError(f"Property '{property_name}' unavailable for species CAS '{cas}'.")


@lru_cache(maxsize=512)
def resolve_species(identifier: str) -> Species:
    normalized_identifier = _normalize_identifier(identifier)
    try:
        cas = str(CAS_from_any(normalized_identifier))
        metadata = search_chemical(cas)
    except Exception as error:
        raise _build_resolution_error(normalized_identifier, error) from error

    return Species(
        cas=cas,
        name=str(metadata.common_name),
        formula=str(metadata.formula),
        mw=_as_float(MW(cas), "MW", cas),
        tc=_as_float(Tc(cas), "Tc", cas),
        pc=_as_float(Pc(cas), "Pc", cas),
        omega=_as_float(omega(cas), "omega", cas),
    )


@dataclass(frozen=True)
class SpeciesProjection:
    global_to_local: NDArray[np.int64]
    local_to_global: NDArray[np.int64]
    n_local: int
    n_global: int

    def to_local(
        self, global_fractions: NDArray[np.float64] | list[float] | tuple[float, ...]
    ) -> NDArray[np.float64]:
        global_array = np.asarray(global_fractions, dtype=float)
        if global_array.shape != (self.n_global,):
            raise ValueError(
                f"Global fraction vector length mismatch: expected {self.n_global}, got {global_array.shape[0]}."
            )
        return global_array[self.global_to_local]

    def to_global(
        self, local_fractions: NDArray[np.float64] | list[float] | tuple[float, ...]
    ) -> NDArray[np.float64]:
        local_array = np.asarray(local_fractions, dtype=float)
        if local_array.shape != (self.n_local,):
            raise ValueError(
                f"Local fraction vector length mismatch: expected {self.n_local}, got {local_array.shape[0]}."
            )
        global_array = np.zeros(self.n_global, dtype=float)
        global_array[self.local_to_global] = local_array
        return global_array


@dataclass(frozen=True)
class ActiveSpeciesRegistry:
    species: tuple[Species, ...]

    @classmethod
    def from_names(cls, identifiers: list[str] | tuple[str, ...]) -> "ActiveSpeciesRegistry":
        if not identifiers:
            raise ValueError("ActiveSpeciesRegistry requires at least one species identifier.")

        resolved_species: list[Species] = []
        seen_cas: set[str] = set()
        for identifier in identifiers:
            resolved = resolve_species(identifier)
            if resolved.cas in seen_cas:
                continue
            seen_cas.add(resolved.cas)
            resolved_species.append(resolved)

        return cls(species=tuple(resolved_species))

    @property
    def n_species(self) -> int:
        return len(self.species)

    @property
    def cas_list(self) -> tuple[str, ...]:
        return tuple(item.cas for item in self.species)

    @property
    def name_list(self) -> tuple[str, ...]:
        return tuple(item.name for item in self.species)

    @property
    def mw_array(self) -> NDArray[np.float64]:
        return np.array([item.mw for item in self.species], dtype=float)

    def index_of(self, species_or_name: str) -> int:
        normalized = _normalize_identifier(species_or_name)
        cas_lookup = self._cas_to_index.get(normalized)
        if cas_lookup is not None:
            return cas_lookup

        lower_lookup = self._name_to_index.get(normalized.casefold())
        if lower_lookup is not None:
            return lower_lookup

        try:
            cas = CAS_from_any(normalized)
        except Exception:
            cas = None
        if cas is not None and cas in self._cas_to_index:
            return self._cas_to_index[cas]

        suggestion_candidates = sorted(set(self.name_list + self.cas_list))
        suggestions = get_close_matches(normalized, suggestion_candidates, n=3, cutoff=0.5)
        suggestion_text = f" Did you mean: {', '.join(suggestions)}?" if suggestions else ""
        raise ValueError(
            f"Species '{species_or_name}' not found in active registry.{suggestion_text}"
        )

    def contains(self, name: str) -> bool:
        try:
            _ = self.index_of(name)
        except ValueError:
            return False
        return True

    def subset_indices(self, sub_registry: "ActiveSpeciesRegistry") -> NDArray[np.int64]:
        indices = [self.index_of(species.cas) for species in sub_registry.species]
        return np.array(indices, dtype=np.int64)

    def project_fractions(
        self,
        global_fractions: NDArray[np.float64] | list[float] | tuple[float, ...],
        sub_registry: "ActiveSpeciesRegistry",
    ) -> NDArray[np.float64]:
        global_array = np.asarray(global_fractions, dtype=float)
        if global_array.shape != (self.n_species,):
            raise ValueError(
                f"Global fraction vector length mismatch: expected {self.n_species}, got {global_array.shape[0]}."
            )
        return global_array[self.subset_indices(sub_registry)]

    def get_projection_for(self, sub_registry: "ActiveSpeciesRegistry") -> SpeciesProjection:
        subset = self.subset_indices(sub_registry)
        return SpeciesProjection(
            global_to_local=subset,
            local_to_global=subset,
            n_local=sub_registry.n_species,
            n_global=self.n_species,
        )

    @property
    def _cas_to_index(self) -> dict[str, int]:
        return {item.cas: index for index, item in enumerate(self.species)}

    @property
    def _name_to_index(self) -> dict[str, int]:
        return {item.name.casefold(): index for index, item in enumerate(self.species)}


@dataclass
class SimulationSpeciesContext:
    registry: ActiveSpeciesRegistry
    _projections: dict[str, SpeciesProjection] = field(default_factory=dict)

    def register_subsystem(self, subsystem_id: str, local_species: list[str]) -> None:
        if not subsystem_id.strip():
            raise ValueError("subsystem_id cannot be empty.")
        local_registry = ActiveSpeciesRegistry.from_names(local_species)
        projection = self.registry.get_projection_for(local_registry)
        self._projections[subsystem_id] = projection

    def get_projection(self, subsystem_id: str) -> SpeciesProjection:
        projection = self._projections.get(subsystem_id)
        if projection is None:
            known = ", ".join(sorted(self._projections))
            known_text = f" Registered subsystem IDs: {known}." if known else ""
            raise KeyError(f"Subsystem '{subsystem_id}' is not registered.{known_text}")
        return projection


__all__ = [
    "ActiveSpeciesRegistry",
    "SimulationSpeciesContext",
    "Species",
    "SpeciesProjection",
    "resolve_species",
]

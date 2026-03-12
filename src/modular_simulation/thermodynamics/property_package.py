from __future__ import annotations

# pyright: reportMissingTypeStubs=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportAttributeAccessIssue=false, reportArgumentType=false

from dataclasses import dataclass
from functools import lru_cache
from math import isfinite
from typing import Protocol, cast, final

from thermo import CEOSGas, CEOSLiquid, ChemicalConstantsPackage, FlashPureVLS, FlashVL, PRMIX
from thermo.interaction_parameters import IPDB

from .species import ActiveSpeciesRegistry

_COMPOSITION_SUM_TOL = 1.0e-8
_PHASE_FRACTION_EPS = 1.0e-9


@dataclass(frozen=True)
class FlashResult:
    temperature: float
    pressure: float
    vapor_fraction: float
    phase: str
    liquid_composition: tuple[float, ...] | None
    vapor_composition: tuple[float, ...] | None
    enthalpy_molar: float
    entropy_molar: float
    liquid_density: float | None
    vapor_density: float | None
    K_values: tuple[float, ...] | None

    def __post_init__(self) -> None:
        if self.phase not in {"vapor", "liquid", "two-phase"}:
            raise ValueError(f"Unsupported normalized phase '{self.phase}'.")

        for name, value in (
            ("temperature", self.temperature),
            ("pressure", self.pressure),
            ("vapor_fraction", self.vapor_fraction),
            ("enthalpy_molar", self.enthalpy_molar),
            ("entropy_molar", self.entropy_molar),
        ):
            if not isfinite(value):
                raise ValueError(f"{name} must be finite.")

        if self.vapor_fraction < 0.0 or self.vapor_fraction > 1.0:
            raise ValueError("vapor_fraction must be within [0, 1].")

        if self.liquid_density is not None:
            if not isfinite(self.liquid_density) or self.liquid_density <= 0.0:
                raise ValueError("liquid_density must be finite and positive when present.")

        if self.vapor_density is not None:
            if not isfinite(self.vapor_density) or self.vapor_density <= 0.0:
                raise ValueError("vapor_density must be finite and positive when present.")


class PropertyPackage(Protocol):
    def flash_tp(self, T: float, P: float, z: tuple[float, ...]) -> FlashResult: ...

    def flash_ph(self, P: float, H: float, z: tuple[float, ...]) -> FlashResult: ...

    def flash_ps(self, P: float, S: float, z: tuple[float, ...]) -> FlashResult: ...

    def enthalpy(self, T: float, P: float, z: tuple[float, ...], phase: str) -> float: ...

    def entropy(self, T: float, P: float, z: tuple[float, ...], phase: str) -> float: ...

    def density(self, T: float, P: float, z: tuple[float, ...], phase: str) -> float: ...

    def heat_capacity_cp(self, T: float, P: float, z: tuple[float, ...], phase: str) -> float: ...

    def molecular_weight(self, z: tuple[float, ...]) -> float: ...

    @property
    def species_cas(self) -> tuple[str, ...]: ...


@final
class PengRobinsonPackage:
    @staticmethod
    def _as_finite_float(value: object, name: str) -> float:
        result = float(value)
        if not isfinite(result):
            raise ValueError(f"{name} must be finite.")
        return result

    @staticmethod
    def _round_composition(z: tuple[float, ...]) -> tuple[float, ...]:
        return tuple(round(float(component), 6) for component in z)

    @classmethod
    def _normalize_composition(cls, z: tuple[float, ...], n_expected: int) -> tuple[float, ...]:
        if len(z) != n_expected:
            raise ValueError(f"Composition length mismatch: expected {n_expected}, got {len(z)}.")
        if not z:
            raise ValueError("Composition cannot be empty.")

        finite_z = tuple(
            cls._as_finite_float(component, "composition component") for component in z
        )
        if any(component < 0.0 for component in finite_z):
            raise ValueError("Composition components must be non-negative.")

        total = sum(finite_z)
        if total <= 0.0:
            raise ValueError("Composition must have a positive sum.")

        normalized = tuple(component / total for component in finite_z)
        if abs(sum(normalized) - 1.0) > _COMPOSITION_SUM_TOL:
            raise ValueError("Composition must sum to 1.0 after normalization.")
        return normalized

    @classmethod
    def _prepare_composition(cls, z: tuple[float, ...], n_expected: int) -> tuple[float, ...]:
        return cls._normalize_composition(cls._round_composition(z), n_expected)

    @staticmethod
    def _phase_composition(phase: object | None) -> tuple[float, ...] | None:
        if phase is None:
            return None
        zs = cast(tuple[object, ...] | list[object], cast(object, getattr(phase, "zs")))
        return tuple(float(value) for value in zs)

    @classmethod
    def _finite_attr_value(cls, target: object, attr_name: str, result_name: str) -> float:
        return cls._as_finite_float(cast(object, getattr(target, attr_name)), result_name)

    @classmethod
    def _finite_property_value(cls, target: object, property_name: str, result_name: str) -> float:
        property_accessor = cast(object, getattr(target, property_name))
        value = property_accessor() if callable(property_accessor) else property_accessor
        return cls._as_finite_float(value, result_name)

    def __init__(self, species_ids: tuple[str, ...]) -> None:
        if not species_ids:
            raise ValueError("species_ids must contain at least one CAS number.")

        self._species_cas = tuple(str(cas) for cas in species_ids)
        self._constants, self._correlations = ChemicalConstantsPackage.from_IDs(self._species_cas)

        kijs = IPDB.get_ip_asymmetric_matrix("ChemSep PR", self._constants.CASs, "kij")
        eos_kwargs = {
            "Tcs": self._constants.Tcs,
            "Pcs": self._constants.Pcs,
            "omegas": self._constants.omegas,
            "kijs": kijs,
        }
        gas = CEOSGas(
            PRMIX,
            eos_kwargs=eos_kwargs,
            HeatCapacityGases=self._correlations.HeatCapacityGases,
        )
        liquid = CEOSLiquid(
            PRMIX,
            eos_kwargs=eos_kwargs,
            HeatCapacityGases=self._correlations.HeatCapacityGases,
        )

        if len(self._species_cas) == 1:
            self._flasher = FlashPureVLS(
                self._constants,
                self._correlations,
                gas=gas,
                liquids=[liquid],
                solids=[],
            )
        else:
            self._flasher = FlashVL(
                self._constants,
                self._correlations,
                gas=gas,
                liquid=liquid,
            )

        self._molecular_weights = tuple(float(value) for value in self._constants.MWs)

    @property
    def species_cas(self) -> tuple[str, ...]:
        return self._species_cas

    @lru_cache(maxsize=128)
    def flash_tp(self, T: float, P: float, z: tuple[float, ...]) -> FlashResult:
        cls = type(self)
        rounded_T = round(cls._as_finite_float(T, "T"), 2)
        rounded_P = round(cls._as_finite_float(P, "P"), 0)
        normalized_z = cls._prepare_composition(z, len(self._species_cas))
        state = self._flasher.flash(T=rounded_T, P=rounded_P, zs=list(normalized_z))
        return self._flash_result_from_state(state)

    @lru_cache(maxsize=128)
    def flash_ph(self, P: float, H: float, z: tuple[float, ...]) -> FlashResult:
        cls = type(self)
        rounded_P = round(cls._as_finite_float(P, "P"), 0)
        rounded_H = round(cls._as_finite_float(H, "H"), 2)
        normalized_z = cls._prepare_composition(z, len(self._species_cas))
        state = self._flasher.flash(P=rounded_P, H=rounded_H, zs=list(normalized_z))
        return self._flash_result_from_state(state)

    @lru_cache(maxsize=128)
    def flash_ps(self, P: float, S: float, z: tuple[float, ...]) -> FlashResult:
        cls = type(self)
        rounded_P = round(cls._as_finite_float(P, "P"), 0)
        rounded_S = round(cls._as_finite_float(S, "S"), 4)
        normalized_z = cls._prepare_composition(z, len(self._species_cas))
        state = self._flasher.flash(P=rounded_P, S=rounded_S, zs=list(normalized_z))
        return self._flash_result_from_state(state)

    def enthalpy(self, T: float, P: float, z: tuple[float, ...], phase: str) -> float:
        cls = type(self)
        state = self._flasher.flash(
            T=round(cls._as_finite_float(T, "T"), 2),
            P=round(cls._as_finite_float(P, "P"), 0),
            zs=list(cls._prepare_composition(z, len(self._species_cas))),
        )
        return cls._as_finite_float(self._phase_value(state, phase, "H"), "enthalpy")

    def entropy(self, T: float, P: float, z: tuple[float, ...], phase: str) -> float:
        cls = type(self)
        state = self._flasher.flash(
            T=round(cls._as_finite_float(T, "T"), 2),
            P=round(cls._as_finite_float(P, "P"), 0),
            zs=list(cls._prepare_composition(z, len(self._species_cas))),
        )
        return cls._as_finite_float(self._phase_value(state, phase, "S"), "entropy")

    def density(self, T: float, P: float, z: tuple[float, ...], phase: str) -> float:
        cls = type(self)
        state = self._flasher.flash(
            T=round(cls._as_finite_float(T, "T"), 2),
            P=round(cls._as_finite_float(P, "P"), 0),
            zs=list(cls._prepare_composition(z, len(self._species_cas))),
        )
        density = cls._as_finite_float(self._phase_value(state, phase, "rho_mass"), "density")
        if density <= 0.0:
            raise ValueError("Density must be positive.")
        return density

    def heat_capacity_cp(self, T: float, P: float, z: tuple[float, ...], phase: str) -> float:
        cls = type(self)
        state = self._flasher.flash(
            T=round(cls._as_finite_float(T, "T"), 2),
            P=round(cls._as_finite_float(P, "P"), 0),
            zs=list(cls._prepare_composition(z, len(self._species_cas))),
        )
        cp = cls._as_finite_float(self._phase_value(state, phase, "Cp"), "heat_capacity_cp")
        if cp <= 0.0:
            raise ValueError("heat_capacity_cp must be positive.")
        return cp

    def molecular_weight(self, z: tuple[float, ...]) -> float:
        cls = type(self)
        normalized_z = cls._prepare_composition(z, len(self._species_cas))
        mixture_mw = sum(
            component * mw for component, mw in zip(normalized_z, self._molecular_weights)
        )
        return cls._as_finite_float(mixture_mw, "molecular_weight")

    def _flash_result_from_state(self, state: object) -> FlashResult:
        cls = type(self)
        gas = cast(object | None, getattr(state, "gas", None))
        liquids = tuple(cast(tuple[object, ...], getattr(state, "liquids", ()) or ()))
        liquid0 = cast(object | None, getattr(state, "liquid0", liquids[0] if liquids else None))

        vf_raw = cast(object | None, getattr(state, "VF", None))
        if vf_raw is None:
            vapor_fraction = 1.0 if gas is not None and liquid0 is None else 0.0
        else:
            vapor_fraction = cls._as_finite_float(vf_raw, "vapor_fraction")
        if vapor_fraction < _PHASE_FRACTION_EPS:
            vapor_fraction = 0.0
        elif vapor_fraction > 1.0 - _PHASE_FRACTION_EPS:
            vapor_fraction = 1.0
        vapor_fraction = max(0.0, min(1.0, vapor_fraction))

        if gas is not None and liquid0 is not None and 0.0 < vapor_fraction < 1.0:
            phase = "two-phase"
        elif gas is not None and (liquid0 is None or vapor_fraction >= 1.0):
            phase = "vapor"
        else:
            phase = "liquid"

        vapor_z = cls._phase_composition(gas)
        liquid_z = cls._phase_composition(liquid0)

        vapor_density = None
        if gas is not None:
            vapor_density = cls._finite_property_value(gas, "rho_mass", "vapor_density")

        liquid_density = None
        if liquid0 is not None:
            liquid_density = cls._finite_property_value(liquid0, "rho_mass", "liquid_density")

        k_values: tuple[float, ...] | None = None
        if vapor_z is not None and liquid_z is not None:
            k_raw: list[float] = []
            for vapor_component, liquid_component in zip(vapor_z, liquid_z):
                denominator = max(liquid_component, 1.0e-12)
                ratio = vapor_component / denominator
                k_raw.append(max(1.0e-12, min(1.0e12, ratio)))
            k_values = tuple(k_raw)

        return FlashResult(
            temperature=cls._finite_attr_value(state, "T", "temperature"),
            pressure=cls._finite_attr_value(state, "P", "pressure"),
            vapor_fraction=vapor_fraction,
            phase=phase,
            liquid_composition=liquid_z,
            vapor_composition=vapor_z,
            enthalpy_molar=cls._finite_property_value(state, "H", "enthalpy_molar"),
            entropy_molar=cls._finite_property_value(state, "S", "entropy_molar"),
            liquid_density=liquid_density,
            vapor_density=vapor_density,
            K_values=k_values,
        )

    def _phase_value(self, state: object, phase: str, property_name: str) -> float:
        cls = type(self)
        normalized_phase = phase.strip().casefold()
        if normalized_phase not in {"vapor", "liquid", "two-phase"}:
            raise ValueError("phase must be one of 'vapor', 'liquid', or 'two-phase'.")

        if normalized_phase == "two-phase":
            target = state
        elif normalized_phase == "vapor":
            target = getattr(state, "gas", None)
            if target is None:
                raise ValueError(
                    "Requested vapor property from a flash state without a vapor phase."
                )
        else:
            target = getattr(state, "liquid0", None)
            if target is None:
                liquids = tuple(getattr(state, "liquids", ()) or ())
                target = liquids[0] if liquids else None
            if target is None:
                raise ValueError(
                    "Requested liquid property from a flash state without a liquid phase."
                )

        return cls._finite_property_value(target, property_name, property_name)


def create_property_package(species: ActiveSpeciesRegistry, model: str = "PR") -> PropertyPackage:
    normalized_model = model.strip().upper()
    if normalized_model != "PR":
        raise ValueError(f"Unsupported property model '{model}'. Only 'PR' is currently supported.")
    return PengRobinsonPackage(species_ids=species.cas_list)


__all__ = [
    "FlashResult",
    "PengRobinsonPackage",
    "PropertyPackage",
    "create_property_package",
]

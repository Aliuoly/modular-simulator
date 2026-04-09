from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

import numpy as np
from numpy.typing import NDArray

from .property_package import PengRobinsonPackage

_MIN_SUM = 1.0e-12


class FlashRecoveryError(RuntimeError):
    """Raised when bounded flash-protection fallback cannot recover."""


def smooth_plus(value: float, eps: float = 1.0e-8) -> float:
    return 0.5 * (float(value) + sqrt(float(value) * float(value) + eps * eps))


def smooth_min(a: float, b: float, eps: float = 1.0e-8) -> float:
    diff = float(a) - float(b)
    return 0.5 * (float(a) + float(b) - sqrt(diff * diff + eps * eps))


def normalized_composition(
    values: NDArray[np.float64] | tuple[float, ...] | list[float], *, n_species: int
) -> NDArray[np.float64]:
    arr = np.asarray(values, dtype=np.float64).reshape(-1)
    if arr.size != n_species:
        raise ValueError(f"composition length mismatch: expected {n_species}, got {arr.size}.")
    arr = np.clip(arr, 0.0, None)
    total = float(np.sum(arr))
    if total <= _MIN_SUM:
        return np.full(n_species, 1.0 / float(n_species), dtype=np.float64)
    return arr / total


@dataclass(frozen=True)
class FlashDiagnostics:
    used_fallback: bool
    attempt_count: int
    attempted_conditions: tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class ThermoPRState:
    liquid_composition: NDArray[np.float64]
    vapor_composition: NDArray[np.float64]
    k_values: NDArray[np.float64]
    h_liq_j_per_mol: float
    h_vap_j_per_mol: float
    cp_liq_j_per_mol_k: float
    rho_liq_kg_m3: float
    rho_vap_kg_m3: float
    vapor_fraction: float
    flash_diagnostics: FlashDiagnostics


def _safe_flash(
    package: PengRobinsonPackage, *, T: float, P: float, z: tuple[float, ...]
) -> tuple[object, FlashDiagnostics]:
    t0 = float(T)
    p0 = float(P)
    bounded_t = min(1200.0, max(120.0, t0))
    bounded_p = max(1.0e4, p0)
    attempts: tuple[tuple[float, float], ...] = (
        (t0, p0),
        (bounded_t, bounded_p),
        (bounded_t + 5.0, bounded_p),
        (max(120.0, bounded_t - 5.0), bounded_p * 1.02),
    )
    last_error: Exception | None = None
    for attempt_index, (t_try, p_try) in enumerate(attempts):
        try:
            flash = package.flash_tp(T=t_try, P=p_try, z=z)
            return flash, FlashDiagnostics(
                used_fallback=attempt_index > 0,
                attempt_count=attempt_index + 1,
                attempted_conditions=attempts[: attempt_index + 1],
            )
        except Exception as exc:  # pragma: no cover - exercised via fallback paths
            last_error = exc
            continue
    raise FlashRecoveryError(
        "Flash_PR failed after bounded recovery attempts "
        f"(T={t0:.3f} K, P={p0:.3f} Pa, attempts={attempts})."
    ) from last_error


def thermo_pr(
    package: PengRobinsonPackage,
    *,
    temperature_k: float,
    pressure_pa: float,
    composition: NDArray[np.float64],
) -> ThermoPRState:
    n_species = composition.size
    x = normalized_composition(composition, n_species=n_species)
    z = tuple(float(v) for v in x)
    flash, flash_diagnostics = _safe_flash(package, T=temperature_k, P=pressure_pa, z=z)
    eval_t = float(flash.temperature)
    eval_p = float(flash.pressure)

    liq_comp = normalized_composition(
        np.asarray(flash.liquid_composition if flash.liquid_composition is not None else z),
        n_species=n_species,
    )
    vap_comp = normalized_composition(
        np.asarray(flash.vapor_composition if flash.vapor_composition is not None else liq_comp),
        n_species=n_species,
    )

    k_values = np.clip(vap_comp / np.clip(liq_comp, 1.0e-12, None), 1.0e-10, 1.0e10)

    try:
        h_liq = float(package.enthalpy(eval_t, eval_p, tuple(liq_comp), "liquid"))
    except Exception:
        h_liq = float(flash.enthalpy_molar)
    try:
        h_vap = float(package.enthalpy(eval_t, eval_p, tuple(vap_comp), "vapor"))
    except Exception:
        h_vap = h_liq + 25000.0

    try:
        cp_liq = float(package.heat_capacity_cp(eval_t, eval_p, tuple(liq_comp), "liquid"))
    except Exception:
        cp_liq = 120.0

    try:
        rho_liq = float(package.density(eval_t, eval_p, tuple(liq_comp), "liquid"))
    except Exception:
        rho_liq = 700.0
    try:
        rho_vap = float(package.density(eval_t, eval_p, tuple(vap_comp), "vapor"))
    except Exception:
        rho_vap = 2.0

    return ThermoPRState(
        liquid_composition=liq_comp,
        vapor_composition=vap_comp,
        k_values=k_values,
        h_liq_j_per_mol=h_liq,
        h_vap_j_per_mol=h_vap,
        cp_liq_j_per_mol_k=max(1.0, cp_liq),
        rho_liq_kg_m3=max(1.0, rho_liq),
        rho_vap_kg_m3=max(0.01, rho_vap),
        vapor_fraction=float(np.clip(flash.vapor_fraction, 0.0, 1.0)),
        flash_diagnostics=flash_diagnostics,
    )


def feed_flash_pr(
    package: PengRobinsonPackage,
    *,
    temperature_k: float,
    pressure_pa: float,
    composition: NDArray[np.float64],
) -> ThermoPRState:
    return thermo_pr(
        package,
        temperature_k=temperature_k,
        pressure_pa=pressure_pa,
        composition=composition,
    )


def thermo_pr_liq(
    package: PengRobinsonPackage,
    *,
    temperature_k: float,
    pressure_pa: float,
    composition: NDArray[np.float64],
) -> tuple[float, float, float]:
    state = thermo_pr(
        package,
        temperature_k=temperature_k,
        pressure_pa=pressure_pa,
        composition=composition,
    )
    return state.h_liq_j_per_mol, state.cp_liq_j_per_mol_k, state.rho_liq_kg_m3


__all__ = [
    "FlashDiagnostics",
    "FlashRecoveryError",
    "ThermoPRState",
    "feed_flash_pr",
    "normalized_composition",
    "smooth_min",
    "smooth_plus",
    "thermo_pr",
    "thermo_pr_liq",
]

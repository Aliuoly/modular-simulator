from __future__ import annotations

# pyright: reportMissingTypeStubs=false, reportImplicitOverride=false

from dataclasses import dataclass
from typing import cast

import numpy as np
from numpy.typing import NDArray

from modular_simulation.framework.system import System
from modular_simulation.thermodynamics.property_package import FlashResult, PropertyPackage
from modular_simulation.unit_processes import ShortcutDistillation


@dataclass
class _StubSystem:
    solver_options: dict[str, object]


class _DemoDistillationPackage(PropertyPackage):
    _k_values: tuple[float, ...]
    _vapor_fraction: float
    _species_cas: tuple[str, ...]
    _molecular_weights: tuple[float, ...]

    def __init__(
        self,
        *,
        k_values: tuple[float, ...],
        vapor_fraction: float = 0.35,
    ) -> None:
        self._k_values = tuple(float(value) for value in k_values)
        self._vapor_fraction = float(vapor_fraction)
        self._species_cas = ("7732-18-5", "64-17-5")
        self._molecular_weights = (18.01528, 46.06844)

    @property
    def species_cas(self) -> tuple[str, ...]:
        return self._species_cas

    def flash_ph(self, P: float, H: float, z: tuple[float, ...]) -> FlashResult:
        return self.flash_tp(298.15, P, z)

    def flash_ps(self, P: float, S: float, z: tuple[float, ...]) -> FlashResult:
        return self.flash_tp(298.15, P, z)

    def flash_tp(self, T: float, P: float, z: tuple[float, ...]) -> FlashResult:
        z_vec: NDArray[np.float64] = np.asarray(z, dtype=np.float64)
        y_values = [float(k_value) * float(z_val) for k_value, z_val in zip(self._k_values, z)]
        y_sum = sum(y_values)
        if y_sum != 0.0:
            y_values = [value / y_sum for value in y_values]
        y = tuple(y_values)
        x = tuple(float(value) for value in z)
        enthalpy_value = self._enthalpy_value(T, z_vec, phase="liquid")
        return FlashResult(
            temperature=float(T),
            pressure=float(P),
            vapor_fraction=self._vapor_fraction,
            phase="two-phase",
            liquid_composition=x,
            vapor_composition=y,
            enthalpy_molar=enthalpy_value,
            entropy_molar=float(T),
            liquid_density=750.0,
            vapor_density=1.2,
            K_values=self._k_values,
        )

    def enthalpy(self, T: float, P: float, z: tuple[float, ...], phase: str) -> float:
        del P
        return self._enthalpy_value(T, np.asarray(z, dtype=np.float64), phase=phase)

    def entropy(self, T: float, P: float, z: tuple[float, ...], phase: str) -> float:
        del P, phase
        return float(T)

    def density(self, T: float, P: float, z: tuple[float, ...], phase: str) -> float:
        del T, P, z
        if phase == "vapor":
            return 1.2
        return 750.0

    def heat_capacity_cp(self, T: float, P: float, z: tuple[float, ...], phase: str) -> float:
        del T, P
        cp_liquid: NDArray[np.float64] = np.array([95.0, 140.0], dtype=np.float64)
        cp_vapor: NDArray[np.float64] = cp_liquid + 2200.0
        cp_values: NDArray[np.float64] = cp_vapor if phase == "vapor" else cp_liquid
        z_vec: NDArray[np.float64] = np.asarray(z, dtype=np.float64)
        cp: NDArray[np.float64] = cp_values[: z_vec.size]
        return float(np.dot(z_vec, cp))  # pyright: ignore[reportAny]

    def molecular_weight(self, z: tuple[float, ...]) -> float:
        z_vec: NDArray[np.float64] = np.asarray(z, dtype=np.float64)
        total = float(np.sum(z_vec))
        if total <= 0.0:
            normalized: NDArray[np.float64] = np.asarray(self._molecular_weights, dtype=np.float64)
        else:
            normalized = z_vec / total
        mw_array: NDArray[np.float64] = np.asarray(self._molecular_weights, dtype=np.float64)
        return float(np.dot(normalized, mw_array))  # pyright: ignore[reportAny]

    def _enthalpy_value(self, T: float, z: NDArray[np.float64], *, phase: str) -> float:
        cp_liquid: NDArray[np.float64] = np.array([95.0, 140.0], dtype=np.float64)
        cp_vapor: NDArray[np.float64] = cp_liquid + 2200.0
        cp_values: NDArray[np.float64] = cp_vapor if phase == "vapor" else cp_liquid
        cp: NDArray[np.float64] = cp_values[: z.size]
        return float(np.dot(z, cp) * float(T))  # pyright: ignore[reportAny]


def run_demo() -> dict[str, float]:
    package = _DemoDistillationPackage(k_values=(2.8, 1.0), vapor_fraction=0.38)
    column = ShortcutDistillation(
        n_species=2,
        light_key_index=0,
        heavy_key_index=1,
        inlet_flow=12.0,
        inlet_temperature=358.0,
        inlet_pressure=101325.0,
        inlet_composition=np.array([0.45, 0.55], dtype=np.float64),
        configured_light_key_distillate_recovery_target=0.97,
        configured_heavy_key_bottoms_recovery_target=0.97,
        configured_minimum_reflux_ratio_factor=1.45,
    )
    column.set_property_package(package)
    column.attach_system(cast(System, cast(object, _StubSystem(solver_options={}))))

    try:
        column.step(0.5)
    except ValueError:
        column.set_property_package(None)
        column.step(0.5)
    reboiler_base = float(column.reboiler_duty)

    column.configured_reflux_ratio_target = float(column.actual_reflux_ratio * 1.25)
    column.step(0.5)
    reboiler_after = float(column.reboiler_duty)

    return {
        "minimum_reflux_ratio": float(column.minimum_reflux_ratio),
        "actual_reflux_ratio": float(column.actual_reflux_ratio),
        "minimum_stages": float(column.minimum_stages),
        "actual_stages": float(column.actual_stages),
        "reboiler_duty_base_w": reboiler_base,
        "reboiler_duty_after_w": reboiler_after,
        "reboiler_duty_delta_w": reboiler_after - reboiler_base,
    }


def main() -> None:
    result = run_demo()
    print("SHORTCUT DISTILLATION REBOILER DEMO")
    for key, value in result.items():
        print(f"{key}={value:.6f}")


if __name__ == "__main__":
    main()

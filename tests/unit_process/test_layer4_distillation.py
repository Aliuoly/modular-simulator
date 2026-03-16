from __future__ import annotations

# pyright: reportMissingTypeStubs=false, reportMissingImports=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false, reportMissingTypeArgument=false

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import numpy as np
import pytest
from pydantic import ValidationError

from modular_simulation.thermodynamics.property_package import FlashResult
from modular_simulation.unit_processes import ShortcutDistillation


def _attach(model: ShortcutDistillation) -> None:
    model.attach_system(cast(Any, SimpleNamespace(solver_options={})))


class _MockDistillationPackage:
    def __init__(self, *, k_values: tuple[float, ...], vapor_fraction: float = 0.4) -> None:
        self._k_values = tuple(float(value) for value in k_values)
        self._vf = float(vapor_fraction)

    def flash_tp(self, T: float, P: float, z: tuple[float, ...]) -> FlashResult:
        z_vec = np.asarray(z, dtype=np.float64)
        y = np.asarray(self._k_values, dtype=np.float64) * z_vec
        y /= float(np.sum(y))
        x = z_vec.copy()
        h_mix = self._enthalpy_value(T, z_vec, phase="liquid")
        return FlashResult(
            temperature=float(T),
            pressure=float(P),
            vapor_fraction=self._vf,
            phase="two-phase",
            liquid_composition=tuple(float(v) for v in x),
            vapor_composition=tuple(float(v) for v in y),
            enthalpy_molar=h_mix,
            entropy_molar=float(T),
            liquid_density=750.0,
            vapor_density=1.2,
            K_values=self._k_values,
        )

    def enthalpy(self, T: float, P: float, z: tuple[float, ...], phase: str) -> float:
        del P
        return self._enthalpy_value(T, np.asarray(z, dtype=np.float64), phase=phase)

    def _enthalpy_value(self, T: float, z: np.ndarray, *, phase: str) -> float:
        cp_liquid = np.array([95.0, 120.0, 150.0, 170.0], dtype=np.float64)
        cp_vapor = cp_liquid + 2200.0
        cp_base = cp_vapor if phase == "vapor" else cp_liquid
        cp = cp_base[: z.size]
        return float(np.dot(z, cp) * float(T))


def test_fug_textbook_case() -> None:
    package = _MockDistillationPackage(k_values=(4.0, 2.0, 0.4), vapor_fraction=0.35)
    column = ShortcutDistillation(
        n_species=3,
        light_key_index=0,
        heavy_key_index=1,
        inlet_flow=100.0,
        inlet_temperature=360.0,
        inlet_pressure=101325.0,
        inlet_composition=np.array([0.4, 0.35, 0.25], dtype=np.float64),
        configured_light_key_distillate_recovery_target=0.95,
        configured_heavy_key_bottoms_recovery_target=0.95,
        configured_minimum_reflux_ratio_factor=1.5,
    )
    column.set_property_package(cast(Any, package))
    _attach(column)

    column.step(0.1)

    assert column.minimum_stages > 0.0
    assert column.minimum_reflux_ratio > 0.0
    assert column.actual_reflux_ratio > column.minimum_reflux_ratio
    assert column.actual_stages > column.minimum_stages
    assert column.relative_volatility[0] == pytest.approx(2.0, rel=1.0e-9)
    assert column.relative_volatility[1] == pytest.approx(1.0, rel=1.0e-9)
    assert 1.0 < column.underwood_theta < column.relative_volatility[0]

    lk_feed = column.inlet_flow * column.inlet_composition[0]
    hk_feed = column.inlet_flow * column.inlet_composition[1]
    lk_dist = column.distillate_flow * column.distillate_composition[0]
    hk_bottoms = column.bottoms_flow * column.bottoms_composition[1]
    assert lk_dist / lk_feed == pytest.approx(
        column.configured_light_key_distillate_recovery_target, abs=1.0e-6
    )
    assert hk_bottoms / hk_feed == pytest.approx(
        column.configured_heavy_key_bottoms_recovery_target, abs=1.0e-6
    )

    assert column.condenser_duty < 0.0
    assert column.reboiler_duty > 0.0


def test_mass_balance_closure() -> None:
    package = _MockDistillationPackage(k_values=(5.0, 2.2, 1.0, 0.3), vapor_fraction=0.25)
    column = ShortcutDistillation(
        n_species=4,
        light_key_index=0,
        heavy_key_index=2,
        inlet_flow=80.0,
        inlet_temperature=345.0,
        inlet_pressure=130000.0,
        inlet_composition=np.array([0.25, 0.25, 0.30, 0.20], dtype=np.float64),
        configured_light_key_distillate_recovery_target=0.96,
        configured_heavy_key_bottoms_recovery_target=0.94,
        configured_minimum_reflux_ratio_factor=1.8,
    )
    column.set_property_package(cast(Any, package))
    _attach(column)

    column.step(0.1)

    z_in = np.asarray(column.inlet_composition, dtype=np.float64)
    x_d = np.asarray(column.distillate_composition, dtype=np.float64)
    x_b = np.asarray(column.bottoms_composition, dtype=np.float64)

    assert column.distillate_flow + column.bottoms_flow == pytest.approx(
        column.inlet_flow, abs=1.0e-8
    )
    assert float(np.sum(x_d)) == pytest.approx(1.0, abs=1.0e-8)
    assert float(np.sum(x_b)) == pytest.approx(1.0, abs=1.0e-8)
    assert np.all(x_d >= 0.0)
    assert np.all(x_b >= 0.0)

    component_out = column.distillate_flow * x_d + column.bottoms_flow * x_b
    component_in = column.inlet_flow * z_in
    assert component_out == pytest.approx(component_in, abs=1.0e-6)

    assert column.actual_reflux_ratio > column.minimum_reflux_ratio
    assert column.actual_stages > column.minimum_stages


def test_shortcut_distillation_rejects_legacy_configured_specs() -> None:
    legacy_kwargs: dict[str, Any] = {
        "light_key_distillate_recovery": 0.93,
        "heavy_key_bottoms_recovery": 0.94,
        "reflux_ratio_factor": 1.7,
        "reflux_ratio_setpoint": 0.0,
    }

    with pytest.raises(ValidationError) as excinfo:
        _ = ShortcutDistillation(
            n_species=2,
            light_key_index=0,
            heavy_key_index=1,
            **legacy_kwargs,
        )

    message = str(excinfo.value)
    assert "light_key_distillate_recovery" in message
    assert "heavy_key_bottoms_recovery" in message
    assert "reflux_ratio_factor" in message
    assert "reflux_ratio_setpoint" in message


def test_shortcut_distillation_helper_cluster_is_class_owned() -> None:
    module_path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "modular_simulation"
        / "unit_processes"
        / "separation"
        / "shortcut_distillation.py"
    )
    module_text = module_path.read_text(encoding="utf-8")
    class_prefix = module_text.split("class ShortcutDistillation", 1)[0]

    assert hasattr(ShortcutDistillation, "_solve_underwood_theta")
    assert hasattr(ShortcutDistillation, "_fenske_n_min")
    assert "def _solve_underwood_theta" not in class_prefix
    assert "def _fenske_n_min" not in class_prefix

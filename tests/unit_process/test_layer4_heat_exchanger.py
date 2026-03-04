from __future__ import annotations

# pyright: reportMissingTypeStubs=false, reportAny=false, reportExplicitAny=false, reportUnknownMemberType=false

from types import SimpleNamespace
from typing import Any, cast

import numpy as np
import pytest

from modular_simulation.thermodynamics.property_package import FlashResult
from modular_simulation.unit_processes import HeatExchanger


def _attach(model: HeatExchanger) -> None:
    model.attach_system(cast(Any, SimpleNamespace(solver_options={})))


class _ConstantCpPackage:
    cp_hot: float
    cp_cold: float

    def __init__(self, *, cp_hot: float, cp_cold: float) -> None:
        self.cp_hot = cp_hot
        self.cp_cold = cp_cold

    def flash_tp(self, T: float, P: float, z: tuple[float, ...]) -> FlashResult:
        return FlashResult(
            temperature=T,
            pressure=P,
            vapor_fraction=0.0,
            phase="liquid",
            liquid_composition=z,
            vapor_composition=None,
            enthalpy_molar=100.0 * T,
            entropy_molar=T,
            liquid_density=1000.0,
            vapor_density=None,
            K_values=None,
        )

    def heat_capacity_cp(self, T: float, P: float, z: tuple[float, ...], phase: str) -> float:
        del T, P, phase
        if z[0] >= 0.5:
            return self.cp_hot
        return self.cp_cold


def test_counter_current_energy_balance() -> None:
    package = _ConstantCpPackage(cp_hot=100.0, cp_cold=120.0)
    exchanger = HeatExchanger(
        flow_arrangement="counter",
        n_species=2,
        ua=2400.0,
        hot_inlet_flow=2.0,
        hot_inlet_temperature=410.0,
        hot_inlet_pressure=200000.0,
        hot_inlet_composition=np.array([0.9, 0.1], dtype=np.float64),
        cold_inlet_flow=3.0,
        cold_inlet_temperature=300.0,
        cold_inlet_pressure=180000.0,
        cold_inlet_composition=np.array([0.2, 0.8], dtype=np.float64),
    )
    exchanger.set_property_package(cast(Any, package))
    _attach(exchanger)

    exchanger.step(0.1)

    assert exchanger.heat_duty > 0.0
    assert exchanger.heat_duty_hot < 0.0
    assert exchanger.heat_duty_cold > 0.0
    assert exchanger.heat_duty == pytest.approx(exchanger.heat_duty_cold, rel=1.0e-12, abs=1.0e-9)
    assert exchanger.heat_duty_hot == pytest.approx(
        -exchanger.heat_duty_cold, rel=1.0e-12, abs=1.0e-9
    )
    assert exchanger.hot_outlet_temperature < exchanger.hot_inlet_temperature
    assert exchanger.cold_outlet_temperature > exchanger.cold_inlet_temperature


def test_effectiveness_bounds() -> None:
    package = _ConstantCpPackage(cp_hot=90.0, cp_cold=140.0)
    exchanger = HeatExchanger(
        flow_arrangement="co",
        n_species=2,
        ua=1500.0,
        hot_inlet_flow=1.8,
        hot_inlet_temperature=390.0,
        hot_inlet_pressure=150000.0,
        hot_inlet_composition=np.array([0.8, 0.2], dtype=np.float64),
        cold_inlet_flow=2.6,
        cold_inlet_temperature=305.0,
        cold_inlet_pressure=140000.0,
        cold_inlet_composition=np.array([0.1, 0.9], dtype=np.float64),
    )
    exchanger.set_property_package(cast(Any, package))
    _attach(exchanger)

    exchanger.step(0.1)

    assert np.isfinite(exchanger.effectiveness)
    assert 0.0 <= exchanger.effectiveness <= 1.0
    assert np.isfinite(exchanger.ntu)
    assert exchanger.ntu >= 0.0
    assert np.isfinite(exchanger.lmtd)


def test_flow_arrangements_supported() -> None:
    package = _ConstantCpPackage(cp_hot=100.0, cp_cold=100.0)
    co_current = HeatExchanger(
        flow_arrangement="co",
        n_species=2,
        ua=1800.0,
        hot_inlet_flow=2.0,
        hot_inlet_temperature=400.0,
        hot_inlet_pressure=101325.0,
        hot_inlet_composition=np.array([0.7, 0.3], dtype=np.float64),
        cold_inlet_flow=2.0,
        cold_inlet_temperature=300.0,
        cold_inlet_pressure=101325.0,
        cold_inlet_composition=np.array([0.3, 0.7], dtype=np.float64),
    )
    counter_current = HeatExchanger(
        flow_arrangement="counter",
        n_species=2,
        ua=1800.0,
        hot_inlet_flow=2.0,
        hot_inlet_temperature=400.0,
        hot_inlet_pressure=101325.0,
        hot_inlet_composition=np.array([0.7, 0.3], dtype=np.float64),
        cold_inlet_flow=2.0,
        cold_inlet_temperature=300.0,
        cold_inlet_pressure=101325.0,
        cold_inlet_composition=np.array([0.3, 0.7], dtype=np.float64),
    )

    for unit in (co_current, counter_current):
        unit.set_property_package(cast(Any, package))
        _attach(unit)
        unit.step(0.1)

    assert counter_current.effectiveness >= co_current.effectiveness


def test_composition_preserved_on_both_streams() -> None:
    package = _ConstantCpPackage(cp_hot=110.0, cp_cold=95.0)
    hot_z = np.array([0.65, 0.35], dtype=np.float64)
    cold_z = np.array([0.15, 0.85], dtype=np.float64)
    exchanger = HeatExchanger(
        flow_arrangement="cross",
        n_species=2,
        ua=1200.0,
        hot_inlet_flow=2.5,
        hot_inlet_temperature=380.0,
        hot_inlet_pressure=130000.0,
        hot_inlet_composition=hot_z,
        cold_inlet_flow=1.6,
        cold_inlet_temperature=310.0,
        cold_inlet_pressure=125000.0,
        cold_inlet_composition=cold_z,
    )
    exchanger.set_property_package(cast(Any, package))
    _attach(exchanger)

    exchanger.step(0.1)

    assert np.asarray(exchanger.hot_outlet_composition, dtype=np.float64) == pytest.approx(hot_z)
    assert np.asarray(exchanger.cold_outlet_composition, dtype=np.float64) == pytest.approx(cold_z)

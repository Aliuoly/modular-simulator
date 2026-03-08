from __future__ import annotations

# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false

from types import SimpleNamespace
from typing import Any, cast

import numpy as np
import pytest

from modular_simulation.connection.hydraulic_compile import calculate_effective_valve_resistance
from modular_simulation.connection.hydraulic_element import (
    PumpHydraulicElement,
    ValveHydraulicElement,
    smooth_signed_quadratic_flow_term,
)
from modular_simulation.thermodynamics.property_package import FlashResult
from modular_simulation.unit_processes import Pump, Valve


def _attach(model: Pump | Valve) -> None:
    model.attach_system(cast(Any, SimpleNamespace(solver_options={})))


class _SyntheticLiquidPackage:
    cp_molar: float
    density_value: float
    molecular_weight_value: float
    pressure_enthalpy_coeff: float

    def __init__(
        self,
        *,
        cp_molar: float,
        density_value: float,
        molecular_weight_value: float,
        pressure_enthalpy_coeff: float,
    ) -> None:
        self.cp_molar = cp_molar
        self.density_value = density_value
        self.molecular_weight_value = molecular_weight_value
        self.pressure_enthalpy_coeff = pressure_enthalpy_coeff

    def flash_tp(self, T: float, P: float, z: tuple[float, ...]) -> FlashResult:
        enthalpy = self.cp_molar * T + self.pressure_enthalpy_coeff * P
        return FlashResult(
            temperature=T,
            pressure=P,
            vapor_fraction=0.0,
            phase="liquid",
            liquid_composition=z,
            vapor_composition=None,
            enthalpy_molar=enthalpy,
            entropy_molar=T,
            liquid_density=self.density_value,
            vapor_density=None,
            K_values=None,
        )

    def flash_ph(self, P: float, H: float, z: tuple[float, ...]) -> FlashResult:
        temperature = (H - self.pressure_enthalpy_coeff * P) / self.cp_molar
        return FlashResult(
            temperature=temperature,
            pressure=P,
            vapor_fraction=0.0,
            phase="liquid",
            liquid_composition=z,
            vapor_composition=None,
            enthalpy_molar=H,
            entropy_molar=temperature,
            liquid_density=self.density_value,
            vapor_density=None,
            K_values=None,
        )

    def flash_ps(self, P: float, S: float, z: tuple[float, ...]) -> FlashResult:
        del z
        return self.flash_tp(T=S, P=P, z=(1.0,))

    def enthalpy(self, T: float, P: float, z: tuple[float, ...], phase: str) -> float:
        del z, phase
        return self.cp_molar * T + self.pressure_enthalpy_coeff * P

    def entropy(self, T: float, P: float, z: tuple[float, ...], phase: str) -> float:
        del P, z, phase
        return T

    def density(self, T: float, P: float, z: tuple[float, ...], phase: str) -> float:
        del T, P, z, phase
        return self.density_value

    def heat_capacity_cp(self, T: float, P: float, z: tuple[float, ...], phase: str) -> float:
        del T, P, z, phase
        return self.cp_molar

    def molecular_weight(self, z: tuple[float, ...]) -> float:
        del z
        return self.molecular_weight_value

    @property
    def species_cas(self) -> tuple[str, ...]:
        return ("7732-18-5", "64-17-5")


def test_pump_pressure_power_and_hydraulic_invariant() -> None:
    package = _SyntheticLiquidPackage(
        cp_molar=90.0,
        density_value=1000.0,
        molecular_weight_value=18.0,
        pressure_enthalpy_coeff=0.0,
    )
    pump = Pump(
        n_species=2,
        inlet_flow=0.01,
        inlet_temperature=300.0,
        inlet_pressure=100000.0,
        inlet_composition=np.array([0.7, 0.3], dtype=np.float64),
        pump_speed=200000.0,
        efficiency=0.8,
    )
    pump.set_property_package(cast(Any, package))
    _attach(pump)

    pump.step(0.1)

    expected_power = 0.01 * 200000.0 / 0.8
    cp_mass = package.cp_molar / (package.molecular_weight_value / 1000.0)
    expected_delta_t = 200000.0 / (0.8 * package.density_value * cp_mass)

    assert pump.outlet_flow == pytest.approx(pump.inlet_flow)
    assert pump.outlet_pressure == pytest.approx(300000.0)
    assert pump.power_consumed == pytest.approx(expected_power)
    assert pump.outlet_temperature == pytest.approx(300.0 + expected_delta_t)
    assert pump.outlet_temperature > pump.inlet_temperature

    hydraulic = PumpHydraulicElement(
        dp_curve=lambda flow_rate, pump_speed: pump_speed,
        d_dp_d_mdot=lambda flow_rate, pump_speed: 0.0,
    )
    residual = hydraulic.residuals(
        inputs={
            "upstream_pressure": pump.inlet_pressure,
            "downstream_pressure": pump.outlet_pressure,
        },
        unknowns={"flow_rate": pump.inlet_flow},
        parameters={"pump_speed": pump.pump_speed},
    )["head_balance"]
    assert residual == pytest.approx(0.0, abs=1.0e-9)


def test_valve_pressure_drop_and_isenthalpic_invariant() -> None:
    package = _SyntheticLiquidPackage(
        cp_molar=100.0,
        density_value=950.0,
        molecular_weight_value=18.0,
        pressure_enthalpy_coeff=2.0e-3,
    )
    valve = Valve(
        n_species=2,
        inlet_flow=0.02,
        inlet_temperature=320.0,
        inlet_pressure=250000.0,
        inlet_composition=np.array([0.5, 0.5], dtype=np.float64),
        open_fraction=0.5,
        Cv=0.002,
        delta=1.0e-6,
    )
    valve.set_property_package(cast(Any, package))
    _attach(valve)

    valve.step(0.1)

    resistance_when_open = 1.0 / (valve.Cv * valve.Cv)
    effective_resistance = calculate_effective_valve_resistance(
        resistance_when_open=resistance_when_open,
        open_fraction=valve.open_fraction,
        minimum_open_fraction=valve.minimum_open_fraction,
        maximum_open_fraction=valve.maximum_open_fraction,
        min_relative_open_fraction=valve.min_relative_open_fraction,
    )
    flow_term = smooth_signed_quadratic_flow_term(m_dot=valve.inlet_flow, delta=valve.delta)
    expected_outlet_pressure = valve.inlet_pressure - effective_resistance * flow_term
    h_in = (
        package.cp_molar * valve.inlet_temperature
        + package.pressure_enthalpy_coeff * valve.inlet_pressure
    )
    expected_outlet_temperature = (
        h_in - package.pressure_enthalpy_coeff * expected_outlet_pressure
    ) / package.cp_molar

    assert valve.outlet_flow == pytest.approx(valve.inlet_flow)
    assert valve.outlet_pressure == pytest.approx(expected_outlet_pressure)
    assert valve.outlet_enthalpy == pytest.approx(h_in)
    assert valve.outlet_temperature == pytest.approx(expected_outlet_temperature)

    hydraulic = ValveHydraulicElement()
    residual = hydraulic.residuals(
        inputs={
            "upstream_pressure": valve.inlet_pressure,
            "downstream_pressure": valve.outlet_pressure,
        },
        unknowns={"flow_rate": valve.inlet_flow},
        parameters={"valve_resistance": effective_resistance, "delta": valve.delta},
    )["head_balance"]
    assert residual == pytest.approx(0.0, abs=1.0e-9)


@pytest.mark.parametrize(
    ("kwargs", "error_match"),
    [
        ({"inlet_flow": -1.0}, "inlet_flow must be finite and non-negative"),
        ({"efficiency": 0.0}, "efficiency must be finite and in \\(0, 1]"),
        ({"efficiency": 1.1}, "efficiency must be finite and in \\(0, 1]"),
    ],
)
def test_pump_invalid_inputs_raise(kwargs: dict[str, object], error_match: str) -> None:
    params: dict[str, object] = {
        "n_species": 2,
        "inlet_flow": 0.01,
        "inlet_temperature": 300.0,
        "inlet_pressure": 100000.0,
        "inlet_composition": np.array([0.5, 0.5], dtype=np.float64),
        "pump_speed": 50000.0,
        "efficiency": 0.75,
    }
    params.update(kwargs)

    with pytest.raises(ValueError, match=error_match):
        _ = Pump(**cast(Any, params))


def test_pump_constructor_accepts_legacy_pressure_rise_alias_with_warning() -> None:
    with pytest.warns(DeprecationWarning, match="pressure_rise is deprecated; use pump_speed"):
        pump = cast(
            Pump,
            Pump.model_validate(
                cast(
                    Any,
                    {
                        "n_species": 2,
                        "inlet_flow": 0.01,
                        "inlet_temperature": 300.0,
                        "inlet_pressure": 100000.0,
                        "inlet_composition": np.array([0.5, 0.5], dtype=np.float64),
                        "pressure_rise": 50000.0,
                        "efficiency": 0.75,
                    },
                )
            ),
        )

    assert pump.pump_speed == pytest.approx(50000.0)


@pytest.mark.parametrize(
    ("kwargs", "error_match"),
    [
        ({"inlet_flow": -0.01}, "inlet_flow must be finite and non-negative"),
        ({"Cv": 0.0}, "Cv must be finite and positive"),
        ({"open_fraction": 1.5}, "open_fraction must be within configured min/max bounds"),
    ],
)
def test_valve_invalid_inputs_raise(kwargs: dict[str, object], error_match: str) -> None:
    params: dict[str, object] = {
        "n_species": 2,
        "inlet_flow": 0.02,
        "inlet_temperature": 320.0,
        "inlet_pressure": 250000.0,
        "inlet_composition": np.array([0.5, 0.5], dtype=np.float64),
        "open_fraction": 0.5,
        "Cv": 0.01,
    }
    params.update(kwargs)

    with pytest.raises(ValueError, match=error_match):
        _ = Valve(**cast(Any, params))

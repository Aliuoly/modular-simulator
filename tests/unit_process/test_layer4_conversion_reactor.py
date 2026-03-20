from __future__ import annotations

# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false

from types import SimpleNamespace
from typing import Any, cast

import numpy as np
import pytest

from modular_simulation.thermodynamics.hydraulic_participation import (
    HydraulicBalancingGroupSpec,
    HydraulicParticipationSpec,
    HydraulicPortSpec,
    HydraulicRelationSpec,
    HydraulicScalarStateRef,
)
from modular_simulation.thermodynamics.property_package import FlashResult
from modular_simulation.unit_processes import ConversionReactor


def _attach(model: ConversionReactor) -> None:
    model.attach_system(cast(Any, SimpleNamespace(solver_options={})))


class _LinearShiftEnthalpyPackage:
    cp: float
    shift: float
    flash_tp_calls: int
    flash_ph_calls: int

    def __init__(self, *, cp: float, shift: float) -> None:
        self.cp = cp
        self.shift = shift
        self.flash_tp_calls = 0
        self.flash_ph_calls = 0

    def _mix_marker(self, z: tuple[float, ...]) -> float:
        return float(z[-1]) if z else 0.0

    def flash_tp(self, T: float, P: float, z: tuple[float, ...]) -> FlashResult:
        self.flash_tp_calls += 1
        marker = self._mix_marker(z)
        return FlashResult(
            temperature=T,
            pressure=P,
            vapor_fraction=0.0,
            phase="liquid",
            liquid_composition=z,
            vapor_composition=None,
            enthalpy_molar=self.cp * T + self.shift * marker,
            entropy_molar=T,
            liquid_density=900.0,
            vapor_density=None,
            K_values=None,
        )

    def flash_ph(self, P: float, H: float, z: tuple[float, ...]) -> FlashResult:
        self.flash_ph_calls += 1
        marker = self._mix_marker(z)
        temperature = (H - self.shift * marker) / self.cp
        return FlashResult(
            temperature=temperature,
            pressure=P,
            vapor_fraction=0.0,
            phase="liquid",
            liquid_composition=z,
            vapor_composition=None,
            enthalpy_molar=H,
            entropy_molar=temperature,
            liquid_density=900.0,
            vapor_density=None,
            K_values=None,
        )


def test_50pct_conversion_mass_balance() -> None:
    reactor = ConversionReactor(
        n_species=2,
        thermal_mode="isothermal",
        pressure_drop=5000.0,
        inlet_flow=10.0,
        inlet_temperature=350.0,
        inlet_pressure=200000.0,
        inlet_composition=np.array([0.8, 0.2], dtype=np.float64),
        conversions={"A": 0.5},
        stoichiometry={"A": {"A": -1.0, "B": 1.0}},
        species_order=("A", "B"),
    )
    _attach(reactor)

    reactor.step(0.1)

    assert reactor.outlet_flow == pytest.approx(10.0)
    assert reactor.outlet_pressure == pytest.approx(195000.0)
    assert reactor.outlet_temperature == pytest.approx(350.0)
    assert np.asarray(reactor.outlet_composition, dtype=np.float64) == pytest.approx(
        np.array([0.4, 0.6], dtype=np.float64)
    )


def test_adiabatic_mode_conserves_enthalpy_via_flash_ph() -> None:
    package = _LinearShiftEnthalpyPackage(cp=100.0, shift=500.0)
    reactor = ConversionReactor(
        n_species=2,
        thermal_mode="adiabatic",
        inlet_flow=10.0,
        inlet_temperature=400.0,
        inlet_pressure=300000.0,
        inlet_composition=np.array([0.8, 0.2], dtype=np.float64),
        conversions={"A": 0.5},
        stoichiometry={"A": {"A": -1.0, "B": 1.0}},
        species_order=("A", "B"),
    )
    reactor.set_property_package(cast(Any, package))
    _attach(reactor)

    reactor.step(0.1)

    inlet_enthalpy = 100.0 * 400.0 + 500.0 * 0.2
    expected_outlet_temperature = (inlet_enthalpy - 500.0 * 0.6) / 100.0
    assert reactor.outlet_temperature == pytest.approx(expected_outlet_temperature)
    assert reactor.outlet_enthalpy == pytest.approx(inlet_enthalpy)
    assert package.flash_tp_calls >= 1
    assert package.flash_ph_calls >= 1


def test_isothermal_mode_enforces_outlet_temperature() -> None:
    package = _LinearShiftEnthalpyPackage(cp=80.0, shift=120.0)
    reactor = ConversionReactor(
        n_species=2,
        thermal_mode="isothermal",
        inlet_flow=5.0,
        inlet_temperature=333.3,
        inlet_pressure=101325.0,
        inlet_composition=np.array([0.7, 0.3], dtype=np.float64),
        conversions={"A": 0.25},
        stoichiometry={"A": {"A": -1.0, "B": 1.0}},
        species_order=("A", "B"),
    )
    reactor.set_property_package(cast(Any, package))
    _attach(reactor)

    reactor.step(0.1)

    assert reactor.outlet_temperature == pytest.approx(reactor.inlet_temperature)
    assert package.flash_tp_calls >= 2
    assert package.flash_ph_calls == 0


@pytest.mark.parametrize("invalid_conversion", [-0.1, 1.1])
def test_invalid_conversion_bounds_raise(invalid_conversion: float) -> None:
    with pytest.raises(ValueError, match=r"within \[0, 1\]"):
        _ = ConversionReactor(
            n_species=2,
            inlet_flow=1.0,
            inlet_temperature=300.0,
            inlet_pressure=101325.0,
            inlet_composition=np.array([0.5, 0.5], dtype=np.float64),
            conversions={"A": invalid_conversion},
            species_order=("A", "B"),
        )


def test_pressure_drop_remains_fixed_hydraulic_data() -> None:
    reactor = ConversionReactor(n_species=2, pressure_drop=750.0)

    assert "pressure_drop" not in reactor.boundary_view.state_list
    assert "pressure_drop" in reactor.constant_view.state_list


def test_conversion_reactor_declares_explicit_hydraulic_participation() -> None:
    reactor = ConversionReactor(n_species=2)

    assert reactor.hydraulic_participation == HydraulicParticipationSpec(
        ports={
            "inlet": HydraulicPortSpec(
                role="pressure_state",
                pressure_state=HydraulicScalarStateRef("inlet_pressure"),
            ),
            "outlet": HydraulicPortSpec(
                role="pressure_state",
                pressure_state=HydraulicScalarStateRef("outlet_pressure"),
            ),
        },
        balancing_groups=(
            HydraulicBalancingGroupSpec(name="flow_balance", ports=("inlet", "outlet")),
        ),
        relations=(
            HydraulicRelationSpec(
                name="pressure_drop",
                kind="pressure_drop",
                ports=("inlet", "outlet"),
                parameter_state=HydraulicScalarStateRef("pressure_drop"),
            ),
        ),
    )

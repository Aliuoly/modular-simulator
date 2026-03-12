from __future__ import annotations

# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false

from dataclasses import dataclass
from typing import cast

import numpy as np
import pytest

from modular_simulation.framework.system import System
from modular_simulation.thermodynamics.property_package import PengRobinsonPackage
from modular_simulation.unit_processes import FlashDrum


@dataclass
class _StubSystem:
    solver_options: dict[str, object]


def _attach(model: FlashDrum) -> None:
    model.attach_system(cast(System, cast(object, _StubSystem(solver_options={}))))


@pytest.fixture(scope="module")
def binary_package() -> PengRobinsonPackage:
    return PengRobinsonPackage(species_ids=("7732-18-5", "64-17-5"))


def test_binary_isothermal_flash(binary_package: PengRobinsonPackage) -> None:
    drum = FlashDrum(
        thermal_mode="isothermal",
        n_species=2,
        inlet_flow=10.0,
        inlet_temperature=340.0,
        inlet_pressure=101325.0,
        inlet_composition=np.array([0.5, 0.5], dtype=np.float64),
        imposed_pressure=101325.0,
        imposed_temperature=350.0,
    )
    drum.set_property_package(binary_package)
    _attach(drum)

    drum.step(0.1)

    assert 0.0 < drum.vapor_fraction < 1.0
    assert drum.vapor_flow + drum.liquid_flow == pytest.approx(drum.inlet_flow)

    y = np.asarray(drum.vapor_composition, dtype=np.float64)
    x = np.asarray(drum.liquid_composition, dtype=np.float64)
    z_in = np.asarray(drum.inlet_composition, dtype=np.float64)
    vf = float(drum.vapor_fraction)

    assert float(np.sum(y)) == pytest.approx(1.0, abs=1.0e-8)
    assert float(np.sum(x)) == pytest.approx(1.0, abs=1.0e-8)

    reconstructed_z = vf * y + (1.0 - vf) * x
    assert reconstructed_z == pytest.approx(z_in, abs=1.0e-5)

    component_out = drum.vapor_flow * y + drum.liquid_flow * x
    assert component_out == pytest.approx(drum.inlet_flow * z_in, abs=1.0e-5)


def test_adiabatic_flash_energy(binary_package: PengRobinsonPackage) -> None:
    z = (0.5000004, 0.4999996)
    inlet_flash = binary_package.flash_tp(T=350.0, P=101325.0, z=z)

    drum = FlashDrum(
        thermal_mode="adiabatic",
        n_species=2,
        inlet_flow=8.0,
        inlet_temperature=350.0,
        inlet_pressure=101325.0,
        inlet_composition=np.array(z, dtype=np.float64),
        imposed_pressure=85000.0,
        imposed_temperature=330.0,
    )
    drum.set_property_package(binary_package)
    _attach(drum)

    drum.step(0.1)

    expected = binary_package.flash_ph(P=85000.0, H=inlet_flash.enthalpy_molar, z=z)
    assert drum.outlet_temperature == pytest.approx(expected.temperature, abs=1.0e-6)
    assert drum.vapor_fraction == pytest.approx(expected.vapor_fraction, abs=1.0e-8)

    y_array = cast(np.ndarray[tuple[int], np.dtype[np.float64]], drum.vapor_composition)
    x_array = cast(np.ndarray[tuple[int], np.dtype[np.float64]], drum.liquid_composition)
    y = tuple(float(value) for value in y_array)
    x = tuple(float(value) for value in x_array)
    vf = float(drum.vapor_fraction)
    h_v = binary_package.enthalpy(T=drum.outlet_temperature, P=85000.0, z=y, phase="vapor")
    h_l = binary_package.enthalpy(T=drum.outlet_temperature, P=85000.0, z=x, phase="liquid")
    h_out = vf * h_v + (1.0 - vf) * h_l
    assert h_out == pytest.approx(inlet_flash.enthalpy_molar, abs=0.5)


@pytest.mark.parametrize(
    ("temperature", "expected_vf"),
    [
        (300.0, 0.0),
        (430.0, 1.0),
    ],
)
def test_vf_boundary_compositions_are_valid(temperature: float, expected_vf: float) -> None:
    package = PengRobinsonPackage(species_ids=("7732-18-5",))
    drum = FlashDrum(
        thermal_mode="isothermal",
        n_species=1,
        inlet_flow=5.0,
        inlet_temperature=350.0,
        inlet_pressure=101325.0,
        inlet_composition=np.array([1.0], dtype=np.float64),
        imposed_pressure=101325.0,
        imposed_temperature=temperature,
    )
    drum.set_property_package(package)
    _attach(drum)

    drum.step(0.1)

    assert drum.vapor_fraction == pytest.approx(expected_vf, abs=1.0e-8)
    assert drum.vapor_flow + drum.liquid_flow == pytest.approx(drum.inlet_flow)

    y = np.asarray(drum.vapor_composition, dtype=np.float64)
    x = np.asarray(drum.liquid_composition, dtype=np.float64)
    assert np.all(np.isfinite(y))
    assert np.all(np.isfinite(x))
    assert float(np.sum(y)) == pytest.approx(1.0, abs=1.0e-8)
    assert float(np.sum(x)) == pytest.approx(1.0, abs=1.0e-8)

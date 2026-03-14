from __future__ import annotations

# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false

from types import SimpleNamespace
from typing import Any, cast

import numpy as np
import pytest

from modular_simulation.components import ControlElement, ControllerMode, Trajectory
from modular_simulation.framework.system import System
from modular_simulation.thermodynamics.property_package import FlashResult
from modular_simulation.unit_processes import HeaterCooler


def _attach(model: HeaterCooler) -> None:
    model.attach_system(cast(Any, SimpleNamespace(solver_options={})))


class _LinearEnthalpyPackage:
    cp: float
    flash_tp_calls: int
    flash_ph_calls: int

    def __init__(self, cp: float) -> None:
        self.cp = cp
        self.flash_tp_calls = 0
        self.flash_ph_calls = 0

    def flash_tp(self, T: float, P: float, z: tuple[float, ...]) -> FlashResult:
        self.flash_tp_calls += 1
        return FlashResult(
            temperature=T,
            pressure=P,
            vapor_fraction=0.0,
            phase="liquid",
            liquid_composition=z,
            vapor_composition=None,
            enthalpy_molar=self.cp * T,
            entropy_molar=T,
            liquid_density=1000.0,
            vapor_density=None,
            K_values=None,
        )

    def flash_ph(self, P: float, H: float, z: tuple[float, ...]) -> FlashResult:
        self.flash_ph_calls += 1
        temperature = H / self.cp
        return FlashResult(
            temperature=temperature,
            pressure=P,
            vapor_fraction=0.0,
            phase="liquid",
            liquid_composition=z,
            vapor_composition=None,
            enthalpy_molar=H,
            entropy_molar=temperature,
            liquid_density=1000.0,
            vapor_density=None,
            K_values=None,
        )


def test_heater_duty_mode_energy_balance() -> None:
    package = _LinearEnthalpyPackage(cp=100.0)
    heater = HeaterCooler(
        mode="duty",
        n_species=2,
        inlet_flow=2.0,
        inlet_temperature=300.0,
        inlet_pressure=200000.0,
        inlet_composition=np.array([0.7, 0.3], dtype=np.float64),
        pressure_drop=5000.0,
        external_heat_duty=1000.0,
    )
    heater.set_property_package(cast(Any, package))
    _attach(heater)

    heater.step(0.1)

    assert heater.outlet_pressure == pytest.approx(195000.0)
    assert heater.outlet_temperature == pytest.approx(305.0)
    assert heater.outlet_enthalpy == pytest.approx(30500.0)
    assert heater.duty == pytest.approx(1000.0)
    assert heater.duty == pytest.approx(
        heater.inlet_flow * (heater.outlet_enthalpy - package.cp * heater.inlet_temperature)
    )
    assert package.flash_tp_calls >= 1
    assert package.flash_ph_calls >= 1


def test_cooler_temperature_mode_computes_duty() -> None:
    package = _LinearEnthalpyPackage(cp=100.0)
    cooler = HeaterCooler(
        mode="temperature",
        n_species=2,
        inlet_flow=1.5,
        inlet_temperature=360.0,
        inlet_pressure=160000.0,
        inlet_composition=np.array([0.4, 0.6], dtype=np.float64),
        pressure_drop=2000.0,
        external_outlet_temperature=320.0,
    )
    cooler.set_property_package(cast(Any, package))
    _attach(cooler)

    cooler.step(0.1)

    assert cooler.outlet_pressure == pytest.approx(158000.0)
    assert cooler.outlet_temperature == pytest.approx(320.0)
    assert cooler.duty == pytest.approx(-6000.0)
    assert cooler.duty < 0.0
    assert package.flash_tp_calls >= 2
    assert package.flash_ph_calls == 0


def test_zero_duty_leaves_state_unchanged() -> None:
    package = _LinearEnthalpyPackage(cp=120.0)
    heater = HeaterCooler(
        mode="duty",
        n_species=2,
        inlet_flow=3.0,
        inlet_temperature=330.0,
        inlet_pressure=101325.0,
        inlet_composition=np.array([0.5, 0.5], dtype=np.float64),
        pressure_drop=0.0,
        external_heat_duty=0.0,
    )
    heater.set_property_package(cast(Any, package))
    _attach(heater)

    heater.step(0.1)

    assert heater.outlet_temperature == pytest.approx(heater.inlet_temperature)
    assert heater.outlet_pressure == pytest.approx(heater.inlet_pressure)
    assert np.asarray(heater.outlet_composition, dtype=np.float64) == pytest.approx(
        np.asarray(heater.inlet_composition, dtype=np.float64)
    )
    assert heater.duty == pytest.approx(0.0)


def test_outlet_pressure_applies_drop_with_positive_floor() -> None:
    package = _LinearEnthalpyPackage(cp=100.0)
    cooler = HeaterCooler(
        mode="temperature",
        n_species=2,
        inlet_flow=1.0,
        inlet_temperature=330.0,
        inlet_pressure=5.0,
        inlet_composition=np.array([0.2, 0.8], dtype=np.float64),
        pressure_drop=100.0,
        external_outlet_temperature=320.0,
    )
    cooler.set_property_package(cast(Any, package))
    _attach(cooler)

    cooler.step(0.1)

    assert cooler.outlet_pressure == pytest.approx(1.0e-9)


def test_invalid_mode_raises() -> None:
    with pytest.raises(ValueError, match="mode must be either 'duty' or 'temperature'"):
        _ = HeaterCooler(mode=cast(Any, "invalid"), n_species=2)


def test_negative_inlet_flow_raises() -> None:
    with pytest.raises(ValueError, match="inlet_flow must be finite and non-negative"):
        _ = HeaterCooler(
            mode="duty",
            n_species=2,
            inlet_flow=-1.0,
            inlet_composition=np.array([0.5, 0.5], dtype=np.float64),
        )


def test_heater_cooler_uses_external_boundary_names_not_controller_proxies() -> None:
    heater = HeaterCooler(mode="temperature", n_species=2)

    assert "pressure_drop" not in heater.boundary_view.state_list
    assert "external_heat_duty" in heater.boundary_view.state_list
    assert "external_outlet_temperature" in heater.boundary_view.state_list
    assert "duty_setpoint" not in heater.state_list
    assert "target_temperature_setpoint" not in heater.state_list
    assert "external_heat_duty" not in heater.constant_view.state_list
    assert "external_outlet_temperature" not in heater.constant_view.state_list


def test_legacy_setpoint_inputs_warn_and_normalize() -> None:
    with pytest.warns(
        DeprecationWarning, match="duty_setpoint is deprecated; use external_heat_duty"
    ):
        with pytest.warns(
            DeprecationWarning,
            match="target_temperature_setpoint is deprecated; use external_outlet_temperature",
        ):
            heater = HeaterCooler(
                **cast(
                    Any,
                    {
                        "mode": "temperature",
                        "n_species": 2,
                        "duty_setpoint": 123.0,
                        "target_temperature_setpoint": 345.0,
                    },
                )
            )

    assert heater.external_heat_duty == pytest.approx(123.0)
    assert heater.external_outlet_temperature == pytest.approx(345.0)


def test_heater_cooler_well_mixed_external_boundaries_are_driven_via_heat_actuator_plane() -> None:
    heater = HeaterCooler(
        mode="duty",
        n_species=2,
        inlet_flow=2.0,
        inlet_temperature=320.0,
        inlet_pressure=101325.0,
        inlet_composition=np.array([0.6, 0.4], dtype=np.float64),
        external_heat_duty=250.0,
        external_outlet_temperature=330.0,
    )
    system = System(
        dt=0.1,
        process_model=heater,
        sensors=[],
        calculations=[],
        control_elements=[
            ControlElement(
                mv_tag="actuator/heat/heater_cooler_loop",
                mv_range=(-20000.0, 20000.0),
                mv_trajectory=Trajectory(y0=-1500.0),
                mode=ControllerMode.MANUAL,
            )
        ],
        show_progress=False,
    )

    system.step(duration=0.1)
    pending_heat_commands = system.consume_pending_heat_actuator_rate_commands()

    assert heater.external_heat_duty == pytest.approx(250.0)
    assert heater.external_outlet_temperature == pytest.approx(330.0)
    assert "actuator/heat/heater_cooler_loop" in pending_heat_commands
    assert pending_heat_commands["actuator/heat/heater_cooler_loop"] == pytest.approx(-1500.0)

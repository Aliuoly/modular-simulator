from __future__ import annotations

# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnusedCallResult=false

from types import SimpleNamespace
from typing import cast

import numpy as np
import pytest

from modular_simulation.thermodynamics.property_package import PropertyPackage
from modular_simulation.thermodynamics.property_package import FlashResult
from modular_simulation.thermodynamics.stream import StreamData
from modular_simulation.framework.system import System
from modular_simulation.unit_processes import (
    ComponentSeparator,
    ConversionReactor,
    CSTR,
    FlashDrum,
    HeatExchanger,
    HeaterCooler,
    PFR,
    ShortcutDistillation,
)


def _attach(
    model: (
        HeaterCooler
        | ConversionReactor
        | CSTR
        | ComponentSeparator
        | FlashDrum
        | ShortcutDistillation
        | HeatExchanger
        | PFR
    ),
) -> None:
    model.attach_system(cast(System, cast(object, SimpleNamespace(solver_options={}))))


class _DensityPackage:
    _density_kg_m3: float
    _molecular_weight_g_mol: float

    def __init__(self, *, density_kg_m3: float, molecular_weight_g_mol: float) -> None:
        self._density_kg_m3 = density_kg_m3
        self._molecular_weight_g_mol = molecular_weight_g_mol

    def flash_tp(self, T: float, P: float, z: tuple[float, ...]) -> FlashResult:
        return FlashResult(
            temperature=T,
            pressure=P,
            vapor_fraction=0.0,
            phase="liquid",
            liquid_composition=z,
            vapor_composition=None,
            enthalpy_molar=0.0,
            entropy_molar=0.0,
            liquid_density=self._density_kg_m3,
            vapor_density=None,
            K_values=None,
        )

    def density(self, T: float, P: float, z: tuple[float, ...], phase: str) -> float:
        del T, P, z, phase
        return self._density_kg_m3

    def molecular_weight(self, z: tuple[float, ...]) -> float:
        del z
        return self._molecular_weight_g_mol


def test_heater_cooler_stream_port_round_trip() -> None:
    heater = HeaterCooler(
        mode="duty",
        n_species=2,
        pressure_drop=0.0,
        inlet_composition=np.array([0.5, 0.5], dtype=np.float64),
    )
    _attach(heater)

    inlet = StreamData(
        temperature=345.0,
        pressure=205000.0,
        mole_fractions=(0.2, 0.8),
        molar_flow_rate=3.5,
    )
    heater.apply_inlet("inlet", inlet)
    heater.step(0.1)

    outlet = heater.get_outlet_stream("outlet")
    assert outlet.temperature == pytest.approx(inlet.temperature)
    assert outlet.pressure == pytest.approx(inlet.pressure)
    assert outlet.molar_flow_rate == pytest.approx(inlet.molar_flow_rate)
    assert outlet.mole_fractions == pytest.approx(inlet.mole_fractions)


def test_cstr_flow_conversion_uses_density() -> None:
    package = _DensityPackage(density_kg_m3=950.0, molecular_weight_g_mol=44.0)
    cstr = CSTR(
        n_species=2,
        inlet_composition=np.array([0.5, 0.5], dtype=np.float64),
        outlet_composition=np.array([0.5, 0.5], dtype=np.float64),
    )
    cstr.set_property_package(cast(PropertyPackage, cast(object, package)))

    inlet = StreamData(
        temperature=305.0,
        pressure=150000.0,
        mole_fractions=(0.3, 0.7),
        molar_flow_rate=40.0,
    )
    cstr.apply_inlet("inlet", inlet)

    expected_inlet_l_s = 40.0 * 44.0 / 950.0
    assert cstr.inlet_flow == pytest.approx(expected_inlet_l_s)

    cstr.outlet_flow = expected_inlet_l_s * 1.5
    cstr.outlet_temperature = 315.0
    cstr.pressure = 149000.0
    cstr.outlet_composition = np.array([0.4, 0.6], dtype=np.float64)

    outlet = cstr.get_outlet_stream("outlet")
    assert outlet.molar_flow_rate == pytest.approx(60.0)
    assert outlet.temperature == pytest.approx(315.0)
    assert outlet.pressure == pytest.approx(149000.0)
    assert outlet.mole_fractions == pytest.approx((0.4, 0.6))


def test_pfr_flow_conversion_uses_density() -> None:
    package = _DensityPackage(density_kg_m3=880.0, molecular_weight_g_mol=28.0)
    pfr = PFR(
        n_species=2,
        inlet_composition=np.array([0.5, 0.5], dtype=np.float64),
        outlet_composition=np.array([0.5, 0.5], dtype=np.float64),
    )
    pfr.set_property_package(cast(PropertyPackage, cast(object, package)))

    inlet = StreamData(
        temperature=330.0,
        pressure=170000.0,
        mole_fractions=(0.2, 0.8),
        molar_flow_rate=55.0,
    )
    pfr.apply_inlet("inlet", inlet)

    expected_inlet_l_s = 55.0 * 28.0 / 880.0
    assert pfr.inlet_flow == pytest.approx(expected_inlet_l_s)

    pfr.outlet_flow = expected_inlet_l_s * 2.0
    pfr.outlet_temperature = 340.0
    pfr.pressure = 165000.0
    pfr.outlet_composition = np.array([0.25, 0.75], dtype=np.float64)

    outlet = pfr.get_outlet_stream("outlet")
    assert outlet.molar_flow_rate == pytest.approx(110.0)
    assert outlet.temperature == pytest.approx(340.0)
    assert outlet.pressure == pytest.approx(165000.0)
    assert outlet.mole_fractions == pytest.approx((0.25, 0.75))


@pytest.mark.parametrize(
    "unit",
    [
        CSTR(
            n_species=2,
            inlet_composition=np.array([0.5, 0.5], dtype=np.float64),
            outlet_composition=np.array([0.5, 0.5], dtype=np.float64),
        ),
        PFR(
            n_species=2,
            inlet_composition=np.array([0.5, 0.5], dtype=np.float64),
            outlet_composition=np.array([0.5, 0.5], dtype=np.float64),
        ),
    ],
)
def test_reactor_stream_port_round_trip_within_one_percent(unit: CSTR | PFR) -> None:
    package = _DensityPackage(density_kg_m3=998.0, molecular_weight_g_mol=18.0)
    unit.set_property_package(cast(PropertyPackage, cast(object, package)))

    inlet = StreamData(
        temperature=300.0,
        pressure=101325.0,
        mole_fractions=(0.5, 0.5),
        molar_flow_rate=75.0,
    )
    unit.apply_inlet("inlet", inlet)

    unit.outlet_flow = unit.inlet_flow
    unit.outlet_temperature = inlet.temperature
    unit.pressure = inlet.pressure
    unit.outlet_composition = np.array(inlet.mole_fractions, dtype=np.float64)
    outlet = unit.get_outlet_stream("outlet")

    assert outlet.molar_flow_rate == pytest.approx(inlet.molar_flow_rate, rel=0.01)


@pytest.mark.parametrize(
    "unit",
    [
        CSTR(
            n_species=2,
            inlet_composition=np.array([0.5, 0.5], dtype=np.float64),
            outlet_composition=np.array([0.5, 0.5], dtype=np.float64),
        ),
        PFR(
            n_species=2,
            inlet_composition=np.array([0.5, 0.5], dtype=np.float64),
            outlet_composition=np.array([0.5, 0.5], dtype=np.float64),
        ),
    ],
)
def test_reactor_volumetric_units_raise_clear_error_without_property_package(
    unit: CSTR | PFR,
) -> None:
    stream = StreamData(
        temperature=300.0,
        pressure=101325.0,
        mole_fractions=(0.5, 0.5),
        molar_flow_rate=1.0,
    )

    with pytest.raises(ValueError, match="property package.*density"):
        unit.apply_inlet("inlet", stream)


def test_component_separator_dual_outlets_return_distinct_streams() -> None:
    separator = ComponentSeparator(
        n_species=2,
        configured_split_fraction_targets=np.array([0.8, 0.2], dtype=np.float64),
        inlet_composition=np.array([0.5, 0.5], dtype=np.float64),
    )
    inlet = StreamData(
        temperature=330.0,
        pressure=175000.0,
        mole_fractions=(0.25, 0.75),
        molar_flow_rate=12.0,
    )
    separator.apply_inlet("inlet", inlet)

    separator.outlet_1_flow = 3.0
    separator.outlet_1_temperature = 329.0
    separator.outlet_1_pressure = 174000.0
    separator.outlet_1_composition = np.array([0.5, 0.5], dtype=np.float64)

    separator.outlet_2_flow = 9.0
    separator.outlet_2_temperature = 331.0
    separator.outlet_2_pressure = 173000.0
    separator.outlet_2_composition = np.array([0.1, 0.9], dtype=np.float64)

    outlet_1 = separator.get_outlet_stream("outlet_1")
    outlet_2 = separator.get_outlet_stream("outlet_2")

    assert outlet_1.molar_flow_rate == pytest.approx(3.0)
    assert outlet_1.temperature == pytest.approx(329.0)
    assert outlet_1.pressure == pytest.approx(174000.0)
    assert outlet_1.mole_fractions == pytest.approx((0.5, 0.5))

    assert outlet_2.molar_flow_rate == pytest.approx(9.0)
    assert outlet_2.temperature == pytest.approx(331.0)
    assert outlet_2.pressure == pytest.approx(173000.0)
    assert outlet_2.mole_fractions == pytest.approx((0.1, 0.9))


def test_flash_drum_dual_outlets_map_nonstandard_attributes() -> None:
    flash = FlashDrum(n_species=2)
    inlet = StreamData(
        temperature=350.0,
        pressure=220000.0,
        mole_fractions=(0.45, 0.55),
        molar_flow_rate=10.0,
    )
    flash.apply_inlet("inlet", inlet)

    flash.vapor_flow = 6.0
    flash.liquid_flow = 4.0
    flash.outlet_temperature = 340.0
    flash.outlet_pressure = 150000.0
    flash.vapor_composition = np.array([0.8, 0.2], dtype=np.float64)
    flash.liquid_composition = np.array([0.2, 0.8], dtype=np.float64)

    vapor = flash.get_outlet_stream("vapor_outlet")
    liquid = flash.get_outlet_stream("liquid_outlet")

    assert vapor.molar_flow_rate == pytest.approx(6.0)
    assert vapor.temperature == pytest.approx(340.0)
    assert vapor.pressure == pytest.approx(150000.0)
    assert vapor.mole_fractions == pytest.approx((0.8, 0.2))

    assert liquid.molar_flow_rate == pytest.approx(4.0)
    assert liquid.temperature == pytest.approx(340.0)
    assert liquid.pressure == pytest.approx(150000.0)
    assert liquid.mole_fractions == pytest.approx((0.2, 0.8))


def test_shortcut_distillation_outlets_use_condenser_and_reboiler_conditions() -> None:
    column = ShortcutDistillation(n_species=2)
    inlet = StreamData(
        temperature=360.0,
        pressure=190000.0,
        mole_fractions=(0.6, 0.4),
        molar_flow_rate=20.0,
    )
    column.apply_inlet("inlet", inlet)

    column.distillate_flow = 7.0
    column.bottoms_flow = 13.0
    column.distillate_composition = np.array([0.95, 0.05], dtype=np.float64)
    column.bottoms_composition = np.array([0.2, 0.8], dtype=np.float64)
    column.condenser_temperature = 325.0
    column.condenser_pressure = 135000.0
    column.reboiler_temperature = 385.0
    column.reboiler_pressure = 160000.0

    distillate = column.get_outlet_stream("distillate")
    bottoms = column.get_outlet_stream("bottoms")

    assert distillate.molar_flow_rate == pytest.approx(7.0)
    assert distillate.temperature == pytest.approx(325.0)
    assert distillate.pressure == pytest.approx(135000.0)
    assert distillate.mole_fractions == pytest.approx((0.95, 0.05))

    assert bottoms.molar_flow_rate == pytest.approx(13.0)
    assert bottoms.temperature == pytest.approx(385.0)
    assert bottoms.pressure == pytest.approx(160000.0)
    assert bottoms.mole_fractions == pytest.approx((0.2, 0.8))


def test_heat_exchanger_dual_inlet_and_dual_outlet_stream_io() -> None:
    hx = HeatExchanger(n_species=2)

    hot_feed = StreamData(
        temperature=420.0,
        pressure=250000.0,
        mole_fractions=(0.7, 0.3),
        molar_flow_rate=5.0,
    )
    cold_feed = StreamData(
        temperature=300.0,
        pressure=210000.0,
        mole_fractions=(0.1, 0.9),
        molar_flow_rate=8.0,
    )
    hx.apply_inlet("hot_inlet", hot_feed)
    hx.apply_inlet("cold_inlet", cold_feed)

    assert hx.hot_inlet_flow == pytest.approx(5.0)
    assert hx.cold_inlet_flow == pytest.approx(8.0)
    assert hx.hot_inlet_temperature == pytest.approx(420.0)
    assert hx.cold_inlet_temperature == pytest.approx(300.0)

    hx.hot_outlet_flow = 5.0
    hx.hot_outlet_temperature = 360.0
    hx.hot_outlet_pressure = 240000.0
    hx.hot_outlet_composition = np.array([0.65, 0.35], dtype=np.float64)

    hx.cold_outlet_flow = 8.0
    hx.cold_outlet_temperature = 335.0
    hx.cold_outlet_pressure = 200000.0
    hx.cold_outlet_composition = np.array([0.15, 0.85], dtype=np.float64)

    hot_out = hx.get_outlet_stream("hot_outlet")
    cold_out = hx.get_outlet_stream("cold_outlet")

    assert hot_out.molar_flow_rate == pytest.approx(5.0)
    assert hot_out.temperature == pytest.approx(360.0)
    assert hot_out.pressure == pytest.approx(240000.0)
    assert hot_out.mole_fractions == pytest.approx((0.65, 0.35))

    assert cold_out.molar_flow_rate == pytest.approx(8.0)
    assert cold_out.temperature == pytest.approx(335.0)
    assert cold_out.pressure == pytest.approx(200000.0)
    assert cold_out.mole_fractions == pytest.approx((0.15, 0.85))


@pytest.mark.parametrize(
    "unit",
    [
        HeaterCooler(mode="duty", n_species=2),
        ConversionReactor(n_species=2),
        ComponentSeparator(
            n_species=2,
            configured_split_fraction_targets=np.array([0.0, 0.0], dtype=np.float64),
        ),
        FlashDrum(n_species=2),
        ShortcutDistillation(n_species=2),
        HeatExchanger(n_species=2),
        CSTR(n_species=2),
        PFR(n_species=2),
    ],
)
def test_invalid_port_names_raise_clear_errors(
    unit: (
        HeaterCooler
        | ConversionReactor
        | ComponentSeparator
        | FlashDrum
        | ShortcutDistillation
        | HeatExchanger
        | CSTR
        | PFR
    ),
) -> None:
    stream = StreamData(
        temperature=300.0,
        pressure=101325.0,
        mole_fractions=(0.5, 0.5),
        molar_flow_rate=1.0,
    )

    with pytest.raises(ValueError, match="Invalid inlet port 'bad_inlet'"):
        unit.apply_inlet("bad_inlet", stream)

    with pytest.raises(ValueError, match="Invalid outlet port 'bad_outlet'"):
        _ = unit.get_outlet_stream("bad_outlet")

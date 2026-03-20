from __future__ import annotations

# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false

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


def test_flow_sensitivity_changes_capacity_rates_and_duty() -> None:
    package = _ConstantCpPackage(cp_hot=100.0, cp_cold=100.0)
    low_flow = HeatExchanger(
        flow_arrangement="counter",
        n_species=2,
        ua=2000.0,
        hot_inlet_flow=1.0,
        hot_inlet_temperature=400.0,
        hot_inlet_pressure=101325.0,
        hot_inlet_composition=np.array([0.8, 0.2], dtype=np.float64),
        cold_inlet_flow=1.0,
        cold_inlet_temperature=300.0,
        cold_inlet_pressure=101325.0,
        cold_inlet_composition=np.array([0.2, 0.8], dtype=np.float64),
    )
    high_flow = HeatExchanger(
        flow_arrangement="counter",
        n_species=2,
        ua=2000.0,
        hot_inlet_flow=4.0,
        hot_inlet_temperature=400.0,
        hot_inlet_pressure=101325.0,
        hot_inlet_composition=np.array([0.8, 0.2], dtype=np.float64),
        cold_inlet_flow=4.0,
        cold_inlet_temperature=300.0,
        cold_inlet_pressure=101325.0,
        cold_inlet_composition=np.array([0.2, 0.8], dtype=np.float64),
    )

    for unit in (low_flow, high_flow):
        unit.set_property_package(cast(Any, package))
        _attach(unit)
        unit.step(0.1)

    assert high_flow.c_hot > low_flow.c_hot
    assert high_flow.c_cold > low_flow.c_cold
    assert high_flow.ntu < low_flow.ntu
    assert high_flow.effectiveness < low_flow.effectiveness
    assert high_flow.heat_duty > low_flow.heat_duty


def test_hydraulic_participation_declares_all_four_ports_as_pressure_state() -> None:
    exchanger = HeatExchanger(
        n_species=2,
        ua=500.0,
        hot_inlet_composition=np.array([0.8, 0.2], dtype=np.float64),
        cold_inlet_composition=np.array([0.2, 0.8], dtype=np.float64),
    )

    spec = exchanger.hydraulic_participation
    assert spec is not None

    expected_ports = {"hot_inlet", "hot_outlet", "cold_inlet", "cold_outlet"}
    assert set(spec.ports.keys()) == expected_ports

    for port_name in expected_ports:
        port_spec = spec.ports[port_name]
        assert port_spec.role == "pressure_state", (
            f"Expected port '{port_name}' to have role 'pressure_state', got '{port_spec.role}'"
        )
        assert port_spec.pressure_state is not None, (
            f"Expected port '{port_name}' to have a pressure_state ref"
        )


def test_hydraulic_participation_has_two_balancing_groups_no_cross_side() -> None:
    exchanger = HeatExchanger(
        n_species=2,
        ua=500.0,
        hot_inlet_composition=np.array([0.8, 0.2], dtype=np.float64),
        cold_inlet_composition=np.array([0.2, 0.8], dtype=np.float64),
    )

    spec = exchanger.hydraulic_participation
    assert spec is not None

    assert len(spec.balancing_groups) == 2

    group_ports = {frozenset(g.ports) for g in spec.balancing_groups}
    assert frozenset({"hot_inlet", "hot_outlet"}) in group_ports
    assert frozenset({"cold_inlet", "cold_outlet"}) in group_ports

    # No cross-side group
    for group in spec.balancing_groups:
        ports = set(group.ports)
        assert not (
            ports & {"hot_inlet", "hot_outlet"} and ports & {"cold_inlet", "cold_outlet"}
        ), f"Balancing group '{group.name}' crosses hot/cold sides: {group.ports}"


def test_hydraulic_participation_has_two_pressure_equal_relations_no_cross_side() -> None:
    exchanger = HeatExchanger(
        n_species=2,
        ua=500.0,
        hot_inlet_composition=np.array([0.8, 0.2], dtype=np.float64),
        cold_inlet_composition=np.array([0.2, 0.8], dtype=np.float64),
    )

    spec = exchanger.hydraulic_participation
    assert spec is not None

    assert len(spec.relations) == 2

    for relation in spec.relations:
        assert relation.kind == "pressure_equal"

    relation_ports = {frozenset(r.ports) for r in spec.relations}
    assert frozenset({"hot_inlet", "hot_outlet"}) in relation_ports
    assert frozenset({"cold_inlet", "cold_outlet"}) in relation_ports

    # No cross-side relation
    for relation in spec.relations:
        ports = set(relation.ports)
        assert not (
            ports & {"hot_inlet", "hot_outlet"} and ports & {"cold_inlet", "cold_outlet"}
        ), f"Relation '{relation.name}' crosses hot/cold sides: {relation.ports}"


def test_hydraulic_participation_has_no_element_couplings() -> None:
    exchanger = HeatExchanger(
        n_species=2,
        ua=500.0,
        hot_inlet_composition=np.array([0.8, 0.2], dtype=np.float64),
        cold_inlet_composition=np.array([0.2, 0.8], dtype=np.float64),
    )

    spec = exchanger.hydraulic_participation
    assert spec is not None

    assert len(spec.element_couplings) == 0


def test_lmtd_and_ua_lmtd_are_diagnostic_outputs() -> None:
    package = _ConstantCpPackage(cp_hot=105.0, cp_cold=95.0)
    exchanger = HeatExchanger(
        flow_arrangement="counter",
        n_species=2,
        ua=1800.0,
        hot_inlet_flow=2.0,
        hot_inlet_temperature=395.0,
        hot_inlet_pressure=101325.0,
        hot_inlet_composition=np.array([0.7, 0.3], dtype=np.float64),
        cold_inlet_flow=2.5,
        cold_inlet_temperature=305.0,
        cold_inlet_pressure=101325.0,
        cold_inlet_composition=np.array([0.3, 0.7], dtype=np.float64),
    )
    exchanger.set_property_package(cast(Any, package))
    _attach(exchanger)

    exchanger.ua_lmtd = 999999.0
    exchanger.step(0.1)
    first_duty = exchanger.heat_duty

    exchanger.ua_lmtd = 1.0
    exchanger.step(0.1)

    assert exchanger.heat_duty == pytest.approx(first_duty)
    if exchanger.lmtd > 1.0e-12:
        assert exchanger.ua_lmtd == pytest.approx(exchanger.heat_duty / exchanger.lmtd)

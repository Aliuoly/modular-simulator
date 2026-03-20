from __future__ import annotations

# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false

import math
from types import SimpleNamespace
from typing import Any, cast

import numpy as np
import pytest
from numpy.typing import NDArray

from modular_simulation.thermodynamics.hydraulic_participation import (
    HydraulicBalancingGroupSpec,
    HydraulicIndexedStateRef,
    HydraulicParticipationSpec,
    HydraulicPortSpec,
    HydraulicRelationSpec,
    HydraulicScalarStateRef,
)
from modular_simulation.thermodynamics.property_package import FlashResult
from modular_simulation.unit_processes.mixing.mixer import Mixer
from modular_simulation.unit_processes.separation.splitter import Splitter


def _attach(model: Mixer | Splitter) -> None:
    model.attach_system(cast(Any, SimpleNamespace(solver_options={})))


class _QuadraticEnthalpyPackage:
    def flash_tp(self, T: float, P: float, z: tuple[float, ...]) -> FlashResult:
        return FlashResult(
            temperature=T,
            pressure=P,
            vapor_fraction=0.0,
            phase="liquid",
            liquid_composition=z,
            vapor_composition=None,
            enthalpy_molar=T * T,
            entropy_molar=T,
            liquid_density=1000.0,
            vapor_density=None,
            K_values=None,
        )

    def flash_ph(self, P: float, H: float, z: tuple[float, ...]) -> FlashResult:
        temperature = math.sqrt(H)
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


def test_mixer_mass_balance_and_composition_conservation() -> None:
    mixer = Mixer(
        n_inlets=2,
        n_species=2,
        inlet_flows=np.array([1.5, 2.5], dtype=np.float64),
        inlet_temperatures=np.array([310.0, 350.0], dtype=np.float64),
        inlet_pressures=np.array([200000.0, 150000.0], dtype=np.float64),
        inlet_compositions=np.array([1.0, 0.0, 0.4, 0.6], dtype=np.float64),
    )
    _attach(mixer)

    mixer.step(0.1)

    expected_outlet_flow = 4.0
    expected_outlet_composition = np.array(
        [
            (1.5 * 1.0 + 2.5 * 0.4) / expected_outlet_flow,
            (1.5 * 0.0 + 2.5 * 0.6) / expected_outlet_flow,
        ],
        dtype=np.float64,
    )

    assert mixer.outlet_flow == pytest.approx(expected_outlet_flow)
    assert mixer.outlet_flow == pytest.approx(float(np.sum(mixer.inlet_flows)))
    assert mixer.outlet_temperature == pytest.approx(
        (1.5 * 310.0 + 2.5 * 350.0) / expected_outlet_flow
    )
    assert mixer.outlet_pressure == pytest.approx(150000.0)
    assert np.asarray(mixer.outlet_composition, dtype=np.float64) == pytest.approx(
        expected_outlet_composition
    )
    assert mixer.ports.inlets == ("inlet_1", "inlet_2")
    assert mixer.ports.outlets == ("outlet",)


def test_mixer_uses_property_package_for_enthalpy_correct_temperature() -> None:
    mixer = Mixer(
        n_inlets=2,
        n_species=2,
        inlet_flows=np.array([1.0, 1.0], dtype=np.float64),
        inlet_temperatures=np.array([300.0, 500.0], dtype=np.float64),
        inlet_pressures=np.array([101325.0, 101325.0], dtype=np.float64),
        inlet_compositions=np.array([0.5, 0.5, 0.5, 0.5], dtype=np.float64),
    )
    mixer.set_property_package(cast(Any, _QuadraticEnthalpyPackage()))
    _attach(mixer)

    mixer.step(0.1)

    expected_enthalpy_temperature = math.sqrt((300.0 * 300.0 + 500.0 * 500.0) / 2.0)
    linear_temperature = 400.0
    assert mixer.outlet_temperature == pytest.approx(expected_enthalpy_temperature)
    assert mixer.outlet_temperature != pytest.approx(linear_temperature)


def test_mixer_declares_explicit_hydraulic_participation_with_zero_based_indexed_inlets() -> None:
    mixer = Mixer(n_inlets=3, n_species=2)

    assert mixer.hydraulic_participation == HydraulicParticipationSpec(
        ports={
            "inlet_1": HydraulicPortSpec(
                role="pressure_state",
                pressure_state=HydraulicIndexedStateRef(state="inlet_pressures", index=0),
            ),
            "inlet_2": HydraulicPortSpec(
                role="pressure_state",
                pressure_state=HydraulicIndexedStateRef(state="inlet_pressures", index=1),
            ),
            "inlet_3": HydraulicPortSpec(
                role="pressure_state",
                pressure_state=HydraulicIndexedStateRef(state="inlet_pressures", index=2),
            ),
            "outlet": HydraulicPortSpec(
                role="pressure_state",
                pressure_state=HydraulicScalarStateRef(state="outlet_pressure"),
            ),
        },
        balancing_groups=(
            HydraulicBalancingGroupSpec(
                name="mixing_flow_balance",
                ports=("inlet_1", "inlet_2", "inlet_3", "outlet"),
            ),
        ),
        relations=(
            HydraulicRelationSpec(
                name="mixing_equal_pressure",
                kind="pressure_equal",
                ports=("inlet_1", "inlet_2", "inlet_3", "outlet"),
            ),
        ),
    )


def test_splitter_copies_state_without_internal_branch_allocation() -> None:
    splitter = Splitter(
        n_outlets=2,
        n_species=2,
        inlet_flow=10.0,
        inlet_temperature=325.0,
        inlet_pressure=175000.0,
        inlet_composition=np.array([0.2, 0.8], dtype=np.float64),
        split_ratios=np.array([0.6], dtype=np.float64),
    )
    _attach(splitter)

    splitter.step(0.1)

    assert np.asarray(splitter.outlet_flows, dtype=np.float64) == pytest.approx(
        np.array([0.0, 0.0])
    )
    assert np.asarray(splitter.outlet_temperatures, dtype=np.float64) == pytest.approx(
        np.array([325.0, 325.0])
    )
    assert np.asarray(splitter.outlet_pressures, dtype=np.float64) == pytest.approx(
        np.array([175000.0, 175000.0])
    )
    assert np.asarray(splitter.outlet_compositions, dtype=np.float64) == pytest.approx(
        np.array([0.2, 0.8, 0.2, 0.8], dtype=np.float64)
    )
    assert "split_ratios" not in splitter.boundary_view.state_list
    assert "inlet_flow" in splitter.boundary_view.state_list
    assert splitter.ports.inlets == ("inlet",)
    assert splitter.ports.outlets == ("outlet_1", "outlet_2")


def test_splitter_declares_explicit_hydraulic_participation_with_zero_based_indexed_outlets() -> (
    None
):
    splitter = Splitter(n_outlets=3, n_species=2)

    assert splitter.hydraulic_participation == HydraulicParticipationSpec(
        ports={
            "inlet": HydraulicPortSpec(
                role="pressure_state",
                pressure_state=HydraulicScalarStateRef(state="inlet_pressure"),
            ),
            "outlet_1": HydraulicPortSpec(
                role="pressure_state",
                pressure_state=HydraulicIndexedStateRef(state="outlet_pressures", index=0),
            ),
            "outlet_2": HydraulicPortSpec(
                role="pressure_state",
                pressure_state=HydraulicIndexedStateRef(state="outlet_pressures", index=1),
            ),
            "outlet_3": HydraulicPortSpec(
                role="pressure_state",
                pressure_state=HydraulicIndexedStateRef(state="outlet_pressures", index=2),
            ),
        },
        balancing_groups=(
            HydraulicBalancingGroupSpec(
                name="split_flow_balance",
                ports=("inlet", "outlet_1", "outlet_2", "outlet_3"),
            ),
        ),
        relations=(
            HydraulicRelationSpec(
                name="split_equal_pressure",
                kind="pressure_equal",
                ports=("inlet", "outlet_1", "outlet_2", "outlet_3"),
            ),
        ),
    )


@pytest.mark.parametrize(
    ("n_outlets", "ratios", "error_match"),
    [
        (2, np.array([-0.1], dtype=np.float64), "split_ratios must contain non-negative values"),
        (3, np.array([0.8, 0.4], dtype=np.float64), "split_ratios sum must be <= 1.0"),
    ],
)
def test_splitter_invalid_split_ratios_raise(
    n_outlets: int,
    ratios: NDArray[np.float64],
    error_match: str,
) -> None:
    with pytest.raises(ValueError, match=error_match):
        _ = Splitter(
            n_outlets=n_outlets,
            n_species=2,
            inlet_flow=8.0,
            inlet_temperature=320.0,
            inlet_pressure=101325.0,
            inlet_composition=np.array([0.6, 0.4], dtype=np.float64),
            split_ratios=ratios,
        )

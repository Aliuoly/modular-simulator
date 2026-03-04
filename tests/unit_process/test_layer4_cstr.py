from __future__ import annotations

# pyright: reportMissingTypeStubs=false, reportAny=false, reportExplicitAny=false, reportUnknownMemberType=false

from types import SimpleNamespace
from typing import Any, cast

import numpy as np
import pytest

from modular_simulation.thermodynamics.kinetics import PowerLawRateLaw, Reaction, ReactionSet
from modular_simulation.unit_processes import CSTR


def _attach(model: CSTR) -> None:
    model.attach_system(cast(Any, SimpleNamespace(solver_options={})))


def _run_to_steady_state(model: CSTR, *, dt: float = 0.25, steps: int = 320) -> None:
    for _ in range(steps):
        model.step(dt)


def _first_order_reaction_set(k_value: float) -> ReactionSet:
    return ReactionSet(
        reactions=(
            Reaction(
                name="A_to_B",
                stoichiometry={"A": -1.0, "B": 1.0},
                rate_law=PowerLawRateLaw(
                    k_ref=k_value,
                    orders={"A": 1.0},
                    key_species="r1",
                ),
            ),
        )
    )


def test_first_order_steady_state() -> None:
    k_value = 0.8
    reactor_volume = 10.0
    inlet_flow = 2.0
    tau = reactor_volume / inlet_flow
    expected_ca = 1.0 / (1.0 + k_value * tau)

    reactor = CSTR(
        n_species=2,
        species_names=("A", "B"),
        reaction_set=_first_order_reaction_set(k_value),
        species_moles=np.array([reactor_volume, 0.0], dtype=np.float64),
        temperature=320.0,
        volume=reactor_volume,
        inlet_flow=inlet_flow,
        inlet_temperature=320.0,
        inlet_pressure=101325.0,
        inlet_composition=np.array([1.0, 0.0], dtype=np.float64),
        reactor_volume=reactor_volume,
        level_control_gain=3.0,
    )
    _attach(reactor)

    _run_to_steady_state(reactor)

    concentration_a = float(np.asarray(reactor.concentrations, dtype=np.float64)[0])
    assert concentration_a == pytest.approx(expected_ca, rel=0.03, abs=2.0e-3)


def test_kinetics_swap() -> None:
    reactor = CSTR(
        n_species=2,
        species_names=("A", "B"),
        reaction_set=_first_order_reaction_set(0.2),
        species_moles=np.array([10.0, 0.0], dtype=np.float64),
        temperature=315.0,
        volume=10.0,
        inlet_flow=2.0,
        inlet_temperature=315.0,
        inlet_pressure=101325.0,
        inlet_composition=np.array([1.0, 0.0], dtype=np.float64),
        reactor_volume=10.0,
        level_control_gain=2.0,
    )
    _attach(reactor)

    _run_to_steady_state(reactor)
    concentration_low_k = float(np.asarray(reactor.concentrations, dtype=np.float64)[0])

    reactor.set_reaction_set(_first_order_reaction_set(1.2), species_names=("A", "B"))
    reactor.species_moles = np.array([10.0, 0.0], dtype=np.float64)
    reactor.temperature = 315.0
    reactor.volume = 10.0
    reactor.t = 0.0

    _run_to_steady_state(reactor)
    concentration_high_k = float(np.asarray(reactor.concentrations, dtype=np.float64)[0])

    assert concentration_high_k < concentration_low_k


def test_energy_balance() -> None:
    base_kwargs = dict(
        n_species=2,
        species_names=("A", "B"),
        reaction_set=_first_order_reaction_set(0.7),
        species_moles=np.array([8.0, 0.0], dtype=np.float64),
        temperature=300.0,
        volume=8.0,
        inlet_flow=1.0,
        inlet_temperature=300.0,
        inlet_pressure=101325.0,
        inlet_composition=np.array([1.0, 0.0], dtype=np.float64),
        reactor_volume=8.0,
        level_control_gain=2.0,
        volumetric_heat_capacity=4200.0,
        reaction_heat_coeffs=np.array([60000.0, 0.0], dtype=np.float64),
    )

    adiabatic = CSTR(
        **base_kwargs,
        heat_transfer_coeff=0.0,
        jacket_area=0.0,
        jacket_temperature=290.0,
    )
    cooled = CSTR(
        **base_kwargs,
        heat_transfer_coeff=250.0,
        jacket_area=3.0,
        jacket_temperature=290.0,
    )
    _attach(adiabatic)
    _attach(cooled)

    _run_to_steady_state(adiabatic)
    _run_to_steady_state(cooled)

    assert adiabatic.temperature > 300.0
    assert cooled.temperature < adiabatic.temperature
    assert cooled.temperature > 290.0

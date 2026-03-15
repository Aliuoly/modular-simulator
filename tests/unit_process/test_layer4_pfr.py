from __future__ import annotations

# pyright: reportMissingTypeStubs=false, reportMissingImports=false, reportUnknownMemberType=false

from math import exp
from types import SimpleNamespace
from typing import Any, cast

import numpy as np
import pytest
from numpy.typing import NDArray
from pydantic import ValidationError

from modular_simulation.thermodynamics import PowerLawRateLaw, Reaction, ReactionSet
from modular_simulation.unit_processes import CSTR, PFR


def _attach(model: PFR | CSTR) -> None:
    model.attach_system(cast(Any, SimpleNamespace(solver_options={})))


def _run_to_steady_state(model: PFR | CSTR, *, dt: float = 0.2, steps: int = 500) -> None:
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
                ),
            ),
        )
    )


def _initial_cell_moles(*, n_cells: int, reactor_volume: float) -> NDArray[np.float64]:
    cell_volume = reactor_volume / float(n_cells)
    cell_moles = np.zeros((n_cells, 2), dtype=np.float64)
    cell_moles[:, 0] = cell_volume
    return cell_moles.reshape(-1)


def _run_pfr_outlet_a(
    *, n_cells: int, k_value: float, reactor_volume: float, inlet_flow: float
) -> float:
    reactor = PFR(
        n_species=2,
        n_cells=n_cells,
        species_names=("A", "B"),
        reaction_set=_first_order_reaction_set(k_value),
        cell_species_moles=_initial_cell_moles(n_cells=n_cells, reactor_volume=reactor_volume),
        cell_temperatures=np.full(n_cells, 320.0, dtype=np.float64),
        inlet_flow=inlet_flow,
        inlet_temperature=320.0,
        inlet_pressure=101325.0,
        inlet_composition=np.array([1.0, 0.0], dtype=np.float64),
        total_volume=reactor_volume,
        pressure=101325.0,
        volumetric_heat_capacity=4200.0,
    )
    _attach(reactor)
    _run_to_steady_state(reactor)
    return float(np.asarray(reactor.outlet_composition, dtype=np.float64)[0])


def _run_pfr_outlet_temperature_with_utility(
    *, utility_flow: float, utility_inlet_temperature: float = 360.0
) -> float:
    n_cells = 60
    reactor = PFR(
        n_species=2,
        n_cells=n_cells,
        species_names=("A", "B"),
        reaction_set=ReactionSet(reactions=()),
        cell_species_moles=_initial_cell_moles(n_cells=n_cells, reactor_volume=6.0),
        cell_temperatures=np.full(n_cells, 300.0, dtype=np.float64),
        inlet_flow=2.0,
        inlet_temperature=300.0,
        inlet_pressure=101325.0,
        inlet_composition=np.array([1.0, 0.0], dtype=np.float64),
        utility_inlet_temperature=utility_inlet_temperature,
        utility_flow=utility_flow,
        total_volume=6.0,
        pressure=101325.0,
        volumetric_heat_capacity=4200.0,
        heat_transfer_coeff=400.0,
        jacket_area=8.0,
        utility_volumetric_heat_capacity=4200.0,
    )
    _attach(reactor)
    _run_to_steady_state(reactor, dt=0.15, steps=500)
    return float(reactor.outlet_temperature)


def test_first_order_matches_analytical() -> None:
    k_value = 0.8
    reactor_volume = 10.0
    inlet_flow = 2.0
    tau = reactor_volume / inlet_flow
    analytical_ca = exp(-k_value * tau)

    outlet_low_cells = _run_pfr_outlet_a(
        n_cells=8,
        k_value=k_value,
        reactor_volume=reactor_volume,
        inlet_flow=inlet_flow,
    )
    outlet_high_cells = _run_pfr_outlet_a(
        n_cells=120,
        k_value=k_value,
        reactor_volume=reactor_volume,
        inlet_flow=inlet_flow,
    )

    low_error = abs(outlet_low_cells - analytical_ca)
    high_error = abs(outlet_high_cells - analytical_ca)

    assert high_error < low_error
    assert outlet_high_cells == pytest.approx(analytical_ca, rel=0.05, abs=2.0e-3)


def test_pfr_higher_conversion_than_cstr() -> None:
    k_value = 0.6
    reactor_volume = 10.0
    inlet_flow = 2.0

    pfr_outlet_a = _run_pfr_outlet_a(
        n_cells=80,
        k_value=k_value,
        reactor_volume=reactor_volume,
        inlet_flow=inlet_flow,
    )

    cstr = CSTR(
        n_species=2,
        species_names=("A", "B"),
        reaction_set=_first_order_reaction_set(k_value),
        species_moles=np.array([reactor_volume, 0.0], dtype=np.float64),
        temperature=320.0,
        volume=reactor_volume,
        inlet_flow=inlet_flow,
        outlet_flow=inlet_flow,
        inlet_temperature=320.0,
        inlet_pressure=101325.0,
        inlet_composition=np.array([1.0, 0.0], dtype=np.float64),
    )
    _attach(cstr)
    _run_to_steady_state(cstr)
    cstr_outlet_a = float(np.asarray(cstr.outlet_composition, dtype=np.float64)[0])

    assert pfr_outlet_a < cstr_outlet_a


def test_pfr_distributed_external_coupling_is_flow_sensitive() -> None:
    no_utility_flow_temperature = _run_pfr_outlet_temperature_with_utility(utility_flow=0.0)
    low_utility_flow_temperature = _run_pfr_outlet_temperature_with_utility(utility_flow=0.2)
    high_utility_flow_temperature = _run_pfr_outlet_temperature_with_utility(utility_flow=8.0)

    assert no_utility_flow_temperature == pytest.approx(300.0, abs=2.0e-2)
    assert low_utility_flow_temperature > no_utility_flow_temperature + 1.0
    assert high_utility_flow_temperature > low_utility_flow_temperature + 8.0


def test_pfr_rejects_legacy_imposed_jacket_temperature_field() -> None:
    assert "imposed_jacket_temperature" not in PFR.model_fields

    with pytest.raises(ValidationError):
        PFR(imposed_jacket_temperature=330.0)

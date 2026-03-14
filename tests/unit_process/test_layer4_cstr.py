from __future__ import annotations

# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false

from types import SimpleNamespace
from typing import Any, cast

import numpy as np
import pytest

from modular_simulation.components import (
    ControlElement,
    ControllerMode,
    PIDController,
    SampledDelayedSensor,
    Trajectory,
)
from modular_simulation.framework.system import System
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
        outlet_flow=inlet_flow,
        inlet_temperature=320.0,
        inlet_pressure=101325.0,
        inlet_composition=np.array([1.0, 0.0], dtype=np.float64),
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
        outlet_flow=2.0,
        inlet_temperature=315.0,
        inlet_pressure=101325.0,
        inlet_composition=np.array([1.0, 0.0], dtype=np.float64),
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
        outlet_flow=1.0,
        inlet_temperature=300.0,
        inlet_pressure=101325.0,
        inlet_composition=np.array([1.0, 0.0], dtype=np.float64),
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


def test_external_controller_drives_cstr_volume_via_outlet_flow_actuator() -> None:
    reactor = CSTR(
        n_species=2,
        species_names=("A", "B"),
        reaction_set=ReactionSet(reactions=()),
        species_moles=np.array([6.0, 0.0], dtype=np.float64),
        temperature=300.0,
        volume=6.0,
        inlet_flow=1.2,
        outlet_flow=1.2,
        inlet_temperature=300.0,
        inlet_pressure=101325.0,
        inlet_composition=np.array([1.0, 0.0], dtype=np.float64),
    )
    sensor = SampledDelayedSensor(
        measurement_tag="volume",
        alias_tag="reactor_volume",
        unit="L",
        sampling_period=0.0,
        deadtime=0.0,
    )
    controller = PIDController(
        cv_tag="reactor_volume",
        cv_range=(1.0, 20.0),
        reference_trajectory=Trajectory(y0=8.0),
        Kp=0.4,
        Ti=6.0,
        inverted=True,
        period=0.0,
    )
    outlet_flow_element = ControlElement(
        mv_tag="outlet_flow",
        mv_range=(0.0, 3.0),
        mv_trajectory=Trajectory(y0=1.2),
        controller=controller,
        mode=ControllerMode.AUTO,
    )
    system = System(
        dt=0.1,
        process_model=reactor,
        sensors=[sensor],
        calculations=[],
        control_elements=[outlet_flow_element],
        show_progress=False,
    )

    reactor.inlet_flow = 1.5
    for _ in range(320):
        system.step(duration=0.1)

    assert reactor.outlet_flow != pytest.approx(1.2, abs=1.0e-9)
    assert reactor.volume == pytest.approx(8.0, rel=0.06, abs=0.2)


def test_cstr_well_mixed_jacket_boundary_is_driven_via_external_heat_actuator_plane() -> None:
    reactor = CSTR(
        n_species=2,
        species_names=("A", "B"),
        reaction_set=ReactionSet(reactions=()),
        species_moles=np.array([5.0, 0.0], dtype=np.float64),
        temperature=305.0,
        volume=5.0,
        inlet_flow=1.0,
        outlet_flow=1.0,
        inlet_temperature=305.0,
        inlet_pressure=101325.0,
        inlet_composition=np.array([1.0, 0.0], dtype=np.float64),
        jacket_temperature=290.0,
    )
    system = System(
        dt=0.1,
        process_model=reactor,
        sensors=[],
        calculations=[],
        control_elements=[
            ControlElement(
                mv_tag="actuator/heat/cstr_jacket_loop",
                mv_range=(-20000.0, 20000.0),
                mv_trajectory=Trajectory(y0=1200.0),
                mode=ControllerMode.MANUAL,
            )
        ],
        show_progress=False,
    )

    system.step(duration=0.1)
    pending_heat_commands = system.consume_pending_heat_actuator_rate_commands()

    assert reactor.jacket_temperature == pytest.approx(290.0)
    assert "actuator/heat/cstr_jacket_loop" in pending_heat_commands
    assert pending_heat_commands["actuator/heat/cstr_jacket_loop"] == pytest.approx(1200.0)

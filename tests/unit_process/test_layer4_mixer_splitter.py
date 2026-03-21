from __future__ import annotations

import numpy as np
import pytest

from modular_simulation.connection.domain.state import MaterialState
from modular_simulation.connection.domain.state import PortCondition
from modular_simulation.connection.topology.junction import JunctionMixingResult
from modular_simulation.connection.topology.junction import mix_junction_state


def _material_state(
    *, pressure: float, temperature: float, mole_fractions: tuple[float, float]
) -> MaterialState:
    return MaterialState(
        pressure=pressure,
        temperature=temperature,
        mole_fractions=mole_fractions,
        species_ids=("7732-18-5", "64-17-5"),
        phase="liquid",
    )


def test_junction_mixing_matches_flow_weighted_temperature_and_composition() -> None:
    incoming = {
        "edge_a": PortCondition(
            state=_material_state(
                pressure=120_000.0,
                temperature=310.0,
                mole_fractions=(1.0, 0.0),
            ),
            species_ids=("7732-18-5", "64-17-5"),
            through_molar_flow_rate=5.0,
        ),
        "edge_b": PortCondition(
            state=_material_state(
                pressure=130_000.0,
                temperature=330.0,
                mole_fractions=(0.0, 1.0),
            ),
            species_ids=("7732-18-5", "64-17-5"),
            through_molar_flow_rate=3.0,
        ),
    }
    previous = _material_state(pressure=125_000.0, temperature=315.0, mole_fractions=(0.5, 0.5))

    result = mix_junction_state(
        incoming_port_conditions=incoming,
        previous_state=previous,
        near_zero_incoming_flow_epsilon=1.0e-12,
    )

    assert result.used_fallback is False
    assert result.total_incoming_flow_rate == pytest.approx(8.0)
    assert result.state.temperature == pytest.approx((5.0 * 310.0 + 3.0 * 330.0) / 8.0)
    assert result.state.mole_fractions == pytest.approx((0.625, 0.375))
    assert result.state.pressure == pytest.approx((5.0 * 120_000.0 + 3.0 * 130_000.0) / 8.0)


def test_junction_near_zero_flow_uses_previous_state_fallback() -> None:
    previous = _material_state(
        pressure=125_000.0,
        temperature=315.0,
        mole_fractions=(0.55, 0.45),
    )

    result = mix_junction_state(
        incoming_port_conditions={
            "edge_a": PortCondition(
                state=_material_state(
                    pressure=120_000.0,
                    temperature=300.0,
                    mole_fractions=(0.9, 0.1),
                ),
                species_ids=("7732-18-5", "64-17-5"),
                through_molar_flow_rate=0.0,
            )
        },
        previous_state=previous,
        near_zero_incoming_flow_epsilon=1.0e-9,
    )

    assert result.used_fallback is True
    assert result.state == previous


def test_junction_result_container_round_trips_state_without_branch_allocation() -> None:
    result = JunctionMixingResult(
        state=_material_state(
            pressure=118_000.0,
            temperature=322.0,
            mole_fractions=(0.2, 0.8),
        ),
        total_incoming_flow_rate=4.0,
        used_fallback=False,
    )

    assert result.total_incoming_flow_rate == pytest.approx(4.0)
    assert np.asarray(result.state.mole_fractions, dtype=np.float64) == pytest.approx(
        np.array([0.2, 0.8], dtype=np.float64)
    )

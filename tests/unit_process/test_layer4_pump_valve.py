from __future__ import annotations

import pytest

from modular_simulation.connection.hydraulics.hydraulic_compile import (
    calculate_effective_valve_resistance,
)
from modular_simulation.connection.hydraulics.hydraulic_element import (
    PumpHydraulicElement,
    ValveHydraulicElement,
    smooth_signed_quadratic_flow_term,
)


def test_pressure_gain_element_residual_zero_at_balanced_head() -> None:
    element = PumpHydraulicElement(
        dp_curve=lambda flow_rate, gain: gain,
        d_dp_d_mdot=lambda flow_rate, gain: 0.0,
    )

    residual = element.residuals(
        inputs={"upstream_pressure": 100_000.0, "downstream_pressure": 180_000.0},
        unknowns={"flow_rate": 0.012},
        parameters={"pump_speed": 80_000.0},
    )["head_balance"]

    assert residual == pytest.approx(0.0, abs=1.0e-10)


def test_pressure_gain_element_jacobian_matches_linear_gain_model() -> None:
    element = PumpHydraulicElement(
        dp_curve=lambda flow_rate, gain: gain,
        d_dp_d_mdot=lambda flow_rate, gain: 0.0,
    )

    jacobian = element.jacobian(
        inputs={"upstream_pressure": 100_000.0, "downstream_pressure": 180_000.0},
        unknowns={"flow_rate": 0.05},
        parameters={"pump_speed": 80_000.0},
    )

    assert jacobian[("head_balance", "flow_rate")] == pytest.approx(0.0)


def test_throttle_element_residual_matches_expected_pressure_drop_equation() -> None:
    open_fraction = 0.5
    resistance = calculate_effective_valve_resistance(
        resistance_when_open=1.0 / (0.002 * 0.002),
        open_fraction=open_fraction,
        minimum_open_fraction=0.0,
        maximum_open_fraction=1.0,
        min_relative_open_fraction=1.0e-3,
    )
    flow_rate = 0.02
    delta = 1.0e-6
    flow_term = smooth_signed_quadratic_flow_term(m_dot=flow_rate, delta=delta)
    expected_drop = resistance * flow_term

    element = ValveHydraulicElement()
    residual = element.residuals(
        inputs={
            "upstream_pressure": 250_000.0,
            "downstream_pressure": 250_000.0 - expected_drop,
        },
        unknowns={"flow_rate": flow_rate},
        parameters={"valve_resistance": resistance, "delta": delta},
    )["head_balance"]

    assert residual == pytest.approx(0.0, abs=1.0e-10)

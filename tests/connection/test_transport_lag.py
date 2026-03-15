# pyright: reportMissingImports=false, reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnusedCallResult=false

from __future__ import annotations

from math import isfinite

import pytest

from modular_simulation.connection.transport import (
    LagTransportState,
    MVPLagTransportModel,
    TransportModel,
)


def test_owner_led_mvp_model_update_is_stable_for_single_step() -> None:
    current = LagTransportState(composition=(0.9, 0.1), temperature=300.0)
    advected = LagTransportState(composition=(0.2, 0.8), temperature=360.0)
    model = MVPLagTransportModel(
        lag_time_constant_s=1.0,
        near_zero_flow_epsilon=1.0e-12,
        flow_smoothing_flow_rate=1.0e-9,
    )

    owner_result = model.update(
        current_state=current,
        advected_state=advected,
        dt=0.2,
        through_molar_flow_rate=0.5,
        previous_through_molar_flow_rate=0.4,
    )

    assert 0.0 <= owner_result.update_fraction <= 1.0
    assert owner_result.flow_scale > 0.0
    assert not owner_result.held_for_near_zero_flow
    assert owner_result.state.temperature > current.temperature
    assert owner_result.state.temperature < advected.temperature
    assert sum(owner_result.state.composition) == pytest.approx(1.0, abs=1.0e-9)
    assert all(0.0 <= value <= 1.0 for value in owner_result.state.composition)


def test_transport_model_is_nominal_and_framework_owned() -> None:
    with pytest.raises(
        TypeError,
        match="TransportModel is framework-owned and may only be implemented",
    ):
        type(
            "TestTransportModel",
            (TransportModel,),
            {
                "__module__": __name__,
                "model": property(lambda self: "test"),
                "update": lambda self, **kwargs: kwargs["current_state"],
            },
        )


def test_owner_led_mvp_model_converges_stably_over_multiple_steps() -> None:
    current = LagTransportState(composition=(0.9, 0.1), temperature=300.0)
    advected = LagTransportState(composition=(0.2, 0.8), temperature=360.0)
    model = MVPLagTransportModel(lag_time_constant_s=1.0)

    previous_gap = abs(current.temperature - advected.temperature)
    for _ in range(20):
        result = model.update(
            current_state=current,
            advected_state=advected,
            dt=0.2,
            through_molar_flow_rate=0.5,
        )
        current = result.state

        assert 0.0 <= result.update_fraction <= 1.0
        assert result.flow_scale > 0.0
        assert not result.held_for_near_zero_flow

        gap = abs(current.temperature - advected.temperature)
        assert gap <= previous_gap + 1.0e-12
        previous_gap = gap

        assert sum(current.composition) == pytest.approx(1.0, abs=1.0e-9)
        assert all(0.0 <= value <= 1.0 for value in current.composition)

    assert current.temperature == pytest.approx(advected.temperature, abs=2.0)
    assert current.composition[0] == pytest.approx(advected.composition[0], abs=3.0e-2)
    assert current.composition[1] == pytest.approx(advected.composition[1], abs=3.0e-2)


def test_owner_led_mvp_model_sign_change_sequence_remains_bounded_and_continuous() -> None:
    state = LagTransportState(composition=(0.5, 0.5), temperature=320.0)
    forward_advected = LagTransportState(composition=(0.95, 0.05), temperature=400.0)
    reverse_advected = LagTransportState(composition=(0.05, 0.95), temperature=260.0)
    model = MVPLagTransportModel(lag_time_constant_s=0.8)

    previous_flow: float | None = None
    for step in range(24):
        flow = 1.0 if step % 2 == 0 else -1.0
        advected = forward_advected if flow > 0.0 else reverse_advected

        result = model.update(
            current_state=state,
            advected_state=advected,
            dt=0.05,
            through_molar_flow_rate=flow,
            previous_through_molar_flow_rate=previous_flow,
        )
        state = result.state
        previous_flow = flow

        if step > 0:
            assert result.flow_sign_changed
        assert not result.held_for_near_zero_flow
        assert 0.0 <= result.update_fraction <= 1.0

        assert all(isfinite(value) for value in state.composition)
        assert all(0.0 <= value <= 1.0 for value in state.composition)
        assert sum(state.composition) == pytest.approx(1.0, abs=1.0e-9)
        assert isfinite(state.temperature)
        assert 200.0 <= state.temperature <= 500.0

    near_zero_hold = model.update(
        current_state=state,
        advected_state=forward_advected,
        dt=0.05,
        through_molar_flow_rate=1.0e-14,
        previous_through_molar_flow_rate=previous_flow,
    )
    assert near_zero_hold.held_for_near_zero_flow
    assert near_zero_hold.update_fraction == pytest.approx(0.0)
    assert near_zero_hold.state == state


@pytest.mark.parametrize(
    ("dt",),
    [
        (0.0,),
        (-0.1,),
    ],
)
def test_invalid_dt_raises_value_error(dt: float) -> None:
    current = LagTransportState(composition=(0.5, 0.5), temperature=300.0)
    advected = LagTransportState(composition=(0.4, 0.6), temperature=310.0)
    model = MVPLagTransportModel(lag_time_constant_s=1.0)

    with pytest.raises(ValueError, match="dt must be positive"):
        model.update(
            current_state=current,
            advected_state=advected,
            dt=dt,
            through_molar_flow_rate=1.0,
        )


def test_owner_led_mvp_model_invalid_composition_vectors_raise_value_error() -> None:
    with pytest.raises(ValueError, match="must contain at least one component"):
        LagTransportState(composition=(), temperature=300.0)

    with pytest.raises(ValueError, match="must sum to 1.0"):
        LagTransportState(composition=(0.6, 0.6), temperature=300.0)

    current = LagTransportState(composition=(0.5, 0.5), temperature=300.0)
    advected = LagTransportState(composition=(1.0,), temperature=305.0)
    model = MVPLagTransportModel(lag_time_constant_s=1.0)
    with pytest.raises(ValueError, match="composition lengths must match"):
        model.update(
            current_state=current,
            advected_state=advected,
            dt=0.1,
            through_molar_flow_rate=1.0,
        )

from __future__ import annotations

from types import SimpleNamespace
from typing import Annotated, Any, cast

import numpy as np
import pytest
from numpy.typing import NDArray

from modular_simulation.utils.typing import ArrayIndex
from modular_simulation.measurables.process_model import StateMetadata as M
from modular_simulation.measurables.process_model import StateType as T
from modular_simulation.thermodynamics import (
    AlgebraicProcessModel,
    DUAL_INLET,
    DUAL_OUTLET,
    ENERGY_INLET,
    ENERGY_IO,
    SINGLE_IO,
)
from modular_simulation.validation.exceptions import MeasurableConfigurationError


class SignalPassThrough(AlgebraicProcessModel):
    inlet_signal: Annotated[float, M(type=T.BOUNDARY, unit="", description="input signal")] = 1.0
    gain: Annotated[float, M(type=T.CONSTANT, unit="", description="multiplicative gain")] = 2.0
    outlet_signal: Annotated[float, M(type=T.ALGEBRAIC, unit="", description="output signal")] = 0.0

    @staticmethod
    def calculate_algebraic_values(
        y: NDArray[np.float64],
        u: NDArray[np.float64],
        k: NDArray[np.float64],
        y_map: dict[str, ArrayIndex],
        u_map: dict[str, ArrayIndex],
        k_map: dict[str, ArrayIndex],
        algebraic_map: dict[str, ArrayIndex],
        algebraic_size: int,
    ) -> NDArray[np.float64]:
        assert y.size == 0
        assert y_map == {}
        result = np.zeros(algebraic_size, dtype=np.float64)
        result[algebraic_map["outlet_signal"]] = u[u_map["inlet_signal"]] * k[k_map["gain"]]
        return result


def test_algebraic_step_skips_ode_and_updates_only_algebraic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _forbidden_solve_ivp(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError("solve_ivp should not be called by AlgebraicProcessModel.step")

    import modular_simulation.measurables.process_model as process_model_module

    monkeypatch.setattr(process_model_module, "solve_ivp", _forbidden_solve_ivp)

    model = SignalPassThrough(inlet_signal=3.0, gain=4.0)
    model.attach_system(cast(Any, SimpleNamespace(solver_options={})))

    model.step(0.5)

    assert model.differential_view.array_size == 0
    assert model.outlet_signal == pytest.approx(12.0)
    assert model.t == pytest.approx(0.5)

    rhs = SignalPassThrough.differential_rhs(
        t=0.0,
        y=np.zeros(0, dtype=np.float64),
        u=np.zeros(1, dtype=np.float64),
        k=np.zeros(1, dtype=np.float64),
        algebraic=np.zeros(1, dtype=np.float64),
        y_map={},
        u_map={"inlet_signal": 0},
        k_map={"gain": 0},
        algebraic_map={"outlet_signal": 0},
    )
    assert rhs.size == 0


def test_algebraic_process_model_rejects_differential_states() -> None:
    class InvalidAlgebraicModel(AlgebraicProcessModel):
        illegal_state: Annotated[
            float, M(type=T.DIFFERENTIAL, unit="", description="forbidden")
        ] = 0.0

        @staticmethod
        def calculate_algebraic_values(
            y: NDArray[np.float64],
            u: NDArray[np.float64],
            k: NDArray[np.float64],
            y_map: dict[str, ArrayIndex],
            u_map: dict[str, ArrayIndex],
            k_map: dict[str, ArrayIndex],
            algebraic_map: dict[str, ArrayIndex],
            algebraic_size: int,
        ) -> NDArray[np.float64]:
            del y, u, k, y_map, u_map, k_map, algebraic_map, algebraic_size
            return np.zeros(0, dtype=np.float64)

    with pytest.raises(MeasurableConfigurationError, match="does not allow DIFFERENTIAL states"):
        _ = InvalidAlgebraicModel()


def test_unit_process_ports_constants() -> None:
    assert SINGLE_IO.inlets == ("inlet",)
    assert SINGLE_IO.outlets == ("outlet",)

    assert DUAL_INLET.inlets == ("inlet_1", "inlet_2")
    assert DUAL_INLET.outlets == ("outlet",)

    assert DUAL_OUTLET.inlets == ("inlet",)
    assert DUAL_OUTLET.outlets == ("outlet_1", "outlet_2")

    assert ENERGY_INLET.inlets == ("inlet", "energy_in")
    assert ENERGY_INLET.outlets == ("outlet",)

    assert ENERGY_IO.inlets == ("inlet", "energy_in")
    assert ENERGY_IO.outlets == ("outlet", "energy_out")

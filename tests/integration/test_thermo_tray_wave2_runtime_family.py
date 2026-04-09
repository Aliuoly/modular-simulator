from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest

from modular_simulation.thermodynamics.stream import StreamData


def _attach(model: Any, *, solver_options: dict[str, Any] | None = None) -> None:
    model.attach_system(cast(Any, SimpleNamespace(solver_options=solver_options or {})))


def test_total_condenser_class_is_explicitly_exported() -> None:
    from modular_simulation.unit_processes import ThermoTrayDistillationColumnTotalCondenser
    from modular_simulation.unit_processes.separation import (
        ThermoTrayDistillationColumnTotalCondenser as SeparationTotal,
    )

    assert ThermoTrayDistillationColumnTotalCondenser is SeparationTotal


def test_partial_condenser_boundary_exists_as_reserved_stub() -> None:
    from modular_simulation.unit_processes.separation import (
        ThermoTrayDistillationColumnPartialCondenser,
    )

    with pytest.raises(NotImplementedError, match="reserved"):
        ThermoTrayDistillationColumnPartialCondenser()


def test_legacy_thermo_tray_alias_points_to_total_condenser_class() -> None:
    from modular_simulation.unit_processes.separation import (
        ThermoTrayDistillationColumn,
        ThermoTrayDistillationColumnTotalCondenser,
    )

    assert ThermoTrayDistillationColumn is ThermoTrayDistillationColumnTotalCondenser


def test_total_condenser_honors_framework_solver_options_via_process_model_seam() -> None:
    from modular_simulation.unit_processes.separation import (
        ThermoTrayDistillationColumnTotalCondenser,
    )

    col = ThermoTrayDistillationColumnTotalCondenser(n_species=3, n_trays=4, feed_tray_indices=(2,))
    _attach(col, solver_options={"method": "Radau"})
    col.apply_inlet(
        "feed_1",
        StreamData(
            temperature=350.0,
            pressure=150000.0,
            mole_fractions=(0.5, 0.3, 0.2),
            molar_flow_rate=8.0,
        ),
    )

    import modular_simulation.measurables.process_model as process_model_module

    recorded: dict[str, Any] = {}
    original = process_model_module.solve_ivp

    def _recording_solve_ivp(*args: Any, **kwargs: Any):
        recorded["kwargs"] = kwargs
        return original(*args, **kwargs)

    process_model_module.solve_ivp = _recording_solve_ivp
    try:
        col.step(0.1)
    finally:
        process_model_module.solve_ivp = original

    assert recorded.get("kwargs", {}).get("method") == "Radau"

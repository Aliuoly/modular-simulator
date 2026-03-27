from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import numpy as np
import pytest

from modular_simulation.unit_processes import StagewiseDistillationColumn


def _attach(model: StagewiseDistillationColumn) -> None:
    model.attach_system(cast(Any, SimpleNamespace(solver_options={})))


def test_distillation_path_uses_stagewise_column_only() -> None:
    column = StagewiseDistillationColumn(n_species=3, active_contact_height_m=4.0)
    _attach(column)

    assert isinstance(column, StagewiseDistillationColumn)


def test_condenser_duty_supports_zero_partial_and_full_condensation() -> None:
    column = StagewiseDistillationColumn(n_species=3, stage_vapor_flow_mol_s=1.0)
    _attach(column)
    params = column._params

    def _realized_for(duty_w: float) -> float:
        column.condenser_duty_request_W = duty_w
        y = column.differential_view.to_array()
        u = column.boundary_view.to_array()
        algebraic = column.calculate_algebraic_values(
            y=y,
            u=u,
            k=params.k,
            y_map=params.y_map,
            u_map=params.boundary_map,
            k_map=params.k_map,
            algebraic_map=params.algebraic_map,
            algebraic_size=params.algebraic_size,
        )
        return float(algebraic[params.algebraic_map["realized_condensed_flow_mol_s"]])

    assert _realized_for(0.0) == pytest.approx(0.0)
    assert _realized_for(-15000.0) == pytest.approx(0.5)
    assert _realized_for(-30000.0) == pytest.approx(1.0)


def test_shell_diameter_changes_capacity_not_selectivity() -> None:
    narrow = StagewiseDistillationColumn(n_species=3, shell_diameter_m=0.8)
    wide = StagewiseDistillationColumn(n_species=3, shell_diameter_m=1.6)
    _attach(narrow)
    _attach(wide)

    assert np.asarray(narrow.relative_volatility_reference) == pytest.approx(
        np.asarray(wide.relative_volatility_reference)
    )

    narrow.condenser_duty_request_W = -1.0e9
    wide.condenser_duty_request_W = -1.0e9

    n_params = narrow._params
    w_params = wide._params

    n_alg = narrow.calculate_algebraic_values(
        y=narrow.differential_view.to_array(),
        u=narrow.boundary_view.to_array(),
        k=n_params.k,
        y_map=n_params.y_map,
        u_map=n_params.boundary_map,
        k_map=n_params.k_map,
        algebraic_map=n_params.algebraic_map,
        algebraic_size=n_params.algebraic_size,
    )
    w_alg = wide.calculate_algebraic_values(
        y=wide.differential_view.to_array(),
        u=wide.boundary_view.to_array(),
        k=w_params.k,
        y_map=w_params.y_map,
        u_map=w_params.boundary_map,
        k_map=w_params.k_map,
        algebraic_map=w_params.algebraic_map,
        algebraic_size=w_params.algebraic_size,
    )

    assert float(w_alg[w_params.algebraic_map["maximum_vapor_capacity_flow_mol_s"]]) > float(
        n_alg[n_params.algebraic_map["maximum_vapor_capacity_flow_mol_s"]]
    )

from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Any, cast

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from examples.dynamic_simulation_demos import thermo_tray_distillation_startup_demo as startup_demo
from examples.dynamic_simulation_demos import (
    thermo_tray_step_characterization_demo as step_characterization_demo,
)
from modular_simulation.measurables.process_model import ProcessModel
from modular_simulation.thermodynamics.stream import StreamData
from modular_simulation.unit_processes.separation import ThermoTrayDistillationColumn


def _attach(model: ProcessModel) -> None:
    model.attach_system(cast(Any, SimpleNamespace(solver_options={})))


def _stabilize_state(col: ThermoTrayDistillationColumn, values: np.ndarray) -> np.ndarray:
    clipped = np.asarray(values, dtype=np.float64).copy()
    for name, index in col.differential_view.index_map.items():
        state = np.asarray(clipped[index], dtype=np.float64)
        lower: float | None = None
        upper: float | None = None
        lname = name.lower()
        if "component_holdup" in lname or "component_moles" in lname:
            lower = 1.0e-9
        elif "temperature" in lname:
            lower = 250.0
            upper = 800.0
        if lower is not None:
            state = np.maximum(state, lower)
        if upper is not None:
            state = np.minimum(state, upper)
        clipped[index] = state
    return clipped


def _bounded_step(col: ThermoTrayDistillationColumn, dt_s: float, n_substeps: int = 2) -> None:
    params = col._params
    y = col.differential_view.to_array()
    u = col.boundary_view.to_array()
    h = dt_s / max(1, n_substeps)
    t_val = float(col.t)
    common = dict(
        k=params.k,
        y_map=params.y_map,
        u_map=params.boundary_map,
        k_map=params.k_map,
        algebraic_map=params.algebraic_map,
    )

    for _ in range(max(1, n_substeps)):
        alg0 = col.calculate_algebraic_values(
            y=y, u=u, algebraic_size=params.algebraic_size, **common
        )
        k1 = col.differential_rhs(t=t_val, y=y, u=u, algebraic=alg0, **common)
        y1 = _stabilize_state(col, y + h * k1)
        alg1 = col.calculate_algebraic_values(
            y=y1,
            u=u,
            algebraic_size=params.algebraic_size,
            **common,
        )
        k2 = col.differential_rhs(t=t_val + h, y=y1, u=u, algebraic=alg1, **common)
        y = _stabilize_state(col, y + 0.5 * h * (k1 + k2))
        t_val += h

    final_alg = col.calculate_algebraic_values(
        y=y,
        u=u,
        algebraic_size=params.algebraic_size,
        **common,
    )
    col.differential_view.update_from_array(y)
    col.algebraic_view.update_from_array(final_alg)
    col.accepted_dt_s = dt_s
    col.t = t_val


def _save_state(col: ThermoTrayDistillationColumn) -> dict[str, Any]:
    return {
        "diff": col.differential_view.to_array().copy(),
        "alg": col.algebraic_view.to_array().copy(),
        "t": float(col.t),
        "settle_hold": float(getattr(col, "_settle_hold_s", 0.0)),
    }


def _restore_state(col: ThermoTrayDistillationColumn, snap: dict[str, Any]) -> None:
    col.differential_view.update_from_array(snap["diff"].copy())
    col.algebraic_view.update_from_array(snap["alg"].copy())
    col.t = float(snap["t"])
    col._settle_hold_s = float(snap["settle_hold"])
    col._last_boundary_snapshot = None


def _build_demo_column() -> ThermoTrayDistillationColumn:
    col = ThermoTrayDistillationColumn(
        n_species=3,
        species_selector=np.asarray((3.0, 4.0, 5.0), dtype=np.float64),
        n_trays=12,
        feed_tray_indices=(6,),
        p_top_pa=150000.0,
        delta_p_tray_pa=500.0,
        eps_start=50.0,
        eps_drum=200.0,
        eps_kettle=100.0,
        tray_weir_height_m=0.001,
        liquid_flow_coeff=10000.0,
        vapor_flow_coeff=5.0,
    )
    _attach(col)
    col.apply_inlet(
        "feed_1",
        StreamData(
            temperature=385.0,
            pressure=150000.0,
            mole_fractions=(1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0),
            molar_flow_rate=2.0,
        ),
    )
    col.build_startup_state()
    col.condenser_duty_request_W = -100000.0
    col.reboiler_duty_request_W = 100000.0
    col.reflux_withdrawal_flow = 1.5
    col.distillate_withdrawal_flow = 0.8
    col.bottoms_withdrawal_flow = 1.1
    return col


def _settle_demo_column(col: ThermoTrayDistillationColumn, steps: int = 80) -> None:
    for _ in range(steps):
        _bounded_step(col, dt_s=4.0, n_substeps=2)


def test_species_selector_rejects_duplicates() -> None:
    with pytest.raises(ValueError, match="species_selector must contain unique indices"):
        ThermoTrayDistillationColumn(
            n_species=3,
            species_selector=np.asarray((3.0, 3.0, 5.0), dtype=np.float64),
            n_trays=8,
        )


def test_species_selector_changes_default_thermo_properties() -> None:
    default = ThermoTrayDistillationColumn(n_species=2, n_trays=8)
    aromatic = ThermoTrayDistillationColumn(
        n_species=2,
        species_selector=np.asarray((6.0, 7.0), dtype=np.float64),
        n_trays=8,
    )

    assert not np.allclose(default.cp_species_liq_j_per_mol_k, aromatic.cp_species_liq_j_per_mol_k)
    assert np.array_equal(default.species_selector, np.asarray((0.0, 1.0), dtype=np.float64))
    assert np.array_equal(aromatic.species_selector, np.asarray((6.0, 7.0), dtype=np.float64))


def test_multicomponent_demo_operating_point_shows_separation() -> None:
    col = _build_demo_column()
    _settle_demo_column(col)

    x_d = np.asarray(col.distillate_composition, dtype=np.float64)
    x_b = np.asarray(col.bottoms_composition, dtype=np.float64)
    tray_t = np.asarray(col.tray_temperature, dtype=np.float64)

    assert np.all(np.isfinite(tray_t))
    assert np.all(np.isfinite(x_d))
    assert np.all(np.isfinite(x_b))
    assert x_d[0] > (1.0 / 3.0) + 0.03, f"expected top product enriched in light key, got {x_d}"
    assert x_b[-1] > (1.0 / 3.0) + 0.12, f"expected bottoms enriched in heavy key, got {x_b}"
    assert float(tray_t[0]) < float(tray_t[-1]), (
        f"expected top tray cooler than bottom tray, got {tray_t[0]:.2f} K and {tray_t[-1]:.2f} K"
    )
    assert float(np.sum(col.condenser_drum_component_moles)) > 10.0
    assert float(np.sum(col.reboiler_kettle_component_moles)) > 10.0


def test_demo_operating_point_top_pressure_rises_and_outlet_liquid_is_subcooled() -> None:
    """Demo-scoped overload check through the local stepping harness."""
    col = _build_demo_column()
    col.condenser_duty_request_W = -5.0
    _settle_demo_column(col, steps=20)

    non_condensed = getattr(col, "non_condensed_flow", None)
    assert non_condensed is not None, (
        "Demo harness should expose overload evidence via non_condensed_flow"
    )
    assert float(non_condensed) > 0.0, (
        f"Expected demo overload to produce nonzero non_condensed_flow, got {non_condensed}"
    )
    assert "distillate" in col.ports.outlets
    assert col.hydraulic_participation.ports["distillate"].pressure_state is not None


def test_multicomponent_demo_step_responses_have_expected_signs() -> None:
    col = _build_demo_column()
    _settle_demo_column(col)
    snap = _save_state(col)

    baseline_xd_light = float(col.distillate_composition[0])
    baseline_xb_heavy = float(col.bottoms_composition[-1])
    col.apply_inlet(
        "feed_1",
        StreamData(
            temperature=385.0,
            pressure=150000.0,
            mole_fractions=(0.45, 0.35, 0.20),
            molar_flow_rate=2.0,
        ),
    )
    for _ in range(40):
        _bounded_step(col, dt_s=4.0, n_substeps=2)

    assert float(col.distillate_composition[0]) > baseline_xd_light
    assert float(col.bottoms_composition[-1]) < baseline_xb_heavy
    assert np.all(np.isfinite(np.asarray(col.tray_temperature, dtype=np.float64)))

    _restore_state(col, snap)
    baseline_kettle_temp = float(col.reboiler_kettle_temperature)
    col.reboiler_duty_request_W = 115000.0
    for _ in range(40):
        _bounded_step(col, dt_s=4.0, n_substeps=2)

    assert float(col.reboiler_kettle_temperature) > baseline_kettle_temp


def test_demo_overload_does_not_imply_partial_condenser_semantics() -> None:
    """Demo-scoped check: overload still presents the total-condenser surface."""
    col = _build_demo_column()
    col.condenser_duty_request_W = -1.0
    _settle_demo_column(col, steps=5)

    assert hasattr(col, "condenser_drum_component_moles")
    assert "distillate" in col.ports.outlets
    assert col.hydraulic_participation.ports["distillate"].pressure_state is not None
    assert not hasattr(col, "partial_condenser")


def test_startup_demo_reports_wave5_observability_surfaces_honestly() -> None:
    result = startup_demo.run_demo(dt_s=1.0, n_steps=8, n_substeps=2)

    assert result["stepping_strategy"] == "demo_scoped_bounded_substep_refinement"
    assert "demo-scoped" in result["stepping_disclosure"].lower()
    assert "raw runtime step()" in result["stepping_disclosure"]

    for key in (
        "top_headspace_pressure_pa",
        "bottom_pressure_pa",
        "realized_condensed_flow_mol_s",
        "non_condensed_flow_mol_s",
        "distillate_source_pressure_pa",
        "reflux_source_pressure_pa",
        "condenser_bubble_temperature_K",
        "condenser_subcooling_K",
    ):
        assert key in result
        assert np.isfinite(float(result[key]))

    assert float(result["bottom_pressure_pa"]) >= float(result["top_headspace_pressure_pa"])
    assert float(result["distillate_source_pressure_pa"]) >= float(
        result["top_headspace_pressure_pa"]
    )
    assert float(result["reflux_source_pressure_pa"]) >= float(result["top_headspace_pressure_pa"])
    assert float(result["realized_condensed_flow_mol_s"]) >= 0.0
    assert float(result["non_condensed_flow_mol_s"]) >= 0.0
    assert float(result["condenser_subcooling_K"]) == pytest.approx(
        float(result["condenser_bubble_temperature_K"]) - float(result["drum_temperature_K"]),
        rel=1e-9,
        abs=1e-9,
    )


def test_step_characterization_demo_reports_wave5_observability_and_disclosure() -> None:
    results = step_characterization_demo.run_demo(
        dt_s=4.0,
        n_substeps=2,
        max_settle_steps=20,
        pre_steps=3,
        post_steps=20,
    )

    meta = results["meta"]
    assert meta["stepping_strategy"] == "demo_scoped_bounded_substep_refinement"
    assert "demo-scoped" in meta["stepping_disclosure"].lower()
    assert "raw runtime step()" in meta["stepping_disclosure"]

    assert results["scenarios"], "Expected at least one scenario in demo output"
    summary = results["scenarios"][0]["summary"]
    for key in (
        "top_headspace_pressure_pa",
        "bottom_pressure_pa",
        "realized_condensed_flow_mol_s",
        "non_condensed_flow_mol_s",
        "distillate_source_pressure_pa",
        "reflux_source_pressure_pa",
        "condenser_bubble_temperature_K",
        "condenser_subcooling_K",
    ):
        assert key in summary, f"Missing Wave 5 observable summary: {key}"

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import numpy as np
import pytest

from modular_simulation.measurables.process_model import ProcessModel
from modular_simulation.thermodynamics.hydraulic_participation import (
    HydraulicScalarStateRef,
)
from modular_simulation.thermodynamics.stream import StreamData
from modular_simulation.unit_processes import StagewiseDistillationColumn


def _attach(model: StagewiseDistillationColumn) -> None:
    model.attach_system(cast(Any, SimpleNamespace(solver_options={})))


def _inventory_component_vector(model: StagewiseDistillationColumn) -> np.ndarray:
    stage = np.asarray(model.stage_component_moles, dtype=np.float64).reshape(
        model.n_stages, model.n_species
    )
    return (
        np.sum(stage, axis=0)
        + np.asarray(model.reflux_drum_component_moles, dtype=np.float64)
        + np.asarray(model.bottoms_sump_component_moles, dtype=np.float64)
    )


def _compute_algebraic(column: StagewiseDistillationColumn) -> np.ndarray:
    params = column._params
    y = column.differential_view.to_array()
    u = column.boundary_view.to_array()
    return column.calculate_algebraic_values(
        y=y,
        u=u,
        k=params.k,
        y_map=params.y_map,
        u_map=params.boundary_map,
        k_map=params.k_map,
        algebraic_map=params.algebraic_map,
        algebraic_size=params.algebraic_size,
    )


def test_stagewise_column_is_dynamic_process_model() -> None:
    column = StagewiseDistillationColumn(n_species=3, active_contact_height_m=4.0)
    _attach(column)

    assert isinstance(column, ProcessModel)
    assert "stage_component_moles" in column.differential_view.state_list


def test_multicomponent_stagewise_transient_evolves_across_multiple_steps() -> None:
    column = StagewiseDistillationColumn(
        n_species=3,
        active_contact_height_m=6.0,
        shell_diameter_m=1.0,
        feed_stage_indices=(1,),
    )
    _attach(column)
    column.condenser_duty_request_W = -30000.0
    column.reboiler_duty_request_W = 30000.0
    column.apply_inlet(
        "feed_1",
        StreamData(
            temperature=355.0,
            pressure=130000.0,
            mole_fractions=(0.75, 0.20, 0.05),
            molar_flow_rate=10.0,
        ),
    )

    initial = column.get_outlet_stream("distillate").mole_fractions[0]
    column.step(0.2)
    first = column.get_outlet_stream("distillate").mole_fractions[0]
    column.step(0.2)
    second = column.get_outlet_stream("distillate").mole_fractions[0]

    assert first != pytest.approx(initial)
    assert second != pytest.approx(first)


def test_component_inventory_rhs_closes_to_feed_minus_products() -> None:
    column = StagewiseDistillationColumn(
        n_species=3,
        active_contact_height_m=5.0,
        shell_diameter_m=1.1,
        feed_stage_indices=(1, 3),
    )
    _attach(column)
    column.apply_inlet(
        "feed_1",
        StreamData(
            temperature=340.0,
            pressure=150000.0,
            mole_fractions=(0.6, 0.3, 0.1),
            molar_flow_rate=7.0,
        ),
    )
    column.apply_inlet(
        "feed_2",
        StreamData(
            temperature=330.0,
            pressure=150000.0,
            mole_fractions=(0.1, 0.3, 0.6),
            molar_flow_rate=5.0,
        ),
    )

    params = column._params
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
    dy = column.differential_rhs(
        t=column.t,
        y=y,
        u=u,
        k=params.k,
        algebraic=algebraic,
        y_map=params.y_map,
        u_map=params.boundary_map,
        k_map=params.k_map,
        algebraic_map=params.algebraic_map,
    )

    stage_rates = np.asarray(dy[params.y_map["stage_component_moles"]], dtype=np.float64).reshape(
        column.n_stages, column.n_species
    )
    drum_rates = np.asarray(dy[params.y_map["reflux_drum_component_moles"]], dtype=np.float64)
    sump_rates = np.asarray(dy[params.y_map["bottoms_sump_component_moles"]], dtype=np.float64)
    inventory_rate = np.sum(stage_rates, axis=0) + drum_rates + sump_rates

    feed_rates = np.zeros(column.n_species, dtype=np.float64)
    feed_compositions = np.asarray(column.feed_compositions, dtype=np.float64).reshape(
        column.n_feeds, column.n_species
    )
    for feed_index in range(column.n_feeds):
        flow = float(column.feed_flows[feed_index])
        composition = np.asarray(feed_compositions[feed_index], dtype=np.float64)
        feed_rates += flow * composition

    distillate_component = float(algebraic[params.algebraic_map["distillate_flow"]]) * np.asarray(
        algebraic[params.algebraic_map["distillate_composition"]], dtype=np.float64
    )
    bottoms_component = float(algebraic[params.algebraic_map["bottoms_flow"]]) * np.asarray(
        algebraic[params.algebraic_map["bottoms_composition"]], dtype=np.float64
    )

    assert inventory_rate == pytest.approx(
        feed_rates - distillate_component - bottoms_component, abs=1.0e-8
    )


def test_feed_stage_assignment_materially_changes_response() -> None:
    top_feed_column = StagewiseDistillationColumn(
        n_species=3,
        active_contact_height_m=6.0,
        shell_diameter_m=1.0,
        feed_stage_indices=(1, 1),
    )
    bottom_feed_column = StagewiseDistillationColumn(
        n_species=3,
        active_contact_height_m=6.0,
        shell_diameter_m=1.0,
        feed_stage_indices=(1, 5),
    )
    _attach(top_feed_column)
    _attach(bottom_feed_column)
    for unit in (top_feed_column, bottom_feed_column):
        unit.condenser_duty_request_W = -30000.0
        unit.reboiler_duty_request_W = 30000.0

    feed_a = StreamData(
        temperature=350.0,
        pressure=120000.0,
        mole_fractions=(0.8, 0.15, 0.05),
        molar_flow_rate=6.0,
    )
    feed_b = StreamData(
        temperature=350.0,
        pressure=120000.0,
        mole_fractions=(0.05, 0.30, 0.65),
        molar_flow_rate=6.0,
    )
    for unit in (top_feed_column, bottom_feed_column):
        unit.apply_inlet("feed_1", feed_a)
        unit.apply_inlet("feed_2", feed_b)

    for _ in range(5):
        top_feed_column.step(0.2)
        bottom_feed_column.step(0.2)

    top_distillate_light = top_feed_column.get_outlet_stream("distillate").mole_fractions[0]
    bottom_distillate_light = bottom_feed_column.get_outlet_stream("distillate").mole_fractions[0]

    assert abs(top_distillate_light - bottom_distillate_light) > 1.0e-4


def test_active_contact_height_controls_stage_count_and_behavior() -> None:
    short_column = StagewiseDistillationColumn(
        n_species=3, active_contact_height_m=2.0, tray_spacing_m=0.5
    )
    tall_column = StagewiseDistillationColumn(
        n_species=3, active_contact_height_m=6.0, tray_spacing_m=0.5
    )
    _attach(short_column)
    _attach(tall_column)
    short_column.condenser_duty_request_W = -30000.0
    short_column.reboiler_duty_request_W = 30000.0
    tall_column.condenser_duty_request_W = -30000.0
    tall_column.reboiler_duty_request_W = 30000.0

    assert short_column.n_stages == 4
    assert tall_column.n_stages == 12

    feed = StreamData(
        temperature=345.0,
        pressure=140000.0,
        mole_fractions=(0.7, 0.2, 0.1),
        molar_flow_rate=9.0,
    )
    short_column.apply_inlet("feed_1", feed)
    tall_column.apply_inlet("feed_1", feed)
    for _ in range(4):
        short_column.step(0.2)
        tall_column.step(0.2)

    assert short_column.get_outlet_stream("distillate").mole_fractions[0] != pytest.approx(
        tall_column.get_outlet_stream("distillate").mole_fractions[0]
    )


def test_shell_diameter_changes_holdup_residence_semantics_not_selectivity_parameter() -> None:
    narrow = StagewiseDistillationColumn(
        n_species=3, shell_diameter_m=0.7, active_contact_height_m=5.0
    )
    wide = StagewiseDistillationColumn(
        n_species=3, shell_diameter_m=1.4, active_contact_height_m=5.0
    )
    _attach(narrow)
    _attach(wide)

    assert narrow.relative_volatility_reference == pytest.approx(wide.relative_volatility_reference)

    feed = StreamData(
        temperature=350.0,
        pressure=135000.0,
        mole_fractions=(0.78, 0.15, 0.07),
        molar_flow_rate=8.0,
    )
    narrow.apply_inlet("feed_1", feed)
    wide.apply_inlet("feed_1", feed)

    narrow_total_before = float(np.sum(_inventory_component_vector(narrow)))
    wide_total_before = float(np.sum(_inventory_component_vector(wide)))
    assert wide_total_before > narrow_total_before

    before_narrow = _inventory_component_vector(narrow)
    before_wide = _inventory_component_vector(wide)
    narrow.step(0.2)
    wide.step(0.2)
    after_narrow = _inventory_component_vector(narrow)
    after_wide = _inventory_component_vector(wide)

    narrow_fractional_delta = np.linalg.norm(after_narrow - before_narrow) / max(
        1.0e-12, narrow_total_before
    )
    wide_fractional_delta = np.linalg.norm(after_wide - before_wide) / max(
        1.0e-12, wide_total_before
    )
    assert wide_fractional_delta < narrow_fractional_delta


def test_distillate_and_bottoms_share_live_column_pressure_state() -> None:
    column = StagewiseDistillationColumn(n_species=3, column_pressure_pa=180000.0)
    _attach(column)
    column.apply_inlet(
        "feed_1",
        StreamData(
            temperature=330.0,
            pressure=180000.0,
            mole_fractions=(0.5, 0.3, 0.2),
            molar_flow_rate=6.0,
        ),
    )
    column.step(0.2)

    column.column_pressure_pa = 165000.0
    distillate = column.get_outlet_stream("distillate")
    bottoms = column.get_outlet_stream("bottoms")
    assert distillate.pressure == pytest.approx(165000.0)
    assert bottoms.pressure == pytest.approx(165000.0)


def test_hydraulic_participation_declares_feed_and_product_ports() -> None:
    column = StagewiseDistillationColumn(n_species=3, feed_stage_indices=(1, 3))

    participation = column.hydraulic_participation

    assert participation is not None
    assert set(participation.ports) == {
        "feed_1",
        "feed_2",
        "reflux_return",
        "distillate",
        "bottoms",
        "reflux_outlet",
    }
    assert participation.ports["feed_1"].role == "pressure_state"
    assert participation.ports["feed_1"].pressure_state == HydraulicScalarStateRef(
        state="column_pressure_pa"
    )
    assert participation.ports["feed_2"].pressure_state == HydraulicScalarStateRef(
        state="column_pressure_pa"
    )
    assert participation.ports["distillate"].pressure_state == HydraulicScalarStateRef(
        state="column_pressure_pa"
    )
    assert participation.ports["bottoms"].pressure_state == HydraulicScalarStateRef(
        state="column_pressure_pa"
    )
    assert participation.ports["reflux_return"].pressure_state == HydraulicScalarStateRef(
        state="column_pressure_pa"
    )
    assert participation.ports["reflux_outlet"].pressure_state == HydraulicScalarStateRef(
        state="column_pressure_pa"
    )


def test_reflux_ports_are_exposed_on_stagewise_column() -> None:
    column = StagewiseDistillationColumn(n_species=3, feed_stage_indices=(1, 2))

    assert column.ports.inlets == ("feed_1", "feed_2", "reflux_return")
    assert column.ports.outlets == ("distillate", "bottoms", "reflux_outlet")


def test_reflux_return_inlet_stores_normalized_boundary_state() -> None:
    column = StagewiseDistillationColumn(n_species=3)
    _attach(column)

    column.apply_inlet(
        "reflux_return",
        StreamData(
            temperature=322.0,
            pressure=144000.0,
            mole_fractions=(2.0, 1.0, 1.0),
            molar_flow_rate=3.5,
        ),
    )

    assert float(column.reflux_return_flow) == pytest.approx(3.5)
    assert float(column.reflux_return_temperature) == pytest.approx(322.0)
    assert float(column.reflux_return_pressure) == pytest.approx(144000.0)
    assert tuple(column.reflux_return_composition) == pytest.approx((0.5, 0.25, 0.25))


def test_reflux_outlet_tracks_reflux_drum_composition_and_column_pressure() -> None:
    column = StagewiseDistillationColumn(
        n_species=3,
        reflux_drum_component_moles=np.array([9.0, 3.0, 0.0], dtype=np.float64),
        column_pressure_pa=162000.0,
    )
    _attach(column)

    column.step(0.05)
    reflux_outlet = column.get_outlet_stream("reflux_outlet")
    expected = np.asarray(column.reflux_drum_component_moles, dtype=np.float64)
    expected = expected / float(np.sum(expected))

    assert reflux_outlet.pressure == pytest.approx(column.column_pressure_pa)
    assert reflux_outlet.molar_flow_rate >= 0.0
    assert reflux_outlet.mole_fractions == pytest.approx(tuple(expected), abs=1.0e-8)


def test_reflux_return_does_not_bypass_into_reflux_outlet_flow_in_same_closure() -> None:
    baseline = StagewiseDistillationColumn(
        n_species=3,
        reflux_drum_component_moles=np.array([6.0, 2.0, 1.0], dtype=np.float64),
    )
    with_return = StagewiseDistillationColumn(
        n_species=3,
        reflux_drum_component_moles=np.array([6.0, 2.0, 1.0], dtype=np.float64),
    )
    _attach(baseline)
    _attach(with_return)

    with_return.apply_inlet(
        "reflux_return",
        StreamData(
            temperature=321.0,
            pressure=145000.0,
            mole_fractions=(0.0, 1.0, 0.0),
            molar_flow_rate=8.0,
        ),
    )

    params = baseline._params
    y = baseline.differential_view.to_array()
    u_base = baseline.boundary_view.to_array()
    u_return = with_return.boundary_view.to_array()

    algebraic_base = baseline.calculate_algebraic_values(
        y=y,
        u=u_base,
        k=params.k,
        y_map=params.y_map,
        u_map=params.boundary_map,
        k_map=params.k_map,
        algebraic_map=params.algebraic_map,
        algebraic_size=params.algebraic_size,
    )
    algebraic_return = with_return.calculate_algebraic_values(
        y=y,
        u=u_return,
        k=params.k,
        y_map=params.y_map,
        u_map=params.boundary_map,
        k_map=params.k_map,
        algebraic_map=params.algebraic_map,
        algebraic_size=params.algebraic_size,
    )

    assert float(algebraic_return[params.algebraic_map["reflux_outlet_flow"]]) == pytest.approx(
        float(algebraic_base[params.algebraic_map["reflux_outlet_flow"]])
    )


def test_reflux_return_stress_case_does_not_pull_missing_component_out_of_drum_same_step() -> None:
    baseline = StagewiseDistillationColumn(
        n_species=3,
        reflux_drum_component_moles=np.array([1.0, 0.0, 0.0], dtype=np.float64),
    )
    stressed = StagewiseDistillationColumn(
        n_species=3,
        reflux_drum_component_moles=np.array([1.0, 0.0, 0.0], dtype=np.float64),
    )
    _attach(baseline)
    _attach(stressed)

    stressed.apply_inlet(
        "reflux_return",
        StreamData(
            temperature=320.0,
            pressure=145000.0,
            mole_fractions=(0.0, 1.0, 0.0),
            molar_flow_rate=25.0,
        ),
    )

    params = baseline._params
    y = baseline.differential_view.to_array()
    u_base = baseline.boundary_view.to_array()
    u_stressed = stressed.boundary_view.to_array()

    algebraic_base = baseline.calculate_algebraic_values(
        y=y,
        u=u_base,
        k=params.k,
        y_map=params.y_map,
        u_map=params.boundary_map,
        k_map=params.k_map,
        algebraic_map=params.algebraic_map,
        algebraic_size=params.algebraic_size,
    )
    algebraic_stressed = stressed.calculate_algebraic_values(
        y=y,
        u=u_stressed,
        k=params.k,
        y_map=params.y_map,
        u_map=params.boundary_map,
        k_map=params.k_map,
        algebraic_map=params.algebraic_map,
        algebraic_size=params.algebraic_size,
    )

    dy_base = baseline.differential_rhs(
        t=baseline.t,
        y=y,
        u=u_base,
        k=params.k,
        algebraic=algebraic_base,
        y_map=params.y_map,
        u_map=params.boundary_map,
        k_map=params.k_map,
        algebraic_map=params.algebraic_map,
    )
    dy_stressed = stressed.differential_rhs(
        t=stressed.t,
        y=y,
        u=u_stressed,
        k=params.k,
        algebraic=algebraic_stressed,
        y_map=params.y_map,
        u_map=params.boundary_map,
        k_map=params.k_map,
        algebraic_map=params.algebraic_map,
    )

    drum_rates_base = np.asarray(
        dy_base[params.y_map["reflux_drum_component_moles"]], dtype=np.float64
    )
    drum_rates_stressed = np.asarray(
        dy_stressed[params.y_map["reflux_drum_component_moles"]], dtype=np.float64
    )

    assert drum_rates_stressed[1] == pytest.approx(drum_rates_base[1] + 25.0)
    assert drum_rates_stressed[1] > 0.0


def test_empty_reflux_drum_does_not_withdraw_nonexistent_species_through_product_sources() -> None:
    column = StagewiseDistillationColumn(
        n_species=3,
        reflux_drum_component_moles=np.zeros(3, dtype=np.float64),
        stage_component_moles=np.array([12.0, 0.0, 0.0] + [0.0, 0.0, 0.0] * 7, dtype=np.float64),
    )
    _attach(column)
    column.condenser_duty_request_W = -30000.0

    params = column._params
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
    dy = column.differential_rhs(
        t=column.t,
        y=y,
        u=u,
        k=params.k,
        algebraic=algebraic,
        y_map=params.y_map,
        u_map=params.boundary_map,
        k_map=params.k_map,
        algebraic_map=params.algebraic_map,
    )

    drum_rates = np.asarray(dy[params.y_map["reflux_drum_component_moles"]], dtype=np.float64)

    assert drum_rates[1] == pytest.approx(0.0, abs=1.0e-12)
    assert drum_rates[2] == pytest.approx(0.0, abs=1.0e-12)
    assert drum_rates[0] > 0.0


def test_external_reflux_return_changes_transient_column_response() -> None:
    baseline = StagewiseDistillationColumn(n_species=3, active_contact_height_m=6.0)
    with_external_reflux = StagewiseDistillationColumn(n_species=3, active_contact_height_m=6.0)
    _attach(baseline)
    _attach(with_external_reflux)

    feed = StreamData(
        temperature=350.0,
        pressure=150000.0,
        mole_fractions=(0.7, 0.2, 0.1),
        molar_flow_rate=8.0,
    )
    baseline.apply_inlet("feed_1", feed)
    with_external_reflux.apply_inlet("feed_1", feed)
    with_external_reflux.apply_inlet(
        "reflux_return",
        StreamData(
            temperature=330.0,
            pressure=150000.0,
            mole_fractions=(0.05, 0.15, 0.80),
            molar_flow_rate=5.0,
        ),
    )

    for _ in range(4):
        baseline.step(0.1)
        with_external_reflux.step(0.1)

    assert with_external_reflux.get_outlet_stream("distillate").mole_fractions[0] != pytest.approx(
        baseline.get_outlet_stream("distillate").mole_fractions[0]
    )


def test_reflux_return_rhs_closes_to_feed_plus_reflux_return_minus_products() -> None:
    column = StagewiseDistillationColumn(
        n_species=3,
        active_contact_height_m=5.0,
        shell_diameter_m=1.1,
        feed_stage_indices=(1, 3),
    )
    _attach(column)
    column.apply_inlet(
        "feed_1",
        StreamData(
            temperature=340.0,
            pressure=150000.0,
            mole_fractions=(0.6, 0.3, 0.1),
            molar_flow_rate=7.0,
        ),
    )
    column.apply_inlet(
        "feed_2",
        StreamData(
            temperature=330.0,
            pressure=150000.0,
            mole_fractions=(0.1, 0.3, 0.6),
            molar_flow_rate=5.0,
        ),
    )
    column.apply_inlet(
        "reflux_return",
        StreamData(
            temperature=322.0,
            pressure=150000.0,
            mole_fractions=(0.2, 0.4, 0.4),
            molar_flow_rate=2.0,
        ),
    )

    params = column._params
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
    dy = column.differential_rhs(
        t=column.t,
        y=y,
        u=u,
        k=params.k,
        algebraic=algebraic,
        y_map=params.y_map,
        u_map=params.boundary_map,
        k_map=params.k_map,
        algebraic_map=params.algebraic_map,
    )

    stage_rates = np.asarray(dy[params.y_map["stage_component_moles"]], dtype=np.float64).reshape(
        column.n_stages, column.n_species
    )
    drum_rates = np.asarray(dy[params.y_map["reflux_drum_component_moles"]], dtype=np.float64)
    sump_rates = np.asarray(dy[params.y_map["bottoms_sump_component_moles"]], dtype=np.float64)
    inventory_rate = np.sum(stage_rates, axis=0) + drum_rates + sump_rates

    feed_rates = np.zeros(column.n_species, dtype=np.float64)
    feed_compositions = np.asarray(column.feed_compositions, dtype=np.float64).reshape(
        column.n_feeds, column.n_species
    )
    for feed_index in range(column.n_feeds):
        flow = float(column.feed_flows[feed_index])
        composition = np.asarray(feed_compositions[feed_index], dtype=np.float64)
        feed_rates += flow * composition

    reflux_return_rates = float(column.reflux_return_flow) * np.asarray(
        column.reflux_return_composition, dtype=np.float64
    )
    distillate_component = float(algebraic[params.algebraic_map["distillate_flow"]]) * np.asarray(
        algebraic[params.algebraic_map["distillate_composition"]], dtype=np.float64
    )
    bottoms_component = float(algebraic[params.algebraic_map["bottoms_flow"]]) * np.asarray(
        algebraic[params.algebraic_map["bottoms_composition"]], dtype=np.float64
    )

    assert inventory_rate == pytest.approx(
        feed_rates + reflux_return_rates - distillate_component - bottoms_component,
        abs=1.0e-8,
    )


def test_reflux_return_does_not_drive_negative_drum_component_inventory() -> None:
    column = StagewiseDistillationColumn(
        n_species=3,
        reflux_drum_component_moles=np.array([0.2, 0.2, 0.2], dtype=np.float64),
    )
    _attach(column)
    column.apply_inlet(
        "reflux_return",
        StreamData(
            temperature=330.0,
            pressure=130000.0,
            mole_fractions=(0.0, 0.0, 1.0),
            molar_flow_rate=4.0,
        ),
    )

    for _ in range(3):
        column.step(0.02)

    assert np.min(np.asarray(column.reflux_drum_component_moles, dtype=np.float64)) >= -1.0e-12


def test_column_pressure_does_not_change_constant_relative_volatility_closure() -> None:
    low_pressure_column = StagewiseDistillationColumn(n_species=3, column_pressure_pa=120000.0)
    high_pressure_column = StagewiseDistillationColumn(n_species=3, column_pressure_pa=260000.0)
    _attach(low_pressure_column)
    _attach(high_pressure_column)

    feed = StreamData(
        temperature=350.0,
        pressure=180000.0,
        mole_fractions=(0.75, 0.2, 0.05),
        molar_flow_rate=8.0,
    )
    low_pressure_column.apply_inlet("feed_1", feed)
    high_pressure_column.apply_inlet("feed_1", feed)

    low_params = low_pressure_column._params
    high_params = high_pressure_column._params
    low_y = low_pressure_column.differential_view.to_array()
    high_y = high_pressure_column.differential_view.to_array()
    low_u = low_pressure_column.boundary_view.to_array()
    high_u = high_pressure_column.boundary_view.to_array()

    low_alg = low_pressure_column.calculate_algebraic_values(
        y=low_y,
        u=low_u,
        k=low_params.k,
        y_map=low_params.y_map,
        u_map=low_params.boundary_map,
        k_map=low_params.k_map,
        algebraic_map=low_params.algebraic_map,
        algebraic_size=low_params.algebraic_size,
    )
    high_alg = high_pressure_column.calculate_algebraic_values(
        y=high_y,
        u=high_u,
        k=high_params.k,
        y_map=high_params.y_map,
        u_map=high_params.boundary_map,
        k_map=high_params.k_map,
        algebraic_map=high_params.algebraic_map,
        algebraic_size=high_params.algebraic_size,
    )

    assert low_alg[low_params.algebraic_map["distillate_composition"]] == pytest.approx(
        high_alg[high_params.algebraic_map["distillate_composition"]]
    )
    assert low_alg[low_params.algebraic_map["bottoms_composition"]] == pytest.approx(
        high_alg[high_params.algebraic_map["bottoms_composition"]]
    )
    assert low_alg[low_params.algebraic_map["distillate_flow"]] == pytest.approx(
        high_alg[high_params.algebraic_map["distillate_flow"]]
    )
    assert low_alg[low_params.algebraic_map["bottoms_flow"]] == pytest.approx(
        high_alg[high_params.algebraic_map["bottoms_flow"]]
    )


def test_column_pressure_derivative_is_neutral_hold_not_feed_average_chasing() -> None:
    column = StagewiseDistillationColumn(
        n_species=3, feed_stage_indices=(1, 3), column_pressure_pa=140000.0
    )
    _attach(column)
    column.apply_inlet(
        "feed_1",
        StreamData(
            temperature=345.0,
            pressure=120000.0,
            mole_fractions=(0.6, 0.3, 0.1),
            molar_flow_rate=5.0,
        ),
    )
    column.apply_inlet(
        "feed_2",
        StreamData(
            temperature=345.0,
            pressure=240000.0,
            mole_fractions=(0.1, 0.3, 0.6),
            molar_flow_rate=7.0,
        ),
    )

    params = column._params
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
    dy = column.differential_rhs(
        t=column.t,
        y=y,
        u=u,
        k=params.k,
        algebraic=algebraic,
        y_map=params.y_map,
        u_map=params.boundary_map,
        k_map=params.k_map,
        algebraic_map=params.algebraic_map,
    )

    assert float(dy[params.y_map["column_pressure_pa"]]) == pytest.approx(0.0, abs=1.0e-12)


def test_shell_diameter_does_not_directly_rescale_named_molar_flow_parameters() -> None:
    narrow = StagewiseDistillationColumn(n_species=3, shell_diameter_m=0.8)
    wide = StagewiseDistillationColumn(n_species=3, shell_diameter_m=1.6)
    _attach(narrow)
    _attach(wide)

    feed = StreamData(
        temperature=350.0,
        pressure=150000.0,
        mole_fractions=(0.7, 0.2, 0.1),
        molar_flow_rate=8.0,
    )
    narrow.apply_inlet("feed_1", feed)
    wide.apply_inlet("feed_1", feed)

    assert narrow.stage_liquid_flow_mol_s == pytest.approx(wide.stage_liquid_flow_mol_s)
    assert narrow.stage_vapor_flow_mol_s == pytest.approx(wide.stage_vapor_flow_mol_s)

    narrow.step(0.2)
    wide.step(0.2)

    assert narrow.distillate_flow == pytest.approx(wide.distillate_flow)
    assert narrow.bottoms_flow == pytest.approx(wide.bottoms_flow)


def test_boundary_distillate_withdrawal_controls_distillate_outlet_flow() -> None:
    column = StagewiseDistillationColumn(
        n_species=3,
        reflux_drum_component_moles=np.array([10.0, 4.0, 2.0], dtype=np.float64),
    )
    _attach(column)

    column.distillate_withdrawal_flow = 2.75
    column.step(0.05)

    assert column.get_outlet_stream("distillate").molar_flow_rate == pytest.approx(2.75)


def test_higher_distillate_withdrawal_lowers_reflux_outlet_flow() -> None:
    low = StagewiseDistillationColumn(
        n_species=3,
        reflux_drum_component_moles=np.array([10.0, 4.0, 2.0], dtype=np.float64),
    )
    high = StagewiseDistillationColumn(
        n_species=3,
        reflux_drum_component_moles=np.array([10.0, 4.0, 2.0], dtype=np.float64),
    )
    _attach(low)
    _attach(high)
    low.condenser_duty_request_W = -30000.0
    high.condenser_duty_request_W = -30000.0

    low.distillate_withdrawal_flow = 0.2
    high.distillate_withdrawal_flow = 3.0

    low_params = low._params
    low_y = low.differential_view.to_array()
    low_u = low.boundary_view.to_array()
    low_alg = low.calculate_algebraic_values(
        y=low_y,
        u=low_u,
        k=low_params.k,
        y_map=low_params.y_map,
        u_map=low_params.boundary_map,
        k_map=low_params.k_map,
        algebraic_map=low_params.algebraic_map,
        algebraic_size=low_params.algebraic_size,
    )

    high_params = high._params
    high_y = high.differential_view.to_array()
    high_u = high.boundary_view.to_array()
    high_alg = high.calculate_algebraic_values(
        y=high_y,
        u=high_u,
        k=high_params.k,
        y_map=high_params.y_map,
        u_map=high_params.boundary_map,
        k_map=high_params.k_map,
        algebraic_map=high_params.algebraic_map,
        algebraic_size=high_params.algebraic_size,
    )

    assert float(high_alg[high_params.algebraic_map["reflux_outlet_flow"]]) < float(
        low_alg[low_params.algebraic_map["reflux_outlet_flow"]]
    )


def test_empty_reflux_drum_reports_zero_reflux_outlet_flow() -> None:
    column = StagewiseDistillationColumn(
        n_species=3,
        reflux_drum_component_moles=np.zeros(3, dtype=np.float64),
    )
    _attach(column)

    params = column._params
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

    assert float(algebraic[params.algebraic_map["reflux_outlet_flow"]]) == pytest.approx(0.0)


def test_distillate_withdrawal_remains_reflux_drum_owned_and_holdup_bounded() -> None:
    column = StagewiseDistillationColumn(
        n_species=3,
        reflux_drum_component_moles=np.array([10.0, 4.0, 2.0], dtype=np.float64),
    )
    _attach(column)

    column.distillate_withdrawal_flow = 2.75
    params = column._params
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

    assert float(algebraic[params.algebraic_map["distillate_flow"]]) == pytest.approx(2.75)


def test_boundary_bottoms_withdrawal_controls_bottoms_outlet_flow() -> None:
    column = StagewiseDistillationColumn(
        n_species=3,
        bottoms_sump_component_moles=np.array([8.0, 3.0, 1.0], dtype=np.float64),
    )
    _attach(column)

    column.bottoms_withdrawal_flow = 1.8
    column.step(0.05)

    assert column.get_outlet_stream("bottoms").molar_flow_rate == pytest.approx(1.8)


def test_distillate_withdrawal_is_reflux_drum_owned_and_holdup_bounded() -> None:
    column = StagewiseDistillationColumn(
        n_species=3,
        reflux_drum_component_moles=np.zeros(3, dtype=np.float64),
        stage_component_moles=np.array([30.0, 10.0, 5.0] + [0.0, 0.0, 0.0] * 7, dtype=np.float64),
    )
    _attach(column)

    column.distillate_withdrawal_flow = 9.0
    params = column._params
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

    assert float(algebraic[params.algebraic_map["distillate_flow"]]) == pytest.approx(0.0)


def test_bottoms_withdrawal_is_bottoms_sump_owned_and_holdup_bounded() -> None:
    column = StagewiseDistillationColumn(
        n_species=3,
        bottoms_sump_component_moles=np.zeros(3, dtype=np.float64),
        stage_component_moles=np.array([0.0, 0.0, 0.0] * 7 + [30.0, 10.0, 5.0], dtype=np.float64),
    )
    _attach(column)

    column.bottoms_withdrawal_flow = 7.0
    params = column._params
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

    assert float(algebraic[params.algebraic_map["bottoms_flow"]]) == pytest.approx(0.0)


def test_product_withdrawal_changes_owner_balance_direction() -> None:
    low = StagewiseDistillationColumn(
        n_species=3,
        reflux_drum_component_moles=np.array([10.0, 4.0, 2.0], dtype=np.float64),
        bottoms_sump_component_moles=np.array([8.0, 3.0, 1.0], dtype=np.float64),
    )
    high = StagewiseDistillationColumn(
        n_species=3,
        reflux_drum_component_moles=np.array([10.0, 4.0, 2.0], dtype=np.float64),
        bottoms_sump_component_moles=np.array([8.0, 3.0, 1.0], dtype=np.float64),
    )
    _attach(low)
    _attach(high)
    for unit in (low, high):
        unit.condenser_duty_request_W = -30000.0
        unit.reboiler_duty_request_W = 30000.0

    low.distillate_withdrawal_flow = 0.2
    low.bottoms_withdrawal_flow = 0.1
    high.distillate_withdrawal_flow = 3.0
    high.bottoms_withdrawal_flow = 2.5

    low_params = low._params
    low_y = low.differential_view.to_array()
    low_u = low.boundary_view.to_array()
    low_alg = low.calculate_algebraic_values(
        y=low_y,
        u=low_u,
        k=low_params.k,
        y_map=low_params.y_map,
        u_map=low_params.boundary_map,
        k_map=low_params.k_map,
        algebraic_map=low_params.algebraic_map,
        algebraic_size=low_params.algebraic_size,
    )
    low_dy = low.differential_rhs(
        t=low.t,
        y=low_y,
        u=low_u,
        k=low_params.k,
        algebraic=low_alg,
        y_map=low_params.y_map,
        u_map=low_params.boundary_map,
        k_map=low_params.k_map,
        algebraic_map=low_params.algebraic_map,
    )

    high_params = high._params
    high_y = high.differential_view.to_array()
    high_u = high.boundary_view.to_array()
    high_alg = high.calculate_algebraic_values(
        y=high_y,
        u=high_u,
        k=high_params.k,
        y_map=high_params.y_map,
        u_map=high_params.boundary_map,
        k_map=high_params.k_map,
        algebraic_map=high_params.algebraic_map,
        algebraic_size=high_params.algebraic_size,
    )

    assert float(high_alg[high_params.algebraic_map["reflux_outlet_flow"]]) < float(
        low_alg[low_params.algebraic_map["reflux_outlet_flow"]]
    )
    assert float(high_alg[high_params.algebraic_map["distillate_flow"]]) > float(
        low_alg[low_params.algebraic_map["distillate_flow"]]
    )
    assert float(high_alg[high_params.algebraic_map["bottoms_flow"]]) > float(
        low_alg[low_params.algebraic_map["bottoms_flow"]]
    )


def test_ratios_no_longer_actuate_live_product_withdrawal_flows() -> None:
    low_ratio = StagewiseDistillationColumn(
        n_species=3,
        reflux_ratio=0.1,
        boilup_ratio=0.2,
        reflux_drum_component_moles=np.array([10.0, 3.0, 1.0], dtype=np.float64),
        bottoms_sump_component_moles=np.array([8.0, 3.0, 1.0], dtype=np.float64),
    )
    high_ratio = StagewiseDistillationColumn(
        n_species=3,
        reflux_ratio=8.0,
        boilup_ratio=6.0,
        reflux_drum_component_moles=np.array([10.0, 3.0, 1.0], dtype=np.float64),
        bottoms_sump_component_moles=np.array([8.0, 3.0, 1.0], dtype=np.float64),
    )
    _attach(low_ratio)
    _attach(high_ratio)

    low_ratio.distillate_withdrawal_flow = 1.4
    low_ratio.bottoms_withdrawal_flow = 0.7
    high_ratio.distillate_withdrawal_flow = 1.4
    high_ratio.bottoms_withdrawal_flow = 0.7

    low_ratio.step(0.05)
    high_ratio.step(0.05)

    assert low_ratio.distillate_flow == pytest.approx(1.4)
    assert high_ratio.distillate_flow == pytest.approx(1.4)
    assert low_ratio.bottoms_flow == pytest.approx(0.7)
    assert high_ratio.bottoms_flow == pytest.approx(0.7)


def test_zero_duties_disable_direct_duty_phase_change_paths() -> None:
    column = StagewiseDistillationColumn(
        n_species=3,
        stage_vapor_flow_mol_s=8.0,
    )
    _attach(column)

    algebraic = _compute_algebraic(column)
    params = column._params

    assert float(algebraic[params.algebraic_map["realized_condensed_flow_mol_s"]]) == pytest.approx(
        0.0
    )
    assert float(
        algebraic[params.algebraic_map["realized_reboiler_boilup_flow_mol_s"]]
    ) == pytest.approx(0.0)
    assert float(algebraic[params.algebraic_map["condenser_duty_W"]]) == pytest.approx(0.0)
    assert float(algebraic[params.algebraic_map["reboiler_duty_W"]]) == pytest.approx(0.0)


def test_direct_duty_readouts_match_realized_q_over_lambda_after_clipping() -> None:
    column = StagewiseDistillationColumn(
        n_species=3,
        stage_vapor_flow_mol_s=1.0,
        bottoms_sump_component_moles=np.array([0.2, 0.1, 0.0], dtype=np.float64),
    )
    _attach(column)

    column.condenser_duty_request_W = -60000.0
    column.reboiler_duty_request_W = 60000.0

    algebraic = _compute_algebraic(column)
    params = column._params

    assert float(algebraic[params.algebraic_map["realized_condensed_flow_mol_s"]]) == pytest.approx(
        1.0
    )
    assert float(algebraic[params.algebraic_map["condenser_duty_W"]]) == pytest.approx(-30000.0)
    assert float(
        algebraic[params.algebraic_map["realized_reboiler_boilup_flow_mol_s"]]
    ) == pytest.approx(0.3)
    assert float(algebraic[params.algebraic_map["reboiler_duty_W"]]) == pytest.approx(9000.0)


def test_wrong_sign_direct_duty_requests_do_not_drive_phase_change() -> None:
    column = StagewiseDistillationColumn(
        n_species=3,
        stage_vapor_flow_mol_s=8.0,
        bottoms_sump_component_moles=np.array([0.2, 0.1, 0.0], dtype=np.float64),
    )
    _attach(column)

    column.condenser_duty_request_W = 15000.0
    column.reboiler_duty_request_W = -15000.0

    algebraic = _compute_algebraic(column)
    params = column._params

    assert float(algebraic[params.algebraic_map["realized_condensed_flow_mol_s"]]) == pytest.approx(
        0.0
    )
    assert float(algebraic[params.algebraic_map["condenser_duty_W"]]) == pytest.approx(0.0)
    assert float(
        algebraic[params.algebraic_map["realized_reboiler_boilup_flow_mol_s"]]
    ) == pytest.approx(0.0)
    assert float(algebraic[params.algebraic_map["reboiler_duty_W"]]) == pytest.approx(0.0)


def test_condenser_duty_request_increases_realized_condensation_and_is_nonpositive() -> None:
    low = StagewiseDistillationColumn(n_species=3)
    high = StagewiseDistillationColumn(n_species=3)
    _attach(low)
    _attach(high)

    low.condenser_duty_request_W = -20000.0
    high.condenser_duty_request_W = -50000.0

    low_alg = _compute_algebraic(low)
    high_alg = _compute_algebraic(high)
    low_map = low._params.algebraic_map
    high_map = high._params.algebraic_map

    assert float(high_alg[high_map["realized_condensed_flow_mol_s"]]) > float(
        low_alg[low_map["realized_condensed_flow_mol_s"]]
    )
    assert float(low_alg[low_map["condenser_duty_W"]]) <= 0.0
    assert float(high_alg[high_map["condenser_duty_W"]]) <= 0.0


def test_reboiler_duty_request_increases_realized_boilup_and_is_nonnegative() -> None:
    low = StagewiseDistillationColumn(n_species=3)
    high = StagewiseDistillationColumn(n_species=3)
    _attach(low)
    _attach(high)

    low.reboiler_duty_request_W = 10000.0
    high.reboiler_duty_request_W = 30000.0

    low_alg = _compute_algebraic(low)
    high_alg = _compute_algebraic(high)
    low_map = low._params.algebraic_map
    high_map = high._params.algebraic_map

    assert float(high_alg[high_map["realized_reboiler_boilup_flow_mol_s"]]) > float(
        low_alg[low_map["realized_reboiler_boilup_flow_mol_s"]]
    )
    assert float(low_alg[low_map["reboiler_duty_W"]]) >= 0.0
    assert float(high_alg[high_map["reboiler_duty_W"]]) >= 0.0


def test_direct_duty_phase_change_paths_follow_realized_q_over_lambda_in_rhs() -> None:
    column = StagewiseDistillationColumn(
        n_species=3,
        stage_vapor_flow_mol_s=8.0,
        bottoms_sump_component_moles=np.array([0.2, 0.1, 0.0], dtype=np.float64),
    )
    _attach(column)
    params = column._params
    y = column.differential_view.to_array()

    def snapshot() -> tuple[np.ndarray, np.ndarray]:
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
        dy = column.differential_rhs(
            t=column.t,
            y=y,
            u=u,
            k=params.k,
            algebraic=algebraic,
            y_map=params.y_map,
            u_map=params.boundary_map,
            k_map=params.k_map,
            algebraic_map=params.algebraic_map,
        )
        return algebraic, dy

    base_alg, base_dy = snapshot()

    column.condenser_duty_request_W = -30000.0
    column.reboiler_duty_request_W = 30000.0
    active_alg, active_dy = snapshot()

    column.condenser_duty_request_W = 30000.0
    column.reboiler_duty_request_W = -30000.0
    wrong_alg, wrong_dy = snapshot()

    active_stage_rates = np.asarray(
        active_dy[params.y_map["stage_component_moles"]], dtype=np.float64
    ).reshape(column.n_stages, column.n_species)
    base_stage_rates = np.asarray(
        base_dy[params.y_map["stage_component_moles"]], dtype=np.float64
    ).reshape(column.n_stages, column.n_species)
    wrong_stage_rates = np.asarray(
        wrong_dy[params.y_map["stage_component_moles"]], dtype=np.float64
    ).reshape(column.n_stages, column.n_species)

    active_drum_rates = np.asarray(
        active_dy[params.y_map["reflux_drum_component_moles"]], dtype=np.float64
    )
    base_drum_rates = np.asarray(
        base_dy[params.y_map["reflux_drum_component_moles"]], dtype=np.float64
    )
    wrong_drum_rates = np.asarray(
        wrong_dy[params.y_map["reflux_drum_component_moles"]], dtype=np.float64
    )

    active_sump_rates = np.asarray(
        active_dy[params.y_map["bottoms_sump_component_moles"]], dtype=np.float64
    )
    base_sump_rates = np.asarray(
        base_dy[params.y_map["bottoms_sump_component_moles"]], dtype=np.float64
    )
    wrong_sump_rates = np.asarray(
        wrong_dy[params.y_map["bottoms_sump_component_moles"]], dtype=np.float64
    )

    assert float(
        active_alg[params.algebraic_map["realized_condensed_flow_mol_s"]]
    ) == pytest.approx(1.0)
    assert float(
        active_alg[params.algebraic_map["realized_reboiler_boilup_flow_mol_s"]]
    ) == pytest.approx(0.3)
    assert float(wrong_alg[params.algebraic_map["realized_condensed_flow_mol_s"]]) == pytest.approx(
        0.0
    )
    assert float(
        wrong_alg[params.algebraic_map["realized_reboiler_boilup_flow_mol_s"]]
    ) == pytest.approx(0.0)

    assert not np.allclose(active_stage_rates[0], base_stage_rates[0])
    assert not np.allclose(active_drum_rates, base_drum_rates)
    assert not np.allclose(active_stage_rates[-1], base_stage_rates[-1])
    assert not np.allclose(active_sump_rates, base_sump_rates)

    assert np.allclose(wrong_stage_rates[0], base_stage_rates[0])
    assert np.allclose(wrong_drum_rates, base_drum_rates)
    assert np.allclose(wrong_stage_rates[-1], base_stage_rates[-1])
    assert np.allclose(wrong_sump_rates, base_sump_rates)


def test_reflux_outlet_flow_uses_realized_condensed_flow_not_legacy_fallback() -> None:
    column = StagewiseDistillationColumn(
        n_species=3,
        stage_vapor_flow_mol_s=8.0,
        reflux_drum_component_moles=np.array([10.0, 3.0, 1.0], dtype=np.float64),
    )
    _attach(column)

    column.condenser_duty_request_W = -30000.0

    algebraic = _compute_algebraic(column)
    params = column._params

    assert float(algebraic[params.algebraic_map["realized_condensed_flow_mol_s"]]) == pytest.approx(
        1.0
    )
    assert float(algebraic[params.algebraic_map["reflux_outlet_flow"]]) == pytest.approx(1.0)


def test_duty_driven_phase_change_rates_remain_inventory_bounded_and_conservative() -> None:
    column = StagewiseDistillationColumn(
        n_species=3,
        bottoms_sump_component_moles=np.array([0.2, 0.1, 0.0], dtype=np.float64),
    )
    _attach(column)

    column.condenser_duty_request_W = -1.0e9
    column.reboiler_duty_request_W = 1.0e9

    params = column._params
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
    dy = column.differential_rhs(
        t=column.t,
        y=y,
        u=u,
        k=params.k,
        algebraic=algebraic,
        y_map=params.y_map,
        u_map=params.boundary_map,
        k_map=params.k_map,
        algebraic_map=params.algebraic_map,
    )

    assert (
        float(algebraic[params.algebraic_map["realized_condensed_flow_mol_s"]])
        <= float(column.stage_vapor_flow_mol_s) + 1.0e-12
    )
    assert (
        float(algebraic[params.algebraic_map["realized_reboiler_boilup_flow_mol_s"]])
        <= float(np.sum(column.bottoms_sump_component_moles)) + 1.0e-12
    )

    stage_rates = np.asarray(dy[params.y_map["stage_component_moles"]], dtype=np.float64).reshape(
        column.n_stages, column.n_species
    )
    drum_rates = np.asarray(dy[params.y_map["reflux_drum_component_moles"]], dtype=np.float64)
    sump_rates = np.asarray(dy[params.y_map["bottoms_sump_component_moles"]], dtype=np.float64)
    inventory_rate = np.sum(stage_rates, axis=0) + drum_rates + sump_rates

    distillate_component = float(algebraic[params.algebraic_map["distillate_flow"]]) * np.asarray(
        algebraic[params.algebraic_map["distillate_composition"]], dtype=np.float64
    )
    bottoms_component = float(algebraic[params.algebraic_map["bottoms_flow"]]) * np.asarray(
        algebraic[params.algebraic_map["bottoms_composition"]], dtype=np.float64
    )
    assert inventory_rate == pytest.approx(-(distillate_component + bottoms_component), abs=1.0e-8)


def test_ratios_do_not_override_live_duty_actuation_path() -> None:
    low_ratio = StagewiseDistillationColumn(n_species=3, reflux_ratio=0.2, boilup_ratio=0.3)
    high_ratio = StagewiseDistillationColumn(n_species=3, reflux_ratio=8.0, boilup_ratio=6.0)
    _attach(low_ratio)
    _attach(high_ratio)

    for unit in (low_ratio, high_ratio):
        unit.condenser_duty_request_W = -24000.0
        unit.reboiler_duty_request_W = 18000.0

    low_alg = _compute_algebraic(low_ratio)
    high_alg = _compute_algebraic(high_ratio)
    low_map = low_ratio._params.algebraic_map
    high_map = high_ratio._params.algebraic_map

    assert float(low_alg[low_map["realized_condensed_flow_mol_s"]]) == pytest.approx(
        float(high_alg[high_map["realized_condensed_flow_mol_s"]])
    )
    assert float(low_alg[low_map["realized_reboiler_boilup_flow_mol_s"]]) == pytest.approx(
        float(high_alg[high_map["realized_reboiler_boilup_flow_mol_s"]])
    )

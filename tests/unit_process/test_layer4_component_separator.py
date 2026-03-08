from __future__ import annotations

# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportMissingImports=false, reportUnknownVariableType=false, reportUnknownParameterType=false, reportUnknownArgumentType=false, reportAttributeAccessIssue=false, reportUnnecessaryTypeIgnoreComment=false, reportArgumentType=false

from types import SimpleNamespace

import numpy as np
import pytest
from numpy.typing import NDArray

from modular_simulation.unit_processes.component_separator import ComponentSeparator


def _attach(model: ComponentSeparator) -> None:
    model.attach_system(SimpleNamespace(solver_options={}))


def test_component_separator_species_split_and_balance() -> None:
    separator = ComponentSeparator(
        n_species=2,
        configured_split_fraction_targets=np.array([0.9, 0.1], dtype=np.float64),
        inlet_flow=10.0,
        inlet_temperature=330.0,
        inlet_pressure=200000.0,
        inlet_composition=np.array([0.4, 0.6], dtype=np.float64),
    )
    _attach(separator)

    separator.step(0.1)

    inlet_component_flows = np.array([4.0, 6.0], dtype=np.float64)
    expected_outlet_1_component = np.array([3.6, 0.6], dtype=np.float64)
    expected_outlet_2_component = np.array([0.4, 5.4], dtype=np.float64)

    expected_outlet_1_flow = float(np.sum(expected_outlet_1_component))
    expected_outlet_2_flow = float(np.sum(expected_outlet_2_component))

    expected_outlet_1_composition = expected_outlet_1_component / expected_outlet_1_flow
    expected_outlet_2_composition = expected_outlet_2_component / expected_outlet_2_flow

    assert separator.outlet_1_flow == pytest.approx(expected_outlet_1_flow)
    assert separator.outlet_2_flow == pytest.approx(expected_outlet_2_flow)
    assert separator.outlet_1_temperature == pytest.approx(separator.inlet_temperature)
    assert separator.outlet_2_temperature == pytest.approx(separator.inlet_temperature)
    assert separator.outlet_1_pressure == pytest.approx(separator.inlet_pressure)
    assert separator.outlet_2_pressure == pytest.approx(separator.inlet_pressure)
    assert np.asarray(separator.outlet_1_composition, dtype=np.float64) == pytest.approx(
        expected_outlet_1_composition
    )
    assert np.asarray(separator.outlet_2_composition, dtype=np.float64) == pytest.approx(
        expected_outlet_2_composition
    )

    outlet_component_flows = separator.outlet_1_flow * np.asarray(
        separator.outlet_1_composition, dtype=np.float64
    ) + separator.outlet_2_flow * np.asarray(separator.outlet_2_composition, dtype=np.float64)
    assert outlet_component_flows == pytest.approx(inlet_component_flows)
    assert separator.outlet_1_flow + separator.outlet_2_flow == pytest.approx(separator.inlet_flow)
    assert separator.ports.inlets == ("inlet",)
    assert separator.ports.outlets == ("outlet_1", "outlet_2")


def test_component_separator_supports_species_named_split_mapping() -> None:
    separator = ComponentSeparator(
        n_species=2,
        configured_split_fraction_targets={"water": 0.9, "ethanol": 0.1},
        species_order=("water", "ethanol"),
        inlet_flow=10.0,
        inlet_temperature=325.0,
        inlet_pressure=101325.0,
        inlet_composition=np.array([0.5, 0.5], dtype=np.float64),
    )

    assert np.asarray(
        separator.configured_split_fraction_targets, dtype=np.float64
    ) == pytest.approx(np.array([0.9, 0.1], dtype=np.float64))


def test_component_separator_accepts_legacy_split_fractions_with_warning() -> None:
    with pytest.warns(
        DeprecationWarning,
        match=r"split_fractions is deprecated; use configured_split_fraction_targets",
    ):
        separator = ComponentSeparator(
            n_species=2,
            split_fractions={"water": 0.8, "ethanol": 0.2},
            species_order=("water", "ethanol"),
        )

    assert np.asarray(
        separator.configured_split_fraction_targets, dtype=np.float64
    ) == pytest.approx(np.array([0.8, 0.2], dtype=np.float64))


@pytest.mark.parametrize(
    ("configured_split_fraction_targets", "zero_is_outlet_1", "expected_nonzero_comp"),
    [
        (
            np.array([0.0, 0.0], dtype=np.float64),
            True,
            np.array([0.3, 0.7], dtype=np.float64),
        ),
        (
            np.array([1.0, 1.0], dtype=np.float64),
            False,
            np.array([0.3, 0.7], dtype=np.float64),
        ),
    ],
)
def test_component_separator_zero_flow_outlet_composition_is_stable(
    configured_split_fraction_targets: NDArray[np.float64],
    zero_is_outlet_1: bool,
    expected_nonzero_comp: NDArray[np.float64],
) -> None:
    separator = ComponentSeparator(
        n_species=2,
        configured_split_fraction_targets=configured_split_fraction_targets,
        inlet_flow=5.0,
        inlet_temperature=300.0,
        inlet_pressure=101325.0,
        inlet_composition=np.array([0.3, 0.7], dtype=np.float64),
    )
    _attach(separator)

    separator.step(0.1)

    if zero_is_outlet_1:
        assert separator.outlet_1_flow == pytest.approx(0.0)
        assert separator.outlet_2_flow == pytest.approx(separator.inlet_flow)
        zero_composition = np.asarray(separator.outlet_1_composition, dtype=np.float64)
        nonzero_composition = np.asarray(separator.outlet_2_composition, dtype=np.float64)
    else:
        assert separator.outlet_2_flow == pytest.approx(0.0)
        assert separator.outlet_1_flow == pytest.approx(separator.inlet_flow)
        zero_composition = np.asarray(separator.outlet_2_composition, dtype=np.float64)
        nonzero_composition = np.asarray(separator.outlet_1_composition, dtype=np.float64)

    assert np.all(np.isfinite(zero_composition))
    assert float(np.sum(zero_composition)) == pytest.approx(1.0)
    assert nonzero_composition == pytest.approx(expected_nonzero_comp)


@pytest.mark.parametrize("invalid_fraction", [-0.1, 1.1])
def test_component_separator_invalid_split_fraction_raises(invalid_fraction: float) -> None:
    with pytest.raises(
        ValueError,
        match=r"configured_split_fraction_targets must stay within \[0, 1\]",
    ):
        _ = ComponentSeparator(
            n_species=2,
            configured_split_fraction_targets=np.array([invalid_fraction, 0.5], dtype=np.float64),
            inlet_flow=3.0,
            inlet_temperature=310.0,
            inlet_pressure=101325.0,
            inlet_composition=np.array([0.5, 0.5], dtype=np.float64),
        )

"""Wave 1 failing unit tests for Howard1970DistillationColumn.

These tests define the pre-implementation contract for the Howard (1970)
paper-faithful dynamic distillation model.  They are expected to **fail**
(ImportError / AttributeError) until Wave 2 introduces the class and
updates the package exports.

Covers:
  - Class existence, construction, and ProcessModel lineage
  - Package-level export in ``separation`` and ``unit_processes``
  - Sibling coexistence with ``StagewiseDistillationColumn``
  - Feed/product runtime seam shape (``apply_inlet``, ``get_outlet_stream``,
    ``ports``)
  - Equation-fidelity regression fixtures against frozen GE-H70-1..GE-H70-8
"""

from __future__ import annotations

import importlib
from types import SimpleNamespace
from typing import Any, cast

import numpy as np
import pytest

from modular_simulation.measurables.process_model import ProcessModel
from modular_simulation.thermodynamics.stream import StreamData
from modular_simulation.unit_processes import StagewiseDistillationColumn
from modular_simulation.unit_processes.separation import (
    StagewiseDistillationColumn as StagewiseFromPkg,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _attach(model: ProcessModel) -> None:
    model.attach_system(cast(Any, SimpleNamespace(solver_options={})))


def _require_callable(candidate: Any, *names: str) -> Any:
    for name in names:
        value = getattr(candidate, name, None)
        if callable(value):
            return value
    joined = ", ".join(names)
    pytest.fail(f"Expected one of the following callables to exist: {joined}")


# ---------------------------------------------------------------------------
# 1. Class existence, construction, and lineage
# ---------------------------------------------------------------------------


class TestHowardClassExistenceAndConstruction:
    """Howard1970DistillationColumn must be importable and constructable."""

    def test_import_from_separation_package(self) -> None:
        """Howard1970DistillationColumn is exported from ``separation``."""
        from modular_simulation.unit_processes.separation import (
            Howard1970DistillationColumn,
        )  # noqa: F401

    def test_import_from_unit_processes_top_level(self) -> None:
        """Howard1970DistillationColumn is exported from ``unit_processes``."""
        from modular_simulation.unit_processes import (
            Howard1970DistillationColumn,
        )  # noqa: F401

    def test_class_is_process_model_subclass(self) -> None:
        from modular_simulation.unit_processes.separation import (
            Howard1970DistillationColumn,
        )

        column = Howard1970DistillationColumn(n_species=3, n_plates=5)
        assert isinstance(column, ProcessModel)

    def test_basic_construction_with_defaults(self) -> None:
        from modular_simulation.unit_processes.separation import (
            Howard1970DistillationColumn,
        )

        column = Howard1970DistillationColumn(n_species=2, n_plates=4)
        assert column.n_species == 2
        assert column.n_plates == 4

    def test_construction_rejects_single_species(self) -> None:
        from modular_simulation.unit_processes.separation import (
            Howard1970DistillationColumn,
        )

        with pytest.raises(ValueError, match="n_species"):
            Howard1970DistillationColumn(n_species=1, n_plates=4)

    def test_construction_rejects_zero_plates(self) -> None:
        from modular_simulation.unit_processes.separation import (
            Howard1970DistillationColumn,
        )

        with pytest.raises(ValueError):
            Howard1970DistillationColumn(n_species=2, n_plates=0)


# ---------------------------------------------------------------------------
# 2. Package exports
# ---------------------------------------------------------------------------


class TestHowardPackageExports:
    """Howard class must appear in the correct __all__ lists."""

    def test_separation_dunder_all_contains_howard(self) -> None:
        import modular_simulation.unit_processes.separation as sep_pkg

        assert "Howard1970DistillationColumn" in sep_pkg.__all__

    def test_unit_processes_dunder_all_contains_howard(self) -> None:
        import modular_simulation.unit_processes as up_pkg

        assert "Howard1970DistillationColumn" in up_pkg.__all__


# ---------------------------------------------------------------------------
# 3. Sibling coexistence with StagewiseDistillationColumn
# ---------------------------------------------------------------------------


class TestHowardSiblingCoexistence:
    """Howard must be a distinct class from StagewiseDistillationColumn."""

    def test_howard_is_not_stagewise(self) -> None:
        from modular_simulation.unit_processes.separation import (
            Howard1970DistillationColumn,
        )

        assert Howard1970DistillationColumn is not StagewiseDistillationColumn

    def test_stagewise_still_importable_after_howard_addition(self) -> None:
        from modular_simulation.unit_processes.separation import (
            Howard1970DistillationColumn,
            StagewiseDistillationColumn as Stagewise2,
        )

        assert Stagewise2 is StagewiseFromPkg

    def test_stagewise_class_name_unchanged(self) -> None:
        assert StagewiseDistillationColumn.__name__ == "StagewiseDistillationColumn"

    def test_no_shortcut_distillation_in_separation_package(self) -> None:
        import modular_simulation.unit_processes.separation as sep_pkg

        assert not hasattr(sep_pkg, "ShortcutDistillation")


# ---------------------------------------------------------------------------
# 4. Feed/product runtime seam shape
# ---------------------------------------------------------------------------


class TestHowardRuntimeSeam:
    """Howard model must expose feed/product ports compatible with the
    monolithic runtime seam used by the existing stagewise column."""

    @pytest.fixture()
    def howard(self) -> Any:
        from modular_simulation.unit_processes.separation import (
            Howard1970DistillationColumn,
        )

        col = Howard1970DistillationColumn(n_species=3, n_plates=5)
        _attach(col)
        return col

    def test_ports_property_exists(self, howard: Any) -> None:
        assert hasattr(howard, "ports")
        assert hasattr(howard.ports, "inlets")
        assert hasattr(howard.ports, "outlets")

    def test_feed_inlet_port_present(self, howard: Any) -> None:
        assert "feed_1" in howard.ports.inlets

    def test_distillate_and_bottoms_outlet_ports(self, howard: Any) -> None:
        assert "distillate" in howard.ports.outlets
        assert "bottoms" in howard.ports.outlets

    def test_reflux_return_inlet_port(self, howard: Any) -> None:
        assert "reflux_return" in howard.ports.inlets

    def test_apply_inlet_accepts_feed_stream(self, howard: Any) -> None:
        howard.apply_inlet(
            "feed_1",
            StreamData(
                temperature=350.0,
                pressure=101325.0,
                mole_fractions=(0.5, 0.3, 0.2),
                molar_flow_rate=10.0,
            ),
        )

    def test_get_outlet_stream_returns_stream_data(self, howard: Any) -> None:
        result = howard.get_outlet_stream("distillate")
        assert isinstance(result, StreamData)

    def test_get_outlet_stream_bottoms(self, howard: Any) -> None:
        result = howard.get_outlet_stream("bottoms")
        assert isinstance(result, StreamData)

    def test_apply_inlet_rejects_invalid_port(self, howard: Any) -> None:
        with pytest.raises(ValueError, match="Invalid inlet port"):
            howard.apply_inlet(
                "nonexistent",
                StreamData(
                    temperature=300.0,
                    pressure=101325.0,
                    mole_fractions=(0.5, 0.5),
                    molar_flow_rate=1.0,
                ),
            )


# ---------------------------------------------------------------------------
# 5. Equation-fidelity regression fixtures  (GE-H70-1 .. GE-H70-8)
# ---------------------------------------------------------------------------


class TestHowardEquationFidelity:
    """Regression checks against the frozen Howard (1970) governing equations.

    Each test constructs a small synthetic state and verifies that the model's
    internal arithmetic matches the published equation form.  These tests
    should fail until the implementation exists and preserves the correct
    signs, coefficients, and closure structure.
    """

    @pytest.fixture()
    def howard(self) -> Any:
        from modular_simulation.unit_processes.separation import (
            Howard1970DistillationColumn,
        )

        col = Howard1970DistillationColumn(n_species=3, n_plates=3)
        _attach(col)
        return col

    # -- GE-H70-1: General component balance (Howard Eq. 5) ------------------

    def test_ge_h70_1_component_balance_form(self, howard: Any) -> None:
        """R_j * dx/dt = V_{j+1}*(y_{j+1} - x_j) + L_{j-1}*(x_{j-1} - x_j)
        - V_j*(y_j - x_j)  on interior plates."""
        # We set up a minimal 3-plate state and read the RHS to confirm
        # the balance matches the Howard form (signs, ordering, no extra terms).
        # This test expects the class to expose a method or attribute that
        # lets us evaluate the plate-level component balance.
        assert hasattr(howard, "calculate_component_balance_rhs"), (
            "Howard1970DistillationColumn must expose "
            "calculate_component_balance_rhs for equation-fidelity verification"
        )

        n_plates = 3
        n_species = 3
        # Synthetic plate compositions
        x = np.array(
            [
                [0.6, 0.3, 0.1],
                [0.4, 0.35, 0.25],
                [0.2, 0.4, 0.4],
            ]
        )
        # Synthetic equilibrium vapor
        y_star = np.array(
            [
                [0.75, 0.20, 0.05],
                [0.55, 0.28, 0.17],
                [0.30, 0.35, 0.35],
            ]
        )
        # Simple vaporization efficiency (GE-H70-3)
        E_o = y_star * 0.9 / y_star  # uniform 0.9
        y = E_o * y_star  # actual vapor

        V_plus1 = 5.0  # V_{j+1}
        V_j = 5.0
        L_minus1 = 4.0  # L_{j-1}
        R_j = 50.0

        # Howard Eq. 5 for plate j=1 (0-indexed), component i=0
        j = 1
        i = 0
        expected_rhs = (
            V_plus1 * (y[j + 1, i] - x[j, i])
            + L_minus1 * (x[j - 1, i] - x[j, i])
            - V_j * (y[j, i] - x[j, i])
        ) / R_j

        result = howard.calculate_component_balance_rhs(
            plate_index=j,
            component_index=i,
            x_plate=x,
            y_plate=y,
            V_above=V_plus1,
            V_plate=V_j,
            L_below=L_minus1,
            R_plate=R_j,
        )
        assert result == pytest.approx(expected_rhs, rel=1e-10)

    # -- GE-H70-3: Vaporization efficiency (Howard Eq. 7) --------------------

    def test_ge_h70_2_equilibrium_relation(self, howard: Any) -> None:
        """y*_{j,i} = K_i(T_j, P_j) * x_{j,i}."""
        equilibrium = _require_callable(
            howard,
            "compute_equilibrium_vapor",
            "calculate_equilibrium_vapor",
        )

        K = np.array([2.5, 1.0, 0.4])
        x = np.array([0.25, 0.35, 0.40])
        expected = K * x

        result = equilibrium(K, x)
        np.testing.assert_allclose(result, expected, rtol=1e-12)

    def test_ge_h70_3_vaporization_efficiency(self, howard: Any) -> None:
        """E^o_{j,i} = y_{j,i} / y^*_{j,i}."""
        y = np.array([0.45, 0.35, 0.20])
        y_star = np.array([0.50, 0.30, 0.20])
        expected = y / y_star

        result = _require_callable(
            howard,
            "compute_vaporization_efficiency",
            "calculate_vaporization_efficiency",
        )(y, y_star)
        np.testing.assert_allclose(result, expected, rtol=1e-12)

    # -- GE-H70-4: Murphree efficiency (Howard Eq. 8) ------------------------

    def test_ge_h70_4_murphree_efficiency(self, howard: Any) -> None:
        """E^M_{j,i} = (y_{j,i} - y_{j-1,i}) / (y^*_{j,i} - y_{j-1,i})."""
        y_j = np.array([0.45, 0.35, 0.20])
        y_j_minus1 = np.array([0.30, 0.40, 0.30])
        y_star_j = np.array([0.50, 0.30, 0.20])
        expected = (y_j - y_j_minus1) / (y_star_j - y_j_minus1)

        result = _require_callable(
            howard,
            "compute_murphree_efficiency",
            "calculate_murphree_efficiency",
        )(y_j, y_j_minus1, y_star_j)
        np.testing.assert_allclose(result, expected, rtol=1e-12)

    # -- GE-H70-5: Liquid enthalpy and energy-balance family -----------------

    def test_ge_h70_5_liquid_enthalpy_relation(self, howard: Any) -> None:
        """h_j = sum_i x_{j,i} * f_i(T_j) + phi_M(x_j)."""
        liquid_enthalpy = _require_callable(
            howard,
            "compute_liquid_enthalpy",
            "calculate_liquid_enthalpy",
        )

        x = np.array([0.30, 0.45, 0.25])
        ideal_component_enthalpies = np.array([12000.0, 21000.0, 17000.0])
        phi_m = 135.0
        expected = float(np.dot(x, ideal_component_enthalpies) + phi_m)

        result = liquid_enthalpy(x, ideal_component_enthalpies, phi_m)
        assert result == pytest.approx(expected, rel=1e-12)

    def test_ge_h70_5_energy_balance_residual(self, howard: Any) -> None:
        """Howard Eq. 14 algebraic energy-balance residual stays explicit."""
        energy_balance = _require_callable(
            howard,
            "compute_energy_balance_residual",
            "calculate_energy_balance_residual",
        )

        V_above = 5.0
        H_above = 42000.0
        h_plate = 26000.0
        A_j = 300.0
        L_below = 4.5
        h_below = 25000.0
        B_j = -150.0
        V_plate = 5.3
        H_plate = 41000.0
        C_j = 100.0
        Q_Lj = 1200.0

        expected = (
            V_above * ((H_above - h_plate) - A_j)
            + L_below * ((h_below - h_plate) - B_j)
            - V_plate * ((H_plate - h_plate) - C_j)
            - Q_Lj
        )

        result = energy_balance(
            V_above=V_above,
            H_above=H_above,
            h_plate=h_plate,
            A_j=A_j,
            L_below=L_below,
            h_below=h_below,
            B_j=B_j,
            V_plate=V_plate,
            H_plate=H_plate,
            C_j=C_j,
            Q_Lj=Q_Lj,
        )
        assert result == pytest.approx(expected, rel=1e-12)

    # -- GE-H70-6: Bubble-point closure (Howard Eqs. 15-16) ------------------

    def test_ge_h70_6_bubble_point_residual(self, howard: Any) -> None:
        """sum_i K_i(T_j) * x_{j,i} should equal 1 at the bubble point."""
        # Synthetic: ideal K-values and a composition that does NOT sum to 1
        K = np.array([2.5, 1.0, 0.4])
        x = np.array([0.25, 0.35, 0.40])
        residual = float(np.dot(K, x)) - 1.0  # = 0.335

        result = _require_callable(
            howard,
            "bubble_point_residual",
            "compute_bubble_point_residual",
        )(K, x)
        assert result == pytest.approx(residual, rel=1e-12)

    def test_ge_h70_6_temperature_derivative_family(self, howard: Any) -> None:
        """dT_j/dx_{j,i} = -(dZ/dx_{j,i}) / (dZ/dT_j)."""
        temperature_derivative = _require_callable(
            howard,
            "compute_bubble_point_temperature_derivative",
            "compute_temperature_composition_derivative",
        )

        K = np.array([2.10, 1.35, 0.80])
        dK_dT = np.array([0.020, 0.012, 0.006])
        x = np.array([0.25, 0.35, 0.40])
        reference_index = 2
        component_index = 0

        dZ_dx = K[component_index] - K[reference_index]
        dZ_dT = (
            (dK_dT[0] - dK_dT[reference_index]) * x[0]
            + (dK_dT[1] - dK_dT[reference_index]) * x[1]
            + dK_dT[reference_index]
        )
        expected = -(dZ_dx / dZ_dT)

        result = temperature_derivative(
            K_values=K,
            dK_dT=dK_dT,
            x_independent=x[:2],
            component_index=component_index,
            reference_component_index=reference_index,
        )
        assert result == pytest.approx(expected, rel=1e-12)

    # -- GE-H70-7: Feed-plate extension (Howard Eqs. 22-25) ------------------

    def test_ge_h70_7_feed_plate_component_balance(self, howard: Any) -> None:
        """Feed plate: extra +F*(x_F,i - x_j,i) term vs ordinary plate."""
        calculate_feed_plate_balance_rhs = _require_callable(
            howard,
            "calculate_feed_plate_balance_rhs",
            "compute_feed_plate_balance_rhs",
        )

        n_species = 3
        x_plate = np.array([0.3, 0.4, 0.3])
        y_plate = np.array([0.5, 0.3, 0.2])
        x_above = np.array([0.4, 0.35, 0.25])
        y_below = np.array([0.2, 0.4, 0.4])
        x_F = np.array([0.5, 0.3, 0.2])

        V_above = 5.0
        V_plate = 5.0
        L_below = 4.0
        F = 2.0
        R_j = 50.0

        for i in range(n_species):
            expected = (
                V_above * (y_below[i] - x_plate[i])
                + L_below * (x_above[i] - x_plate[i])
                + F * (x_F[i] - x_plate[i])
                - V_plate * (y_plate[i] - x_plate[i])
            ) / R_j

            result = calculate_feed_plate_balance_rhs(
                plate_index=1,
                component_index=i,
                x_plate=x_plate,
                y_plate=y_plate,
                x_above=x_above,
                y_below=y_below,
                x_feed=x_F,
                V_above=V_above,
                V_plate=V_plate,
                L_below=L_below,
                F_feed=F,
                R_plate=R_j,
            )
            assert result == pytest.approx(expected, rel=1e-10)

    # -- GE-H70-7 continued: total holdup on feed plate (Howard Eq. 25) ------

    def test_ge_h70_7_feed_plate_total_holdup_rate(self, howard: Any) -> None:
        """dR_j/dt = V_{j+1} + L_{j-1} + F - V_j - L_j  (Howard Eq. 25)."""
        calculate_feed_plate_holdup_rate = _require_callable(
            howard,
            "calculate_feed_plate_holdup_rate",
            "compute_feed_plate_holdup_rate",
        )

        V_above = 5.0
        V_plate = 5.0
        L_below = 4.0
        L_plate = 4.5
        F = 2.0
        expected = V_above + L_below + F - V_plate - L_plate

        result = calculate_feed_plate_holdup_rate(
            V_above=V_above,
            V_plate=V_plate,
            L_below=L_below,
            L_plate=L_plate,
            F_feed=F,
        )
        assert result == pytest.approx(expected, rel=1e-10)

    # -- GE-H70-8: Constant-volume-holdup closure (Howard Eqs. 26-30) --------

    def test_ge_h70_8_molar_volume_is_composition_weighted(self, howard: Any) -> None:
        """v(x_j, T_j) = sum_i x_{j,i} * v_i(T_j)  (Howard Eq. 27)."""
        compute_molar_volume = _require_callable(
            howard,
            "compute_molar_volume",
            "calculate_molar_volume",
        )

        x = np.array([0.3, 0.5, 0.2])
        v_pure = np.array([0.08, 0.10, 0.12])  # m^3/mol
        expected = float(np.dot(x, v_pure))

        result = compute_molar_volume(x, v_pure)
        assert result == pytest.approx(expected, rel=1e-12)

    def test_ge_h70_8_temperature_dependent_pure_component_molar_volumes(self, howard: Any) -> None:
        """v_i(T_j) is explicit and temperature dependent."""
        compute_vi_at_temperature = _require_callable(
            howard,
            "compute_temperature_dependent_molar_volumes",
        )

        v_ref = np.array([0.080, 0.100, 0.120])
        dv_dT = np.array([1.0e-4, 1.5e-4, 2.0e-4])
        temperature = 338.15
        expected = v_ref + dv_dT * (temperature - 298.15)

        result = compute_vi_at_temperature(
            reference_molar_volumes=v_ref,
            temperature_coefficients=dv_dT,
            temperature_K=temperature,
        )
        np.testing.assert_allclose(result, expected, rtol=1e-12)

    def test_ge_h70_8_holdup_from_constant_volume(self, howard: Any) -> None:
        """R_j = V_bar * v(x_j, T_j)  (Howard Eq. 26)."""
        compute_holdup_from_volume = _require_callable(
            howard,
            "compute_holdup_from_volume",
            "calculate_holdup_from_volume",
        )

        V_bar = 0.5  # m^3
        v_mix = 0.095  # m^3/mol
        expected = V_bar * v_mix

        result = compute_holdup_from_volume(V_bar, v_mix)
        assert result == pytest.approx(expected, rel=1e-12)

    # -- GE-H70-8 continued: liquid flow constraint (Howard Eq. 29) ----------

    def test_ge_h70_8_eq28_rearranged_liquid_flow(self, howard: Any) -> None:
        """L_j = V_{j+1}+L_{j-1}+F_j^feed-V_j+Vbar*(dv/dt) from Eq. (28)."""
        solve_liquid_flow = _require_callable(
            howard,
            "compute_liquid_flow_from_eq28",
        )
        V_above = 5.3
        V_plate = 5.0
        L_below = 4.2
        V_bar = 0.08
        dvdt = 0.45
        feed_term = 1.1
        expected = V_above + L_below + feed_term - V_plate + V_bar * dvdt

        result = solve_liquid_flow(
            V_above=V_above,
            V_plate=V_plate,
            L_below=L_below,
            V_bar=V_bar,
            dvdt=dvdt,
            feed_flow=feed_term,
        )
        assert result == pytest.approx(expected, rel=1e-12)

    def test_ge_h70_8_eq29_coefficients_are_deterministic_from_eq28(self, howard: Any) -> None:
        derive_coefficients = _require_callable(
            howard,
            "compute_eq29_coefficients_from_eq28",
            "compute_eq30_coefficients",
        )
        R_j = 10.0
        V_bar = 0.08
        v_i = np.array([0.08, 0.10, 0.12])
        x_j = np.array([0.30, 0.40, 0.30])
        x_j_minus_1 = np.array([0.35, 0.40, 0.25])
        y_j = np.array([0.46, 0.34, 0.20])
        y_j_plus_1 = np.array([0.42, 0.36, 0.22])

        prefactor = V_bar / R_j
        expected_f = -prefactor * float(np.dot(v_i, y_j_plus_1 - x_j))
        expected_g = -prefactor * float(np.dot(v_i, x_j_minus_1 - x_j))
        expected_k = -prefactor * float(np.dot(v_i, y_j - x_j))

        f_j, g_j, k_j = derive_coefficients(
            R_plate=R_j,
            V_bar=V_bar,
            pure_component_molar_volumes=v_i,
            x_j=x_j,
            x_j_minus_1=x_j_minus_1,
            y_j=y_j,
            y_j_plus_1=y_j_plus_1,
        )
        assert f_j == pytest.approx(expected_f, rel=1e-12)
        assert g_j == pytest.approx(expected_g, rel=1e-12)
        assert k_j == pytest.approx(expected_k, rel=1e-12)


class TestHowardRuntimeRealism:
    """Regression checks for executable first-slice Howard runtime behavior."""

    @pytest.fixture()
    def howard(self) -> Any:
        from modular_simulation.unit_processes.separation import Howard1970DistillationColumn

        col = Howard1970DistillationColumn(n_species=3, n_plates=4)
        _attach(col)
        return col

    def test_differential_rhs_is_nontrivial_under_feed(self, howard: Any) -> None:
        howard.apply_inlet(
            "feed_1",
            StreamData(
                temperature=360.0,
                pressure=101325.0,
                mole_fractions=(0.50, 0.30, 0.20),
                molar_flow_rate=12.0,
            ),
        )
        howard.apply_inlet(
            "reflux_return",
            StreamData(
                temperature=320.0,
                pressure=101325.0,
                mole_fractions=(0.70, 0.20, 0.10),
                molar_flow_rate=2.0,
            ),
        )
        howard.apply_requested_outlet_through_flow_demand("distillate", 5.0)
        howard.apply_requested_outlet_through_flow_demand("bottoms", 4.0)

        y = howard.differential_view.to_array()
        u = howard.boundary_view.to_array()
        k = howard.constant_view.to_array()
        algebraic = howard.calculate_algebraic_values(
            y=y,
            u=u,
            k=k,
            y_map=howard.differential_view.index_map,
            u_map=howard.boundary_view.index_map,
            k_map=howard.constant_view.index_map,
            algebraic_map=howard.algebraic_view.index_map,
            algebraic_size=howard.algebraic_view.array_size,
        )
        rhs = howard.differential_rhs(
            0.0,
            y,
            u,
            k,
            algebraic,
            howard.differential_view.index_map,
            howard.boundary_view.index_map,
            howard.constant_view.index_map,
            howard.algebraic_view.index_map,
        )

        assert np.any(np.abs(rhs) > 1.0e-9)

    def test_outlet_flows_are_inventory_limited_not_direct_mirror(self, howard: Any) -> None:
        howard.reflux_drum_component_moles[:] = 0.01
        howard.plate_component_holdup.reshape(howard.n_plates, howard.n_species)[-1, :] = 0.01

        howard.apply_requested_outlet_through_flow_demand("distillate", 50.0)
        howard.apply_requested_outlet_through_flow_demand("bottoms", 60.0)

        howard.algebraic_view.update_from_array(
            howard.calculate_algebraic_values(
                y=howard.differential_view.to_array(),
                u=howard.boundary_view.to_array(),
                k=howard.constant_view.to_array(),
                y_map=howard.differential_view.index_map,
                u_map=howard.boundary_view.index_map,
                k_map=howard.constant_view.index_map,
                algebraic_map=howard.algebraic_view.index_map,
                algebraic_size=howard.algebraic_view.array_size,
            )
        )

        assert 0.0 <= howard.distillate_flow < 50.0
        assert 0.0 <= howard.bottoms_flow < 60.0

    def test_product_temperatures_come_from_runtime_plate_state(self, howard: Any) -> None:
        plate_temperatures = np.array([325.0, 335.0, 350.0, 366.0])
        howard.plate_temperature_K = plate_temperatures.copy()

        howard.algebraic_view.update_from_array(
            howard.calculate_algebraic_values(
                y=howard.differential_view.to_array(),
                u=howard.boundary_view.to_array(),
                k=howard.constant_view.to_array(),
                y_map=howard.differential_view.index_map,
                u_map=howard.boundary_view.index_map,
                k_map=howard.constant_view.index_map,
                algebraic_map=howard.algebraic_view.index_map,
                algebraic_size=howard.algebraic_view.array_size,
            )
        )

        assert howard.distillate_temperature == pytest.approx(plate_temperatures[0])
        assert howard.bottoms_temperature == pytest.approx(plate_temperatures[-1])

    def test_runtime_surface_exposes_per_plate_flow_enthalpy_and_closures(
        self, howard: Any
    ) -> None:
        required_algebraic_states = {
            "plate_vapor_flow_mol_s",
            "plate_liquid_flow_mol_s",
            "plate_liquid_enthalpy_j_per_mol",
            "plate_vapor_enthalpy_j_per_mol",
            "plate_bubble_point_residual",
            "plate_flow_closure_residual",
            "plate_molar_volume_time_derivative_m3_per_mol_s",
            "plate_F_coefficient",
            "plate_G_coefficient",
            "plate_K_coefficient",
        }
        state_names = set(howard.algebraic_view.state_list)
        assert required_algebraic_states.issubset(state_names)

    def test_runtime_k_values_change_with_column_pressure(self, howard: Any) -> None:
        y = howard.differential_view.to_array()
        u = howard.boundary_view.to_array()
        k = howard.constant_view.to_array()
        y_map = howard.differential_view.index_map

        low_pressure_y = y.copy()
        high_pressure_y = y.copy()
        low_pressure_y[y_map["column_pressure_pa"]] = 8.5e4
        high_pressure_y[y_map["column_pressure_pa"]] = 1.6e5

        algebraic_low_p = howard.calculate_algebraic_values(
            y=low_pressure_y,
            u=u,
            k=k,
            y_map=y_map,
            u_map=howard.boundary_view.index_map,
            k_map=howard.constant_view.index_map,
            algebraic_map=howard.algebraic_view.index_map,
            algebraic_size=howard.algebraic_view.array_size,
        )
        algebraic_high_p = howard.calculate_algebraic_values(
            y=high_pressure_y,
            u=u,
            k=k,
            y_map=y_map,
            u_map=howard.boundary_view.index_map,
            k_map=howard.constant_view.index_map,
            algebraic_map=howard.algebraic_view.index_map,
            algebraic_size=howard.algebraic_view.array_size,
        )

        k_low = np.asarray(
            algebraic_low_p[howard.algebraic_view.index_map["plate_K_values"]], dtype=np.float64
        )
        k_high = np.asarray(
            algebraic_high_p[howard.algebraic_view.index_map["plate_K_values"]], dtype=np.float64
        )
        assert np.any(np.abs(k_low - k_high) > 1.0e-8)

    def test_temperature_rhs_uses_energy_balance_residual_family(self, howard: Any) -> None:
        howard.apply_inlet(
            "feed_1",
            StreamData(
                temperature=395.0,
                pressure=101325.0,
                mole_fractions=(0.70, 0.20, 0.10),
                molar_flow_rate=18.0,
            ),
        )

        y = howard.differential_view.to_array()
        u = howard.boundary_view.to_array()
        k = howard.constant_view.to_array()
        algebraic = howard.calculate_algebraic_values(
            y=y,
            u=u,
            k=k,
            y_map=howard.differential_view.index_map,
            u_map=howard.boundary_view.index_map,
            k_map=howard.constant_view.index_map,
            algebraic_map=howard.algebraic_view.index_map,
            algebraic_size=howard.algebraic_view.array_size,
        )
        rhs = howard.differential_rhs(
            0.0,
            y,
            u,
            k,
            algebraic,
            howard.differential_view.index_map,
            howard.boundary_view.index_map,
            howard.constant_view.index_map,
            howard.algebraic_view.index_map,
        )

        energy_residual = np.asarray(
            algebraic[howard.algebraic_view.index_map["plate_energy_balance_residual_j_per_s"]],
            dtype=np.float64,
        )
        d_temperature = np.asarray(
            rhs[howard.differential_view.index_map["plate_temperature_K"]],
            dtype=np.float64,
        )
        assert np.any(np.abs(energy_residual) > 1.0e-7)
        assert np.any(np.abs(d_temperature) > 1.0e-9)
        assert np.any(np.sign(d_temperature) == np.sign(energy_residual))

    def test_runtime_vapor_closure_uses_murphree_plate_coupling(self, howard: Any) -> None:
        y_map = howard.differential_view.index_map
        base_y = howard.differential_view.to_array()
        u = howard.boundary_view.to_array()
        k = howard.constant_view.to_array()

        algebraic_base = howard.calculate_algebraic_values(
            y=base_y,
            u=u,
            k=k,
            y_map=y_map,
            u_map=howard.boundary_view.index_map,
            k_map=howard.constant_view.index_map,
            algebraic_map=howard.algebraic_view.index_map,
            algebraic_size=howard.algebraic_view.array_size,
        )
        vapor_base = np.asarray(
            algebraic_base[howard.algebraic_view.index_map["plate_vapor_composition"]],
            dtype=np.float64,
        ).reshape(howard.n_plates, howard.n_species)

        perturbed_y = base_y.copy()
        holdup = np.asarray(perturbed_y[y_map["plate_component_holdup"]], dtype=np.float64).reshape(
            howard.n_plates, howard.n_species
        )
        holdup[0] = np.array([18.0, 1.0, 1.0])

        algebraic_perturbed = howard.calculate_algebraic_values(
            y=perturbed_y,
            u=u,
            k=k,
            y_map=y_map,
            u_map=howard.boundary_view.index_map,
            k_map=howard.constant_view.index_map,
            algebraic_map=howard.algebraic_view.index_map,
            algebraic_size=howard.algebraic_view.array_size,
        )
        vapor_perturbed = np.asarray(
            algebraic_perturbed[howard.algebraic_view.index_map["plate_vapor_composition"]],
            dtype=np.float64,
        ).reshape(howard.n_plates, howard.n_species)

        assert np.linalg.norm(vapor_perturbed[1] - vapor_base[1], ord=1) > 1.0e-6

    def test_runtime_liquid_flow_uses_eq28_derivative_balance(self, howard: Any) -> None:
        algebraic = howard.calculate_algebraic_values(
            y=howard.differential_view.to_array(),
            u=howard.boundary_view.to_array(),
            k=howard.constant_view.to_array(),
            y_map=howard.differential_view.index_map,
            u_map=howard.boundary_view.index_map,
            k_map=howard.constant_view.index_map,
            algebraic_map=howard.algebraic_view.index_map,
            algebraic_size=howard.algebraic_view.array_size,
        )
        amap = howard.algebraic_view.index_map
        vapor_flow = np.asarray(algebraic[amap["plate_vapor_flow_mol_s"]], dtype=np.float64)
        liquid_flow = np.asarray(algebraic[amap["plate_liquid_flow_mol_s"]], dtype=np.float64)
        dvdt = np.asarray(
            algebraic[amap["plate_molar_volume_time_derivative_m3_per_mol_s"]],
            dtype=np.float64,
        )
        v_bar = float(howard.plate_reference_volume_m3)
        reflux_to_column = float(algebraic[amap["reflux_to_column_flow_mol_s"]])

        for j in range(howard.n_plates):
            v_above = (
                float(vapor_flow[j + 1]) if j < (howard.n_plates - 1) else float(vapor_flow[j])
            )
            v_plate = float(vapor_flow[j])
            l_below = reflux_to_column if j == 0 else float(liquid_flow[j - 1])
            feed_term = float(howard.feed_1_flow) if j == int(howard.feed_plate_index) else 0.0
            expected_lj = max(
                0.0,
                float(
                    howard.compute_liquid_flow_from_eq28(
                        V_above=v_above,
                        V_plate=v_plate,
                        L_below=l_below,
                        V_bar=v_bar,
                        dvdt=float(dvdt[j]),
                        feed_flow=feed_term,
                    )
                ),
            )
            assert liquid_flow[j] == pytest.approx(expected_lj, rel=1.0e-10, abs=1.0e-10)

    def test_runtime_eq29_residual_matches_flow_constraint_expression(self, howard: Any) -> None:
        """The F/G/K coefficients from Eq. (29) closure must be deterministically
        derived from the full Eq. (28) dynamics so that the standard Eq. (29)
        constraint expression is exact under temperature-dependent molar-volume
        dynamics.

        The normative path computes L_j from the full Eq. (28) including both
        composition and temperature dv/dt contributions.  The exposed F/G/K
        coefficients must capture that full path so that:
          L_j = V_above*(1-F_j) + L_below*(1-G_j) - V_plate*(1-K_j)
        holds exactly for non-feed plates.
        """
        algebraic = howard.calculate_algebraic_values(
            y=howard.differential_view.to_array(),
            u=howard.boundary_view.to_array(),
            k=howard.constant_view.to_array(),
            y_map=howard.differential_view.index_map,
            u_map=howard.boundary_view.index_map,
            k_map=howard.constant_view.index_map,
            algebraic_map=howard.algebraic_view.index_map,
            algebraic_size=howard.algebraic_view.array_size,
        )
        amap = howard.algebraic_view.index_map
        vapor_flow = np.asarray(algebraic[amap["plate_vapor_flow_mol_s"]], dtype=np.float64)
        liquid_flow = np.asarray(algebraic[amap["plate_liquid_flow_mol_s"]], dtype=np.float64)
        plate_f = np.asarray(algebraic[amap["plate_F_coefficient"]], dtype=np.float64)
        plate_g = np.asarray(algebraic[amap["plate_G_coefficient"]], dtype=np.float64)
        plate_k = np.asarray(algebraic[amap["plate_K_coefficient"]], dtype=np.float64)
        closure = np.asarray(algebraic[amap["plate_flow_closure_residual"]], dtype=np.float64)
        reflux_to_column = float(algebraic[amap["reflux_to_column_flow_mol_s"]])

        for j in range(howard.n_plates):
            v_above = (
                float(vapor_flow[j + 1]) if j < (howard.n_plates - 1) else float(vapor_flow[j])
            )
            v_plate = float(vapor_flow[j])
            l_below = reflux_to_column if j == 0 else float(liquid_flow[j - 1])

            # The flow closure residual from Eq. (28) should be essentially zero
            # because L_j was computed directly from the full Eq. (28) including
            # both composition and temperature contributions to dv/dt.
            assert closure[j] == pytest.approx(0.0, abs=1.0e-10)

            # The F/G/K coefficients are deterministically derived from the full
            # Eq. (28) dynamics, so the Eq. (29) constraint must be exact:
            #   L_j = V_above*(1-F_j) + L_below*(1-G_j) - V_plate*(1-K_j)
            # for non-feed plates.  For feed plates the constraint omits the
            # feed term, so we verify the gap equals F_feed instead.
            constraint_Lj = howard.compute_liquid_flow_constraint(
                V_above=v_above,
                V_plate=v_plate,
                L_below=l_below,
                F_j=float(plate_f[j]),
                G_j=float(plate_g[j]),
                K_j=float(plate_k[j]),
            )
            if j != int(howard.feed_plate_index):
                assert constraint_Lj == pytest.approx(
                    float(liquid_flow[j]), rel=1.0e-8, abs=1.0e-12
                ), (
                    f"Plate {j}: Eq. (29) constraint {constraint_Lj:.8e} "
                    f"!= L_j {float(liquid_flow[j]):.8e}"
                )
            else:
                # Feed plates have an additional F*(1-H_j) term in the full
                # Eq. (29) that the three-coefficient constraint omits.
                feed_gap = float(liquid_flow[j]) - constraint_Lj
                assert feed_gap == pytest.approx(
                    float(howard.feed_1_flow), rel=1.0e-8, abs=1.0e-12
                ), (
                    f"Feed plate {j}: gap {feed_gap:.8e} "
                    f"!= feed flow {float(howard.feed_1_flow):.8e}"
                )

    def test_runtime_dvdt_changes_with_plate_temperature_dependent_molar_volumes(
        self, howard: Any
    ) -> None:
        howard.equilibrium_temperature_sensitivity_per_K = np.zeros(
            howard.n_species, dtype=np.float64
        )
        howard.component_molar_volume_temperature_coefficient_m3_per_mol_K = np.array(
            [1.0e-4, 1.7e-4, 2.4e-4],
            dtype=np.float64,
        )
        howard.apply_inlet(
            "feed_1",
            StreamData(
                temperature=360.0,
                pressure=101325.0,
                mole_fractions=(0.55, 0.30, 0.15),
                molar_flow_rate=9.5,
            ),
        )

        y_base = howard.differential_view.to_array()
        y_warm = y_base.copy()
        t_index = howard.differential_view.index_map["plate_temperature_K"]
        y_warm[t_index] = np.asarray(y_base[t_index], dtype=np.float64) + 30.0

        common_kwargs = {
            "u": howard.boundary_view.to_array(),
            "k": howard.constant_view.to_array(),
            "y_map": howard.differential_view.index_map,
            "u_map": howard.boundary_view.index_map,
            "k_map": howard.constant_view.index_map,
            "algebraic_map": howard.algebraic_view.index_map,
            "algebraic_size": howard.algebraic_view.array_size,
        }
        algebraic_base = howard.calculate_algebraic_values(y=y_base, **common_kwargs)
        algebraic_warm = howard.calculate_algebraic_values(y=y_warm, **common_kwargs)

        dvdt_base = np.asarray(
            algebraic_base[
                howard.algebraic_view.index_map["plate_molar_volume_time_derivative_m3_per_mol_s"]
            ],
            dtype=np.float64,
        )
        dvdt_warm = np.asarray(
            algebraic_warm[
                howard.algebraic_view.index_map["plate_molar_volume_time_derivative_m3_per_mol_s"]
            ],
            dtype=np.float64,
        )
        assert np.any(np.abs(dvdt_warm - dvdt_base) > 1.0e-9)

    def test_runtime_dvdt_includes_explicit_temperature_derivative_term(self, howard: Any) -> None:
        """Eq. (28) dv/dt must include sum_i x_i (dv_i/dT) dT/dt, not just composition terms.

        We set up a model with large molar-volume temperature coefficients and a strong
        energy imbalance (hot feed).  We then compute dv/dt from the algebraic closure
        and also compute the composition-only contribution manually.  The difference
        must be non-zero, proving the temperature term is wired in.
        """
        from modular_simulation.unit_processes.separation import Howard1970DistillationColumn

        n_sp = howard.n_species
        n_pl = howard.n_plates

        # Large temperature coefficients so the temperature term is visible.
        howard.component_molar_volume_temperature_coefficient_m3_per_mol_K = np.array(
            [5.0e-3, 7.0e-3, 9.0e-3], dtype=np.float64
        )
        # Turn off equilibrium temperature sensitivity to isolate the molar-volume effect.
        howard.equilibrium_temperature_sensitivity_per_K = np.zeros(n_sp, dtype=np.float64)

        # Hot feed to create a strong thermal drive on the feed plate.
        howard.feed_plate_index = 1
        howard.apply_inlet(
            "feed_1",
            StreamData(
                temperature=400.0,
                pressure=101325.0,
                mole_fractions=(0.50, 0.30, 0.20),
                molar_flow_rate=15.0,
            ),
        )
        howard.apply_inlet(
            "reflux_return",
            StreamData(
                temperature=310.0,
                pressure=101325.0,
                mole_fractions=(0.70, 0.20, 0.10),
                molar_flow_rate=3.0,
            ),
        )
        howard.apply_requested_outlet_through_flow_demand("distillate", 5.0)
        howard.apply_requested_outlet_through_flow_demand("bottoms", 4.0)

        y = howard.differential_view.to_array()
        u = howard.boundary_view.to_array()
        k = howard.constant_view.to_array()
        kwargs = {
            "y": y,
            "u": u,
            "k": k,
            "y_map": howard.differential_view.index_map,
            "u_map": howard.boundary_view.index_map,
            "k_map": howard.constant_view.index_map,
            "algebraic_map": howard.algebraic_view.index_map,
            "algebraic_size": howard.algebraic_view.array_size,
        }
        algebraic = Howard1970DistillationColumn.calculate_algebraic_values(**kwargs)

        # Extract runtime dv/dt.
        amap = howard.algebraic_view.index_map
        dvdt_runtime = np.asarray(
            algebraic[amap["plate_molar_volume_time_derivative_m3_per_mol_s"]],
            dtype=np.float64,
        )

        # Manually compute composition-only dv/dt for each plate.
        ymap = howard.differential_view.index_map
        kmap = howard.constant_view.index_map
        plate_holdup = np.asarray(y[ymap["plate_component_holdup"]], dtype=np.float64).reshape(
            n_pl, n_sp
        )
        plate_temperature = np.asarray(y[ymap["plate_temperature_K"]], dtype=np.float64).reshape(-1)
        reference_molar_volumes = np.asarray(
            k[kmap["reference_molar_volumes_m3_per_mol"]], dtype=np.float64
        ).reshape(-1)
        molar_vol_temp_coeff = np.asarray(
            k[kmap["component_molar_volume_temperature_coefficient_m3_per_mol_K"]],
            dtype=np.float64,
        ).reshape(-1)

        vapor_flow_alg = np.asarray(
            algebraic[amap["plate_vapor_flow_mol_s"]], dtype=np.float64
        ).reshape(-1)
        liquid_flow_alg = np.asarray(
            algebraic[amap["plate_liquid_flow_mol_s"]], dtype=np.float64
        ).reshape(-1)
        plate_y_alg = np.asarray(
            algebraic[amap["plate_vapor_composition"]], dtype=np.float64
        ).reshape(n_pl, n_sp)
        reflux_to_col = float(algebraic[amap["reflux_to_column_flow_mol_s"]])

        distillate_x = np.zeros(n_sp, dtype=np.float64)
        drum_moles_arr = np.asarray(y[ymap["reflux_drum_component_moles"]], dtype=np.float64)
        s = float(np.sum(np.maximum(drum_moles_arr, 0.0)))
        if s > 1.0e-15:
            distillate_x = np.maximum(drum_moles_arr, 0.0) / s

        x_plate = np.vstack(
            [
                np.maximum(plate_holdup[j], 0.0)
                / max(1.0e-15, float(np.sum(np.maximum(plate_holdup[j], 0.0))))
                for j in range(n_pl)
            ]
        )

        feed_flow = float(u[howard.boundary_view.index_map["feed_1_flow"]])
        feed_comp = np.asarray(
            u[howard.boundary_view.index_map["feed_1_composition"]], dtype=np.float64
        ).reshape(-1)
        s_f = float(np.sum(np.maximum(feed_comp, 0.0)))
        if s_f > 1.0e-15:
            feed_comp = np.maximum(feed_comp, 0.0) / s_f

        dvdt_composition_only = np.zeros(n_pl, dtype=np.float64)
        for j in range(n_pl):
            V_above = vapor_flow_alg[j + 1] if j < (n_pl - 1) else vapor_flow_alg[j]
            V_plate = vapor_flow_alg[j]
            L_below = reflux_to_col if j == 0 else liquid_flow_alg[j - 1]
            x_above = x_plate[j - 1] if j > 0 else distillate_x
            y_below = plate_y_alg[j + 1] if j < (n_pl - 1) else plate_y_alg[j]
            R_j = max(1.0e-8, float(np.sum(plate_holdup[j])))

            x_rate = np.zeros(n_sp, dtype=np.float64)
            for i in range(n_sp):
                x_rate[i] = (
                    float(V_above) * (float(y_below[i]) - float(x_plate[j, i]))
                    + float(L_below) * (float(x_above[i]) - float(x_plate[j, i]))
                    - float(V_plate) * (float(plate_y_alg[j, i]) - float(x_plate[j, i]))
                ) / R_j
                if j == int(howard.feed_plate_index):
                    x_rate[i] += (
                        float(feed_flow) * (float(feed_comp[i]) - float(x_plate[j, i])) / R_j
                    )

            v_i = Howard1970DistillationColumn.compute_temperature_dependent_molar_volumes(
                reference_molar_volumes=reference_molar_volumes,
                temperature_coefficients=molar_vol_temp_coeff,
                temperature_K=float(plate_temperature[j]),
            )
            dvdt_composition_only[j] = float(np.dot(v_i, x_rate))

        # If the temperature term is wired in, at least one plate must show
        # a difference between runtime dv/dt and composition-only dv/dt.
        diff = dvdt_runtime - dvdt_composition_only
        assert np.any(np.abs(diff) > 1.0e-10), (
            f"Runtime dv/dt equals composition-only dv/dt on every plate — "
            f"temperature derivative term is not wired in.  diff={diff}"
        )

    def test_runtime_energy_balance_uses_named_closure_terms(self, howard: Any) -> None:
        howard.energy_balance_A_term_j_per_mol = np.array(
            [10.0, 20.0, 30.0, 40.0], dtype=np.float64
        )
        howard.energy_balance_B_term_j_per_mol = np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float64)
        howard.energy_balance_C_term_j_per_mol = np.array([7.0, 8.0, 9.0, 10.0], dtype=np.float64)
        howard.plate_heat_loss_j_per_s = np.array([250.0, 500.0, 750.0, 1000.0], dtype=np.float64)
        howard.feed_energy_closure_D_term_j_per_mol = np.array(
            [0.0, 12.0, 0.0, 0.0], dtype=np.float64
        )
        howard.feed_plate_index = 1
        howard.apply_inlet(
            "feed_1",
            StreamData(
                temperature=390.0,
                pressure=101325.0,
                mole_fractions=(0.60, 0.25, 0.15),
                molar_flow_rate=11.0,
            ),
        )

        algebraic = howard.calculate_algebraic_values(
            y=howard.differential_view.to_array(),
            u=howard.boundary_view.to_array(),
            k=howard.constant_view.to_array(),
            y_map=howard.differential_view.index_map,
            u_map=howard.boundary_view.index_map,
            k_map=howard.constant_view.index_map,
            algebraic_map=howard.algebraic_view.index_map,
            algebraic_size=howard.algebraic_view.array_size,
        )
        amap = howard.algebraic_view.index_map
        liquid_h = np.asarray(algebraic[amap["plate_liquid_enthalpy_j_per_mol"]], dtype=np.float64)
        vapor_h = np.asarray(algebraic[amap["plate_vapor_enthalpy_j_per_mol"]], dtype=np.float64)
        vapor_flow = np.asarray(algebraic[amap["plate_vapor_flow_mol_s"]], dtype=np.float64)
        liquid_flow = np.asarray(algebraic[amap["plate_liquid_flow_mol_s"]], dtype=np.float64)
        energy_residual = np.asarray(
            algebraic[amap["plate_energy_balance_residual_j_per_s"]],
            dtype=np.float64,
        )
        reflux_to_column = float(algebraic[amap["reflux_to_column_flow_mol_s"]])

        cp = np.asarray(howard.component_heat_capacity_j_per_mol_K, dtype=np.float64)
        feed_x = np.asarray(howard.feed_1_composition, dtype=np.float64)
        feed_ideal_h = cp * (float(howard.feed_1_temperature) - 298.15)
        feed_phi = 120.0 * (1.0 - float(np.dot(feed_x, feed_x)))
        feed_h = float(howard.compute_liquid_enthalpy(feed_x, feed_ideal_h, feed_phi))

        for j in range(howard.n_plates):
            v_above = (
                float(vapor_flow[j + 1]) if j < (howard.n_plates - 1) else float(vapor_flow[j])
            )
            l_below = reflux_to_column if j == 0 else float(liquid_flow[j - 1])
            h_below = float(liquid_h[j - 1]) if j > 0 else float(liquid_h[j])
            h_plate = float(liquid_h[j])
            q_lj = float(howard.plate_heat_loss_j_per_s[j])
            if j == int(howard.feed_plate_index) and float(howard.feed_1_flow) > 0.0:
                q_lj -= float(howard.feed_1_flow) * (
                    (feed_h - h_plate) - float(howard.feed_energy_closure_D_term_j_per_mol[j])
                )

            expected = float(
                howard.compute_energy_balance_residual(
                    V_above=v_above,
                    H_above=(
                        float(vapor_h[j + 1]) if j < (howard.n_plates - 1) else float(vapor_h[j])
                    ),
                    h_plate=h_plate,
                    A_j=float(howard.energy_balance_A_term_j_per_mol[j]),
                    L_below=l_below,
                    h_below=h_below,
                    B_j=float(howard.energy_balance_B_term_j_per_mol[j]),
                    V_plate=float(vapor_flow[j]),
                    H_plate=float(vapor_h[j]),
                    C_j=float(howard.energy_balance_C_term_j_per_mol[j]),
                    Q_Lj=q_lj,
                )
            )
            assert energy_residual[j] == pytest.approx(expected, rel=1.0e-10, abs=1.0e-10)

    def test_algebraic_dTdt_matches_rhs_dTdt_including_bubble_drive(self, howard: Any) -> None:
        """The algebraic-pass dT/dt used inside Eq. (28) dv/dt must match the full
        RHS temperature derivative (thermal_drive + bubble_drive +
        feed_energy_drive - 6*bubble_residual), not the surrogate that omits
        bubble_drive.

        We extract the implicit dT/dt from the algebraic dv/dt and compare
        it directly against the RHS d_temperature.
        """
        from modular_simulation.unit_processes.separation import Howard1970DistillationColumn

        n_sp = howard.n_species
        n_pl = howard.n_plates

        # Non-zero dK/dT so bubble_drive is active.
        howard.equilibrium_temperature_sensitivity_per_K = np.array(
            [0.020, 0.012, 0.006], dtype=np.float64
        )
        # Large temperature coefficients so the dT/dt term in dv/dt is extractable.
        howard.component_molar_volume_temperature_coefficient_m3_per_mol_K = np.array(
            [5.0e-3, 7.0e-3, 9.0e-3], dtype=np.float64
        )

        howard.feed_plate_index = 1
        howard.apply_inlet(
            "feed_1",
            StreamData(
                temperature=400.0,
                pressure=101325.0,
                mole_fractions=(0.50, 0.30, 0.20),
                molar_flow_rate=15.0,
            ),
        )
        howard.apply_inlet(
            "reflux_return",
            StreamData(
                temperature=310.0,
                pressure=101325.0,
                mole_fractions=(0.70, 0.20, 0.10),
                molar_flow_rate=3.0,
            ),
        )
        howard.apply_requested_outlet_through_flow_demand("distillate", 5.0)
        howard.apply_requested_outlet_through_flow_demand("bottoms", 4.0)

        y = howard.differential_view.to_array()
        u = howard.boundary_view.to_array()
        k = howard.constant_view.to_array()
        kmap = howard.constant_view.index_map
        ymap = howard.differential_view.index_map
        amap = howard.algebraic_view.index_map
        kwargs_alg = {
            "y": y,
            "u": u,
            "k": k,
            "y_map": ymap,
            "u_map": howard.boundary_view.index_map,
            "k_map": kmap,
            "algebraic_map": amap,
            "algebraic_size": howard.algebraic_view.array_size,
        }
        algebraic = Howard1970DistillationColumn.calculate_algebraic_values(**kwargs_alg)

        rhs = Howard1970DistillationColumn.differential_rhs(
            0.0,
            y,
            u,
            k,
            algebraic,
            ymap,
            howard.boundary_view.index_map,
            kmap,
            amap,
        )

        d_temperature = np.asarray(rhs[ymap["plate_temperature_K"]], dtype=np.float64)
        dvdt_runtime = np.asarray(
            algebraic[amap["plate_molar_volume_time_derivative_m3_per_mol_s"]],
            dtype=np.float64,
        )

        plate_holdup = np.asarray(y[ymap["plate_component_holdup"]], dtype=np.float64).reshape(
            n_pl, n_sp
        )
        plate_temperature = np.asarray(y[ymap["plate_temperature_K"]], dtype=np.float64)
        plate_K_vals = np.asarray(algebraic[amap["plate_K_values"]], dtype=np.float64).reshape(
            n_pl, n_sp
        )
        plate_y_alg = np.asarray(
            algebraic[amap["plate_vapor_composition"]], dtype=np.float64
        ).reshape(n_pl, n_sp)
        vapor_flow_alg = np.asarray(algebraic[amap["plate_vapor_flow_mol_s"]], dtype=np.float64)
        liquid_flow_alg = np.asarray(algebraic[amap["plate_liquid_flow_mol_s"]], dtype=np.float64)
        bubble_residual = np.asarray(
            algebraic[amap["plate_bubble_point_residual"]], dtype=np.float64
        )
        energy_residual = np.asarray(
            algebraic[amap["plate_energy_balance_residual_j_per_s"]], dtype=np.float64
        )
        reflux_to_col = float(algebraic[amap["reflux_to_column_flow_mol_s"]])

        reference_molar_volumes = np.asarray(
            k[kmap["reference_molar_volumes_m3_per_mol"]], dtype=np.float64
        )
        molar_vol_temp_coeff = np.asarray(
            k[kmap["component_molar_volume_temperature_coefficient_m3_per_mol_K"]],
            dtype=np.float64,
        )
        dK_dT = np.asarray(k[kmap["equilibrium_temperature_sensitivity_per_K"]], dtype=np.float64)
        cp = np.asarray(k[kmap["component_heat_capacity_j_per_mol_K"]], dtype=np.float64)

        distillate_x_arr = np.zeros(n_sp, dtype=np.float64)
        drum_moles_arr = np.asarray(y[ymap["reflux_drum_component_moles"]], dtype=np.float64)
        s_drum = float(np.sum(np.maximum(drum_moles_arr, 0.0)))
        if s_drum > 1.0e-15:
            distillate_x_arr = np.maximum(drum_moles_arr, 0.0) / s_drum

        x_plate = np.vstack(
            [
                np.maximum(plate_holdup[j], 0.0)
                / max(1.0e-15, float(np.sum(np.maximum(plate_holdup[j], 0.0))))
                for j in range(n_pl)
            ]
        )

        feed_flow = float(u[howard.boundary_view.index_map["feed_1_flow"]])
        feed_comp = np.asarray(
            u[howard.boundary_view.index_map["feed_1_composition"]], dtype=np.float64
        ).reshape(-1)
        s_f = float(np.sum(np.maximum(feed_comp, 0.0)))
        if s_f > 1.0e-15:
            feed_comp = np.maximum(feed_comp, 0.0) / s_f
        feed_temperature = float(u[howard.boundary_view.index_map["feed_1_temperature"]])

        for j in range(n_pl):
            # Compute the composition-only dv/dt and dvdT_mix for this plate.
            V_above = vapor_flow_alg[j + 1] if j < (n_pl - 1) else vapor_flow_alg[j]
            V_plate = vapor_flow_alg[j]
            L_below = reflux_to_col if j == 0 else liquid_flow_alg[j - 1]
            x_above = x_plate[j - 1] if j > 0 else distillate_x_arr
            y_below = plate_y_alg[j + 1] if j < (n_pl - 1) else plate_y_alg[j]
            R_j = max(1.0e-8, float(np.sum(plate_holdup[j])))

            x_rate = np.zeros(n_sp, dtype=np.float64)
            for i in range(n_sp):
                x_rate[i] = (
                    float(V_above) * (float(y_below[i]) - float(x_plate[j, i]))
                    + float(L_below) * (float(x_above[i]) - float(x_plate[j, i]))
                    - float(V_plate) * (float(plate_y_alg[j, i]) - float(x_plate[j, i]))
                ) / R_j
                if j == int(howard.feed_plate_index):
                    x_rate[i] += (
                        float(feed_flow) * (float(feed_comp[i]) - float(x_plate[j, i])) / R_j
                    )

            v_i = Howard1970DistillationColumn.compute_temperature_dependent_molar_volumes(
                reference_molar_volumes=reference_molar_volumes,
                temperature_coefficients=molar_vol_temp_coeff,
                temperature_K=float(plate_temperature[j]),
            )
            dvdt_composition_only = float(np.dot(v_i, x_rate))
            dvdT_mix = float(np.dot(x_plate[j], molar_vol_temp_coeff))

            # Extract the implicit dT/dt from algebraic dv/dt:
            #   dvdt_runtime = dvdt_composition_only + dvdT_mix * dTdt_implicit
            if abs(dvdT_mix) > 1.0e-14:
                dTdt_algebraic = (float(dvdt_runtime[j]) - dvdt_composition_only) / dvdT_mix
            else:
                # Temperature coefficient is negligible; skip this plate.
                continue

            # The RHS dT/dt must match the algebraic-pass dT/dt.
            assert dTdt_algebraic == pytest.approx(
                float(d_temperature[j]), rel=1.0e-6, abs=1.0e-10
            ), (
                f"Plate {j}: algebraic dT/dt={dTdt_algebraic:.8e} "
                f"!= RHS dT/dt={d_temperature[j]:.8e}"
            )

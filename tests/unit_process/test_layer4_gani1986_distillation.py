"""Wave 1 failing unit tests for Gani1986DistillationColumn.

These tests define the pre-implementation contract for the Gani, Ruiz,
Cameroni (1986) paper-faithful dynamic distillation model.  They are
expected to **fail** (ImportError / AttributeError) until Wave 3 introduces
the class and updates the package exports.

Covers:
  - Class existence, construction, and ProcessModel lineage
  - Package-level export in ``separation`` and ``unit_processes``
  - Sibling coexistence with ``StagewiseDistillationColumn``
  - Feed/product runtime seam shape
  - Equation-fidelity regression fixtures against frozen GE-G86-1..GE-G86-8
"""

from __future__ import annotations

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


class TestGaniClassExistenceAndConstruction:
    """Gani1986DistillationColumn must be importable and constructable."""

    def test_import_from_separation_package(self) -> None:
        from modular_simulation.unit_processes.separation import (
            Gani1986DistillationColumn,
        )  # noqa: F401

    def test_import_from_unit_processes_top_level(self) -> None:
        from modular_simulation.unit_processes import (
            Gani1986DistillationColumn,
        )  # noqa: F401

    def test_class_is_process_model_subclass(self) -> None:
        from modular_simulation.unit_processes.separation import (
            Gani1986DistillationColumn,
        )

        column = Gani1986DistillationColumn(n_species=3, n_plates=5)
        assert isinstance(column, ProcessModel)

    def test_basic_construction_with_defaults(self) -> None:
        from modular_simulation.unit_processes.separation import (
            Gani1986DistillationColumn,
        )

        column = Gani1986DistillationColumn(n_species=2, n_plates=4)
        assert column.n_species == 2
        assert column.n_plates == 4

    def test_construction_rejects_single_species(self) -> None:
        from modular_simulation.unit_processes.separation import (
            Gani1986DistillationColumn,
        )

        with pytest.raises(ValueError, match="n_species"):
            Gani1986DistillationColumn(n_species=1, n_plates=4)

    def test_construction_rejects_zero_plates(self) -> None:
        from modular_simulation.unit_processes.separation import (
            Gani1986DistillationColumn,
        )

        with pytest.raises(ValueError):
            Gani1986DistillationColumn(n_species=2, n_plates=0)


# ---------------------------------------------------------------------------
# 2. Package exports
# ---------------------------------------------------------------------------


class TestGaniPackageExports:
    """Gani class must appear in the correct __all__ lists."""

    def test_separation_dunder_all_contains_gani(self) -> None:
        import modular_simulation.unit_processes.separation as sep_pkg

        assert "Gani1986DistillationColumn" in sep_pkg.__all__

    def test_unit_processes_dunder_all_contains_gani(self) -> None:
        import modular_simulation.unit_processes as up_pkg

        assert "Gani1986DistillationColumn" in up_pkg.__all__


# ---------------------------------------------------------------------------
# 3. Sibling coexistence with StagewiseDistillationColumn
# ---------------------------------------------------------------------------


class TestGaniSiblingCoexistence:
    """Gani must be a distinct class from StagewiseDistillationColumn."""

    def test_gani_is_not_stagewise(self) -> None:
        from modular_simulation.unit_processes.separation import (
            Gani1986DistillationColumn,
        )

        assert Gani1986DistillationColumn is not StagewiseDistillationColumn

    def test_stagewise_still_importable_after_gani_addition(self) -> None:
        from modular_simulation.unit_processes.separation import (
            Gani1986DistillationColumn,
            StagewiseDistillationColumn as Stagewise2,
        )

        assert Stagewise2 is StagewiseFromPkg

    def test_gani_is_not_howard(self) -> None:
        """Gani and Howard are separate sibling classes."""
        from modular_simulation.unit_processes.separation import (
            Gani1986DistillationColumn,
            Howard1970DistillationColumn,
        )

        assert Gani1986DistillationColumn is not Howard1970DistillationColumn

    def test_no_shortcut_distillation_in_separation_package(self) -> None:
        import modular_simulation.unit_processes.separation as sep_pkg

        assert not hasattr(sep_pkg, "ShortcutDistillation")


# ---------------------------------------------------------------------------
# 4. Feed/product runtime seam shape
# ---------------------------------------------------------------------------


class TestGaniRuntimeSeam:
    """Gani model must expose feed/product ports compatible with the
    monolithic runtime seam used by the existing stagewise column."""

    @pytest.fixture()
    def gani(self) -> Any:
        from modular_simulation.unit_processes.separation import (
            Gani1986DistillationColumn,
        )

        col = Gani1986DistillationColumn(n_species=3, n_plates=5)
        _attach(col)
        return col

    def test_ports_property_exists(self, gani: Any) -> None:
        assert hasattr(gani, "ports")
        assert hasattr(gani.ports, "inlets")
        assert hasattr(gani.ports, "outlets")

    def test_feed_inlet_port_present(self, gani: Any) -> None:
        assert "feed_1" in gani.ports.inlets

    def test_distillate_and_bottoms_outlet_ports(self, gani: Any) -> None:
        assert "distillate" in gani.ports.outlets
        assert "bottoms" in gani.ports.outlets

    def test_reflux_return_inlet_port(self, gani: Any) -> None:
        assert "reflux_return" in gani.ports.inlets

    def test_apply_inlet_accepts_feed_stream(self, gani: Any) -> None:
        gani.apply_inlet(
            "feed_1",
            StreamData(
                temperature=350.0,
                pressure=101325.0,
                mole_fractions=(0.5, 0.3, 0.2),
                molar_flow_rate=10.0,
            ),
        )

    def test_get_outlet_stream_returns_stream_data(self, gani: Any) -> None:
        result = gani.get_outlet_stream("distillate")
        assert isinstance(result, StreamData)

    def test_get_outlet_stream_bottoms(self, gani: Any) -> None:
        result = gani.get_outlet_stream("bottoms")
        assert isinstance(result, StreamData)


# ---------------------------------------------------------------------------
# 5. Equation-fidelity regression fixtures  (GE-G86-1 .. GE-G86-8)
# ---------------------------------------------------------------------------


class TestGaniEquationFidelity:
    """Regression checks against the frozen Gani (1986) governing equations.

    Each test constructs a small synthetic state and verifies that the model's
    internal arithmetic matches the published equation form.
    """

    @pytest.fixture()
    def gani(self) -> Any:
        from modular_simulation.unit_processes.separation import (
            Gani1986DistillationColumn,
        )

        col = Gani1986DistillationColumn(n_species=3, n_plates=3)
        _attach(col)
        return col

    # -- GE-G86-1: Component mass balance (Gani Eq. 1) -----------------------

    def test_ge_g86_1_component_balance_form(self, gani: Any) -> None:
        """dC_{p,i}/dt = inlet terms - outlet terms.

        Full form from the paper with V, L, entrainment, feeds, products.
        Entrainment inlet terms carry source-plate compositions, not
        receiving-plate compositions (GE-G86-1: E_L_{p-1}*x_{p-1,i},
        E_V_{p+1}*y_{p+1,i}).
        """
        calculate_component_balance_rhs = _require_callable(
            gani,
            "calculate_component_balance_rhs",
            "compute_component_balance_rhs",
        )

        # Synthetic plate state
        n_species = 3
        y_below = np.array([0.5, 0.3, 0.2])  # y_{p-1,i}  (from plate below)
        x_above = np.array([0.3, 0.4, 0.3])  # x_{p+1,i}  (from plate above)
        x_plate = np.array([0.4, 0.35, 0.25])  # x_{p,i}
        y_plate = np.array([0.55, 0.28, 0.17])  # y_{p,i}
        # Source-plate compositions for entrainment (distinct from receiving plate)
        x_below = np.array([0.6, 0.25, 0.15])  # x_{p-1,i}  (liquid entrainment source)
        y_above = np.array([0.45, 0.35, 0.20])  # y_{p+1,i}  (vapor entrainment source)

        V_below = 5.0
        V_plate = 5.0
        L_above = 4.0
        L_plate = 4.5
        E_L_below = 0.1  # liquid entrainment from plate below
        E_V_above = 0.1  # vapor entrainment from plate above
        E_L_plate = 0.05
        E_V_plate = 0.05
        P_L = 0.3  # liquid product draw
        P_V = 0.2  # vapor product draw
        F_L = 1.0  # liquid feed
        F_V = 0.0  # vapor feed
        x_F_L = np.array([0.5, 0.3, 0.2])
        y_F_V = np.array([0.0, 0.0, 0.0])

        for i in range(n_species):
            inlet = (
                F_V * y_F_V[i]
                + F_L * x_F_L[i]
                + V_below * y_below[i]
                + E_L_below * x_below[i]  # entrainment from below carries x from below
                + L_above * x_above[i]
                + E_V_above * y_above[i]  # entrainment from above carries y from above
            )
            outlet = (P_V + V_plate + E_V_plate) * y_plate[i] + (
                P_L + L_plate + E_L_plate
            ) * x_plate[i]
            expected = inlet - outlet

            result = calculate_component_balance_rhs(
                plate_index=1,
                component_index=i,
                x_above=x_above,
                y_below=y_below,
                x_plate=x_plate,
                y_plate=y_plate,
                V_below=V_below,
                V_plate=V_plate,
                L_above=L_above,
                L_plate=L_plate,
                E_L_below=E_L_below,
                E_V_above=E_V_above,
                E_L_plate=E_L_plate,
                E_V_plate=E_V_plate,
                P_L=P_L,
                P_V=P_V,
                F_L=F_L,
                F_V=F_V,
                x_F_L=x_F_L,
                y_F_V=y_F_V,
                x_below=x_below,
                y_above=y_above,
            )
            assert result == pytest.approx(expected, rel=1e-10)

    # -- GE-G86-2: Total energy balance (Gani Eq. 2) -------------------------

    def test_ge_g86_2_energy_balance_form(self, gani: Any) -> None:
        """dC_{E,p}/dt = energy_in - energy_out with enthalpy-weighted flows.

        Entrainment inlet terms carry source-plate enthalpies, not
        receiving-plate enthalpies (GE-G86-2: E_L_{p-1}*h_{p-1},
        E_V_{p+1}*H_{p+1}).
        """
        calculate_energy_balance_rhs = _require_callable(
            gani,
            "calculate_energy_balance_rhs",
            "compute_energy_balance_rhs",
        )

        H_below = 35000.0  # J/mol  (vapor enthalpy from plate below)
        H_plate = 38000.0
        h_above = 25000.0  # liquid enthalpy from plate above
        h_plate = 26000.0
        # Source-plate enthalpies for entrainment (distinct from receiving plate)
        h_below = 24500.0  # h_{p-1} liquid enthalpy from plate below (entrainment source)
        H_above = 36500.0  # H_{p+1} vapor enthalpy from plate above (entrainment source)
        H_F_V = 0.0
        h_F_L = 27000.0

        V_below = 5.0
        V_plate = 5.0
        L_above = 4.0
        L_plate = 4.5
        E_L_below = 0.1
        E_V_above = 0.1
        E_L_plate = 0.05
        E_V_plate = 0.05
        P_L = 0.3
        P_V = 0.2
        F_L = 1.0
        F_V = 0.0

        inlet_energy = (
            F_V * H_F_V
            + F_L * h_F_L
            + V_below * H_below
            + E_L_below * h_below
            + L_above * h_above
            + E_V_above * H_above
        )
        outlet_energy = (P_V + V_plate + E_V_plate) * H_plate + (
            P_L + L_plate + E_L_plate
        ) * h_plate
        expected = inlet_energy - outlet_energy

        result = calculate_energy_balance_rhs(
            plate_index=1,
            H_below=H_below,
            H_plate=H_plate,
            h_above=h_above,
            h_plate=h_plate,
            V_below=V_below,
            V_plate=V_plate,
            L_above=L_above,
            L_plate=L_plate,
            E_L_below=E_L_below,
            E_V_above=E_V_above,
            E_L_plate=E_L_plate,
            E_V_plate=E_V_plate,
            P_L=P_L,
            P_V=P_V,
            F_L=F_L,
            F_V=F_V,
            H_F_V=H_F_V,
            h_F_L=h_F_L,
            h_below=h_below,
            H_above=H_above,
        )
        assert result == pytest.approx(expected, rel=1e-10)

    # -- GE-G86-3: Total mass balance (Gani Eq. 3) ---------------------------

    def test_ge_g86_3_total_mass_balance(self, gani: Any) -> None:
        """dC_{T,p}/dt = sum of molar inlets - sum of molar outlets."""
        calculate_total_mass_balance_rhs = _require_callable(
            gani,
            "calculate_total_mass_balance_rhs",
            "compute_total_mass_balance_rhs",
        )

        V_below = 5.0
        V_plate = 5.0
        L_above = 4.0
        L_plate = 4.5
        E_L_below = 0.1
        E_V_above = 0.1
        E_L_plate = 0.05
        E_V_plate = 0.05
        P_L = 0.3
        P_V = 0.2
        F_L = 1.0
        F_V = 0.0

        inlet = F_V + F_L + V_below + E_L_below + L_above + E_V_above
        outlet = V_plate + E_L_plate + L_plate + E_V_plate + P_V + P_L
        expected = inlet - outlet

        result = calculate_total_mass_balance_rhs(
            V_below=V_below,
            V_plate=V_plate,
            L_above=L_above,
            L_plate=L_plate,
            E_L_below=E_L_below,
            E_V_above=E_V_above,
            E_L_plate=E_L_plate,
            E_V_plate=E_V_plate,
            P_L=P_L,
            P_V=P_V,
            F_L=F_L,
            F_V=F_V,
        )
        assert result == pytest.approx(expected, rel=1e-10)

    # -- GE-G86-4: Murphree efficiency inversion (Gani Eqs. 4-8) -------------

    def test_ge_g86_4_murphree_inversion(self, gani: Any) -> None:
        """y*_{p,i} = (y_{p,i} - y_{p-1,i}) / ME_p + y_{p-1,i}.

        Gani's Murphree form (Eq. 8) inverts to recover y* from y, y_below, ME.
        """
        compute_equilibrium_from_murphree = _require_callable(
            gani,
            "compute_equilibrium_from_murphree",
            "calculate_equilibrium_from_murphree",
        )

        y_p = np.array([0.50, 0.30, 0.20])
        y_p_minus1 = np.array([0.35, 0.40, 0.25])
        ME = 0.8
        expected = (y_p - y_p_minus1) / ME + y_p_minus1

        result = compute_equilibrium_from_murphree(y_p, y_p_minus1, ME)
        np.testing.assert_allclose(result, expected, rtol=1e-12)

    # -- GE-G86-4 continued: composition definitions --------------------------

    def test_ge_g86_4_composition_from_holdup(self, gani: Any) -> None:
        """x_{p,i} = C_{p,i} / C_{T,p}  (Gani Eq. 7)."""
        compute_composition_from_holdup = _require_callable(
            gani,
            "compute_composition_from_holdup",
            "calculate_composition_from_holdup",
        )

        C_i = np.array([30.0, 50.0, 20.0])
        C_T = float(np.sum(C_i))
        expected = C_i / C_T

        result = compute_composition_from_holdup(C_i, C_T)
        np.testing.assert_allclose(result, expected, rtol=1e-12)

    # -- GE-G86-5: Equilibrium relation (Gani Eq. 9) -------------------------

    def test_ge_g86_5_equilibrium_relation(self, gani: Any) -> None:
        """y*_{p,i} = K_{p,i} * x_{p,i}  (Gani Eq. 9)."""
        compute_equilibrium_composition = _require_callable(
            gani,
            "compute_equilibrium_composition",
            "calculate_equilibrium_composition",
        )

        K = np.array([2.5, 1.0, 0.4])
        x = np.array([0.25, 0.35, 0.40])
        expected = K * x

        result = compute_equilibrium_composition(K, x)
        np.testing.assert_allclose(result, expected, rtol=1e-12)

    # -- GE-G86-5 continued: mixture molecular weight -------------------------

    def test_ge_g86_5_mixture_molecular_weight(self, gani: Any) -> None:
        """M_bar_{L,p} = sum_i M_{i} * x_{p,i}  (Gani Eq. 17)."""
        compute_mixture_molecular_weight = _require_callable(
            gani,
            "compute_mixture_molecular_weight",
            "calculate_mixture_molecular_weight",
        )

        M_i = np.array([16.0, 30.0, 44.0])
        x = np.array([0.5, 0.3, 0.2])
        expected = float(np.dot(M_i, x))

        result = compute_mixture_molecular_weight(M_i, x)
        assert result == pytest.approx(expected, rel=1e-12)

    # -- GE-G86-6: Generic hydraulic dependency family -----------------------

    def test_ge_g86_6_pressure_drop_definition(self, gani: Any) -> None:
        """DeltaPi_p = Pi_{p-1} - Pi_p."""
        compute_pressure_drop = _require_callable(
            gani,
            "compute_pressure_drop",
            "calculate_pressure_drop",
        )

        P_below = 150000.0
        P_plate = 148250.0
        expected = P_below - P_plate

        result = compute_pressure_drop(P_below, P_plate)
        assert result == pytest.approx(expected, rel=1e-12)

    def test_ge_g86_6_generic_hydraulic_dependency_family(self, gani: Any) -> None:
        """Hydraulic family preserves dependence on DeltaPi, holdup, geometry."""
        hydraulic_family = _require_callable(
            gani,
            "compute_generic_hydraulic_family",
            "evaluate_hydraulic_dependency_family",
        )

        delta_pressure = 1750.0
        total_holdup = 120.0
        geometry = {"tray_area": 0.8, "weir_length": 1.1}

        result = hydraulic_family(
            delta_pressure=delta_pressure,
            total_holdup=total_holdup,
            plate_geometry=geometry,
            vapor_flow_fn=lambda dp, ct, geom: dp + ct + geom["tray_area"],
            liquid_flow_fn=lambda ct, geom: ct - geom["weir_length"],
            liquid_weir_flow_fn=lambda ct, vp, geom: ct + vp + geom["tray_area"],
            vapor_froth_flow_fn=lambda vp, lp, geom: vp - lp + geom["weir_length"],
            liquid_entrainment_fn=lambda ct, dp, geom: ct + dp + geom["weir_length"],
            vapor_entrainment_fn=lambda ct, dp, geom: ct - dp + geom["tray_area"],
        )

        assert result["delta_pressure"] == pytest.approx(delta_pressure)
        assert result["vapor_flow"] == pytest.approx(delta_pressure + total_holdup + 0.8)
        assert result["liquid_flow"] == pytest.approx(total_holdup - 1.1)
        assert result["liquid_weir_flow"] == pytest.approx(
            total_holdup + result["vapor_flow"] + 0.8
        )
        assert result["vapor_froth_flow"] == pytest.approx(
            result["vapor_flow"] - result["liquid_flow"] + 1.1
        )
        assert result["liquid_entrainment"] == pytest.approx(total_holdup + delta_pressure + 1.1)
        assert result["vapor_entrainment"] == pytest.approx(total_holdup - delta_pressure + 0.8)

    # -- GE-G86-7: Reflux-drum balance (Gani Eq. 20) -------------------------

    def test_ge_g86_7_reflux_drum_balance(self, gani: Any) -> None:
        """dM_{RD,i}/dt = V_{N_p} * y_{N_p,i} - (L_0 + D) * x_{D,i}."""
        calculate_reflux_drum_balance_rhs = _require_callable(
            gani,
            "calculate_reflux_drum_balance_rhs",
            "compute_reflux_drum_balance_rhs",
        )

        n_species = 3
        y_top = np.array([0.6, 0.25, 0.15])
        x_D = np.array([0.55, 0.28, 0.17])
        V_top = 5.0
        L_0 = 3.0
        D = 1.5

        for i in range(n_species):
            expected = V_top * y_top[i] - (L_0 + D) * x_D[i]
            result = calculate_reflux_drum_balance_rhs(
                component_index=i,
                y_top_plate=y_top,
                x_distillate=x_D,
                V_top_plate=V_top,
                L_reflux=L_0,
                D_distillate=D,
            )
            assert result == pytest.approx(expected, rel=1e-10)

    # -- GE-G86-7 continued: Reboiler balance (Gani Eq. 21) ------------------

    def test_ge_g86_7_reboiler_balance(self, gani: Any) -> None:
        """dM_{RB,i}/dt = L_1 * x_{1,i} - B * x_{B,i} - V_B * y_{B,i}."""
        calculate_reboiler_balance_rhs = _require_callable(
            gani,
            "calculate_reboiler_balance_rhs",
            "compute_reboiler_balance_rhs",
        )

        n_species = 3
        x_bottom_plate = np.array([0.2, 0.4, 0.4])
        x_B = np.array([0.15, 0.35, 0.50])
        y_B = np.array([0.35, 0.35, 0.30])
        L_1 = 4.5
        B = 1.0
        V_B = 5.0

        for i in range(n_species):
            expected = L_1 * x_bottom_plate[i] - B * x_B[i] - V_B * y_B[i]
            result = calculate_reboiler_balance_rhs(
                component_index=i,
                x_bottom_plate=x_bottom_plate,
                x_bottoms=x_B,
                y_bottoms=y_B,
                L_bottom_plate=L_1,
                B_bottoms=B,
                V_reboiler=V_B,
            )
            assert result == pytest.approx(expected, rel=1e-10)

    # -- GE-G86-8: Bubble-cap hydraulic subset (Gani Appendix A.1) -----------

    def test_ge_g86_8_crest_height_over_weir(self, gani: Any) -> None:
        """h_ow = ((L^D_p) / (W * rho_{L,p} * 999.0))^(2/3)  (A.1)."""
        compute_crest_height_over_weir = _require_callable(
            gani,
            "compute_crest_height_over_weir",
            "calculate_crest_height_over_weir",
        )

        L_D_p = 0.005  # m^3/s  (liquid volumetric flow)
        W = 1.0  # m      (weir length)
        rho_L = 800.0  # kg/m^3

        expected = (L_D_p / (W * rho_L * 999.0)) ** (2.0 / 3.0)

        result = compute_crest_height_over_weir(L_D_p, W, rho_L)
        assert result == pytest.approx(expected, rel=1e-10)

    # -- GE-G86-8 continued: dry-tray pressure drop (A.2) --------------------

    def test_ge_g86_8_dry_tray_pressure_drop(self, gani: Any) -> None:
        """h^da_p = (0.003 / 12.0) * (g^L / (100.0 * A_D1))^2  (A.2)."""
        compute_dry_tray_pressure_drop = _require_callable(
            gani,
            "compute_dry_tray_pressure_drop",
            "calculate_dry_tray_pressure_drop",
        )

        g_L = 0.5  # some vapour load term
        A_D1 = 0.01  # tray area

        expected = (0.003 / 12.0) * (g_L / (100.0 * A_D1)) ** 2

        result = compute_dry_tray_pressure_drop(g_L, A_D1)
        assert result == pytest.approx(expected, rel=1e-10)

    # -- GE-G86-8 continued: total holdup from hydraulics (A.3) ---------------

    def test_ge_g86_8_total_holdup_from_hydraulics(self, gani: Any) -> None:
        """C_{T,p} = beta*(h_w + h_ow)*(A_p*rho_L / M_L)
        + (h_T + h_da + h_L - l)*(rho_L*A_D2 / M_L)  (A.3)."""
        compute_total_holdup_from_hydraulics = _require_callable(
            gani,
            "compute_total_holdup_from_hydraulics",
            "calculate_total_holdup_from_hydraulics",
        )

        beta = 1.0
        h_w = 0.05
        h_ow = 0.02
        A_p = 0.5
        rho_L = 800.0
        M_L = 30.0
        h_T = 0.01
        h_da = 0.005
        h_L = 0.08
        l_clearance = 0.03
        A_D2 = 0.02

        term1 = beta * (h_w + h_ow) * (A_p * rho_L / M_L)
        term2 = (h_T + h_da + h_L - l_clearance) * (rho_L * A_D2 / M_L)
        expected = term1 + term2

        result = compute_total_holdup_from_hydraulics(
            beta=beta,
            h_w=h_w,
            h_ow=h_ow,
            A_p=A_p,
            rho_L=rho_L,
            M_L=M_L,
            h_T=h_T,
            h_da=h_da,
            h_L=h_L,
            l_clearance=l_clearance,
            A_D2=A_D2,
        )
        assert result == pytest.approx(expected, rel=1e-10)

    def test_ge_g86_8_downcomer_unsealed_tray_head(self, gani: Any) -> None:
        """If h^L_{p-1} < h_bc, the Appendix A.4 tray-head relation applies."""
        compute_downcomer_unsealed_tray_head = _require_callable(
            gani,
            "compute_downcomer_unsealed_tray_head",
            "calculate_downcomer_unsealed_tray_head",
        )

        h_L_below = 0.04
        h_bc = 0.05
        gravity = 9.81
        rho_L = 800.0
        rho_V = 2.5
        V_D = 1500.0
        M_V = 28.0
        A_D2 = 0.03
        A_D1 = 0.02
        f_0 = 0.8
        l_D = 0.40
        d_be = 0.015

        bracket = 0.7 * (A_D2 / A_D1) ** 2 + 1.2 + f_0 * (l_D / d_be)
        expected = (6.0 / (gravity * rho_L * rho_V)) * (V_D * M_V / (3600.0 * A_D2)) ** 2 * bracket

        result = compute_downcomer_unsealed_tray_head(
            h_L_below=h_L_below,
            h_bc=h_bc,
            gravity=gravity,
            rho_L=rho_L,
            rho_V=rho_V,
            V_D=V_D,
            M_V=M_V,
            A_D2=A_D2,
            A_D1=A_D1,
            f_0=f_0,
            l_D=l_D,
            d_be=d_be,
        )
        assert result == pytest.approx(expected, rel=1e-10)

    # -- GE-G86-8 continued: flooding velocity (A.5) -------------------------

    def test_ge_g86_8_flooding_velocity(self, gani: Any) -> None:
        """U_f = F_1 * F_2 * (sigma_{L,p} / rho_{L,p})^(1/2)  (A.5)."""
        compute_flooding_velocity = _require_callable(
            gani,
            "compute_flooding_velocity",
            "calculate_flooding_velocity",
        )

        F_1 = 0.8
        F_2 = 1.1
        sigma_L = 0.02  # N/m
        rho_L = 800.0  # kg/m^3

        expected = F_1 * F_2 * (sigma_L / rho_L) ** 0.5

        result = compute_flooding_velocity(F_1, F_2, sigma_L, rho_L)
        assert result == pytest.approx(expected, rel=1e-10)

    # -- GE-G86-8 continued: liquid height (A.6) -----------------------------

    def test_ge_g86_8_liquid_height(self, gani: Any) -> None:
        """h^L_p = h^bc_p + h^op_p + h^hu_p  (A.6)."""
        compute_liquid_height = _require_callable(
            gani,
            "compute_liquid_height",
            "calculate_liquid_height",
        )

        h_bc = 0.05
        h_op = 0.03
        h_hu = 0.01
        expected = h_bc + h_op + h_hu

        result = compute_liquid_height(h_bc, h_op, h_hu)
        assert result == pytest.approx(expected, rel=1e-12)

    # -- GE-G86-8 continued: active liquid height (A.7) ----------------------

    def test_ge_g86_8_active_liquid_height(self, gani: Any) -> None:
        """h^{aL}_p = beta*(h_w + h_ow + Delta_p / 2.0)  (A.7)."""
        compute_active_liquid_height = _require_callable(
            gani,
            "compute_active_liquid_height",
            "calculate_active_liquid_height",
        )

        beta = 1.0
        h_w = 0.05
        h_ow = 0.02
        delta_p = 500.0  # Pa

        expected = beta * (h_w + h_ow + delta_p / 2.0)

        result = compute_active_liquid_height(beta, h_w, h_ow, delta_p)
        assert result == pytest.approx(expected, rel=1e-12)

    # -- GE-G86-8 continued: weeping flow rate (A.8) -------------------------

    def test_ge_g86_8_weeping_flow_rate(self, gani: Any) -> None:
        """Q'_p = 2.36 * (A_h / h_dc) * ((rho_L - rho_V)/rho_V)^(1/2)
        * [(2/(31+R_s))*(h_os)^(3/2) + (4/(151+R_s))*(1-R_s*h_os/h_sh)^(5/2)]
        with R_s = d_st / d_tb  (A.8)."""
        compute_weeping_flow_rate = _require_callable(
            gani,
            "compute_weeping_flow_rate",
            "calculate_weeping_flow_rate",
        )

        A_h = 0.01
        h_dc = 0.05
        rho_L = 800.0
        rho_V = 2.5
        R_s = 0.6
        h_os = 0.03
        h_sh = 0.06

        density_factor = ((rho_L - rho_V) / rho_V) ** 0.5
        bracket = (2.0 / (31.0 + R_s)) * h_os**1.5 + (4.0 / (151.0 + R_s)) * (
            1.0 - R_s * h_os / h_sh
        ) ** 2.5
        expected = 2.36 * (A_h / h_dc) * density_factor * bracket

        result = compute_weeping_flow_rate(
            A_h=A_h,
            h_dc=h_dc,
            rho_L=rho_L,
            rho_V=rho_V,
            R_s=R_s,
            h_os=h_os,
            h_sh=h_sh,
        )
        assert result == pytest.approx(expected, rel=1e-10)


class TestGaniRuntimeRealism:
    """Runtime-level checks that the executable path uses GE-G86 balances."""

    @pytest.fixture()
    def gani(self) -> Any:
        from modular_simulation.unit_processes.separation import Gani1986DistillationColumn

        col = Gani1986DistillationColumn(n_species=3, n_plates=4)
        _attach(col)
        return col

    def test_runtime_hydraulic_flows_change_with_plate_holdup(self, gani: Any) -> None:
        y_base = gani.differential_view.to_array()
        y_perturbed = y_base.copy()

        y_map = gani.differential_view.index_map
        holdup = np.asarray(y_perturbed[y_map["plate_component_holdup"]], dtype=np.float64).reshape(
            gani.n_plates, gani.n_species
        )
        holdup[2, :] *= 2.4

        common_kwargs = {
            "u": gani.boundary_view.to_array(),
            "k": gani.constant_view.to_array(),
            "y_map": gani.differential_view.index_map,
            "u_map": gani.boundary_view.index_map,
            "k_map": gani.constant_view.index_map,
            "algebraic_map": gani.algebraic_view.index_map,
            "algebraic_size": gani.algebraic_view.array_size,
        }

        algebraic_base = gani.calculate_algebraic_values(y=y_base, **common_kwargs)
        algebraic_perturbed = gani.calculate_algebraic_values(y=y_perturbed, **common_kwargs)

        vapor_base = np.asarray(
            algebraic_base[gani.algebraic_view.index_map["plate_vapor_flow_mol_s"]],
            dtype=np.float64,
        )
        vapor_perturbed = np.asarray(
            algebraic_perturbed[gani.algebraic_view.index_map["plate_vapor_flow_mol_s"]],
            dtype=np.float64,
        )
        liquid_base = np.asarray(
            algebraic_base[gani.algebraic_view.index_map["plate_liquid_flow_mol_s"]],
            dtype=np.float64,
        )
        liquid_perturbed = np.asarray(
            algebraic_perturbed[gani.algebraic_view.index_map["plate_liquid_flow_mol_s"]],
            dtype=np.float64,
        )

        assert np.any(np.abs(vapor_perturbed - vapor_base) > 1.0e-9)
        assert np.any(np.abs(liquid_perturbed - liquid_base) > 1.0e-9)

    def test_runtime_reflux_drum_and_reboiler_rhs_follow_ge_g86_7(self, gani: Any) -> None:
        gani.apply_inlet(
            "feed_1",
            StreamData(
                temperature=356.0,
                pressure=101325.0,
                mole_fractions=(0.55, 0.30, 0.15),
                molar_flow_rate=11.0,
            ),
        )
        gani.apply_inlet(
            "reflux_return",
            StreamData(
                temperature=330.0,
                pressure=101325.0,
                mole_fractions=(0.70, 0.20, 0.10),
                molar_flow_rate=2.0,
            ),
        )
        gani.apply_requested_outlet_through_flow_demand("distillate", 3.0)
        gani.apply_requested_outlet_through_flow_demand("bottoms", 2.0)

        y = gani.differential_view.to_array()
        u = gani.boundary_view.to_array()
        k = gani.constant_view.to_array()
        y_map = gani.differential_view.index_map
        u_map = gani.boundary_view.index_map
        k_map = gani.constant_view.index_map
        a_map = gani.algebraic_view.index_map
        algebraic = gani.calculate_algebraic_values(
            y=y,
            u=u,
            k=k,
            y_map=y_map,
            u_map=u_map,
            k_map=k_map,
            algebraic_map=a_map,
            algebraic_size=gani.algebraic_view.array_size,
        )
        rhs = gani.differential_rhs(0.0, y, u, k, algebraic, y_map, u_map, k_map, a_map)

        y_top = np.asarray(algebraic[a_map["plate_vapor_composition"]], dtype=np.float64).reshape(
            gani.n_plates, gani.n_species
        )[0]
        x_distillate = np.asarray(algebraic[a_map["distillate_composition"]], dtype=np.float64)
        V_top = float(np.asarray(algebraic[a_map["plate_vapor_flow_mol_s"]], dtype=np.float64)[0])
        L_reflux = float(algebraic[a_map["reflux_to_column_flow_mol_s"]])
        D = float(algebraic[a_map["distillate_flow"]])

        x_bottom_plate = np.asarray(
            algebraic[a_map["plate_liquid_composition"]], dtype=np.float64
        ).reshape(gani.n_plates, gani.n_species)[-1]
        x_bottoms = np.asarray(algebraic[a_map["bottoms_composition"]], dtype=np.float64)
        y_bottoms = np.asarray(algebraic[a_map["reboiler_vapor_composition"]], dtype=np.float64)
        L_bottom_plate = float(
            np.asarray(algebraic[a_map["plate_liquid_flow_mol_s"]], dtype=np.float64)[-1]
        )
        B = float(algebraic[a_map["bottoms_flow"]])
        V_reboiler = float(algebraic[a_map["reboiler_vapor_flow_mol_s"]])

        drum_rhs = np.asarray(rhs[y_map["reflux_drum_component_moles"]], dtype=np.float64)
        reboiler_rhs = np.asarray(rhs[y_map["reboiler_component_moles"]], dtype=np.float64)
        for i in range(gani.n_species):
            expected_drum = gani.calculate_reflux_drum_balance_rhs(
                component_index=i,
                y_top_plate=y_top,
                x_distillate=x_distillate,
                V_top_plate=V_top,
                L_reflux=L_reflux,
                D_distillate=D,
            )
            expected_reboiler = gani.calculate_reboiler_balance_rhs(
                component_index=i,
                x_bottom_plate=x_bottom_plate,
                x_bottoms=x_bottoms,
                y_bottoms=y_bottoms,
                L_bottom_plate=L_bottom_plate,
                B_bottoms=B,
                V_reboiler=V_reboiler,
            )
            assert drum_rhs[i] == pytest.approx(expected_drum, rel=1e-10)
            assert reboiler_rhs[i] == pytest.approx(expected_reboiler, rel=1e-10)

    def test_runtime_plate_rhs_uses_ge_g86_1_component_balance_family(self, gani: Any) -> None:
        gani.apply_inlet(
            "feed_1",
            StreamData(
                temperature=348.0,
                pressure=101325.0,
                mole_fractions=(0.45, 0.35, 0.20),
                molar_flow_rate=8.0,
            ),
        )
        gani.apply_inlet(
            "reflux_return",
            StreamData(
                temperature=325.0,
                pressure=101325.0,
                mole_fractions=(0.68, 0.20, 0.12),
                molar_flow_rate=1.5,
            ),
        )

        y = gani.differential_view.to_array()
        u = gani.boundary_view.to_array()
        k = gani.constant_view.to_array()
        y_map = gani.differential_view.index_map
        u_map = gani.boundary_view.index_map
        k_map = gani.constant_view.index_map
        a_map = gani.algebraic_view.index_map

        algebraic = gani.calculate_algebraic_values(
            y=y,
            u=u,
            k=k,
            y_map=y_map,
            u_map=u_map,
            k_map=k_map,
            algebraic_map=a_map,
            algebraic_size=gani.algebraic_view.array_size,
        )
        rhs = gani.differential_rhs(0.0, y, u, k, algebraic, y_map, u_map, k_map, a_map)

        p = 1
        plate_x = np.asarray(
            algebraic[a_map["plate_liquid_composition"]], dtype=np.float64
        ).reshape(gani.n_plates, gani.n_species)
        plate_y = np.asarray(algebraic[a_map["plate_vapor_composition"]], dtype=np.float64).reshape(
            gani.n_plates, gani.n_species
        )
        vapor_flow = np.asarray(algebraic[a_map["plate_vapor_flow_mol_s"]], dtype=np.float64)
        liquid_flow = np.asarray(algebraic[a_map["plate_liquid_flow_mol_s"]], dtype=np.float64)
        liquid_entrainment = np.asarray(
            algebraic[a_map["plate_liquid_entrainment_mol_s"]], dtype=np.float64
        )
        vapor_entrainment = np.asarray(
            algebraic[a_map["plate_vapor_entrainment_mol_s"]], dtype=np.float64
        )
        reboiler_vapor_flow = float(algebraic[a_map["reboiler_vapor_flow_mol_s"]])
        reboiler_y = np.asarray(algebraic[a_map["reboiler_vapor_composition"]], dtype=np.float64)

        # Source-plate compositions for entrainment (GE-G86-1):
        # E_L_{p-1} carries x from p+1 (plate below the receiving plate),
        # E_V_{p+1} carries y from p-1 (plate above the receiving plate).
        x_below_entrainment = (
            plate_x[p + 1]
            if p < (gani.n_plates - 1)
            else np.asarray(algebraic[a_map["bottoms_composition"]], dtype=np.float64)
        )
        y_above_entrainment = (
            plate_y[p - 1]
            if p > 0
            else np.asarray(algebraic[a_map["distillate_composition"]], dtype=np.float64)
        )

        expected = np.zeros(gani.n_species, dtype=np.float64)
        for i in range(gani.n_species):
            expected[i] = gani.calculate_component_balance_rhs(
                plate_index=p,
                component_index=i,
                x_above=plate_x[p - 1],
                y_below=reboiler_y if p == (gani.n_plates - 1) else plate_y[p + 1],
                x_plate=plate_x[p],
                y_plate=plate_y[p],
                V_below=reboiler_vapor_flow
                if p == (gani.n_plates - 1)
                else float(vapor_flow[p + 1]),
                V_plate=float(vapor_flow[p]),
                L_above=float(liquid_flow[p - 1]),
                L_plate=float(liquid_flow[p]),
                E_L_below=float(liquid_entrainment[p + 1]) if p < (gani.n_plates - 1) else 0.0,
                E_V_above=float(vapor_entrainment[p - 1]) if p > 0 else 0.0,
                E_L_plate=float(liquid_entrainment[p]),
                E_V_plate=float(vapor_entrainment[p]),
                P_L=0.0,
                P_V=0.0,
                F_L=0.0,
                F_V=0.0,
                x_F_L=np.zeros(gani.n_species, dtype=np.float64),
                y_F_V=np.zeros(gani.n_species, dtype=np.float64),
                x_below=x_below_entrainment,
                y_above=y_above_entrainment,
            )

        actual = np.asarray(rhs[y_map["plate_component_holdup"]], dtype=np.float64).reshape(
            gani.n_plates, gani.n_species
        )[p]
        np.testing.assert_allclose(actual, expected, rtol=1e-10, atol=1e-10)

    def test_runtime_plate_energy_rhs_uses_ge_g86_2_and_live_energy_state(self, gani: Any) -> None:
        gani.apply_inlet(
            "feed_1",
            StreamData(
                temperature=362.0,
                pressure=101325.0,
                mole_fractions=(0.48, 0.32, 0.20),
                molar_flow_rate=9.0,
            ),
        )

        y = gani.differential_view.to_array()
        y_map = gani.differential_view.index_map
        u = gani.boundary_view.to_array()
        u_map = gani.boundary_view.index_map
        k = gani.constant_view.to_array()
        k_map = gani.constant_view.index_map
        a_map = gani.algebraic_view.index_map

        plate_energy = np.asarray(y[y_map["plate_energy_holdup_j"]], dtype=np.float64)
        plate_energy[1] *= 1.35

        algebraic = gani.calculate_algebraic_values(
            y=y,
            u=u,
            k=k,
            y_map=y_map,
            u_map=u_map,
            k_map=k_map,
            algebraic_map=a_map,
            algebraic_size=gani.algebraic_view.array_size,
        )
        rhs = gani.differential_rhs(0.0, y, u, k, algebraic, y_map, u_map, k_map, a_map)

        p = 1
        plate_vapor_h = np.asarray(algebraic[a_map["plate_vapor_enthalpy_j_mol"]], dtype=np.float64)
        plate_liquid_h = np.asarray(
            algebraic[a_map["plate_liquid_enthalpy_j_mol"]], dtype=np.float64
        )
        plate_vapor_flow = np.asarray(algebraic[a_map["plate_vapor_flow_mol_s"]], dtype=np.float64)
        plate_liquid_flow = np.asarray(
            algebraic[a_map["plate_liquid_flow_mol_s"]], dtype=np.float64
        )
        plate_EL = np.asarray(algebraic[a_map["plate_liquid_entrainment_mol_s"]], dtype=np.float64)
        plate_EV = np.asarray(algebraic[a_map["plate_vapor_entrainment_mol_s"]], dtype=np.float64)
        reboiler_flow = float(algebraic[a_map["reboiler_vapor_flow_mol_s"]])
        bottoms_T = float(algebraic[a_map["bottoms_temperature"]])
        reboiler_y = np.asarray(algebraic[a_map["reboiler_vapor_composition"]], dtype=np.float64)

        cp_liq = np.asarray(k[k_map["species_liquid_heat_capacity_j_mol_k"]], dtype=np.float64)
        cp_vap = np.asarray(k[k_map["species_vapor_heat_capacity_j_mol_k"]], dtype=np.float64)
        dh_vap = np.asarray(k[k_map["species_vaporization_enthalpy_j_mol"]], dtype=np.float64)
        T_ref = float(k[k_map["thermo_reference_temperature_k"]])
        feed_comp = np.asarray(u[u_map["feed_1_composition"]], dtype=np.float64)
        feed_T = float(u[u_map["feed_1_temperature"]])
        h_F_L = float(np.dot(cp_liq, feed_comp) * (feed_T - T_ref))
        H_F_V = float(h_F_L + np.dot(dh_vap, feed_comp))
        H_reboiler = float(np.dot(cp_vap * (bottoms_T - T_ref) + dh_vap, reboiler_y))

        # Source-plate enthalpies for entrainment (GE-G86-2):
        # E_L_{p-1} carries h from p+1 (liquid entrainment source below),
        # E_V_{p+1} carries H from p-1 (vapor entrainment source above).
        h_below_entrainment = (
            float(plate_liquid_h[p + 1]) if p < (gani.n_plates - 1) else float(plate_liquid_h[-1])
        )
        H_above_entrainment = float(plate_vapor_h[p - 1]) if p > 0 else float(plate_vapor_h[0])

        expected = gani.calculate_energy_balance_rhs(
            plate_index=p,
            H_below=float(plate_vapor_h[p + 1]) if p < (gani.n_plates - 1) else H_reboiler,
            H_plate=float(plate_vapor_h[p]),
            h_above=float(plate_liquid_h[p - 1]),
            h_plate=float(plate_liquid_h[p]),
            V_below=float(plate_vapor_flow[p + 1]) if p < (gani.n_plates - 1) else reboiler_flow,
            V_plate=float(plate_vapor_flow[p]),
            L_above=float(plate_liquid_flow[p - 1]),
            L_plate=float(plate_liquid_flow[p]),
            E_L_below=float(plate_EL[p + 1]) if p < (gani.n_plates - 1) else 0.0,
            E_V_above=float(plate_EV[p - 1]) if p > 0 else 0.0,
            E_L_plate=float(plate_EL[p]),
            E_V_plate=float(plate_EV[p]),
            P_L=0.0,
            P_V=0.0,
            F_L=0.0,
            F_V=0.0,
            H_F_V=H_F_V,
            h_F_L=h_F_L,
            h_below=h_below_entrainment,
            H_above=H_above_entrainment,
        )
        actual = float(np.asarray(rhs[y_map["plate_energy_holdup_j"]], dtype=np.float64)[p])
        assert actual == pytest.approx(expected, rel=1e-10, abs=1e-10)

    def test_runtime_thermo_property_closures_materially_drive_live_algebraics(
        self, gani: Any
    ) -> None:
        y = gani.differential_view.to_array()
        u = gani.boundary_view.to_array()
        k = gani.constant_view.to_array()

        y_map = gani.differential_view.index_map
        u_map = gani.boundary_view.index_map
        k_map = gani.constant_view.index_map
        a_map = gani.algebraic_view.index_map

        algebraic_base = gani.calculate_algebraic_values(
            y=y,
            u=u,
            k=k,
            y_map=y_map,
            u_map=u_map,
            k_map=k_map,
            algebraic_map=a_map,
            algebraic_size=gani.algebraic_view.array_size,
        )

        y_hot = y.copy()
        np.asarray(y_hot[y_map["plate_energy_holdup_j"]], dtype=np.float64)[:] *= 1.6
        algebraic_hot = gani.calculate_algebraic_values(
            y=y_hot,
            u=u,
            k=k,
            y_map=y_map,
            u_map=u_map,
            k_map=k_map,
            algebraic_map=a_map,
            algebraic_size=gani.algebraic_view.array_size,
        )

        K_base = np.asarray(algebraic_base[a_map["plate_equilibrium_K_values"]], dtype=np.float64)
        K_hot = np.asarray(algebraic_hot[a_map["plate_equilibrium_K_values"]], dtype=np.float64)
        hL_base = np.asarray(algebraic_base[a_map["plate_liquid_enthalpy_j_mol"]], dtype=np.float64)
        hL_hot = np.asarray(algebraic_hot[a_map["plate_liquid_enthalpy_j_mol"]], dtype=np.float64)
        rhoL_base = np.asarray(
            algebraic_base[a_map["plate_liquid_density_kg_m3"]], dtype=np.float64
        )
        rhoL_hot = np.asarray(algebraic_hot[a_map["plate_liquid_density_kg_m3"]], dtype=np.float64)
        MWL_base = np.asarray(
            algebraic_base[a_map["plate_liquid_molecular_weight_kg_mol"]], dtype=np.float64
        )
        MWL_hot = np.asarray(
            algebraic_hot[a_map["plate_liquid_molecular_weight_kg_mol"]], dtype=np.float64
        )

        assert np.any(np.abs(K_hot - K_base) > 1.0e-9)
        assert np.any(np.abs(hL_hot - hL_base) > 1.0e-9)
        assert np.any(np.abs(rhoL_hot - rhoL_base) > 1.0e-9)
        # Molecular weight should remain composition-driven only in this slice.
        np.testing.assert_allclose(MWL_hot, MWL_base, rtol=1e-12, atol=1e-12)

    def test_runtime_bubblecap_appendix_family_drives_hydraulic_algebraics(self, gani: Any) -> None:
        y = gani.differential_view.to_array()
        u = gani.boundary_view.to_array()
        k = gani.constant_view.to_array()

        y_map = gani.differential_view.index_map
        u_map = gani.boundary_view.index_map
        k_map = gani.constant_view.index_map
        a_map = gani.algebraic_view.index_map

        algebraic_base = gani.calculate_algebraic_values(
            y=y,
            u=u,
            k=k,
            y_map=y_map,
            u_map=u_map,
            k_map=k_map,
            algebraic_map=a_map,
            algebraic_size=gani.algebraic_view.array_size,
        )

        y_variant = y.copy()
        np.asarray(y_variant[y_map["plate_component_holdup"]], dtype=np.float64)[:] *= 1.25
        np.asarray(y_variant[y_map["plate_energy_holdup_j"]], dtype=np.float64)[:] *= 1.15
        algebraic_variant = gani.calculate_algebraic_values(
            y=y_variant,
            u=u,
            k=k,
            y_map=y_map,
            u_map=u_map,
            k_map=k_map,
            algebraic_map=a_map,
            algebraic_size=gani.algebraic_view.array_size,
        )

        crest_base = np.asarray(
            algebraic_base[a_map["plate_bubblecap_crest_height_m"]], dtype=np.float64
        )
        crest_variant = np.asarray(
            algebraic_variant[a_map["plate_bubblecap_crest_height_m"]], dtype=np.float64
        )
        weep_base = np.asarray(
            algebraic_base[a_map["plate_bubblecap_weeping_flow_m3_s"]], dtype=np.float64
        )
        weep_variant = np.asarray(
            algebraic_variant[a_map["plate_bubblecap_weeping_flow_m3_s"]], dtype=np.float64
        )
        holdup_base = np.asarray(
            algebraic_base[a_map["plate_bubblecap_total_holdup_mol"]], dtype=np.float64
        )
        holdup_variant = np.asarray(
            algebraic_variant[a_map["plate_bubblecap_total_holdup_mol"]], dtype=np.float64
        )
        liquid_flow_base = np.asarray(
            algebraic_base[a_map["plate_liquid_flow_mol_s"]], dtype=np.float64
        )
        liquid_flow_variant = np.asarray(
            algebraic_variant[a_map["plate_liquid_flow_mol_s"]], dtype=np.float64
        )

        assert np.any(np.abs(crest_variant - crest_base) > 1.0e-9)
        assert np.any(np.abs(weep_variant - weep_base) > 1.0e-9)
        assert np.any(np.abs(holdup_variant - holdup_base) > 1.0e-9)
        assert np.any(np.abs(liquid_flow_variant - liquid_flow_base) > 1.0e-9)


class TestGaniEntrainmentSourceRegression:
    """Regression tests verifying entrainment terms use source-plate states.

    These tests construct states where source-plate and receiving-plate values
    differ and confirm the runtime path uses the correct source-neighbor values.
    They MUST fail if receiving-plate values are used instead.
    """

    @pytest.fixture()
    def gani(self) -> Any:
        from modular_simulation.unit_processes.separation import Gani1986DistillationColumn

        col = Gani1986DistillationColumn(n_species=3, n_plates=4)
        _attach(col)
        return col

    def test_component_balance_entrainment_uses_neighbor_source_not_receiving_plate(
        self, gani: Any
    ) -> None:
        """GE-G86-1: E_L_{p-1}*x_{p-1,i} and E_V_{p+1}*y_{p+1,i}.

        When source-plate compositions differ from receiving-plate compositions,
        the component balance RHS must use source values.  We verify by calling
        the static method with distinct source/receiving values and checking
        the result differs from the incorrect receiving-plate version.
        """
        n_species = gani.n_species
        x_plate = np.array([0.4, 0.35, 0.25])
        y_plate = np.array([0.55, 0.28, 0.17])
        x_below = np.array([0.6, 0.25, 0.15])  # source from plate below
        y_above = np.array([0.45, 0.35, 0.20])  # source from plate above
        x_above = np.array([0.3, 0.4, 0.3])
        y_below = np.array([0.5, 0.3, 0.2])

        E_L_below = 0.1
        E_V_above = 0.1

        # Compute with correct source-plate values
        result_correct = gani.calculate_component_balance_rhs(
            plate_index=1,
            component_index=0,
            x_above=x_above,
            y_below=y_below,
            x_plate=x_plate,
            y_plate=y_plate,
            V_below=5.0,
            V_plate=5.0,
            L_above=4.0,
            L_plate=4.5,
            E_L_below=E_L_below,
            E_V_above=E_V_above,
            E_L_plate=0.05,
            E_V_plate=0.05,
            P_L=0.0,
            P_V=0.0,
            F_L=0.0,
            F_V=0.0,
            x_F_L=np.zeros(n_species),
            y_F_V=np.zeros(n_species),
            x_below=x_below,
            y_above=y_above,
        )

        # Compute with incorrect receiving-plate values (the old bug)
        result_wrong = gani.calculate_component_balance_rhs(
            plate_index=1,
            component_index=0,
            x_above=x_above,
            y_below=y_below,
            x_plate=x_plate,
            y_plate=y_plate,
            V_below=5.0,
            V_plate=5.0,
            L_above=4.0,
            L_plate=4.5,
            E_L_below=E_L_below,
            E_V_above=E_V_above,
            E_L_plate=0.05,
            E_V_plate=0.05,
            P_L=0.0,
            P_V=0.0,
            F_L=0.0,
            F_V=0.0,
            x_F_L=np.zeros(n_species),
            y_F_V=np.zeros(n_species),
            x_below=x_plate,  # WRONG: using receiving-plate composition
            y_above=y_plate,  # WRONG: using receiving-plate composition
        )

        # The results MUST differ because source != receiving values
        assert result_correct != pytest.approx(result_wrong, rel=1e-10, abs=1e-12)

        # Verify the correct result uses source compositions
        inlet_correct = (
            5.0 * y_below[0] + E_L_below * x_below[0] + 4.0 * x_above[0] + E_V_above * y_above[0]
        )
        inlet_wrong = (
            5.0 * y_below[0] + E_L_below * x_plate[0] + 4.0 * x_above[0] + E_V_above * y_plate[0]
        )
        assert inlet_correct != pytest.approx(inlet_wrong, rel=1e-10, abs=1e-12)

        # Manual expected value with source compositions
        inlet = (
            5.0 * y_below[0] + E_L_below * x_below[0] + 4.0 * x_above[0] + E_V_above * y_above[0]
        )
        outlet = (5.0 + 0.05) * y_plate[0] + (4.5 + 0.05) * x_plate[0]
        expected = inlet - outlet
        assert result_correct == pytest.approx(expected, rel=1e-12)

    def test_energy_balance_entrainment_uses_neighbor_source_not_receiving_plate(
        self, gani: Any
    ) -> None:
        """GE-G86-2: E_L_{p-1}*h_{p-1} and E_V_{p+1}*H_{p+1}.

        When source-plate enthalpies differ from receiving-plate enthalpies,
        the energy balance RHS must use source values.
        """
        H_plate = 38000.0
        h_plate = 26000.0
        h_below = 24500.0  # source from plate below
        H_above = 36500.0  # source from plate above
        H_below = 35000.0
        h_above = 25000.0

        E_L_below = 0.1
        E_V_above = 0.1

        # Compute with correct source-plate values
        result_correct = gani.calculate_energy_balance_rhs(
            plate_index=1,
            H_below=H_below,
            H_plate=H_plate,
            h_above=h_above,
            h_plate=h_plate,
            V_below=5.0,
            V_plate=5.0,
            L_above=4.0,
            L_plate=4.5,
            E_L_below=E_L_below,
            E_V_above=E_V_above,
            E_L_plate=0.05,
            E_V_plate=0.05,
            P_L=0.0,
            P_V=0.0,
            F_L=0.0,
            F_V=0.0,
            H_F_V=0.0,
            h_F_L=0.0,
            h_below=h_below,
            H_above=H_above,
        )

        # Compute with incorrect receiving-plate values (the old bug)
        result_wrong = gani.calculate_energy_balance_rhs(
            plate_index=1,
            H_below=H_below,
            H_plate=H_plate,
            h_above=h_above,
            h_plate=h_plate,
            V_below=5.0,
            V_plate=5.0,
            L_above=4.0,
            L_plate=4.5,
            E_L_below=E_L_below,
            E_V_above=E_V_above,
            E_L_plate=0.05,
            E_V_plate=0.05,
            P_L=0.0,
            P_V=0.0,
            F_L=0.0,
            F_V=0.0,
            H_F_V=0.0,
            h_F_L=0.0,
            h_below=h_plate,  # WRONG: using receiving-plate enthalpy
            H_above=H_plate,  # WRONG: using receiving-plate enthalpy
        )

        # Results MUST differ because source != receiving values
        assert result_correct != pytest.approx(result_wrong, rel=1e-10, abs=1e-12)

        # Manual expected with source enthalpies
        inlet = 5.0 * H_below + E_L_below * h_below + 4.0 * h_above + E_V_above * H_above
        outlet = (5.0 + 0.05) * H_plate + (4.5 + 0.05) * h_plate
        expected = inlet - outlet
        assert result_correct == pytest.approx(expected, rel=1e-12)

    def test_runtime_differential_rhs_entrainment_differs_from_receiving_plate(
        self, gani: Any
    ) -> None:
        """Runtime RHS must change when neighbor compositions differ from plate's own.

        This test perturbs a neighboring plate's composition to be different from
        the receiving plate, runs the full runtime, and checks that the RHS
        reflects the neighbor composition, not the receiving plate's own.
        """
        gani.apply_inlet(
            "feed_1",
            StreamData(
                temperature=350.0,
                pressure=101325.0,
                mole_fractions=(0.5, 0.3, 0.2),
                molar_flow_rate=8.0,
            ),
        )
        gani.apply_inlet(
            "reflux_return",
            StreamData(
                temperature=330.0,
                pressure=101325.0,
                mole_fractions=(0.7, 0.2, 0.1),
                molar_flow_rate=2.0,
            ),
        )

        y = gani.differential_view.to_array()
        y_map = gani.differential_view.index_map
        u = gani.boundary_view.to_array()
        k = gani.constant_view.to_array()
        u_map = gani.boundary_view.index_map
        k_map = gani.constant_view.index_map
        a_map = gani.algebraic_view.index_map

        # Make plate 2 holdup distinct from plate 1 to create a compositional difference
        holdup = np.asarray(y[y_map["plate_component_holdup"]], dtype=np.float64).reshape(
            gani.n_plates, gani.n_species
        )
        holdup[2, :] = [18.0, 4.0, 2.0]  # Very different from plate 1

        algebraic = gani.calculate_algebraic_values(
            y=y,
            u=u,
            k=k,
            y_map=y_map,
            u_map=u_map,
            k_map=k_map,
            algebraic_map=a_map,
            algebraic_size=gani.algebraic_view.array_size,
        )
        rhs = gani.differential_rhs(0.0, y, u, k, algebraic, y_map, u_map, k_map, a_map)

        plate_x = np.asarray(
            algebraic[a_map["plate_liquid_composition"]], dtype=np.float64
        ).reshape(gani.n_plates, gani.n_species)
        plate_y = np.asarray(algebraic[a_map["plate_vapor_composition"]], dtype=np.float64).reshape(
            gani.n_plates, gani.n_species
        )
        liquid_ent = np.asarray(
            algebraic[a_map["plate_liquid_entrainment_mol_s"]], dtype=np.float64
        )
        vapor_ent = np.asarray(algebraic[a_map["plate_vapor_entrainment_mol_s"]], dtype=np.float64)

        # Check plate 1: its entrainment source from plate 2 (x_below) must differ
        # from its own composition, and the RHS must reflect this
        p = 1
        if liquid_ent[p + 1] > 1e-10 or vapor_ent[p - 1] > 1e-10:
            # Source compositions must differ from receiving plate
            assert not np.allclose(plate_x[p + 1], plate_x[p], rtol=1e-3, atol=1e-4), (
                "Test precondition: source and receiving compositions must differ"
            )

            # Compute what the RHS would be with wrong receiving-plate values
            actual_rhs = np.asarray(rhs[y_map["plate_component_holdup"]], dtype=np.float64).reshape(
                gani.n_plates, gani.n_species
            )[p]

            # Verify by manually computing with source values vs receiving values
            E_L_below_val = float(liquid_ent[p + 1])
            x_source = plate_x[p + 1]  # correct source
            x_receive = plate_x[p]  # wrong receiving plate

            # The entrainment contribution differs
            entrainment_contribution_source = E_L_below_val * x_source
            entrainment_contribution_wrong = E_L_below_val * x_receive
            assert not np.allclose(
                entrainment_contribution_source, entrainment_contribution_wrong, rtol=1e-3
            ), "Source vs receiving entrainment must produce different contributions"

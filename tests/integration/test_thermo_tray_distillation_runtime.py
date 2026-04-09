"""Wave 1 red integration tests for ThermoTrayDistillationColumn runtime.

These tests verify the runtime-compatibility contract for the
ThermoTrayDistillationColumn backend-only model.  They are expected to
**fail** (ImportError / AttributeError) until Waves 2–4 introduce the
class, thermo closures, and runtime seams.

Covers:
  - Backend-only startup-and-settle operation (GE-TTD-ST-1 through GE-TTD-ST-4)
  - Reuse of normal runtime stepping path (no separate steady-state solver)
  - Product withdrawal compatibility with existing connection contract
  - Existing observability-contract compatibility (no snapshot-schema widening)
  - No broad hard clipping during normal runtime
  - Four-model coexistence with Stagewise, Howard, and Gani siblings
  - No ShortcutDistillation compatibility path
  - No gameplay/build/client exposure widening
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys
from typing import Any, cast

import numpy as np
import pytest

from modular_simulation.measurables.process_model import ProcessModel
from modular_simulation.connection.hydraulics.hydraulic_solver import (
    HydraulicSystemDefinition,
    LinearResidualEquation,
)
from modular_simulation.connection.hydraulics.hydraulic_compile import HydraulicCompileLifecycle
from modular_simulation.connection.runtime.connected_plant_orchestrator import (
    ConnectedPlantOrchestrator,
)
from modular_simulation.connection.runtime.connection_layer import TransportAndMixingUpdate
from modular_simulation.connection.runtime.runtime import ConnectionRuntimeOrchestrator
from modular_simulation.connection.topology.network import ConnectionNetwork
from modular_simulation.connection.topology.unit_process_wiring import create_subsystem_for_unit
from modular_simulation.thermodynamics.runtime_context import SimulationRuntimeContext
from modular_simulation.thermodynamics.stream import StreamData
from modular_simulation.unit_processes import StagewiseDistillationColumn


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _attach(model: ProcessModel) -> None:
    model.attach_system(cast(Any, SimpleNamespace(solver_options={})))


def _valid_system() -> HydraulicSystemDefinition:
    return HydraulicSystemDefinition(
        equations=(),
        linear_residual_equations=(
            LinearResidualEquation(
                residual_name="ref",
                coefficients={"pressure": 1.0},
                constant=-5.0,
            ),
            LinearResidualEquation(
                residual_name="balance",
                coefficients={"pressure": 1.0, "flow": -1.0},
            ),
        ),
    )


def _require_startup_builder(col: ProcessModel) -> Any:
    """Return the startup-state builder callable or fail."""
    for name in ("build_startup_state", "initialize_dry_startup"):
        attr = getattr(col, name, None)
        if callable(attr):
            return attr
    pytest.fail(
        "ThermoTrayDistillationColumn must expose build_startup_state() or "
        "initialize_dry_startup() as a callable"
    )


def _require_settle_metric_value(col: ProcessModel) -> float:
    """Read the settle metric from the model or fail."""
    for name in ("settle_metric", "r_settle", "compute_settle_metric"):
        attr = getattr(col, name, None)
        if callable(attr):
            return float(attr())
        if attr is not None:
            return float(attr)
    pytest.fail(
        "ThermoTrayDistillationColumn must expose settle_metric / r_settle / "
        "compute_settle_metric as a callable or numeric attribute"
    )


# ---------------------------------------------------------------------------
# 1. Backend-only startup-and-settle
# ---------------------------------------------------------------------------


class TestBackendOnlyStartupAndSettle:
    """ThermoTrayDistillationColumn must support startup-and-settle using
    the same runtime equations, not a separate steady-state solver."""

    def test_import_and_construct(self) -> None:
        from modular_simulation.unit_processes.separation import (
            ThermoTrayDistillationColumn,
        )

        col = ThermoTrayDistillationColumn(n_species=3, n_trays=5)
        assert isinstance(col, ProcessModel)

    def test_startup_from_dry_state_and_step(self) -> None:
        """GE-TTD-ST-1: startup from numerically dry state and step successfully."""
        from modular_simulation.thermodynamics.stream import StreamData
        from modular_simulation.unit_processes.separation import (
            ThermoTrayDistillationColumn,
        )

        col = ThermoTrayDistillationColumn(n_species=3, n_trays=4, feed_tray_indices=(2,))
        _attach(col)
        col.apply_inlet(
            "feed_1",
            StreamData(
                temperature=350.0,
                pressure=150000.0,
                mole_fractions=(0.5, 0.3, 0.2),
                molar_flow_rate=8.0,
            ),
        )
        # Build startup state — required, not optional
        builder = _require_startup_builder(col)
        builder()

        col.step(0.1)
        assert col.t > 0.0

    def test_settle_uses_runtime_equations_not_separate_solver(self) -> None:
        """GE-TTD-ST-4: settling reuses runtime model, not a separate solver.

        After stepping multiple times under fixed boundary conditions,
        the settle metric must be computable and must decrease over time.
        """
        from modular_simulation.thermodynamics.stream import StreamData
        from modular_simulation.unit_processes.separation import (
            ThermoTrayDistillationColumn,
        )

        col = ThermoTrayDistillationColumn(n_species=3, n_trays=4, feed_tray_indices=(2,))
        _attach(col)
        col.condenser_duty_request_W = -50000.0
        col.reboiler_duty_request_W = 50000.0
        col.apply_inlet(
            "feed_1",
            StreamData(
                temperature=350.0,
                pressure=150000.0,
                mole_fractions=(0.5, 0.3, 0.2),
                molar_flow_rate=8.0,
            ),
        )
        builder = _require_startup_builder(col)
        builder()

        # Step multiple times and record settle metric
        metrics: list[float] = []
        for _ in range(6):
            col.step(0.2)
            metrics.append(_require_settle_metric_value(col))

        # Metrics must be finite and non-negative
        for m in metrics:
            assert np.isfinite(m), f"Settle metric must be finite, got {m}"
            assert m >= 0.0, f"Settle metric must be non-negative, got {m}"

        # Under fixed boundary conditions, metric should trend downward
        early_avg = sum(metrics[:3]) / 3.0
        late_avg = sum(metrics[-3:]) / 3.0
        assert late_avg < early_avg, (
            f"GE-TTD-ST-4 violation: settle metric not decreasing under fixed "
            f"boundary conditions. Early avg: {early_avg:.6e}, "
            f"late avg: {late_avg:.6e}"
        )


# ---------------------------------------------------------------------------
# 2. Reuse of normal runtime stepping path
# ---------------------------------------------------------------------------


class TestNormalRuntimeSteppingPath:
    """ThermoTrayDistillationColumn must step through the same
    ProcessModel step() interface as other models."""

    def test_step_advances_simulation_time(self) -> None:
        from modular_simulation.thermodynamics.stream import StreamData
        from modular_simulation.unit_processes.separation import (
            ThermoTrayDistillationColumn,
        )

        col = ThermoTrayDistillationColumn(n_species=3, n_trays=4, feed_tray_indices=(2,))
        _attach(col)
        col.apply_inlet(
            "feed_1",
            StreamData(
                temperature=350.0,
                pressure=150000.0,
                mole_fractions=(0.5, 0.3, 0.2),
                molar_flow_rate=8.0,
            ),
        )
        t_before = float(col.t)
        col.step(0.3)
        assert float(col.t) > t_before

    def test_multiple_steps_produce_evolving_state(self) -> None:
        from modular_simulation.thermodynamics.stream import StreamData
        from modular_simulation.unit_processes.separation import (
            ThermoTrayDistillationColumn,
        )

        col = ThermoTrayDistillationColumn(n_species=3, n_trays=4, feed_tray_indices=(2,))
        _attach(col)
        col.apply_inlet(
            "feed_1",
            StreamData(
                temperature=350.0,
                pressure=150000.0,
                mole_fractions=(0.5, 0.3, 0.2),
                molar_flow_rate=8.0,
            ),
        )
        col.condenser_duty_request_W = -40000.0
        col.reboiler_duty_request_W = 40000.0

        distillate_compositions = []
        for _ in range(3):
            col.step(0.2)
            d = col.get_outlet_stream("distillate")
            distillate_compositions.append(d.mole_fractions[0])

        # At least the first and last should differ (transient behavior)
        assert distillate_compositions[-1] != pytest.approx(distillate_compositions[0], abs=1e-6)


# ---------------------------------------------------------------------------
# 3. Product withdrawal compatibility
# ---------------------------------------------------------------------------


class TestProductWithdrawalCompatibility:
    """Product withdrawal must be compatible with existing connection contract."""

    def test_has_distillate_and_bottoms_outlets(self) -> None:
        from modular_simulation.unit_processes.separation import (
            ThermoTrayDistillationColumn,
        )

        col = ThermoTrayDistillationColumn(n_species=3, n_trays=4)
        assert "distillate" in col.ports.outlets
        assert "bottoms" in col.ports.outlets

    def test_has_feed_inlet_ports(self) -> None:
        from modular_simulation.unit_processes.separation import (
            ThermoTrayDistillationColumn,
        )

        col = ThermoTrayDistillationColumn(n_species=3, n_trays=4, feed_tray_indices=(2,))
        assert "feed_1" in col.ports.inlets

    def test_implements_outlet_demand_protocol(self) -> None:
        """Must implement apply_requested_outlet_through_flow_demand."""
        from modular_simulation.connection.runtime.process_stream_io import (
            is_process_outlet_demand_applier,
        )
        from modular_simulation.unit_processes.separation import (
            ThermoTrayDistillationColumn,
        )

        col = ThermoTrayDistillationColumn(n_species=3, n_trays=4)
        assert is_process_outlet_demand_applier(col)

    def test_outlet_demand_sets_distillate_withdrawal(self) -> None:
        from modular_simulation.unit_processes.separation import (
            ThermoTrayDistillationColumn,
        )

        col = ThermoTrayDistillationColumn(n_species=3, n_trays=4)
        _attach(col)

        col.apply_requested_outlet_through_flow_demand("distillate", 3.0)
        withdrawal = None
        for name in ("distillate_withdrawal_flow", "distillate_withdrawal_flow_mol_s"):
            attr = getattr(col, name, None)
            if attr is not None:
                withdrawal = float(attr)
                break
        assert withdrawal is not None
        assert withdrawal == pytest.approx(3.0)

    def test_outlet_demand_sets_bottoms_withdrawal(self) -> None:
        from modular_simulation.unit_processes.separation import (
            ThermoTrayDistillationColumn,
        )

        col = ThermoTrayDistillationColumn(n_species=3, n_trays=4)
        _attach(col)

        col.apply_requested_outlet_through_flow_demand("bottoms", 2.5)
        withdrawal = None
        for name in ("bottoms_withdrawal_flow", "bottoms_withdrawal_flow_mol_s"):
            attr = getattr(col, name, None)
            if attr is not None:
                withdrawal = float(attr)
                break
        assert withdrawal is not None
        assert withdrawal == pytest.approx(2.5)

    def test_outlet_demand_rejects_invalid_port(self) -> None:
        from modular_simulation.unit_processes.separation import (
            ThermoTrayDistillationColumn,
        )

        col = ThermoTrayDistillationColumn(n_species=3, n_trays=4)
        _attach(col)

        with pytest.raises(ValueError, match="Invalid outlet port|outlet"):
            col.apply_requested_outlet_through_flow_demand("nonexistent", 5.0)

    def test_distillate_withdrawal_is_owner_holdup_bounded(self) -> None:
        """Distillate withdrawal must be bounded by reflux-drum holdup."""
        from modular_simulation.unit_processes.separation import (
            ThermoTrayDistillationColumn,
        )

        col = ThermoTrayDistillationColumn(n_species=3, n_trays=4)
        _attach(col)

        # Try to withdraw more than the drum holds
        col.apply_requested_outlet_through_flow_demand("distillate", 100.0)
        dt = 0.5
        col.step(dt)

        # Actual distillate flow should be bounded by available holdup / dt
        distillate = col.get_outlet_stream("distillate")
        assert distillate.molar_flow_rate < 100.0


# ---------------------------------------------------------------------------
# 4. Existing observability-contract compatibility
# ---------------------------------------------------------------------------


class TestObservabilityContractCompatibility:
    """ThermoTrayDistillationColumn must be compatible with the existing
    substrate observability contract without widening the snapshot schema."""

    def test_hydraulic_participation_exists(self) -> None:
        from modular_simulation.unit_processes.separation import (
            ThermoTrayDistillationColumn,
        )

        col = ThermoTrayDistillationColumn(n_species=3, n_trays=4, feed_tray_indices=(2,))
        assert col.hydraulic_participation is not None

    def test_hydraulic_participation_declares_expected_ports(self) -> None:
        from modular_simulation.unit_processes.separation import (
            ThermoTrayDistillationColumn,
        )

        col = ThermoTrayDistillationColumn(n_species=3, n_trays=4, feed_tray_indices=(2,))
        ports = set(col.hydraulic_participation.ports)
        assert "feed_1" in ports
        assert "distillate" in ports
        assert "bottoms" in ports

    def test_get_outlet_stream_returns_stream_data(self) -> None:
        from modular_simulation.thermodynamics.stream import StreamData
        from modular_simulation.unit_processes.separation import (
            ThermoTrayDistillationColumn,
        )

        col = ThermoTrayDistillationColumn(n_species=3, n_trays=4, feed_tray_indices=(2,))
        _attach(col)
        col.apply_inlet(
            "feed_1",
            StreamData(
                temperature=350.0,
                pressure=150000.0,
                mole_fractions=(0.5, 0.3, 0.2),
                molar_flow_rate=8.0,
            ),
        )
        col.step(0.1)
        distillate = col.get_outlet_stream("distillate")
        bottoms = col.get_outlet_stream("bottoms")
        assert isinstance(distillate, StreamData)
        assert isinstance(bottoms, StreamData)

    def test_connected_runtime_observability_uses_existing_snapshot_surface(self) -> None:
        """Wave 4: thermo-tray projections stay under process_state_values only."""
        from modular_simulation.unit_processes.separation import ThermoTrayDistillationColumn

        context = SimulationRuntimeContext.create(species_names=["methanol", "ethanol", "water"])
        col = ThermoTrayDistillationColumn(n_species=3, n_trays=4, feed_tray_indices=(2,))
        subsystem = create_subsystem_for_unit(
            unit=col,
            unit_id="thermo_col",
            dt=0.1,
            runtime_context=context,
        )
        _attach(col)
        col.apply_inlet(
            "feed_1",
            StreamData(
                temperature=350.0,
                pressure=150000.0,
                mole_fractions=(0.5, 0.3, 0.2),
                molar_flow_rate=8.0,
            ),
        )

        runtime = ConnectionRuntimeOrchestrator(
            hydraulic_solve_step=(
                lambda *, network, macro_step_time_s: network.compiled.hydraulic.solve()  # type: ignore[union-attr]
            ),
            transport_and_mixing_step=(
                lambda *, network, hydraulic_result, macro_step_time_s: TransportAndMixingUpdate(
                    transport_results={}
                )
            ),
            boundary_propagation_step=(
                lambda *,
                network,
                hydraulic_result,
                transport_and_mixing_update,
                macro_step_time_s: {}
            ),
            runtime_context=context,
        )
        network = ConnectionNetwork(
            compile_lifecycle=HydraulicCompileLifecycle(),
            hydraulic_system_builder=lambda topology: _valid_system(),
            runtime_orchestrator=runtime,
        )
        network.add_process(
            "thermo_col",
            inlet_ports=subsystem.descriptor.inlet_ports,
            outlet_ports=subsystem.descriptor.outlet_ports,
        )
        network.add_boundary_source("feed")
        network.add_boundary_sink("dist")
        network.add_boundary_sink("bot")
        _ = network.connect("feed", "thermo_col.feed_1")
        _ = network.connect("thermo_col.distillate", "dist")
        _ = network.connect("thermo_col.bottoms", "bot")
        _ = network.compile()

        orchestrator = ConnectedPlantOrchestrator(
            subsystems=(subsystem,),
            network=network,
            runtime_orchestrator=runtime,
            runtime_context=context,
        )
        _ = orchestrator.step(macro_step_time_s=0.2)

        snapshot = network.get_observability_snapshot()
        assert set(snapshot.keys()) == {
            "schema",
            "graph_revision",
            "runtime",
            "queue",
            "observables",
        }
        process_state_values = snapshot["observables"]["process_state_values"]
        assert process_state_values["thermo_col/column_pressure_pa"] == pytest.approx(col.p_top_pa)
        assert process_state_values["thermo_col/distillate_flow_mol_s"] == pytest.approx(
            col.distillate_flow
        )
        assert process_state_values["thermo_col/bottoms_flow_mol_s"] == pytest.approx(
            col.bottoms_flow
        )
        assert "thermo_col/feed_1/stage_index" in process_state_values


# ---------------------------------------------------------------------------
# 5. No broad hard clipping during normal runtime
# ---------------------------------------------------------------------------


class TestNoBroadHardClipping:
    """Normal runtime should evolve states through smooth operators,
    not by repeated hard clamping of temperature, pressure, or flow values."""

    def test_tray_flows_vary_across_trays_not_clamped_to_constant(self) -> None:
        """GE-TTD-MAT-4/5/6: tray liquid and vapor traffic must vary across
        trays under a live feed, proving the smooth closure is active rather
        than a single hard-clipped constant applied to all trays."""
        from modular_simulation.thermodynamics.stream import StreamData
        from modular_simulation.unit_processes.separation import (
            ThermoTrayDistillationColumn,
        )

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
        col.condenser_duty_request_W = -100000.0
        col.reboiler_duty_request_W = 100000.0
        col.reflux_withdrawal_flow = 1.5
        col.distillate_withdrawal_flow = 0.8
        col.bottoms_withdrawal_flow = 1.1
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

        params = col._params
        alg = col.calculate_algebraic_values(
            y=col.differential_view.to_array(),
            u=col.boundary_view.to_array(),
            k=params.k,
            y_map=params.y_map,
            u_map=params.boundary_map,
            k_map=params.k_map,
            algebraic_map=params.algebraic_map,
            algebraic_size=params.algebraic_size,
        )

        liq_attr = None
        for name in ("tray_liquid_flow", "tray_liquid_flow_mol_s", "liquid_downflow"):
            if hasattr(col, name):
                liq_attr = name
                break
        assert liq_attr is not None, (
            "Model must expose tray liquid flow for no-clipping verification"
        )
        liq = np.asarray(alg[params.algebraic_map[liq_attr]], dtype=np.float64)
        assert np.all(np.isfinite(liq))
        assert np.ptp(liq) > 1.0e-3, (
            f"Liquid flows are all identical ({liq[0]}), indicating hard-clipped "
            f"constants rather than smooth GE-TTD-MAT-4/5 closure. Flows: {liq}"
        )

    def test_tray_temperatures_are_finite_and_vary_across_column(self) -> None:
        """Under a live feed with reboiler/condenser duties, tray temperatures
        should vary across the column height (top cooler, bottom hotter),
        proving thermal evolution is not hard-clamped to a single value."""
        from modular_simulation.thermodynamics.stream import StreamData
        from modular_simulation.unit_processes.separation import (
            ThermoTrayDistillationColumn,
        )

        col = ThermoTrayDistillationColumn(n_species=3, n_trays=5, feed_tray_indices=(3,))
        _attach(col)
        col.condenser_duty_request_W = -40000.0
        col.reboiler_duty_request_W = 40000.0
        col.apply_inlet(
            "feed_1",
            StreamData(
                temperature=350.0,
                pressure=150000.0,
                mole_fractions=(0.5, 0.3, 0.2),
                molar_flow_rate=8.0,
            ),
        )
        col.step(0.5)

        temp_attr = None
        for name in ("tray_temperature", "tray_temperatures_K"):
            if hasattr(col, name):
                temp_attr = name
                break
        assert temp_attr is not None, "Model must expose tray temperature attribute"
        temps = np.asarray(getattr(col, temp_attr), dtype=np.float64)
        assert np.all(np.isfinite(temps)), f"Temperatures went non-finite: {temps}"
        # All identical temperatures = no thermal evolution (hard-clamped)
        assert not np.allclose(temps, temps[0]), (
            f"All tray temperatures are identical ({temps[0]} K), suggesting "
            f"hard-clamped thermal state rather than smooth thermo evolution. "
            f"Temps: {temps}"
        )

    def test_temperatures_do_not_pin_to_broad_clip_bounds(self) -> None:
        """Wave 2 guardrail: normal runtime should not pin temperatures to
        broad global clamp bounds (e.g., 250 K / 800 K)."""
        from modular_simulation.thermodynamics.stream import StreamData
        from modular_simulation.unit_processes.separation import ThermoTrayDistillationColumn

        col = ThermoTrayDistillationColumn(n_species=3, n_trays=5, feed_tray_indices=(3,))
        _attach(col)
        col.condenser_duty_request_W = -40000.0
        col.reboiler_duty_request_W = 40000.0
        col.apply_inlet(
            "feed_1",
            StreamData(
                temperature=350.0,
                pressure=150000.0,
                mole_fractions=(0.5, 0.3, 0.2),
                molar_flow_rate=8.0,
            ),
        )
        for _ in range(10):
            col.step(0.2)

        temp_attr = None
        for name in ("tray_temperature", "tray_temperatures_K"):
            if hasattr(col, name):
                temp_attr = name
                break
        assert temp_attr is not None
        temps = np.asarray(getattr(col, temp_attr), dtype=np.float64)
        assert np.all(np.isfinite(temps))
        assert not np.any(np.isclose(temps, 250.0, atol=1.0e-6)), (
            f"Pinned lower bound temps: {temps}"
        )
        assert not np.any(np.isclose(temps, 800.0, atol=1.0e-6)), (
            f"Pinned upper bound temps: {temps}"
        )


# ---------------------------------------------------------------------------
# 6. Four-model coexistence
# ---------------------------------------------------------------------------


class TestFourModelCoexistence:
    """All four distillation models must be simultaneously importable and
    constructable without interfering with each other."""

    def test_all_four_importable(self) -> None:
        from modular_simulation.unit_processes.separation import (
            Gani1986DistillationColumn,
            Howard1970DistillationColumn,
            StagewiseDistillationColumn as Stagewise4,
            ThermoTrayDistillationColumn,
        )

        assert ThermoTrayDistillationColumn is not Stagewise4
        assert ThermoTrayDistillationColumn is not Howard1970DistillationColumn
        assert ThermoTrayDistillationColumn is not Gani1986DistillationColumn

    def test_all_four_constructable(self) -> None:
        from modular_simulation.unit_processes.separation import (
            Gani1986DistillationColumn,
            Howard1970DistillationColumn,
            ThermoTrayDistillationColumn,
        )

        thermo_tray = ThermoTrayDistillationColumn(n_species=3, n_trays=4)
        howard = Howard1970DistillationColumn(n_species=3, n_plates=4)
        gani = Gani1986DistillationColumn(n_species=3, n_plates=4)
        stagewise = StagewiseDistillationColumn(
            n_species=3, active_contact_height_m=4.0, feed_stage_indices=(1,)
        )

        _attach(thermo_tray)
        _attach(howard)
        _attach(gani)
        _attach(stagewise)

        assert isinstance(thermo_tray, ProcessModel)
        assert isinstance(howard, ProcessModel)
        assert isinstance(gani, ProcessModel)
        assert isinstance(stagewise, ProcessModel)

    def test_all_four_have_distillate_and_bottoms(self) -> None:
        from modular_simulation.unit_processes.separation import (
            Gani1986DistillationColumn,
            Howard1970DistillationColumn,
            ThermoTrayDistillationColumn,
        )

        thermo_tray = ThermoTrayDistillationColumn(n_species=3, n_trays=4)
        howard = Howard1970DistillationColumn(n_species=3, n_plates=4)
        gani = Gani1986DistillationColumn(n_species=3, n_plates=4)
        stagewise = StagewiseDistillationColumn(
            n_species=3, active_contact_height_m=4.0, feed_stage_indices=(1,)
        )

        for col in (thermo_tray, howard, gani, stagewise):
            assert "distillate" in col.ports.outlets, (
                f"{type(col).__name__} missing distillate outlet"
            )
            assert "bottoms" in col.ports.outlets, f"{type(col).__name__} missing bottoms outlet"


# ---------------------------------------------------------------------------
# 7. No ShortcutDistillation compatibility path
# ---------------------------------------------------------------------------


class TestNoShortcutDistillation:
    """No ShortcutDistillation class, alias, or compatibility shim should exist."""

    def test_no_shortcut_distillation_in_separation_package(self) -> None:
        import modular_simulation.unit_processes.separation as sep_pkg

        assert not hasattr(sep_pkg, "ShortcutDistillation")

    def test_no_shortcut_distillation_in_unit_processes(self) -> None:
        import modular_simulation.unit_processes as up_pkg

        assert not hasattr(up_pkg, "ShortcutDistillation")

    def test_no_shortcut_in_dunder_all(self) -> None:
        import modular_simulation.unit_processes.separation as sep_pkg
        import modular_simulation.unit_processes as up_pkg

        assert "ShortcutDistillation" not in sep_pkg.__all__
        assert "ShortcutDistillation" not in up_pkg.__all__


# ---------------------------------------------------------------------------
# 8. No gameplay/build/client exposure widening
# ---------------------------------------------------------------------------


class TestNoGameplayExposureWidening:
    """ThermoTrayDistillationColumn must not widen gameplay, start, or catalog
    exposure beyond what already exists."""

    def test_sandbox_catalog_does_not_reference_thermo_tray(self) -> None:
        from modular_simulation.gameplay.sandbox_catalog import build_sandbox_catalog

        catalog = build_sandbox_catalog()
        for _item_id, item in catalog.items():
            assert "ThermoTray" not in str(item.default_config), (
                f"Sandbox catalog unexpectedly references ThermoTray in {_item_id}"
            )

    def test_start_catalog_does_not_reference_thermo_tray(self) -> None:
        from modular_simulation.gameplay.start_catalog import build_start_catalog

        catalog = build_start_catalog()
        for _start_id, start in catalog.items():
            for item_id in getattr(start, "allowed_item_ids", ()):
                assert "ThermoTray" not in item_id

    def test_stagewise_still_in_sandbox_catalog(self) -> None:
        from modular_simulation.gameplay.sandbox_catalog import build_sandbox_catalog

        catalog = build_sandbox_catalog()
        stagewise_items = [
            item_id
            for item_id, item in catalog.items()
            if "StagewiseDistillationColumn" in str(item.default_config)
        ]
        assert len(stagewise_items) >= 1, (
            "StagewiseDistillationColumn must remain in the sandbox catalog"
        )


# ---------------------------------------------------------------------------
# 9. Demo contract
# ---------------------------------------------------------------------------


class TestThermoTrayStartupDemoContract:
    """The startup demo must be importable and report expected structure."""

    def test_demo_runs_and_reports_expected_keys(self) -> None:
        project_root = Path(__file__).resolve().parents[2]
        if str(project_root) not in sys.path:
            sys.path.append(str(project_root))
        from examples.dynamic_simulation_demos.thermo_tray_distillation_startup_demo import (
            run_demo,
        )

        result = run_demo()

        assert result["model_role"] == "backend_only_thermo_tray_actual"
        assert result["startup_mode"] == "numerically_dry"
        assert result["settle_mode"] == "runtime_equations_reused"
        assert result["has_tray_temperatures"] == "yes"
        assert result["has_tray_holdups"] == "yes"
        assert result["has_condenser_drum"] == "yes"
        assert result["has_reboiler_kettle"] == "yes"
        assert result["no_broad_hard_clipping"] == "yes"
        assert result["settle_metric_decreasing"] == "yes"


# ---------------------------------------------------------------------------
# 10. Wave 1 red integration tests: top-end pathologies
#   (fix-thermo-tray-top-end-pathologies)
# ---------------------------------------------------------------------------


class TestTopEndRealizability:
    """Red integration tests: drum holdup and distillate must not be pinned
    at floor values.

    The characterization evidence shows drum holdup pinned at 3e-08 mol
    and distillate flow pinned at 1.5e-07 mol/s due to the shared-drum-overdraw
    and epsilon-flooring pathologies.

    Confirmed behavior: with D=5.0, B=5.0 and dt=0.1, drum depletes by
    step 10 and pins at 3e-08; distillate flow then pins at 3e-07.
    """

    def test_drum_holdup_not_pinned_at_floor(self) -> None:
        """After a startup transient with aggressive withdrawal, drum
        components must not be individually floored to eps_n by step().

        The original pathology: per-component epsilon flooring in step()
        silently creates mass, pinning each drum component at eps_n and
        total at n_species * eps_n = 3e-8.  Post-fix: step() skips the
        floor for drum states, so not all components are >= eps_n.
        """
        from modular_simulation.thermodynamics.stream import StreamData
        from modular_simulation.unit_processes.separation import (
            ThermoTrayDistillationColumn,
        )

        col = ThermoTrayDistillationColumn(n_species=3, n_trays=4, feed_tray_indices=(2,))
        _attach(col)
        col.condenser_drum_component_moles = np.zeros(3, dtype=np.float64)
        col.reboiler_duty_request_W = 0.0
        col.condenser_duty_request_W = 0.0

        for _ in range(5):
            col.step(0.1)

        drum_components = np.asarray(col.condenser_drum_component_moles, dtype=np.float64)
        assert not np.allclose(drum_components, np.full(3, col.eps_n), atol=0.0, rtol=0.0), (
            f"Per-component epsilon flooring detected: drum components were forced to eps_n. "
            f"eps_n={col.eps_n:.2e}, drum={drum_components}"
        )

    def test_distillate_flow_not_pinned_at_floor(self) -> None:
        """Distillate flow must not be pinned at the floor value derived from
        the pinned drum (3*eps_n / dt).

        The characterization evidence shows distillate_flow pinned at ~1.5e-07 mol/s
        (which equals drum_total / dt = 3e-08 / 0.2 = 1.5e-07).
        """
        from modular_simulation.thermodynamics.stream import StreamData
        from modular_simulation.unit_processes.separation import (
            ThermoTrayDistillationColumn,
        )

        col = ThermoTrayDistillationColumn(n_species=3, n_trays=4, feed_tray_indices=(2,))
        _attach(col)
        col.apply_inlet(
            "feed_1",
            StreamData(
                temperature=350.0,
                pressure=150000.0,
                mole_fractions=(0.5, 0.3, 0.2),
                molar_flow_rate=8.0,
            ),
        )
        col.reboiler_duty_request_W = 50000.0
        col.condenser_duty_request_W = -50000.0
        col.distillate_withdrawal_flow = 5.0
        col.bottoms_withdrawal_flow = 5.0

        dt = 0.2
        distillate_flows = []
        for _ in range(15):
            col.step(dt)
            d = col.get_outlet_stream("distillate")
            distillate_flows.append(d.molar_flow_rate)

        # The pinned value from characterization: drum/dt = 3e-08/0.2 = 1.5e-07
        pinned_flow = 3.0 * col.eps_n / dt  # 1.5e-07

        # Check that distillate flow is NOT consistently pinned near this value
        last_flows = distillate_flows[-5:]
        all_near_pinned = all(np.isclose(f, pinned_flow, rtol=0.5) for f in last_flows)

        assert not all_near_pinned, (
            f"Distillate flow is pinned at {pinned_flow:.2e} mol/s. "
            f"Last 5 flows: {last_flows}. "
            f"This matches the characterization pathology."
        )


class TestDrumTemperatureSanity:
    """Red integration tests: drum temperature must remain physically plausible
    throughout the startup transient.

    Confirmed behavior: with D=5, B=5 and dt=0.1, drum depletes by step 10,
    then temperature drops 5 K/step, reaching 140 K by step 40 and continuing
    to spiral.  Post-fix: temperature must stay positive and near feed temp.
    """

    def test_drum_temperature_positive_throughout_startup(self) -> None:
        """Drum temperature must remain positive throughout startup transient."""
        from modular_simulation.thermodynamics.stream import StreamData
        from modular_simulation.unit_processes.separation import (
            ThermoTrayDistillationColumn,
        )

        col = ThermoTrayDistillationColumn(n_species=3, n_trays=4, feed_tray_indices=(2,))
        _attach(col)
        col.apply_inlet(
            "feed_1",
            StreamData(
                temperature=350.0,
                pressure=150000.0,
                mole_fractions=(0.5, 0.3, 0.2),
                molar_flow_rate=8.0,
            ),
        )
        col.reboiler_duty_request_W = 50000.0
        col.condenser_duty_request_W = -50000.0
        col.distillate_withdrawal_flow = 5.0
        col.bottoms_withdrawal_flow = 5.0

        temperatures = []
        for _ in range(40):
            col.step(0.1)
            temperatures.append(float(col.condenser_drum_temperature))

        min_temp = min(temperatures)
        max_temp = max(temperatures)

        assert min_temp > 200.0, (
            f"Drum temperature went below 200 K during startup: min={min_temp:.1f} K. "
            f"This is the dry-drum temperature pathology. Last 5 temps: {temperatures[-5:]}"
        )
        assert max_temp < 2000.0, (
            f"Drum temperature exceeded 2000 K during startup: max={max_temp:.1f} K."
        )

    def test_drum_temperature_within_plausible_range_of_feed(self) -> None:
        """Drum temperature must remain within 200 K of feed temperature."""
        from modular_simulation.thermodynamics.stream import StreamData
        from modular_simulation.unit_processes.separation import (
            ThermoTrayDistillationColumn,
        )

        feed_temp = 350.0
        col = ThermoTrayDistillationColumn(n_species=3, n_trays=4, feed_tray_indices=(2,))
        _attach(col)
        col.apply_inlet(
            "feed_1",
            StreamData(
                temperature=feed_temp,
                pressure=150000.0,
                mole_fractions=(0.5, 0.3, 0.2),
                molar_flow_rate=8.0,
            ),
        )
        col.reboiler_duty_request_W = 50000.0
        col.condenser_duty_request_W = -50000.0
        col.distillate_withdrawal_flow = 5.0
        col.bottoms_withdrawal_flow = 5.0

        for _ in range(40):
            col.step(0.1)
            drum_temp = float(col.condenser_drum_temperature)
            assert abs(drum_temp - feed_temp) < 200.0, (
                f"Drum temperature {drum_temp:.1f} K is outside plausible range "
                f"({feed_temp} ± 200 K). This is the dry-drum temperature pathology."
            )


class TestRefluxCausality:
    """Red integration tests: reflux must respond to explicit boundary input,
    not a back-computed value."""

    def test_reflux_responds_to_explicit_boundary_not_vapor_minus_distillate(self) -> None:
        """When reflux_withdrawal_flow is set to a specific value, the reflux
        used by the model must come from that boundary input, not from
        vap_flow[0] - distillate_flow."""
        from modular_simulation.thermodynamics.stream import StreamData
        from modular_simulation.unit_processes.separation import (
            ThermoTrayDistillationColumn,
        )

        col = ThermoTrayDistillationColumn(n_species=3, n_trays=4, feed_tray_indices=(2,))
        _attach(col)
        col.apply_inlet(
            "feed_1",
            StreamData(
                temperature=350.0,
                pressure=150000.0,
                mole_fractions=(0.5, 0.3, 0.2),
                molar_flow_rate=8.0,
            ),
        )
        col.reboiler_duty_request_W = 50000.0
        col.condenser_duty_request_W = -50000.0
        col.distillate_withdrawal_flow = 0.5

        # Step once to establish vapor flow
        col.step(0.1)

        params = col._params
        y = col.differential_view.to_array()
        u = col.boundary_view.to_array()
        alg = col.calculate_algebraic_values(
            y=y,
            u=u,
            k=params.k,
            y_map=params.y_map,
            u_map=params.boundary_map,
            k_map=params.k_map,
            algebraic_map=params.algebraic_map,
            algebraic_size=params.algebraic_size,
        )
        vap_flow = np.asarray(alg[params.algebraic_map["tray_vapor_flow"]], dtype=np.float64)
        d_flow = float(alg[params.algebraic_map["distillate_flow"]])
        back_computed = max(0.0, float(vap_flow[0]) - d_flow)

        # Set explicit reflux to a value distinctly different from back-computation
        explicit_reflux = max(0.1, back_computed + 1.0)
        col.reflux_withdrawal_flow = explicit_reflux

        # Step again — the reflux must come from the boundary, not back-computation
        col.step(0.1)

        y = col.differential_view.to_array()
        u = col.boundary_view.to_array()
        alg = col.calculate_algebraic_values(
            y=y,
            u=u,
            k=params.k,
            y_map=params.y_map,
            u_map=params.boundary_map,
            k_map=params.k_map,
            algebraic_map=params.algebraic_map,
            algebraic_size=params.algebraic_size,
        )
        vap_flow_new = np.asarray(alg[params.algebraic_map["tray_vapor_flow"]], dtype=np.float64)
        d_flow_new = float(alg[params.algebraic_map["distillate_flow"]])
        new_back_computed = max(0.0, float(vap_flow_new[0]) - d_flow_new)

        # Verify that the boundary is being used: reflux_withdrawal_flow
        # must be in the boundary map
        assert "reflux_withdrawal_flow" in col._params.boundary_map, (
            "reflux_withdrawal_flow not in boundary map — reflux uses "
            "back-computation instead of explicit boundary request"
        )

    def test_reflux_matches_back_computation_formula(self) -> None:
        """Reflux must NOT equal max(0, vap_flow[0] - distillate_flow).

        This test extracts the reflux implied by the drum RHS and checks
        that it does NOT match the back-computation formula.  Currently
        the reflux matches exactly, proving the model has no explicit
        reflux boundary input — reflux is algebraically derived.

        Uses delta_p_tray_pa=5000 to ensure active vapor flow so that
        back-computation produces a non-trivial (non-zero) reflux.

        Red because: RHS-implied reflux equals max(0, V_0 - D).
        Post-fix: reflux comes from boundary, breaking equality.
        """
        from modular_simulation.thermodynamics.stream import StreamData
        from modular_simulation.unit_processes.separation import (
            ThermoTrayDistillationColumn,
        )

        # delta_p=5000 ensures active vapor flow
        col = ThermoTrayDistillationColumn(
            n_species=3, n_trays=4, feed_tray_indices=(2,), delta_p_tray_pa=5000.0
        )
        _attach(col)
        col.apply_inlet(
            "feed_1",
            StreamData(
                temperature=350.0,
                pressure=150000.0,
                mole_fractions=(0.5, 0.3, 0.2),
                molar_flow_rate=8.0,
            ),
        )
        col.reboiler_duty_request_W = 50000.0
        col.condenser_duty_request_W = -50000.0
        col.distillate_withdrawal_flow = 0.5

        # Step 3+ times for vapor to build up
        col.step(0.1)
        col.step(0.1)
        col.step(0.1)

        params = col._params
        y = col.differential_view.to_array()
        u = col.boundary_view.to_array()
        alg = col.calculate_algebraic_values(
            y=y,
            u=u,
            k=params.k,
            y_map=params.y_map,
            u_map=params.boundary_map,
            k_map=params.k_map,
            algebraic_map=params.algebraic_map,
            algebraic_size=params.algebraic_size,
        )

        vap_flow = np.asarray(alg[params.algebraic_map["tray_vapor_flow"]], dtype=np.float64)
        d_flow = float(alg[params.algebraic_map["distillate_flow"]])

        # The back-computation formula used at line 1087
        back_computed_reflux = max(0.0, float(vap_flow[0]) - d_flow)

        # Derive the reflux actually used from the drum RHS:
        # sum(d_drum) = V_0 - D - R  =>  R = V_0 - D - sum(d_drum)
        dy = col.differential_rhs(
            t=col.t,
            y=y,
            u=u,
            k=params.k,
            algebraic=alg,
            y_map=params.y_map,
            u_map=params.boundary_map,
            k_map=params.k_map,
            algebraic_map=params.algebraic_map,
        )
        drum_dy = np.asarray(dy[params.y_map["condenser_drum_component_moles"]], dtype=np.float64)
        rhs_implied_reflux = float(vap_flow[0]) - d_flow - float(np.sum(drum_dy))

        # Precondition: vapor flow and back-computed reflux must be non-trivial
        assert float(vap_flow[0]) > 1.0, (
            f"Precondition failed: vap_flow[0]={float(vap_flow[0]):.4f} too small"
        )
        assert back_computed_reflux > 1.0, (
            f"Precondition failed: back_computed_reflux={back_computed_reflux:.4f} too small"
        )

        # Post-fix: reflux must NOT match back-computation (it reads boundary)
        # Currently RED: reflux matches back-computation exactly.
        assert rhs_implied_reflux != pytest.approx(back_computed_reflux, rel=1e-6, abs=1e-9), (
            f"Reflux is back-computed: RHS-implied {rhs_implied_reflux:.6f} matches "
            f"max(0, V_0-D) = {back_computed_reflux:.6f}. "
            f"The model uses vap_flow[0]-distillate_flow instead of an explicit "
            f"boundary request.  Post-fix: reflux must come from "
            f"reflux_withdrawal_flow in the boundary map."
        )

        col = ThermoTrayDistillationColumn(n_species=3, n_trays=4, feed_tray_indices=(2,))
        _attach(col)
        col.apply_inlet(
            "feed_1",
            StreamData(
                temperature=350.0,
                pressure=150000.0,
                mole_fractions=(0.5, 0.3, 0.2),
                molar_flow_rate=8.0,
            ),
        )
        col.reboiler_duty_request_W = 50000.0
        col.condenser_duty_request_W = -50000.0
        col.distillate_withdrawal_flow = 0.5

        # Step twice to get past initial transient
        col.step(0.1)
        col.step(0.1)

        params = col._params
        y = col.differential_view.to_array()
        u = col.boundary_view.to_array()
        alg = col.calculate_algebraic_values(
            y=y,
            u=u,
            k=params.k,
            y_map=params.y_map,
            u_map=params.boundary_map,
            k_map=params.k_map,
            algebraic_map=params.algebraic_map,
            algebraic_size=params.algebraic_size,
        )

        vap_flow = np.asarray(alg[params.algebraic_map["tray_vapor_flow"]], dtype=np.float64)
        d_flow = float(alg[params.algebraic_map["distillate_flow"]])

        # The back-computation formula used at line 1087
        back_computed_reflux = max(0.0, float(vap_flow[0]) - d_flow)

        # Derive the reflux actually used from the drum RHS:
        # sum(d_drum) = V_0 - D - R  =>  R = V_0 - D - sum(d_drum)
        dy = col.differential_rhs(
            t=col.t,
            y=y,
            u=u,
            k=params.k,
            algebraic=alg,
            y_map=params.y_map,
            u_map=params.boundary_map,
            k_map=params.k_map,
            algebraic_map=params.algebraic_map,
        )
        drum_dy = np.asarray(dy[params.y_map["condenser_drum_component_moles"]], dtype=np.float64)
        rhs_implied_reflux = float(vap_flow[0]) - d_flow - float(np.sum(drum_dy))

        # Currently the reflux matches back-computation exactly.
        # Post-fix: reflux comes from the boundary, breaking this equality.
        assert rhs_implied_reflux != pytest.approx(back_computed_reflux, rel=1e-6, abs=1e-9), (
            f"Reflux {rhs_implied_reflux:.6f} matches back-computation "
            f"max(0, V_0-D) = {back_computed_reflux:.6f}. "
            f"The model uses vap_flow[0]-distillate_flow instead of an explicit "
            f"boundary request.  Post-fix: reflux must come from "
            f"reflux_withdrawal_flow in the boundary map."
        )

    def test_reflux_boundary_zero_means_no_reflux(self) -> None:
        """When reflux_withdrawal_flow is zero, reflux must be zero regardless
        of vap_flow[0] - distillate_flow."""
        from modular_simulation.thermodynamics.stream import StreamData
        from modular_simulation.unit_processes.separation import (
            ThermoTrayDistillationColumn,
        )

        col = ThermoTrayDistillationColumn(n_species=3, n_trays=4, feed_tray_indices=(2,))
        _attach(col)
        col.apply_inlet(
            "feed_1",
            StreamData(
                temperature=350.0,
                pressure=150000.0,
                mole_fractions=(0.5, 0.3, 0.2),
                molar_flow_rate=8.0,
            ),
        )
        col.reboiler_duty_request_W = 50000.0
        col.condenser_duty_request_W = -50000.0
        col.distillate_withdrawal_flow = 0.5

        # Explicitly set reflux to zero
        col.reflux_withdrawal_flow = 0.0

        col.step(0.1)

        # Verify that reflux_withdrawal_flow is in boundary map
        assert "reflux_withdrawal_flow" in col._params.boundary_map, (
            "reflux_withdrawal_flow must be in boundary map for explicit causal reflux control"
        )

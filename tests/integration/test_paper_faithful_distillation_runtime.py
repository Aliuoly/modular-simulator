"""Wave 1 failing integration tests for paper-faithful distillation runtime.

These tests verify the runtime-compatibility contract for the Howard (1970)
and Gani (1986) paper-faithful distillation models.  They are expected to
**fail** (ImportError / AttributeError) until Waves 2 and 3 introduce the
classes and runtime seams.

Covers:
  - Feed/product routing through the monolithic runtime seam
  - Explicit holdup ownership (the models own their plate inventories)
  - Runtime outlet-demand application (apply_requested_outlet_through_flow_demand)
  - Non-widening of gameplay/start exposure
  - No ShortcutDistillation compatibility path
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys
from typing import Any, cast

import pytest

from modular_simulation.measurables.process_model import ProcessModel
from modular_simulation.thermodynamics.stream import StreamData
from modular_simulation.unit_processes import StagewiseDistillationColumn


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _attach(model: ProcessModel) -> None:
    model.attach_system(cast(Any, SimpleNamespace(solver_options={})))


def _read_first_present_attr(candidate: Any, *names: str) -> Any:
    for name in names:
        if hasattr(candidate, name):
            return getattr(candidate, name)
    joined = ", ".join(names)
    pytest.fail(f"Expected one of the following attributes to exist: {joined}")


# ---------------------------------------------------------------------------
# 1. Feed/product routing through monolithic seam
# ---------------------------------------------------------------------------


class TestFeedProductRouting:
    """Both Howard and Gani models must accept feeds and produce product
    streams through the same apply_inlet / get_outlet_stream interface
    used by StagewiseDistillationColumn."""

    def test_howard_feed_routing_to_distillate_and_bottoms(self) -> None:
        from modular_simulation.unit_processes.separation import (
            Howard1970DistillationColumn,
        )

        col = Howard1970DistillationColumn(n_species=3, n_plates=5)
        _attach(col)

        col.apply_inlet(
            "feed_1",
            StreamData(
                temperature=350.0,
                pressure=101325.0,
                mole_fractions=(0.5, 0.3, 0.2),
                molar_flow_rate=10.0,
            ),
        )
        distillate = col.get_outlet_stream("distillate")
        bottoms = col.get_outlet_stream("bottoms")

        assert isinstance(distillate, StreamData)
        assert isinstance(bottoms, StreamData)
        # Both outlets should have positive flow when configured
        assert distillate.molar_flow_rate >= 0.0
        assert bottoms.molar_flow_rate >= 0.0

    def test_gani_feed_routing_to_distillate_and_bottoms(self) -> None:
        from modular_simulation.unit_processes.separation import (
            Gani1986DistillationColumn,
        )

        col = Gani1986DistillationColumn(n_species=3, n_plates=5)
        _attach(col)

        col.apply_inlet(
            "feed_1",
            StreamData(
                temperature=350.0,
                pressure=101325.0,
                mole_fractions=(0.5, 0.3, 0.2),
                molar_flow_rate=10.0,
            ),
        )
        distillate = col.get_outlet_stream("distillate")
        bottoms = col.get_outlet_stream("bottoms")

        assert isinstance(distillate, StreamData)
        assert isinstance(bottoms, StreamData)
        assert distillate.molar_flow_rate >= 0.0
        assert bottoms.molar_flow_rate >= 0.0

    def test_stagewise_still_routes_feeds_and_products(self) -> None:
        """Existing stagewise column routing is unchanged by the addition."""
        col = StagewiseDistillationColumn(
            n_species=3,
            active_contact_height_m=4.0,
            feed_stage_indices=(1,),
        )
        _attach(col)
        col.condenser_duty_request_W = -30000.0
        col.reboiler_duty_request_W = 30000.0

        col.apply_inlet(
            "feed_1",
            StreamData(
                temperature=350.0,
                pressure=101325.0,
                mole_fractions=(0.5, 0.3, 0.2),
                molar_flow_rate=10.0,
            ),
        )

        distillate = col.get_outlet_stream("distillate")
        bottoms = col.get_outlet_stream("bottoms")
        assert isinstance(distillate, StreamData)
        assert isinstance(bottoms, StreamData)

    def test_howard_reflux_return_routing(self) -> None:
        from modular_simulation.unit_processes.separation import (
            Howard1970DistillationColumn,
        )

        col = Howard1970DistillationColumn(n_species=2, n_plates=4)
        _attach(col)
        col.apply_inlet(
            "reflux_return",
            StreamData(
                temperature=300.0,
                pressure=101325.0,
                mole_fractions=(0.7, 0.3),
                molar_flow_rate=5.0,
            ),
        )

    def test_gani_reflux_return_routing(self) -> None:
        from modular_simulation.unit_processes.separation import (
            Gani1986DistillationColumn,
        )

        col = Gani1986DistillationColumn(n_species=2, n_plates=4)
        _attach(col)
        col.apply_inlet(
            "reflux_return",
            StreamData(
                temperature=300.0,
                pressure=101325.0,
                mole_fractions=(0.7, 0.3),
                molar_flow_rate=5.0,
            ),
        )


# ---------------------------------------------------------------------------
# 2. Explicit holdup ownership
# ---------------------------------------------------------------------------


class TestExplicitHoldupOwnership:
    """Howard and Gani models must own their plate inventories as explicit
    differential state, not delegate to external storage or proxies."""

    def test_howard_has_plate_holdup_state(self) -> None:
        from modular_simulation.unit_processes.separation import (
            Howard1970DistillationColumn,
        )

        col = Howard1970DistillationColumn(n_species=3, n_plates=5)
        _attach(col)

        # The model must own plate-level component holdup
        assert (
            "plate_component_holdup" in col.differential_view.state_list
            or "stage_component_moles" in col.differential_view.state_list
        )

    def test_gani_has_plate_holdup_state(self) -> None:
        from modular_simulation.unit_processes.separation import (
            Gani1986DistillationColumn,
        )

        col = Gani1986DistillationColumn(n_species=3, n_plates=5)
        _attach(col)

        # The model must own plate-level component holdup
        assert (
            "plate_component_holdup" in col.differential_view.state_list
            or "stage_component_moles" in col.differential_view.state_list
        )

    def test_howard_owns_reflux_drum_holdup(self) -> None:
        from modular_simulation.unit_processes.separation import (
            Howard1970DistillationColumn,
        )

        col = Howard1970DistillationColumn(n_species=2, n_plates=4)
        _attach(col)

        # Reflux drum or condenser pool must be owned by the model
        assert (
            "reflux_drum_component_moles" in col.differential_view.state_list
            or "condenser_pool_moles" in col.differential_view.state_list
        )

    def test_gani_owns_reflux_drum_and_reboiler_holdup(self) -> None:
        from modular_simulation.unit_processes.separation import (
            Gani1986DistillationColumn,
        )

        col = Gani1986DistillationColumn(n_species=2, n_plates=4)
        _attach(col)

        # Gani model explicitly tracks reflux-drum and reboiler inventories
        state_names = col.differential_view.state_list
        has_drum = (
            "reflux_drum_component_moles" in state_names or "reflux_drum_holdup" in state_names
        )
        has_reboiler = (
            "reboiler_component_moles" in state_names
            or "bottoms_sump_component_moles" in state_names
        )
        assert has_drum, "Gani model must own reflux-drum holdup"
        assert has_reboiler, "Gani model must own reboiler holdup"


# ---------------------------------------------------------------------------
# 3. Runtime outlet-demand application
# ---------------------------------------------------------------------------


class TestRuntimeOutletDemand:
    """Both models must implement apply_requested_outlet_through_flow_demand
    so the hydraulic-solved runtime can drive product withdrawal."""

    def test_howard_implements_outlet_demand_protocol(self) -> None:
        from modular_simulation.connection.runtime.process_stream_io import (
            is_process_outlet_demand_applier,
        )
        from modular_simulation.unit_processes.separation import (
            Howard1970DistillationColumn,
        )

        col = Howard1970DistillationColumn(n_species=2, n_plates=4)
        assert is_process_outlet_demand_applier(col)

    def test_gani_implements_outlet_demand_protocol(self) -> None:
        from modular_simulation.connection.runtime.process_stream_io import (
            is_process_outlet_demand_applier,
        )
        from modular_simulation.unit_processes.separation import (
            Gani1986DistillationColumn,
        )

        col = Gani1986DistillationColumn(n_species=2, n_plates=4)
        assert is_process_outlet_demand_applier(col)

    def test_howard_outlet_demand_sets_withdrawal(self) -> None:
        from modular_simulation.unit_processes.separation import (
            Howard1970DistillationColumn,
        )

        col = Howard1970DistillationColumn(n_species=2, n_plates=4)
        _attach(col)

        col.apply_requested_outlet_through_flow_demand("distillate", 5.0)
        withdrawal = _read_first_present_attr(
            col,
            "distillate_withdrawal_flow",
            "distillate_withdrawal_flow_mol_s",
            "requested_distillate_flow",
        )
        assert float(withdrawal) == pytest.approx(5.0)

    def test_gani_outlet_demand_sets_withdrawal(self) -> None:
        from modular_simulation.unit_processes.separation import (
            Gani1986DistillationColumn,
        )

        col = Gani1986DistillationColumn(n_species=2, n_plates=4)
        _attach(col)

        col.apply_requested_outlet_through_flow_demand("bottoms", 3.0)
        withdrawal = _read_first_present_attr(
            col,
            "bottoms_withdrawal_flow",
            "bottoms_withdrawal_flow_mol_s",
            "requested_bottoms_flow",
        )
        assert float(withdrawal) == pytest.approx(3.0)

    def test_howard_rejects_invalid_outlet_demand_port(self) -> None:
        from modular_simulation.unit_processes.separation import (
            Howard1970DistillationColumn,
        )

        col = Howard1970DistillationColumn(n_species=2, n_plates=4)
        _attach(col)

        with pytest.raises(ValueError, match="Invalid outlet port|outlet"):
            col.apply_requested_outlet_through_flow_demand("nonexistent", 5.0)

    def test_gani_rejects_invalid_outlet_demand_port(self) -> None:
        from modular_simulation.unit_processes.separation import (
            Gani1986DistillationColumn,
        )

        col = Gani1986DistillationColumn(n_species=2, n_plates=4)
        _attach(col)

        with pytest.raises(ValueError, match="Invalid outlet port|outlet"):
            col.apply_requested_outlet_through_flow_demand("nonexistent", 5.0)


# ---------------------------------------------------------------------------
# 4. Non-widening of gameplay/start exposure
# ---------------------------------------------------------------------------


class TestGameplayStartExposure:
    """Adding Howard and Gani models must not widen gameplay, start, or
    catalog exposure beyond what already exists for StagewiseDistillationColumn."""

    def test_sandbox_catalog_does_not_reference_howard(self) -> None:
        """Howard model should NOT appear in the sandbox catalog in this change."""
        from modular_simulation.gameplay.sandbox_catalog import build_sandbox_catalog

        catalog = build_sandbox_catalog()
        for _item_id, item in catalog.items():
            assert "Howard1970" not in str(item.default_config), (
                f"Sandbox catalog unexpectedly references Howard1970 in {_item_id}"
            )

    def test_sandbox_catalog_does_not_reference_gani(self) -> None:
        """Gani model should NOT appear in the sandbox catalog in this change."""
        from modular_simulation.gameplay.sandbox_catalog import build_sandbox_catalog

        catalog = build_sandbox_catalog()
        for _item_id, item in catalog.items():
            assert "Gani1986" not in str(item.default_config), (
                f"Sandbox catalog unexpectedly references Gani1986 in {_item_id}"
            )

    def test_start_catalog_does_not_reference_howard_or_gani(self) -> None:
        """Start catalog items should not reference the new models."""
        from modular_simulation.gameplay.start_catalog import build_start_catalog

        catalog = build_start_catalog()
        for _start_id, start in catalog.items():
            for item_id in getattr(start, "allowed_item_ids", ()):
                assert "Howard" not in item_id
                assert "Gani" not in item_id

    def test_stagewise_still_in_sandbox_catalog(self) -> None:
        """StagewiseDistillationColumn must remain in the sandbox catalog."""
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
# 5. No ShortcutDistillation compatibility path
# ---------------------------------------------------------------------------


class TestNoShortcutDistillation:
    """No ShortcutDistillation class, alias, or compatibility shim should
    exist in the codebase after this change."""

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
# 6. Three-class coexistence smoke test
# ---------------------------------------------------------------------------


class TestThreeClassCoexistence:
    """All three distillation classes must be simultaneously importable and
    constructable without interfering with each other."""

    def test_all_three_importable(self) -> None:
        from modular_simulation.unit_processes.separation import (
            Gani1986DistillationColumn,
            Howard1970DistillationColumn,
            StagewiseDistillationColumn as Stagewise3,
        )

        assert Stagewise3 is StagewiseDistillationColumn
        assert Howard1970DistillationColumn is not Gani1986DistillationColumn
        assert Howard1970DistillationColumn is not StagewiseDistillationColumn
        assert Gani1986DistillationColumn is not StagewiseDistillationColumn

    def test_all_three_constructable(self) -> None:
        from modular_simulation.unit_processes.separation import (
            Gani1986DistillationColumn,
            Howard1970DistillationColumn,
        )

        howard = Howard1970DistillationColumn(n_species=2, n_plates=4)
        gani = Gani1986DistillationColumn(n_species=2, n_plates=4)
        stagewise = StagewiseDistillationColumn(
            n_species=2,
            active_contact_height_m=4.0,
            feed_stage_indices=(1,),
        )

        _attach(howard)
        _attach(gani)
        _attach(stagewise)

        assert isinstance(howard, ProcessModel)
        assert isinstance(gani, ProcessModel)
        assert isinstance(stagewise, ProcessModel)

    def test_all_three_have_distillate_and_bottoms(self) -> None:
        from modular_simulation.unit_processes.separation import (
            Gani1986DistillationColumn,
            Howard1970DistillationColumn,
        )

        howard = Howard1970DistillationColumn(n_species=2, n_plates=4)
        gani = Gani1986DistillationColumn(n_species=2, n_plates=4)
        stagewise = StagewiseDistillationColumn(
            n_species=2,
            active_contact_height_m=4.0,
            feed_stage_indices=(1,),
        )

        for col in (howard, gani, stagewise):
            assert "distillate" in col.ports.outlets, (
                f"{type(col).__name__} missing distillate outlet"
            )
            assert "bottoms" in col.ports.outlets, f"{type(col).__name__} missing bottoms outlet"


# ---------------------------------------------------------------------------
# 7. Wave 4 demo contract
# ---------------------------------------------------------------------------


class TestWave4PaperFaithfulDemo:
    def test_demo_reports_ownership_and_runtime_demand_comparison(self) -> None:
        project_root = Path(__file__).resolve().parents[2]
        if str(project_root) not in sys.path:
            sys.path.append(str(project_root))
        from examples.dynamic_simulation_demos.paper_faithful_distillation_comparison import (
            run_demo,
        )

        result = run_demo()

        assert result["stagewise_role"] == "reduced_order_baseline"
        assert result["howard_role"] == "paper_faithful_first_slice"
        assert result["gani_role"] == "paper_faithful_first_slice"
        assert result["closure_note"].startswith("Models use distinct governing closures")

        assert result["stagewise_has_owner_state"] == "yes"
        assert result["howard_has_owner_state"] == "yes"
        assert result["gani_has_owner_state"] == "yes"
        assert result["stagewise_runtime_demand_port_compat"] == "yes"
        assert result["howard_runtime_demand_port_compat"] == "yes"
        assert result["gani_runtime_demand_port_compat"] == "yes"

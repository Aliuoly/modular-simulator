from __future__ import annotations

from pathlib import Path
import sys
from typing import cast

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from examples.connection_layer.two_tank_reaction_comparison import run_demo as run_two_tank_demo
from examples.unit_process_flowsheet.complex_6_ammonia_recycle_loop import (
    _build_flowsheet as build_ammonia_loop_flowsheet,
    run_example as run_ammonia_loop_example,
)
from examples.unit_process_flowsheet.easy_2_heater_flash import (
    run_example as run_heater_flash_example,
)
from examples.unit_process_flowsheet.easy_3_dual_feed_heat_exchanger import (
    run_example as run_dual_feed_exchanger_example,
)
from examples.unit_process_flowsheet.gas_1_inlet_separator import (
    build_example_flowsheet as build_gas_1,
)
from examples.unit_process_flowsheet.gas_2_teg_dehydration import (
    build_example_flowsheet as build_gas_2,
)
from examples.unit_process_flowsheet.gas_3_jt_low_temperature_separation import (
    build_example_flowsheet as build_gas_3,
)
from examples.unit_process_flowsheet.gas_4_condensate_stabilizer import (
    build_example_flowsheet as build_gas_4,
)
from examples.van_de_vusse_cstr.run_simulation import run_demo as run_van_de_vusse_demo
from modular_simulation.gameplay.sandbox_session import (
    SandboxSessionRuntime,
    _SANDBOX_UNLOCKED_PROGRESSION,
)


def test_van_de_vusse_cstr_run_demo_smoke() -> None:
    result = run_van_de_vusse_demo()
    duration_hours = cast(float, result["duration_hours"])
    system_labels = cast(tuple[str, ...], result["system_labels"])
    final_ca = cast(float, result["final_Ca"])
    final_cb = cast(float, result["final_Cb"])
    final_t = cast(float, result["final_T"])
    final_tk = cast(float, result["final_Tk"])
    final_tj_in = cast(float, result["final_Tj_in"])

    assert duration_hours == 120.0
    assert system_labels == ("normal",)
    assert 0.0 <= final_ca < 5.1
    assert 0.0 <= final_cb < 5.1
    assert 0.0 < final_tk < final_t < 300.0
    assert 10.0 <= final_tj_in <= 110.0


def test_curated_heater_flash_example_smoke() -> None:
    result = run_heater_flash_example(steps=12, dt=0.2, make_plot=False)
    vapor_fraction = cast(float, result["flash_vapor_fraction"])
    vapor_flow = cast(float, result["estimated_flash_vapor_flow_mol_s"])
    liquid_flow = cast(float, result["flash_liquid_flow_mol_s"])
    assert 0.0 < vapor_fraction < 1.0
    assert vapor_flow > 0.0
    assert liquid_flow >= 0.0


def test_curated_dual_feed_exchanger_example_smoke() -> None:
    result = run_dual_feed_exchanger_example(steps=12, dt=0.2, make_plot=False)
    hot_outlet_temperature = cast(float, result["hot_outlet_temperature_K"])
    cold_outlet_temperature = cast(float, result["cold_outlet_temperature_K"])
    heat_duty = cast(float, result["heat_duty_W"])
    assert hot_outlet_temperature > 0.0
    assert cold_outlet_temperature > 0.0
    assert heat_duty != 0.0


def test_curated_dual_feed_exchanger_runs_without_dangling_outlet_warnings() -> None:
    """Regression: easy_3 must be a fully grounded topology with no dangling exchanger outlets."""
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        run_dual_feed_exchanger_example(steps=4, dt=0.2, make_plot=False)


def test_curated_ammonia_recycle_example_smoke() -> None:
    topology_results = build_ammonia_loop_flowsheet(dt=0.2).run(steps=4, dt=0.2)
    recycle_leg = topology_results.get_stream("purge_split.recycle", "synthesis_mixer.recycle")
    assert recycle_leg.flow_rate.shape == (4,)
    with pytest.raises(
        ValueError, match="unknown stream connection 'recycle_return->synthesis_mixer.recycle'"
    ):
        _ = topology_results.get_stream("recycle_return", "synthesis_mixer.recycle")

    result = run_ammonia_loop_example(steps=60, dt=0.2, make_plot=False)
    recycle_ratio = cast(float, result["recycle_to_fresh_ratio"])
    recycle_flow = cast(float, result["recycle_edge_flow_mol_s"])
    product_purity = cast(float, result["liquid_product_purity"])
    product_flow = cast(float, result["liquid_product_flow_mol_s"])
    recycle_pump_id = cast(str, result["recycle_pump_id"])
    assert recycle_flow >= 0.0
    assert recycle_ratio >= 0.0
    assert 0.0 <= product_purity <= 1.0
    assert product_flow >= 0.0
    assert recycle_pump_id == "recycle_pump"


def test_curated_two_tank_comparison_smoke() -> None:
    result = run_two_tank_demo()
    max_abs_error_a = cast(float, result.max_abs_error_a)
    max_abs_error_b = cast(float, result.max_abs_error_b)
    monotonic_decay_a = cast(bool, result.monotonic_decay_a)
    monotonic_decay_b = cast(bool, result.monotonic_decay_b)
    assert max_abs_error_a < 1.0e-6
    assert max_abs_error_b < 1.0e-2
    assert monotonic_decay_a is True
    assert monotonic_decay_b is True


def test_gas_example_stage_topologies_smoke() -> None:
    gas_1 = build_gas_1(dt=0.2)
    gas_2 = build_gas_2(dt=0.2)
    gas_3 = build_gas_3(dt=0.2)
    gas_4 = build_gas_4(dt=0.2)

    # Stage 1 has the separator outputs required for research mix.
    gas_1.run(steps=2, dt=0.2)
    assert "separator_gas" in gas_1._sinks
    assert "unstabilized_condensate" in gas_1._sinks

    # Stage 2 contains dehydration package proxies and dry-gas sink.
    gas_2.run(steps=2, dt=0.2)
    assert "dry_gas" in gas_2._sinks
    assert "teg_contactor" in gas_2._units
    assert "rich_flash" in gas_2._units
    assert "lean_rich_exchanger" in gas_2._units
    assert "teg_regenerator" in gas_2._units
    glycol_loop = next(conn for conn in gas_2._connections if conn.line_id == "glycol_loop")
    assert glycol_loop.pump is not None
    assert glycol_loop.pump.id == "glycol_pump"
    assert glycol_loop.source == "lean_rich_exchanger.cold_outlet"
    assert glycol_loop.target == "teg_regenerator.inlet"

    teg_to_dry = next(conn for conn in gas_2._connections if conn.target == "dry_gas.inlet")
    assert teg_to_dry.source == "teg_contactor.outlet_1"

    # Stage 3 demonstrates JT/LTS proxy chain.
    gas_3.run(steps=2, dt=0.2)
    assert "ngl_liquids" in gas_3._sinks
    assert "gas_gas_exchanger" in gas_3._units
    assert "low_temperature_separator" in gas_3._units
    jt_to_lts = next(conn for conn in gas_3._connections if conn.line_id == "jt_lts_feed")
    assert jt_to_lts.valve is not None
    assert jt_to_lts.valve.id == "jt_valve"
    assert jt_to_lts.source == "gas_gas_exchanger.hot_outlet"
    assert jt_to_lts.target == "low_temperature_separator.inlet"

    teg_to_hx = next(
        conn for conn in gas_3._connections if conn.target == "gas_gas_exchanger.hot_inlet"
    )
    assert teg_to_hx.source == "teg_contactor.outlet_1"

    # Stage 4 demonstrates condensate stabilization proxy wiring.
    assert "stabilized_condensate" in gas_4._sinks
    assert "condensate_stabilizer" in gas_4._units
    stab_feed = next(
        conn for conn in gas_4._connections if conn.target == "condensate_stabilizer.feed_1"
    )
    assert stab_feed.source == "inlet_separator.liquid_outlet"


def test_stage3_runtime_reachability_produces_ngl_liquids_post_unlock() -> None:
    runtime = SandboxSessionRuntime()
    runtime.start_sandbox()
    runtime._state.progression_snapshot = _SANDBOX_UNLOCKED_PROGRESSION

    for item_id, config in (
        ("place_inlet_gas_separator", {"process_id": "inlet_separator"}),
        ("place_teg_contactor", {"process_id": "teg_contactor"}),
        ("place_gas_gas_exchanger", {"process_id": "gas_gas_exchanger"}),
        (
            "place_low_temperature_separator",
            {"process_id": "low_temperature_separator"},
        ),
        (
            "build_process_line",
            {"source": "sweet_wet_gas", "target": "inlet_separator.inlet", "line_id": "a"},
        ),
        (
            "build_process_line",
            {
                "source": "inlet_separator.vapor_outlet",
                "target": "teg_contactor.inlet",
                "line_id": "b",
            },
        ),
        (
            "build_process_line",
            {
                "source": "teg_contactor.outlet_1",
                "target": "gas_gas_exchanger.hot_inlet",
                "line_id": "c",
            },
        ),
        (
            "build_process_line",
            {
                "source": "gas_gas_exchanger.hot_outlet",
                "target": "low_temperature_separator.inlet",
                "line_id": "d",
            },
        ),
        (
            "install_jt_valve",
            {"line_id": "d", "valve_id": "jt_1"},
        ),
        (
            "build_process_line",
            {
                "source": "low_temperature_separator.liquid_outlet",
                "target": "ngl_liquids",
                "line_id": "e",
            },
        ),
    ):
        runtime.install_catalog_item(item_id, config=config, equipment_receipt_id="receipt")

    runtime.load_feed_inventory("sweet_wet_gas", 10.0, procurement_receipt_id="feed")
    step = runtime.advance(1.0)
    assert step.product_production_by_product_id.get("ngl_liquids", 0.0) > 0.0

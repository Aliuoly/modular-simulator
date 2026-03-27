from __future__ import annotations

import inspect
import math
from importlib import import_module
from typing import Any
from unittest.mock import MagicMock

import pytest


REQUIRED_SIMULATION_METHODS = (
    "start_sandbox",
    "start_tutorial",
    "install_catalog_item",
    "load_feed_inventory",
    "advance",
    "withdraw_product_inventory",
    "submit_research_unlock",
    "get_simulation_state",
)


def _sandbox_error_type():
    contracts = import_module("modular_simulation.gameplay.contracts")
    return getattr(contracts, "SandboxRequestError")


def _has_required_session_methods(candidate: object) -> bool:
    return all(callable(getattr(candidate, method, None)) for method in REQUIRED_SIMULATION_METHODS)


def _try_build(candidate: Any) -> Any:
    """Try to call a callable, supplying MagicMock stubs for every required parameter.

    This allows discovery of DI-style factories and classes that require injected
    dependencies, without constraining what those dependencies must be.
    """
    sig = inspect.signature(candidate)
    kwargs: dict[str, Any] = {}
    for param_name, param in sig.parameters.items():
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue
        if param.default is inspect.Parameter.empty:
            kwargs[param_name] = MagicMock()
    try:
        return candidate(**kwargs)
    except Exception:
        return None


def _session_api() -> Any:
    """Discover the sandbox session API surface without constraining implementation shape.

    Accepts any of:
    (a) The module itself has all required methods directly.
    (b) Any public non-callable exported object that directly has all required methods.
    (c) Any public callable in the module — tried with MagicMock stubs for all required
        parameters (supports no-arg, default-arg, and DI-injected factories/classes).
    """
    module = import_module("modular_simulation.gameplay.sandbox_session")

    # (a) Module-level methods
    if _has_required_session_methods(module):
        return module

    for name in dir(module):
        if name.startswith("_"):
            continue
        candidate = getattr(module, name)

        # (b) Non-callable exported object with required methods
        if not callable(candidate) and _has_required_session_methods(candidate):
            return candidate

        # (c) Any callable — attempt construction with mock stubs for required params
        if callable(candidate):
            built = _try_build(candidate)
            if built is not None and _has_required_session_methods(built):
                return built

    raise AssertionError(
        "modular_simulation.gameplay.sandbox_session exposes no public API surface "
        "with the frozen simulation-session methods"
    )


def _build_starter_gas_paths(api: Any, *, connected_support: bool = True) -> None:
    def _install(item_id: str, config: dict[str, object]) -> None:
        api.install_catalog_item(item_id, config=config, equipment_receipt_id="helper-receipt")

    _install("place_inlet_gas_separator", {"process_id": "sep_1"})
    _install("place_teg_contactor", {"process_id": "cont_1"})
    _install("build_process_line", {"source": "sweet_wet_gas", "target": "sep_1.inlet"})
    _install("build_process_line", {"source": "sep_1.vapor_outlet", "target": "separator_gas"})
    _install(
        "build_process_line",
        {"source": "sep_1.liquid_outlet", "target": "unstabilized_condensate"},
    )
    _install("build_process_line", {"source": "sep_1.vapor_outlet", "target": "cont_1.inlet"})
    _install("build_process_line", {"source": "cont_1.outlet_1", "target": "dry_gas"})

    _install("place_rich_glycol_flash_tank", {"process_id": "rgf_1"})
    _install("place_lean_rich_glycol_exchanger", {"process_id": "lre_1"})
    _install("place_teg_regenerator", {"process_id": "reg_1"})

    if connected_support:
        _install(
            "install_glycol_circulation_pump",
            {"line_id": "line_1", "pump_id": "glycol_pump_1"},
        )
        _install("build_process_line", {"source": "sep_1.liquid_outlet", "target": "rgf_1.inlet"})
        _install(
            "build_process_line", {"source": "rgf_1.liquid_outlet", "target": "lre_1.hot_inlet"}
        )
        _install("build_process_line", {"source": "lre_1.hot_outlet", "target": "reg_1.feed_1"})


def test_simulation_api_surface_is_frozen() -> None:
    api = _session_api()
    assert (
        tuple(name for name in REQUIRED_SIMULATION_METHODS if callable(getattr(api, name, None)))
        == REQUIRED_SIMULATION_METHODS
    )


def test_public_runtime_class_is_instance_backed_and_isolated() -> None:
    module = import_module("modular_simulation.gameplay.sandbox_session")
    runtime_cls = getattr(module, "SandboxSessionRuntime", None)

    assert runtime_cls is not None
    runtime_a = runtime_cls()
    runtime_b = runtime_cls()
    assert _has_required_session_methods(runtime_a)
    assert _has_required_session_methods(runtime_b)

    runtime_a.start_sandbox()

    error_type = _sandbox_error_type()
    with pytest.raises(error_type) as no_active:
        runtime_b.get_simulation_state()
    assert no_active.value.error_code == "no_active_session"


def test_start_sandbox_uses_frozen_start_id() -> None:
    api = _session_api()
    snapshot = api.start_sandbox()
    assert snapshot.session_kind == "sandbox"
    assert snapshot.active_start_id == "phase1_process_sandbox_v1"
    assert snapshot.active_tutorial_id is None


def test_start_sandbox_exposes_starter_batch_progression_snapshot() -> None:
    api = _session_api()
    snapshot = api.start_sandbox()

    progression = snapshot.progression_snapshot
    assert progression.active_stage_id == "teg_dehydration_v1"
    assert progression.unlocked_stage_ids == (
        "gas_inlet_separation_v1",
        "teg_dehydration_v1",
    )
    assert progression.available_item_ids == (
        "place_inlet_gas_separator",
        "place_teg_contactor",
        "place_rich_glycol_flash_tank",
        "place_lean_rich_glycol_exchanger",
        "place_teg_regenerator",
        "install_glycol_circulation_pump",
        "build_process_line",
    )
    assert progression.available_research_ids == ("unlock_cold_recovery_train_v1",)


def test_tutorial_snapshot_progression_is_none() -> None:
    api = _session_api()
    snapshot = api.start_tutorial("heater_flash_guided_build_v1")
    assert snapshot.progression_snapshot is None


@pytest.mark.parametrize(
    ("tutorial_id", "expected_start_id"),
    [
        ("heater_flash_guided_build_v1", "heater_flash_tutorial_start_v1"),
        ("reactor_control_fixup_v1", "reactor_control_tutorial_start_v1"),
        ("recycle_purge_tradeoff_v1", "recycle_purge_tutorial_start_v1"),
    ],
)
def test_start_tutorial_uses_bound_start_id(tutorial_id: str, expected_start_id: str) -> None:
    api = _session_api()
    snapshot = api.start_tutorial(tutorial_id)
    assert snapshot.session_kind == "tutorial"
    assert snapshot.active_tutorial_id == tutorial_id
    assert snapshot.active_start_id == expected_start_id


def test_unknown_tutorial_is_rejected_with_stable_error_code() -> None:
    api = _session_api()
    error_type = _sandbox_error_type()

    with pytest.raises(error_type) as exc_info:
        api.start_tutorial("unknown_tutorial")
    assert exc_info.value.error_code == "unknown_tutorial"
    assert isinstance(exc_info.value.message, str)


def test_submit_research_unlock_rejection_codes_are_stable() -> None:
    api = _session_api()
    error_type = _sandbox_error_type()

    with pytest.raises(error_type) as no_active:
        api.submit_research_unlock(
            "unlock_cold_recovery_train_v1",
            submitted_quantities_by_product_id={
                "separator_gas": 20.0,
                "unstabilized_condensate": 10.0,
                "dry_gas": 20.0,
            },
        )
    assert no_active.value.error_code == "no_active_session"

    tutorial_api = _session_api()
    tutorial_api.start_tutorial("heater_flash_guided_build_v1")
    with pytest.raises(error_type) as tutorial_research:
        tutorial_api.submit_research_unlock(
            "unlock_cold_recovery_train_v1",
            submitted_quantities_by_product_id={
                "separator_gas": 20.0,
                "unstabilized_condensate": 10.0,
                "dry_gas": 20.0,
            },
        )
    assert tutorial_research.value.error_code == "research_unavailable_for_session"

    api.start_sandbox()

    with pytest.raises(error_type) as unknown_research:
        api.submit_research_unlock(
            "unknown_research",
            submitted_quantities_by_product_id={
                "separator_gas": 20.0,
                "unstabilized_condensate": 10.0,
                "dry_gas": 20.0,
            },
        )
    assert unknown_research.value.error_code == "unknown_research_unlock"

    with pytest.raises(error_type) as invalid_quantity:
        api.submit_research_unlock(
            "unlock_cold_recovery_train_v1",
            submitted_quantities_by_product_id={
                "separator_gas": 20.0,
                "unstabilized_condensate": 10.0,
            },
        )
    assert invalid_quantity.value.error_code == "invalid_quantity"

    with pytest.raises(error_type) as insufficient_inventory:
        api.submit_research_unlock(
            "unlock_cold_recovery_train_v1",
            submitted_quantities_by_product_id={
                "separator_gas": 20.0,
                "unstabilized_condensate": 10.0,
                "dry_gas": 20.0,
            },
        )
    assert insufficient_inventory.value.error_code == "insufficient_product_inventory"

    api.load_feed_inventory("sweet_wet_gas", 100.0)
    _build_starter_gas_paths(api)
    api.advance(100.0)

    api.submit_research_unlock(
        "unlock_cold_recovery_train_v1",
        submitted_quantities_by_product_id={
            "separator_gas": 20.0,
            "unstabilized_condensate": 10.0,
            "dry_gas": 20.0,
        },
    )

    with pytest.raises(error_type) as unavailable:
        api.submit_research_unlock(
            "unlock_cold_recovery_train_v1",
            submitted_quantities_by_product_id={
                "separator_gas": 20.0,
                "unstabilized_condensate": 10.0,
                "dry_gas": 20.0,
            },
        )
    assert unavailable.value.error_code == "research_not_available"


def test_submit_research_unlock_success_advances_progression_snapshot() -> None:
    api = _session_api()
    api.start_sandbox()
    api.load_feed_inventory("sweet_wet_gas", 100.0)
    _build_starter_gas_paths(api)
    api.advance(100.0)

    result = api.submit_research_unlock(
        "unlock_cold_recovery_train_v1",
        submitted_quantities_by_product_id={
            "separator_gas": 20.0,
            "unstabilized_condensate": 10.0,
            "dry_gas": 20.0,
        },
    )
    assert result.success is True
    assert result.reason_code is None
    progression = result.snapshot.progression_snapshot

    assert progression.active_stage_id == "condensate_stabilization_v1"
    assert progression.unlocked_stage_ids == (
        "gas_inlet_separation_v1",
        "teg_dehydration_v1",
        "jt_low_temperature_separation_v1",
        "condensate_stabilization_v1",
    )
    assert progression.available_item_ids == (
        "place_inlet_gas_separator",
        "place_teg_contactor",
        "place_rich_glycol_flash_tank",
        "place_lean_rich_glycol_exchanger",
        "place_teg_regenerator",
        "install_glycol_circulation_pump",
        "place_gas_gas_exchanger",
        "install_jt_valve",
        "place_low_temperature_separator",
        "place_condensate_stabilizer",
        "build_process_line",
    )
    assert progression.available_research_ids == ()


def test_submit_research_rejection_does_not_consume_inventory() -> None:
    api = _session_api()
    error_type = _sandbox_error_type()
    api.start_sandbox()
    api.load_feed_inventory("sweet_wet_gas", 100.0)
    _build_starter_gas_paths(api)
    api.advance(100.0)
    before = api.get_simulation_state().product_inventory_by_product_id

    with pytest.raises(error_type) as invalid_quantity:
        api.submit_research_unlock(
            "unlock_cold_recovery_train_v1",
            submitted_quantities_by_product_id={
                "separator_gas": 20.0,
                "unstabilized_condensate": 10.0,
            },
        )
    assert invalid_quantity.value.error_code == "invalid_quantity"

    after = api.get_simulation_state().product_inventory_by_product_id
    assert after == before


def test_start_sandbox_uses_gas_first_feed_and_product_ids() -> None:
    api = _session_api()
    snapshot = api.start_sandbox()
    assert tuple(snapshot.feed_inventory_by_material_id.keys()) == ("sweet_wet_gas",)
    assert tuple(snapshot.product_inventory_by_product_id.keys()) == (
        "separator_gas",
        "unstabilized_condensate",
        "dry_gas",
        "ngl_liquids",
        "stabilized_condensate",
    )


def test_install_catalog_item_rejection_codes_are_stable() -> None:
    api = _session_api()
    error_type = _sandbox_error_type()

    with pytest.raises(error_type) as no_active:
        api.install_catalog_item("place_heater_cooler", config={})
    assert no_active.value.error_code == "no_active_session"

    api.start_sandbox()

    with pytest.raises(error_type) as unknown_item:
        api.install_catalog_item("unknown_item", config={})
    assert unknown_item.value.error_code == "unknown_item"

    with pytest.raises(error_type) as unsupported:
        tutorial_api = _session_api()
        tutorial_api.start_tutorial("heater_flash_guided_build_v1")
        tutorial_api.install_catalog_item("place_inlet_gas_separator", config={})
    assert unsupported.value.error_code == "unsupported_on_start"

    with pytest.raises(error_type) as invalid_config:
        api.install_catalog_item("build_process_line", config={"length_m": 1.0})
    assert invalid_config.value.error_code == "invalid_config"


def test_new_foundation_items_are_unsupported_on_start_in_sandbox() -> None:
    """Wave-1 red guard: place_holding_tank and place_quality_control_lab must be
    rejected as unsupported_on_start when attempted in phase1_process_sandbox_v1.

    Both items are catalog-only in this pack (supported_start_ids=()); no current
    start allowlist gains them.  No new session API method or progression snapshot
    is introduced by this pack, so REQUIRED_SIMULATION_METHODS must stay frozen.
    """
    api = _session_api()
    error_type = _sandbox_error_type()

    # Guard: session API surface must not grow — no new methods from this pack.
    assert (
        tuple(name for name in REQUIRED_SIMULATION_METHODS if callable(getattr(api, name, None)))
        == REQUIRED_SIMULATION_METHODS
    ), "session API surface must not gain new methods from this pack"

    api.start_sandbox()

    with pytest.raises(error_type) as holding_tank_exc:
        api.install_catalog_item("place_holding_tank", config={})
    assert holding_tank_exc.value.error_code == "unsupported_on_start"

    with pytest.raises(error_type) as qc_lab_exc:
        api.install_catalog_item("place_quality_control_lab", config={})
    assert qc_lab_exc.value.error_code == "unsupported_on_start"


def test_shortcut_distillation_foundation_item_is_unsupported_on_topology_only_starts() -> None:
    api = _session_api()
    error_type = _sandbox_error_type()

    api.start_sandbox()

    with pytest.raises(error_type) as shortcut_exc:
        api.install_catalog_item("place_shortcut_distillation_column", config={})
    assert shortcut_exc.value.error_code == "unsupported_on_start"


def test_install_requires_equipment_receipt_id_when_ledger_active() -> None:
    api = _session_api()
    economics = import_module("modular_simulation.gameplay.economics")
    error_type = _sandbox_error_type()

    if callable(getattr(economics, "open_cash_ledger", None)):
        economics.open_cash_ledger()
    else:
        for name in dir(economics):
            if name.startswith("_"):
                continue
            candidate = getattr(economics, name)
            if callable(candidate):
                built: Any = _try_build(candidate)
                if built is not None and callable(getattr(built, "open_cash_ledger", None)):
                    built.open_cash_ledger()
                    break

    api.start_sandbox()
    with pytest.raises(error_type) as missing_receipt:
        api.install_catalog_item("build_process_line", config={"length_m": 3.0, "radius_m": 0.05})
    assert missing_receipt.value.error_code == "missing_equipment_receipt"


def test_gameplay_surface_still_excludes_controller_installation() -> None:
    realtime_service = import_module("modular_simulation.gameplay.realtime_service")

    assert tuple(realtime_service.SUPPORTED_BUILD_ITEM_IDS) == (
        "place_inlet_gas_separator",
        "place_teg_contactor",
        "place_rich_glycol_flash_tank",
        "place_lean_rich_glycol_exchanger",
        "place_teg_regenerator",
        "install_glycol_circulation_pump",
        "build_process_line",
    )
    assert "install_pid_controller" not in realtime_service.SUPPORTED_BUILD_ITEM_IDS, (
        "Controller proof remains deferred to ModularSimulator-9tr.6; "
        "the current realtime gameplay surface must stay frozen to the build slice."
    )


def test_feed_load_rejection_codes_are_stable() -> None:
    api = _session_api()
    error_type = _sandbox_error_type()

    with pytest.raises(error_type) as no_active:
        api.load_feed_inventory("sweet_wet_gas", 1.0)
    assert no_active.value.error_code == "no_active_session"

    api.start_sandbox()

    with pytest.raises(error_type) as unknown_material:
        api.load_feed_inventory("unknown_material", 1.0)
    assert unknown_material.value.error_code == "unknown_material"

    with pytest.raises(error_type) as invalid_quantity:
        api.load_feed_inventory("sweet_wet_gas", 0.0)
    assert invalid_quantity.value.error_code == "invalid_quantity"

    api.start_tutorial("heater_flash_guided_build_v1")
    with pytest.raises(error_type) as tutorial_disabled:
        api.load_feed_inventory("sweet_wet_gas", 1.0)
    assert tutorial_disabled.value.error_code == "tutorial_feed_loading_disabled"


def test_feed_load_requires_procurement_receipt_id_when_ledger_active() -> None:
    api = _session_api()
    economics = import_module("modular_simulation.gameplay.economics")
    error_type = _sandbox_error_type()

    if callable(getattr(economics, "open_cash_ledger", None)):
        economics.open_cash_ledger()
    else:
        for name in dir(economics):
            if name.startswith("_"):
                continue
            candidate = getattr(economics, name)
            if callable(candidate):
                built: Any = _try_build(candidate)
                if built is not None and callable(getattr(built, "open_cash_ledger", None)):
                    built.open_cash_ledger()
                    break

    api.start_sandbox()
    with pytest.raises(error_type) as missing_receipt:
        api.load_feed_inventory("sweet_wet_gas", 1.0)
    assert missing_receipt.value.error_code == "missing_procurement_receipt"


def test_advance_rejection_codes_are_stable() -> None:
    api = _session_api()
    error_type = _sandbox_error_type()

    with pytest.raises(error_type) as no_active:
        api.advance(1.0)
    assert no_active.value.error_code == "no_active_session"

    api.start_sandbox()
    for invalid_dt in (0.0, -1.0, math.inf, float("nan")):
        with pytest.raises(error_type) as invalid_dt_exc:
            api.advance(invalid_dt)
        assert invalid_dt_exc.value.error_code == "invalid_dt_s"

    with pytest.raises(error_type) as insufficient_feed:
        api.advance(1.0)
    assert insufficient_feed.value.error_code == "insufficient_feed_inventory"

    api.load_feed_inventory("sweet_wet_gas", 0.5)
    with pytest.raises(error_type) as partial_feed:
        api.advance(1.0)
    assert partial_feed.value.error_code == "insufficient_feed_inventory"


def test_withdraw_rejection_codes_and_handoff_token_shape_are_stable() -> None:
    api = _session_api()
    error_type = _sandbox_error_type()

    with pytest.raises(error_type) as no_active:
        api.withdraw_product_inventory("separator_gas", 1.0)
    assert no_active.value.error_code == "no_active_session"

    api.start_sandbox()
    with pytest.raises(error_type) as unknown_product:
        api.withdraw_product_inventory("unknown_product", 1.0)
    assert unknown_product.value.error_code == "unknown_product"

    with pytest.raises(error_type) as invalid_quantity:
        api.withdraw_product_inventory("separator_gas", 0.0)
    assert invalid_quantity.value.error_code == "invalid_quantity"

    with pytest.raises(error_type) as insufficient_product:
        api.withdraw_product_inventory("separator_gas", 1.0)
    assert insufficient_product.value.error_code == "insufficient_product_inventory"


def test_advance_and_withdraw_surface_inventory_deltas_and_stable_withdrawal_id() -> None:
    api = _session_api()

    api.start_sandbox()
    _build_starter_gas_paths(api)
    api.load_feed_inventory("sweet_wet_gas", 50.0)
    advance_result = api.advance(1.0)

    assert isinstance(advance_result.feed_consumption_by_material_id, dict)
    assert isinstance(advance_result.product_production_by_product_id, dict)
    assert isinstance(advance_result.published_signal_values_by_id, dict)

    produced = next(iter(advance_result.product_production_by_product_id.keys()))
    withdrawn = api.withdraw_product_inventory(produced, 0.1)
    assert isinstance(withdrawn.withdrawal_id, str)
    assert withdrawn.withdrawal_id
    assert withdrawn.withdrawn_quantity_mol == pytest.approx(0.1)


def test_withdrawal_handoff_token_can_be_sold_once_via_economics() -> None:
    api = _session_api()
    economics = import_module("modular_simulation.gameplay.economics")
    error_type = _sandbox_error_type()

    economics.open_cash_ledger(initial_cash=5_000.0)
    api.start_sandbox()

    equipment_receipt = economics.record_equipment_purchase(
        "build_process_line",
        config={"length_m": 3.0, "radius_m": 0.05},
    )
    api.install_catalog_item(
        "build_process_line",
        config={"length_m": 3.0, "radius_m": 0.05},
        equipment_receipt_id=equipment_receipt.receipt_id,
    )
    _build_starter_gas_paths(api)

    feed_receipt = economics.record_feed_purchase("feed_a", quantity_mol=2.0)
    api.load_feed_inventory(
        "sweet_wet_gas",
        2.0,
        procurement_receipt_id=feed_receipt.receipt_id,
    )

    api.advance(1.0)
    withdrawal = api.withdraw_product_inventory("separator_gas", 0.1)

    sale = economics.record_product_sale(withdrawal.withdrawal_id)
    assert sale.withdrawal_id == withdrawal.withdrawal_id
    assert sale.product_id == "separator_gas"
    assert sale.quantity_mol == pytest.approx(0.1)
    assert sale.gross_revenue == pytest.approx(0.6)

    with pytest.raises(error_type) as replay_error:
        economics.record_product_sale(withdrawal.withdrawal_id)
    assert replay_error.value.error_code == "unknown_withdrawal_id"


def test_runtime_composition_requires_receipts_with_open_cash_ledger_runtime() -> None:
    sandbox = import_module("modular_simulation.gameplay.sandbox_session")
    economics = import_module("modular_simulation.gameplay.economics")
    error_type = _sandbox_error_type()

    ledger = economics.CashLedgerRuntime()
    ledger.open_cash_ledger(initial_cash=500.0)
    api = sandbox.SandboxSessionRuntime(economics_api=ledger)
    api.start_sandbox()

    with pytest.raises(error_type) as missing_equipment:
        api.install_catalog_item("build_process_line", config={"length_m": 3.0, "radius_m": 0.05})
    assert missing_equipment.value.error_code == "missing_equipment_receipt"

    with pytest.raises(error_type) as missing_feed:
        api.load_feed_inventory("sweet_wet_gas", 1.0)
    assert missing_feed.value.error_code == "missing_procurement_receipt"


def test_runtime_withdrawals_register_handoff_on_injected_cash_ledger_runtime() -> None:
    sandbox = import_module("modular_simulation.gameplay.sandbox_session")
    economics = import_module("modular_simulation.gameplay.economics")
    error_type = _sandbox_error_type()

    ledger = economics.CashLedgerRuntime()
    ledger.open_cash_ledger(initial_cash=5_000.0)
    api = sandbox.SandboxSessionRuntime(economics_api=ledger)
    api.start_sandbox()

    equipment_receipt = ledger.record_equipment_purchase(
        "build_process_line",
        config={"length_m": 3.0, "radius_m": 0.05},
    )
    api.install_catalog_item(
        "build_process_line",
        config={"length_m": 3.0, "radius_m": 0.05},
        equipment_receipt_id=equipment_receipt.receipt_id,
    )
    _build_starter_gas_paths(api)

    feed_receipt = ledger.record_feed_purchase("feed_a", quantity_mol=2.0)
    api.load_feed_inventory(
        "sweet_wet_gas",
        2.0,
        procurement_receipt_id=feed_receipt.receipt_id,
    )

    api.advance(1.0)
    withdrawal = api.withdraw_product_inventory("separator_gas", 0.1)

    sale = ledger.record_product_sale(withdrawal.withdrawal_id)
    assert sale.withdrawal_id == withdrawal.withdrawal_id
    assert sale.product_id == "separator_gas"
    assert sale.quantity_mol == pytest.approx(0.1)
    assert sale.gross_revenue == pytest.approx(0.6)

    with pytest.raises(error_type) as replay_error:
        ledger.record_product_sale(withdrawal.withdrawal_id)
    assert replay_error.value.error_code == "unknown_withdrawal_id"


def test_module_open_ledger_does_not_affect_fresh_isolated_runtime() -> None:
    sandbox = import_module("modular_simulation.gameplay.sandbox_session")
    economics = import_module("modular_simulation.gameplay.economics")

    economics.open_cash_ledger(initial_cash=5_000.0)
    api = sandbox.SandboxSessionRuntime()
    api.start_sandbox()

    install_result = api.install_catalog_item(
        "build_process_line", config={"length_m": 3.0, "radius_m": 0.05}
    )
    assert install_result.success is True

    load_result = api.load_feed_inventory("sweet_wet_gas", 1.0)
    assert load_result.success is True


def test_snapshot_exposes_tutorial_completion_time_and_not_score() -> None:
    api = _session_api()

    tutorial_snapshot = api.start_tutorial("heater_flash_guided_build_v1")
    assert hasattr(tutorial_snapshot, "tutorial_completion_time_s")
    assert not hasattr(tutorial_snapshot, "score")
    assert not hasattr(tutorial_snapshot, "points")


def test_advance_increases_elapsed_time_and_deltas_match_snapshot_inventory() -> None:
    """advance(dt_s) must increment elapsed_time_s by exactly dt_s, and the feed
    consumed reported in the advance result must match what is deducted from the
    snapshot's feed inventory; similarly for products produced."""
    api = _session_api()

    api.start_sandbox()
    _build_starter_gas_paths(api)
    api.load_feed_inventory("sweet_wet_gas", 50.0)
    # Capture baseline AFTER loading feed, immediately before advancing,
    # so inventory deltas are relative to the pre-advance state.
    snapshot_before = api.get_simulation_state()
    dt = 5.0
    advance_result = api.advance(dt)
    snapshot_after = api.get_simulation_state()

    # elapsed_time_s increases by exactly dt_s
    assert snapshot_after.elapsed_time_s == pytest.approx(snapshot_before.elapsed_time_s + dt)

    # feed consumed in advance result matches the deduction from the snapshot inventory
    for material_id, consumed_mol in advance_result.feed_consumption_by_material_id.items():
        before_qty = snapshot_before.feed_inventory_by_material_id.get(material_id, 0.0)
        after_qty = snapshot_after.feed_inventory_by_material_id.get(material_id, 0.0)
        assert after_qty == pytest.approx(before_qty - consumed_mol), (
            f"feed inventory delta for {material_id!r} does not match advance result: "
            f"before={before_qty}, consumed={consumed_mol}, after={after_qty}"
        )

    # products produced in advance result matches the addition to the snapshot inventory
    for product_id, produced_mol in advance_result.product_production_by_product_id.items():
        before_qty = snapshot_before.product_inventory_by_product_id.get(product_id, 0.0)
        after_qty = snapshot_after.product_inventory_by_product_id.get(product_id, 0.0)
        assert after_qty == pytest.approx(before_qty + produced_mol), (
            f"product inventory delta for {product_id!r} does not match advance result: "
            f"before={before_qty}, produced={produced_mol}, after={after_qty}"
        )


def test_no_topology_no_products_and_research_stays_unavailable() -> None:
    api = _session_api()
    error_type = _sandbox_error_type()
    api.start_sandbox()
    api.load_feed_inventory("sweet_wet_gas", 100.0)
    step = api.advance(10.0)
    assert step.product_production_by_product_id == {}

    with pytest.raises(error_type) as research_error:
        api.submit_research_unlock(
            "unlock_cold_recovery_train_v1",
            submitted_quantities_by_product_id={
                "separator_gas": 20.0,
                "unstabilized_condensate": 10.0,
                "dry_gas": 20.0,
            },
        )
    assert research_error.value.error_code == "insufficient_product_inventory"


def test_disconnected_dehydration_support_items_do_not_qualify_dry_gas() -> None:
    api = _session_api()
    api.start_sandbox()
    api.install_catalog_item("place_inlet_gas_separator", config={"process_id": "sep_1"})
    api.install_catalog_item("place_teg_contactor", config={"process_id": "cont_1"})
    api.install_catalog_item(
        "build_process_line", config={"source": "sweet_wet_gas", "target": "sep_1.inlet"}
    )
    api.install_catalog_item(
        "build_process_line", config={"source": "sep_1.vapor_outlet", "target": "cont_1.inlet"}
    )
    api.install_catalog_item(
        "build_process_line", config={"source": "cont_1.outlet_1", "target": "dry_gas"}
    )

    # Support items exist but are disconnected from the qualifying path component.
    api.install_catalog_item(
        "place_rich_glycol_flash_tank", config={"process_id": "rgf_disconnected"}
    )
    api.install_catalog_item(
        "place_lean_rich_glycol_exchanger", config={"process_id": "lre_disconnected"}
    )
    api.install_catalog_item("place_teg_regenerator", config={"process_id": "reg_disconnected"})
    api.install_catalog_item(
        "install_glycol_circulation_pump",
        config={"line_id": "line_999", "pump_id": "pump_disconnected"},
    )

    api.load_feed_inventory("sweet_wet_gas", 10.0)
    step = api.advance(1.0)
    assert step.product_production_by_product_id.get("dry_gas", 0.0) == 0.0


def test_separator_gas_requires_vapor_side_not_liquid_side() -> None:
    api = _session_api()
    api.start_sandbox()
    api.install_catalog_item("place_inlet_gas_separator", config={"process_id": "sep_1"})
    api.install_catalog_item(
        "build_process_line", config={"source": "sweet_wet_gas", "target": "sep_1.inlet"}
    )
    api.install_catalog_item(
        "build_process_line", config={"source": "sep_1.liquid_outlet", "target": "separator_gas"}
    )

    api.load_feed_inventory("sweet_wet_gas", 10.0)
    step = api.advance(1.0)
    assert step.product_production_by_product_id.get("separator_gas", 0.0) == pytest.approx(0.0)


def test_dry_gas_requires_teg_contactor_outlet_1_path() -> None:
    api = _session_api()
    api.start_sandbox()
    api.install_catalog_item("place_inlet_gas_separator", config={"process_id": "sep_1"})
    api.install_catalog_item("place_teg_contactor", config={"process_id": "cont_1"})
    api.install_catalog_item(
        "build_process_line", config={"source": "sweet_wet_gas", "target": "sep_1.inlet"}
    )
    api.install_catalog_item(
        "build_process_line", config={"source": "sep_1.vapor_outlet", "target": "cont_1.inlet"}
    )
    api.install_catalog_item(
        "build_process_line", config={"source": "cont_1.outlet_2", "target": "dry_gas"}
    )
    api.install_catalog_item("place_rich_glycol_flash_tank", config={"process_id": "rgf_1"})
    api.install_catalog_item("place_lean_rich_glycol_exchanger", config={"process_id": "lre_1"})
    api.install_catalog_item("place_teg_regenerator", config={"process_id": "reg_1"})
    api.install_catalog_item(
        "install_glycol_circulation_pump", config={"line_id": "line_1", "pump_id": "pump_1"}
    )
    api.install_catalog_item(
        "build_process_line", config={"source": "sep_1.liquid_outlet", "target": "rgf_1.inlet"}
    )
    api.install_catalog_item(
        "build_process_line", config={"source": "rgf_1.liquid_outlet", "target": "lre_1.hot_inlet"}
    )
    api.install_catalog_item(
        "build_process_line", config={"source": "lre_1.hot_outlet", "target": "reg_1.feed_1"}
    )

    api.load_feed_inventory("sweet_wet_gas", 10.0)
    step = api.advance(1.0)
    assert step.product_production_by_product_id.get("dry_gas", 0.0) == pytest.approx(0.0)


def _build_unlocked_stage3_runtime_path(*, jt_line_id: str | None) -> float:
    sandbox = import_module("modular_simulation.gameplay.sandbox_session")
    runtime = sandbox.SandboxSessionRuntime()
    runtime.start_sandbox()
    runtime._state.progression_snapshot = sandbox._SANDBOX_UNLOCKED_PROGRESSION

    for item_id, config in (
        ("place_inlet_gas_separator", {"process_id": "inlet_separator"}),
        ("place_teg_contactor", {"process_id": "teg_contactor"}),
        ("place_gas_gas_exchanger", {"process_id": "gas_gas_exchanger"}),
        (
            "place_low_temperature_separator",
            {"process_id": "low_temperature_separator"},
        ),
    ):
        runtime.install_catalog_item(item_id, config=config, equipment_receipt_id="receipt")

    for item_id, config in (
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
            "build_process_line",
            {
                "source": "low_temperature_separator.liquid_outlet",
                "target": "ngl_liquids",
                "line_id": "e",
            },
        ),
    ):
        runtime.install_catalog_item(item_id, config=config, equipment_receipt_id="receipt")

    if jt_line_id is not None:
        runtime.install_catalog_item(
            "install_jt_valve",
            config={"line_id": jt_line_id, "valve_id": "jt_1"},
            equipment_receipt_id="receipt",
        )

    runtime.load_feed_inventory("sweet_wet_gas", 10.0, procurement_receipt_id="feed")
    step = runtime.advance(1.0)
    return step.product_production_by_product_id.get("ngl_liquids", 0.0)


def test_ngl_requires_jt_valve_on_immediately_upstream_lts_line() -> None:
    assert _build_unlocked_stage3_runtime_path(jt_line_id=None) == pytest.approx(0.0)
    assert _build_unlocked_stage3_runtime_path(jt_line_id="c") == pytest.approx(0.0)
    assert _build_unlocked_stage3_runtime_path(jt_line_id="d") > 0.0

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
        tutorial_api.install_catalog_item("place_heat_exchanger", config={})
    assert unsupported.value.error_code == "unsupported_on_start"

    with pytest.raises(error_type) as invalid_config:
        api.install_catalog_item("build_process_line", config={"length_m": 1.0})
    assert invalid_config.value.error_code == "invalid_config"


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
        api.install_catalog_item("place_heater_cooler", config={})
    assert missing_receipt.value.error_code == "missing_equipment_receipt"


def test_feed_load_rejection_codes_are_stable() -> None:
    api = _session_api()
    error_type = _sandbox_error_type()

    with pytest.raises(error_type) as no_active:
        api.load_feed_inventory("feed_a", 1.0)
    assert no_active.value.error_code == "no_active_session"

    api.start_sandbox()

    with pytest.raises(error_type) as unknown_material:
        api.load_feed_inventory("unknown_material", 1.0)
    assert unknown_material.value.error_code == "unknown_material"

    with pytest.raises(error_type) as invalid_quantity:
        api.load_feed_inventory("feed_a", 0.0)
    assert invalid_quantity.value.error_code == "invalid_quantity"

    api.start_tutorial("heater_flash_guided_build_v1")
    with pytest.raises(error_type) as tutorial_disabled:
        api.load_feed_inventory("feed_a", 1.0)
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
        api.load_feed_inventory("feed_a", 1.0)
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

    api.load_feed_inventory("feed_a", 0.5)
    with pytest.raises(error_type) as partial_feed:
        api.advance(1.0)
    assert partial_feed.value.error_code == "insufficient_feed_inventory"


def test_withdraw_rejection_codes_and_handoff_token_shape_are_stable() -> None:
    api = _session_api()
    error_type = _sandbox_error_type()

    with pytest.raises(error_type) as no_active:
        api.withdraw_product_inventory("product_a", 1.0)
    assert no_active.value.error_code == "no_active_session"

    api.start_sandbox()
    with pytest.raises(error_type) as unknown_product:
        api.withdraw_product_inventory("unknown_product", 1.0)
    assert unknown_product.value.error_code == "unknown_product"

    with pytest.raises(error_type) as invalid_quantity:
        api.withdraw_product_inventory("product_a", 0.0)
    assert invalid_quantity.value.error_code == "invalid_quantity"

    with pytest.raises(error_type) as insufficient_product:
        api.withdraw_product_inventory("product_a", 1.0)
    assert insufficient_product.value.error_code == "insufficient_product_inventory"


def test_advance_and_withdraw_surface_inventory_deltas_and_stable_withdrawal_id() -> None:
    api = _session_api()

    api.start_sandbox()
    api.load_feed_inventory("feed_a", 50.0)
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

    feed_receipt = economics.record_feed_purchase("feed_a", quantity_mol=2.0)
    api.load_feed_inventory(
        "feed_a",
        2.0,
        procurement_receipt_id=feed_receipt.receipt_id,
    )

    api.advance(1.0)
    withdrawal = api.withdraw_product_inventory("product_a", 0.1)

    sale = economics.record_product_sale(withdrawal.withdrawal_id)
    assert sale.withdrawal_id == withdrawal.withdrawal_id
    assert sale.product_id == "product_a"
    assert sale.quantity_mol == pytest.approx(0.1)
    assert sale.gross_revenue == pytest.approx(0.8)

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
        api.install_catalog_item("place_heater_cooler", config={})
    assert missing_equipment.value.error_code == "missing_equipment_receipt"

    with pytest.raises(error_type) as missing_feed:
        api.load_feed_inventory("feed_a", 1.0)
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

    feed_receipt = ledger.record_feed_purchase("feed_a", quantity_mol=2.0)
    api.load_feed_inventory(
        "feed_a",
        2.0,
        procurement_receipt_id=feed_receipt.receipt_id,
    )

    api.advance(1.0)
    withdrawal = api.withdraw_product_inventory("product_a", 0.1)

    sale = ledger.record_product_sale(withdrawal.withdrawal_id)
    assert sale.withdrawal_id == withdrawal.withdrawal_id
    assert sale.product_id == "product_a"
    assert sale.quantity_mol == pytest.approx(0.1)
    assert sale.gross_revenue == pytest.approx(0.8)

    with pytest.raises(error_type) as replay_error:
        ledger.record_product_sale(withdrawal.withdrawal_id)
    assert replay_error.value.error_code == "unknown_withdrawal_id"


def test_module_open_ledger_does_not_affect_fresh_isolated_runtime() -> None:
    sandbox = import_module("modular_simulation.gameplay.sandbox_session")
    economics = import_module("modular_simulation.gameplay.economics")

    economics.open_cash_ledger(initial_cash=5_000.0)
    api = sandbox.SandboxSessionRuntime()
    api.start_sandbox()

    install_result = api.install_catalog_item("place_heater_cooler", config={})
    assert install_result.success is True

    load_result = api.load_feed_inventory("feed_a", 1.0)
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
    api.load_feed_inventory("feed_a", 50.0)
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

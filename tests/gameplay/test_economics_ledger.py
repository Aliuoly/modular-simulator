from __future__ import annotations

import inspect
from importlib import import_module
from typing import Any, Protocol, cast
from unittest.mock import MagicMock

import pytest


REQUIRED_ECONOMICS_METHODS = (
    "open_cash_ledger",
    "quote_equipment_purchase",
    "record_equipment_purchase",
    "quote_feed_purchase",
    "record_feed_purchase",
    "quote_product_sale",
    "record_product_sale",
    "register_product_withdrawal_handoff",
    "record_operating_costs",
    "get_cash_ledger",
    "is_cash_ledger_open",
)


class EconomicsApi(Protocol):
    def open_cash_ledger(self, *, initial_cash: float | None = None) -> Any: ...

    def quote_equipment_purchase(self, item_id: str, *, config: dict[str, object]) -> Any: ...

    def record_equipment_purchase(self, item_id: str, *, config: dict[str, object]) -> Any: ...

    def quote_feed_purchase(self, material_id: str, *, quantity_mol: float) -> Any: ...

    def record_feed_purchase(self, material_id: str, *, quantity_mol: float) -> Any: ...

    def quote_product_sale(self, product_id: str, *, quantity_mol: float) -> Any: ...

    def record_product_sale(self, withdrawal_id: str) -> Any: ...

    def register_product_withdrawal_handoff(
        self,
        withdrawal_id: str,
        *,
        product_id: str,
        quantity_mol: float,
    ) -> None: ...

    def record_operating_costs(
        self, *, dt_s: float, published_signal_values_by_id: dict[str, float]
    ) -> Any: ...

    def get_cash_ledger(self) -> Any: ...

    def is_cash_ledger_open(self) -> bool: ...


def _has_required_methods(candidate: object) -> bool:
    return all(callable(getattr(candidate, method, None)) for method in REQUIRED_ECONOMICS_METHODS)


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


def _economics_api() -> EconomicsApi:
    """Discover the economics API surface without constraining implementation shape.

    Accepts any of:
    (a) The module itself has all required methods directly.
    (b) Any public non-callable exported object that directly has all required methods.
    (c) Any public callable in the module — tried with MagicMock stubs for all required
        parameters (supports no-arg, default-arg, and DI-injected factories/classes).
    """
    module = import_module("modular_simulation.gameplay.economics")

    # (a) Module-level methods
    if _has_required_methods(module):
        return cast(EconomicsApi, module)

    for name in dir(module):
        if name.startswith("_"):
            continue
        candidate = getattr(module, name)

        # (b) Non-callable exported object with required methods
        if not callable(candidate) and _has_required_methods(candidate):
            return cast(EconomicsApi, candidate)

        # (c) Any callable — attempt construction with mock stubs for required params
        if callable(candidate):
            built = _try_build(candidate)
            if built is not None and _has_required_methods(built):
                return cast(EconomicsApi, built)

    raise AssertionError(
        "modular_simulation.gameplay.economics exposes no public API surface "
        "with the frozen economics-ledger methods"
    )


def _sandbox_error_type():
    contracts = import_module("modular_simulation.gameplay.contracts")
    return getattr(contracts, "SandboxRequestError")


def test_economics_api_surface_is_frozen() -> None:
    api = _economics_api()
    assert tuple(
        name for name in REQUIRED_ECONOMICS_METHODS if callable(getattr(api, name, None))
    ) == (REQUIRED_ECONOMICS_METHODS)


def test_default_cash_ledger_open_balance_is_frozen() -> None:
    api = _economics_api()
    ledger = api.open_cash_ledger()
    assert ledger.cash_balance == 900.0


def test_public_cash_ledger_runtime_is_instance_backed() -> None:
    economics = import_module("modular_simulation.gameplay.economics")
    runtime_type = getattr(economics, "CashLedgerRuntime")

    runtime_a = runtime_type()
    runtime_b = runtime_type()

    assert runtime_a.is_cash_ledger_open() is False
    assert runtime_b.is_cash_ledger_open() is False

    runtime_a.open_cash_ledger(initial_cash=50.0)
    assert runtime_a.get_cash_ledger().cash_balance == pytest.approx(50.0)
    assert runtime_b.is_cash_ledger_open() is False


def test_module_level_api_remains_compatible_with_handoff_registration() -> None:
    api = _economics_api()
    api.open_cash_ledger(initial_cash=100.0)
    api.register_product_withdrawal_handoff(
        "w1",
        product_id="product_a",
        quantity_mol=2.0,
    )

    sale = api.record_product_sale("w1")
    assert sale.gross_revenue == pytest.approx(16.0)


@pytest.mark.parametrize(
    ("item_id", "config", "expected_amount", "expected_rule_ids"),
    [
        (
            "place_heater_cooler",
            {},
            145.0,
            ("lang_factor_fluid_processing", "six_tenths_scaling"),
        ),
        (
            "place_flash_drum",
            {},
            185.6,
            ("lang_factor_fluid_processing", "six_tenths_scaling"),
        ),
        (
            "place_heat_exchanger",
            {},
            336.4,
            ("lang_factor_fluid_processing", "six_tenths_scaling"),
        ),
        (
            "place_component_separator",
            {},
            243.6,
            ("lang_factor_fluid_processing", "six_tenths_scaling"),
        ),
        (
            "install_line_pump",
            {},
            116.0,
            ("lang_factor_fluid_processing", "six_tenths_scaling"),
        ),
        (
            "install_line_valve",
            {},
            69.6,
            ("lang_factor_fluid_processing", "six_tenths_scaling"),
        ),
        (
            "install_line_heat_actuator",
            {},
            104.4,
            ("lang_factor_fluid_processing", "six_tenths_scaling"),
        ),
        (
            "place_inlet_gas_separator",
            {},
            185.6,
            ("lang_factor_fluid_processing", "six_tenths_scaling"),
        ),
        (
            "place_teg_contactor",
            {},
            243.6,
            ("lang_factor_fluid_processing", "six_tenths_scaling"),
        ),
        (
            "place_rich_glycol_flash_tank",
            {},
            185.6,
            ("lang_factor_fluid_processing", "six_tenths_scaling"),
        ),
        (
            "place_lean_rich_glycol_exchanger",
            {},
            336.4,
            ("lang_factor_fluid_processing", "six_tenths_scaling"),
        ),
        (
            "place_teg_regenerator",
            {},
            440.8,
            ("lang_factor_fluid_processing", "six_tenths_scaling"),
        ),
        (
            "install_glycol_circulation_pump",
            {},
            116.0,
            ("lang_factor_fluid_processing", "six_tenths_scaling"),
        ),
        (
            "place_gas_gas_exchanger",
            {},
            336.4,
            ("lang_factor_fluid_processing", "six_tenths_scaling"),
        ),
        (
            "install_jt_valve",
            {},
            69.6,
            ("lang_factor_fluid_processing", "six_tenths_scaling"),
        ),
        (
            "place_low_temperature_separator",
            {},
            185.6,
            ("lang_factor_fluid_processing", "six_tenths_scaling"),
        ),
        (
            "place_condensate_stabilizer",
            {},
            440.8,
            ("lang_factor_fluid_processing", "six_tenths_scaling"),
        ),
        (
            "install_sampled_delayed_sensor",
            {},
            35.0,
            ("instrument_fixed_price_table",),
        ),
        (
            "install_pid_controller",
            {},
            85.0,
            ("instrument_fixed_price_table",),
        ),
        (
            "place_merge_junction_2x1",
            {},
            36.0,
            ("junction_fitting_price_table",),
        ),
        (
            "place_split_junction_1x2",
            {},
            36.0,
            ("junction_fitting_price_table",),
        ),
        (
            "build_process_line",
            {"length_m": 3.0, "radius_m": 0.05},
            14.0 * 3.0 * ((2.0 * 0.05) / 0.10) ** 0.6,
            ("shortcut_piping_length_cost",),
        ),
    ],
)
def test_equipment_quotes_freeze_phase1_anchors(
    item_id: str,
    config: dict[str, object],
    expected_amount: float,
    expected_rule_ids: tuple[str, ...],
) -> None:
    api = _economics_api()
    api.open_cash_ledger()

    quote = api.quote_equipment_purchase(item_id, config=config)
    assert quote.subject_id == item_id
    assert quote.subject_kind == "equipment"
    assert quote.quoted_amount == pytest.approx(expected_amount)
    assert quote.applied_rule_ids == expected_rule_ids
    assert isinstance(quote.affordable, bool)


def test_feed_and_product_quotes_freeze_price_tables() -> None:
    api = _economics_api()
    api.open_cash_ledger()

    feed_a = api.quote_feed_purchase("feed_a", quantity_mol=4.0)
    assert feed_a.subject_kind == "feed"
    assert feed_a.quoted_amount == pytest.approx(8.0)
    assert feed_a.applied_rule_ids == ("feed_purchase_price_table",)

    feed_b = api.quote_feed_purchase("feed_b", quantity_mol=2.5)
    assert feed_b.subject_kind == "feed"
    assert feed_b.quoted_amount == pytest.approx(7.5)
    assert feed_b.applied_rule_ids == ("feed_purchase_price_table",)

    product_a = api.quote_product_sale("product_a", quantity_mol=1.5)
    assert product_a.subject_kind == "product_sale"
    assert product_a.quoted_amount == pytest.approx(12.0)
    assert product_a.applied_rule_ids == ("product_sale_price_table",)

    product_b = api.quote_product_sale("product_b", quantity_mol=1.5)
    assert product_b.subject_kind == "product_sale"
    assert product_b.quoted_amount == pytest.approx(18.0)
    assert product_b.applied_rule_ids == ("product_sale_price_table",)

    sweet_wet_gas = api.quote_feed_purchase("sweet_wet_gas", quantity_mol=4.0)
    assert sweet_wet_gas.subject_kind == "feed"
    assert sweet_wet_gas.quoted_amount == pytest.approx(10.0)
    assert sweet_wet_gas.applied_rule_ids == ("feed_purchase_price_table",)

    separator_gas = api.quote_product_sale("separator_gas", quantity_mol=1.0)
    assert separator_gas.subject_kind == "product_sale"
    assert separator_gas.quoted_amount == pytest.approx(6.0)
    assert separator_gas.applied_rule_ids == ("product_sale_price_table",)

    unstabilized_condensate = api.quote_product_sale("unstabilized_condensate", quantity_mol=1.0)
    assert unstabilized_condensate.subject_kind == "product_sale"
    assert unstabilized_condensate.quoted_amount == pytest.approx(8.0)
    assert unstabilized_condensate.applied_rule_ids == ("product_sale_price_table",)

    dry_gas = api.quote_product_sale("dry_gas", quantity_mol=1.0)
    assert dry_gas.subject_kind == "product_sale"
    assert dry_gas.quoted_amount == pytest.approx(9.0)
    assert dry_gas.applied_rule_ids == ("product_sale_price_table",)

    ngl_liquids = api.quote_product_sale("ngl_liquids", quantity_mol=1.0)
    assert ngl_liquids.subject_kind == "product_sale"
    assert ngl_liquids.quoted_amount == pytest.approx(12.0)
    assert ngl_liquids.applied_rule_ids == ("product_sale_price_table",)

    stabilized_condensate = api.quote_product_sale("stabilized_condensate", quantity_mol=1.0)
    assert stabilized_condensate.subject_kind == "product_sale"
    assert stabilized_condensate.quoted_amount == pytest.approx(10.0)
    assert stabilized_condensate.applied_rule_ids == ("product_sale_price_table",)


def test_operating_costs_use_exact_frozen_formulas_and_rule_names() -> None:
    api = _economics_api()
    api.open_cash_ledger(initial_cash=10_000.0)

    dt_s = 20.0
    signal_values = {
        "heating_steam_duty_W": 50_000.0,
        "total_normalized_pump_load": 1.2,
    }
    result = api.record_operating_costs(dt_s=dt_s, published_signal_values_by_id=signal_values)

    expected_heating = 50_000.0 * dt_s * 0.02 / 1_000_000
    expected_pump = 1.2 * dt_s * 0.004
    assert result.operating_cost_paid == pytest.approx(expected_heating + expected_pump)

    by_id = {application.rule_id: application for application in result.rule_applications}
    assert set(by_id) == {"heating_steam_cost_heuristic", "pump_electricity_cost_heuristic"}
    assert by_id["heating_steam_cost_heuristic"].rule_name == "Heating steam cost heuristic"
    assert by_id["pump_electricity_cost_heuristic"].rule_name == "Pump electricity cost heuristic"
    assert by_id["heating_steam_cost_heuristic"].basis_snapshot == {
        "heating_steam_duty_W": 50_000.0,
        "dt_s": dt_s,
    }
    assert by_id["pump_electricity_cost_heuristic"].basis_snapshot == {
        "total_normalized_pump_load": 1.2,
        "dt_s": dt_s,
    }


def test_malformed_config_raises_invalid_config_not_type_error() -> None:
    """config=None and other non-Mapping values must raise invalid_config, not TypeError."""
    api = _economics_api()
    error_type = _sandbox_error_type()
    api.open_cash_ledger()

    # None is the canonical reviewer-reported case
    with pytest.raises(error_type) as exc_none:
        api.quote_equipment_purchase("place_heater_cooler", config=None)  # type: ignore[arg-type]
    assert exc_none.value.error_code == "invalid_config"

    # build_process_line with None must also raise invalid_config, not TypeError
    with pytest.raises(error_type) as exc_pipe_none:
        api.quote_equipment_purchase("build_process_line", config=None)  # type: ignore[arg-type]
    assert exc_pipe_none.value.error_code == "invalid_config"


def test_economics_error_codes_are_stable() -> None:
    api = _economics_api()
    error_type = _sandbox_error_type()

    with pytest.raises(error_type) as before_open:
        api.quote_feed_purchase("feed_a", quantity_mol=1.0)
    assert before_open.value.error_code == "ledger_not_open"

    api.open_cash_ledger(initial_cash=1.0)

    with pytest.raises(error_type) as unknown_item:
        api.quote_equipment_purchase("unknown_item", config={})
    assert unknown_item.value.error_code == "unknown_item"

    with pytest.raises(error_type) as unknown_material:
        api.quote_feed_purchase("unknown_material", quantity_mol=1.0)
    assert unknown_material.value.error_code == "unknown_material"

    with pytest.raises(error_type) as unknown_product:
        api.quote_product_sale("unknown_product", quantity_mol=1.0)
    assert unknown_product.value.error_code == "unknown_product"

    with pytest.raises(error_type) as invalid_quantity:
        api.quote_feed_purchase("feed_a", quantity_mol=0.0)
    assert invalid_quantity.value.error_code == "invalid_quantity"

    with pytest.raises(error_type) as invalid_config:
        api.quote_equipment_purchase("build_process_line", config={"radius_m": 0.1})
    assert invalid_config.value.error_code == "invalid_config"

    with pytest.raises(error_type) as invalid_dt_s:
        api.record_operating_costs(dt_s=0.0, published_signal_values_by_id={})
    assert invalid_dt_s.value.error_code == "invalid_dt_s"

    with pytest.raises(error_type) as insufficient_cash:
        api.record_equipment_purchase("place_heat_exchanger", config={})
    assert insufficient_cash.value.error_code == "insufficient_cash"

    with pytest.raises(error_type) as missing_withdrawal_id:
        api.record_product_sale("")
    assert missing_withdrawal_id.value.error_code == "missing_withdrawal_id"

    with pytest.raises(error_type) as unknown_withdrawal_id:
        api.record_product_sale("unknown-withdrawal-token")
    assert unknown_withdrawal_id.value.error_code == "unknown_withdrawal_id"


def test_cash_balance_transitions_include_single_use_withdrawal_sale_handoff() -> None:
    api = _economics_api()
    session = import_module("modular_simulation.gameplay.sandbox_session")
    error_type = _sandbox_error_type()

    initial = api.open_cash_ledger(initial_cash=2_000.0)
    assert initial.cash_balance == pytest.approx(2_000.0)

    equipment_receipt = api.record_equipment_purchase(
        "build_process_line",
        config={"length_m": 3.0, "radius_m": 0.05},
    )
    after_equipment = api.get_cash_ledger()
    assert after_equipment.cash_balance == pytest.approx(1_958.0)
    assert after_equipment.equipment_capex_spent == pytest.approx(42.0)

    session.start_sandbox()
    session.install_catalog_item(
        "build_process_line",
        config={"length_m": 3.0, "radius_m": 0.05},
        equipment_receipt_id=equipment_receipt.receipt_id,
    )

    feed_receipt = api.record_feed_purchase("feed_a", quantity_mol=2.0)
    after_feed = api.get_cash_ledger()
    assert after_feed.cash_balance == pytest.approx(1_954.0)
    assert after_feed.feed_procurement_spent == pytest.approx(4.0)

    session.load_feed_inventory(
        "sweet_wet_gas", 2.0, procurement_receipt_id=feed_receipt.receipt_id
    )
    step = session.advance(1.0)

    op = api.record_operating_costs(
        dt_s=1.0,
        published_signal_values_by_id=step.published_signal_values_by_id,
    )
    assert op.operating_cost_paid == pytest.approx(0.005)
    after_op = api.get_cash_ledger()
    assert after_op.cash_balance == pytest.approx(1_953.995)
    assert after_op.operating_costs_paid == pytest.approx(0.005)

    api.register_product_withdrawal_handoff(
        "withdrawal-1",
        product_id="product_a",
        quantity_mol=0.2,
    )
    withdrawal_id = "withdrawal-1"
    sale = api.record_product_sale(withdrawal_id)
    assert sale.withdrawal_id == withdrawal_id
    assert sale.gross_revenue == pytest.approx(1.6)

    after_sale = api.get_cash_ledger()
    assert after_sale.cash_balance == pytest.approx(1_955.595)
    assert after_sale.product_sales_received == pytest.approx(1.6)

    with pytest.raises(error_type) as replay:
        api.record_product_sale(withdrawal_id)
    assert replay.value.error_code == "unknown_withdrawal_id"


def test_module_level_quote_callers_share_default_pricing_policy_seam() -> None:
    economics = import_module("modular_simulation.gameplay.economics")
    api = _economics_api()
    api.open_cash_ledger(initial_cash=100.0)

    calls: list[tuple[str, str]] = []

    def _fake_pricing_seam(
        *, subject_kind: str, subject_id: str, **_: object
    ) -> tuple[float, tuple[str, ...]]:
        calls.append((subject_kind, subject_id))
        if subject_kind == "equipment":
            return 11.0, ("equipment_rule",)
        if subject_kind == "feed":
            return 13.0, ("feed_rule",)
        if subject_kind == "product_sale":
            return 17.0, ("product_rule",)
        raise AssertionError(f"unexpected subject_kind {subject_kind!r}")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(economics, "_quote_with_default_pricing_policy", _fake_pricing_seam)

        equipment = api.quote_equipment_purchase("place_heater_cooler", config={})
        feed = api.quote_feed_purchase("feed_a", quantity_mol=1.0)
        product = api.quote_product_sale("product_a", quantity_mol=1.0)

    assert equipment.quoted_amount == pytest.approx(11.0)
    assert equipment.applied_rule_ids == ("equipment_rule",)
    assert feed.quoted_amount == pytest.approx(13.0)
    assert feed.applied_rule_ids == ("feed_rule",)
    assert product.quoted_amount == pytest.approx(17.0)
    assert product.applied_rule_ids == ("product_rule",)
    assert calls == [
        ("equipment", "place_heater_cooler"),
        ("feed", "feed_a"),
        ("product_sale", "product_a"),
    ]


def test_runtime_quote_callers_share_default_pricing_policy_seam() -> None:
    economics = import_module("modular_simulation.gameplay.economics")
    runtime = economics.CashLedgerRuntime()
    runtime.open_cash_ledger(initial_cash=100.0)

    calls: list[tuple[str, str]] = []

    def _fake_pricing_seam(
        *, subject_kind: str, subject_id: str, **_: object
    ) -> tuple[float, tuple[str, ...]]:
        calls.append((subject_kind, subject_id))
        if subject_kind == "equipment":
            return 21.0, ("equipment_rule_rt",)
        if subject_kind == "feed":
            return 23.0, ("feed_rule_rt",)
        if subject_kind == "product_sale":
            return 27.0, ("product_rule_rt",)
        raise AssertionError(f"unexpected subject_kind {subject_kind!r}")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(economics, "_quote_with_default_pricing_policy", _fake_pricing_seam)

        equipment = runtime.quote_equipment_purchase("place_heater_cooler", config={})
        feed = runtime.quote_feed_purchase("feed_a", quantity_mol=1.0)
        product = runtime.quote_product_sale("product_a", quantity_mol=1.0)

    assert equipment.quoted_amount == pytest.approx(21.0)
    assert equipment.applied_rule_ids == ("equipment_rule_rt",)
    assert feed.quoted_amount == pytest.approx(23.0)
    assert feed.applied_rule_ids == ("feed_rule_rt",)
    assert product.quoted_amount == pytest.approx(27.0)
    assert product.applied_rule_ids == ("product_rule_rt",)
    assert calls == [
        ("equipment", "place_heater_cooler"),
        ("feed", "feed_a"),
        ("product_sale", "product_a"),
    ]

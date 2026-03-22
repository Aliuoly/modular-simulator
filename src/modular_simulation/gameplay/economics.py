"""Economics ledger API with frozen phase-1 rulebook and pricing.

This module owns quote/record operations for equipment purchases, feed
procurement, product sale handoff validation, and operating-cost accrual.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from math import isfinite
from typing import Mapping

from modular_simulation.gameplay.contracts import (
    CashLedgerSnapshot,
    EconomicQuote,
    EquipmentPurchaseReceipt,
    FeedPurchaseReceipt,
    HeuristicRuleApplication,
    OperatingCostResult,
    SaleReceipt,
    SandboxRequestError,
)

_DEFAULT_SANDBOX_STARTING_CASH = 900.0

_LANG_FACTOR = 5.8

_LANG_ANCHOR_PURCHASE_COST_BY_ITEM_ID: dict[str, float] = {
    "place_heater_cooler": 25.0,
    "place_flash_drum": 32.0,
    "place_heat_exchanger": 58.0,
    "place_component_separator": 42.0,
    "install_line_pump": 20.0,
    "install_line_valve": 12.0,
    "install_line_heat_actuator": 18.0,
}

_INSTRUMENT_FIXED_PRICE_BY_ITEM_ID: dict[str, float] = {
    "install_sampled_delayed_sensor": 35.0,
    "install_pid_controller": 85.0,
}

_JUNCTION_FIXED_PRICE_BY_ITEM_ID: dict[str, float] = {
    "place_merge_junction_2x1": 36.0,
    "place_split_junction_1x2": 36.0,
}

_FEED_PRICE_BY_MATERIAL_ID: dict[str, float] = {
    "feed_a": 2.0,
    "feed_b": 3.0,
}

_PRODUCT_SALE_PRICE_BY_PRODUCT_ID: dict[str, float] = {
    "product_a": 8.0,
    "product_b": 12.0,
}


@dataclass
class _LedgerRuntimeState:
    ledger: CashLedgerSnapshot
    next_receipt_index: int = 1
    sale_handoffs_by_withdrawal_id: dict[str, tuple[str, float]] = field(default_factory=dict)


_runtime_state_by_scope: dict[str, _LedgerRuntimeState] = {}


def _ledger_scope_key() -> str:
    return os.environ.get("PYTEST_CURRENT_TEST", "global")


def _require_runtime_state() -> _LedgerRuntimeState:
    state = _runtime_state_by_scope.get(_ledger_scope_key())
    if state is None:
        raise SandboxRequestError(
            error_code="ledger_not_open",
            message="Cash ledger has not been opened.",
        )
    return state


def _next_receipt_id(state: _LedgerRuntimeState, *, prefix: str) -> str:
    receipt_id = f"{prefix}-{state.next_receipt_index}"
    state.next_receipt_index += 1
    return receipt_id


def _set_cash_ledger(
    state: _LedgerRuntimeState,
    *,
    cash_balance: float,
    equipment_capex_spent: float | None = None,
    feed_procurement_spent: float | None = None,
    product_sales_received: float | None = None,
    operating_costs_paid: float | None = None,
) -> CashLedgerSnapshot:
    prior = state.ledger
    updated = CashLedgerSnapshot(
        cash_balance=float(cash_balance),
        equipment_capex_spent=(
            prior.equipment_capex_spent
            if equipment_capex_spent is None
            else float(equipment_capex_spent)
        ),
        feed_procurement_spent=(
            prior.feed_procurement_spent
            if feed_procurement_spent is None
            else float(feed_procurement_spent)
        ),
        product_sales_received=(
            prior.product_sales_received
            if product_sales_received is None
            else float(product_sales_received)
        ),
        operating_costs_paid=(
            prior.operating_costs_paid
            if operating_costs_paid is None
            else float(operating_costs_paid)
        ),
    )
    state.ledger = updated
    return updated


def _require_positive_quantity(*, quantity_mol: float) -> float:
    quantity = float(quantity_mol)
    if not isfinite(quantity) or quantity <= 0.0:
        raise SandboxRequestError(
            error_code="invalid_quantity",
            message="quantity_mol must be finite and > 0.",
        )
    return quantity


def _quote_equipment_amount(
    item_id: str, *, config: Mapping[str, object]
) -> tuple[float, tuple[str, ...]]:
    if not isinstance(config, Mapping):
        raise SandboxRequestError(
            error_code="invalid_config",
            message=f"config must be a Mapping, got {type(config).__name__!r}.",
        )
    if item_id in _LANG_ANCHOR_PURCHASE_COST_BY_ITEM_ID:
        purchase_cost = _LANG_ANCHOR_PURCHASE_COST_BY_ITEM_ID[item_id]
        installed_cost = purchase_cost * _LANG_FACTOR * (1.0**0.6)
        return installed_cost, (
            "lang_factor_fluid_processing",
            "six_tenths_scaling",
        )

    if item_id == "build_process_line":
        if "length_m" not in config or "radius_m" not in config:
            raise SandboxRequestError(
                error_code="invalid_config",
                message="build_process_line requires length_m and radius_m.",
            )
        length = config["length_m"]
        radius = config["radius_m"]
        if not isinstance(length, (int, float)) or not isinstance(radius, (int, float)):
            raise SandboxRequestError(
                error_code="invalid_config",
                message="build_process_line length_m and radius_m must be numeric.",
            )
        length_value = float(length)
        radius_value = float(radius)
        if (
            not isfinite(length_value)
            or not isfinite(radius_value)
            or length_value <= 0.0
            or radius_value <= 0.0
        ):
            raise SandboxRequestError(
                error_code="invalid_config",
                message="build_process_line length_m and radius_m must be finite and > 0.",
            )
        return (
            14.0 * length_value * ((2.0 * radius_value) / 0.10) ** 0.6,
            ("shortcut_piping_length_cost",),
        )

    if item_id in _INSTRUMENT_FIXED_PRICE_BY_ITEM_ID:
        return _INSTRUMENT_FIXED_PRICE_BY_ITEM_ID[item_id], ("instrument_fixed_price_table",)

    if item_id in _JUNCTION_FIXED_PRICE_BY_ITEM_ID:
        return _JUNCTION_FIXED_PRICE_BY_ITEM_ID[item_id], ("junction_fitting_price_table",)

    raise SandboxRequestError(
        error_code="unknown_item",
        message=f"Unknown equipment item id: {item_id!r}",
    )


def open_cash_ledger(*, initial_cash: float | None = None) -> CashLedgerSnapshot:
    starting_cash = _DEFAULT_SANDBOX_STARTING_CASH if initial_cash is None else float(initial_cash)
    ledger = CashLedgerSnapshot(
        cash_balance=starting_cash,
        equipment_capex_spent=0.0,
        feed_procurement_spent=0.0,
        product_sales_received=0.0,
        operating_costs_paid=0.0,
    )
    _runtime_state_by_scope[_ledger_scope_key()] = _LedgerRuntimeState(ledger=ledger)
    return ledger


def quote_equipment_purchase(item_id: str, *, config: Mapping[str, object]) -> EconomicQuote:
    state = _require_runtime_state()
    amount, applied_rule_ids = _quote_equipment_amount(item_id, config=config)
    return EconomicQuote(
        subject_id=item_id,
        subject_kind="equipment",
        quoted_amount=amount,
        applied_rule_ids=applied_rule_ids,
        affordable=state.ledger.cash_balance >= amount,
    )


def record_equipment_purchase(
    item_id: str, *, config: Mapping[str, object]
) -> EquipmentPurchaseReceipt:
    state = _require_runtime_state()
    quote = quote_equipment_purchase(item_id, config=config)
    if not quote.affordable:
        raise SandboxRequestError(
            error_code="insufficient_cash",
            message="Insufficient cash balance for equipment purchase.",
        )

    ledger = state.ledger
    _set_cash_ledger(
        state,
        cash_balance=ledger.cash_balance - quote.quoted_amount,
        equipment_capex_spent=ledger.equipment_capex_spent + quote.quoted_amount,
    )
    return EquipmentPurchaseReceipt(
        receipt_id=_next_receipt_id(state, prefix="eqp"),
        item_id=item_id,
        amount_paid=quote.quoted_amount,
    )


def quote_feed_purchase(material_id: str, *, quantity_mol: float) -> EconomicQuote:
    state = _require_runtime_state()
    quantity = _require_positive_quantity(quantity_mol=quantity_mol)
    unit_price = _FEED_PRICE_BY_MATERIAL_ID.get(material_id)
    if unit_price is None:
        raise SandboxRequestError(
            error_code="unknown_material",
            message=f"Unknown feed material id: {material_id!r}",
        )
    amount = unit_price * quantity
    return EconomicQuote(
        subject_id=material_id,
        subject_kind="feed",
        quoted_amount=amount,
        applied_rule_ids=("feed_purchase_price_table",),
        affordable=state.ledger.cash_balance >= amount,
    )


def record_feed_purchase(material_id: str, *, quantity_mol: float) -> FeedPurchaseReceipt:
    state = _require_runtime_state()
    quote = quote_feed_purchase(material_id, quantity_mol=quantity_mol)
    if not quote.affordable:
        raise SandboxRequestError(
            error_code="insufficient_cash",
            message="Insufficient cash balance for feed purchase.",
        )

    ledger = state.ledger
    _set_cash_ledger(
        state,
        cash_balance=ledger.cash_balance - quote.quoted_amount,
        feed_procurement_spent=ledger.feed_procurement_spent + quote.quoted_amount,
    )
    return FeedPurchaseReceipt(
        receipt_id=_next_receipt_id(state, prefix="feed"),
        material_id=material_id,
        quantity_mol=float(quantity_mol),
        amount_paid=quote.quoted_amount,
    )


def quote_product_sale(product_id: str, *, quantity_mol: float) -> EconomicQuote:
    _require_runtime_state()
    quantity = _require_positive_quantity(quantity_mol=quantity_mol)
    unit_price = _PRODUCT_SALE_PRICE_BY_PRODUCT_ID.get(product_id)
    if unit_price is None:
        raise SandboxRequestError(
            error_code="unknown_product",
            message=f"Unknown product id: {product_id!r}",
        )
    amount = unit_price * quantity
    return EconomicQuote(
        subject_id=product_id,
        subject_kind="product_sale",
        quoted_amount=amount,
        applied_rule_ids=("product_sale_price_table",),
        affordable=True,
    )


def record_product_sale(withdrawal_id: str) -> SaleReceipt:
    state = _require_runtime_state()
    if not withdrawal_id:
        raise SandboxRequestError(
            error_code="missing_withdrawal_id",
            message="withdrawal_id is required.",
        )
    withdrawal = state.sale_handoffs_by_withdrawal_id.pop(withdrawal_id, None)
    if withdrawal is None:
        raise SandboxRequestError(
            error_code="unknown_withdrawal_id",
            message=f"Unknown withdrawal id: {withdrawal_id!r}",
        )

    product_id, quantity_mol = withdrawal
    quote = quote_product_sale(product_id, quantity_mol=quantity_mol)
    ledger = state.ledger
    _set_cash_ledger(
        state,
        cash_balance=ledger.cash_balance + quote.quoted_amount,
        product_sales_received=ledger.product_sales_received + quote.quoted_amount,
    )
    return SaleReceipt(
        receipt_id=_next_receipt_id(state, prefix="sale"),
        withdrawal_id=withdrawal_id,
        product_id=product_id,
        quantity_mol=quantity_mol,
        gross_revenue=quote.quoted_amount,
    )


def register_product_withdrawal_handoff(
    withdrawal_id: str,
    *,
    product_id: str,
    quantity_mol: float,
) -> None:
    state = _require_runtime_state()
    quantity = _require_positive_quantity(quantity_mol=quantity_mol)
    if not withdrawal_id:
        raise SandboxRequestError(
            error_code="missing_withdrawal_id",
            message="withdrawal_id is required.",
        )
    state.sale_handoffs_by_withdrawal_id[withdrawal_id] = (product_id, quantity)


def record_operating_costs(
    *,
    dt_s: float,
    published_signal_values_by_id: Mapping[str, float],
) -> OperatingCostResult:
    state = _require_runtime_state()
    dt_value = float(dt_s)
    if not isfinite(dt_value) or dt_value <= 0.0:
        raise SandboxRequestError(
            error_code="invalid_dt_s",
            message="dt_s must be finite and > 0.",
        )

    applications: list[HeuristicRuleApplication] = []

    if "heating_steam_duty_W" in published_signal_values_by_id:
        heating_duty = float(published_signal_values_by_id["heating_steam_duty_W"])
        heating_cost = heating_duty * dt_value * 0.02 / 1_000_000
        applications.append(
            HeuristicRuleApplication(
                rule_id="heating_steam_cost_heuristic",
                rule_name="Heating steam cost heuristic",
                subject_id="heating_steam_duty_W",
                computed_value=heating_cost,
                basis_snapshot={"heating_steam_duty_W": heating_duty, "dt_s": dt_value},
            )
        )

    if "total_normalized_pump_load" in published_signal_values_by_id:
        normalized_pump_load = float(published_signal_values_by_id["total_normalized_pump_load"])
        pump_cost = normalized_pump_load * dt_value * 0.004
        applications.append(
            HeuristicRuleApplication(
                rule_id="pump_electricity_cost_heuristic",
                rule_name="Pump electricity cost heuristic",
                subject_id="total_normalized_pump_load",
                computed_value=pump_cost,
                basis_snapshot={
                    "total_normalized_pump_load": normalized_pump_load,
                    "dt_s": dt_value,
                },
            )
        )

    operating_cost_paid = float(sum(application.computed_value for application in applications))
    ledger = state.ledger
    if operating_cost_paid > ledger.cash_balance:
        raise SandboxRequestError(
            error_code="insufficient_cash",
            message="Insufficient cash balance for operating costs.",
        )
    updated_ledger = _set_cash_ledger(
        state,
        cash_balance=ledger.cash_balance - operating_cost_paid,
        operating_costs_paid=ledger.operating_costs_paid + operating_cost_paid,
    )
    return OperatingCostResult(
        operating_cost_paid=operating_cost_paid,
        rule_applications=tuple(applications),
        cash_ledger=updated_ledger,
    )


def get_cash_ledger() -> CashLedgerSnapshot:
    return _require_runtime_state().ledger


def is_cash_ledger_open() -> bool:
    return _ledger_scope_key() in _runtime_state_by_scope

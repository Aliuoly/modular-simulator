from __future__ import annotations

from importlib import import_module
from typing import Literal, Mapping, get_type_hints


def _contracts_module():
    return import_module("modular_simulation.gameplay.contracts")


def _attribute_names(contract_name: str) -> frozenset[str]:
    """Return the set of public attribute names on the contract class.

    Uses ``__annotations__`` (covers dataclasses, attrs, plain typed classes)
    so the test is not coupled to a specific implementation mechanism.
    """
    cls = getattr(_contracts_module(), contract_name)
    # Walk the MRO so inherited annotations are included, but exclude anything
    # from builtins / object itself.
    names: dict[str, None] = {}
    for base in reversed(cls.__mro__):
        if base is object:
            continue
        names.update({k: None for k in getattr(base, "__annotations__", {})})
    return frozenset(names)


def _resolved_type_hints(contract_name: str) -> dict[str, object]:
    module = _contracts_module()
    cls = getattr(module, contract_name)
    return get_type_hints(cls, globalns=vars(module), localns=vars(module))


def test_play_start_definition_fields_are_frozen() -> None:
    assert _attribute_names("PlayStartDefinition") == frozenset(
        {
            "start_id",
            "start_kind",
            "title",
            "seed_source_paths",
            "starting_topology_summary",
            "published_signal_ids",
            "allowed_item_ids",
        }
    )


def test_sandbox_catalog_item_definition_fields_are_frozen() -> None:
    assert _attribute_names("SandboxCatalogItemDefinition") == frozenset(
        {
            "item_id",
            "title",
            "item_kind",
            "apply_kind",
            "default_config",
            "required_user_inputs",
            "supported_start_ids",
            "educational_summary",
        }
    )


def test_tutorial_definition_fields_are_frozen() -> None:
    assert _attribute_names("TutorialDefinition") == frozenset(
        {
            "tutorial_id",
            "title",
            "teaching_track",
            "start_id",
            "goal_mode",
            "goals",
            "guidance_steps",
        }
    )


def test_tutorial_goal_definition_fields_are_frozen() -> None:
    assert _attribute_names("TutorialGoalDefinition") == frozenset(
        {
            "goal_id",
            "title",
            "goal_kind",
            "item_id",
            "required_count",
            "prerequisite_goal_ids",
        }
    )


def test_guidance_step_definition_fields_are_frozen() -> None:
    assert _attribute_names("GuidanceStepDefinition") == frozenset(
        {
            "step_id",
            "title",
            "related_goal_ids",
            "hint_text",
        }
    )


def test_simulation_session_snapshot_fields_and_types_are_frozen() -> None:
    assert _attribute_names("SimulationSessionSnapshot") == frozenset(
        {
            "session_kind",
            "active_start_id",
            "active_tutorial_id",
            "elapsed_time_s",
            "tutorial_completion_time_s",
            "installed_item_instance_ids",
            "feed_inventory_by_material_id",
            "product_inventory_by_product_id",
            "tutorial_goal_status_by_id",
        }
    )
    module = _contracts_module()
    hints = _resolved_type_hints("SimulationSessionSnapshot")
    assert hints == {
        "session_kind": Literal["sandbox", "tutorial"],
        "active_start_id": str,
        "active_tutorial_id": str | None,
        "elapsed_time_s": float,
        "tutorial_completion_time_s": float | None,
        "installed_item_instance_ids": tuple[str, ...],
        "feed_inventory_by_material_id": Mapping[str, float],
        "product_inventory_by_product_id": Mapping[str, float],
        "tutorial_goal_status_by_id": Mapping[str, getattr(module, "TutorialGoalStatus")],
    }


def test_tutorial_goal_status_fields_and_types_are_frozen() -> None:
    assert _attribute_names("TutorialGoalStatus") == frozenset(
        {"goal_id", "completed", "completed_at_time_s"}
    )
    assert _resolved_type_hints("TutorialGoalStatus") == {
        "goal_id": str,
        "completed": bool,
        "completed_at_time_s": float | None,
    }


def test_simulation_result_contracts_are_frozen() -> None:
    module = _contracts_module()

    assert _attribute_names("BuildApplyResult") == frozenset({"success", "reason_code", "snapshot"})
    assert _resolved_type_hints("BuildApplyResult") == {
        "success": bool,
        "reason_code": str | None,
        "snapshot": getattr(module, "SimulationSessionSnapshot"),
    }

    assert _attribute_names("InventoryLoadResult") == frozenset(
        {"success", "reason_code", "snapshot"}
    )
    assert _resolved_type_hints("InventoryLoadResult") == {
        "success": bool,
        "reason_code": str | None,
        "snapshot": getattr(module, "SimulationSessionSnapshot"),
    }

    assert _attribute_names("InventoryWithdrawalResult") == frozenset(
        {
            "withdrawal_id",
            "success",
            "reason_code",
            "withdrawn_quantity_mol",
            "snapshot",
        }
    )
    assert _resolved_type_hints("InventoryWithdrawalResult") == {
        "withdrawal_id": str,
        "success": bool,
        "reason_code": str | None,
        "withdrawn_quantity_mol": float,
        "snapshot": getattr(module, "SimulationSessionSnapshot"),
    }

    assert _attribute_names("SimulationAdvanceResult") == frozenset(
        {
            "snapshot",
            "feed_consumption_by_material_id",
            "product_production_by_product_id",
            "published_signal_values_by_id",
        }
    )
    assert _resolved_type_hints("SimulationAdvanceResult") == {
        "snapshot": getattr(module, "SimulationSessionSnapshot"),
        "feed_consumption_by_material_id": Mapping[str, float],
        "product_production_by_product_id": Mapping[str, float],
        "published_signal_values_by_id": Mapping[str, float],
    }


def test_economics_contracts_are_frozen() -> None:
    module = _contracts_module()

    assert _attribute_names("EconomicQuote") == frozenset(
        {"subject_id", "subject_kind", "quoted_amount", "applied_rule_ids", "affordable"}
    )
    assert _resolved_type_hints("EconomicQuote") == {
        "subject_id": str,
        "subject_kind": Literal["equipment", "feed", "product_sale"],
        "quoted_amount": float,
        "applied_rule_ids": tuple[str, ...],
        "affordable": bool,
    }

    assert _attribute_names("EquipmentPurchaseReceipt") == frozenset(
        {"receipt_id", "item_id", "amount_paid"}
    )
    assert _resolved_type_hints("EquipmentPurchaseReceipt") == {
        "receipt_id": str,
        "item_id": str,
        "amount_paid": float,
    }

    assert _attribute_names("FeedPurchaseReceipt") == frozenset(
        {"receipt_id", "material_id", "quantity_mol", "amount_paid"}
    )
    assert _resolved_type_hints("FeedPurchaseReceipt") == {
        "receipt_id": str,
        "material_id": str,
        "quantity_mol": float,
        "amount_paid": float,
    }

    assert _attribute_names("SaleReceipt") == frozenset(
        {"receipt_id", "withdrawal_id", "product_id", "quantity_mol", "gross_revenue"}
    )
    assert _resolved_type_hints("SaleReceipt") == {
        "receipt_id": str,
        "withdrawal_id": str,
        "product_id": str,
        "quantity_mol": float,
        "gross_revenue": float,
    }

    assert _attribute_names("CashLedgerSnapshot") == frozenset(
        {
            "cash_balance",
            "equipment_capex_spent",
            "feed_procurement_spent",
            "product_sales_received",
            "operating_costs_paid",
        }
    )
    assert _resolved_type_hints("CashLedgerSnapshot") == {
        "cash_balance": float,
        "equipment_capex_spent": float,
        "feed_procurement_spent": float,
        "product_sales_received": float,
        "operating_costs_paid": float,
    }

    assert _attribute_names("HeuristicRuleApplication") == frozenset(
        {"rule_id", "rule_name", "subject_id", "computed_value", "basis_snapshot"}
    )
    assert _resolved_type_hints("HeuristicRuleApplication") == {
        "rule_id": str,
        "rule_name": str,
        "subject_id": str,
        "computed_value": float,
        "basis_snapshot": Mapping[str, float],
    }

    assert _attribute_names("OperatingCostResult") == frozenset(
        {"operating_cost_paid", "rule_applications", "cash_ledger"}
    )
    assert _resolved_type_hints("OperatingCostResult") == {
        "operating_cost_paid": float,
        "rule_applications": tuple[getattr(module, "HeuristicRuleApplication"), ...],
        "cash_ledger": getattr(module, "CashLedgerSnapshot"),
    }


def test_sandbox_request_error_contract_is_frozen() -> None:
    assert _attribute_names("SandboxRequestError") == frozenset({"error_code", "message"})
    assert _resolved_type_hints("SandboxRequestError") == {
        "error_code": str,
        "message": str,
    }

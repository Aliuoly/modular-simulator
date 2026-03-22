"""Typed data contracts for gameplay metadata definitions.

These are plain dataclasses used as frozen records throughout the catalog modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping


@dataclass(frozen=True)
class PlayStartDefinition:
    start_id: str
    start_kind: Literal["sandbox", "tutorial_start"]
    title: str
    seed_source_paths: tuple[str, ...]
    starting_topology_summary: str
    published_signal_ids: tuple[str, ...]
    allowed_item_ids: tuple[str, ...]


@dataclass(frozen=True)
class SandboxCatalogItemDefinition:
    item_id: str
    title: str
    item_kind: Literal[
        "unit_blueprint",
        "junction_blueprint",
        "line",
        "line_overlay",
        "sensor",
        "controller",
    ]
    apply_kind: Literal[
        "add_process",
        "add_junction",
        "connect_configure_line",
        "attach_line_pump",
        "attach_line_valve",
        "attach_line_heat_actuator",
        "create_bind_sensor",
        "create_bind_activate_controller",
    ]
    default_config: Mapping[str, object]
    required_user_inputs: tuple[str, ...]
    supported_start_ids: tuple[str, ...]
    educational_summary: str


@dataclass(frozen=True)
class TutorialGoalDefinition:
    goal_id: str
    title: str
    goal_kind: Literal["install_item_count"]
    item_id: str
    required_count: int
    prerequisite_goal_ids: tuple[str, ...]


@dataclass(frozen=True)
class GuidanceStepDefinition:
    step_id: str
    title: str
    related_goal_ids: tuple[str, ...]
    hint_text: str


@dataclass(frozen=True)
class TutorialDefinition:
    tutorial_id: str
    title: str
    teaching_track: Literal[
        "topology_separation",
        "reactor_control",
        "recycle_process_design",
    ]
    start_id: str
    goal_mode: Literal["sequential", "mixed"]
    goals: tuple[TutorialGoalDefinition, ...]
    guidance_steps: tuple[GuidanceStepDefinition, ...]


@dataclass(frozen=True)
class TutorialGoalStatus:
    goal_id: str
    completed: bool
    completed_at_time_s: float | None


@dataclass(frozen=True)
class SimulationSessionSnapshot:
    session_kind: Literal["sandbox", "tutorial"]
    active_start_id: str
    active_tutorial_id: str | None
    elapsed_time_s: float
    tutorial_completion_time_s: float | None
    installed_item_instance_ids: tuple[str, ...]
    feed_inventory_by_material_id: Mapping[str, float]
    product_inventory_by_product_id: Mapping[str, float]
    tutorial_goal_status_by_id: Mapping[str, TutorialGoalStatus]


@dataclass(frozen=True)
class BuildApplyResult:
    success: bool
    reason_code: str | None
    snapshot: SimulationSessionSnapshot


@dataclass(frozen=True)
class InventoryLoadResult:
    success: bool
    reason_code: str | None
    snapshot: SimulationSessionSnapshot


@dataclass(frozen=True)
class InventoryWithdrawalResult:
    withdrawal_id: str
    success: bool
    reason_code: str | None
    withdrawn_quantity_mol: float
    snapshot: SimulationSessionSnapshot


@dataclass(frozen=True)
class SimulationAdvanceResult:
    snapshot: SimulationSessionSnapshot
    feed_consumption_by_material_id: Mapping[str, float]
    product_production_by_product_id: Mapping[str, float]
    published_signal_values_by_id: Mapping[str, float]


@dataclass(frozen=True)
class EconomicQuote:
    subject_id: str
    subject_kind: Literal["equipment", "feed", "product_sale"]
    quoted_amount: float
    applied_rule_ids: tuple[str, ...]
    affordable: bool


@dataclass(frozen=True)
class EquipmentPurchaseReceipt:
    receipt_id: str
    item_id: str
    amount_paid: float


@dataclass(frozen=True)
class FeedPurchaseReceipt:
    receipt_id: str
    material_id: str
    quantity_mol: float
    amount_paid: float


@dataclass(frozen=True)
class SaleReceipt:
    receipt_id: str
    withdrawal_id: str
    product_id: str
    quantity_mol: float
    gross_revenue: float


@dataclass(frozen=True)
class CashLedgerSnapshot:
    cash_balance: float
    equipment_capex_spent: float
    feed_procurement_spent: float
    product_sales_received: float
    operating_costs_paid: float


@dataclass(frozen=True)
class HeuristicRuleApplication:
    rule_id: str
    rule_name: str
    subject_id: str
    computed_value: float
    basis_snapshot: Mapping[str, float]


@dataclass(frozen=True)
class OperatingCostResult:
    operating_cost_paid: float
    rule_applications: tuple[HeuristicRuleApplication, ...]
    cash_ledger: CashLedgerSnapshot


@dataclass
class SandboxRequestError(Exception):
    error_code: str
    message: str

    def __str__(self) -> str:
        return f"{self.error_code}: {self.message}"

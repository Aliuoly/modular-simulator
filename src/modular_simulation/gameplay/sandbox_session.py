"""Simulation-first sandbox session API for phase-1 gameplay tests."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from typing import Mapping, Protocol

from modular_simulation.gameplay import economics
from modular_simulation.gameplay.contracts import (
    BuildApplyResult,
    InventoryLoadResult,
    InventoryWithdrawalResult,
    SandboxCatalogItemDefinition,
    SandboxRequestError,
    SimulationAdvanceResult,
    SimulationSessionSnapshot,
    TutorialDefinition,
    TutorialGoalStatus,
)
from modular_simulation.gameplay.sandbox_catalog import build_sandbox_catalog
from modular_simulation.gameplay.start_catalog import build_start_catalog
from modular_simulation.gameplay.starts.builders import LEARNER_START_SCAFFOLDS
from modular_simulation.gameplay.tutorial_catalog import build_tutorial_catalog


@dataclass
class _RuntimeSessionState:
    session_kind: str
    active_start_id: str
    active_tutorial_id: str | None
    elapsed_time_s: float = 0.0
    tutorial_completion_time_s: float | None = None
    installed_item_instance_ids: list[str] = field(default_factory=list)
    installed_item_counts_by_id: dict[str, int] = field(default_factory=dict)
    feed_inventory_by_material_id: dict[str, float] = field(default_factory=dict)
    product_inventory_by_product_id: dict[str, float] = field(default_factory=dict)
    tutorial_definition: TutorialDefinition | None = None
    tutorial_goal_status_by_id: dict[str, TutorialGoalStatus] = field(default_factory=dict)
    next_install_index: int = 1
    next_withdrawal_index: int = 1


class _EconomicsApi(Protocol):
    def is_cash_ledger_open(self) -> bool: ...

    def register_product_withdrawal_handoff(
        self,
        withdrawal_id: str,
        *,
        product_id: str,
        quantity_mol: float,
    ) -> None: ...


class SandboxSessionRuntime:
    """Instance-backed runtime for sandbox/tutorial session state."""

    def __init__(self, *, economics_api: _EconomicsApi | None = None) -> None:
        self._start_catalog = build_start_catalog()
        self._tutorial_catalog = build_tutorial_catalog()
        self._sandbox_catalog = build_sandbox_catalog()
        self._economics_api = (
            economics.CashLedgerRuntime() if economics_api is None else economics_api
        )
        self._state: _RuntimeSessionState | None = None

    def start_sandbox(self) -> SimulationSessionSnapshot:
        return self._start_state(session_kind="sandbox", start_id="phase1_process_sandbox_v1")

    def start_tutorial(self, tutorial_id: str) -> SimulationSessionSnapshot:
        tutorial = self._tutorial_catalog.get(tutorial_id)
        if tutorial is None:
            raise SandboxRequestError(
                error_code="unknown_tutorial",
                message=f"Unknown tutorial id: {tutorial_id!r}",
            )
        return self._start_state(
            session_kind="tutorial",
            start_id=tutorial.start_id,
            tutorial_id=tutorial_id,
            tutorial=tutorial,
        )

    def install_catalog_item(
        self,
        item_id: str,
        *,
        config: Mapping[str, object],
        equipment_receipt_id: str | None = None,
    ) -> BuildApplyResult:
        state = self._require_state()
        item = self._sandbox_catalog.get(item_id)
        if item is None:
            raise SandboxRequestError(
                error_code="unknown_item", message=f"Unknown item id: {item_id!r}"
            )
        if not self._is_supported_on_active_start(item):
            raise SandboxRequestError(
                error_code="unsupported_on_start",
                message=f"Item {item_id!r} is unsupported on start {state.active_start_id!r}",
            )
        if self._economics_api.is_cash_ledger_open() and not equipment_receipt_id:
            raise SandboxRequestError(
                error_code="missing_equipment_receipt",
                message="equipment_receipt_id is required when cash ledger is open.",
            )
        self._validate_install_config(item_id=item_id, config=config)

        instance_id = f"{item_id}:{state.next_install_index}"
        state.next_install_index += 1
        state.installed_item_instance_ids.append(instance_id)
        state.installed_item_counts_by_id[item_id] = (
            state.installed_item_counts_by_id.get(item_id, 0) + 1
        )
        self._refresh_tutorial_goal_statuses(state)
        return BuildApplyResult(success=True, reason_code=None, snapshot=self._snapshot())

    def load_feed_inventory(
        self,
        material_id: str,
        quantity_mol: float,
        *,
        procurement_receipt_id: str | None = None,
    ) -> InventoryLoadResult:
        state = self._require_state()
        if state.session_kind == "tutorial":
            raise SandboxRequestError(
                error_code="tutorial_feed_loading_disabled",
                message="Feed loading is disabled while a tutorial session is active.",
            )
        if not math.isfinite(quantity_mol) or quantity_mol <= 0.0:
            raise SandboxRequestError(
                error_code="invalid_quantity", message="quantity_mol must be > 0."
            )
        if material_id not in set(LEARNER_START_SCAFFOLDS[state.active_start_id].named_feed_ids):
            raise SandboxRequestError(
                error_code="unknown_material",
                message=f"Unknown material id for this start: {material_id!r}",
            )
        if self._economics_api.is_cash_ledger_open() and not procurement_receipt_id:
            raise SandboxRequestError(
                error_code="missing_procurement_receipt",
                message="procurement_receipt_id is required when cash ledger is open.",
            )

        state.feed_inventory_by_material_id[material_id] = state.feed_inventory_by_material_id.get(
            material_id, 0.0
        ) + float(quantity_mol)
        return InventoryLoadResult(success=True, reason_code=None, snapshot=self._snapshot())

    def advance(self, dt_s: float) -> SimulationAdvanceResult:
        state = self._require_state()
        if not math.isfinite(dt_s) or dt_s <= 0.0:
            raise SandboxRequestError(
                error_code="invalid_dt_s", message="dt_s must be finite and > 0."
            )

        feed_consumption_by_material_id: dict[str, float] = {}
        product_production_by_product_id: dict[str, float] = {}

        if state.session_kind == "sandbox":
            available_total = sum(
                max(0.0, qty) for qty in state.feed_inventory_by_material_id.values()
            )
            if available_total < float(dt_s):
                raise SandboxRequestError(
                    error_code="insufficient_feed_inventory",
                    message="Cannot advance with less feed inventory than the requested step requires.",
                )

            total_consumption = float(dt_s)
            remaining_to_consume = total_consumption
            for material_id in sorted(state.feed_inventory_by_material_id):
                if remaining_to_consume <= 0.0:
                    break
                current = state.feed_inventory_by_material_id[material_id]
                consume = min(current, remaining_to_consume)
                if consume <= 0.0:
                    continue
                state.feed_inventory_by_material_id[material_id] = current - consume
                feed_consumption_by_material_id[material_id] = consume
                remaining_to_consume -= consume

            produced_a = total_consumption * 0.6
            produced_b = total_consumption * 0.4
            state.product_inventory_by_product_id["product_a"] = (
                state.product_inventory_by_product_id.get("product_a", 0.0) + produced_a
            )
            state.product_inventory_by_product_id["product_b"] = (
                state.product_inventory_by_product_id.get("product_b", 0.0) + produced_b
            )
            product_production_by_product_id = {"product_a": produced_a, "product_b": produced_b}
        elif state.active_start_id == "recycle_purge_tutorial_start_v1":
            produced_a = float(dt_s) * 0.1
            state.product_inventory_by_product_id["product_a"] = (
                state.product_inventory_by_product_id.get("product_a", 0.0) + produced_a
            )
            product_production_by_product_id = {"product_a": produced_a}

        state.elapsed_time_s += float(dt_s)
        self._refresh_tutorial_goal_statuses(state)
        return SimulationAdvanceResult(
            snapshot=self._snapshot(),
            feed_consumption_by_material_id=feed_consumption_by_material_id,
            product_production_by_product_id=product_production_by_product_id,
            published_signal_values_by_id=self._build_published_signal_values(
                state=state,
                dt_s=float(dt_s),
                feed_consumption_by_material_id=feed_consumption_by_material_id,
                product_production_by_product_id=product_production_by_product_id,
            ),
        )

    def withdraw_product_inventory(
        self,
        product_id: str,
        quantity_mol: float,
    ) -> InventoryWithdrawalResult:
        state = self._require_state()
        known_product_ids = set(state.product_inventory_by_product_id)
        if product_id not in known_product_ids:
            raise SandboxRequestError(
                error_code="unknown_product",
                message=f"Unknown product id for this start: {product_id!r}",
            )
        if not math.isfinite(quantity_mol) or quantity_mol <= 0.0:
            raise SandboxRequestError(
                error_code="invalid_quantity", message="quantity_mol must be > 0."
            )
        available = state.product_inventory_by_product_id.get(product_id, 0.0)
        if quantity_mol > available:
            raise SandboxRequestError(
                error_code="insufficient_product_inventory",
                message=f"Requested {quantity_mol} mol, only {available} available.",
            )

        state.product_inventory_by_product_id[product_id] = available - quantity_mol
        withdrawal_id = f"wd-{state.next_withdrawal_index}"
        state.next_withdrawal_index += 1
        if self._economics_api.is_cash_ledger_open():
            self._economics_api.register_product_withdrawal_handoff(
                withdrawal_id,
                product_id=product_id,
                quantity_mol=float(quantity_mol),
            )
        return InventoryWithdrawalResult(
            withdrawal_id=withdrawal_id,
            success=True,
            reason_code=None,
            withdrawn_quantity_mol=float(quantity_mol),
            snapshot=self._snapshot(),
        )

    def get_simulation_state(self) -> SimulationSessionSnapshot:
        return self._snapshot()

    def _start_state(
        self,
        *,
        session_kind: str,
        start_id: str,
        tutorial_id: str | None = None,
        tutorial: TutorialDefinition | None = None,
    ) -> SimulationSessionSnapshot:
        scaffold = LEARNER_START_SCAFFOLDS[start_id]
        tutorial_statuses: dict[str, TutorialGoalStatus] = {}
        if tutorial is not None:
            tutorial_statuses = {
                goal.goal_id: TutorialGoalStatus(
                    goal_id=goal.goal_id,
                    completed=False,
                    completed_at_time_s=None,
                )
                for goal in tutorial.goals
            }

        self._state = _RuntimeSessionState(
            session_kind=session_kind,
            active_start_id=start_id,
            active_tutorial_id=tutorial_id,
            feed_inventory_by_material_id={
                material_id: 0.0 for material_id in scaffold.named_feed_ids
            },
            product_inventory_by_product_id={
                product_id: 0.0 for product_id in scaffold.named_sink_ids
            },
            tutorial_definition=tutorial,
            tutorial_goal_status_by_id=tutorial_statuses,
        )
        return self._snapshot()

    def _require_state(self) -> _RuntimeSessionState:
        if self._state is None:
            raise SandboxRequestError(
                error_code="no_active_session",
                message="No active simulation session.",
            )
        return self._state

    def _snapshot(self) -> SimulationSessionSnapshot:
        state = self._require_state()
        return SimulationSessionSnapshot(
            session_kind=state.session_kind,  # type: ignore[arg-type]
            active_start_id=state.active_start_id,
            active_tutorial_id=state.active_tutorial_id,
            elapsed_time_s=state.elapsed_time_s,
            tutorial_completion_time_s=state.tutorial_completion_time_s,
            installed_item_instance_ids=tuple(state.installed_item_instance_ids),
            feed_inventory_by_material_id=dict(state.feed_inventory_by_material_id),
            product_inventory_by_product_id=dict(state.product_inventory_by_product_id),
            tutorial_goal_status_by_id=dict(state.tutorial_goal_status_by_id),
        )

    def _validate_install_config(self, *, item_id: str, config: Mapping[str, object]) -> None:
        if item_id != "build_process_line":
            return
        has_length = "length_m" in config
        has_radius = "radius_m" in config
        if has_length != has_radius:
            raise SandboxRequestError(
                error_code="invalid_config",
                message="build_process_line config requires both length_m and radius_m when provided.",
            )

    def _is_supported_on_active_start(self, item: SandboxCatalogItemDefinition) -> bool:
        state = self._require_state()
        return state.active_start_id in set(item.supported_start_ids)

    def _refresh_tutorial_goal_statuses(self, state: _RuntimeSessionState) -> None:
        tutorial = state.tutorial_definition
        if tutorial is None:
            return

        statuses = dict(state.tutorial_goal_status_by_id)
        made_progress = True
        while made_progress:
            made_progress = False
            for goal in tutorial.goals:
                existing = statuses[goal.goal_id]
                if existing.completed:
                    continue
                prereqs_done = all(statuses[pre].completed for pre in goal.prerequisite_goal_ids)
                if not prereqs_done:
                    continue
                installed_count = state.installed_item_counts_by_id.get(goal.item_id, 0)
                if installed_count >= goal.required_count:
                    statuses[goal.goal_id] = TutorialGoalStatus(
                        goal_id=goal.goal_id,
                        completed=True,
                        completed_at_time_s=state.elapsed_time_s,
                    )
                    made_progress = True

        state.tutorial_goal_status_by_id = statuses
        if (
            state.tutorial_completion_time_s is None
            and statuses
            and all(status.completed for status in statuses.values())
        ):
            state.tutorial_completion_time_s = state.elapsed_time_s

    def _build_published_signal_values(
        self,
        *,
        state: _RuntimeSessionState,
        dt_s: float,
        feed_consumption_by_material_id: Mapping[str, float],
        product_production_by_product_id: Mapping[str, float],
    ) -> dict[str, float]:
        signal_values = {
            signal_id: 0.0
            for signal_id in self._start_catalog[state.active_start_id].published_signal_ids
        }

        if "feed_a_draw_mol_s" in signal_values:
            signal_values["feed_a_draw_mol_s"] = (
                feed_consumption_by_material_id.get("feed_a", 0.0) / dt_s
            )
        if "feed_b_draw_mol_s" in signal_values:
            signal_values["feed_b_draw_mol_s"] = (
                feed_consumption_by_material_id.get("feed_b", 0.0) / dt_s
            )
        if "feed_draw_mol_s" in signal_values:
            signal_values["feed_draw_mol_s"] = sum(feed_consumption_by_material_id.values()) / dt_s

        if "product_a_flow_mol_s" in signal_values:
            signal_values["product_a_flow_mol_s"] = (
                product_production_by_product_id.get("product_a", 0.0) / dt_s
            )
        if "product_b_flow_mol_s" in signal_values:
            signal_values["product_b_flow_mol_s"] = (
                product_production_by_product_id.get("product_b", 0.0) / dt_s
            )
        if "vapor_product_flow_mol_s" in signal_values:
            signal_values["vapor_product_flow_mol_s"] = (
                product_production_by_product_id.get("vapor_product", 0.0) / dt_s
            )
        if "liquid_product_flow_mol_s" in signal_values:
            signal_values["liquid_product_flow_mol_s"] = (
                product_production_by_product_id.get("liquid_product", 0.0) / dt_s
            )

        if "heating_steam_duty_W" in signal_values:
            signal_values["heating_steam_duty_W"] = (
                50_000.0 if sum(feed_consumption_by_material_id.values()) > 0.0 else 0.0
            )
        if "total_normalized_pump_load" in signal_values:
            signal_values["total_normalized_pump_load"] = (
                1.0 if sum(feed_consumption_by_material_id.values()) > 0.0 else 0.0
            )
        return signal_values


_API_BY_SCOPE: dict[str, SandboxSessionRuntime] = {}


def _session_scope_key() -> str:
    return os.environ.get("PYTEST_CURRENT_TEST", "global")


def _api() -> SandboxSessionRuntime:
    scope = _session_scope_key()
    existing = _API_BY_SCOPE.get(scope)
    if existing is not None:
        return existing
    created = SandboxSessionRuntime(economics_api=economics)
    _API_BY_SCOPE[scope] = created
    return created


def start_sandbox() -> SimulationSessionSnapshot:
    return _api().start_sandbox()


def start_tutorial(tutorial_id: str) -> SimulationSessionSnapshot:
    return _api().start_tutorial(tutorial_id)


def install_catalog_item(
    item_id: str,
    *,
    config: Mapping[str, object],
    equipment_receipt_id: str | None = None,
) -> BuildApplyResult:
    return _api().install_catalog_item(
        item_id,
        config=config,
        equipment_receipt_id=equipment_receipt_id,
    )


def load_feed_inventory(
    material_id: str,
    quantity_mol: float,
    *,
    procurement_receipt_id: str | None = None,
) -> InventoryLoadResult:
    return _api().load_feed_inventory(
        material_id,
        quantity_mol,
        procurement_receipt_id=procurement_receipt_id,
    )


def advance(dt_s: float) -> SimulationAdvanceResult:
    return _api().advance(dt_s)


def withdraw_product_inventory(product_id: str, quantity_mol: float) -> InventoryWithdrawalResult:
    return _api().withdraw_product_inventory(product_id, quantity_mol)


def get_simulation_state() -> SimulationSessionSnapshot:
    return _api().get_simulation_state()

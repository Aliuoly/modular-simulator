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
    ProgressionSnapshot,
    ResearchSubmissionResult,
    SandboxCatalogItemDefinition,
    SandboxRequestError,
    SimulationAdvanceResult,
    SimulationSessionSnapshot,
    TutorialDefinition,
    TutorialGoalStatus,
)
from modular_simulation.gameplay.progression import (
    RESEARCH_CATALOG,
    STARTER_STAGE_IDS,
    UNLOCK_RESEARCH_ID,
    build_progression_snapshot,
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
    progression_snapshot: ProgressionSnapshot | None = None
    next_install_index: int = 1
    next_withdrawal_index: int = 1
    process_item_id_by_process_id: dict[str, str] = field(default_factory=dict)
    directed_edges: list[tuple[str, str]] = field(default_factory=list)
    line_endpoints_by_line_id: dict[str, tuple[str, str]] = field(default_factory=dict)
    support_component_nodes_by_item_id: dict[str, set[str]] = field(default_factory=dict)


_SANDBOX_STARTER_PROGRESSION = build_progression_snapshot(STARTER_STAGE_IDS)
_SANDBOX_UNLOCKED_PROGRESSION = build_progression_snapshot(
    (
        "gas_inlet_separation_v1",
        "teg_dehydration_v1",
        "jt_low_temperature_separation_v1",
        "condensate_stabilization_v1",
    )
)

_SANDBOX_FEED_IDS = ("sweet_wet_gas",)
_SANDBOX_PRODUCT_IDS = (
    "separator_gas",
    "unstabilized_condensate",
    "dry_gas",
    "ngl_liquids",
    "stabilized_condensate",
)

_SANDBOX_PROGRESS_ITEM_IDS = frozenset(
    (
        *_SANDBOX_STARTER_PROGRESSION.available_item_ids,
        *_SANDBOX_UNLOCKED_PROGRESSION.available_item_ids,
    )
)

_SANDBOX_RESEARCH_RECIPE = RESEARCH_CATALOG[UNLOCK_RESEARCH_ID].required_product_quantities

_DRY_GAS_SUPPORT_ITEM_IDS = (
    "place_rich_glycol_flash_tank",
    "place_lean_rich_glycol_exchanger",
    "place_teg_regenerator",
    "install_glycol_circulation_pump",
)


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
        if item is None and item_id in _SANDBOX_PROGRESS_ITEM_IDS:
            item = SandboxCatalogItemDefinition(
                item_id=item_id,
                title=item_id,
                item_kind="unit_blueprint" if item_id != "build_process_line" else "line",
                apply_kind=(
                    "add_process" if item_id != "build_process_line" else "connect_configure_line"
                ),
                default_config={},
                required_user_inputs=(),
                supported_start_ids=("phase1_process_sandbox_v1",),
                educational_summary="",
            )
        if item is None:
            raise SandboxRequestError(
                error_code="unknown_item", message=f"Unknown item id: {item_id!r}"
            )
        if not self._is_supported_on_active_start(item):
            raise SandboxRequestError(
                error_code="unsupported_on_start",
                message=f"Item {item_id!r} is unsupported on start {state.active_start_id!r}",
            )
        if state.active_start_id == "phase1_process_sandbox_v1":
            progression = state.progression_snapshot
            if progression is None or item_id not in set(progression.available_item_ids):
                raise SandboxRequestError(
                    error_code="item_locked",
                    message=f"Item {item_id!r} is locked in current progression state.",
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
        self._track_topology_install(state=state, item_id=item_id, config=config)
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
        if material_id not in set(_feed_ids_for_start(state.active_start_id)):
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

            product_production_by_product_id = self._compute_gas_product_generation(
                state=state,
                total_consumption=total_consumption,
            )
            for product_id, produced in product_production_by_product_id.items():
                state.product_inventory_by_product_id[product_id] = (
                    state.product_inventory_by_product_id.get(product_id, 0.0) + produced
                )
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
            handoff_product_id = _handoff_sale_product_id(product_id)
            self._economics_api.register_product_withdrawal_handoff(
                withdrawal_id,
                product_id=handoff_product_id,
                quantity_mol=float(quantity_mol),
            )
        return InventoryWithdrawalResult(
            withdrawal_id=withdrawal_id,
            success=True,
            reason_code=None,
            withdrawn_quantity_mol=float(quantity_mol),
            snapshot=self._snapshot(),
        )

    def submit_research_unlock(
        self,
        research_id: str,
        *,
        submitted_quantities_by_product_id: Mapping[str, float],
    ) -> ResearchSubmissionResult:
        state = self._require_state()
        if state.session_kind != "sandbox":
            raise SandboxRequestError(
                error_code="research_unavailable_for_session",
                message="Research submission is unavailable for tutorial sessions.",
            )
        if research_id != UNLOCK_RESEARCH_ID:
            raise SandboxRequestError(
                error_code="unknown_research_unlock",
                message=f"Unknown research id: {research_id!r}",
            )
        progression = state.progression_snapshot
        if progression is None or research_id not in set(progression.available_research_ids):
            raise SandboxRequestError(
                error_code="research_not_available",
                message=f"Research id is unavailable in current progression state: {research_id!r}",
            )

        expected_ids = set(_SANDBOX_RESEARCH_RECIPE)
        submitted_ids = set(submitted_quantities_by_product_id)
        if submitted_ids != expected_ids:
            raise SandboxRequestError(
                error_code="invalid_quantity",
                message="submitted_quantities_by_product_id must match the exact recipe ids.",
            )

        for product_id, required_qty in _SANDBOX_RESEARCH_RECIPE.items():
            raw = submitted_quantities_by_product_id.get(product_id)
            if not isinstance(raw, (int, float)):
                raise SandboxRequestError(
                    error_code="invalid_quantity",
                    message=f"Submitted quantity for {product_id!r} must be numeric.",
                )
            qty = float(raw)
            if not math.isfinite(qty) or qty <= 0.0 or qty != required_qty:
                raise SandboxRequestError(
                    error_code="invalid_quantity",
                    message=f"Submitted quantity for {product_id!r} must be exactly {required_qty}.",
                )
            available = state.product_inventory_by_product_id.get(product_id, 0.0)
            if available < qty:
                raise SandboxRequestError(
                    error_code="insufficient_product_inventory",
                    message=f"Insufficient product inventory for {product_id!r}.",
                )

        for product_id, qty in _SANDBOX_RESEARCH_RECIPE.items():
            state.product_inventory_by_product_id[product_id] -= qty

        state.progression_snapshot = _SANDBOX_UNLOCKED_PROGRESSION
        return ResearchSubmissionResult(success=True, reason_code=None, snapshot=self._snapshot())

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
                material_id: 0.0 for material_id in _feed_ids_for_start(start_id)
            },
            product_inventory_by_product_id={
                product_id: 0.0 for product_id in _product_ids_for_start(start_id)
            },
            tutorial_definition=tutorial,
            tutorial_goal_status_by_id=tutorial_statuses,
            progression_snapshot=(
                _SANDBOX_STARTER_PROGRESSION if start_id == "phase1_process_sandbox_v1" else None
            ),
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
            progression_snapshot=state.progression_snapshot,
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

    def _track_topology_install(
        self,
        *,
        state: _RuntimeSessionState,
        item_id: str,
        config: Mapping[str, object],
    ) -> None:
        if state.active_start_id != "phase1_process_sandbox_v1":
            return
        if item_id == "build_process_line":
            source = config.get("source")
            target = config.get("target")
            if isinstance(source, str) and isinstance(target, str):
                raw_line_id = config.get("line_id")
                if isinstance(raw_line_id, str) and raw_line_id:
                    line_id = raw_line_id
                else:
                    line_id = f"line_{len(state.line_endpoints_by_line_id) + 1}"
                line_node = f"line:{line_id}"
                state.line_endpoints_by_line_id[line_id] = (source, target)
                state.directed_edges.append((source, line_node))
                state.directed_edges.append((line_node, target))
                self._attach_endpoint_process_node(state=state, endpoint=source)
                self._attach_endpoint_process_node(state=state, endpoint=target)
            return

        if item_id == "place_teg_regenerator":
            process_id = config.get("process_id")
            if not isinstance(process_id, str):
                return
            state.process_item_id_by_process_id[process_id] = item_id
            state.support_component_nodes_by_item_id.setdefault(item_id, set()).add(process_id)
            return

        if item_id == "place_condensate_stabilizer":
            process_id = config.get("process_id")
            if not isinstance(process_id, str):
                return
            state.process_item_id_by_process_id[process_id] = item_id
            return

        if item_id in {"install_glycol_circulation_pump", "install_jt_valve"}:
            line_id = config.get("line_id")
            if not isinstance(line_id, str):
                return
            line_node = f"line:{line_id}"
            overlay_node = f"overlay:{item_id}:{line_id}"
            state.support_component_nodes_by_item_id.setdefault(item_id, set()).add(overlay_node)
            state.directed_edges.append((line_node, overlay_node))
            state.directed_edges.append((overlay_node, line_node))
            return

        process_id = config.get("process_id")
        if not isinstance(process_id, str):
            return
        state.process_item_id_by_process_id[process_id] = item_id
        if item_id in set(_DRY_GAS_SUPPORT_ITEM_IDS):
            state.support_component_nodes_by_item_id.setdefault(item_id, set()).add(process_id)

    def _attach_endpoint_process_node(self, *, state: _RuntimeSessionState, endpoint: str) -> None:
        process_id = self._process_id_for_node(state=state, node=endpoint)
        if process_id is None:
            return
        state.directed_edges.append((endpoint, process_id))
        state.directed_edges.append((process_id, endpoint))

    def _compute_gas_product_generation(
        self,
        *,
        state: _RuntimeSessionState,
        total_consumption: float,
    ) -> dict[str, float]:
        requested: dict[str, float] = {}

        separator_path = self._find_path_with_item_sequence(
            state=state,
            source_id="sweet_wet_gas",
            sink_id="separator_gas",
            required_sequence=("place_inlet_gas_separator",),
        )
        if separator_path is not None and self._path_has_item_endpoint_port(
            state=state,
            path=separator_path,
            item_id="place_inlet_gas_separator",
            port_name="vapor_outlet",
        ):
            requested["separator_gas"] = total_consumption * 0.6

        unstabilized_path = self._find_path_with_item_sequence(
            state=state,
            source_id="sweet_wet_gas",
            sink_id="unstabilized_condensate",
            required_sequence=("place_inlet_gas_separator",),
        )
        if unstabilized_path is not None and self._path_has_item_endpoint_port(
            state=state,
            path=unstabilized_path,
            item_id="place_inlet_gas_separator",
            port_name="liquid_outlet",
        ):
            requested["unstabilized_condensate"] = total_consumption * 0.2

        dry_path = self._find_path_with_item_sequence(
            state=state,
            source_id="sweet_wet_gas",
            sink_id="dry_gas",
            required_sequence=("place_inlet_gas_separator", "place_teg_contactor"),
        )
        if (
            dry_path is not None
            and self._path_has_item_endpoint_port(
                state=state,
                path=dry_path,
                item_id="place_teg_contactor",
                port_name="outlet_1",
            )
            and self._dry_gas_support_is_connected(state=state, qualifying_path_nodes=dry_path)
        ):
            requested["dry_gas"] = total_consumption * 0.2

        ngl_path = self._find_path_with_item_sequence(
            state=state,
            source_id="sweet_wet_gas",
            sink_id="ngl_liquids",
            required_sequence=(
                "place_inlet_gas_separator",
                "place_teg_contactor",
                "place_gas_gas_exchanger",
                "place_low_temperature_separator",
            ),
        )
        if (
            ngl_path is not None
            and self._path_has_item_endpoint_port(
                state=state,
                path=ngl_path,
                item_id="place_teg_contactor",
                port_name="outlet_1",
            )
            and self._path_has_jt_valve_immediately_upstream_of_item(
                state=state,
                path=ngl_path,
                item_id="place_low_temperature_separator",
            )
        ):
            requested["ngl_liquids"] = total_consumption * 0.15

        stabilized_path = self._find_path_with_item_sequence(
            state=state,
            source_id="sweet_wet_gas",
            sink_id="stabilized_condensate",
            required_sequence=("place_inlet_gas_separator", "place_condensate_stabilizer"),
        )
        if stabilized_path is not None and self._path_has_item_endpoint_port(
            state=state,
            path=stabilized_path,
            item_id="place_inlet_gas_separator",
            port_name="liquid_outlet",
        ):
            requested["stabilized_condensate"] = total_consumption * 0.15

        requested_total = sum(requested.values())
        if requested_total <= 0.0:
            return {}

        if requested_total <= total_consumption + 1e-12:
            return requested

        scale = total_consumption / requested_total
        return {product_id: qty * scale for product_id, qty in requested.items()}

    def _find_path_with_item_sequence(
        self,
        *,
        state: _RuntimeSessionState,
        source_id: str,
        sink_id: str,
        required_sequence: tuple[str, ...],
    ) -> tuple[str, ...] | None:
        adjacency: dict[str, list[str]] = {}
        for src, dst in state.directed_edges:
            adjacency.setdefault(src, []).append(dst)

        stack: list[tuple[str, tuple[str, ...], frozenset[str]]] = [
            (source_id, (source_id,), frozenset({source_id}))
        ]
        while stack:
            node, path, seen = stack.pop()
            if node == sink_id and self._path_matches_sequence(
                state=state,
                path=path,
                required_sequence=required_sequence,
            ):
                return path
            for next_node in adjacency.get(node, []):
                if next_node in seen:
                    continue
                stack.append((next_node, (*path, next_node), seen | {next_node}))
        return None

    def _path_matches_sequence(
        self,
        *,
        state: _RuntimeSessionState,
        path: tuple[str, ...],
        required_sequence: tuple[str, ...],
    ) -> bool:
        found: list[str] = []
        for node in path:
            if node.startswith("overlay:"):
                parts = node.split(":")
                if len(parts) >= 3:
                    found.append(parts[1])
                continue
            if node in state.process_item_id_by_process_id:
                found.append(state.process_item_id_by_process_id[node])
                continue
            process_id = self._process_id_for_node(state=state, node=node)
            if process_id is not None:
                found.append(state.process_item_id_by_process_id[process_id])
        idx = 0
        for item_id in found:
            if idx < len(required_sequence) and item_id == required_sequence[idx]:
                idx += 1
        return idx == len(required_sequence)

    def _process_id_for_node(self, *, state: _RuntimeSessionState, node: str) -> str | None:
        if node in state.process_item_id_by_process_id:
            return node
        if "." not in node:
            return None
        process_id, _sep, _port_name = node.partition(".")
        if process_id in state.process_item_id_by_process_id:
            return process_id
        return None

    def _path_has_item_endpoint_port(
        self,
        *,
        state: _RuntimeSessionState,
        path: tuple[str, ...],
        item_id: str,
        port_name: str,
    ) -> bool:
        suffix = f".{port_name}"
        for node in path:
            if not node.endswith(suffix):
                continue
            process_id = self._process_id_for_node(state=state, node=node)
            if process_id is None:
                continue
            if state.process_item_id_by_process_id.get(process_id) == item_id:
                return True
        return False

    def _path_has_jt_valve_immediately_upstream_of_item(
        self,
        *,
        state: _RuntimeSessionState,
        path: tuple[str, ...],
        item_id: str,
    ) -> bool:
        jt_nodes = state.support_component_nodes_by_item_id.get("install_jt_valve", set())
        if not jt_nodes:
            return False
        for idx, node in enumerate(path):
            if not node.startswith("line:"):
                continue
            if idx + 1 >= len(path):
                continue
            downstream = path[idx + 1]
            process_id = self._process_id_for_node(state=state, node=downstream)
            if process_id is None:
                continue
            if state.process_item_id_by_process_id.get(process_id) != item_id:
                continue
            line_id = node.partition(":")[2]
            if f"overlay:install_jt_valve:{line_id}" in jt_nodes:
                return True
        return False

    def _has_path_with_item(
        self,
        *,
        state: _RuntimeSessionState,
        source_id: str,
        sink_id: str,
        required_sequence: tuple[str, ...],
    ) -> bool:
        return (
            self._find_path_with_item_sequence(
                state=state,
                source_id=source_id,
                sink_id=sink_id,
                required_sequence=required_sequence,
            )
            is not None
        )

    def _dry_gas_support_is_connected(
        self,
        *,
        state: _RuntimeSessionState,
        qualifying_path_nodes: tuple[str, ...],
    ) -> bool:
        undirected: dict[str, set[str]] = {}
        for src, dst in state.directed_edges:
            undirected.setdefault(src, set()).add(dst)
            undirected.setdefault(dst, set()).add(src)

        seed_nodes = set(qualifying_path_nodes)
        if not seed_nodes:
            return False
        stack = list(seed_nodes)
        component = set(seed_nodes)
        while stack:
            node = stack.pop()
            for nxt in undirected.get(node, set()):
                if nxt in component:
                    continue
                component.add(nxt)
                stack.append(nxt)

        for item_id in _DRY_GAS_SUPPORT_ITEM_IDS:
            nodes = state.support_component_nodes_by_item_id.get(item_id, set())
            if not nodes:
                return False
            if not any(node in component for node in nodes):
                return False
        return True

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
        if "sweet_wet_gas_draw_mol_s" in signal_values:
            signal_values["sweet_wet_gas_draw_mol_s"] = (
                feed_consumption_by_material_id.get("sweet_wet_gas", 0.0) / dt_s
            )

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
        if "separator_gas_flow_mol_s" in signal_values:
            signal_values["separator_gas_flow_mol_s"] = (
                product_production_by_product_id.get("separator_gas", 0.0) / dt_s
            )
        if "unstabilized_condensate_flow_mol_s" in signal_values:
            signal_values["unstabilized_condensate_flow_mol_s"] = (
                product_production_by_product_id.get("unstabilized_condensate", 0.0) / dt_s
            )
        if "dry_gas_flow_mol_s" in signal_values:
            signal_values["dry_gas_flow_mol_s"] = (
                product_production_by_product_id.get("dry_gas", 0.0) / dt_s
            )
        if "ngl_liquids_flow_mol_s" in signal_values:
            signal_values["ngl_liquids_flow_mol_s"] = (
                product_production_by_product_id.get("ngl_liquids", 0.0) / dt_s
            )
        if "stabilized_condensate_flow_mol_s" in signal_values:
            signal_values["stabilized_condensate_flow_mol_s"] = (
                product_production_by_product_id.get("stabilized_condensate", 0.0) / dt_s
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


def _feed_ids_for_start(start_id: str) -> tuple[str, ...]:
    if start_id == "phase1_process_sandbox_v1":
        return _SANDBOX_FEED_IDS
    return LEARNER_START_SCAFFOLDS[start_id].named_feed_ids


def _product_ids_for_start(start_id: str) -> tuple[str, ...]:
    if start_id == "phase1_process_sandbox_v1":
        return _SANDBOX_PRODUCT_IDS
    return LEARNER_START_SCAFFOLDS[start_id].named_sink_ids


def _handoff_sale_product_id(product_id: str) -> str:
    if product_id == "separator_gas":
        return "separator_gas"
    if product_id == "unstabilized_condensate":
        return "unstabilized_condensate"
    if product_id == "dry_gas":
        return "dry_gas"
    if product_id == "ngl_liquids":
        return "ngl_liquids"
    if product_id == "stabilized_condensate":
        return "stabilized_condensate"
    if product_id in {"separator_gas", "dry_gas", "ngl_liquids"}:
        return "product_a"
    if product_id in {"unstabilized_condensate", "stabilized_condensate"}:
        return "product_b"
    return product_id


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


def submit_research_unlock(
    research_id: str,
    *,
    submitted_quantities_by_product_id: Mapping[str, float],
) -> ResearchSubmissionResult:
    return _api().submit_research_unlock(
        research_id,
        submitted_quantities_by_product_id=submitted_quantities_by_product_id,
    )

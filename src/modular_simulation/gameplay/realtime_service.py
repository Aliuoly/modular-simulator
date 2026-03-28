"""Authoritative realtime gameplay service for the phase-1 slice."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from importlib import import_module as _import_module
from math import isfinite
from time import monotonic as _time_monotonic
from typing import Mapping
from uuid import uuid4


def _monotonic() -> float:
    """Thin wrapper around time.monotonic for testability."""
    return _time_monotonic()


from modular_simulation.gameplay.board_layout import BoardLayoutRuntime
from modular_simulation.gameplay.contracts import (
    PlayStartDefinition,
    SandboxCatalogItemDefinition,
    SandboxRequestError,
)
from modular_simulation.gameplay.sandbox_catalog import build_sandbox_catalog
from modular_simulation.gameplay.start_catalog import build_start_catalog
from modular_simulation.gameplay.service_contracts import (
    CommandAcceptedResponse,
    GameBootstrapResponse,
    GameSnapshot,
    SessionCreatedResponse,
)
from modular_simulation.gameplay.start_runtime import (
    MODE_TO_START_ID,
    SUPPORTED_MODE_IDS,
    StartRuntimeBundle,
    create_start_runtime_bundle,
)

_SANDBOX_STARTER_BUILD_ITEM_IDS: tuple[str, ...] = (
    "place_inlet_gas_separator",
    "place_teg_contactor",
    "place_rich_glycol_flash_tank",
    "place_lean_rich_glycol_exchanger",
    "place_teg_regenerator",
    "install_glycol_circulation_pump",
    "build_process_line",
)

# Backward-compatible exported constant name used by API/tests.
SUPPORTED_BUILD_ITEM_IDS: tuple[str, ...] = _SANDBOX_STARTER_BUILD_ITEM_IDS

_RESEARCH_IDS: frozenset[str] = frozenset({"unlock_cold_recovery_train_v1"})

_TUTORIAL_BUILD_ITEM_IDS: tuple[str, ...] = (
    "place_heater_cooler",
    "place_flash_drum",
    "build_process_line",
)

PUBLIC_BUILD_FAMILY_MATRIX: tuple[tuple[str, str], ...] = (
    ("unit_blueprint", "add_process"),
    ("line", "connect_configure_line"),
)

DEFERRED_PUBLIC_BUILD_ITEM_IDS: frozenset[str] = frozenset(
    {
        "place_component_separator",
        "place_merge_junction_2x1",
        "place_split_junction_1x2",
    }
)

ADD_PROCESS_METADATA_KEYS: frozenset[str] = frozenset(
    {"unit_module", "unit_type", "constructor_payload"}
)


def _sale_product_id_for_economics(product_id: str) -> str:
    return product_id


def _feed_material_id_for_economics(material_id: str) -> str:
    return material_id


def _equipment_item_id_for_economics(item_id: str) -> str:
    return item_id


def _fallback_catalog_item(item_id: str) -> SandboxCatalogItemDefinition:
    if item_id == "build_process_line":
        return SandboxCatalogItemDefinition(
            item_id=item_id,
            title="Process line",
            item_kind="line",
            apply_kind="connect_configure_line",
            default_config={"radius_m": 0.05, "length_m": 1.0},
            required_user_inputs=("source", "target"),
            supported_start_ids=("phase1_process_sandbox_v1", "heater_flash_tutorial_start_v1"),
            educational_summary="",
        )
    return SandboxCatalogItemDefinition(
        item_id=item_id,
        title=item_id,
        item_kind="unit_blueprint",
        apply_kind="add_process",
        default_config={
            "unit_type": "HeaterCooler",
            "unit_module": "modular_simulation.unit_processes.thermal.heater_cooler",
            "constructor_payload": {
                "mode": "temperature",
                "external_outlet_temperature": 325.0,
                "pressure_drop": 0.0,
            },
        },
        required_user_inputs=("process_id",),
        supported_start_ids=("phase1_process_sandbox_v1", "heater_flash_tutorial_start_v1"),
        educational_summary="",
    )


_STAGEWISE_COMPAT_PORTS_BY_ITEM_ID: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "place_teg_regenerator": (("inlet",), ("outlet",)),
    "place_condensate_stabilizer": (("inlet",), ("outlet",)),
}


@dataclass(frozen=True)
class _UnitMetadata:
    """Resolved runtime-authoritative metadata for a unit_blueprint catalog item."""

    unit_module: str
    unit_type: str
    constructor_payload: dict[str, object]
    inlet_ports: tuple[str, ...]
    outlet_ports: tuple[str, ...]


class _MetadataResolutionError(Exception):
    """Sentinel exception raised at exactly the approved failure sites within
    _resolve_unit_metadata().  Only _install_unit() may catch this class.

    The three approved failure sites are:
    1. The target unit_module cannot be imported (ModuleNotFoundError for that module).
    2. The unit_type attribute does not exist on the imported module (AttributeError).
    3. The constructor_payload kwargs are invalid for the unit class (TypeError/ValueError).

    Import-time side-effect failures inside an otherwise valid module are NOT
    translated here; they are allowed to propagate as-is.
    """


def _resolve_unit_metadata(
    item: SandboxCatalogItemDefinition,
) -> _UnitMetadata:
    """Resolve runtime-authoritative unit metadata from a catalog item definition.

    For ``apply_kind="add_process"`` records, this helper extracts
    ``unit_module``, ``unit_type``, and ``constructor_payload`` from
    ``item.default_config``, then derives real declared inlet/outlet ports
    by importing the unit class and reading its ``.ports`` property.

    The helper is module-private; it must not be called for non-unit items.

    Only three exact failure sites raise ``_MetadataResolutionError``; all other
    exceptions propagate unchanged.  See ``_MetadataResolutionError`` for the
    approved failure-site list.
    """
    cfg = item.default_config
    unit_module = str(cfg["unit_module"])
    unit_type = str(cfg["unit_type"])
    raw_payload = cfg.get("constructor_payload", {})
    constructor_payload: dict[str, object] = dict(raw_payload) if raw_payload else {}

    # --- Failure site 1: missing configured module target ---
    # Only translate ModuleNotFoundError if it refers to the target module itself
    # (or a missing parent package).  A ModuleNotFoundError whose .name is a
    # dependency of an otherwise-valid module must propagate unchanged.
    try:
        mod = _import_module(unit_module)
    except ModuleNotFoundError as exc:
        if exc.name is not None and (
            exc.name == unit_module or unit_module.startswith(exc.name + ".")
        ):
            raise _MetadataResolutionError(
                f"unit_module {unit_module!r} cannot be imported: {exc}"
            ) from exc
        raise

    # --- Failure site 2: missing configured exported unit type ---
    try:
        unit_cls = getattr(mod, unit_type)
    except AttributeError as exc:
        raise _MetadataResolutionError(
            f"unit_type {unit_type!r} not found in module {unit_module!r}: {exc}"
        ) from exc

    # --- Failure site 3: constructor payload signature/validation failure ---
    try:
        instance = unit_cls(**constructor_payload)
    except (TypeError, ValueError) as exc:
        raise _MetadataResolutionError(
            f"constructor_payload is invalid for {unit_type!r}: {exc}"
        ) from exc

    ports = instance.ports

    return _UnitMetadata(
        unit_module=unit_module,
        unit_type=unit_type,
        constructor_payload=constructor_payload,
        inlet_ports=tuple(ports.inlets),
        outlet_ports=tuple(ports.outlets),
    )


SUPPORTED_SIMULATION_DT_S_PRESETS: tuple[float, ...] = (1 / 60, 1 / 30, 1 / 20)
DEFAULT_SIMULATION_DT_S: float = 1 / 60


@dataclass
class _ActiveSession:
    session_id: str
    mode_id: str
    simulation_dt_s: float
    runtime_bundle: StartRuntimeBundle
    board_layout: BoardLayoutRuntime
    last_wall_time_s: float = field(default_factory=_monotonic)
    lag_backlog_s: float = 0.0
    published_signal_values_by_id: dict[str, float] | None = None


class RealtimeGameService:
    def __init__(self) -> None:
        self._sandbox_catalog = build_sandbox_catalog()
        self._start_catalog = build_start_catalog()
        self._supported_build_item_ids_by_mode_id = {
            "phase1_process_sandbox_v1": _SANDBOX_STARTER_BUILD_ITEM_IDS,
            "heater_flash_guided_build_v1": _TUTORIAL_BUILD_ITEM_IDS,
        }
        self._active_session: _ActiveSession | None = None

    def get_bootstrap(self) -> GameBootstrapResponse:
        return GameBootstrapResponse(
            supported_mode_ids=SUPPORTED_MODE_IDS,
            supported_build_item_ids_by_mode_id=dict(self._supported_build_item_ids_by_mode_id),
            supported_simulation_dt_s_presets=SUPPORTED_SIMULATION_DT_S_PRESETS,
            default_simulation_dt_s=DEFAULT_SIMULATION_DT_S,
            pause_supported=False,
        )

    def create_session(
        self,
        *,
        mode_id: str,
        simulation_dt_s: float | None = None,
    ) -> SessionCreatedResponse:
        if self._active_session is not None:
            raise SandboxRequestError(
                error_code="session_already_active",
                message="An active local session already exists.",
            )
        if mode_id not in set(SUPPORTED_MODE_IDS):
            normalized_error = "unknown_mode" if mode_id == "unknown_mode" else "unsupported_mode"
            raise SandboxRequestError(
                error_code=normalized_error,
                message=f"Unsupported mode id: {mode_id!r}",
            )

        chosen_dt = DEFAULT_SIMULATION_DT_S if simulation_dt_s is None else float(simulation_dt_s)
        if chosen_dt not in set(SUPPORTED_SIMULATION_DT_S_PRESETS):
            raise SandboxRequestError(
                error_code="unsupported_simulation_dt_s",
                message=f"Unsupported simulation_dt_s: {chosen_dt!r}",
            )

        runtime_bundle = create_start_runtime_bundle(mode_id=mode_id)
        simulation_snapshot = runtime_bundle.sandbox_runtime.get_simulation_state()
        published_signal_values_by_id = {
            signal_id: 0.0 for signal_id in simulation_snapshot.tutorial_goal_status_by_id.keys()
        }
        # Use start catalog signal ids instead of tutorial-goal ids.
        published_signal_values_by_id = {
            signal_id: 0.0
            for signal_id in {
                *simulation_snapshot.feed_inventory_by_material_id.keys(),
                *simulation_snapshot.product_inventory_by_product_id.keys(),
            }
        }
        # Keep fixed keyset by active start metadata when available.
        start_id = MODE_TO_START_ID[mode_id]
        if start_id == "phase1_process_sandbox_v1":
            published_signal_values_by_id = {
                "sweet_wet_gas_draw_mol_s": 0.0,
                "separator_gas_flow_mol_s": 0.0,
                "unstabilized_condensate_flow_mol_s": 0.0,
                "dry_gas_flow_mol_s": 0.0,
                "ngl_liquids_flow_mol_s": 0.0,
                "stabilized_condensate_flow_mol_s": 0.0,
                "heating_steam_duty_W": 0.0,
                "total_normalized_pump_load": 0.0,
            }
        elif start_id == "heater_flash_tutorial_start_v1":
            published_signal_values_by_id = {
                "feed_draw_mol_s": 0.0,
                "vapor_product_flow_mol_s": 0.0,
                "liquid_product_flow_mol_s": 0.0,
                "heating_steam_duty_W": 0.0,
            }

        self._active_session = _ActiveSession(
            session_id=f"session-{uuid4()}",
            mode_id=mode_id,
            simulation_dt_s=chosen_dt,
            runtime_bundle=runtime_bundle,
            board_layout=BoardLayoutRuntime(),
            last_wall_time_s=_monotonic(),
            published_signal_values_by_id=published_signal_values_by_id,
        )
        return SessionCreatedResponse(
            session_id=self._active_session.session_id,
            snapshot=self._snapshot_for(self._active_session),
        )

    def get_snapshot(self, *, session_id: str) -> GameSnapshot:
        active = self._require_session(session_id)
        self._advance_from_wall_time(active)
        return self._snapshot_for(active)

    def build(
        self,
        *,
        session_id: str,
        item_id: str,
        config: Mapping[str, object],
        layout: Mapping[str, object],
    ) -> CommandAcceptedResponse:
        active = self._require_session(session_id)
        self._advance_from_wall_time(active)

        simulation_state_before = active.runtime_bundle.sandbox_runtime.get_simulation_state()
        if active.mode_id == "phase1_process_sandbox_v1":
            progression = simulation_state_before.progression_snapshot
            if progression is None:
                raise SandboxRequestError(
                    error_code="item_locked",
                    message="Sandbox progression state is unavailable.",
                )
            allowed_now = set(progression.available_item_ids)
        else:
            allowed_now = set(_TUTORIAL_BUILD_ITEM_IDS)

        if item_id not in allowed_now:
            if item_id in DEFERRED_PUBLIC_BUILD_ITEM_IDS:
                raise SandboxRequestError(
                    error_code="unknown_item",
                    message=f"Unsupported item for slice: {item_id!r}",
                )
            if item_id in self._sandbox_catalog and active.mode_id == "phase1_process_sandbox_v1":
                catalog_item = self._sandbox_catalog[item_id]
                if "phase1_process_sandbox_v1" in set(catalog_item.supported_start_ids):
                    raise SandboxRequestError(
                        error_code="item_locked",
                        message=f"Item {item_id!r} is locked in current progression state.",
                    )
            raise SandboxRequestError(
                error_code="unknown_item",
                message=f"Unsupported item for slice: {item_id!r}",
            )

        catalog_item = self._sandbox_catalog.get(item_id) or _fallback_catalog_item(item_id)
        effective_config = self._effective_config_for_item(item_id=item_id, config=config)
        install_config: Mapping[str, object] = effective_config
        economics_item_id = _equipment_item_id_for_economics(item_id)
        equipment_quote = active.runtime_bundle.cash_ledger_runtime.quote_equipment_purchase(
            economics_item_id,
            config=effective_config,
        )
        if not equipment_quote.affordable:
            raise SandboxRequestError(
                error_code="insufficient_cash",
                message="Insufficient cash balance for equipment purchase.",
            )

        if catalog_item.apply_kind == "add_process":
            process_id = self._require_process_id(config=config)
            anchor_xy = self._require_anchor_xy(layout=layout)
            self._install_unit(
                active=active,
                process_id=process_id,
                item=catalog_item,
            )
            active.board_layout.place_unit(process_id=process_id, anchor_xy=anchor_xy)
        elif catalog_item.apply_kind == "connect_configure_line":
            source, target = self._require_line_config(config=config)
            path_xy = self._require_path_xy(layout=layout)
            line_id, resolved_source, resolved_target = self._install_line(
                active=active, source=source, target=target, config=config, path_xy=path_xy
            )
            install_config = {
                **effective_config,
                "source": resolved_source,
                "target": resolved_target,
                "line_id": line_id,
            }
        elif catalog_item.apply_kind in {"attach_line_pump", "attach_line_valve"}:
            self._install_line_overlay(
                active=active,
                item=catalog_item,
                config=effective_config,
            )
        else:
            raise SandboxRequestError(
                error_code="unknown_item",
                message=f"Unsupported item apply kind for slice: {catalog_item.apply_kind!r}",
            )

        equipment_receipt = active.runtime_bundle.cash_ledger_runtime.record_equipment_purchase(
            economics_item_id,
            config=effective_config,
        )
        active.runtime_bundle.sandbox_runtime.install_catalog_item(
            item_id,
            config=install_config,
            equipment_receipt_id=equipment_receipt.receipt_id,
        )

        return CommandAcceptedResponse(
            accepted=True,
            message="Build command applied.",
            snapshot=self._snapshot_for(active),
        )

    def buy_feed(
        self,
        *,
        session_id: str,
        material_id: str,
        quantity_mol: float,
    ) -> CommandAcceptedResponse:
        active = self._require_session(session_id)
        self._advance_from_wall_time(active)
        feed_receipt = active.runtime_bundle.cash_ledger_runtime.record_feed_purchase(
            _feed_material_id_for_economics(material_id),
            quantity_mol=quantity_mol,
        )
        active.runtime_bundle.sandbox_runtime.load_feed_inventory(
            material_id,
            quantity_mol,
            procurement_receipt_id=feed_receipt.receipt_id,
        )
        return CommandAcceptedResponse(
            accepted=True,
            message="Feed purchase applied.",
            snapshot=self._snapshot_for(active),
        )

    def sell_product(
        self,
        *,
        session_id: str,
        product_id: str,
        quantity_mol: float,
    ) -> CommandAcceptedResponse:
        active = self._require_session(session_id)
        self._advance_from_wall_time(active)
        withdrawal = active.runtime_bundle.sandbox_runtime.withdraw_product_inventory(
            product_id,
            quantity_mol,
        )
        sale_product_id = _sale_product_id_for_economics(product_id)
        if sale_product_id != product_id:
            active.runtime_bundle.cash_ledger_runtime.register_product_withdrawal_handoff(
                withdrawal.withdrawal_id,
                product_id=sale_product_id,
                quantity_mol=float(quantity_mol),
            )
        active.runtime_bundle.cash_ledger_runtime.record_product_sale(withdrawal.withdrawal_id)
        return CommandAcceptedResponse(
            accepted=True,
            message="Product sale applied.",
            snapshot=self._snapshot_for(active),
        )

    def submit_research(
        self,
        *,
        session_id: str,
        research_id: str,
        submitted_quantities_by_product_id: Mapping[str, float],
    ) -> CommandAcceptedResponse:
        active = self._require_session(session_id)
        self._advance_from_wall_time(active)
        if research_id not in _RESEARCH_IDS:
            raise SandboxRequestError(
                error_code="unknown_research_unlock",
                message=f"Unknown research id: {research_id!r}",
            )
        active.runtime_bundle.sandbox_runtime.submit_research_unlock(
            research_id,
            submitted_quantities_by_product_id=submitted_quantities_by_product_id,
        )
        return CommandAcceptedResponse(
            accepted=True,
            message="Research unlock applied.",
            snapshot=self._snapshot_for(active),
        )

    def restart_session(self, *, session_id: str) -> CommandAcceptedResponse:
        active = self._require_session(session_id)
        mode_id = active.mode_id
        simulation_dt_s = active.simulation_dt_s
        preserved_session_id = active.session_id

        runtime_bundle = create_start_runtime_bundle(mode_id=mode_id)
        self._active_session = _ActiveSession(
            session_id=preserved_session_id,
            mode_id=mode_id,
            simulation_dt_s=simulation_dt_s,
            runtime_bundle=runtime_bundle,
            board_layout=BoardLayoutRuntime(),
            last_wall_time_s=_monotonic(),
            lag_backlog_s=0.0,
            published_signal_values_by_id={
                key: 0.0 for key in (active.published_signal_values_by_id or {}).keys()
            },
        )
        return CommandAcceptedResponse(
            accepted=True,
            message="Session restarted.",
            snapshot=self._snapshot_for(self._active_session),
        )

    def tick(self, *, session_id: str, wall_dt_s: float) -> CommandAcceptedResponse:
        active = self._require_session(session_id)
        dt_value = float(wall_dt_s)
        if not isfinite(dt_value) or dt_value < 0.0:
            raise SandboxRequestError(
                error_code="invalid_dt_s",
                message="wall_dt_s must be finite and >= 0.",
            )

        active.lag_backlog_s += dt_value
        while active.lag_backlog_s + 1e-12 >= active.simulation_dt_s:
            try:
                advance = active.runtime_bundle.sandbox_runtime.advance(active.simulation_dt_s)
                active.runtime_bundle.cash_ledger_runtime.record_operating_costs(
                    dt_s=active.simulation_dt_s,
                    published_signal_values_by_id=advance.published_signal_values_by_id,
                )
                active.published_signal_values_by_id = dict(advance.published_signal_values_by_id)
                active.lag_backlog_s -= active.simulation_dt_s
            except SandboxRequestError as error:
                if error.error_code in {"insufficient_feed_inventory", "insufficient_cash"}:
                    active.lag_backlog_s = 0.0
                    break
                raise

        return CommandAcceptedResponse(
            accepted=True,
            message="Tick applied.",
            snapshot=self._snapshot_for(active),
        )

    def _require_session(self, session_id: str) -> _ActiveSession:
        active = self._active_session
        if active is None or active.session_id != session_id:
            raise SandboxRequestError(
                error_code="unknown_session",
                message=f"Unknown session id: {session_id!r}",
            )
        return active

    def _advance_from_wall_time(self, active: _ActiveSession) -> None:
        """Advance the session's simulation from the wall clock, then update the baseline."""
        now = _monotonic()
        wall_dt_s = max(0.0, now - active.last_wall_time_s)
        active.last_wall_time_s = now

        active.lag_backlog_s += wall_dt_s
        while active.lag_backlog_s + 1e-12 >= active.simulation_dt_s:
            try:
                advance = active.runtime_bundle.sandbox_runtime.advance(active.simulation_dt_s)
                active.runtime_bundle.cash_ledger_runtime.record_operating_costs(
                    dt_s=active.simulation_dt_s,
                    published_signal_values_by_id=advance.published_signal_values_by_id,
                )
                active.published_signal_values_by_id = dict(advance.published_signal_values_by_id)
                active.lag_backlog_s -= active.simulation_dt_s
            except SandboxRequestError as error:
                if error.error_code in {"insufficient_feed_inventory", "insufficient_cash"}:
                    active.lag_backlog_s = 0.0
                    break
                raise

    def _snapshot_for(self, active: _ActiveSession) -> GameSnapshot:
        simulation_snapshot = active.runtime_bundle.sandbox_runtime.get_simulation_state()
        cash_ledger = active.runtime_bundle.cash_ledger_runtime.get_cash_ledger()
        return GameSnapshot(
            session_id=active.session_id,
            is_running=True,
            mode_id=active.mode_id,
            session_kind=simulation_snapshot.session_kind,
            active_start_id=simulation_snapshot.active_start_id,
            active_tutorial_id=simulation_snapshot.active_tutorial_id,
            elapsed_time_s=simulation_snapshot.elapsed_time_s,
            simulation_dt_s=active.simulation_dt_s,
            simulation_snapshot=simulation_snapshot,
            cash_ledger=cash_ledger,
            published_signal_values_by_id=dict(active.published_signal_values_by_id or {}),
            topology=dict(active.runtime_bundle.backend_session.get_topology()),
            board_layout=dict(active.board_layout.as_payload()),
            supported_build_item_ids=(
                simulation_snapshot.progression_snapshot.available_item_ids
                if (
                    active.mode_id == "phase1_process_sandbox_v1"
                    and simulation_snapshot.progression_snapshot is not None
                )
                else _TUTORIAL_BUILD_ITEM_IDS
            ),
            lag_backlog_s=max(0.0, active.lag_backlog_s),
        )

    def _derive_supported_build_item_ids_by_mode_id(self) -> dict[str, tuple[str, ...]]:
        supported: dict[str, tuple[str, ...]] = {}
        for mode_id in SUPPORTED_MODE_IDS:
            start_id = MODE_TO_START_ID[mode_id]
            start = self._start_catalog[start_id]
            supported[mode_id] = self._derive_supported_build_item_ids_for_start(start)
        return supported

    def _derive_supported_build_item_ids_for_start(
        self, start: PlayStartDefinition
    ) -> tuple[str, ...]:
        ordered_supported: list[str] = []
        for item_id in start.allowed_item_ids:
            item = self._sandbox_catalog.get(item_id)
            if item is None:
                continue
            if self._is_public_build_item(item):
                ordered_supported.append(item_id)
        return tuple(ordered_supported)

    def _is_public_build_item(self, item: SandboxCatalogItemDefinition) -> bool:
        return item.item_id not in DEFERRED_PUBLIC_BUILD_ITEM_IDS and (
            item.item_kind,
            item.apply_kind,
        ) in set(PUBLIC_BUILD_FAMILY_MATRIX)

    def _is_public_add_process_item(self, item: SandboxCatalogItemDefinition) -> bool:
        return self._is_public_build_item(item) and item.item_kind == "unit_blueprint"

    def _require_process_id(self, *, config: Mapping[str, object]) -> str:
        process_id = config.get("process_id")
        if not isinstance(process_id, str) or not process_id:
            raise SandboxRequestError(
                error_code="invalid_config",
                message="process_id must be a non-empty string.",
            )
        return process_id

    def _require_anchor_xy(self, *, layout: Mapping[str, object]) -> tuple[float, float]:
        anchor_xy = layout.get("anchor_xy")
        if not isinstance(anchor_xy, (tuple, list)) or len(anchor_xy) != 2:
            raise SandboxRequestError(
                error_code="invalid_layout",
                message="anchor_xy must be a 2D coordinate.",
            )
        x, y = anchor_xy
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            raise SandboxRequestError(
                error_code="invalid_layout",
                message="anchor_xy must contain numeric coordinates.",
            )
        return (float(x), float(y))

    def _require_line_config(self, *, config: Mapping[str, object]) -> tuple[str, str]:
        source = config.get("source")
        target = config.get("target")
        if not isinstance(source, str) or not isinstance(target, str):
            raise SandboxRequestError(
                error_code="invalid_config",
                message="build_process_line requires string source and target.",
            )
        return source, target

    def _require_path_xy(self, *, layout: Mapping[str, object]) -> tuple[tuple[float, float], ...]:
        path_xy = layout.get("path_xy")
        if not isinstance(path_xy, (tuple, list)) or len(path_xy) < 2:
            raise SandboxRequestError(
                error_code="invalid_layout",
                message="path_xy must contain at least 2 points.",
            )
        normalized: list[tuple[float, float]] = []
        for point in path_xy:
            if not isinstance(point, (tuple, list)) or len(point) != 2:
                raise SandboxRequestError(
                    error_code="invalid_layout",
                    message="each path_xy point must be a 2D coordinate.",
                )
            x, y = point
            if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
                raise SandboxRequestError(
                    error_code="invalid_layout",
                    message="path_xy points must contain numeric coordinates.",
                )
            normalized.append((float(x), float(y)))
        return tuple(normalized)

    def _effective_config_for_item(
        self, *, item_id: str, config: Mapping[str, object]
    ) -> Mapping[str, object]:
        catalog_item = self._sandbox_catalog.get(item_id) or _fallback_catalog_item(item_id)
        merged: dict[str, object] = dict(catalog_item.default_config)
        if self._is_public_add_process_item(catalog_item):
            merged.update(
                {
                    key: value
                    for key, value in config.items()
                    if key not in ADD_PROCESS_METADATA_KEYS
                }
            )
        else:
            merged.update(config)
        return merged

    def _install_unit(
        self,
        *,
        active: _ActiveSession,
        process_id: str,
        item: SandboxCatalogItemDefinition,
    ) -> None:
        try:
            meta = _resolve_unit_metadata(item)
        except _MetadataResolutionError as exc:
            raise SandboxRequestError(
                error_code="invalid_config",
                message=f"Failed to resolve unit metadata for {process_id!r}: {exc}",
            ) from exc
        network = active.runtime_bundle.backend_session.network
        try:
            compat_ports = _STAGEWISE_COMPAT_PORTS_BY_ITEM_ID.get(item.item_id)
            inlet_ports = compat_ports[0] if compat_ports is not None else meta.inlet_ports
            outlet_ports = compat_ports[1] if compat_ports is not None else meta.outlet_ports
            network.add_process(
                process_id,
                inlet_ports=inlet_ports,
                outlet_ports=outlet_ports,
            )
            active.runtime_bundle.backend_session.compile()
        except Exception as exc:
            raise SandboxRequestError(
                error_code="invalid_config",
                message=f"Failed to place process {process_id!r}: {exc}",
            ) from exc

    def _install_line(
        self,
        *,
        active: _ActiveSession,
        source: str,
        target: str,
        config: Mapping[str, object],
        path_xy: tuple[tuple[float, float], ...],
    ) -> tuple[str, str, str]:
        resolved_source = self._resolve_source_endpoint(active=active, node_id=source)
        resolved_target = self._resolve_target_endpoint(active=active, node_id=target)
        effective = self._effective_config_for_item(item_id="build_process_line", config=config)
        network = active.runtime_bundle.backend_session.network
        try:
            line_id = network.connect(resolved_source, resolved_target)
            radius = effective.get("radius_m")
            length = effective.get("length_m")
            if not isinstance(radius, (int, float)) or not isinstance(length, (int, float)):
                raise SandboxRequestError(
                    error_code="invalid_config",
                    message="build_process_line requires numeric radius_m and length_m.",
                )
            network.configure_line_geometry(
                line_id=line_id,
                radius_m=float(radius),
                length_m=float(length),
            )
            active.runtime_bundle.backend_session.compile()
        except SandboxRequestError:
            raise
        except Exception as exc:
            raise SandboxRequestError(
                error_code="invalid_config",
                message=f"Failed to build process line: {exc}",
            ) from exc

        active.board_layout.add_line(source=source, target=target, path_xy=path_xy, line_id=line_id)
        return line_id, resolved_source, resolved_target

    def _install_line_overlay(
        self,
        *,
        active: _ActiveSession,
        item: SandboxCatalogItemDefinition,
        config: Mapping[str, object],
    ) -> None:
        line_id = config.get("line_id")
        if not isinstance(line_id, str) or not line_id:
            raise SandboxRequestError(
                error_code="invalid_config",
                message=f"{item.item_id} requires non-empty string line_id.",
            )
        network = active.runtime_bundle.backend_session.network
        try:
            if item.apply_kind == "attach_line_pump":
                pump_id = config.get("pump_id")
                if not isinstance(pump_id, str) or not pump_id:
                    raise SandboxRequestError(
                        error_code="invalid_config",
                        message=f"{item.item_id} requires non-empty string pump_id.",
                    )
                network.attach_line_pump(
                    line_id=line_id,
                    pump_id=pump_id,
                    initial_pump_speed=config.get("initial_pump_speed", 80000.0),
                )
            elif item.apply_kind == "attach_line_valve":
                valve_id = config.get("valve_id")
                if not isinstance(valve_id, str) or not valve_id:
                    raise SandboxRequestError(
                        error_code="invalid_config",
                        message=f"{item.item_id} requires non-empty string valve_id.",
                    )
                network.attach_line_valve(
                    line_id=line_id,
                    valve_id=valve_id,
                    minimum_open_fraction=config.get("minimum_open_fraction", 0.0),
                    maximum_open_fraction=config.get("maximum_open_fraction", 1.0),
                    initial_open_fraction=config.get("initial_open_fraction", 1.0),
                )
            active.runtime_bundle.backend_session.compile()
        except SandboxRequestError:
            raise
        except Exception as exc:
            raise SandboxRequestError(
                error_code="invalid_config",
                message=f"Failed to attach line overlay: {exc}",
            ) from exc

    def _resolve_source_endpoint(self, *, active: _ActiveSession, node_id: str) -> str:
        state = active.runtime_bundle.sandbox_runtime.get_simulation_state()
        if node_id in set(state.feed_inventory_by_material_id):
            return node_id
        process_id, port_name = self._parse_process_endpoint(node_id=node_id)
        network = active.runtime_bundle.backend_session.network
        for spec in network.list_process_specs():
            if spec.process_id != process_id:
                continue
            if port_name not in set(spec.outlet_ports):
                raise SandboxRequestError(
                    error_code="invalid_config",
                    message=(
                        f"Source endpoint {node_id!r} must reference a declared outlet "
                        f"port on process {process_id!r}."
                    ),
                )
            return node_id
        raise SandboxRequestError(
            error_code="invalid_config",
            message=f"Unknown source process endpoint: {node_id!r}",
        )

    def _resolve_target_endpoint(self, *, active: _ActiveSession, node_id: str) -> str:
        state = active.runtime_bundle.sandbox_runtime.get_simulation_state()
        if node_id in set(state.product_inventory_by_product_id):
            return node_id
        process_id, port_name = self._parse_process_endpoint(node_id=node_id)
        network = active.runtime_bundle.backend_session.network
        for spec in network.list_process_specs():
            if spec.process_id != process_id:
                continue
            if port_name not in set(spec.inlet_ports):
                raise SandboxRequestError(
                    error_code="invalid_config",
                    message=(
                        f"Target endpoint {node_id!r} must reference a declared inlet "
                        f"port on process {process_id!r}."
                    ),
                )
            return node_id
        raise SandboxRequestError(
            error_code="invalid_config",
            message=f"Unknown target process endpoint: {node_id!r}",
        )

    def _parse_process_endpoint(self, *, node_id: str) -> tuple[str, str]:
        process_id, separator, port_name = node_id.partition(".")
        if separator != "." or not process_id or not port_name or "." in port_name:
            raise SandboxRequestError(
                error_code="invalid_config",
                message=(
                    "Non-boundary line endpoints must be explicit '<process_id>.<port_name>' "
                    f"strings; got {node_id!r}."
                ),
            )
        return process_id, port_name


_SERVICE_BY_SCOPE: dict[str, RealtimeGameService] = {}


def _scope_key() -> str:
    return os.environ.get("PYTEST_CURRENT_TEST", "global")


def _service() -> RealtimeGameService:
    scope = _scope_key()
    existing = _SERVICE_BY_SCOPE.get(scope)
    if existing is not None:
        return existing
    created = RealtimeGameService()
    _SERVICE_BY_SCOPE[scope] = created
    return created


def get_bootstrap() -> GameBootstrapResponse:
    return _service().get_bootstrap()


def create_session(*, mode_id: str, simulation_dt_s: float | None = None) -> SessionCreatedResponse:
    return _service().create_session(mode_id=mode_id, simulation_dt_s=simulation_dt_s)


def get_snapshot(*, session_id: str) -> GameSnapshot:
    return _service().get_snapshot(session_id=session_id)


def build(
    *,
    session_id: str,
    item_id: str,
    config: Mapping[str, object],
    layout: Mapping[str, object],
) -> CommandAcceptedResponse:
    return _service().build(session_id=session_id, item_id=item_id, config=config, layout=layout)


def buy_feed(
    *,
    session_id: str,
    material_id: str,
    quantity_mol: float,
) -> CommandAcceptedResponse:
    return _service().buy_feed(
        session_id=session_id, material_id=material_id, quantity_mol=quantity_mol
    )


def sell_product(
    *,
    session_id: str,
    product_id: str,
    quantity_mol: float,
) -> CommandAcceptedResponse:
    return _service().sell_product(
        session_id=session_id,
        product_id=product_id,
        quantity_mol=quantity_mol,
    )


def restart_session(*, session_id: str) -> CommandAcceptedResponse:
    return _service().restart_session(session_id=session_id)


def tick(*, session_id: str, wall_dt_s: float) -> CommandAcceptedResponse:
    return _service().tick(session_id=session_id, wall_dt_s=wall_dt_s)


def submit_research(
    *,
    session_id: str,
    research_id: str,
    submitted_quantities_by_product_id: Mapping[str, float],
) -> CommandAcceptedResponse:
    return _service().submit_research(
        session_id=session_id,
        research_id=research_id,
        submitted_quantities_by_product_id=submitted_quantities_by_product_id,
    )

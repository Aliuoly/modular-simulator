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
from modular_simulation.gameplay.contracts import SandboxCatalogItemDefinition, SandboxRequestError
from modular_simulation.gameplay.sandbox_catalog import build_sandbox_catalog
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

SUPPORTED_BUILD_ITEM_IDS: tuple[str, ...] = (
    "place_heater_cooler",
    "place_flash_drum",
    "build_process_line",
)


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
        self._active_session: _ActiveSession | None = None

    def get_bootstrap(self) -> GameBootstrapResponse:
        return GameBootstrapResponse(
            supported_mode_ids=SUPPORTED_MODE_IDS,
            supported_build_item_ids_by_mode_id={
                mode_id: SUPPORTED_BUILD_ITEM_IDS for mode_id in SUPPORTED_MODE_IDS
            },
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
            raise SandboxRequestError(
                error_code="unsupported_mode",
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
                "feed_a_draw_mol_s": 0.0,
                "feed_b_draw_mol_s": 0.0,
                "product_a_flow_mol_s": 0.0,
                "product_b_flow_mol_s": 0.0,
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
        if item_id not in set(SUPPORTED_BUILD_ITEM_IDS):
            raise SandboxRequestError(
                error_code="unknown_item",
                message=f"Unsupported item for slice: {item_id!r}",
            )

        if item_id in ("place_heater_cooler", "place_flash_drum"):
            process_id = self._require_process_id(config=config)
            anchor_xy = self._require_anchor_xy(layout=layout)
            self._install_unit(
                active=active,
                process_id=process_id,
                item=self._sandbox_catalog[item_id],
            )
            active.board_layout.place_unit(process_id=process_id, anchor_xy=anchor_xy)
        elif item_id == "build_process_line":
            source, target = self._require_line_config(config=config)
            path_xy = self._require_path_xy(layout=layout)
            self._install_line(
                active=active, source=source, target=target, config=config, path_xy=path_xy
            )

        # Orchestrate economics receipt internally.
        equipment_receipt = active.runtime_bundle.cash_ledger_runtime.record_equipment_purchase(
            item_id,
            config=self._effective_config_for_item(item_id=item_id, config=config),
        )
        active.runtime_bundle.sandbox_runtime.install_catalog_item(
            item_id,
            config=self._effective_config_for_item(item_id=item_id, config=config),
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
            material_id,
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
        active.runtime_bundle.cash_ledger_runtime.record_product_sale(withdrawal.withdrawal_id)
        return CommandAcceptedResponse(
            accepted=True,
            message="Product sale applied.",
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
            supported_build_item_ids=SUPPORTED_BUILD_ITEM_IDS,
            lag_backlog_s=max(0.0, active.lag_backlog_s),
        )

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
        catalog_item = self._sandbox_catalog[item_id]
        merged: dict[str, object] = dict(catalog_item.default_config)
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
            network.add_process(
                process_id,
                inlet_ports=meta.inlet_ports,
                outlet_ports=meta.outlet_ports,
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
    ) -> None:
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

    def _resolve_source_endpoint(self, *, active: _ActiveSession, node_id: str) -> str:
        state = active.runtime_bundle.sandbox_runtime.get_simulation_state()
        if node_id in set(state.feed_inventory_by_material_id):
            return node_id
        return f"{node_id}.out"

    def _resolve_target_endpoint(self, *, active: _ActiveSession, node_id: str) -> str:
        state = active.runtime_bundle.sandbox_runtime.get_simulation_state()
        if node_id in set(state.product_inventory_by_product_id):
            return node_id
        return f"{node_id}.in"


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

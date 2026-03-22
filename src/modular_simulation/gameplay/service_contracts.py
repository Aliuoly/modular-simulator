"""Service-layer transport contracts for the realtime gameplay slice."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from modular_simulation.gameplay.contracts import CashLedgerSnapshot, SimulationSessionSnapshot


@dataclass(frozen=True)
class GameBootstrapResponse:
    supported_mode_ids: tuple[str, ...]
    supported_build_item_ids_by_mode_id: Mapping[str, tuple[str, ...]]
    supported_simulation_dt_s_presets: tuple[float, ...]
    default_simulation_dt_s: float
    pause_supported: bool


@dataclass(frozen=True)
class GameSnapshot:
    session_id: str
    is_running: bool
    mode_id: str
    session_kind: str
    active_start_id: str
    active_tutorial_id: str | None
    elapsed_time_s: float
    simulation_dt_s: float
    simulation_snapshot: SimulationSessionSnapshot
    cash_ledger: CashLedgerSnapshot
    published_signal_values_by_id: Mapping[str, float]
    topology: Mapping[str, object]
    board_layout: Mapping[str, object]
    supported_build_item_ids: tuple[str, ...]
    lag_backlog_s: float


@dataclass(frozen=True)
class SessionCreatedResponse:
    session_id: str
    snapshot: GameSnapshot


@dataclass(frozen=True)
class CommandAcceptedResponse:
    accepted: bool
    message: str
    snapshot: GameSnapshot

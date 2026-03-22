from __future__ import annotations

import inspect
from importlib import import_module
from typing import Any, Mapping, cast
from unittest.mock import MagicMock, patch

import pytest

from modular_simulation.gameplay.contracts import CashLedgerSnapshot, SimulationSessionSnapshot


SUPPORTED_MODE_IDS = (
    "phase1_process_sandbox_v1",
    "heater_flash_guided_build_v1",
)
SUPPORTED_SIMULATION_DT_S_PRESETS = (1 / 60, 1 / 30, 1 / 20)
DEFAULT_SIMULATION_DT_S = 1 / 60

REQUIRED_SERVICE_METHODS = (
    "get_bootstrap",
    "create_session",
    "get_snapshot",
    "build",
    "buy_feed",
    "sell_product",
    "restart_session",
    "tick",
)


def _as_mapping(obj: object) -> Mapping[str, object] | None:
    return obj if isinstance(obj, Mapping) else None


def _field(obj: object, name: str) -> object:
    as_mapping = _as_mapping(obj)
    if as_mapping is not None:
        return as_mapping[name]
    return getattr(obj, name)


def _sandbox_error_type() -> type[Any]:
    contracts = import_module("modular_simulation.gameplay.contracts")
    return getattr(contracts, "SandboxRequestError")


def _has_required_methods(candidate: object) -> bool:
    return all(callable(getattr(candidate, method, None)) for method in REQUIRED_SERVICE_METHODS)


def _try_build(candidate: Any) -> Any:
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


def _service_api() -> Any:
    module = import_module("modular_simulation.gameplay.realtime_service")

    if _has_required_methods(module):
        return module

    for name in dir(module):
        if name.startswith("_"):
            continue
        candidate = getattr(module, name)
        if not callable(candidate) and _has_required_methods(candidate):
            return candidate
        if callable(candidate):
            built = _try_build(candidate)
            if built is not None and _has_required_methods(built):
                return built

    raise AssertionError(
        "modular_simulation.gameplay.realtime_service exposes no public API "
        "surface with the frozen realtime-service methods"
    )


def _create_session(
    service: Any,
    *,
    mode_id: str,
    simulation_dt_s: float | None = None,
) -> object:
    if simulation_dt_s is None:
        return service.create_session(mode_id=mode_id)
    return service.create_session(mode_id=mode_id, simulation_dt_s=simulation_dt_s)


def test_realtime_service_api_surface_is_frozen() -> None:
    service = _service_api()
    assert (
        tuple(name for name in REQUIRED_SERVICE_METHODS if callable(getattr(service, name, None)))
        == REQUIRED_SERVICE_METHODS
    )


def test_bootstrap_exposes_exact_slice_modes_and_simulation_dt_contract() -> None:
    service = _service_api()

    bootstrap = service.get_bootstrap()

    assert tuple(cast(Any, _field(bootstrap, "supported_mode_ids"))) == SUPPORTED_MODE_IDS
    assert tuple(
        cast(Any, _field(bootstrap, "supported_simulation_dt_s_presets"))
    ) == pytest.approx(SUPPORTED_SIMULATION_DT_S_PRESETS)
    assert _field(bootstrap, "default_simulation_dt_s") == pytest.approx(DEFAULT_SIMULATION_DT_S)
    assert _field(bootstrap, "pause_supported") is False


@pytest.mark.parametrize("simulation_dt_s", [None, 1 / 60, 1 / 30, 1 / 20])
def test_session_creation_accepts_only_advertised_simulation_dt_presets(
    simulation_dt_s: float | None,
) -> None:
    service = _service_api()

    created = _create_session(
        service,
        mode_id="phase1_process_sandbox_v1",
        simulation_dt_s=simulation_dt_s,
    )
    snapshot = _field(created, "snapshot")
    expected_dt = DEFAULT_SIMULATION_DT_S if simulation_dt_s is None else simulation_dt_s
    assert _field(snapshot, "simulation_dt_s") == pytest.approx(expected_dt)


def test_unsupported_simulation_dt_is_rejected_with_stable_error_code() -> None:
    service = _service_api()
    error_type = _sandbox_error_type()

    with pytest.raises(error_type) as exc_info:
        _create_session(
            service,
            mode_id="phase1_process_sandbox_v1",
            simulation_dt_s=0.1,
        )
    assert exc_info.value.error_code == "unsupported_simulation_dt_s"


def test_only_one_active_local_session_can_exist_at_once() -> None:
    service = _service_api()
    error_type = _sandbox_error_type()

    _create_session(service, mode_id="phase1_process_sandbox_v1")
    with pytest.raises(error_type) as exc_info:
        _create_session(service, mode_id="heater_flash_guided_build_v1")
    assert exc_info.value.error_code == "session_already_active"


def test_sessions_are_always_running_and_pause_resume_are_not_supported() -> None:
    service = _service_api()

    created = _create_session(service, mode_id="phase1_process_sandbox_v1")
    snapshot = _field(created, "snapshot")

    assert _field(snapshot, "is_running") is True
    assert not callable(getattr(service, "pause_session", None))
    assert not callable(getattr(service, "resume_session", None))


def test_restart_preserves_session_id_and_resets_slice_state() -> None:
    service = _service_api()

    created = _create_session(service, mode_id="phase1_process_sandbox_v1")
    session_id = _field(created, "session_id")
    initial_snapshot = _field(created, "snapshot")

    service.buy_feed(session_id=session_id, material_id="feed_a", quantity_mol=1.0)
    service.tick(session_id=session_id, wall_dt_s=0.5)

    restarted = service.restart_session(session_id=session_id)
    restarted_snapshot = _field(restarted, "snapshot")

    assert _field(restarted_snapshot, "session_id") == session_id
    assert _field(restarted_snapshot, "mode_id") == _field(initial_snapshot, "mode_id")
    assert _field(restarted_snapshot, "simulation_dt_s") == pytest.approx(
        _field(initial_snapshot, "simulation_dt_s")
    )

    restarted_sim = _field(restarted_snapshot, "simulation_snapshot")
    initial_sim = _field(initial_snapshot, "simulation_snapshot")
    assert isinstance(restarted_sim, SimulationSessionSnapshot)
    assert isinstance(initial_sim, SimulationSessionSnapshot)
    assert restarted_sim.elapsed_time_s == pytest.approx(initial_sim.elapsed_time_s)
    assert restarted_sim.feed_inventory_by_material_id == initial_sim.feed_inventory_by_material_id
    assert (
        restarted_sim.product_inventory_by_product_id == initial_sim.product_inventory_by_product_id
    )


def test_combined_snapshot_contains_required_authoritative_sections() -> None:
    service = _service_api()

    created = _create_session(service, mode_id="phase1_process_sandbox_v1")
    session_id = _field(created, "session_id")
    snapshot = service.get_snapshot(session_id=session_id)

    for required_field in (
        "session_id",
        "is_running",
        "mode_id",
        "session_kind",
        "active_start_id",
        "active_tutorial_id",
        "elapsed_time_s",
        "simulation_dt_s",
        "simulation_snapshot",
        "cash_ledger",
        "published_signal_values_by_id",
        "topology",
        "board_layout",
        "supported_build_item_ids",
        "lag_backlog_s",
    ):
        _field(snapshot, required_field)

    assert _field(snapshot, "mode_id") in SUPPORTED_MODE_IDS
    assert isinstance(_field(snapshot, "simulation_snapshot"), SimulationSessionSnapshot)
    assert isinstance(_field(snapshot, "cash_ledger"), CashLedgerSnapshot)
    assert isinstance(_field(snapshot, "published_signal_values_by_id"), Mapping)
    assert isinstance(_field(snapshot, "topology"), Mapping)
    assert isinstance(_field(snapshot, "board_layout"), Mapping)
    assert tuple(cast(Any, _field(snapshot, "supported_build_item_ids"))) == (
        "place_heater_cooler",
        "place_flash_drum",
        "build_process_line",
    )
    assert cast(float, _field(snapshot, "lag_backlog_s")) >= 0.0

    simulation_snapshot = cast(SimulationSessionSnapshot, _field(snapshot, "simulation_snapshot"))
    assert _field(snapshot, "session_kind") == simulation_snapshot.session_kind
    assert _field(snapshot, "active_start_id") == simulation_snapshot.active_start_id
    assert _field(snapshot, "active_tutorial_id") == simulation_snapshot.active_tutorial_id
    assert _field(snapshot, "elapsed_time_s") == pytest.approx(simulation_snapshot.elapsed_time_s)


def test_commands_do_not_require_or_accept_client_receipt_ids() -> None:
    service = _service_api()

    create_result = _create_session(service, mode_id="phase1_process_sandbox_v1")
    session_id = _field(create_result, "session_id")

    for method_name in ("build", "buy_feed", "sell_product"):
        signature = inspect.signature(getattr(service, method_name))
        assert all("receipt" not in parameter_name for parameter_name in signature.parameters)

    build_result = service.build(
        session_id=session_id,
        item_id="place_heater_cooler",
        config={"process_id": "heater_1"},
        layout={"anchor_xy": (0.0, 0.0)},
    )
    assert _field(build_result, "accepted") is True

    buy_result = service.buy_feed(session_id=session_id, material_id="feed_a", quantity_mol=1.0)
    assert _field(buy_result, "accepted") is True


def test_service_advances_from_wall_clock_without_explicit_tick_on_get_snapshot() -> None:
    """Service must own wall-clock progression: get_snapshot() advances without a prior tick().

    Uses deterministic time patching so no real-time waiting is needed.
    """
    realtime_module = import_module("modular_simulation.gameplay.realtime_service")
    service = realtime_module.RealtimeGameService()

    # Patch the time source at t=0 for session creation and feed purchase.
    with patch.object(realtime_module, "_monotonic", return_value=0.0):
        created = service.create_session(mode_id="phase1_process_sandbox_v1")
        session_id = _field(created, "session_id")
        # Buy feed at t=0 so the simulation can actually run (wall_dt=0 here, no advancement).
        service.buy_feed(session_id=session_id, material_id="feed_a", quantity_mol=100.0)

    # Now advance simulated wall clock by 1.0 second and call get_snapshot() (no tick()).
    with patch.object(realtime_module, "_monotonic", return_value=1.0):
        snapshot = service.get_snapshot(session_id=session_id)

    # Simulation must have advanced: elapsed_time_s > 0.0.
    elapsed = cast(float, _field(snapshot, "elapsed_time_s"))
    assert elapsed > 0.0, (
        "Service should self-advance from wall-clock time inside get_snapshot(); "
        "elapsed_time_s was still 0 after 1 simulated second."
    )


def test_service_advances_from_wall_clock_without_explicit_tick_on_buy_feed() -> None:
    """Service must advance the session from wall clock in buy_feed() without prior tick().

    A second buy_feed call at t=1.0 (after session created at t=0.0 with initial feed) should
    show elapsed simulation time has advanced due to the wall-clock delta.
    """
    realtime_module = import_module("modular_simulation.gameplay.realtime_service")
    service = realtime_module.RealtimeGameService()

    with patch.object(realtime_module, "_monotonic", return_value=0.0):
        created = service.create_session(mode_id="phase1_process_sandbox_v1")
        session_id = _field(created, "session_id")
        # Prime with feed so simulation can run during the subsequent wall-clock tick.
        service.buy_feed(session_id=session_id, material_id="feed_a", quantity_mol=100.0)

    # At t=1.0, buy more feed. The service must advance the simulation from the 1s wall delta
    # before recording the purchase.
    with patch.object(realtime_module, "_monotonic", return_value=1.0):
        result = service.buy_feed(session_id=session_id, material_id="feed_a", quantity_mol=1.0)

    elapsed = cast(float, _field(_field(result, "snapshot"), "elapsed_time_s"))
    assert elapsed > 0.0, (
        "Service should self-advance from wall-clock time inside buy_feed(); "
        "elapsed_time_s was still 0 after 1 simulated second."
    )


def test_restart_resets_wall_clock_baseline_so_subsequent_snapshot_is_not_inflated() -> None:
    """After restart, the session's internal clock baseline must reset.

    If we restart at t=10.0 and then call get_snapshot() at t=10.05,
    only ~0.05s worth of simulation must advance, not 10.05s.
    """
    realtime_module = import_module("modular_simulation.gameplay.realtime_service")
    service = realtime_module.RealtimeGameService()

    with patch.object(realtime_module, "_monotonic", return_value=0.0):
        created = service.create_session(mode_id="phase1_process_sandbox_v1")
    session_id = _field(created, "session_id")

    # Advance 5 seconds to get some history.
    with patch.object(realtime_module, "_monotonic", return_value=5.0):
        service.get_snapshot(session_id=session_id)

    # Restart at t=10.0.
    with patch.object(realtime_module, "_monotonic", return_value=10.0):
        service.restart_session(session_id=session_id)

    # 50ms after restart - should only advance ~0.05s.
    with patch.object(realtime_module, "_monotonic", return_value=10.05):
        snapshot = service.get_snapshot(session_id=session_id)

    elapsed = cast(float, _field(snapshot, "elapsed_time_s"))
    # Must be much less than the 10.05s total wall time since session start.
    # Allow up to 0.5s slack for rounding but not 10s.
    assert elapsed < 1.0, (
        f"After restart, elapsed_time_s ({elapsed:.3f}) should reflect only the time "
        "since restart (0.05s), not the full 10.05s since session creation."
    )

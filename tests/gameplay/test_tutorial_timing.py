from __future__ import annotations

import inspect
from importlib import import_module
from typing import Any
from unittest.mock import MagicMock

import pytest


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


def _session_api() -> Any:
    """Discover the sandbox session API surface without constraining implementation shape.

    Accepts any of:
    (a) The module itself has all required methods directly.
    (b) Any public non-callable exported object that directly has all required methods.
    (c) Any public callable in the module — tried with MagicMock stubs for all required
        parameters (supports no-arg, default-arg, and DI-injected factories/classes).
    """
    module = import_module("modular_simulation.gameplay.sandbox_session")
    required = (
        "start_tutorial",
        "install_catalog_item",
        "advance",
        "get_simulation_state",
    )

    # (a) Module-level methods
    if all(callable(getattr(module, name, None)) for name in required):
        return module

    for name in dir(module):
        if name.startswith("_"):
            continue
        candidate = getattr(module, name)

        # (b) Non-callable exported object with required methods
        if not callable(candidate) and all(callable(getattr(candidate, m, None)) for m in required):
            return candidate

        # (c) Any callable — attempt construction with mock stubs for required params
        if callable(candidate):
            built = _try_build(candidate)
            if built is not None and all(callable(getattr(built, m, None)) for m in required):
                return built

    raise AssertionError(
        "modular_simulation.gameplay.sandbox_session exposes no API with "
        "start_tutorial/install_catalog_item/advance/get_simulation_state"
    )


def _completion_tuple(snapshot: Any) -> tuple[bool, float | None]:
    statuses = tuple(snapshot.tutorial_goal_status_by_id.values())
    return (all(status.completed for status in statuses), snapshot.tutorial_completion_time_s)


def test_tutorial_goals_complete_only_from_frozen_goal_count_records() -> None:
    api = _session_api()
    snapshot = api.start_tutorial("heater_flash_guided_build_v1")
    assert _completion_tuple(snapshot) == (False, None)

    api.install_catalog_item("place_heater_cooler", config={})
    snapshot = api.get_simulation_state()
    assert snapshot.tutorial_goal_status_by_id["goal_place_heater"].completed is True
    assert snapshot.tutorial_goal_status_by_id["goal_place_flash"].completed is False
    assert snapshot.tutorial_goal_status_by_id["goal_wire_flowsheet"].completed is False
    assert snapshot.tutorial_completion_time_s is None

    api.install_catalog_item("place_flash_drum", config={})
    snapshot = api.get_simulation_state()
    assert snapshot.tutorial_goal_status_by_id["goal_place_flash"].completed is True
    assert snapshot.tutorial_goal_status_by_id["goal_wire_flowsheet"].completed is False
    assert snapshot.tutorial_completion_time_s is None

    # wire goal requires exactly 4 build_process_line installs — incomplete at 1, 2, 3
    for count in range(1, 4):
        api.install_catalog_item("build_process_line", config={})
        snapshot = api.get_simulation_state()
        assert snapshot.tutorial_goal_status_by_id["goal_wire_flowsheet"].completed is False, (
            f"goal_wire_flowsheet should not complete at count={count}"
        )
        assert snapshot.tutorial_completion_time_s is None

    # completing the 4th install must flip the goal and record completion time
    api.install_catalog_item("build_process_line", config={})
    snapshot = api.get_simulation_state()
    assert snapshot.tutorial_goal_status_by_id["goal_wire_flowsheet"].completed is True
    assert snapshot.tutorial_completion_time_s is not None


def test_tutorial_completion_time_is_elapsed_time_at_final_goal_and_freezes() -> None:
    api = _session_api()
    api.start_tutorial("heater_flash_guided_build_v1")

    api.install_catalog_item("place_heater_cooler", config={})
    api.advance(1.5)
    api.install_catalog_item("place_flash_drum", config={})
    api.advance(2.0)
    for _ in range(4):
        api.install_catalog_item("build_process_line", config={})

    completed_snapshot = api.get_simulation_state()
    completion_time = completed_snapshot.tutorial_completion_time_s
    assert completion_time == pytest.approx(completed_snapshot.elapsed_time_s)

    api.advance(3.0)
    post_completion_snapshot = api.get_simulation_state()
    assert post_completion_snapshot.elapsed_time_s > completion_time
    assert post_completion_snapshot.tutorial_completion_time_s == pytest.approx(completion_time)


def test_tutorial_completion_contract_contains_no_score_fields() -> None:
    api = _session_api()
    snapshot = api.start_tutorial("recycle_purge_tradeoff_v1")

    status = next(iter(snapshot.tutorial_goal_status_by_id.values()))
    assert not hasattr(snapshot, "score")
    assert not hasattr(snapshot, "points")
    assert not hasattr(snapshot, "total_score")
    assert not hasattr(status, "score")
    assert not hasattr(status, "points")

from __future__ import annotations

import inspect
from importlib import import_module
from typing import Any, Mapping, cast
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest


def _as_mapping(obj: object) -> Mapping[str, object] | None:
    return obj if isinstance(obj, Mapping) else None


def _field(obj: object, name: str) -> object:
    as_mapping = _as_mapping(obj)
    if as_mapping is not None:
        return as_mapping[name]
    return getattr(obj, name)


def _require_mapping(obj: object) -> Mapping[str, object]:
    as_mapping = _as_mapping(obj)
    assert as_mapping is not None
    return as_mapping


def _has_methods(candidate: object, methods: tuple[str, ...]) -> bool:
    return all(callable(getattr(candidate, method, None)) for method in methods)


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
    required_methods = ("create_session", "build", "get_snapshot")
    module = import_module("modular_simulation.gameplay.realtime_service")

    if _has_methods(module, required_methods):
        return module

    for name in dir(module):
        if name.startswith("_"):
            continue
        candidate = getattr(module, name)
        if not callable(candidate) and _has_methods(candidate, required_methods):
            return candidate
        if callable(candidate):
            built = _try_build(candidate)
            if built is not None and _has_methods(built, required_methods):
                return built

    raise AssertionError(
        "modular_simulation.gameplay.realtime_service exposes no public API "
        "surface with the required board-layout service methods"
    )


def test_board_layout_tracks_unit_anchor_positions_for_gas_starter_units() -> None:
    service = _service_api()

    created = service.create_session(mode_id="phase1_process_sandbox_v1")
    session_id = _field(created, "session_id")

    service.build(
        session_id=session_id,
        item_id="place_inlet_gas_separator",
        config={"process_id": "separator_1"},
        layout={"anchor_xy": (2.0, 3.0)},
    )
    service.build(
        session_id=session_id,
        item_id="place_teg_contactor",
        config={"process_id": "contactor_1"},
        layout={"anchor_xy": (6.0, 7.5)},
    )

    snapshot = service.get_snapshot(session_id=session_id)
    board_layout = _field(snapshot, "board_layout")

    unit_entities = _field(board_layout, "unit_entities_by_process_id")
    assert _field(_field(unit_entities, "separator_1"), "anchor_xy") == (2.0, 3.0)
    assert _field(_field(unit_entities, "contactor_1"), "anchor_xy") == (6.0, 7.5)


def test_board_layout_tracks_line_anchor_links_and_render_path_metadata() -> None:
    service = _service_api()

    created = service.create_session(mode_id="phase1_process_sandbox_v1")
    session_id = _field(created, "session_id")

    build_result = service.build(
        session_id=session_id,
        item_id="build_process_line",
        config={"source": "sweet_wet_gas", "target": "separator_gas"},
        layout={"path_xy": ((0.0, 0.0), (1.0, 0.5), (2.0, 1.0))},
    )

    snapshot = _field(build_result, "snapshot")
    board_layout = _field(snapshot, "board_layout")
    line_entities = _field(board_layout, "line_entities_by_line_id")
    line_entity = next(iter(_require_mapping(line_entities).values()))

    assert _field(line_entity, "source") == "sweet_wet_gas"
    assert _field(line_entity, "target") == "separator_gas"
    assert tuple(cast(Any, _field(line_entity, "path_xy"))) == (
        (0.0, 0.0),
        (1.0, 0.5),
        (2.0, 1.0),
    )


def test_board_layout_payload_is_separate_from_topology_payload() -> None:
    service = _service_api()

    created = service.create_session(mode_id="phase1_process_sandbox_v1")
    session_id = _field(created, "session_id")

    snapshot = service.get_snapshot(session_id=session_id)
    board_layout = _field(snapshot, "board_layout")
    topology = _field(snapshot, "topology")

    assert board_layout is not topology
    assert "board_layout" not in _require_mapping(topology)


def test_rejected_build_does_not_mutate_board_layout_or_topology() -> None:
    service_module = import_module("modular_simulation.gameplay.realtime_service")
    economics_module = import_module("modular_simulation.gameplay.economics")
    error_type = getattr(service_module, "SandboxRequestError")

    with patch.object(economics_module, "_DEFAULT_SANDBOX_STARTING_CASH", 10.0):
        service = _service_api()
        created = service.create_session(mode_id="phase1_process_sandbox_v1")
        session_id = _field(created, "session_id")

        before = service.get_snapshot(session_id=session_id)
        with pytest.raises(error_type) as exc_info:
            service.build(
                session_id=session_id,
                item_id="place_inlet_gas_separator",
                config={"process_id": "separator_1"},
                layout={"anchor_xy": (0.0, 0.0)},
            )
        assert exc_info.value.error_code == "insufficient_cash"

        after = service.get_snapshot(session_id=session_id)
        assert _field(before, "board_layout") == _field(after, "board_layout")
        assert _field(before, "topology") == _field(after, "topology")

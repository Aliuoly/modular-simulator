from __future__ import annotations

import inspect
from importlib import import_module
from typing import Any, Mapping, cast
from unittest.mock import MagicMock


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


def test_board_layout_tracks_unit_anchor_positions_for_heater_and_flash() -> None:
    service = _service_api()

    created = service.create_session(mode_id="phase1_process_sandbox_v1")
    session_id = _field(created, "session_id")

    service.build(
        session_id=session_id,
        item_id="place_heater_cooler",
        config={"process_id": "heater_1"},
        layout={"anchor_xy": (2.0, 3.0)},
    )
    service.build(
        session_id=session_id,
        item_id="place_flash_drum",
        config={"process_id": "flash_1"},
        layout={"anchor_xy": (6.0, 7.5)},
    )

    snapshot = service.get_snapshot(session_id=session_id)
    board_layout = _field(snapshot, "board_layout")

    unit_entities = _field(board_layout, "unit_entities_by_process_id")
    assert _field(_field(unit_entities, "heater_1"), "anchor_xy") == (2.0, 3.0)
    assert _field(_field(unit_entities, "flash_1"), "anchor_xy") == (6.0, 7.5)


def test_board_layout_tracks_line_anchor_links_and_render_path_metadata() -> None:
    service = _service_api()

    created = service.create_session(mode_id="phase1_process_sandbox_v1")
    session_id = _field(created, "session_id")

    build_result = service.build(
        session_id=session_id,
        item_id="build_process_line",
        config={"source": "feed_a", "target": "product_a"},
        layout={"path_xy": ((0.0, 0.0), (1.0, 0.5), (2.0, 1.0))},
    )

    snapshot = _field(build_result, "snapshot")
    board_layout = _field(snapshot, "board_layout")
    line_entities = _field(board_layout, "line_entities_by_line_id")
    line_entity = next(iter(_require_mapping(line_entities).values()))

    assert _field(line_entity, "source") == "feed_a"
    assert _field(line_entity, "target") == "product_a"
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

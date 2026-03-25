from __future__ import annotations

from importlib import import_module
from time import sleep, time
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


SUPPORTED_MODE_IDS = [
    "phase1_process_sandbox_v1",
    "heater_flash_guided_build_v1",
]

SUPPORTED_BUILD_ITEM_IDS_BY_MODE_ID = {
    "phase1_process_sandbox_v1": [
        "place_heater_cooler",
        "place_flash_drum",
        "place_heat_exchanger",
        "build_process_line",
    ],
    "heater_flash_guided_build_v1": [
        "place_heater_cooler",
        "place_flash_drum",
        "build_process_line",
    ],
}

SUPPORTED_SIMULATION_DT_S_PRESETS = [1.0 / 60.0, 1.0 / 30.0, 1.0 / 20.0]
DEFAULT_SIMULATION_DT_S = 1.0 / 60.0


def _client() -> TestClient:
    try:
        module = import_module("modular_simulation.app.game_api")
    except ModuleNotFoundError:
        pytest.fail(
            "Expected module modular_simulation.app.game_api to exist for API contract tests",
            pytrace=False,
        )

    app: Any | None = getattr(module, "app", None)
    if app is None:
        factory = getattr(module, "create_app", None)
        if callable(factory):
            app = factory()

    if app is None:
        pytest.fail(
            "Expected modular_simulation.app.game_api to expose FastAPI app or create_app()",
            pytrace=False,
        )
    return TestClient(app)


def _assert_stable_error_payload(payload: dict[str, Any]) -> None:
    assert set(payload) == {"error_code", "message"}
    assert isinstance(payload["error_code"], str)
    assert payload["error_code"]
    assert isinstance(payload["message"], str)
    assert payload["message"]


def _wait_for_product_inventory(
    client: TestClient,
    session_id: str,
    *,
    minimum_product_a_mol: float,
    timeout_s: float = 2.0,
) -> dict[str, Any]:
    deadline = time() + timeout_s
    latest: dict[str, Any] = {}
    while time() < deadline:
        snapshot = client.get(f"/game/sessions/{session_id}/snapshot")
        assert snapshot.status_code == 200
        latest = snapshot.json()
        product_inventory = latest["simulation_snapshot"]["product_inventory_by_product_id"]
        if product_inventory.get("product_a", 0.0) >= minimum_product_a_mol:
            return latest
        sleep(0.05)
    return latest


def test_bootstrap_contract_is_frozen() -> None:
    client = _client()

    response = client.get("/game/bootstrap")
    assert response.status_code == 200
    payload = response.json()

    assert set(payload) == {
        "supported_mode_ids",
        "supported_build_item_ids_by_mode_id",
        "supported_simulation_dt_s_presets",
        "default_simulation_dt_s",
        "pause_supported",
    }
    assert payload["supported_mode_ids"] == SUPPORTED_MODE_IDS
    assert payload["supported_build_item_ids_by_mode_id"] == SUPPORTED_BUILD_ITEM_IDS_BY_MODE_ID
    assert payload["supported_simulation_dt_s_presets"] == pytest.approx(
        SUPPORTED_SIMULATION_DT_S_PRESETS
    )
    assert payload["default_simulation_dt_s"] == pytest.approx(DEFAULT_SIMULATION_DT_S)
    assert payload["default_simulation_dt_s"] in payload["supported_simulation_dt_s_presets"]
    assert payload["pause_supported"] is False


def test_create_session_returns_201_with_exact_payload_shape() -> None:
    client = _client()

    response = client.post("/game/sessions", json={"mode_id": "phase1_process_sandbox_v1"})
    assert response.status_code == 201

    payload = response.json()
    assert set(payload) == {"session_id", "snapshot"}
    assert isinstance(payload["session_id"], str)
    assert payload["session_id"]
    assert isinstance(payload["snapshot"], dict)
    assert set(payload["snapshot"]) == {
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
    }
    assert payload["snapshot"]["mode_id"] == "phase1_process_sandbox_v1"
    assert payload["snapshot"]["simulation_dt_s"] == pytest.approx(DEFAULT_SIMULATION_DT_S)


def test_successful_command_routes_return_200_with_exact_payload_shape() -> None:
    client = _client()

    create = client.post("/game/sessions", json={"mode_id": "phase1_process_sandbox_v1"})
    assert create.status_code == 201
    session_id = create.json()["session_id"]

    command_responses = [
        client.post(
            f"/game/sessions/{session_id}/commands/build",
            json={
                "item_id": "place_heater_cooler",
                "config": {"process_id": "heater_1"},
                "layout": {"anchor_xy": [0.0, 0.0]},
            },
        ),
        client.post(
            f"/game/sessions/{session_id}/commands/buy-feed",
            json={"material_id": "feed_a", "quantity_mol": 2.0},
        ),
    ]

    _wait_for_product_inventory(client, session_id, minimum_product_a_mol=0.01)

    command_responses.extend(
        (
            client.post(
                f"/game/sessions/{session_id}/commands/sell-product",
                json={"product_id": "product_a", "quantity_mol": 0.01},
            ),
            client.post(f"/game/sessions/{session_id}/restart"),
        )
    )

    for response in command_responses:
        assert response.status_code == 200
        payload = response.json()
        assert set(payload) == {"accepted", "message", "snapshot"}
        assert isinstance(payload["accepted"], bool)
        assert isinstance(payload["message"], str)
        assert payload["message"]
        assert isinstance(payload["snapshot"], dict)


def test_build_route_accepts_widened_add_process_items_in_sandbox() -> None:
    client = _client()

    create = client.post("/game/sessions", json={"mode_id": "phase1_process_sandbox_v1"})
    assert create.status_code == 201
    session_id = create.json()["session_id"]

    build_heat_exchanger = client.post(
        f"/game/sessions/{session_id}/commands/build",
        json={
            "item_id": "place_heat_exchanger",
            "config": {"process_id": "heat_exchanger_1"},
            "layout": {"anchor_xy": [1.0, 0.0]},
        },
    )
    assert build_heat_exchanger.status_code == 200
    assert set(build_heat_exchanger.json()) == {"accepted", "message", "snapshot"}


def test_build_route_accepts_explicit_named_endpoints_for_public_line_contract() -> None:
    client = _client()

    create = client.post("/game/sessions", json={"mode_id": "phase1_process_sandbox_v1"})
    assert create.status_code == 201
    session_id = create.json()["session_id"]

    for item_id, process_id, anchor_xy in (
        ("place_heater_cooler", "heater_1", [0.0, 0.0]),
        ("place_flash_drum", "flash_1", [4.0, 0.0]),
        ("place_heat_exchanger", "heat_exchanger_1", [2.0, 2.0]),
    ):
        placed = client.post(
            f"/game/sessions/{session_id}/commands/build",
            json={
                "item_id": item_id,
                "config": {"process_id": process_id},
                "layout": {"anchor_xy": anchor_xy},
            },
        )
        assert placed.status_code == 200

    for source, target in (
        ("feed_a", "heater_1.inlet"),
        ("heater_1.outlet", "product_a"),
        ("feed_a", "flash_1.inlet"),
        ("flash_1.vapor_outlet", "product_a"),
        ("flash_1.liquid_outlet", "product_b"),
        ("feed_a", "heat_exchanger_1.hot_inlet"),
        ("feed_b", "heat_exchanger_1.cold_inlet"),
        ("heat_exchanger_1.hot_outlet", "product_a"),
        ("heat_exchanger_1.cold_outlet", "product_b"),
    ):
        built = client.post(
            f"/game/sessions/{session_id}/commands/build",
            json={
                "item_id": "build_process_line",
                "config": {"source": source, "target": target},
                "layout": {"path_xy": [[0.0, 0.0], [1.0, 0.0]]},
            },
        )
        assert built.status_code == 200


@pytest.mark.parametrize(
    ("source", "target"),
    [
        ("feed_a", "heater_1"),
        ("feed_a", "flash_1"),
        ("feed_a", "heat_exchanger_1"),
        ("heater_1", "product_a"),
        ("flash_1", "product_a"),
        ("heat_exchanger_1", "product_a"),
        ("heater_1..outlet", "product_a"),
        ("ghost_1.outlet", "product_a"),
        ("feed_a", "ghost_product"),
        ("heater_1.ghost_port", "product_a"),
        ("heater_1.inlet", "product_a"),
        ("feed_a", "heater_1.outlet"),
    ],
)
def test_build_route_rejects_invalid_line_endpoints_with_stable_invalid_config_json(
    source: str, target: str
) -> None:
    client = _client()

    create = client.post("/game/sessions", json={"mode_id": "phase1_process_sandbox_v1"})
    assert create.status_code == 201
    session_id = create.json()["session_id"]

    place_heater = client.post(
        f"/game/sessions/{session_id}/commands/build",
        json={
            "item_id": "place_heater_cooler",
            "config": {"process_id": "heater_1"},
            "layout": {"anchor_xy": [0.0, 0.0]},
        },
    )
    assert place_heater.status_code == 200

    rejected = client.post(
        f"/game/sessions/{session_id}/commands/build",
        json={
            "item_id": "build_process_line",
            "config": {"source": source, "target": target},
            "layout": {"path_xy": [[0.0, 0.0], [1.0, 0.0]]},
        },
    )

    assert rejected.status_code == 400
    payload = rejected.json()
    _assert_stable_error_payload(payload)
    assert payload["error_code"] == "invalid_config"


@pytest.mark.parametrize(
    "deferred_item_id",
    [
        "place_component_separator",
        "install_sampled_delayed_sensor",
        "install_pid_controller",
        "install_line_pump",
        "install_line_valve",
        "install_line_heat_actuator",
        "place_merge_junction_2x1",
        "place_split_junction_1x2",
    ],
)
def test_deferred_build_items_stay_unknown_item_in_api_for_current_slice(
    deferred_item_id: str,
) -> None:
    client = _client()

    create = client.post("/game/sessions", json={"mode_id": "phase1_process_sandbox_v1"})
    assert create.status_code == 201
    session_id = create.json()["session_id"]

    rejected = client.post(
        f"/game/sessions/{session_id}/commands/build",
        json={"item_id": deferred_item_id, "config": {}, "layout": {}},
    )
    assert rejected.status_code == 400
    payload = rejected.json()
    _assert_stable_error_payload(payload)
    assert payload["error_code"] == "unknown_item"


def test_rejections_use_stable_error_json_and_frozen_status_semantics() -> None:
    client = _client()

    bad_mode = client.post("/game/sessions", json={"mode_id": "unknown_mode"})
    assert bad_mode.status_code == 400
    _assert_stable_error_payload(bad_mode.json())
    assert bad_mode.json()["error_code"] == "unknown_mode"

    bad_dt = client.post(
        "/game/sessions",
        json={"mode_id": "phase1_process_sandbox_v1", "simulation_dt_s": 0.1},
    )
    assert bad_dt.status_code == 400
    _assert_stable_error_payload(bad_dt.json())
    assert bad_dt.json()["error_code"] == "unsupported_simulation_dt_s"

    missing_session = client.get("/game/sessions/does-not-exist/snapshot")
    assert missing_session.status_code == 404
    _assert_stable_error_payload(missing_session.json())
    assert missing_session.json()["error_code"] == "unknown_session"

    first = client.post("/game/sessions", json={"mode_id": "phase1_process_sandbox_v1"})
    assert first.status_code == 201
    conflict = client.post(
        "/game/sessions",
        json={"mode_id": "heater_flash_guided_build_v1"},
    )
    assert conflict.status_code == 409
    _assert_stable_error_payload(conflict.json())
    assert conflict.json()["error_code"] == "session_already_active"


def test_pause_and_resume_routes_do_not_exist() -> None:
    client = _client()

    create = client.post("/game/sessions", json={"mode_id": "phase1_process_sandbox_v1"})
    assert create.status_code == 201
    session_id = create.json()["session_id"]

    pause = client.post(f"/game/sessions/{session_id}/pause")
    resume = client.post(f"/game/sessions/{session_id}/resume")

    assert pause.status_code == 404
    assert resume.status_code == 404


def test_purge_tank_route_does_not_exist() -> None:
    """Freeze guard: purge-by-tank is internal only in this pack.

    The purge primitive must not be exposed as a public HTTP command in 4fm.
    This guard will fail if anyone accidentally adds a /commands/purge-tank route.
    """
    client = _client()

    create = client.post("/game/sessions", json={"mode_id": "phase1_process_sandbox_v1"})
    assert create.status_code == 201
    session_id = create.json()["session_id"]

    purge_tank = client.post(
        f"/game/sessions/{session_id}/commands/purge-tank",
        json={"tank_id": "some_tank"},
    )

    assert purge_tank.status_code == 404


def test_buy_feed_and_sell_product_payloads_remain_without_tank_id() -> None:
    """Freeze guard: buy-feed and sell-product keep their current payload shapes.

    The current routes accept {material_id, quantity_mol} and {product_id, quantity_mol}
    respectively, with no tank_id field.  This test pins those exact shapes so any attempt
    to add tank_id to these routes triggers a deliberate review.
    """
    client = _client()

    create = client.post("/game/sessions", json={"mode_id": "phase1_process_sandbox_v1"})
    assert create.status_code == 201
    session_id = create.json()["session_id"]

    # buy-feed: exact payload shape without tank_id succeeds
    buy = client.post(
        f"/game/sessions/{session_id}/commands/buy-feed",
        json={"material_id": "feed_a", "quantity_mol": 1.0},
    )
    assert buy.status_code == 200
    buy_payload = buy.json()
    assert set(buy_payload) == {"accepted", "message", "snapshot"}

    _wait_for_product_inventory(client, session_id, minimum_product_a_mol=0.01)

    # sell-product: exact payload shape without tank_id succeeds
    sell = client.post(
        f"/game/sessions/{session_id}/commands/sell-product",
        json={"product_id": "product_a", "quantity_mol": 0.01},
    )
    assert sell.status_code == 200
    sell_payload = sell.json()
    assert set(sell_payload) == {"accepted", "message", "snapshot"}


def test_build_route_returns_400_with_stable_invalid_config_on_metadata_resolution_failure() -> (
    None
):
    """API regression: build route returns HTTP 400 with stable {error_code, message} when
    the gameplay build path raises a metadata-resolution failure translated to invalid_config.

    This pins the contract that _install_unit()'s SandboxRequestError(error_code="invalid_config")
    surfaces as HTTP 400 with the frozen error shape, not as a 500 or unhandled exception.
    """
    module = import_module("modular_simulation.app.game_api")
    from modular_simulation.gameplay.contracts import SandboxRequestError

    def _fake_build_raises_invalid_config(**kwargs: Any) -> dict[str, Any]:
        raise SandboxRequestError(
            error_code="invalid_config",
            message="Failed to resolve unit metadata for 'heater_1': No module named 'missing.module'",
        )

    with patch.object(module, "build", side_effect=_fake_build_raises_invalid_config):
        client = TestClient(module.create_app())

        response = client.post(
            "/game/sessions/session-test/commands/build",
            json={
                "item_id": "place_heater_cooler",
                "config": {"process_id": "heater_1"},
                "layout": {"anchor_xy": [0.0, 0.0]},
            },
        )

    assert response.status_code == 400
    payload = response.json()
    _assert_stable_error_payload(payload)
    assert payload["error_code"] == "invalid_config"


def test_buy_feed_and_sell_product_routes_do_not_forward_tank_id() -> None:
    """Freeze guard: tank_id is not part of the current public buy/sell command contract.

    The routes may receive extra JSON keys because they currently accept generic
    Mapping payloads, but in this pack they must continue forwarding only the
    frozen arguments to gameplay: session_id + material/product id + quantity_mol.
    """
    module = import_module("modular_simulation.app.game_api")
    buy_calls: list[dict[str, Any]] = []
    sell_calls: list[dict[str, Any]] = []

    def _fake_buy_feed(**kwargs: Any) -> dict[str, Any]:
        buy_calls.append(kwargs)
        return {"accepted": True, "message": "ok", "snapshot": {}}

    def _fake_sell_product(**kwargs: Any) -> dict[str, Any]:
        sell_calls.append(kwargs)
        return {"accepted": True, "message": "ok", "snapshot": {}}

    with (
        patch.object(module, "buy_feed", side_effect=_fake_buy_feed),
        patch.object(module, "sell_product", side_effect=_fake_sell_product),
    ):
        client = TestClient(module.create_app())

        buy = client.post(
            "/game/sessions/session-test/commands/buy-feed",
            json={"material_id": "feed_a", "quantity_mol": 1.0, "tank_id": "tank_1"},
        )
        sell = client.post(
            "/game/sessions/session-test/commands/sell-product",
            json={"product_id": "product_a", "quantity_mol": 0.5, "tank_id": "tank_2"},
        )

    assert buy.status_code == 200
    assert sell.status_code == 200
    assert buy_calls == [
        {"session_id": "session-test", "material_id": "feed_a", "quantity_mol": 1.0}
    ]
    assert sell_calls == [
        {"session_id": "session-test", "product_id": "product_a", "quantity_mol": 0.5}
    ]

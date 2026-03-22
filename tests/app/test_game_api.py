from __future__ import annotations

from importlib import import_module
from time import sleep, time
from typing import Any

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

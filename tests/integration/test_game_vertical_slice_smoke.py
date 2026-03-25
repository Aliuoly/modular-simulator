from __future__ import annotations

from importlib import import_module
from time import sleep, time
from typing import Any

import pytest
from fastapi.testclient import TestClient


def _client() -> TestClient:
    try:
        module = import_module("modular_simulation.app.game_api")
    except ModuleNotFoundError:
        pytest.fail(
            "Expected module modular_simulation.app.game_api to exist for vertical-slice smoke tests",
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


def test_sandbox_flow_smoke() -> None:
    client = _client()

    created = client.post("/game/sessions", json={"mode_id": "phase1_process_sandbox_v1"})
    assert created.status_code == 201
    body = created.json()
    assert set(body) == {"session_id", "snapshot"}
    session_id = body["session_id"]

    build_heater = client.post(
        f"/game/sessions/{session_id}/commands/build",
        json={
            "item_id": "place_heater_cooler",
            "config": {"process_id": "heater_1"},
            "layout": {"anchor_xy": [0.0, 0.0]},
        },
    )
    assert build_heater.status_code == 200
    assert set(build_heater.json()) == {"accepted", "message", "snapshot"}

    build_flash = client.post(
        f"/game/sessions/{session_id}/commands/build",
        json={
            "item_id": "place_flash_drum",
            "config": {"process_id": "flash_1"},
            "layout": {"anchor_xy": [4.0, 0.0]},
        },
    )
    assert build_flash.status_code == 200

    build_heat_exchanger = client.post(
        f"/game/sessions/{session_id}/commands/build",
        json={
            "item_id": "place_heat_exchanger",
            "config": {"process_id": "heat_exchanger_1"},
            "layout": {"anchor_xy": [2.0, 2.0]},
        },
    )
    assert build_heat_exchanger.status_code == 200
    assert set(build_heat_exchanger.json()) == {"accepted", "message", "snapshot"}

    line_commands = (
        {"source": "feed_a", "target": "heater_1.inlet"},
        {"source": "heater_1.outlet", "target": "flash_1.inlet"},
        {"source": "flash_1.vapor_outlet", "target": "heat_exchanger_1.hot_inlet"},
        {"source": "feed_b", "target": "heat_exchanger_1.cold_inlet"},
        {"source": "heat_exchanger_1.hot_outlet", "target": "product_a"},
        {"source": "heat_exchanger_1.cold_outlet", "target": "product_b"},
    )
    for line_config in line_commands:
        build_line = client.post(
            f"/game/sessions/{session_id}/commands/build",
            json={
                "item_id": "build_process_line",
                "config": line_config,
                "layout": {"path_xy": [[0.0, 0.0], [2.0, 0.0], [4.0, 0.0]]},
            },
        )
        assert build_line.status_code == 200

    buy_feed = client.post(
        f"/game/sessions/{session_id}/commands/buy-feed",
        json={"material_id": "feed_a", "quantity_mol": 2.0},
    )
    assert buy_feed.status_code == 200
    assert set(buy_feed.json()) == {"accepted", "message", "snapshot"}

    snapshot = _wait_for_product_inventory(client, session_id, minimum_product_a_mol=0.1)
    assert (
        snapshot["simulation_snapshot"]["product_inventory_by_product_id"].get("product_a", 0.0)
        > 0.0
    )

    sell_product = client.post(
        f"/game/sessions/{session_id}/commands/sell-product",
        json={"product_id": "product_a", "quantity_mol": 0.1},
    )
    assert sell_product.status_code == 200
    assert set(sell_product.json()) == {"accepted", "message", "snapshot"}

    post_build_snapshot = client.get(f"/game/sessions/{session_id}/snapshot")
    assert post_build_snapshot.status_code == 200
    payload = post_build_snapshot.json()
    assert set(payload) == {
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


def test_tutorial_flow_smoke() -> None:
    client = _client()

    created = client.post("/game/sessions", json={"mode_id": "heater_flash_guided_build_v1"})
    assert created.status_code == 201
    body = created.json()
    assert set(body) == {"session_id", "snapshot"}
    session_id = body["session_id"]

    build_heater = client.post(
        f"/game/sessions/{session_id}/commands/build",
        json={
            "item_id": "place_heater_cooler",
            "config": {"process_id": "heater_1"},
            "layout": {"anchor_xy": [0.0, 0.0]},
        },
    )
    assert build_heater.status_code == 200

    build_flash = client.post(
        f"/game/sessions/{session_id}/commands/build",
        json={
            "item_id": "place_flash_drum",
            "config": {"process_id": "flash_1"},
            "layout": {"anchor_xy": [4.0, 0.0]},
        },
    )
    assert build_flash.status_code == 200

    build_line_1 = client.post(
        f"/game/sessions/{session_id}/commands/build",
        json={
            "item_id": "build_process_line",
            "config": {"source": "feed", "target": "heater_1.inlet"},
            "layout": {"path_xy": [[0.0, 0.0], [1.0, 0.0]]},
        },
    )
    assert build_line_1.status_code == 200

    build_line_2 = client.post(
        f"/game/sessions/{session_id}/commands/build",
        json={
            "item_id": "build_process_line",
            "config": {"source": "heater_1.outlet", "target": "flash_1.inlet"},
            "layout": {"path_xy": [[1.0, 0.0], [2.0, 0.0]]},
        },
    )
    assert build_line_2.status_code == 200

    build_line_3 = client.post(
        f"/game/sessions/{session_id}/commands/build",
        json={
            "item_id": "build_process_line",
            "config": {"source": "flash_1.vapor_outlet", "target": "vapor_product"},
            "layout": {"path_xy": [[2.0, 0.0], [3.0, 0.0]]},
        },
    )
    assert build_line_3.status_code == 200

    build_line_4 = client.post(
        f"/game/sessions/{session_id}/commands/build",
        json={
            "item_id": "build_process_line",
            "config": {"source": "flash_1.liquid_outlet", "target": "liquid_product"},
            "layout": {"path_xy": [[2.0, 0.0], [3.0, -1.0]]},
        },
    )
    assert build_line_4.status_code == 200

    snapshot = client.get(f"/game/sessions/{session_id}/snapshot")
    assert snapshot.status_code == 200
    payload = snapshot.json()
    assert isinstance(payload, dict)
    assert payload["mode_id"] == "heater_flash_guided_build_v1"
    assert payload["simulation_snapshot"]["active_tutorial_id"] == "heater_flash_guided_build_v1"
    assert payload["simulation_snapshot"]["elapsed_time_s"] >= 0.0


def test_restart_flow_smoke() -> None:
    client = _client()

    created = client.post("/game/sessions", json={"mode_id": "phase1_process_sandbox_v1"})
    assert created.status_code == 201
    created_payload = created.json()
    session_id = created_payload["session_id"]

    buy_feed = client.post(
        f"/game/sessions/{session_id}/commands/buy-feed",
        json={"material_id": "feed_a", "quantity_mol": 2.0},
    )
    assert buy_feed.status_code == 200

    build = client.post(
        f"/game/sessions/{session_id}/commands/build",
        json={
            "item_id": "place_heater_cooler",
            "config": {"process_id": "heater_1"},
            "layout": {"anchor_xy": [0.0, 0.0]},
        },
    )
    assert build.status_code == 200

    restarted = client.post(f"/game/sessions/{session_id}/restart")
    assert restarted.status_code == 200
    body = restarted.json()
    assert set(body) == {"accepted", "message", "snapshot"}
    assert body["snapshot"]["session_id"] == session_id

    snapshot = client.get(f"/game/sessions/{session_id}/snapshot")
    assert snapshot.status_code == 200
    payload = snapshot.json()
    assert isinstance(payload, dict)
    assert payload["simulation_snapshot"]["elapsed_time_s"] == pytest.approx(
        created_payload["snapshot"]["simulation_snapshot"]["elapsed_time_s"]
    )

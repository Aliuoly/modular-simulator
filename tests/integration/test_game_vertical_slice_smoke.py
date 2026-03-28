from __future__ import annotations

from importlib import import_module

from fastapi.testclient import TestClient


def _client() -> TestClient:
    return TestClient(import_module("modular_simulation.app.game_api").app)


def test_sandbox_vertical_slice_smoke_uses_gas_first_surface() -> None:
    client = _client()
    created = client.post("/game/sessions", json={"mode_id": "phase1_process_sandbox_v1"})
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    assert (
        client.post(
            f"/game/sessions/{session_id}/commands/build",
            json={
                "item_id": "place_inlet_gas_separator",
                "config": {"process_id": "sep_1"},
                "layout": {"anchor_xy": [0.0, 0.0]},
            },
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/game/sessions/{session_id}/commands/build",
            json={
                "item_id": "build_process_line",
                "config": {"source": "sweet_wet_gas", "target": "sep_1.inlet"},
                "layout": {"path_xy": [[0.0, 0.0], [1.0, 0.0]]},
            },
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/game/sessions/{session_id}/commands/build",
            json={
                "item_id": "build_process_line",
                "config": {"source": "sep_1.vapor_outlet", "target": "separator_gas"},
                "layout": {"path_xy": [[1.0, 0.0], [2.0, 0.0]]},
            },
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/game/sessions/{session_id}/commands/buy-feed",
            json={"material_id": "sweet_wet_gas", "quantity_mol": 2.0},
        ).status_code
        == 200
    )


def test_tutorial_vertical_slice_smoke_remains_heater_flash() -> None:
    client = _client()
    created = client.post("/game/sessions", json={"mode_id": "heater_flash_guided_build_v1"})
    assert created.status_code == 201
    session_id = created.json()["session_id"]
    assert (
        client.post(
            f"/game/sessions/{session_id}/commands/build",
            json={
                "item_id": "place_heater_cooler",
                "config": {"process_id": "heater_1"},
                "layout": {"anchor_xy": [0.0, 0.0]},
            },
        ).status_code
        == 200
    )

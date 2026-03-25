from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Mapping, cast

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from modular_simulation.gameplay.contracts import SandboxRequestError
from modular_simulation.gameplay.realtime_service import (
    build,
    buy_feed,
    create_session,
    get_bootstrap,
    get_snapshot,
    restart_session,
    sell_product,
)
from modular_simulation.gameplay.start_runtime import SUPPORTED_MODE_IDS


class _ApiError(Exception):
    def __init__(self, *, error_code: str, message: str, status_code: int) -> None:
        self.error_code = error_code
        self.message = message
        self.status_code = status_code


def _status_for_error_code(error_code: str) -> int:
    if error_code == "unknown_session":
        return 404
    if error_code in {
        "session_already_active",
        "insufficient_cash",
        "insufficient_product_inventory",
    }:
        return 409
    return 400


def _error_response(error_code: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error_code": error_code, "message": message},
    )


def _as_payload(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    return value


def create_app() -> FastAPI:
    app = FastAPI(title="Modular Simulation Game API")

    @app.exception_handler(_ApiError)
    async def _handle_api_error(_: Request, error: _ApiError) -> JSONResponse:
        return _error_response(error.error_code, error.message, error.status_code)

    @app.exception_handler(SandboxRequestError)
    async def _handle_sandbox_request_error(_: Request, error: SandboxRequestError) -> JSONResponse:
        return _error_response(
            error.error_code,
            error.message,
            _status_for_error_code(error.error_code),
        )

    @app.get("/game/bootstrap")
    async def bootstrap_route() -> object:
        return _as_payload(get_bootstrap())

    @app.post("/game/sessions", status_code=201)
    async def create_session_route(payload: Mapping[str, object]) -> object:
        mode_id = payload.get("mode_id")
        simulation_dt_s = payload.get("simulation_dt_s")
        if mode_id not in SUPPORTED_MODE_IDS:
            raise _ApiError(
                error_code="unknown_mode",
                message=f"Unknown mode id: {mode_id!r}",
                status_code=400,
            )
        if simulation_dt_s is not None and not isinstance(simulation_dt_s, (int, float)):
            raise _ApiError(
                error_code="unsupported_simulation_dt_s",
                message="simulation_dt_s must be numeric when provided",
                status_code=400,
            )
        created = create_session(
            mode_id=cast(str, mode_id),
            simulation_dt_s=None if simulation_dt_s is None else float(simulation_dt_s),
        )
        return _as_payload(created)

    @app.get("/game/sessions/{session_id}/snapshot")
    async def get_snapshot_route(session_id: str) -> object:
        return _as_payload(get_snapshot(session_id=session_id))

    @app.post("/game/sessions/{session_id}/commands/build")
    async def build_route(session_id: str, payload: Mapping[str, object]) -> object:
        item_id = payload.get("item_id")
        config = payload.get("config")
        layout = payload.get("layout")
        if not isinstance(item_id, str):
            raise _ApiError(
                error_code="unknown_item", message="item_id is required", status_code=400
            )
        if not isinstance(config, Mapping):
            raise _ApiError(
                error_code="invalid_config",
                message="config must be a JSON object",
                status_code=400,
            )
        if not isinstance(layout, Mapping):
            raise _ApiError(
                error_code="invalid_layout",
                message="layout must be a JSON object",
                status_code=400,
            )
        accepted = build(session_id=session_id, item_id=item_id, config=config, layout=layout)
        return _as_payload(accepted)

    @app.post("/game/sessions/{session_id}/commands/buy-feed")
    async def buy_feed_route(session_id: str, payload: Mapping[str, object]) -> object:
        material_id = payload.get("material_id")
        quantity_mol = payload.get("quantity_mol")
        if not isinstance(material_id, str) or not material_id:
            raise _ApiError(
                error_code="unknown_material",
                message="material_id is required",
                status_code=400,
            )
        if not isinstance(quantity_mol, (int, float)):
            raise _ApiError(
                error_code="invalid_quantity",
                message="quantity_mol must be numeric",
                status_code=400,
            )
        accepted = buy_feed(
            session_id=session_id,
            material_id=material_id,
            quantity_mol=float(quantity_mol),
        )
        return _as_payload(accepted)

    @app.post("/game/sessions/{session_id}/commands/sell-product")
    async def sell_product_route(session_id: str, payload: Mapping[str, object]) -> object:
        product_id = payload.get("product_id")
        quantity_mol = payload.get("quantity_mol")
        if not isinstance(product_id, str) or not product_id:
            raise _ApiError(
                error_code="unknown_product",
                message="product_id is required",
                status_code=400,
            )
        if not isinstance(quantity_mol, (int, float)):
            raise _ApiError(
                error_code="invalid_quantity",
                message="quantity_mol must be numeric",
                status_code=400,
            )
        accepted = sell_product(
            session_id=session_id,
            product_id=product_id,
            quantity_mol=float(quantity_mol),
        )
        return _as_payload(accepted)

    @app.post("/game/sessions/{session_id}/restart")
    async def restart_route(session_id: str) -> object:
        accepted = restart_session(session_id=session_id)
        return _as_payload(accepted)

    return app


app = create_app()

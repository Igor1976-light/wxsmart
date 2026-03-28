from __future__ import annotations

from fastapi import APIRouter

from .state import StateStore


def create_api_router(state_store: StateStore) -> APIRouter:
    router = APIRouter()

    @router.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/api/state")
    def get_state() -> dict:
        return state_store.snapshot()

    @router.get("/api/tools")
    def get_tools() -> dict:
        return state_store.snapshot().get("tools", {})

    @router.get("/api/station")
    def get_station() -> dict:
        return state_store.snapshot().get("station", {})

    return router

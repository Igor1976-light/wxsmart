from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from .api import create_api_router
from .config import settings
from .mqtt_service import MqttIngestService
from .state import StateStore


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


state_store = StateStore()
mqtt_service = MqttIngestService(settings, state_store)
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
INDEX_FILE = STATIC_DIR / "index.html"

app = FastAPI(title="WXsmart Dashboard API", version="0.1.0")
app.include_router(create_api_router(state_store))


@app.get("/")
def dashboard_index() -> FileResponse:
    return FileResponse(INDEX_FILE)


@app.websocket("/ws/live")
async def ws_live(websocket: WebSocket) -> None:
    await websocket.accept()
    last_message_count = -1
    try:
        while True:
            snapshot = state_store.snapshot()
            message_count = int(snapshot.get("message_count", 0))

            if message_count != last_message_count:
                await websocket.send_json(snapshot)
                last_message_count = message_count

            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")


@app.on_event("startup")
def on_startup() -> None:
    logger.info("Starting WXsmart Dashboard API")
    mqtt_service.start()


@app.on_event("shutdown")
def on_shutdown() -> None:
    logger.info("Stopping WXsmart Dashboard API")
    mqtt_service.stop()

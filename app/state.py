from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
import threading
from typing import Any


@dataclass
class ToolState:
    temperature_raw: str | None = None
    temperature_c: float | None = None
    power_raw: str | None = None
    power_w: float | None = None
    counter_time: str | None = None
    serial_number: str | None = None
    state: str | None = None
    updated_at: str | None = None


@dataclass
class StationState:
    online: str | None = None
    firmware: str | None = None
    device_name: str | None = None
    utc: str | None = None
    updated_at: str | None = None


@dataclass
class AppState:
    station: StationState = field(default_factory=StationState)
    tools: dict[str, ToolState] = field(
        default_factory=lambda: {"Tool1": ToolState(), "Tool2": ToolState()}
    )
    last_topic: str | None = None
    last_payload: str | None = None
    message_count: int = 0


class StateStore:
    def __init__(self) -> None:
        self._state = AppState()
        self._lock = threading.Lock()

    def _now(self) -> str:
        return datetime.now().isoformat(timespec="seconds")

    def update_from_topic(self, topic: str, payload_value: str) -> None:
        with self._lock:
            self._state.message_count += 1
            self._state.last_topic = topic
            self._state.last_payload = payload_value

            parts = topic.split("/")
            if len(parts) < 4 or parts[0].upper() != "WXSMART":
                return

            if "/STATUS/ONLINE" in topic:
                self._state.station.online = payload_value
                self._state.station.updated_at = self._now()
                return

            if "/Station1/Version/Firmware" in topic:
                self._state.station.firmware = payload_value
                self._state.station.updated_at = self._now()
                return

            if "/Config/System/DeviceName" in topic:
                self._state.station.device_name = payload_value
                self._state.station.updated_at = self._now()
                return

            if "/Station1/UTC" in topic:
                self._state.station.utc = payload_value
                self._state.station.updated_at = self._now()
                return

            tool_name = "Tool1" if "/STATUS/Tool1/" in topic else "Tool2" if "/STATUS/Tool2/" in topic else None
            if tool_name is None:
                return

            tool = self._state.tools[tool_name]
            if "/Temperature/Read" in topic:
                tool.temperature_raw = payload_value
                if payload_value.isdigit():
                    tool.temperature_c = int(payload_value) / 10.0
            elif "/Power/Read" in topic:
                tool.power_raw = payload_value
                if payload_value.isdigit():
                    tool.power_w = int(payload_value) / 10.0
            elif "/Power" in topic:
                tool.power_raw = payload_value
                if payload_value.isdigit():
                    tool.power_w = float(payload_value)
            elif "/Counter/Time" in topic:
                tool.counter_time = payload_value
            elif "/SerialNumber" in topic:
                tool.serial_number = payload_value
            elif topic.endswith("/State"):
                tool.state = payload_value

            tool.updated_at = self._now()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return asdict(self._state)

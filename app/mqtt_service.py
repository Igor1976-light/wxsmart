from __future__ import annotations

import json
import logging
from typing import Literal
from typing import Any

import paho.mqtt.client as mqtt

from .config import Settings
from .influx_writer import InfluxWriter
from .state import StateStore


logger = logging.getLogger(__name__)


class MqttIngestService:
    def __init__(self, settings: Settings, state_store: StateStore, influx_writer: InfluxWriter | None = None) -> None:
        self.settings = settings
        self.state_store = state_store
        self.influx_writer = influx_writer

        transport = self._normalize_transport(self.settings.mqtt_transport)
        callback_api_version = getattr(getattr(mqtt, "CallbackAPIVersion", None), "VERSION2", None)
        if callback_api_version is not None:
            self.client = mqtt.Client(
                callback_api_version=callback_api_version,
                transport=transport,
            )
        else:
            self.client = mqtt.Client(transport=transport)

        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect

    @staticmethod
    def _normalize_transport(value: str) -> Literal["tcp", "websockets", "unix"]:
        normalized = value.strip().lower()
        if normalized in ("tcp", "websockets", "unix"):
            return normalized  # type: ignore[return-value]
        return "websockets"

    def start(self) -> None:
        logger.info("MQTT connect %s:%s (%s)", self.settings.mqtt_host, self.settings.mqtt_port, self.settings.mqtt_transport)
        self.client.connect(self.settings.mqtt_host, self.settings.mqtt_port, keepalive=self.settings.mqtt_keepalive)
        self.client.loop_start()

    def stop(self) -> None:
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except Exception:
            logger.exception("MQTT stop failed")

    def on_connect(self, client: Any, userdata: Any, flags: Any, reason_code: Any, properties: Any = None) -> None:
        if reason_code == 0:
            logger.info("MQTT connected; subscribe %s", self.settings.mqtt_topic)
            client.subscribe(self.settings.mqtt_topic, qos=0)
        else:
            logger.error("MQTT connect failed: %s", reason_code)

    def on_disconnect(self, client: Any, userdata: Any, disconnect_flags: Any, reason_code: Any, properties: Any = None) -> None:
        logger.warning("MQTT disconnected: %s", reason_code)

    def on_message(self, client: Any, userdata: Any, msg: Any) -> None:
        payload_bytes = bytes(msg.payload)
        payload_text = payload_bytes.decode("utf-8", errors="replace")
        payload_value = self.parse_payload_value(payload_text)
        self.state_store.update_from_topic(msg.topic, payload_value)
        if self.influx_writer and self.influx_writer.enabled:
            snapshot = self.state_store.snapshot()
            # Nur bei Power- oder Temperatur-Topics schreiben (nicht bei jedem Counter-Heartbeat)
            topic_upper = msg.topic.upper()
            if "POWER" in topic_upper or "TEMPERATURE" in topic_upper:
                from .state import AppState
                import dataclasses
                app_state = self.state_store._state  # noqa: SLF001
                self.influx_writer.write_state(app_state)

    @staticmethod
    def parse_payload_value(payload_text: str) -> str:
        stripped = payload_text.strip()
        if not stripped:
            return ""
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            return payload_text

        if isinstance(parsed, (dict, list)):
            return json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))
        return str(parsed)

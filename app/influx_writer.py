"""
InfluxDB 2 Writer für wxsmart-Lötdaten.

Schreibt bei jeder MQTT-Nachricht die aktuellen Messwerte als Time-Series
in InfluxDB. Wird nur aktiv wenn INFLUX_URL in der Umgebung gesetzt ist.

Measurement: soldering_session
Tags:        tool (Tool1|Tool2), tip_id, tip_serial
Fields:      power_w, temperature_c, counter_time, operating_hours_total
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

try:
    from influxdb_client import InfluxDBClient, Point, WritePrecision
    from influxdb_client.client.write_api import SYNCHRONOUS
    _INFLUX_AVAILABLE = True
except ImportError:
    _INFLUX_AVAILABLE = False

if TYPE_CHECKING:
    from .config import Settings
    from .state import AppState


class InfluxWriter:
    """Schreibt Messwerte in InfluxDB 2. Kein-Op wenn nicht konfiguriert."""

    def __init__(self, settings: "Settings") -> None:
        self.settings = settings
        self._client = None
        self._write_api = None
        self._lock = threading.Lock()
        self._enabled = False

        if not settings.influx_url:
            logger.info("InfluxDB deaktiviert (INFLUX_URL nicht gesetzt)")
            return

        if not _INFLUX_AVAILABLE:
            logger.warning(
                "influxdb-client nicht installiert – InfluxDB-Schreiben deaktiviert. "
                "Installieren mit: pip install influxdb-client"
            )
            return

        try:
            self._client = InfluxDBClient(
                url=settings.influx_url,
                token=settings.influx_token,
                org=settings.influx_org,
                timeout=5_000,
            )
            self._write_api = self._client.write_api(write_options=SYNCHRONOUS)
            self._enabled = True
            logger.info(
                "InfluxDB Writer bereit: %s  bucket=%s  org=%s",
                settings.influx_url,
                settings.influx_bucket,
                settings.influx_org,
            )
        except Exception:
            logger.exception("InfluxDB Writer konnte nicht initialisiert werden")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def enabled(self) -> bool:
        return self._enabled

    def write_state(self, state: "AppState") -> None:
        """Schreibt alle Tool-Messwerte aus dem aktuellen AppState."""
        if not self._enabled:
            return

        now = datetime.now(tz=timezone.utc)
        points: list[Point] = []

        for tool_name, tool in state.tools.items():
            # Nur schreiben wenn mindestens Power oder Temperatur vorhanden
            if tool.power_w is None and tool.temperature_c is None:
                continue

            # Zugehörige Tip-Metadaten
            tip_key = tool_name.replace("Tool", "Tip")
            tip = state.tips.get(tip_key)

            p = (
                Point("soldering_session")
                .tag("tool", tool_name)
                .tag("tip_id", tip.id if tip and tip.id else "unknown")
                .tag("tip_serial", tip.serial_number if tip and tip.serial_number else "unknown")
                .tag("tool_serial", tool.serial_number or "unknown")
                .time(now, WritePrecision.SECONDS)
            )

            if tool.power_w is not None:
                p = p.field("power_w", float(tool.power_w))
            if tool.temperature_c is not None:
                p = p.field("temperature_c", float(tool.temperature_c))
            if tool.counter_time is not None:
                try:
                    p = p.field("counter_time_s", int(tool.counter_time))
                except (ValueError, TypeError):
                    pass
            if tool.operating_hours_total is not None:
                try:
                    p = p.field("operating_hours_total", int(tool.operating_hours_total))
                except (ValueError, TypeError):
                    pass

            points.append(p)

        if not points:
            return

        try:
            with self._lock:
                self._write_api.write(
                    bucket=self.settings.influx_bucket,
                    org=self.settings.influx_org,
                    record=points,
                )
        except Exception:
            logger.exception("InfluxDB Schreibfehler")

    def stop(self) -> None:
        """Verbindung sauber schließen."""
        if self._client is not None:
            try:
                self._client.close()
                logger.info("InfluxDB Writer gestoppt")
            except Exception:
                logger.exception("InfluxDB close fehlgeschlagen")
        self._enabled = False

from __future__ import annotations

import io
import csv
from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING

from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import StreamingResponse

from .state import StateStore

if TYPE_CHECKING:
    from .influx_writer import InfluxWriter


def create_api_router(state_store: StateStore, influx_writer: "InfluxWriter | None" = None) -> APIRouter:
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

    @router.get("/api/export/csv")
    def export_csv(
        start: str = Query(
            default=None,
            description="Start-Zeitpunkt (ISO8601, z.B. 2026-03-29T10:00:00Z). Standard: letzte Stunde.",
        ),
        stop: str = Query(
            default=None,
            description="End-Zeitpunkt (ISO8601). Standard: jetzt.",
        ),
        tool: str = Query(
            default="both",
            description="Welches Tool: Tool1 | Tool2 | both",
        ),
    ) -> StreamingResponse:
        """Exportiert Lötdaten als CSV-Datei aus InfluxDB."""
        if influx_writer is None or not influx_writer.enabled:
            raise HTTPException(
                status_code=503,
                detail="InfluxDB nicht konfiguriert. INFLUX_URL in .env setzen.",
            )

        # Zeitbereich bestimmen
        now = datetime.now(tz=timezone.utc)
        try:
            t_stop = datetime.fromisoformat(stop.replace("Z", "+00:00")) if stop else now
            t_start = datetime.fromisoformat(start.replace("Z", "+00:00")) if start else t_stop - timedelta(hours=1)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=f"Ungültiges Zeitformat: {exc}") from exc

        # Tool-Filter
        tool_filter = ""
        if tool in ("Tool1", "Tool2"):
            tool_filter = f'|> filter(fn: (r) => r["tool"] == "{tool}")'

        flux_query = f"""
            from(bucket: "{influx_writer.settings.influx_bucket}")
              |> range(start: {t_start.strftime("%Y-%m-%dT%H:%M:%SZ")}, stop: {t_stop.strftime("%Y-%m-%dT%H:%M:%SZ")})
              |> filter(fn: (r) => r["_measurement"] == "soldering_session")
              {tool_filter}
              |> pivot(rowKey: ["_time", "tool", "tip_id", "tip_serial", "tool_serial"],
                       columnKey: ["_field"],
                       valueColumn: "_value")
              |> sort(columns: ["_time"])
        """

        try:
            query_api = influx_writer._client.query_api()  # noqa: SLF001
            tables = query_api.query(flux_query, org=influx_writer.settings.influx_org)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"InfluxDB Query-Fehler: {exc}") from exc

        # Daten in CSV umwandeln
        output = io.StringIO()
        writer = csv.writer(output)

        columns = ["time", "tool", "tip_id", "tip_serial", "tool_serial",
                   "power_w", "temperature_c", "counter_time_s", "operating_hours_total"]
        writer.writerow(columns)

        for table in tables:
            for record in table.records:
                writer.writerow([
                    record.get_time().isoformat() if record.get_time() else "",
                    record.values.get("tool", ""),
                    record.values.get("tip_id", ""),
                    record.values.get("tip_serial", ""),
                    record.values.get("tool_serial", ""),
                    record.values.get("power_w", ""),
                    record.values.get("temperature_c", ""),
                    record.values.get("counter_time_s", ""),
                    record.values.get("operating_hours_total", ""),
                ])

        filename = f"wxsmart_{t_start.strftime('%Y%m%d_%H%M')}_{t_stop.strftime('%Y%m%d_%H%M')}.csv"
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return router

# WXsmart Workspace

This project captures and visualizes MQTT data from a **Weller WX SMART Power Unit**.

It includes:

- a CLI monitor (`wxsmart.py`)
- a FastAPI-based dashboard API with live WebSocket updates
- a browser dashboard (`app/static/index.html`)
- diagnostic scripts for topic discovery and analysis

## Purpose

- Live monitoring of MQTT data sent by the station
- Browser-based live visualization (Station, Tool1, Tool2, Log)
- Support for MQTT topic analysis, debugging, and firmware behavior checks

## Supported platforms

- **macOS**
- **Linux**
- **Windows**

Requirements: a Python environment and a reachable MQTT broker.

## Prerequisites

- **Python 3.11+** (virtual environment recommended)
- MQTT broker (for example Mosquitto), typically with WebSocket support
- Python dependencies from `requirements.txt`
- optional: modern browser for the dashboard

## Project structure

- `app/main.py` – FastAPI app, lifespan startup/shutdown, WebSocket `/ws/live`
- `app/config.py` – ENV-based configuration
- `app/state.py` – in-memory state (`station`, `tools`, `tips`) + topic parsing
- `app/mqtt_service.py` – MQTT subscriber/ingest
- `app/influx_writer.py` – optional InfluxDB 2 writer (active when `INFLUX_URL` is set)
- `app/api.py` – REST endpoints (`/api/health`, `/api/state`, `/api/tools`, `/api/station`, `/api/export/csv`)
- `app/static/index.html` – live dashboard
- `scripts/run_dashboard.sh` – local start helper
- `scripts/reload_dashboard.sh` – restart + health checks
- `diagnostic/mqtt_discovery.py` – topic discovery (all topics, filters, grouping)
- `docker-compose.yml` – InfluxDB 2 + Grafana stack
- `grafana/provisioning/` – Grafana datasource + dashboard (auto-provisioned)
- `wxsmart.py` – CLI monitor

## Current dashboard status

- **Station**: Online, Firmware, Device Name, Total Power, UTC, Updated
- **Tool1/Tool2**: ID, Temperature (+ history chart), Power, Counter Time, Operating Hours Total, Serial, Firmware
- **Tip1/Tip2**: ID, Serial (only fields that currently provide data on this firmware)
- **Log tab**: latest live updates

Note: available topics/fields depend on firmware and station configuration.

## Quick start (dashboard)

1. Install dependencies:

```zsh
cd /path/to/wxsmart
source .venv/bin/activate
pip install -r requirements.txt
```

2. Optionally prepare `.env`:

```zsh
cp .env.example .env
```

3. Start dashboard:

```zsh
cd /path/to/wxsmart
source .venv/bin/activate
scripts/run_dashboard.sh
```

or directly via `uvicorn`:

```zsh
cd /path/to/wxsmart
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

4. Open/test:

- `http://127.0.0.1:8000/`
- `http://127.0.0.1:8000/api/health`
- `http://127.0.0.1:8000/api/state`

## Useful scripts

Reload dashboard (kill/start + checks):

```zsh
cd /path/to/wxsmart
scripts/reload_dashboard.sh
```

Discover MQTT topics (see all incoming data):

```zsh
cd /path/to/wxsmart
python3 diagnostic/mqtt_discovery.py --duration 120 --group --verbose
```

Filtered examples:

```zsh
python3 diagnostic/mqtt_discovery.py --pattern "Tool" --duration 90 --group --verbose
python3 diagnostic/mqtt_discovery.py --pattern "Tip" --duration 60 --verbose
python3 diagnostic/mqtt_discovery.py --pattern "Tool.*Power" --regex --duration 60
```

## Key environment variables

- `MQTT_HOST` (default: `localhost`)
- `MQTT_PORT` (default: `9001`)
- `MQTT_TOPIC` (default: `WXSMART/#`)
- `MQTT_TRANSPORT` (default: `websockets`)
- `APP_HOST` (default: `127.0.0.1`)
- `APP_PORT` (default: `8000`)

InfluxDB (optional — leave empty to disable):

- `INFLUX_URL` (e.g. `http://localhost:8086`)
- `INFLUX_TOKEN` (API token from InfluxDB)
- `INFLUX_ORG` (default: `wxsmart`)
- `INFLUX_BUCKET` (default: `soldering`)

## InfluxDB + Grafana (time-series recording)

The stack stores all power and temperature values as time-series data and
displays them in Grafana. CSV export is available via the API endpoint.

**Start the stack:**

```zsh
# Set token in .env:
echo 'INFLUX_TOKEN=my-secure-token' >> .env

docker compose up -d
```

Then open:

- Grafana: `http://localhost:3000` (login: `admin` / `admin`)
- InfluxDB: `http://localhost:8086` (login: `admin` / `adminadmin`)

**Connect the wxsmart app to InfluxDB:**

```zsh
# Add to .env:
INFLUX_URL=http://localhost:8086
INFLUX_TOKEN=my-secure-token
```

Data will be written automatically on the next dashboard start.

**CSV export:**

```zsh
# Last hour:
curl "http://127.0.0.1:8000/api/export/csv" -o session.csv

# Specific time range:
curl "http://127.0.0.1:8000/api/export/csv?start=2026-03-29T10:00:00Z&stop=2026-03-29T11:00:00Z" -o session.csv

# Tool1 only:
curl "http://127.0.0.1:8000/api/export/csv?tool=Tool1" -o tool1.csv
```

Stored fields: `time`, `tool`, `tip_id`, `tip_serial`, `tool_serial`, `power_w`, `temperature_c`, `counter_time_s`, `operating_hours_total`

**Grafana dashboard** includes:
- Power over time for Tool1 + Tool2 [W]
- Temperature over time for Tool1 + Tool2 [°C]
- Energy consumption [Wh] (integral over selected time range)
- Average temperature per tool

## Live updates without reload

- Dashboard uses `ws://<host>/ws/live` (or `wss://` under HTTPS)
- a snapshot is sent immediately after connect
- changes are then streamed live
- automatic reconnect is used on disconnect

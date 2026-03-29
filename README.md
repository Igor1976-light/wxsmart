# WXsmart Workspace

Dieses Projekt erfasst und visualisiert MQTT-Daten einer **Weller WX SMART Power Unit**.

Es enthält:

- einen CLI-Monitor (`wxsmart.py`)
- eine FastAPI-basierte Dashboard-API mit Live-WebSocket
- ein Browser-Dashboard (`app/static/index.html`)
- Diagnose-Skripte für Topic-Discovery und Analyse

## Zweck

- Live-Monitoring der von der Station gesendeten MQTT-Daten
- grafische Live-Anzeige im Browser (Station, Tool1, Tool2, Log)
- Unterstützung bei Analyse/Fehlersuche von MQTT-Themen und Firmware-Verhalten

## Plattformen

- **macOS**
- **Linux**
- **Windows**

Voraussetzung: Python-Umgebung + erreichbarer MQTT-Broker.

## Voraussetzungen

- **Python 3.11+** (virtuelle Umgebung empfohlen)
- MQTT-Broker (z. B. Mosquitto), typischerweise mit WebSocket-Support
- Abhängigkeiten aus `requirements.txt`
- optional: moderner Browser für das Dashboard

## Projektstruktur

- `app/main.py` – FastAPI App, Lifespan-Start/Stop, WebSocket `/ws/live`
- `app/config.py` – Konfiguration aus ENV
- `app/state.py` – In-Memory-Zustand (`station`, `tools`, `tips`) + Topic-Parsing
- `app/mqtt_service.py` – MQTT-Subscriber/Ingest
- `app/influx_writer.py` – optionaler InfluxDB 2-Writer (aktiv wenn `INFLUX_URL` gesetzt)
- `app/api.py` – REST-Endpunkte (`/api/health`, `/api/state`, `/api/tools`, `/api/station`, `/api/export/csv`)
- `app/static/index.html` – Live-Dashboard
- `scripts/run_dashboard.sh` – lokaler Starthelfer
- `scripts/reload_dashboard.sh` – Neustart + Erreichbarkeits-Check
- `diagnostic/mqtt_discovery.py` – Topic-Discovery (alle Topics, Filter, Gruppierung)
- `docker-compose.yml` – InfluxDB 2 + Grafana Stack
- `grafana/provisioning/` – Grafana Datasource + Dashboard (auto-provisioned)
- `wxsmart.py` – CLI-Monitor

## Aktueller Dashboard-Stand

- **Station**: Online, Firmware, Device Name, Gesamtleistung, UTC, Aktualisiert
- **Tool1/Tool2**: ID, Temperatur (+ Verlauf), Power, Counter Time, Operating Hours Total, Serial, Firmware
- **Tip1/Tip2**: ID, Serial (nur Felder, die auf aktueller Firmware tatsächlich Daten liefern)
- **Log-Tab**: letzte Live-Updates

Hinweis: Welche Topics/Felder verfügbar sind, hängt von Firmware und Station-Konfiguration ab.

## Schnellstart (Dashboard)

1. Abhängigkeiten installieren:

```zsh
cd /pfad/zu/wxsmart
source .venv/bin/activate
pip install -r requirements.txt
```

2. Optional `.env` vorbereiten:

```zsh
cp .env.example .env
```

3. Dashboard starten:

```zsh
cd /pfad/zu/wxsmart
source .venv/bin/activate
scripts/run_dashboard.sh
```

oder direkt via `uvicorn`:

```zsh
cd /pfad/zu/wxsmart
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

4. Öffnen/Testen:

- `http://127.0.0.1:8000/`
- `http://127.0.0.1:8000/api/health`
- `http://127.0.0.1:8000/api/state`

## Nützliche Skripte

Dashboard neu laden (kill/start + Check):

```zsh
cd /pfad/zu/wxsmart
scripts/reload_dashboard.sh
```

MQTT-Topics entdecken (alle Daten sehen):

```zsh
cd /pfad/zu/wxsmart
python3 diagnostic/mqtt_discovery.py --duration 120 --group --verbose
```

Beispiele mit Filter:

```zsh
python3 diagnostic/mqtt_discovery.py --pattern "Tool" --duration 90 --group --verbose
python3 diagnostic/mqtt_discovery.py --pattern "Tip" --duration 60 --verbose
python3 diagnostic/mqtt_discovery.py --pattern "Tool.*Power" --regex --duration 60
```

## Wichtige ENV-Variablen

- `MQTT_HOST` (Default: `localhost`)
- `MQTT_PORT` (Default: `9001`)
- `MQTT_TOPIC` (Default: `WXSMART/#`)
- `MQTT_TRANSPORT` (Default: `websockets`)
- `APP_HOST` (Default: `127.0.0.1`)
- `APP_PORT` (Default: `8000`)

InfluxDB (optional — leer lassen um zu deaktivieren):

- `INFLUX_URL` (z.B. `http://localhost:8086`)
- `INFLUX_TOKEN` (API-Token aus InfluxDB)
- `INFLUX_ORG` (Default: `wxsmart`)
- `INFLUX_BUCKET` (Default: `soldering`)

## InfluxDB + Grafana (Time-Series-Aufzeichnung)

Der Stack speichert alle Power- und Temperaturwerte als Zeitreihe und
stellt sie in Grafana dar. CSV-Export ist über den API-Endpunkt möglich.

**Stack starten:**

```zsh
# Token in .env setzen:
echo 'INFLUX_TOKEN=mein-sicherer-token' >> .env

docker compose up -d
```

Danach:

- Grafana: `http://localhost:3000` (Login: `admin` / `admin`)
- InfluxDB: `http://localhost:8086` (Login: `admin` / `adminadmin`)

**wxsmart-App mit InfluxDB verbinden:**

```zsh
# In .env hinzufügen:
INFLUX_URL=http://localhost:8086
INFLUX_TOKEN=mein-sicherer-token
```

Beim nächsten Start des Dashboards wird automatisch geschrieben.

**CSV-Export:**

```zsh
# Letzte Stunde:
curl "http://127.0.0.1:8000/api/export/csv" -o session.csv

# Bestimmter Zeitraum:
curl "http://127.0.0.1:8000/api/export/csv?start=2026-03-29T10:00:00Z&stop=2026-03-29T11:00:00Z" -o session.csv

# Nur Tool1:
curl "http://127.0.0.1:8000/api/export/csv?tool=Tool1" -o tool1.csv
```

Gespeicherte Felder: `time`, `tool`, `tip_id`, `tip_serial`, `tool_serial`, `power_w`, `temperature_c`, `counter_time_s`, `operating_hours_total`

**Grafana-Dashboard** enthält:
- Power-Verlauf Tool1 + Tool2 [W]
- Temperatur-Verlauf Tool1 + Tool2 [°C]
- Energieverbrauch [Wh] (Integral über gewählten Zeitraum)
- Durchschnittstemperatur je Tool

## Live-Update ohne Reload

- Dashboard nutzt `ws://<host>/ws/live` (unter HTTPS: `wss://...`)
- beim Verbinden wird ein Snapshot übertragen
- danach kommen Änderungen live
- bei Verbindungsabbruch erfolgt automatischer Reconnect

## English documentation

An English version is available in `README_en.md`.

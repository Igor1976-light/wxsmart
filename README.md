# WXsmart Workspace

Dieses Repository enthält aktuell zwei Ebenen:

- `wxsmart_2.py`: bestehender CLI-Monitor (laufender Produktions-/Testpfad)
- `app/`: neuer Startpunkt für das kommende Browser-Dashboard (FastAPI + MQTT Ingest)

## Struktur

- `app/main.py` – FastAPI App + Startup/Shutdown
- `app/config.py` – Umgebungsvariablen
- `app/state.py` – In-Memory Zustand (`Tool1`, `Tool2`, `station`)
- `app/mqtt_service.py` – MQTT Subscriber und Topic-Ingest
- `app/api.py` – REST-Endpunkte (`/api/health`, `/api/state`, `/api/tools`, `/api/station`)
- `app/static/index.html` – erstes Live-Dashboard im Browser
- `scripts/run_dashboard.sh` – lokaler Starthelfer
- `todo.md` – Roadmap für das vollständige Live-Dashboard

## Schnellstart (Dashboard-API)

1. Abhängigkeiten installieren:

```zsh
cd /pfad/zu/wxsmart
source .venv/bin/activate
pip install -r requirements.txt
```

Optional: Umgebungsvariablen vorbereiten:

```zsh
cp .env.example .env
```

Danach Werte in `.env` anpassen (z. B. `MQTT_HOST`, `MQTT_TOPIC`).

2. API starten:

```zsh
cd /pfad/zu/wxsmart
source .venv/bin/activate
MQTT_HOST=<broker-ip-oder-hostname> MQTT_PORT=9001 uvicorn app.main:app --host 127.0.0.1 --port 8000
```

3. Testen:

- `http://127.0.0.1:8000/api/health`
- `http://127.0.0.1:8000/api/state`
- `http://127.0.0.1:8000/` (Live-Dashboard)

## Wichtige ENV-Variablen

- `MQTT_HOST` (Default: `localhost`)
- `MQTT_PORT` (Default: `9001`)
- `MQTT_TOPIC` (Default: `WXSMART/#`, optional spezifischer Filter: `WXSMART/<seriennummer>/#`)
- `MQTT_TRANSPORT` (Default: `websockets`)
- `APP_HOST` (Default: `127.0.0.1`)
- `APP_PORT` (Default: `8000`)

## Hinweis

`wxsmart_2.py` bleibt unverändert nutzbar. Die neue `app/`-Struktur ist der Einstieg für das spätere Browser-Dashboard.

### Live-Update ohne Reload

- Das Dashboard nutzt `ws://127.0.0.1:8000/ws/live` (bzw. `wss://` unter HTTPS).
- Beim Verbinden wird automatisch ein Snapshot angezeigt; danach kommen Änderungen live nach.
- Bei Verbindungsabbruch versucht die Seite automatisch einen Reconnect.

#!/usr/bin/env zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

HOST="${APP_HOST:-127.0.0.1}"
PORT="${APP_PORT:-8000}"
LOG_FILE="${APP_LOG_FILE:-temp/dashboard.log}"
APP_IMPORT="app.main:app"

mkdir -p "$(dirname "$LOG_FILE")"

echo "[reload] Root      : $ROOT_DIR"
echo "[reload] Host/Port : $HOST:$PORT"
echo "[reload] Log       : $LOG_FILE"

# Alte Prozesse auf dem Port oder mit passendem Import beenden
existing_pids="$(lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)"
if [[ -n "$existing_pids" ]]; then
  echo "[reload] Stoppe PID(s) auf Port $PORT: $existing_pids"
  kill $existing_pids 2>/dev/null || true
fi

pkill -f "uvicorn $APP_IMPORT" 2>/dev/null || true
sleep 1

# Virtuelle Umgebung nutzen, falls vorhanden
if [[ -x ".venv/bin/python" ]]; then
  PYTHON_BIN=".venv/bin/python"
else
  PYTHON_BIN="python3"
fi

echo "[reload] Starte Dashboard..."
"$PYTHON_BIN" -m uvicorn "$APP_IMPORT" --host "$HOST" --port "$PORT" > "$LOG_FILE" 2>&1 &
NEW_PID=$!

# Kurz warten und dann prüfen
sleep 2

if ! kill -0 "$NEW_PID" 2>/dev/null; then
  echo "[reload] FEHLER: Prozess ist direkt beendet. Log-Auszug:"
  tail -n 40 "$LOG_FILE" || true
  exit 1
fi

if curl -fsS "http://$HOST:$PORT/api/health" >/dev/null 2>&1; then
  echo "[reload] OK: API erreichbar unter http://$HOST:$PORT/api/health"
else
  echo "[reload] WARNUNG: API-Healthcheck fehlgeschlagen. Log-Auszug:"
  tail -n 40 "$LOG_FILE" || true
  exit 1
fi

if curl -fsS "http://$HOST:$PORT/" >/dev/null 2>&1; then
  echo "[reload] OK: Dashboard erreichbar unter http://$HOST:$PORT/"
else
  echo "[reload] WARNUNG: Dashboard-Root nicht erreichbar."
  tail -n 40 "$LOG_FILE" || true
  exit 1
fi

echo "[reload] Erfolgreich neu geladen (PID $NEW_PID)."

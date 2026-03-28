#!/usr/bin/env zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -f ".venv/bin/activate" ]]; then
  source ".venv/bin/activate"
fi

reload_flag=""
if [[ "${APP_RELOAD:-0}" == "1" || "${APP_RELOAD:-0}" == "true" || "${APP_RELOAD:-0}" == "yes" ]]; then
  reload_flag="--reload"
fi

exec uvicorn app.main:app --host "${APP_HOST:-127.0.0.1}" --port "${APP_PORT:-8000}" $reload_flag

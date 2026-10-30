#!/usr/bin/env bash
# Start the FastAPI backend in development mode.
set -euo pipefail
cd "$(dirname "$0")/../backend"

PYTHON_BIN="${PYTHON_BIN:-python3.11}"
command -v "$PYTHON_BIN" >/dev/null 2>&1 || PYTHON_BIN=python3

if [ ! -d .venv ]; then
  echo "Creating virtual environment with $PYTHON_BIN ..."
  "$PYTHON_BIN" -m venv .venv
fi

if [ -f .venv/bin/activate ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
else
  # shellcheck disable=SC1091
  source .venv/Scripts/activate   # Git Bash on Windows
fi

pip install -q -r requirements-dev.txt

if [ ! -f .env ]; then
  cp .env.example .env
  echo "WARNING: backend/.env was missing; copied from .env.example. Review its values."
fi

exec uvicorn app.main:app --reload --host 0.0.0.0 --port 8000


#!/usr/bin/env bash
# Start the Vite frontend dev server.
set -euo pipefail
cd "$(dirname "$0")/../frontend"

if [ ! -d node_modules ]; then
  npm install
fi

if [ ! -f .env ]; then
  cp .env.example .env
  echo "WARNING: frontend/.env was missing; copied from .env.example. Review its values."
fi

exec npm run dev


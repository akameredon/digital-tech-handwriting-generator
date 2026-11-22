#!/usr/bin/env bash
# Replit and local preview entrypoint for the FastAPI app.
set -euo pipefail

if [ ! -d "frontend/node_modules" ]; then
  npm ci --prefix frontend
fi
npm run build --prefix frontend

if [ "${1:-}" = "--build-only" ]; then
  exit 0
fi

exec python3 -m uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"

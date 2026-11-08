#!/usr/bin/env bash
# Start the API and the React UI with private credentials loaded from .env.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -x .venv/bin/python || ! -d frontend/node_modules ]]; then
  echo "Dependencies not installed. Run: bash scripts/setup_mac.sh" >&2
  exit 1
fi
if [[ ! -f .env ]]; then
  echo "Missing .env. Run bash scripts/setup_mac.sh then edit .env." >&2
  exit 1
fi

if ! grep -Eq '^GEMINI_API_KEY=[[:space:]]*[^[:space:]#]+' .env; then
  echo "Gemini key is empty. The app will start in guided-demo mode."
fi

echo "Starting FastAPI backend on http://localhost:8000 ..."
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 &
backend_pid=$!
cleanup() {
  kill "$backend_pid" 2>/dev/null || true
  wait "$backend_pid" 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

echo "Starting React frontend on http://localhost:5173 ..."
echo "Use Ctrl+C to stop both services."
(cd frontend && npm run dev -- --host 127.0.0.1)

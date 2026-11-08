#!/usr/bin/env bash
# Run AFTER cloning casewise-ai. No credentials are read or printed by this script.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is missing. Install Python 3.10+ and try again." >&2
  exit 1
fi
if ! python3 -c 'import sys; assert sys.version_info >= (3, 10)' 2>/dev/null; then
  echo "Python 3.10+ is required." >&2
  exit 1
fi
if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
  echo "Node.js 18+ and npm are required. Install them and try again." >&2
  exit 1
fi
if ! node -e 'process.exit(Number(process.versions.node.split(".")[0]) >= 18 ? 0 : 1)'; then
  echo "Node.js 18+ is required." >&2
  exit 1
fi

echo "Setting up Python environment..."
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt

echo "Installing React frontend dependencies..."
(cd frontend && npm install)

if [[ ! -f .env ]]; then
  cp .env.example .env
  chmod 600 .env
  echo "Created a private .env file (empty API key)."
else
  echo "Existing .env preserved unchanged."
fi

echo
echo "Setup complete. Next:"
echo "  1. Edit the local secret file: nano .env"
echo "  2. Change GEMINI_API_KEY= to GEMINI_API_KEY=YOUR_REAL_KEY"
echo "  3. Save with Ctrl+O, Enter, then Ctrl+X"
echo "  4. Start the app: bash scripts/run_mac.sh"
echo "Never commit .env or share the real key."

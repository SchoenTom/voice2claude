#!/usr/bin/env bash
# voice2claude starten. Nutzt .venv falls vorhanden, sonst system-python3.
set -euo pipefail
cd "$(dirname "$0")"
if [ -x .venv/bin/python ]; then
  exec .venv/bin/python server.py "$@"
else
  exec python3 server.py "$@"
fi

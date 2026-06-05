#!/usr/bin/env bash
# Doppelklick -> startet die voice2claude Menüleisten-App (🎙️ oben rechts).
# Dieses Terminal-Fenster offen lassen (oder minimieren) — es hält die App am Leben.
cd "$(dirname "$0")"
[ -d .venv ] || ./setup.sh
echo "voice2claude startet in der Menüleiste (🎙️). Fenster offen lassen."
exec .venv/bin/python menubar.py

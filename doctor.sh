#!/usr/bin/env bash
# voice2claude doctor — prüft, ob alles für den Betrieb bereit ist.
cd "$(dirname "$0")"
G=$'\033[32m'; R=$'\033[31m'; Y=$'\033[33m'; N=$'\033[0m'
ok(){   echo "  ${G}✓${N} $1"; }
bad(){  echo "  ${R}✗${N} $1"; FAIL=1; }
warn(){ echo "  ${Y}!${N} $1"; }
FAIL=0
PY=.venv/bin/python; [ -x "$PY" ] || PY=python3

echo "voice2claude doctor"
echo "-------------------"

command -v python3 >/dev/null && ok "python3: $(python3 --version 2>&1)" || bad "python3 fehlt"
[ -d .venv ] && ok ".venv vorhanden" || warn ".venv fehlt — ./setup.sh ausführen"
$PY -c 'import faster_whisper' 2>/dev/null && ok "faster-whisper importierbar" || bad "faster-whisper fehlt — ./setup.sh"
$PY -c 'import flask' 2>/dev/null && ok "flask importierbar" || bad "flask fehlt — ./setup.sh"
$PY -c 'import rumps' 2>/dev/null && ok "rumps (Menüleiste) importierbar" || warn "rumps fehlt — Menüleisten-App geht nicht (./setup.sh)"

command -v osascript >/dev/null && ok "osascript da" || bad "osascript fehlt (kein macOS?)"
command -v tmux >/dev/null && ok "tmux da (tmux-Modus möglich)" || warn "tmux fehlt (nur paste/clipboard)"

# Bedienungshilfen
if osascript -e 'tell application "System Events" to count (every window of (first process whose frontmost is true))' >/dev/null 2>&1; then
  ok "Bedienungshilfen aktiv (Auto-Tippen geht)"
else
  bad "Bedienungshilfen AUS — Terminal in Systemeinstellungen → Datenschutz → Bedienungshilfen freigeben"
fi

# Zertifikat
{ [ -f cert.pem ] && [ -f key.pem ]; } && ok "HTTPS-Zertifikat da (Browser-Mikrofon)" || warn "kein Zertifikat — Browser-Client braucht HTTPS (./setup.sh)"

# Ports frei?
PORT=$(grep -E '^V2C_PORT=' .env 2>/dev/null | cut -d= -f2 | tr -dc 0-9); PORT=${PORT:-8765}
if lsof -nP -iTCP:$PORT -sTCP:LISTEN >/dev/null 2>&1; then
  warn "Port $PORT belegt (Server läuft evtl. schon)"
else
  ok "Port $PORT frei"
fi

# Netzwerk
IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null)
[ -n "$IP" ] && ok "LAN-IP: $IP  (iPhone: http://$IP:$PORT/)" || warn "keine LAN-IP — selbes WLAN/Hotspot?"

echo "-------------------"
[ "$FAIL" = 1 ] && echo "${R}Es gibt Probleme — siehe ✗ oben.${N}" || echo "${G}Alles bereit.${N}"
exit ${FAIL:-0}

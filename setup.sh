#!/usr/bin/env bash
# voice2claude — einmaliges Setup (isoliertes venv, beruehrt dein conda nicht)
set -euo pipefail
cd "$(dirname "$0")"

echo "==> Virtuelle Umgebung (.venv) anlegen"
[ -d .venv ] || python3 -m venv .venv

echo "==> Abhaengigkeiten installieren"
./.venv/bin/pip install --upgrade pip >/dev/null
./.venv/bin/pip install -r requirements.txt

echo "==> tmux (optional, nur fuer den tmux-Injection-Modus)"
command -v tmux >/dev/null 2>&1 || brew install tmux || echo "    (uebersprungen — paste-Modus braucht kein tmux)"

echo "==> HTTPS-Zertifikat fuer den Browser-Client (optional)"
if [ ! -f cert.pem ] || [ ! -f key.pem ]; then
  openssl req -x509 -newkey rsa:2048 -nodes \
    -keyout key.pem -out cert.pem -days 825 \
    -subj "/CN=voice2claude" >/dev/null 2>&1
  echo "    cert.pem / key.pem erstellt"
else
  echo "    Zertifikat existiert bereits"
fi

echo
echo "Fertig. Starten mit:   ./run.sh"
echo "Dann das iPhone (gleiches WLAN) auf die angezeigte Adresse richten."

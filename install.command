#!/usr/bin/env bash
# EINMAL doppelklicken. Richtet alles ein UND baut die App. Danach nie wieder.
cd "$(dirname "$0")"
./setup.sh
./make_app.sh
echo
echo "════════════════════════════════════════════════════════════"
echo "  ✓ Fertig. Deine App liegt hier:  voice2claude.app"
echo
echo "  SO GEHT'S WEITER (einmalig):"
echo "  1) Im Finder, der gleich aufgeht, voice2claude.app ins DOCK ziehen."
echo "  2) Per Rechtsklick → \"Öffnen\" einmal starten (Gatekeeper)."
echo "  3) 🎙️ erscheint oben → Server läuft automatisch."
echo
echo "  Ab dann: einfach das Dock-Icon klicken. Nie wieder ein Skript."
echo "════════════════════════════════════════════════════════════"
open -R voice2claude.app   # zeigt die App im Finder
read -n1 -r -p "Taste drücken zum Schließen…"

#!/usr/bin/env bash
# Baut voice2claude.app — den Doppelklick-Start-Button (Menüleisten-Agent mit
# Icon, kein Terminal-Fenster). EINMAL ausführen; danach IMMER die .app nutzen.
set -euo pipefail
cd "$(dirname "$0")"
REPO="$(pwd)"
APP="$REPO/voice2claude.app"

[ -d .venv ] || ./setup.sh

# --- Icon erzeugen (icon.png -> icon.icns) ---
[ -f icon.png ] || ./.venv/bin/python make_icon.py
if [ -f icon.png ] && command -v iconutil >/dev/null; then
  rm -rf /tmp/v2c.iconset; mkdir -p /tmp/v2c.iconset
  for s in 16 32 128 256 512; do
    sips -z $s $s        icon.png --out /tmp/v2c.iconset/icon_${s}x${s}.png    >/dev/null
    sips -z $((s*2)) $((s*2)) icon.png --out /tmp/v2c.iconset/icon_${s}x${s}@2x.png >/dev/null
  done
  iconutil -c icns /tmp/v2c.iconset -o icon.icns
fi

# --- Bundle bauen ---
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
[ -f icon.icns ] && cp icon.icns "$APP/Contents/Resources/icon.icns"

cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>voice2claude</string>
  <key>CFBundleDisplayName</key><string>voice2claude</string>
  <key>CFBundleIdentifier</key><string>com.tomschoen.voice2claude</string>
  <key>CFBundleVersion</key><string>2.0</string>
  <key>CFBundleShortVersionString</key><string>2.0</string>
  <key>CFBundleExecutable</key><string>voice2claude</string>
  <key>CFBundleIconFile</key><string>icon</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>LSUIElement</key><true/>
</dict></plist>
PLIST

# Launcher zeigt fest auf dieses Repo (Repo verschoben? make_app.sh erneut).
cat > "$APP/Contents/MacOS/voice2claude" <<LAUNCH
#!/bin/bash
cd "$REPO"
exec "$REPO/.venv/bin/python" "$REPO/menubar.py"
LAUNCH
chmod +x "$APP/Contents/MacOS/voice2claude"

xattr -dr com.apple.quarantine "$APP" 2>/dev/null || true
touch "$APP"  # Finder-Icon-Cache anstossen

echo "✓ Fertig: voice2claude.app  (mit Icon)"
echo "  Diese .app ist deine richtige App — zieh sie ins Dock / nach /Applications."

#!/usr/bin/env python3
"""voice2claude Menüleisten-App — der Start-Button.

Startet den Server automatisch im Hintergrund und zeigt ein 🎙️ in der
Menüleiste: Status, Bedienungshilfen-Guide, iPhone-QR, „Bei Login starten".
Als App:  ./make_app.sh  -> voice2claude.app doppelklicken.
Direkt:   .venv/bin/python menubar.py
"""
import os
import sys
import json
import socket
import subprocess
import urllib.request

import rumps

HERE = os.path.dirname(os.path.abspath(__file__))
PY = os.path.join(HERE, ".venv", "bin", "python")
if not os.path.exists(PY):
    PY = sys.executable
HISTORY = os.path.expanduser("~/.voice2claude/history.log")
LOGFILE = "/tmp/voice2claude.log"
APP_BUNDLE = os.path.join(HERE, "voice2claude.app")
LOGIN_TARGET = APP_BUNDLE if os.path.exists(APP_BUNDLE) else os.path.join(HERE, "voice2claude.command")


def env_value(key, default=None):
    p = os.path.join(HERE, ".env")
    if os.path.exists(p):
        for line in open(p):
            line = line.strip()
            if line and not line.startswith("#") and line.split("=", 1)[0].strip() == key:
                return line.split("=", 1)[1].split(" #", 1)[0].strip().strip('"').strip("'")
    return default


PORT = int(env_value("V2C_PORT", "8765"))
TOKEN = env_value("V2C_TOKEN") or ""
HAS_HTTPS = os.path.exists(os.path.join(HERE, "cert.pem"))


def osa(script):
    return subprocess.run(["osascript", "-e", script], capture_output=True, text=True).stdout.strip()


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80)); return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def best_host():
    name = subprocess.run(["scutil", "--get", "LocalHostName"], capture_output=True, text=True).stdout.strip()
    return f"{name}.local" if name else lan_ip()


def browser_url():
    host = best_host()
    url = f"https://{host}:{PORT + 1}/" if HAS_HTTPS else f"http://{host}:{PORT}/"
    return url + (f"?token={TOKEN}" if TOKEN else "")


def health():
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=1.2) as r:
            return json.load(r)
    except Exception:
        return None


def last_transcript():
    try:
        line = subprocess.run(["tail", "-n", "1", HISTORY], capture_output=True, text=True).stdout.strip()
        return (line.split("\t")[-1][:40] or "—") if line else "—"
    except Exception:
        return "—"


def login_item_present():
    return "voice2claude" in osa('tell application "System Events" to get the name of every login item')


class V2C(rumps.App):
    def __init__(self):
        super().__init__("🎙️", quit_button=None)
        self.proc = None
        self.m_state = rumps.MenuItem("Starte …")
        self.m_acc = rumps.MenuItem("Bedienungshilfen prüfen", callback=self.fix_access)
        self.m_last = rumps.MenuItem("Letztes Diktat: —")
        self.m_qr = rumps.MenuItem("📱  Auf iPhone öffnen (QR)", callback=self.show_qr)
        self.m_copy = rumps.MenuItem("🔗  iPhone-Link kopieren", callback=self.copy_url)
        self.m_browser = rumps.MenuItem("🖥  Im Browser öffnen", callback=self.open_browser)
        self.m_restart = rumps.MenuItem("↻  Server neu starten", callback=self.restart)
        self.m_login = rumps.MenuItem("Bei Anmeldung starten", callback=self.toggle_login)
        self.menu = [
            self.m_state, self.m_acc, self.m_last, None,
            self.m_qr, self.m_copy, self.m_browser, None,
            self.m_restart, self.m_login, None,
            rumps.MenuItem("Beenden", callback=self.quit_all),
        ]
        self.m_login.state = 1 if login_item_present() else 0
        # Auto-Start im Hintergrund:
        self.start()
        rumps.Timer(self.refresh, 2).start()

    # ---- Server-Lifecycle ----
    def start(self):
        if health():
            return  # laeuft bereits (evtl. extern) -> uebernehmen
        if self.proc and self.proc.poll() is None:
            return
        self.proc = subprocess.Popen([PY, "server.py"], cwd=HERE,
                                     stdout=open(LOGFILE, "w"), stderr=subprocess.STDOUT)

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
        self.proc = None

    def restart(self, _):
        self.stop()
        rumps.Timer(lambda _t: self.start(), 1).start()  # kurz warten, dann neu
        rumps.notification("voice2claude", "Server neu gestartet", browser_url())

    # ---- Aktionen ----
    def show_qr(self, _):
        if not health():
            rumps.alert("Server startet noch", "Gleich nochmal versuchen.")
            return
        subprocess.run(["open", f"http://127.0.0.1:{PORT}/qr"])

    def copy_url(self, _):
        subprocess.run(["pbcopy"], input=browser_url().encode())
        rumps.notification("voice2claude", "iPhone-Link kopiert", browser_url())

    def open_browser(self, _):
        subprocess.run(["open", browser_url()])

    def fix_access(self, _):
        if health() and health().get("accessibility"):
            rumps.alert("Bedienungshilfen: aktiv ✓", "Auto-Tippen funktioniert.")
            return
        rumps.alert(
            "Bedienungshilfen aktivieren",
            "Damit sich der Text selbst tippt, im gleich geöffneten Fenster\n"
            "voice2claude (bzw. dein Terminal) einschalten:\n\n"
            "Datenschutz & Sicherheit → Bedienungshilfen → Schalter AN.\n\n"
            "Ohne Freigabe landet der Text in der Zwischenablage (⌘V).")
        subprocess.run(["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"])

    def toggle_login(self, sender):
        if sender.state:
            osa('tell application "System Events" to delete login item "voice2claude"')
            sender.state = 0
        else:
            osa(f'tell application "System Events" to make login item at end '
                f'with properties {{path:"{LOGIN_TARGET}", hidden:true}}')
            sender.state = 1

    def quit_all(self, _):
        self.stop()
        rumps.quit_application()

    # ---- Status-Refresh ----
    def refresh(self, _):
        h = health()
        if h:
            self.title = "🎙️"
            self.m_state.title = f"●  Läuft — {best_host()}:{PORT}"
            self.m_acc.title = ("Bedienungshilfen: aktiv ✓" if h.get("accessibility")
                                else "⚠️  Bedienungshilfen aktivieren …")
            self.m_last.title = "Letztes Diktat: " + last_transcript()
        else:
            self.title = "🎙️…"
            self.m_state.title = "○  Server startet …"
            self.m_acc.title = "Bedienungshilfen prüfen"
            self.m_last.title = "Letztes Diktat: —"
            self.start()  # falls abgestürzt: wieder hochfahren


if __name__ == "__main__":
    V2C().run()

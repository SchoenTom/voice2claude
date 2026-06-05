"""Injection-Backends + Fernbedienung: wie Text/Tasten in Claude landen.

Backends (wie Text eingefuegt wird):
  paste      Text -> Zwischenablage -> Cmd+V ins fokussierte Fenster. Geht auf
             jeder laufenden Session ohne Vorbereitung. Braucht Bedienungshilfen.
  tmux       tmux send-keys ins Ziel. Praezise, auch im Hintergrund.
  clipboard  Nur kopieren, du fuegst selbst ein. Null Berechtigungen.
  auto       (Default) tmux falls Ziel existiert, sonst paste.

Zusaetzlich: Fernbedienungstasten (Enter/Esc/Pfeile/Ctrl-C/...) via send_key().
Plus Helfer: frontmost_app(), is_terminal_frontmost(), accessibility_ok().
"""
import os
import shutil
import subprocess
import sys

# Bundle-IDs gaengiger Terminals — nur dahin darf paste/key automatisch tippen.
TERMINAL_BUNDLE_IDS = {
    "com.apple.Terminal",
    "com.googlecode.iterm2",
    "com.github.wez.wezterm",
    "com.mitchellh.ghostty",
    "dev.warp.Warp-Stable",
    "io.alacritty",
    "net.kovidgoyal.kitty",
    "com.microsoft.VSCode",        # integriertes Terminal
    "com.todesktop.230313mzl4w4u92",  # Cursor
}

# Fernbedienungs-Tasten: tmux-Namen fuer benannte Tasten (osascript laeuft ueber
# den allgemeinen Kombo-Parser unten, der beliebige Modifier unterstuetzt).
KEYS = {
    "enter":     {"tmux": "Enter"},
    "return":    {"tmux": "Enter"},
    "escape":    {"tmux": "Escape"},
    "esc":       {"tmux": "Escape"},
    "up":        {"tmux": "Up"},
    "down":      {"tmux": "Down"},
    "left":      {"tmux": "Left"},
    "right":     {"tmux": "Right"},
    "tab":       {"tmux": "Tab"},
    "shift-tab": {"tmux": "BTab"},
    "ctrl-c":    {"tmux": "C-c"},
    "space":     {"tmux": "Space"},
}

# Benannte Tasten -> macOS key code (fuer osascript).
KEYCODES = {
    "enter": 36, "return": 36, "escape": 53, "esc": 53,
    "up": 126, "down": 125, "left": 123, "right": 124,
    "tab": 48, "space": 49, "delete": 51, "backspace": 51, "forwarddelete": 117,
    "home": 115, "end": 119, "pageup": 116, "pagedown": 121,
}

# Modifier-Schreibweisen -> osascript-Token.
MODMAP = {
    "cmd": "command down", "command": "command down", "⌘": "command down",
    "shift": "shift down", "⇧": "shift down",
    "ctrl": "control down", "control": "control down", "⌃": "control down",
    "opt": "option down", "option": "option down", "alt": "option down", "⌥": "option down",
}


def build_osa_keyspec(spec: str):
    """Wandelt z.B. 'cmd+shift+]' / 'ctrl-c' / 'enter' / '1' in das
    osascript-Fragment nach 'tell application "System Events" to ...' um.
    -> str oder None bei ungueltiger Eingabe."""
    spec = spec.strip()
    # Legacy-Schreibweise mit Bindestrich (ctrl-c, shift-tab) -> Plus.
    if spec.lower() in ("ctrl-c", "shift-tab"):
        spec = spec.replace("-", "+")
    tokens = [t for t in spec.split("+") if t != ""]
    if not tokens:
        return None
    key = tokens[-1].strip()
    mods = []
    for t in tokens[:-1]:
        m = MODMAP.get(t.strip().lower())
        if not m:
            return None
        mods.append(m)
    kl = key.lower()
    if kl in KEYCODES:
        base = f"key code {KEYCODES[kl]}"
    elif len(key) == 1:
        esc = key.replace("\\", "\\\\").replace('"', '\\"')
        base = f'keystroke "{esc}"'
    else:
        return None
    using = f" using {{{', '.join(mods)}}}" if mods else ""
    return base + using


def _log(msg: str) -> None:
    print(f"[inject] {msg}", file=sys.stderr, flush=True)


def copy_to_clipboard(text: str) -> None:
    subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)


def _osascript(script: str) -> str:
    return subprocess.run(
        ["osascript", "-e", script], capture_output=True, text=True, check=True
    ).stdout.strip()


def _osa_run(script: str, timeout: float = 8.0):
    """osascript ohne Exception. -> (ok, stdout, stderr). Timeout verhindert,
    dass ein blockierender Berechtigungsdialog die Anfrage haengen laesst."""
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True,
                           text=True, timeout=timeout)
        return (r.returncode == 0, r.stdout.strip(), r.stderr.strip())
    except Exception as e:
        return (False, "", str(e))


# ---------------------------------------------------------------- Frontmost / Guard

_FRONT_INFO = '''tell application "System Events"
  set p to first process whose frontmost is true
  set nm to name of p
  set bid to ""
  try
    set bid to bundle identifier of p
  end try
  set wt to ""
  try
    set wt to title of front window of p
  end try
  return nm & linefeed & bid & linefeed & wt
end tell'''


def frontmost_info():
    """EIN osascript-Aufruf -> {app, bundle, title, accessibility}.
    Ersetzt die frueheren 4 Einzelaufrufe in /status (Tempo)."""
    ok, out, _err = _osa_run(_FRONT_INFO, timeout=4)
    if not ok:
        return {"app": None, "bundle": None, "title": None, "accessibility": False}
    parts = out.split("\n")
    return {
        "app": (parts[0] if len(parts) > 0 and parts[0] else None),
        "bundle": (parts[1] if len(parts) > 1 and parts[1] else None),
        "title": (parts[2] if len(parts) > 2 and parts[2] else None),
        "accessibility": True,
    }


def frontmost_app():
    """(name, bundle_id) der App im Vordergrund — nutzt frontmost_info (1 Aufruf)."""
    i = frontmost_info()
    return i["app"], i["bundle"]


def frontmost_window_title():
    try:
        return _osascript(
            'tell application "System Events" to get title of front window '
            'of (first process whose frontmost is true)'
        ) or None
    except Exception:
        return None


def is_terminal_frontmost() -> bool:
    _, bundle = frontmost_app()
    return bundle in TERMINAL_BUNDLE_IDS


def accessibility_ok() -> bool:
    """True, wenn Bedienungshilfen aktiv sind. Liest eine UI-Eigenschaft
    (Accessibility-pflichtig) OHNE einen Tastendruck zu senden."""
    try:
        _osascript(
            'tell application "System Events" to count '
            '(every window of (first process whose frontmost is true))'
        )
        return True
    except Exception:
        return False


# ---------------------------------------------------------------- Terminal-Sessions

_US = chr(31)  # Unit Separator als Feldtrenner (kommt in Fenstertiteln nicht vor)

# Liest Terminals "Fenster"-Menue ueber System Events (Bedienungshilfen) — listet
# ALLE Fenster ueber alle Spaces hinweg, ohne Terminal-Automation-Berechtigung.
_LIST_SESSIONS = '''tell application "System Events" to tell process "Terminal"
  set wm to menu "Window" of menu bar 1
  set ns to name of menu items of wm
  set ms to value of attribute "AXMenuItemMarkChar" of menu items of wm
end tell
set D to (ASCII character 31)
set out to ""
repeat with i from 1 to (count of ns)
  set nm to item i of ns
  if nm is not missing value and nm contains " — " then
    set mk to item i of ms
    set mc to "0"
    if mk is not missing value then set mc to (id of mk) as string
    set out to out & i & D & mc & D & nm & linefeed
  end if
end repeat
return out'''


def _clean_title(name: str) -> str:
    """'user — ✳ Title — claude … — 193×58' -> 'Title'."""
    parts = name.split(" — ")
    t = (parts[1] if len(parts) > 1 else name).strip()
    while t and not t[0].isalnum():   # fuehrende Spinner/Symbole weg
        t = t[1:]
    return t.strip() or name.strip()


def _session_state(name: str) -> str:
    """Claude Code schreibt seinen Status als fuehrendes Glyph in den Titel:
    Braille-Spinner = arbeitet, ✳ (Sparkle) = bereit/idle (wartet evtl. auf dich)."""
    parts = name.split(" — ")
    seg = (parts[1] if len(parts) > 1 else name).strip()
    if not seg:
        return "idle"
    c = ord(seg[0])
    if 0x2800 <= c <= 0x28FF:                               # Braille-Spinner
        return "working"
    if c in (0x2733, 0x2734, 0x2731, 0x2736, 0x2737, 0x2738):  # ✳ und Sparkle-Varianten
        return "ready"
    return "idle"


def list_terminal_sessions():
    """Alle Terminal-Fenster (Spaces-uebergreifend) via Fenster-Menue.
    -> (sessions, ok). ok=False, wenn System Events nicht lesbar ist
    (Bedienungshilfen aus)."""
    ok, raw, err = _osa_run(_LIST_SESSIONS)
    if not ok:
        _log(f"list_terminal_sessions: {err[:140]}")
        return [], False
    sessions = []
    for line in raw.splitlines():
        parts = line.split(_US)
        if len(parts) < 3:
            continue
        try:
            idx = int(parts[0])
        except ValueError:
            continue
        mark = parts[1]
        name = _US.join(parts[2:])
        sessions.append({
            "id": idx,
            "tab": 1,
            "front": (mark == "10003"),   # ✓ U+2713 = aktives Fenster
            "is_claude": ("claude" in name.lower()),
            "title": _clean_title(name),
            "state": _session_state(name),
        })
    return sessions, True


def select_terminal_session(win_id: int, tab: int = 1) -> bool:
    """Aktiviert das Fenster ueber Terminals Fenster-Menue (System Events) —
    wechselt bei Bedarf den Space. Kein Terminal-Automation noetig."""
    script = (
        'tell application "System Events" to tell process "Terminal"\n'
        '  set frontmost to true\n'
        f'  click menu item {int(win_id)} of menu "Window" of menu bar 1\n'
        'end tell'
    )
    ok, _out, err = _osa_run(script)
    if not ok:
        _log(f"select_terminal_session: {err[:140]}")
    return ok


# ---------------------------------------------------------------- Text-Injection

def inject_tmux(text: str, submit: bool, target: str) -> bool:
    try:
        subprocess.run(["tmux", "send-keys", "-t", target, "-l", text], check=True)
        if submit:
            subprocess.run(["tmux", "send-keys", "-t", target, "Enter"], check=True)
        return True
    except Exception as e:
        _log(f"tmux fehlgeschlagen ({target}): {e}")
        return False


def inject_paste(text: str, submit: bool, app: str | None = None) -> bool:
    try:
        copy_to_clipboard(text)
        steps = []
        if app:
            steps.append(f'tell application "{app}" to activate')
            steps.append("delay 0.15")
        steps.append('tell application "System Events"')
        steps.append('  keystroke "v" using command down')
        if submit:
            steps.append("  delay 0.12")
            steps.append("  key code 36")
        steps.append("end tell")
        _osascript("\n".join(steps))
        return True
    except Exception as e:
        _log(f"paste fehlgeschlagen: {e} — Text liegt in der Zwischenablage.")
        return False


def inject_clipboard(text: str, submit: bool, app: str | None = None) -> bool:
    try:
        copy_to_clipboard(text)
        return True
    except Exception as e:
        _log(f"clipboard fehlgeschlagen: {e}")
        return False


def paste_image(path: str, app: str | None = None) -> bool:
    """Bild -> PNG -> Zwischenablage -> Cmd+V ins fokussierte Fenster.
    Claude Code zeigt eingefuegte Bilder inline im Prompt."""
    png = path + ".v2c.png"
    try:
        # iPhone-Fotos sind oft HEIC/JPEG -> sips konvertiert zuverlaessig nach PNG
        subprocess.run(["sips", "-s", "format", "png", path, "--out", png],
                       capture_output=True, check=True)
        _osascript('set the clipboard to (read (POSIX file "%s") as «class PNGf»)' % png)
        steps = []
        if app:
            steps.append('tell application "%s" to activate' % app)
            steps.append("delay 0.15")
        steps.append('tell application "System Events" to keystroke "v" using command down')
        _osascript("\n".join(steps))
        return True
    except Exception as e:
        _log(f"paste_image fehlgeschlagen: {e}")
        return False
    finally:
        try:
            os.unlink(png)
        except OSError:
            pass


def tmux_target_exists(target: str) -> bool:
    if not target or not shutil.which("tmux"):
        return False
    try:
        sessions = subprocess.run(
            ["tmux", "list-panes", "-a", "-F", "#{session_name}"],
            capture_output=True, text=True, check=True,
        ).stdout.split()
        return target.split(":")[0] in sessions
    except Exception:
        return False


def resolve(mode: str, tmux_target: str, paste_app: str | None):
    """(backend_name, fn(text, submit) -> bool)."""
    mode = (mode or "auto").lower()
    if mode == "auto":
        if tmux_target_exists(tmux_target):
            return "tmux", lambda t, s: inject_tmux(t, s, tmux_target)
        return "paste", lambda t, s: inject_paste(t, s, paste_app)
    if mode == "tmux":
        return "tmux", lambda t, s: inject_tmux(t, s, tmux_target)
    if mode == "clipboard":
        return "clipboard", lambda t, s: inject_clipboard(t, s, paste_app)
    if mode != "paste":
        _log(f"unbekannter Modus '{mode}', nutze paste")
    return "paste", lambda t, s: inject_paste(t, s, paste_app)


# ---------------------------------------------------------------- Fernbedienung

def send_key_osascript(spec: str) -> bool:
    osa = build_osa_keyspec(spec)
    if osa is None:
        _log(f"unbekannte Taste/Kombo: {spec!r}")
        return False
    try:
        _osascript(f'tell application "System Events" to {osa}')
        return True
    except Exception as e:
        _log(f"send_key (osascript) fehlgeschlagen: {e}")
        return False


def send_key_tmux(spec: str, target: str) -> bool:
    spec = spec.strip().lower()
    # Cmd/Opt existieren in tmux nicht — solche Kombos gehoeren in den
    # frontmost-Modus (App-/Fensterebene), nicht in eine tmux-Pane.
    if any(spec.startswith(m + "+") for m in ("cmd", "command", "opt", "option", "alt")):
        _log(f"'{spec}' ist eine App-Kombo — im tmux-Modus nicht sendbar")
        return False
    if spec in KEYS:
        send = KEYS[spec]["tmux"]
    elif spec.startswith("ctrl+") and len(spec) == 6:
        send = "C-" + spec[-1]
    elif len(spec) == 1:
        send = None  # literal
    else:
        _log(f"unbekannte Taste: {spec!r}")
        return False
    try:
        if send is None:
            subprocess.run(["tmux", "send-keys", "-t", target, "-l", spec], check=True)
        else:
            subprocess.run(["tmux", "send-keys", "-t", target, send], check=True)
        return True
    except Exception as e:
        _log(f"send_key (tmux) fehlgeschlagen: {e}")
        return False


def resolve_key(mode: str, tmux_target: str):
    """(backend_name, fn(keyspec) -> bool) fuer die Fernbedienung."""
    mode = (mode or "auto").lower()
    if mode == "tmux" or (mode == "auto" and tmux_target_exists(tmux_target)):
        return "tmux", lambda k: send_key_tmux(k, tmux_target)
    return "frontmost", lambda k: send_key_osascript(k)

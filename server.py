#!/usr/bin/env python3
"""voice2claude — dein Handy als Diktiergeraet UND Fernbedienung fuer Claude Code.

- POST /transcribe : Audio -> faster-whisper (lokal) -> Text in die Session
- POST /type       : fertigen Text einfuegen (Canned Prompts)
- POST /key        : eine Taste senden (Enter/Esc/Pfeile/Ctrl-C/Ziffern ...)
- GET  /status     : was ist im Vordergrund? Bedienungshilfen ok? Ziel?
- GET  /health     : Kurzstatus

Konfiguration ueber .env / Umgebungsvariablen (siehe .env.example):
  V2C_MODEL V2C_INJECT V2C_TMUX V2C_APP V2C_LANG V2C_PORT V2C_PROMPT
  V2C_TOKEN (optional: schuetzt schreibende Endpoints) V2C_SOUND (1=Bestaetigungston)
  V2C_GUARD (1=nur in Terminals tippen, sonst Clipboard-Fallback)
"""
import os
import sys
import socket
import tempfile
import datetime
import subprocess
from functools import wraps

from flask import Flask, request, send_from_directory, jsonify, Response

import inject

HERE = os.path.dirname(os.path.abspath(__file__))
HISTORY = os.path.expanduser("~/.voice2claude/history.log")

# .env optional einlesen (ohne Zusatzpaket)
_envfile = os.path.join(HERE, ".env")
if os.path.exists(_envfile):
    for _line in open(_envfile):
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _v = _line.split("=", 1)
        _v = _v.split(" #", 1)[0].strip().strip('"').strip("'")
        os.environ.setdefault(_k.strip(), _v)

MODEL_SIZE = os.environ.get("V2C_MODEL", "small")
INJECT_MODE = os.environ.get("V2C_INJECT", "auto")
TMUX_TARGET = os.environ.get("V2C_TMUX", "claude")
PASTE_APP = os.environ.get("V2C_APP") or None
LANG = os.environ.get("V2C_LANG") or None
PORT = int(os.environ.get("V2C_PORT", "8765"))
TOKEN = os.environ.get("V2C_TOKEN") or None
SOUND = os.environ.get("V2C_SOUND", "0") == "1"
GUARD = os.environ.get("V2C_GUARD", "1") == "1"
PROMPT = os.environ.get(
    "V2C_PROMPT",
    "Claude, Python, git, commit, Funktion, Terminal, Bug, Code, bash, Flask.",
) or None

app = Flask(__name__, static_folder=os.path.join(HERE, "static"))

print(f"[voice2claude] Lade Whisper-Modell '{MODEL_SIZE}' ...", flush=True)
from faster_whisper import WhisperModel  # noqa: E402
model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
print("[voice2claude] Modell bereit.", flush=True)


def lan_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def local_hostname() -> str | None:
    """Stabiler .local-Name (Bonjour) — vom iPhone erreichbar, IP-unabhaengig."""
    try:
        name = subprocess.run(["scutil", "--get", "LocalHostName"],
                              capture_output=True, text=True).stdout.strip()
        return f"{name}.local" if name else None
    except Exception:
        return None


def best_host() -> str:
    return local_hostname() or lan_ip()


def ding():
    if SOUND:
        try:
            subprocess.Popen(["afplay", "/System/Library/Sounds/Tink.aiff"])
        except Exception:
            pass


def log_history(kind: str, text: str):
    try:
        os.makedirs(os.path.dirname(HISTORY), exist_ok=True)
        ts = datetime.datetime.now().isoformat(timespec="seconds")
        with open(HISTORY, "a") as f:
            f.write(f"{ts}\t{kind}\t{text}\n")
    except Exception:
        pass


def require_token(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if TOKEN:
            given = request.args.get("token") or request.headers.get("X-Token")
            if given != TOKEN:
                return jsonify(error="unauthorized"), 401
        return fn(*a, **kw)
    return wrapper


def do_inject(text: str, submit: bool):
    """Fuegt Text ein und beachtet den Safety-Guard. -> (backend, sent)."""
    backend, fn = inject.resolve(INJECT_MODE, TMUX_TARGET, PASTE_APP)
    # Guard: paste tippt ins fokussierte Fenster — nur wenn das ein Terminal ist.
    if GUARD and backend == "paste" and not inject.is_terminal_frontmost():
        inject.copy_to_clipboard(text)
        return "clipboard_fallback", False
    sent = fn(text, submit)
    if sent:
        ding()
    return backend, sent


# --------------------------------------------------------------------- Routes

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


def browser_url():
    has_https = os.path.exists(os.path.join(HERE, "cert.pem"))
    host = best_host()
    url = f"https://{host}:{PORT + 1}/" if has_https else f"http://{host}:{PORT}/"
    return url + (f"?token={TOKEN}" if TOKEN else "")


@app.route("/qr")
def qr_page():
    """Vollbild-QR der Browser-URL — Handy-Kamera drauf, fertig."""
    url = browser_url()
    svg = ""
    try:
        import io
        import qrcode
        import qrcode.image.svg
        img = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, box_size=12, border=2)
        buf = io.BytesIO(); img.save(buf)
        svg = buf.getvalue().decode()
    except Exception as e:
        svg = f"<p>QR nicht verfügbar: {e}</p>"
    html = f"""<!doctype html><html lang=de><head><meta charset=utf-8>
<meta name=viewport content="width=device-width, initial-scale=1">
<title>voice2claude — verbinden</title>
<style>
  :root{{ --bg:#0c0e12; --bg2:#0f1318; --ink:#ECEEF2; --dim:#8A8F98; --faint:#5b616c;
    --glass:rgba(255,255,255,.045); --line:rgba(255,255,255,.09); --iris:#7C8CF8; --green:#5BD6A0;
    --serif:ui-serif,"New York",Georgia,serif; --sans:-apple-system,system-ui,sans-serif; }}
  *{{ box-sizing:border-box; margin:0; }}
  body{{ min-height:100dvh; color:var(--ink); font-family:var(--sans);
    background:radial-gradient(120% 60% at 50% -8%, rgba(124,140,248,.12), transparent 60%),
      linear-gradient(180deg,var(--bg2),var(--bg) 32%); background-attachment:fixed;
    display:flex; flex-direction:column; align-items:center; justify-content:center; gap:26px; padding:32px; }}
  body::after{{ content:""; position:fixed; inset:0; pointer-events:none; opacity:.03;
    background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='140' height='140'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E"); }}
  .reveal{{ opacity:0; transform:translateY(12px); animation:rise .7s cubic-bezier(.2,.7,.2,1) forwards; }}
  @keyframes rise{{ to{{ opacity:1; transform:none; }} }}
  .brand{{ font-family:var(--serif); font-size:30px; font-weight:600; letter-spacing:.3px; }}
  .brand .v{{ color:var(--iris); }}
  .tag{{ font-family:var(--serif); font-style:italic; font-size:16px; color:var(--dim); margin-top:6px; }}
  .card{{ background:var(--glass); border:1px solid var(--line); border-radius:30px; padding:26px;
    backdrop-filter:blur(22px); box-shadow:0 30px 80px rgba(0,0,0,.45); }}
  .qframe{{ background:#fff; border-radius:20px; padding:18px; box-shadow:0 0 0 8px rgba(124,140,248,.10);
    display:grid; place-items:center; }}
  .qframe svg{{ width:min(62vw,290px); height:min(62vw,290px); display:block; }}
  .scan{{ display:flex; align-items:center; gap:9px; justify-content:center; margin-top:18px; color:var(--ink); font-size:15px; font-weight:600; }}
  .scan .pulse{{ width:9px; height:9px; border-radius:50%; background:var(--green); box-shadow:0 0 12px var(--green); animation:bl 1.6s infinite; }}
  @keyframes bl{{ 50%{{ opacity:.3; }} }}
  .url{{ font-size:13px; color:var(--iris); word-break:break-all; text-align:center; max-width:320px; }}
  .foot{{ font-size:12px; color:var(--faint); display:flex; gap:14px; }}
  .foot b{{ color:var(--dim); font-weight:600; }}
</style></head><body>
  <div class=reveal style="text-align:center">
    <div class=brand><span class=v>voice</span>2claude</div>
    <div class=tag>Sprich. Steuere. Verbinde.</div>
  </div>
  <div class="card reveal" style="animation-delay:.08s">
    <div class=qframe>{svg}</div>
    <div class=scan><span class=pulse></span>Mit der iPhone-Kamera scannen</div>
  </div>
  <a class="url reveal" style="animation-delay:.16s" href="{url}">{url}</a>
  <div class="foot reveal" style="animation-delay:.24s"><span><b>Lokal</b></span><span><b>Privat</b></span><span>Audio bleibt auf deinem Mac</span></div>
</body></html>"""
    return Response(html, mimetype="text/html")


@app.route("/health")
def health():
    backend, _ = inject.resolve(INJECT_MODE, TMUX_TARGET, PASTE_APP)
    return jsonify(ok=True, model=MODEL_SIZE, inject=INJECT_MODE,
                   backend=backend, accessibility=inject.accessibility_ok())


@app.route("/status")
def status():
    info = inject.frontmost_info()
    backend, _ = inject.resolve(INJECT_MODE, TMUX_TARGET, PASTE_APP)
    return jsonify(
        ip=lan_ip(),
        frontmost={"app": info["app"], "title": info["title"]},
        is_terminal=(info["bundle"] in inject.TERMINAL_BUNDLE_IDS),
        accessibility=info["accessibility"],
        backend=backend, inject=INJECT_MODE, tmux=TMUX_TARGET,
    )


@app.route("/sessions")
@require_token
def sessions():
    items, authorized = inject.list_terminal_sessions()
    return jsonify(sessions=items, needs_automation=not authorized)


@app.route("/select", methods=["POST"])
@require_token
def select():
    data = request.get_json(silent=True) or request.form
    try:
        wid = int(data.get("id"))
    except (TypeError, ValueError):
        return jsonify(error="id fehlt"), 400
    tab = int(data.get("tab", 1) or 1)
    ok = inject.select_terminal_session(wid, tab)
    log_history("select", str(wid))
    return jsonify(ok=ok)


@app.route("/transcribe", methods=["POST"])
@require_token
def transcribe():
    if "audio" not in request.files:
        return jsonify(error="kein 'audio'-Feld im Request"), 400
    submit = request.args.get("send", "1") != "0"

    f = request.files["audio"]
    suffix = os.path.splitext(f.filename or "")[1] or ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        f.save(tmp.name)
        path = tmp.name
    try:
        segments, info = model.transcribe(
            path, language=LANG, vad_filter=True, initial_prompt=PROMPT
        )
        text = "".join(s.text for s in segments).strip()
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass

    print(f"[voice2claude] ({info.language}) {text!r}", flush=True)
    # Leere / Mini-Clips (Fehlauslösung, Rauschen) nicht einfuegen.
    if len(text) < 2:
        return jsonify(text="", sent=False, backend=None, lang=info.language, empty=True)

    log_history("voice", text)
    # inject=0 -> nur transkribieren (Review-Modus: erst zeigen, dann /type)
    if request.args.get("inject", "1") == "0":
        return jsonify(text=text, sent=False, backend=None, lang=info.language, injected=False)
    backend, sent = do_inject(text, submit)
    return jsonify(text=text, sent=sent, backend=backend, lang=info.language)


@app.route("/type", methods=["POST"])
@require_token
def type_text():
    data = request.get_json(silent=True) or request.form
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify(error="kein Text"), 400
    submit = str(data.get("send", "1")) != "0"
    log_history("type", text)
    backend, sent = do_inject(text, submit)
    return jsonify(text=text, sent=sent, backend=backend)


# Navigations-Tasten wechseln absichtlich Apps/Spaces/Fenster -> kein Guard,
# sonst kommt man nach dem Wegwechseln nicht zurueck.
NAV_KEYS = {"ctrl+left", "ctrl+right", "ctrl+up", "ctrl+down", "cmd+`"}


@app.route("/key", methods=["POST"])
@require_token
def key():
    data = request.get_json(silent=True) or request.form
    spec = (data.get("key") or "").strip()
    if not spec:
        return jsonify(error="keine Taste"), 400
    is_nav = spec.lower() in NAV_KEYS
    backend, fn = inject.resolve_key(INJECT_MODE, TMUX_TARGET)
    if GUARD and not is_nav and backend == "frontmost" and not inject.is_terminal_frontmost():
        return jsonify(error="kein Terminal im Vordergrund", sent=False), 409
    sent = fn(spec)
    if sent:
        ding()
    log_history("key", spec)
    return jsonify(key=spec, sent=sent, backend=backend)


# --------------------------------------------------------------------- Serve

def banner():
    cert = os.path.join(HERE, "cert.pem")
    key_ = os.path.join(HERE, "key.pem")
    use_https = os.path.exists(cert) and os.path.exists(key_)
    host = best_host()
    ip = lan_ip()
    https_port = PORT + 1
    backend, _ = inject.resolve(INJECT_MODE, TMUX_TARGET, PASTE_APP)
    acc = inject.accessibility_ok()
    print("\n" + "=" * 60)
    print("  voice2claude laeuft")
    print("-" * 60)
    print(f"  iPhone-Shortcut  ->  http://{host}:{PORT}/transcribe")
    if use_https:
        print(f"  Browser/Remote   ->  https://{host}:{https_port}/")
    else:
        print(f"  Browser/Remote   ->  http://{host}:{PORT}/  (Mikrofon braucht HTTPS!)")
    if host != ip:
        print(f"  (Fallback per IP ->  http://{ip}:{PORT}/ )")
    print(f"  Injection        ->  {INJECT_MODE}  (aktiv: {backend})")
    print(f"  Bedienungshilfen ->  {'OK' if acc else 'NICHT GRANT — Auto-Tippen geht nicht'}")
    if TOKEN:
        print(f"  Token            ->  aktiv (an URL haengen: ?token=...)")
    try:
        import qrcode
        url = (f"https://{host}:{https_port}/" if use_https else f"http://{host}:{PORT}/")
        if TOKEN:
            url += f"?token={TOKEN}"
        qr = qrcode.QRCode(border=1)
        qr.add_data(url)
        qr.make()
        print("-" * 60)
        print("  Browser/Remote per QR (Handy-Kamera drauf halten):")
        qr.print_ascii(invert=True)
    except Exception:
        pass
    print("=" * 60 + "\n", flush=True)
    return (cert, key_) if use_https else None, https_port


def _serve(host, port, ssl_context):
    from werkzeug.serving import make_server
    make_server(host, port, app, threaded=True, ssl_context=ssl_context).serve_forever()


if __name__ == "__main__":
    import threading
    ssl_context, https_port = banner()
    threading.Thread(target=_serve, args=("0.0.0.0", PORT, None), daemon=True).start()
    if ssl_context:
        threading.Thread(target=_serve, args=("0.0.0.0", https_port, ssl_context), daemon=True).start()
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        print("\n[voice2claude] beendet.", flush=True)

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
<meta name=viewport content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#050810">
<title>voice2claude — verbinden</title>
<style>
  :root{{ --void:#050810; --ink:#f0f4ff; --dim:#8ba4c8; --faint:#4a6080; --teal:#00c6ff; }}
  *{{ box-sizing:border-box; margin:0; -webkit-tap-highlight-color:transparent; }}
  body{{ min-height:100dvh; color:var(--ink); font-family:-apple-system,system-ui,sans-serif;
    background:var(--void); overflow:hidden;
    display:flex; flex-direction:column; align-items:center; justify-content:center; gap:30px; padding:32px; }}
  body::before{{ content:""; position:fixed; inset:0; z-index:0; pointer-events:none;
    background:
      radial-gradient(ellipse 80% 60% at 20% 10%, rgba(13,74,110,.55), transparent 60%),
      radial-gradient(ellipse 60% 80% at 80% 0%, rgba(168,85,247,.30), transparent 50%),
      radial-gradient(ellipse 100% 40% at 50% 100%, rgba(26,10,62,.70), transparent 60%),
      radial-gradient(ellipse 70% 50% at 10% 80%, rgba(16,217,142,.15), transparent 50%);
    animation:shift 18s ease-in-out infinite alternate; }}
  @keyframes shift{{ 0%{{transform:scale(1) translate(0,0)}} 50%{{transform:scale(1.05) translate(10px,-8px)}} 100%{{transform:scale(1.02) translate(-6px,8px)}} }}
  .reveal{{ position:relative; z-index:1; opacity:0; transform:translateY(14px); animation:rise .8s cubic-bezier(.2,.7,.2,1) forwards; }}
  @keyframes rise{{ to{{ opacity:1; transform:none; }} }}
  .brand{{ text-align:center; font-size:14px; font-weight:600; letter-spacing:.1em; text-transform:lowercase; color:var(--dim); }}
  .brand .v{{ color:var(--teal); text-shadow:0 0 16px rgba(0,198,255,.8); }}
  .tag{{ text-align:center; font-size:24px; font-weight:600; letter-spacing:.2px; margin-top:8px;
    background:linear-gradient(90deg,#fff,#bfe9ff); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }}
  .qwrap{{ position:relative; z-index:1; opacity:0; transform:translateY(14px); animation:rise .8s cubic-bezier(.2,.7,.2,1) .1s forwards; }}
  .glowring{{ position:absolute; inset:-14px; border-radius:36px; background:transparent;
    box-shadow:0 0 0 1px rgba(0,198,255,.25), 0 0 50px rgba(0,198,255,.30), 0 0 110px rgba(0,144,200,.18);
    animation:breathe 3.4s ease-in-out infinite; }}
  @keyframes breathe{{ 0%,100%{{ box-shadow:0 0 0 1px rgba(0,198,255,.2), 0 0 40px rgba(0,198,255,.22), 0 0 90px rgba(0,144,200,.12); }}
    50%{{ box-shadow:0 0 0 1px rgba(0,198,255,.4), 0 0 70px rgba(0,198,255,.45), 0 0 140px rgba(0,144,200,.25); }} }}
  .qframe{{ position:relative; background:#fff; border-radius:26px; padding:20px; display:grid; place-items:center; }}
  .qframe svg{{ width:min(64vw,300px); height:min(64vw,300px); display:block; }}
  .scan{{ display:flex; align-items:center; gap:10px; justify-content:center; margin-top:22px; color:var(--ink); font-size:15px; font-weight:600; }}
  .scan .pulse{{ width:9px; height:9px; border-radius:50%; background:var(--teal); box-shadow:0 0 12px var(--teal); animation:bl 1.6s infinite; }}
  @keyframes bl{{ 50%{{ opacity:.3; transform:scale(.8); }} }}
  .url{{ font-size:13px; color:var(--teal); word-break:break-all; text-align:center; max-width:320px; opacity:.85; }}
  .foot{{ font-size:12px; color:var(--faint); display:flex; gap:16px; align-items:center; }}
  .foot b{{ color:var(--dim); font-weight:600; }} .foot .d{{ width:3px; height:3px; border-radius:50%; background:var(--faint); }}
</style></head><body>
  <div class=reveal>
    <div class=brand>voice<span class=v>2claude</span></div>
    <div class=tag>Sprich. Steuere. Verbinde.</div>
  </div>
  <div class=qwrap>
    <div class=glowring></div>
    <div class=qframe>{svg}</div>
    <div class=scan><span class=pulse></span>Mit der iPhone-Kamera scannen</div>
  </div>
  <a class="url reveal" style="animation-delay:.18s" href="{url}">{url}</a>
  <div class="foot reveal" style="animation-delay:.26s"><b>Lokal</b><span class=d></span><b>Privat</b><span class=d></span><span>Audio bleibt auf deinem Mac</span></div>
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
    # Sprache pro Diktat ueberschreibbar: ?lang=de|en|auto (auto = Whisper erkennt selbst)
    req_lang = request.args.get("lang")
    language = None if req_lang == "auto" else (req_lang or LANG)
    try:
        segments, info = model.transcribe(
            path, language=language, vad_filter=True, initial_prompt=PROMPT
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


@app.route("/transcribe-url", methods=["POST"])
@require_token
def transcribe_url():
    """URL (Instagram-Reel / YouTube / TikTok / ...) -> Audio -> Text.

    Latenz-Trick (KISS): nutzt das EINE bereits warme Whisper-Modell (kein Reload)
    und feedet die heruntergeladene Audiospur DIREKT in faster-whisper (kein
    mp3-Re-Encode). Damit ist nur der Download netz-gebunden, die Transkription
    selbst ist sofort. Default = Review (Text zurueck, nicht injizieren).
    """
    data = request.get_json(silent=True) or request.form
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify(error="keine URL"), 400
    req_lang = data.get("lang")
    language = None if req_lang == "auto" else (req_lang or LANG)
    do_send = str(data.get("send", "0")) != "0"
    do_push = str(data.get("inject", "0")) != "0"   # default: nur Text zurueck

    try:
        import yt_dlp
    except Exception:
        return jsonify(error="yt-dlp fehlt — pip install yt-dlp"), 500

    import glob as _glob
    import shutil as _shutil
    tmpdir = tempfile.mkdtemp(prefix="v2c_url_")
    try:
        opts = {
            "format": "bestaudio/best",
            "outtmpl": os.path.join(tmpdir, "a.%(ext)s"),
            "quiet": True, "no_warnings": True,
        }
        cookies = os.environ.get("V2C_COOKIES")   # 'safari'/'chrome'/... fuer Login-Walls
        if cookies:
            opts["cookiesfrombrowser"] = (cookies,)
        with yt_dlp.YoutubeDL(opts) as ydl:
            meta = ydl.extract_info(url, download=True)
        files = _glob.glob(os.path.join(tmpdir, "a.*"))
        if not files:
            return jsonify(error="Download fehlgeschlagen"), 502
        # WICHTIG: kein Re-Encode — faster-whisper dekodiert direkt via ffmpeg.
        segments, winfo = model.transcribe(
            files[0], language=language, vad_filter=True, initial_prompt=PROMPT
        )
        text = "".join(s.text for s in segments).strip()
    except Exception as e:
        return jsonify(error=f"{type(e).__name__}: {e}"), 500
    finally:
        _shutil.rmtree(tmpdir, ignore_errors=True)

    title = (meta.get("title") or meta.get("uploader") or "").strip()
    print(f"[voice2claude] url ({winfo.language}) {text!r}", flush=True)
    if len(text) < 2:
        return jsonify(text="", sent=False, empty=True, lang=winfo.language, title=title)
    log_history("url", f"{url} -> {text[:80]}")
    if not do_push:
        return jsonify(text=text, sent=False, backend=None,
                       lang=winfo.language, title=title, injected=False)
    backend, sent = do_inject(text, do_send)
    return jsonify(text=text, sent=sent, backend=backend, lang=winfo.language, title=title)


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


@app.route("/image", methods=["POST"])
@require_token
def image():
    if "image" not in request.files:
        return jsonify(error="kein 'image'-Feld"), 400
    f = request.files["image"]
    suffix = os.path.splitext(f.filename or "")[1] or ".jpg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        f.save(tmp.name)
        path = tmp.name
    try:
        # Bild-Paste geht nur ins fokussierte Fenster (Cmd+V) -> Terminal-Guard.
        if GUARD and not inject.is_terminal_frontmost():
            return jsonify(sent=False, error="kein Terminal vorne")
        ok = inject.paste_image(path, PASTE_APP)
        if ok:
            ding()
            log_history("image", f.filename or "image")
        return jsonify(sent=ok)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


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

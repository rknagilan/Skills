"""Shared paths, config, logging and helpers for MontClipper."""
import json, os, re, subprocess, threading, time, shutil, datetime, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # the engine (code, fonts)

def _home():
    """Where clips, recordings, settings and models live (easy for the user to find)."""
    if os.environ.get("MONTCLIPPER_HOME"):
        return Path(os.environ["MONTCLIPPER_HOME"]).expanduser()
    if (ROOT / "Upload to Socials").exists():               # engine and data in one folder
        return ROOT
    return Path.home() / "MontClipper"

HOME = _home()
MODELS = HOME / "models"
CLIPS = HOME / "Upload to Socials"
CHANNELS = HOME / "channels"
CACHE = HOME / "Recordings (auto-deleted)"   # temporary stream recordings, deleted automatically
IS_WIN = os.name == "nt"
AUDIO_PY = HOME / "tools-audio" / ("Scripts/python.exe" if IS_WIN else "bin/python")
PRO = (ROOT / "montclipper" / "phone.py").exists()      # phone delivery, Twitch viewer clips, several streamers
LIVE = (ROOT / "montclipper" / "live.py").exists()      # live clipping (Pro); Lite clips finished streams only
LITE_MAX_CLIPS = 5
SECRETS = Path.home() / ".config" / "montclipper" / "secrets.json"
WHISPER_MODEL = MODELS / "ggml-large-v3-turbo-q5_0.bin"
FONT_BOLD = "C:/Windows/Fonts/ariblk.ttf" if IS_WIN else "/System/Library/Fonts/Supplemental/Arial Black.ttf"
FONT_IMPACT = "C:/Windows/Fonts/impact.ttf" if IS_WIN else "/System/Library/Fonts/Supplemental/Impact.ttf"

def exe(name):
    """Full path of a program (Windows needs it for .cmd/.exe launchers). MontClipper's own bin folder first."""
    for p in (HOME / "bin" / "whisper" / "Release" / f"{name}.exe", HOME / "bin" / name, HOME / "bin" / f"{name}.exe"):
        if p.is_file():
            return str(p)
    return shutil.which(name) or name

def detach():
    """Popen/run options so Ctrl+C on MontClipper doesn't kill a helper halfway (a send, a final encode)."""
    if IS_WIN:
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}

def open_path(p):
    """Open a file, folder or web link the way the user would by double-clicking."""
    p = str(p)
    if IS_WIN:
        os.startfile(p)
    elif sys.platform == "darwin":
        subprocess.run(["open", p])
    else:
        subprocess.run(["xdg-open", p])

DEFAULTS = {
    "quality": "1080p60,1080p,936p60,720p60,720p,best",
    "segment_seconds": 20,
    "buffer_minutes": 40,          # rolling recording kept on disk while live
    "warmup_seconds": 120,         # ignore triggers right after go-live
    "chat_ratio": 2.6,             # bucket score vs rolling baseline
    "chat_min_unique": 6,          # minimum distinct chatters in a 10 s bucket
    "audio_jump_db": 9.0,          # loudness jump over rolling median
    "merge_seconds": 45,           # candidates closer than this merge
    "sweep_seconds": 120,          # how often Claude reads the transcript
    "judge_model": "sonnet",
    "sweep_model": "sonnet",
    "min_score": 62,               # judge score needed to render
    "music": "label",              # label: detect music and say "remove it in CapCut" | remove: also try to take it out (slower) | keep: no check
    "clip_min": 15, "clip_max": 75,
    "lookback": 75, "lookahead": 30,
    "vertical": True, "wide": True,
    "use_claude": True,            # use the AI (Claude Code or Codex) to find and judge moments
    "agent": "auto",               # auto | claude | codex: which AI judges the moments
    "codex_model": "",             # empty = your Codex default model
    "max_parallel_renders": 2,
    "brand": "none",               # your clips channel name, e.g. "ClipOga": a small mark with it on 9:16
    "kicker": "STREAM CLIPS",
    "end_pill": True,
    "youtube_browser": "",         # e.g. "chrome" or "safari": use that browser's YouTube login if YouTube asks to sign in              # orange FOLLOW <streamer> pill in the last 2.5 s
}

def load_config():
    cfg = dict(DEFAULTS)
    p = HOME / "config.json"
    if p.exists():
        cfg.update(json.loads(p.read_text()))
    return cfg

def load_secrets():
    if SECRETS.exists():
        try:
            return json.loads(SECRETS.read_text())
        except Exception:
            return {}
    return {}

WHISPER_LOCK = threading.Semaphore(1)
CLAUDE_LOCK = threading.Semaphore(2)
RENDER_LOCK = threading.Semaphore(2)
_print_lock = threading.Lock()

def log(tag, *msg):
    s = f"[{datetime.datetime.now():%H:%M:%S}] [{tag}] " + " ".join(str(m) for m in msg)
    with _print_lock:
        print(s, flush=True)

def ytdlp_auth():
    b = load_config().get("youtube_browser")
    return ["--cookies-from-browser", b] if b else []

PROTECT = threading.local()   # set while a clip renders: its helpers ignore Ctrl+C

def run(cmd, check=True, capture=True, timeout=None, **kw):
    if cmd and cmd[0] == "yt-dlp":
        cmd = cmd[:1] + ytdlp_auth() + cmd[1:]
    if cmd:
        cmd = [exe(cmd[0])] + list(cmd[1:])
    if getattr(PROTECT, "on", False):
        kw = {**detach(), **kw}   # a clip being made finishes even if the user presses Ctrl+C
    r = subprocess.run(cmd, capture_output=capture, text=True, timeout=timeout, **kw)
    if check and r.returncode != 0 and "not a bot" in (r.stderr or ""):
        raise RuntimeError("YouTube is asking to sign in (too many downloads). Fix: tell Claude "
                           "'MontClipper, use my Chrome YouTube login' (or Safari), or try again in an hour.")
    if check and r.returncode != 0:
        raise RuntimeError(f"{cmd[0]} failed ({r.returncode}): {(r.stderr or '')[-800:]}")
    return r

def append_jsonl(path, obj):
    with open(path, "a") as f:
        f.write(json.dumps(obj) + "\n")

def read_jsonl(path):
    out = []
    if not Path(path).exists():
        return out
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except Exception:
                    pass
    return out

def slug(s, n=50):
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s or "").strip("-").lower()
    return s[:n] or "clip"

def fmt_t(sec):
    sec = max(0, int(sec))
    return f"{sec//3600:d}:{sec%3600//60:02d}:{sec%60:02d}"

def parse_source(url):
    """Return (platform, channel_or_id, normalized_url)."""
    u = url.strip()
    if not u.startswith("http"):
        if "/" in u:
            u = "https://" + u
        else:
            u = "https://twitch.tv/" + u
    m = re.search(r"twitch\.tv/videos/(\d+)", u)
    if m:
        return "twitch_vod", m.group(1), u
    m = re.search(r"twitch\.tv/([A-Za-z0-9_]+)", u)
    if m:
        return "twitch", m.group(1).lower(), f"https://twitch.tv/{m.group(1).lower()}"
    if "youtube.com" in u or "youtu.be" in u:
        return "youtube", u, u
    if "kick.com" in u:
        m = re.search(r"kick\.com/([A-Za-z0-9_\-]+)", u)
        return "kick", (m.group(1) if m else u), u
    return "other", u, u

def channel_file(name):
    CHANNELS.mkdir(parents=True, exist_ok=True)
    return CHANNELS / f"{slug(name, 80)}.json"

def channel_get(name):
    p = channel_file(name)
    return json.loads(p.read_text()) if p.exists() else {}

def channel_set(name, **kv):
    d = channel_get(name)
    d.update(kv)
    channel_file(name).write_text(json.dumps(d, indent=2))

def extract_json(text):
    """Pull the first JSON object/array out of model text."""
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        text = m.group(1)
    for opener, closer in (("{", "}"), ("[", "]")):
        i = text.find(opener)
        j = text.rfind(closer)
        if i != -1 and j > i:
            try:
                return json.loads(text[i:j + 1])
            except Exception:
                continue
    raise ValueError("no JSON in model output: " + text[:300])

def agent():
    """Which AI does the judging: "claude" (Claude Code) or "codex" (OpenAI Codex).
    config "agent" or $MONTCLIPPER_AGENT can force one; "auto" uses the one MontClipper was started from,
    else whichever is installed."""
    a = (os.environ.get("MONTCLIPPER_AGENT") or load_config().get("agent") or "auto").strip().lower()
    if a in ("claude", "codex"):
        return a
    has = lambda n: exe(n) != n
    if os.environ.get("CODEX_THREAD_ID") and has("codex"):
        return "codex"
    if os.environ.get("CLAUDECODE") and has("claude"):
        return "claude"
    return "claude" if has("claude") or not has("codex") else "codex"

def claude(prompt, model="sonnet", read_dir=None, timeout=240):
    """Headless AI call (Claude Code, or Codex when that is the agent). Returns the result text."""
    if agent() == "codex":
        return codex(prompt, read_dir=read_dir, timeout=max(timeout, 420))
    cmd = ["claude", "-p", "--model", model, "--strict-mcp-config", "--disable-slash-commands",
           "--no-session-persistence", "--setting-sources", "", "--output-format", "json"]
    if read_dir:
        cmd += ["--tools", "Read", "--allowedTools", "Read", "--add-dir", str(read_dir)]
    else:
        cmd += ["--tools", ""]
    CACHE.mkdir(parents=True, exist_ok=True)
    cmd = [exe(cmd[0])] + cmd[1:]
    with CLAUDE_LOCK:
        r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=timeout,
                           cwd=str(read_dir or CACHE))
    if r.returncode != 0:
        raise RuntimeError("claude failed: " + (r.stderr or r.stdout)[-500:])
    d = json.loads(r.stdout)
    if d.get("is_error"):
        raise RuntimeError("claude error: " + str(d.get("result"))[:300])
    return d.get("result", "")

def codex(prompt, read_dir=None, timeout=420):
    """Headless Codex call: the images the prompt names are attached, nothing can be changed (read-only)."""
    import re as _re, uuid
    CACHE.mkdir(parents=True, exist_ok=True)
    imgs = [m for m in _re.findall(r"(\S+\.(?:jpg|jpeg|png))", prompt) if Path(m).is_file()]
    out = CACHE / f"codex-{uuid.uuid4().hex[:8]}.txt"
    cmd = [exe("codex"), "exec", "--skip-git-repo-check", "--ephemeral", "-s", "read-only", "--color", "never",
           "-o", str(out)]
    m = load_config().get("codex_model")
    if m:
        cmd += ["-m", m]
    for i in imgs:
        cmd += ["-i", i]
    cmd += ["-C", str(read_dir or CACHE), "-"]
    if imgs:
        prompt = ("The images this message names are attached to it: look at them. Do not run any commands; "
                  "answer from the attachments and the text.\n\n" + prompt)
    else:
        prompt = "Do not run any commands; answer from the text.\n\n" + prompt
    try:
        with CLAUDE_LOCK:
            r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=timeout,
                               cwd=str(read_dir or CACHE))
        txt = out.read_text() if out.exists() else ""
        if r.returncode != 0 or not txt.strip():
            raise RuntimeError("codex failed: " + (r.stderr or r.stdout)[-500:])
        return txt
    finally:
        out.unlink(missing_ok=True)

def notify(title, text):
    try:
        if IS_WIN:
            import winsound
            winsound.MessageBeep()
            return
        t = text.replace('"', "'")[:180]
        h = title.replace('"', "'")[:80]
        subprocess.run(["osascript", "-e", f'display notification "{t}" with title "{h}" sound name "Glass"'],
                       capture_output=True, timeout=10)
    except Exception:
        pass

def disk_free_gb(path=Path.home()):
    return shutil.disk_usage(path).free / 1e9


def licence_module():
    """The Pro licence check, or None when this copy has none (Lite, or the maker's own copy)."""
    try:
        from . import licence
    except ImportError:
        return None
    return None if "REPLACE" in licence.URL else licence

class _NoPhone:
    """Stand-in when phone delivery isn't part of this edition: every call does nothing."""
    def __getattr__(self, name):
        return lambda *a, **k: False

def get_phone():
    try:
        from . import phone
        return phone
    except ImportError:
        return _NoPhone()

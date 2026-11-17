"""
AutoClip: live stream -> clips -> phone approval (1 tap) -> Instagram post.

How it works (runs forever on your Windows PC):
  1. Every few minutes, check whether each streamer in streamers.json is live (yt-dlp).
  2. When one goes live, record the stream to a .ts file in the background (yt-dlp).
  3. Every `chunk_minutes`, cut the newest part of the recording (ffmpeg) and ask
     Claude Code (headless) to run the ai-clipping-skill on it: find the best moment,
     cut a 9:16 clip with captions, hook and #ad disclosure, and write a plan. NO posting yet.
  4. Send a notification to your phone (ntfy app) with an "Approve" button.
  5. When you tap Approve, Claude Code posts that clip through WoopSocial.
     You then submit the post link on Whop / Content Rewards (campaign rule).

Start:  python autoclip.py            (normal)
Check:  python autoclip.py --check    (checks tools and config, then exits)
"""
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
CONFIG = HERE / "config.json"
STREAMERS = HERE / "streamers.json"
WORK = HERE / "work"
STATE = WORK / "state.json"
LOG = WORK / "autoclip.log"


def log(msg):
    line = "%s  %s" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(line, flush=True)
    WORK.mkdir(exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_json(p, default=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def save_state(state):
    STATE.write_text(json.dumps(state, indent=1), encoding="utf-8")


# ---------- stream helpers ----------

def stream_url(s):
    platform = s.get("platform", "twitch").lower()
    name = s["channel"]
    return {
        "twitch": "https://www.twitch.tv/%s" % name,
        "kick": "https://kick.com/%s" % name,
        "youtube": "https://www.youtube.com/@%s/live" % name,
    }[platform]


def is_live(s):
    """True if the channel is live right now."""
    try:
        r = subprocess.run(
            ["yt-dlp", "--quiet", "--no-warnings", "--print", "is_live", stream_url(s)],
            capture_output=True, text=True, timeout=90)
        return r.returncode == 0 and "True" in r.stdout
    except (subprocess.TimeoutExpired, OSError):
        return False


def start_recording(s, folder):
    """Record the live stream to a growing .ts file (readable while recording)."""
    folder.mkdir(parents=True, exist_ok=True)
    out = folder / "live.ts"
    cmd = ["yt-dlp", "--quiet", "--no-part", "--hls-use-mpegts", "-f", "best[height<=1080]/best",
           "-o", str(out), stream_url(s)]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=open(folder / "record.log", "a"))
    return proc, out


def cut_last_minutes(recording, minutes, out):
    """Copy the last N minutes of the recording into a new file (fast, no re-encode)."""
    r = subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-sseof", "-%d" % (minutes * 60),
         "-i", str(recording), "-c", "copy", str(out)],
        capture_output=True, text=True, timeout=600)
    return r.returncode == 0 and out.exists() and out.stat().st_size > 1_000_000


# ---------- Claude Code ----------

def run_claude(prompt, cfg, timeout_min=60):
    cmd = [cfg.get("claude_command", "claude"), "-p", prompt,
           "--permission-mode", cfg.get("permission_mode", "acceptEdits"),
           "--allowedTools", "Bash,Read,Write,Edit,Glob,Grep,Skill"]
    try:
        r = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True,
                           timeout=timeout_min * 60, encoding="utf-8", errors="replace")
        return r.returncode, (r.stdout or "")[-4000:]
    except subprocess.TimeoutExpired:
        return 124, "timeout"


def make_clip(s, chunk, job_dir, cfg):
    result = job_dir / "result.json"
    prompt = f"""Use the ai-clipping-skill.
Campaign: {s.get('campaign_name', 'campaign')}. The campaign brief is in the file {s['brief_file']}.
Footage: {chunk} (the last {cfg['chunk_minutes']} minutes of {s['channel']}'s live stream, GTA 6 gameplay).
My account: Instagram Reels, handle {cfg['instagram_handle']}.
Make exactly ONE clip: the single best, most viral moment in this footage that follows the brief.
Use the facecam-over-gameplay layout, captions, a strong hook, the #ad disclosure on screen and the
credit @{s.get('credit_handle', s['channel'])}. Put all files in {job_dir}.
Do NOT post anything. Stop at the plan page.
Finally write {result} as JSON: {{"clip": "<path to mp4>", "caption": "<caption>", "hook": "<hook>",
"ok": true}}. If there is no good moment or the clip fails a check, write {{"ok": false, "reason": "..."}}."""
    code, out = run_claude(prompt, cfg)
    (job_dir / "claude-clip.log").write_text(out, encoding="utf-8")
    data = load_json(result, {})
    if code != 0 or not data.get("ok"):
        log("  no clip (%s)" % (data.get("reason") or "claude exit %s" % code))
        return None
    return data


def post_clip(job, cfg):
    prompt = f"""Use the ai-clipping-skill. I approved this plan by tapping YES on my phone just now:
the clip {job['clip']} in {job['dir']} with caption: {job['caption']!r}.
Post it now to my Instagram Reels account {cfg['instagram_handle']} through WoopSocial,
with the paid-partnership setting on. Then add it to the ledger and submit.md
and write {job['dir']}/posted.json as {{"url": "<public post URL>"}}."""
    code, out = run_claude(prompt, cfg, timeout_min=20)
    (Path(job["dir"]) / "claude-post.log").write_text(out, encoding="utf-8")
    posted = load_json(Path(job["dir"]) / "posted.json", {})
    return posted.get("url")


# ---------- phone (ntfy) ----------

def ntfy(cfg, topic, title, message, actions=None, priority="high"):
    body = {"topic": topic, "title": title, "message": message, "priority": 4 if priority == "high" else 3}
    if actions:
        body["actions"] = actions
    req = urllib.request.Request(cfg.get("ntfy_server", "https://ntfy.sh"),
                                 data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=30).read()
    except OSError as e:
        log("  ntfy failed: %s" % e)


def ask_phone(cfg, job):
    server = cfg.get("ntfy_server", "https://ntfy.sh")
    actions = [
        {"action": "http", "label": "✅ Approve & post", "url": "%s/%s" % (server, cfg["ntfy_reply_topic"]),
         "method": "POST", "body": "approve %s" % job["id"], "clear": True},
        {"action": "http", "label": "❌ Skip", "url": "%s/%s" % (server, cfg["ntfy_reply_topic"]),
         "method": "POST", "body": "skip %s" % job["id"], "clear": True},
    ]
    ntfy(cfg, cfg["ntfy_topic"], "New clip: %s" % job["channel"],
         "Hook: %s\n\nCaption: %s" % (job.get("hook", ""), job["caption"][:300]), actions)


def read_replies(cfg, since):
    """Return list of (time, text) replies from the phone since unix time `since`."""
    url = "%s/%s/json?poll=1&since=%d" % (cfg.get("ntfy_server", "https://ntfy.sh"), cfg["ntfy_reply_topic"], since)
    try:
        raw = urllib.request.urlopen(url, timeout=30).read().decode()
    except OSError:
        return []
    out = []
    for line in raw.splitlines():
        try:
            m = json.loads(line)
        except ValueError:
            continue
        if m.get("event") == "message":
            out.append((m.get("time", 0), m.get("message", "")))
    return out


# ---------- main loop ----------

def check(cfg, streamers):
    ok = True
    for tool in ("yt-dlp", "ffmpeg", cfg.get("claude_command", "claude")):
        if shutil.which(tool):
            print("OK   %s" % tool)
        else:
            print("MISSING  %s  (run install-windows.ps1)" % tool)
            ok = False
    for s in streamers:
        bf = REPO / s["brief_file"] if not os.path.isabs(s["brief_file"]) else Path(s["brief_file"])
        print(("OK   " if bf.exists() else "MISSING  ") + "brief for %s: %s" % (s["channel"], bf))
        ok &= bf.exists()
    for k in ("instagram_handle", "ntfy_topic", "ntfy_reply_topic"):
        if not cfg.get(k) or "CHANGE" in str(cfg.get(k)):
            print("SET THIS in config.json: %s" % k)
            ok = False
    print("\nALL GOOD" if ok else "\nFix the items above, then run again.")
    return ok


def main():
    cfg = load_json(CONFIG)
    streamers = [s for s in load_json(STREAMERS, []) if s.get("enabled", True)]
    if not cfg:
        sys.exit("config.json missing: copy config.example.json to config.json and fill it in.")
    if "--check" in sys.argv:
        sys.exit(0 if check(cfg, streamers) else 1)

    WORK.mkdir(exist_ok=True)
    state = load_json(STATE, {"jobs": {}, "posts_today": {}, "last_reply": int(time.time())})
    rec = {}          # channel -> (process, recording path, next cut time)
    log("AutoClip started. Watching: %s" % ", ".join(s["channel"] for s in streamers))
    ntfy(cfg, cfg["ntfy_topic"], "AutoClip started", "Watching: " + ", ".join(s["channel"] for s in streamers),
         priority="low")
    last_live_check = 0

    while True:
        now = time.time()
        today = datetime.now().strftime("%Y-%m-%d")

        # 1. live check
        if now - last_live_check >= cfg.get("check_every_minutes", 2) * 60:
            last_live_check = now
            for s in streamers:
                ch = s["channel"]
                running = ch in rec and rec[ch][0].poll() is None
                if running:
                    continue
                if is_live(s):
                    folder = WORK / ch / datetime.now().strftime("%Y%m%d-%H%M")
                    proc, path = start_recording(s, folder)
                    rec[ch] = (proc, path, now + cfg["chunk_minutes"] * 60, s, folder)
                    log("%s is LIVE -> recording to %s" % (ch, path))
                    ntfy(cfg, cfg["ntfy_topic"], "%s is live 🔴" % ch, "Recording started. First clip in ~%d min." % cfg["chunk_minutes"], priority="low")
                elif ch in rec:
                    log("%s stream ended" % ch)
                    rec.pop(ch)

        # 2. make clips
        for ch, (proc, path, next_cut, s, folder) in list(rec.items()):
            if now < next_cut:
                continue
            rec[ch] = (proc, path, now + cfg["chunk_minutes"] * 60, s, folder)
            posted = state["posts_today"].get(today, 0)
            if posted >= cfg.get("max_posts_per_day", 6):
                log("daily post limit reached, skipping clip")
                continue
            job_id = uuid.uuid4().hex[:8]
            job_dir = folder / ("clip-" + job_id)
            job_dir.mkdir(parents=True, exist_ok=True)
            chunk = job_dir / "chunk.ts"
            log("%s: cutting last %d min" % (ch, cfg["chunk_minutes"]))
            if not cut_last_minutes(path, cfg["chunk_minutes"], chunk):
                log("  cut failed (recording too short?)")
                continue
            log("  asking Claude for the best clip…")
            data = make_clip(s, chunk, job_dir, cfg)
            if not data:
                continue
            job = {"id": job_id, "channel": ch, "dir": str(job_dir), "clip": data["clip"],
                   "caption": data.get("caption", ""), "hook": data.get("hook", ""),
                   "status": "waiting", "created": now}
            state["jobs"][job_id] = job
            save_state(state)
            ask_phone(cfg, job)
            log("  clip %s ready -> sent to phone for approval" % job_id)

        # 3. phone replies
        for t, text in read_replies(cfg, state["last_reply"]):
            state["last_reply"] = max(state["last_reply"], int(t) + 1)
            parts = text.strip().split()
            if len(parts) != 2:
                continue
            verb, job_id = parts
            job = state["jobs"].get(job_id)
            if not job or job["status"] != "waiting":
                continue
            if verb == "skip":
                job["status"] = "skipped"
                log("clip %s skipped from phone" % job_id)
            elif verb == "approve":
                log("clip %s APPROVED from phone -> posting" % job_id)
                url = post_clip(job, cfg)
                job["status"] = "posted" if url else "post_failed"
                job["url"] = url
                if url:
                    state["posts_today"][today] = state["posts_today"].get(today, 0) + 1
                    ntfy(cfg, cfg["ntfy_topic"], "Posted ✅", "%s\nSubmit this link on Whop within 30 min!" % url,
                         actions=[{"action": "view", "label": "Open post", "url": url}])
                else:
                    ntfy(cfg, cfg["ntfy_topic"], "Post failed ❌", "Check autoclip/work/autoclip.log on the PC.")
            save_state(state)

        # 4. expire old approvals (clip is stale after 2 hours)
        for job in state["jobs"].values():
            if job["status"] == "waiting" and now - job["created"] > 2 * 3600:
                job["status"] = "expired"
        save_state(state)
        time.sleep(20)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("stopped by user")

#!/usr/bin/env python3
"""MontClipper - clips the best moments of streams while they are live, or after they end.

  python3 mc.py watch <streamer> [<streamer> ...]   clip live streams (waits if they are offline)
  python3 mc.py vod <link>                         clip a finished stream
  python3 mc.py open                               open the Upload to Socials folder and the clips page
  python3 mc.py status                             what is being watched right now
  python3 mc.py check                              check that everything is installed
"""
import argparse, getpass, json, os, shutil, subprocess, sys, time, urllib.parse, urllib.request
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from montclipper.common import load_config, CACHE, CLIPS, WHISPER_MODEL, SECRETS, disk_free_gb, AUDIO_PY, PRO, HOME, open_path, exe, LIVE, LITE_MAX_CLIPS

def hms(s):
    if s is None:
        return None
    v = 0
    for p in str(s).split(":"):
        v = v * 60 + float(p)
    return v

def cmd_check(_):
    ok = True
    names = {"streamlink": "stream recorder", "yt-dlp": "video downloader", "ffmpeg": "video editor",
             "ffprobe": "video checker", "whisper-cli": "speech-to-text"}
    print("\nMontClipper check\n")
    for t, label in names.items():
        p = shutil.which(t) or (exe(t) != t)
        print(f"  {'✅' if p else '❌'} {label} ({t})")
        ok &= bool(p)
    print(f"  {'✅' if WHISPER_MODEL.exists() else '❌'} speech model")
    from montclipper.common import agent
    ag = agent(); has = exe(ag) != ag
    print(f"  {'✅' if has else '❌'} AI that judges the clips ({'Codex' if ag == 'codex' else 'Claude Code'})")
    ok &= has
    sec = json.loads(SECRETS.read_text()) if SECRETS.exists() else {}
    print(f"  {'✅' if AUDIO_PY.exists() else '❌ not installed'}: music checker")
    gb = disk_free_gb()
    print(f"  {'✅' if gb > 15 else '⚠️ '} free disk space: {gb:.0f} GB")
    print("\n" + ("Everything is ready." if ok else "Something is missing. Ask Claude or Codex: \"MontClipper, fix my setup\".") + "\n")
    return 0 if ok else 1

def need_licence():
    from montclipper.common import licence_module
    lic = licence_module()
    return bool(lic) and not lic.check()

def cmd_licence(a):
    from montclipper.common import licence_module
    lic = licence_module()
    if not lic:
        print("This copy of MontClipper doesn't need a licence."); return 0
    email = a.email or input("The email of your Skool account (Chris Ife Studio Premium): ").strip()
    code = a.code if a.code is not None else (
        "" if a.move else input("The Premium code from the MontClipper Pro lesson: ").strip())
    skool = a.name if a.name is not None else "" if a.move else input("Your name exactly as it shows on Skool: ").strip()
    ok, msg = lic.activate(email, code, move=a.move, skool=skool)
    print("\n" + msg + "\n")
    return 0 if ok else 1

def sandboxed():
    """Codex's sandbox blocks the GPU (speech-to-text), the network and the clip judge: MontClipper must run outside it."""
    if os.environ.get("CODEX_SANDBOX"):
        print("\nMontClipper can't run inside Codex's sandbox: speech-to-text needs the graphics chip and the clip judge "
              "needs Codex itself. Run this same command again with full access (outside the sandbox).\n")
        return True
    return False

def cmd_watch(a):
    if not LIVE:
        print("\nLive clipping (clips minutes after the moment, while the streamer is still live) is part of "
              "MontClipper Pro, in Chris Ife Studio Premium: https://dub.sh/chrisifestudio\n"
              "This edition clips finished streams. Tell Claude: \"MontClipper, clip this stream: <link>\"\n")
        return 1
    if sandboxed() or need_licence():
        return 1
    from montclipper.live import watch
    cfg = load_config()
    if a.no_claude:
        cfg["use_claude"] = False
    print("\nMontClipper is watching. Clips appear in 'Upload to Socials'. Press Ctrl+C to stop.\n")
    watch(a.sources, cfg, once=a.once)

def cmd_vod(a):
    if sandboxed() or need_licence():
        return 1
    from montclipper.vod import clip_vod
    cfg = load_config()
    if a.no_claude:
        cfg["use_claude"] = False
    n = a.max_clips
    if not PRO and n > LITE_MAX_CLIPS:
        print(f"MontClipper Lite makes up to {LITE_MAX_CLIPS} clips per stream (Pro has no limit).")
        n = LITE_MAX_CLIPS
    clip_vod(a.url, cfg, hms(a.t_from) or 0, hms(a.t_to), n)

def cmd_status(_):
    rows = []
    for st in CACHE.glob("live/*/status.json"):
        d = json.loads(st.read_text())
        if time.time() - d["updated"] < 120:
            rows.append(d)
    if not rows:
        print("Nothing is being watched right now.")
    for d in rows:
        state = f"LIVE, {d['recorded_min']} min watched" if d["live"] else "waiting for the stream to start"
        print(f"{d['channel']}: {state} | {d['candidates']} moments found | {d['clips']} clips made")
    ready = len(list(CLIPS.glob("*/.meta.json")))
    print(f"{ready} clips ready in: {CLIPS}")

def cmd_open(_):
    from montclipper.dashboard import build
    page = build()
    open_path(CLIPS)
    open_path(page)
    print(f"Opened {CLIPS}")

def main():
    ap = argparse.ArgumentParser(description="MontClipper")
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("watch"); w.add_argument("sources", nargs="+"); w.add_argument("--once", action="store_true")
    w.add_argument("--no-claude", action="store_true"); w.set_defaults(fn=cmd_watch)
    v = sub.add_parser("vod"); v.add_argument("url"); v.add_argument("--max-clips", type=int, default=12)
    v.add_argument("--from", dest="t_from"); v.add_argument("--to", dest="t_to")
    v.add_argument("--no-claude", action="store_true"); v.set_defaults(fn=cmd_vod)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    sub.add_parser("open").set_defaults(fn=cmd_open)
    sub.add_parser("dashboard").set_defaults(fn=cmd_open)
    sub.add_parser("check").set_defaults(fn=cmd_check)
    lp = sub.add_parser("licence"); lp.add_argument("email", nargs="?"); lp.add_argument("--code"); lp.add_argument("--name", help="your name exactly as it shows on Skool")
    lp.add_argument("--move", action="store_true")
    lp.set_defaults(fn=cmd_licence)
    a = ap.parse_args()
    sys.exit(a.fn(a) or 0)

if __name__ == "__main__":
    main()

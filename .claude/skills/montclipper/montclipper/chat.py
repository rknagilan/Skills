"""Chat readers (Twitch IRC live, YouTube live, VOD replays) and chat scoring."""
import json, re, socket, ssl, subprocess, threading, time, random, os, urllib.request
from pathlib import Path
from .common import log, append_jsonl, load_secrets, exe

BOTS = {"nightbot", "streamelements", "streamlabs", "moobot", "fossabot", "wizebot", "sery_bot",
        "soundalerts", "kofistreambot", "pokemoncommunitygame", "botrixoficial", "blerp"}

# word -> (weight, mood)
REACT = {
    "kekw": (3, "funny"), "omegalul": (3, "funny"), "lul": (2, "funny"), "lmao": (2.5, "funny"),
    "lmfao": (3, "funny"), "lol": (1.5, "funny"), "icant": (3, "funny"), "kekl": (3, "funny"),
    "kappa": (0.5, "funny"), "😂": (2, "funny"), "🤣": (2.5, "funny"), "💀": (2.5, "funny"),
    "dead": (1.5, "funny"), "crying": (1.5, "funny"), "hahaha": (2, "funny"), "haha": (1.5, "funny"),
    "clip": (4, "clip"), "clipit": (4, "clip"), "clipped": (3, "clip"), "clip it": (4, "clip"),
    "pog": (2, "hype"), "pogchamp": (2, "hype"), "poggers": (2, "hype"), "pogu": (2, "hype"),
    "letsgo": (2, "hype"), "lets go": (2, "hype"), "w": (1.2, "hype"), "insane": (2, "hype"),
    "nowaying": (3, "shock"), "no way": (2.5, "shock"), "wtf": (2.5, "shock"), "what": (1, "shock"),
    "monkas": (2, "shock"), "omg": (2, "shock"), "holy": (2, "shock"), "bro": (0.8, "shock"),
    "😳": (2, "shock"), "😱": (2, "shock"), "????": (2.5, "shock"), "!!!": (1.5, "hype"),
    "l": (1.2, "fail"), "ratio": (1, "fail"), "fail": (1.5, "fail"), "sadge": (1.5, "fail"),
    "pepehands": (1.5, "fail"), "f": (1.2, "fail"), "rip": (1.5, "fail"), "o7": (1, "fail"),
    "aware": (1, "shock"), "copium": (1.5, "funny"), "residentsleeper": (-2, "boring"),
}
SPAM_DOWN = re.compile(r"^(!|http)|giveaway|raid|subscri|gifted|bits|cheer\d", re.I)

def msg_score(text):
    t = text.lower()
    score, moods = 0.5, {}
    toks = re.findall(r"[a-z]+|[^\sa-z0-9]+", t)
    seen = set()
    for tok in toks:
        if tok in REACT and tok not in seen:
            w, m = REACT[tok]; score += w; moods[m] = moods.get(m, 0) + w; seen.add(tok)
    for phrase in ("clip it", "no way", "lets go"):
        if phrase in t and phrase not in seen:
            w, m = REACT[phrase]; score += w; moods[m] = moods.get(m, 0) + w
    if "?" * 3 in t:
        score += 2; moods["shock"] = moods.get("shock", 0) + 2
    if len(t) > 6 and t.upper() == text and any(c.isalpha() for c in text):
        score += 1  # ALL CAPS
    return min(score, 8), moods

def parse_yt_chat_line(line):
    out = []
    try:
        d = json.loads(line)
    except Exception:
        return out
    acts = d.get("replayChatItemAction", {}).get("actions", []) or [d]
    off = d.get("replayChatItemAction", {}).get("videoOffsetTimeMsec")
    for a in acts:
        item = a.get("addChatItemAction", {}).get("item", {})
        r = item.get("liveChatTextMessageRenderer") or item.get("liveChatPaidMessageRenderer")
        if not r:
            continue
        text = "".join(run.get("text", "") or run.get("emoji", {}).get("shortcuts", [""])[0]
                       for run in r.get("message", {}).get("runs", []))
        ts = int(r.get("timestampUsec", 0)) / 1e6
        out.append({"t": ts, "off": (int(off) / 1000 if off is not None else None),
                    "u": r.get("authorName", {}).get("simpleText", "").lower(), "m": text})
    return out

# ---------------------------------------------------------------- VOD chat replays
def youtube_vod_chat(url, workdir, out_path):
    base = Path(workdir) / "ytreplay"
    subprocess.run([exe("yt-dlp"), "--skip-download", "--write-subs", "--sub-langs", "live_chat",
                    "-o", str(base), url], capture_output=True, text=True)
    files = list(Path(workdir).glob("ytreplay*.live_chat.json"))
    n = 0
    with open(out_path, "w") as f:
        for fp in files:
            for line in open(fp, errors="ignore"):
                for m in parse_yt_chat_line(line):
                    if m["off"] is not None:
                        f.write(json.dumps({"off": m["off"], "u": m["u"], "m": m["m"]}) + "\n"); n += 1
    return n

# ---------------------------------------------------------------- scoring
def bucketize(msgs, t0, t1, size=10):
    """msgs: list of {t (timeline seconds), u, m, event?}. Returns per-bucket stats."""
    nb = max(1, int((t1 - t0) // size) + 1)
    b = [{"n": 0, "users": set(), "score": 0.0, "moods": {}, "raid": False, "sample": []} for _ in range(nb)]
    for m in msgs:
        i = int((m["t"] - t0) // size)
        if i < 0 or i >= nb:
            continue
        if m.get("event") in ("raid", "submysterygift", "subgift"):
            b[i]["raid"] = True; continue
        u = m.get("u", "")
        if not u or u in BOTS or SPAM_DOWN.search(m.get("m", "")):
            continue
        if u in b[i]["users"]:
            continue  # one vote per chatter per bucket
        s, moods = msg_score(m.get("m", ""))
        b[i]["n"] += 1; b[i]["users"].add(u); b[i]["score"] += s
        for k, v in moods.items():
            b[i]["moods"][k] = b[i]["moods"].get(k, 0) + v
        if len(b[i]["sample"]) < 25 and m.get("m"):
            b[i]["sample"].append(m["m"][:80])
    return b

def chat_spikes(buckets, t0, size=10, ratio=2.6, min_unique=6, baseline_buckets=30, skip_until=None):
    """Return [(time, strength, mood, sample)] where bucket score spikes over rolling baseline."""
    out = []
    raid_block = -1
    for i, bk in enumerate(buckets):
        if bk["raid"]:
            raid_block = i + 6
        lo = max(0, i - baseline_buckets)
        hist = sorted(x["score"] for x in buckets[lo:i])
        if len(hist) < 6:
            continue
        base = max(hist[len(hist) // 2], 3.0)  # median, floor
        t = t0 + i * size
        if skip_until and t < skip_until:
            continue
        if i <= raid_block:
            continue
        if len(bk["users"]) >= min_unique and bk["score"] >= ratio * base:
            mood = max(bk["moods"], key=bk["moods"].get) if bk["moods"] else "hype"
            out.append((t + size / 2, bk["score"] / base, mood, bk["sample"]))
    return out

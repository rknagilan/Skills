"""Claude transcript sweep and Claude candidate judge."""
import json
from pathlib import Path
from .common import claude, extract_json, log, fmt_t

GUIDE = """You are the head editor of a fast, successful clipping channel that posts streamer moments
to YouTube Shorts, TikTok and Reels. Viewers swipe in under 2 seconds, so a clip must have a
clear setup and a clear payoff (a laugh, a shock, a rage, a fail, an unbelievable play, a
wholesome or emotional beat, a great one-liner) that makes sense to someone who never watched
this streamer. Most stream minutes are NOT clips. Be strict."""

RULES = """Rules:
- Times are timeline seconds, exactly as labelled in the transcript.
- start: begin on the setup (a sentence start), not mid-word. end: right after the payoff and the
  streamer's reaction peak. Usual length 15-55 s, never over 75 s.
- GTA 6 / new games: set "spoiler": true if the clip shows or discusses main-story cutscenes,
  mission endings or plot twists. Gameplay chaos, NPC moments, glitches, driving, fails are fine.
- YouTube removes ads when graphic violence appears in the first 7 seconds. If the opening
  7 s of your chosen range would be graphic (gore, brutal killing shown up close), move start
  earlier/later or set "violent_open": true.
- Set "music": true if a real licensed song (radio, Spotify, in-game radio track with vocals) is
  clearly audible in the range; those get Content ID claims. Prefer ranges without music.
- Never pick moments built on slurs, sexual content, doxxing or real-world harm to someone.
- title: Shorts-style, curiosity-driven, true to the clip, <= 70 chars, max 1 emoji, no hashtags.
- hook: 2-6 word overlay shown on the video (e.g. "HE DID NOT SEE THAT COMING").
- score 0-100 = how likely this does big views as a standalone Short. 80+ only for genuinely
  great moments. Under 60 means skip."""

def transcript_block(lines):
    return "\n".join(f"[{l['s']:.1f}-{l['e']:.1f}] {l['text']}" for l in lines) or "(no speech)"

def chat_block(buckets):
    rows = []
    for b in buckets:
        if b["n"] == 0:
            rows.append(f"[{b['t']:.0f}] 0 msgs"); continue
        moods = ",".join(f"{k}:{v:.0f}" for k, v in sorted(b["moods"].items(), key=lambda x: -x[1])[:3])
        rows.append(f"[{b['t']:.0f}] {b['n']} chatters score {b['score']:.0f} {moods} | " +
                    " / ".join(b["sample"][:8]))
    return "\n".join(rows) or "(no chat)"

def sweep(meta, lines, buckets, model="sonnet"):
    """Ask Claude for clip-worthy moments in a transcript window. Returns [{t, why, strength}]."""
    prompt = f"""{GUIDE}

Streamer: {meta.get('channel')} | Stream title: {meta.get('title','')} | Game: {meta.get('game','')}
Below is the streamer's speech (Whisper transcript, may contain errors) and chat activity per
10 seconds for one window of the stream. Find moments that could become a viral standalone clip,
ESPECIALLY ones chat may have missed (quiet funny lines, slow-burn payoffs, big reactions).

TRANSCRIPT
{transcript_block(lines)}

CHAT (per 10 s: distinct chatters, reaction score, mood, sample messages)
{chat_block(buckets)}

Return ONLY JSON: {{"moments": [{{"t": <timeline second of the payoff>, "strength": <1-10>,
"why": "<short reason>"}}]}}. Include only strength >= 6. An empty list is normal."""
    try:
        d = extract_json(claude(prompt, model=model))
        return [m for m in d.get("moments", []) if m.get("strength", 0) >= 6]
    except Exception as e:
        log("sweep", "failed:", e)
        return []

def judge(meta, cand, lines, buckets, sheet_path, sheet_times, read_dir, cfg, need_facecam):
    face_ask = ("Also locate the streamer's webcam/facecam overlay in the frames (if any) and give its box "
                "as fractions of the frame [x, y, w, h]; null if there is no facecam.") if need_facecam else \
               "Set facecam to null (already known)."
    prompt = f"""{GUIDE}

Streamer: {meta.get('channel')} | Platform: {meta.get('platform')} | Stream title: {meta.get('title','')}
Game: {meta.get('game','')}

A detector flagged a possible clip around timeline second {cand['t']:.0f}
(trigger: {cand['source']}; detail: {cand.get('why','')}).

First Read this image: {sheet_path}
It is a contact sheet of frames at timeline seconds {', '.join(f'{x:.0f}' for x in sheet_times)}
(labelled on each frame). Use it to see what happened on screen.

TRANSCRIPT (timeline seconds)
{transcript_block(lines)}

CHAT (per 10 s)
{chat_block(buckets)}

{RULES}
{face_ask}

Clips ALREADY MADE from this stream (do not clip the same joke, bit or running gag again unless
this one is clearly bigger; if it repeats one of these, set clip false):
{chr(10).join('- ' + t for t in cand.get('made_titles', [])[-15:]) or '- (none yet)'}

Allowed range for start/end: {cand['win'][0]:.0f} to {cand['win'][1]:.0f}.
Return ONLY JSON:
{{"clip": true/false, "score": 0-100, "start": s, "end": s, "title": "...", "hook": "...",
"category": "funny|rage|hype|shock|fail|wholesome|skill|story|other", "spoiler": false,
"violent_open": false, "music": false, "thumb_t": <timeline second of the most expressive frame (big reaction face or peak action)>, "facecam": null, "reason": "<one sentence>"}}"""
    d = extract_json(claude(prompt, model=cfg["judge_model"], read_dir=read_dir))
    lo, hi = cand["win"]
    try:
        s, e = float(d.get("start", lo)), float(d.get("end", hi))
    except Exception:
        s, e = lo, hi
    s, e = max(lo, s), min(hi, e)
    if e - s < cfg["clip_min"]:
        mid = (s + e) / 2; s, e = max(lo, mid - cfg["clip_min"] / 2), min(hi, mid + cfg["clip_min"] / 2)
    if e - s > cfg["clip_max"]:
        e = s + cfg["clip_max"]
    d["start"], d["end"] = s, e
    d["score"] = int(d.get("score", 0) or 0)
    return d

def find_facecam(frame_path, work_dir, model="sonnet"):
    """Locate the webcam overlay on a full frame using a labelled grid, then verify the crop.
    Returns [x, y, w, h] fractions or None."""
    from PIL import Image, ImageDraw, ImageFont
    from .common import FONT_BOLD
    im = Image.open(frame_path).convert("RGB").resize((1280, 720))
    g = im.copy(); d = ImageDraw.Draw(g)
    f = ImageFont.truetype(FONT_BOLD, 14)
    for i in range(1, 20):
        x = i * 64; y = i * 36
        col = (255, 0, 0) if i % 2 == 0 else (255, 255, 0)
        d.line([(x, 0), (x, 720)], fill=col, width=1)
        d.line([(0, y), (1280, y)], fill=col, width=1)
        if i % 2 == 0:
            d.text((x + 2, 2), f"{i*5}", fill=col, font=f)
            d.text((2, y + 2), f"{i*5}", fill=col, font=f)
    grid = Path(work_dir) / "facecam_grid.jpg"
    g.save(grid, quality=90)
    prompt = f"""Read this image: {grid}
It is one frame of a live stream with a grid. Lines are every 5% (labels show percent of width
along the top and percent of height down the left edge).
Is there a webcam / facecam overlay showing the streamer's real face or body? If yes, give the
box of the WHOLE webcam panel (its outer border), as percentages of the frame.
Return ONLY JSON: {{"facecam": true/false, "x": left%, "y": top%, "w": width%, "h": height%}}"""
    try:
        r = extract_json(claude(prompt, model=model, read_dir=work_dir))
    except Exception as e:
        log("facecam", "detect failed, will retry on the next moment:", e)
        raise
    if not r.get("facecam"):
        return None
    box = [max(0, r["x"] / 100), max(0, r["y"] / 100), r["w"] / 100, r["h"] / 100]
    box[2] = min(box[2], 1 - box[0]); box[3] = min(box[3], 1 - box[1])
    # verification pass on the crop
    for _ in range(2):
        x, y, w, h = box
        crop = im.crop((int(x * 1280), int(y * 720), int((x + w) * 1280), int((y + h) * 720)))
        pad = Image.new("RGB", (crop.width + 40, crop.height + 40), (40, 40, 40)); pad.paste(crop, (20, 20))
        cp = Path(work_dir) / "facecam_crop.jpg"; pad.save(cp, quality=90)
        q = f"""Read this image: {cp}
It should be a crop of ONLY a streamer's webcam panel. Is the whole webcam inside (the streamer's
face and body never cut by an edge), with little extra game footage? Chat or alerts drawn over part of
the webcam are fine: keep them inside rather than cutting the webcam. Return ONLY JSON: {{"ok": true/false, "fix": "<if not ok: which edges to move
and by how many percent of the crop, e.g. top +20 means move the top edge down 20%>",
"dx_left": 0, "dx_right": 0, "dy_top": 0, "dy_bottom": 0}} where each d is percent of the crop
size to move that edge INWARD (positive) or OUTWARD (negative)."""
        try:
            v = extract_json(claude(q, model=model, read_dir=work_dir))
        except Exception:
            break
        if v.get("ok"):
            break
        # small nudges only: a big inward move is how a face gets cut in half
        l, rr, t, b = (min(15.0, max(-25.0, float(v.get(k, 0) or 0))) / 100
                       for k in ("dx_left", "dx_right", "dy_top", "dy_bottom"))
        nx, ny = x + l * w, y + t * h
        nw, nh = w * (1 - l - rr), h * (1 - t - b)
        if nw < 0.05 or nh < 0.05:
            break
        box = [max(0, nx), max(0, ny), min(nw, 1 - max(0, nx)), min(nh, 1 - max(0, ny))]
    log("facecam", "box", [round(v, 3) for v in box])
    return box

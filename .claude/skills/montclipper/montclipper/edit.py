"""Render a clip: 9:16 (facecam stack or zoomed gameplay over blur) and 16:9.

Look: Anton two-line hook with one orange line, ink stroke + drop shadow, Anton captions with a
word-by-word highlight, an orange FOLLOW end pill, facecam stack, credit on screen throughout.
All text is drawn into ONE timed overlay track (concat demuxer of PNGs) - looped stills hang ffmpeg.
"""
import json, os, re, tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from .common import run, ROOT, RENDER_LOCK, FONT_BOLD, CACHE
from .media import to_wav, transcribe_words, probe_video, probe_duration, grab_frame

FONTS = ROOT / "fonts"
ANTON = str(FONTS / "anton-latin-400-normal.woff2")
INTER = str(FONTS / "inter-latin-900-normal.woff2")
C = {"night": (11, 18, 32), "teal": (25, 195, 184), "tealDim": (15, 111, 109), "orange": (255, 122, 47),
     "white": (255, 255, 255), "ink": (5, 8, 15)}

def font(path, size):
    try:
        return ImageFont.truetype(path, int(size))
    except Exception:
        return ImageFont.truetype(FONT_BOLD, int(size))

def shadow_text(base, xy, text, f, fill, stroke, anchor="ma"):
    """Text with ink stroke and a soft drop shadow."""
    sh = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).text((xy[0], xy[1] + 8), text, font=f, fill=(0, 0, 0, 180), stroke_width=stroke,
                            stroke_fill=(0, 0, 0, 180), anchor=anchor)
    base.alpha_composite(sh.filter(ImageFilter.GaussianBlur(10)))
    ImageDraw.Draw(base).text(xy, text, font=f, fill=fill, stroke_width=stroke, stroke_fill=C["ink"], anchor=anchor)

def split_hook(hook, max_chars=16):
    words = hook.upper().split()
    if not words:
        return []
    if len(" ".join(words)) <= max_chars:
        return [" ".join(words)]
    best, bi = 1e9, 1
    for i in range(1, len(words)):
        a, b = " ".join(words[:i]), " ".join(words[i:])
        cost = abs(len(a) - len(b)) + (100 if max(len(a), len(b)) > max_chars + 6 else 0)
        if cost < best:
            best, bi = cost, i
    return [" ".join(words[:bi]), " ".join(words[bi:])]

def brand_mark(d, x, y, s):
    """Small folder-and-star mark drawn beside your channel name (config "brand")."""
    r = 256 * s
    d.rounded_rectangle([x - r, y - r, x + r, y + r], radius=112 * s, fill=C["night"])
    d.rounded_rectangle([x - 196 * s, y - 120 * s, x + 196 * s, y + 156 * s], radius=16 * s, fill=C["tealDim"])
    d.rounded_rectangle([x - 196 * s, y - 80 * s, x + 196 * s, y + 156 * s], radius=16 * s, fill=C["teal"])
    d.ellipse([x + (40 - 92) * s, y + (40 - 92) * s, x + (40 + 92) * s, y + (40 + 92) * s], fill=C["orange"])

def frame_layer(W, H, hook_lines, hook_y, credit, brand, kicker):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    vertical = H > W
    if brand and brand != "none" and vertical:
        brand_mark(d, 110, 190, 0.17)
        d.text((170, 158), brand.upper()[:24], font=font(INTER, 34), fill=C["white"])
        d.text((170, 200), kicker, font=font(INTER, 22), fill=C["teal"])
    if hook_lines and vertical:
        size = 112 if all(len(l) <= 14 for l in hook_lines) else 94
        for i, line in enumerate(hook_lines):
            f = font(ANTON, size)
            while d.textlength(line, font=f) > W * 0.92 and f.size > 60:
                f = font(ANTON, f.size - 6)
            col = C["orange"] if (i == len(hook_lines) - 1 and len(hook_lines) > 1) else C["white"]
            shadow_text(im, (W / 2, hook_y + i * size * 1.05), line, f, col, 10)
    if credit:
        fc = font(INTER, 30 if vertical else 26)
        tw = d.textlength(credit, font=fc)
        x, y = ((W - tw) / 2, H - 330) if vertical else (W - tw - 36, 30)
        d.text((x, y), credit, font=fc, fill=(255, 255, 255, 225), stroke_width=3, stroke_fill=(0, 0, 0, 170))
    return im

def end_pill(im, text):
    W, H = im.size
    d = ImageDraw.Draw(im)
    f = font(INTER, 40 if H > W else 34)
    tw = d.textlength(text, font=f)
    pw = min(W - 120, tw + 120)
    y = H - 320 if H > W else H - 170
    x0 = (W - pw) / 2
    d.rounded_rectangle([x0, y, x0 + pw, y + 110], radius=55, fill=C["orange"])
    d.text((W / 2, y + 55), text, font=f, fill=C["night"], anchor="mm")
    return im

def caption_groups(words, max_words=3, max_chars=16):
    groups, cur = [], []
    for w in words:
        txt = re.sub(r"[^\w'?!.,%$-]", "", w["w"]).upper()
        if not txt:
            continue
        w = dict(w, w=txt)
        if cur and (len(cur) >= max_words or sum(len(x["w"]) + 1 for x in cur) + len(txt) > max_chars
                    or w["s"] - cur[-1]["e"] > 0.6 or cur[-1]["w"][-1:] in ".?!"):
            groups.append(cur); cur = []
        cur.append(w)
    if cur:
        groups.append(cur)
    return groups

def draw_caption(im, group, active, y, size):
    W = im.size[0]
    d = ImageDraw.Draw(im)
    f = font(ANTON, size)
    words = [g["w"] for g in group]
    space = d.textlength(" ", font=f)
    total = sum(d.textlength(w, font=f) for w in words) + space * (len(words) - 1)
    if total > W * 0.9:
        f = font(ANTON, size * W * 0.9 / total)
        space = d.textlength(" ", font=f)
        total = sum(d.textlength(w, font=f) for w in words) + space * (len(words) - 1)
    x = (W - total) / 2
    for i, w in enumerate(words):
        wl = d.textlength(w, font=f)
        col = C["orange"] if i == active else C["white"]
        shadow_text(im, (x, y), w, f, col, max(8, f.size // 8), anchor="la")
        x += wl + space

def build_track(words, dur, base, cap_y, cap_size, end_text, td, tag):
    """ONE overlay track: every PNG = frame layer (+ caption state) (+ end pill in the last 2.5 s)."""
    end_at = max(0.0, dur - 2.5) if end_text else dur + 1
    events = []
    for g in caption_groups(words):
        for i, w in enumerate(g):
            s = w["s"]
            e = g[i + 1]["s"] if i + 1 < len(g) else max(w["e"], s + 0.25)
            events.append((s, e, g, i))
    cache = {}
    def png(key, group=None, active=None, end=False):
        if key in cache:
            return cache[key]
        im = base.copy()
        if group is not None:
            draw_caption(im, group, active, cap_y, cap_size)
        if end:
            end_pill(im, end_text)
        p = os.path.join(td, f"{tag}_{len(cache):04d}.png")
        im.save(p, compress_level=1)
        cache[key] = p
        return p
    # timeline of (start, end, png)
    cuts = sorted({0.0, dur, end_at} | {round(s, 3) for s, e, g, i in events} | {round(e, 3) for s, e, g, i in events})
    cuts = [c for c in cuts if 0 <= c <= dur]
    lines = []
    for a, b in zip(cuts, cuts[1:]):
        if b - a < 0.02:
            continue
        mid = (a + b) / 2
        ev = next(((g, i) for s, e, g, i in events if s <= mid < e), None)
        end = mid >= end_at
        key = (id(ev[0]) if ev else None, ev[1] if ev else None, end)
        p = png(key, ev[0] if ev else None, ev[1] if ev else None, end)
        lines += [f"file '{p}'", f"duration {b - a:.3f}"]
    lines.append(lines[-2] if lines else f"file '{png(('x',))}'")
    p = os.path.join(td, f"{tag}_track.txt")
    open(p, "w").write("\n".join(lines))
    return p

from .common import AUDIO_PY
AUDIO_TOOL = Path(__file__).resolve().parent / "audio_tool.py"

def handle_music(src, words, td, cfg, decision):
    """Detect music. mode "label" (default): only detect, and label the clip so the creator removes
    the music in CapCut (fast, honest). mode "remove": also try to take the music out (slower, and songs
    with a held melody can survive it). Returns {status, voice?, music_frac?}.
    status: none | removed | needs_removal | kept"""
    mode = cfg.get("music", "label")
    if mode == "keep":
        return {"status": "kept"}
    if not AUDIO_PY.exists():   # music tool not installed: fall back to Claude's guess
        return {"status": "needs_removal" if decision.get("music") else "none"}
    wav = os.path.join(td, "music_in.wav")
    run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-vn", "-ac", "2", "-ar", "44100", wav])
    wj = os.path.join(td, "words.json")
    Path(wj).write_text(json.dumps(words))
    voice = os.path.join(td, "voice.wav")
    thr = cfg.get("music_threshold", 0.3)
    try:
        r = run([str(AUDIO_PY), str(AUDIO_TOOL), wav, voice, wj, str(thr if mode == "remove" else 99)], timeout=600)
        res = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception as e:
        from .common import log
        log("music", "music check failed:", e)
        return {"status": "needs_removal" if decision.get("music") else "none"}
    if mode != "remove":
        found = res.get("music_frac", 0) >= thr
        song = res.get("song", 0) >= cfg.get("song_threshold", 0.08)
        status = "needs_removal" if found and song else "background_music" if found else "none"
        return {"status": status, "music_frac": res.get("music_frac"), "song": res.get("song")}
    if not res.get("cleaned"):
        return {"status": "none", "music_frac": res.get("music_frac")}
    ok = res.get("residual_max", 1) < cfg.get("music_residual_ok", 0.35)
    return {"status": "removed" if ok else "needs_removal", "voice": voice, "music_frac": res.get("music_frac"),
            "residual_frac": res.get("residual_frac")}

def render(src, meta, decision, out_dir, cfg):
    """src: a video file containing exactly the clip range. Writes vertical.mp4 / wide.mp4 / thumb.jpg."""
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    sw, sh, fps = probe_video(src)
    fps = min(60, round(fps) or 30)
    brand = cfg.get("brand", "none")
    kicker = cfg.get("kicker", "STREAM CLIPS")
    CACHE.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=str(CACHE)) as td:
        wav = to_wav(src, os.path.join(td, "a.wav"))
        words = transcribe_words(wav)
        music = handle_music(src, words, td, cfg, decision)
        decision["music_status"] = music["status"]
        decision["music_frac"] = music.get("music_frac")
        decision["music_song"] = music.get("song")
        dur = probe_duration(src)
        credit = meta.get("credit", "")
        hook_lines = split_hook(decision.get("hook", ""))
        end_text = f"FOLLOW {credit.upper()}" if credit and cfg.get("end_pill", True) else ""
        jobs = []
        if cfg.get("vertical", True):
            W, H = 1080, 1920
            fc = decision.get("facecam")
            if fc and len(fc) == 4 and fc[2] > 0.05 and fc[3] > 0.05:
                top_h = 700
                bot_h = H - top_h
                x, y, w, h = fc
                cx, cy, cw, ch = int(x * sw), int(y * sh), int(w * sw), int(h * sh)
                want = W / top_h
                if cw / ch > want:
                    nw = int(ch * want); cx += (cw - nw) // 2; cw = nw
                else:
                    nh = int(cw / want); cy += (ch - nh) // 2; ch = nh
                gw = int(sh * W / bot_h) // 2 * 2
                vf = (f"[0:v]split=2[a][b];[a]crop={cw}:{ch}:{cx}:{cy},scale={W}:{top_h}[cam];"
                      f"[b]crop={gw}:{sh}:(iw-{gw})/2:0,scale={W}:{bot_h}[game];[cam][game]vstack[base]")
                hook_y, cap_y = top_h + 50, int(top_h + bot_h * 0.56)
            else:
                zw = int(W * 1.4) // 2 * 2
                fg_h = int(zw * sh / sw) // 2 * 2
                vf = (f"[0:v]split=2[a][b];[a]scale=-2:{H},crop={W}:{H},gblur=sigma=30,eq=brightness=-0.18[bg];"
                      f"[b]scale={zw}:{fg_h},crop={W}:{fg_h}[fg];[bg][fg]overlay=0:(H-h)/2[base]")
                hook_y, cap_y = (H - fg_h) / 2 - 290, int((H + fg_h) / 2 + 30)
            jobs.append(("vertical", W, H, vf, hook_y, cap_y, 108))
        if cfg.get("wide", True):
            W, H = 1920, 1080
            vf = f"[0:v]scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2[base]"
            jobs.append(("wide", W, H, vf, None, int(H * 0.74), 92))
        outputs = {}
        def one(job):
            name, W, H, vf, hook_y, cap_y, cap_size = job
            base = frame_layer(W, H, hook_lines if hook_y is not None else [], hook_y or 0, credit, brand, kicker)
            track = build_track(words, dur, base, cap_y, cap_size, end_text, td, name)
            out = out_dir / f"{name}.mp4"
            fcx = vf + f";[1:v]format=rgba[ov];[base][ov]overlay=0:0:eof_action=repeat,fps={fps},setsar=1,format=yuv420p[v]"
            ain = ["-i", music["voice"]] if music.get("voice") else []
            amap = "2:a" if music.get("voice") else "0:a?"
            run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-f", "concat", "-safe", "0", "-i", track, *ain,
                 "-filter_complex", fcx, "-map", "[v]", "-map", amap, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
                 "-ar", "48000", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-profile:v", "high",
                 "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-t", f"{dur:.3f}", str(out)],
                timeout=1200)
            outputs[name] = str(out)
        with RENDER_LOCK, ThreadPoolExecutor(len(jobs) or 1) as ex:
            list(ex.map(one, jobs))
        if music.get("voice"):
            # keep a copy with the original sound (has music) in a subfolder, same picture
            orig = out_dir / "Original sound (has music)"
            orig.mkdir(exist_ok=True)
            for name in outputs:
                run(["ffmpeg", "-y", "-v", "error", "-i", str(out_dir / f"{name}.mp4"), "-i", str(src), "-map", "0:v",
                     "-map", "1:a?", "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "48000",
                     "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
                     str(orig / f"{name}.mp4")])
        make_covers(src, decision, credit, hook_lines, out_dir, td, sw, sh)
        (out_dir / ".captions.json").write_text(json.dumps(words))
    return outputs

def _fill(im, W, H):
    """Scale+crop an image to exactly W x H (cover)."""
    r = max(W / im.width, H / im.height)
    im = im.resize((int(im.width * r + 1), int(im.height * r + 1)), Image.LANCZOS)
    x, y = (im.width - W) // 2, (im.height - H) // 2
    return im.crop((x, y, x + W, y + H))

def make_covers(src, decision, credit, hook_lines, out_dir, td, sw, sh):
    """Vertical cover (1080x1920, headline mid-frame so it survives the 4:5 shelf crop) and a
    wide thumbnail (1280x720): big face when there is a facecam, the action frame otherwise."""
    t = float(decision.get("thumb_rel", 1.0))
    fp = os.path.join(td, "thumb_src.png")
    run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.3f}", "-i", str(src), "-frames:v", "1", fp], check=False)
    if not os.path.exists(fp):
        return
    frame = Image.open(fp).convert("RGB")
    fw, fh = frame.size
    fc = decision.get("facecam")
    face = None
    if fc and len(fc) == 4 and fc[2] > 0.05:
        x, y, w, h = fc
        face = frame.crop((int(x * fw), int(y * fh), int((x + w) * fw), int((y + h) * fh)))
        # gameplay without the facecam corner: crop the side away from it
        gx0 = int((x + w) * fw) if x < 0.5 else 0
        gx1 = fw if x < 0.5 else int(x * fw)
        game = frame.crop((gx0, 0, gx1, fh)) if gx1 - gx0 > fw * 0.5 else frame
    else:
        game = frame
    lines = split_hook(decision.get("hook") or decision.get("title", ""), max_chars=9)[:2]
    # ---- vertical cover
    W, H = 1080, 1920
    if face is not None:
        top = _fill(face, W, 1000)
        bot = _fill(game, W, H - 1000)
        cov = Image.new("RGB", (W, H)); cov.paste(top, (0, 0)); cov.paste(bot, (0, 1000))
    else:
        cov = _fill(game, W, H)
    cov = cov.convert("RGBA")
    grad = Image.new("RGBA", (W, H), (0, 0, 0, 0)); gd = ImageDraw.Draw(grad)
    for i in range(420):
        a = int(150 * (1 - abs(i - 210) / 210))
        gd.line([(0, 750 + i), (W, 750 + i)], fill=(0, 0, 0, a))
    cov.alpha_composite(grad)
    d = ImageDraw.Draw(cov)
    size = 150 if all(len(l) <= 12 for l in lines) else 124
    y0 = 960 - (len(lines) * size * 1.02) / 2
    for i, line in enumerate(lines[:2]):
        f = font(ANTON, size)
        while d.textlength(line, font=f) > W * 0.92 and f.size > 70:
            f = font(ANTON, f.size - 6)
        col = C["orange"] if (i == len(lines) - 1 and len(lines) > 1) else C["white"]
        shadow_text(cov, (W / 2, y0 + i * size * 1.02), line, f, col, 12)
    if credit:
        fcr = font(INTER, 34)
        d.text((W / 2, 1560), credit, font=fcr, fill=C["white"], anchor="mm", stroke_width=4, stroke_fill=C["ink"])
    cov.convert("RGB").save(out_dir / "cover_vertical.png")
    # ---- wide thumbnail
    W, H = 1280, 720
    th = _fill(game, W, H).convert("RGBA")
    if face is not None:
        fimg = _fill(face, 560, 640)
        border = Image.new("RGBA", (fimg.width + 16, fimg.height + 16), C["orange"] + (255,))
        border.paste(fimg, (8, 8))
        th.alpha_composite(border, (W - border.width - 30, H - border.height - 20))
    shade = Image.new("RGBA", (W, H), (0, 0, 0, 0)); sd = ImageDraw.Draw(shade)
    for i in range(W // 2 + 200):
        sd.line([(i, 0), (i, H)], fill=(0, 0, 0, int(170 * max(0, 1 - i / (W / 2 + 200)))))
    th.alpha_composite(shade)
    d = ImageDraw.Draw(th)
    tl = lines[:2]
    for i, line in enumerate(tl):
        f = font(ANTON, 120 if len(line) <= 10 else 96)
        maxw = W * (0.52 if face is not None else 0.9)
        while d.textlength(line, font=f) > maxw and f.size > 54:
            f = font(ANTON, f.size - 4)
        col = C["orange"] if (i == len(tl) - 1 and len(tl) > 1) else C["white"]
        shadow_text(th, (50, 150 + i * f.size * 1.05), line, f, col, 9, anchor="la")
    th.convert("RGB").save(out_dir / "thumb_wide.jpg", quality=92)

def write_meta(out_dir, meta, decision):
    link = meta.get("link", "")
    who = meta.get("channel", "")
    title = decision.get("title", "Clip")
    game = meta.get("game", "")
    tag_who = re.sub(r"\W", "", who.lower())
    tags = ["#" + tag_who, "#shorts", "#gaming"]
    if game:
        tags.insert(1, "#" + re.sub(r"\W", "", game.lower())[:30])
    if "grand theft auto" in game.lower() or "gta" in game.lower():
        tags.insert(1, "#gta6" if "vi" in game.lower() or "6" in game else "#gta")
    caption = f"{title} 😂 (via {who}) {' '.join(tags[:4])}" if decision.get("category") == "funny" else \
              f"{title} (via {who}) {' '.join(tags[:4])}"
    desc = f"{title}\n\nFull credit to {who}. Watch them live: {link}\n\n{' '.join(tags)}"
    files = decision.get("files", {})
    flags = []
    if decision.get("violent_open"):
        flags.append("Starts with violence: YouTube may show fewer ads. Consider skipping.")
    ms = decision.get("music_status")
    if ms == "removed":
        flags.append("Music was playing and has been REMOVED automatically (the voice is kept). "
                     "Listen once before posting. The version with the original sound is in 'Original sound (has music)'.")
    elif ms == "background_music":
        flags.append("Background music (instrumental, no singing), like a game soundtrack. Lower risk: most "
                     "clippers post these as they are. If the platform shows a copyright claim, mute the music in "
                     "CapCut (Audio > Isolate voice).")
    elif ms == "needs_removal":
        flags.append("A SONG IS PLAYING in this clip. REMOVE THE MUSIC BEFORE POSTING: in CapCut tap the clip, "
                     "then Audio > Isolate voice, and listen once. If you can still hear the song, don't post it: "
                     "it can get a copyright claim that takes the earnings.")
    notes = f"""TITLE
{title}

CAPTION (TikTok, Reels, Shorts)
{caption}

DESCRIPTION (YouTube)
{desc}

HASHTAGS
{' '.join(tags)}

FILES
Vertical video (Shorts, TikTok, Reels): {files.get('vertical', '')}
Vertical thumbnail / cover: {files.get('cover_vertical', '')}
Wide video (YouTube, X): {files.get('wide', '')}
Wide thumbnail: {files.get('thumb_wide', '')}

ABOUT THIS CLIP
Streamer: {who} ({link})
When: {meta.get('stamp', '')} ({'your clock time' if ':' in str(meta.get('stamp','')) and meta.get('live') else 'position in the stream'})
Score: {decision.get('score')}/100 ({decision.get('category')})
Why it was picked: {decision.get('reason', '')}
{('CHECK BEFORE POSTING' + chr(10) + chr(10).join(flags)) if flags else 'Checks: no spoilers, no violent opening, no music.'}

AFTER POSTING
Move this folder into "Done".
"""
    Path(out_dir, "Upload notes.txt").write_text(notes)
    Path(out_dir, ".meta.json").write_text(json.dumps({**decision, "meta": meta, "description": desc}, indent=2))
    return caption

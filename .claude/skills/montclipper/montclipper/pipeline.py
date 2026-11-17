"""Shared candidate queue, judging and clip production for live and VOD modes."""
import json, os, threading, time, datetime, tempfile, heapq, itertools
from pathlib import Path
from .common import (log, load_config, CLIPS, slug, fmt_t, channel_get, channel_set, append_jsonl,
                     notify, run)
from . import judge as J, edit, dashboard
from .common import get_phone
phone = get_phone()
from .chat import bucketize
from .media import to_wav, transcribe_words, words_to_lines, grab_frame, contact_sheet

def clean_name(t, n=None):
    """Finder-safe file/folder name that keeps spaces and normal punctuation."""
    import re as _re
    from .common import IS_WIN
    n = n or (70 if IS_WIN else 90)          # Windows trips over paths longer than 260 characters
    t = _re.sub(r'[\\/:*?"<>|]', "", t)
    t = "".join(ch for ch in t if ch.isprintable() and (ord(ch) < 0x2000 or ch in "–—’"))
    return _re.sub(r"\s+", " ", t).strip(" .")[:n] or "Clip"

SOURCE_WEIGHT = {"viewer-clip": 3.0, "chat": 1.0, "claude-sweep": 1.0, "audio": 0.6}

class Candidates:
    """Merging priority queue of moments (timeline seconds)."""
    def __init__(self, merge_seconds):
        self.merge = merge_seconds
        self.items = []          # dicts
        self.lock = threading.Lock()
        self.cv = threading.Condition(self.lock)
        self.ids = itertools.count(1)

    def add(self, t, strength, source, why=""):
        with self.lock:
            for c in self.items:
                if abs(c["t"] - t) <= self.merge and c["state"] in ("new", "judging", "done"):
                    if c["state"] == "new":
                        c["strength"] += strength * SOURCE_WEIGHT.get(source, 1)
                        if source not in c["source"]:
                            c["source"] += "+" + source
                        c["why"] = (c["why"] + " | " + why)[:400] if why else c["why"]
                        # payoff time: prefer the later strong signal
                        if strength * SOURCE_WEIGHT.get(source, 1) > 2:
                            c["t"] = max(c["t"], t) if source != "audio" else c["t"]
                    return c
            c = {"id": next(self.ids), "t": t, "strength": strength * SOURCE_WEIGHT.get(source, 1),
                 "source": source, "why": why, "state": "new", "added": time.time()}
            self.items.append(c)
            self.cv.notify_all()
            return c

    def take(self, ready_until, min_strength=0.0):
        """Pop the strongest new candidate whose aftermath is available."""
        with self.lock:
            ready = [c for c in self.items if c["state"] == "new" and c["t"] <= ready_until
                     and c["strength"] >= min_strength]
            if not ready:
                return None
            c = max(ready, key=lambda c: c["strength"])
            c["state"] = "judging"
            return c

    def pending(self):
        with self.lock:
            return [c for c in self.items if c["state"] in ("new", "judging")]

class Producer:
    """Judges candidates and renders clips. Subclasses supply media + transcript access."""
    def __init__(self, meta, cfg, workdir):
        self.meta, self.cfg, self.dir = meta, cfg, Path(workdir)
        self.cands = Candidates(cfg["merge_seconds"])
        self.made = []           # (start, end) timeline ranges already clipped
        self.made_titles = []    # titles, so Claude does not repeat a joke
        self.judged = 0
        self.stats = {"judged": 0, "clips": 0, "skipped": 0}
        self.rendering = 0       # clips being made right now (stopping waits for them)
        (self.dir / "judge").mkdir(parents=True, exist_ok=True)
        self.decisions = self.dir / "decisions.jsonl"

    # --- to implement
    def window_media(self, a, b):
        """Return (video_path, offset_of_a_in_file) covering [a, b]."""
        raise NotImplementedError
    def window_lines(self, a, b, media=None):
        raise NotImplementedError
    def window_chat(self, a, b):
        raise NotImplementedError
    def stamp(self, t):
        return fmt_t(t)

    def overlaps_made(self, s, e):
        for a, b in self.made:
            inter = min(b, e) - max(a, s)
            if inter > 0.5 * min(e - s, b - a):
                return True
        return False

    def process(self, cand):
        cfg = self.cfg
        a, b = cand["t"] - cfg["lookback"], cand["t"] + cfg["lookahead"]
        a = max(a, self.timeline_start())
        cand["win"] = (a, b)
        cand["made_titles"] = list(self.made_titles)
        if self.overlaps_made(cand["t"] - 10, cand["t"] + 10):
            cand["state"] = "done"; return
        media, off = self.window_media(a, b)
        if not media:
            log("judge", f"#{cand['id']} no media for window"); cand["state"] = "done"; return
        lines = self.window_lines(a, b, (media, off))
        buckets = self.window_chat(a, b)
        # contact sheet: 6 frames from t-35 to t+15
        times = [cand["t"] + d for d in (-35, -25, -15, -5, 5, 15)]
        times = [t for t in times if a <= t <= b] or [cand["t"]]
        jd = self.dir / "judge"
        frames = []
        for i, t in enumerate(times):
            fp = jd / f"c{cand['id']}_{i}.jpg"
            if grab_frame(media, off + (t - a), fp, width=640):
                frames.append(str(fp))
        sheet = contact_sheet(frames, [f"{t:.0f}s" for t in times[:len(frames)]], jd / f"c{cand['id']}_sheet.jpg")
        name = self.meta["channel"]
        ch = channel_get(name)
        # look again after 40 clips (layouts change), or after 5 if no facecam was found
        # (the camera may come on later, or the first frame was a full-screen scene)
        recheck = 5 if ch.get("facecam") is None else 40
        if cfg.get("use_claude", True) and ("facecam" not in ch or ch.get("facecam_checks", 0) >= recheck):
            fp = jd / f"c{cand['id']}_full.jpg"
            if grab_frame(media, off + (cand["t"] - a), fp, width=1280):
                try:
                    channel_set(name, facecam=J.find_facecam(fp, jd, cfg["judge_model"]), facecam_checks=0)
                except Exception:
                    pass   # a failed check is not "no facecam": try again on the next moment
                ch = channel_get(name)
        need_face = False
        if not cfg.get("use_claude", True):
            d = self.heuristic(cand, lines)
        else:
            try:
                d = J.judge(self.meta, cand, lines, buckets, sheet, times[:len(frames)], jd, cfg, need_face)
            except Exception as e:
                log("judge", f"#{cand['id']} judge error: {e}"); cand["state"] = "done"; return
        self.stats["judged"] += 1
        d["facecam"] = ch.get("facecam")
        channel_set(name, facecam_checks=ch.get("facecam_checks", 0) + 1)
        d["trigger"] = cand["source"]
        append_jsonl(self.decisions, {"cand": {k: v for k, v in cand.items() if k not in ("win", "made_titles")}, "decision": d})
        ok = d.get("clip") and d["score"] >= cfg["min_score"] and not d.get("spoiler")
        log("judge", f"{self.meta['channel']} #{cand['id']} t={self.stamp(cand['t'])} via {cand['source']} -> "
                     f"{'CLIP' if ok else 'skip'} {d['score']} {d.get('category','')} | {d.get('title','')[:60]} | {d.get('reason','')[:90]}")
        if not ok or self.overlaps_made(d["start"], d["end"]):
            self.stats["skipped"] += 1; cand["state"] = "done"; return
        cap = getattr(self, "max_clips", None)
        if cap and len(self.made) >= cap:
            cand["state"] = "done"; return
        self.made.append((d["start"], d["end"]))
        self.made_titles.append(d.get("title", ""))
        # streamers move their webcam mid-stream: locate it again on a frame from inside this clip
        if cfg.get("use_claude", True):
            fp = jd / f"c{cand['id']}_clip.jpg"
            if grab_frame(media, off + ((d["start"] + d["end"]) / 2 - a), fp, width=1280):
                try:
                    box = J.find_facecam(fp, jd, cfg["judge_model"])
                    if box != d["facecam"]:
                        log("facecam", f"{name}: webcam is somewhere else in this clip, using the new place")
                    d["facecam"] = box
                    channel_set(name, facecam=box, facecam_checks=0)
                except Exception as e:
                    log("facecam", "clip check failed, keeping the last place:", e)
        from .common import PROTECT
        self.rendering += 1
        PROTECT.on = True
        try:
            self.produce(d, media, off, a)
        except Exception as e:
            log("edit", f"#{cand['id']} render failed: {e}")
            if d.get("_folder"):
                import shutil
                shutil.rmtree(d["_folder"], ignore_errors=True)
        finally:
            PROTECT.on = False
            self.rendering -= 1
        cand["state"] = "done"

    def heuristic(self, cand, lines):
        s = cand["t"] - 25
        return {"clip": cand["strength"] >= 3, "score": min(95, int(50 + cand["strength"] * 6)),
                "start": max(cand["win"][0], s), "end": min(cand["win"][1], cand["t"] + 12),
                "title": f"{self.meta['channel']} moment", "hook": "", "category": "other",
                "spoiler": False, "violent_open": False, "facecam": None, "reason": "heuristic (no Claude)"}

    def produce(self, d, media, off, a):
        from .common import licence_module
        lic = licence_module()
        if lic and not lic.ok_recent():
            log("licence", "MontClipper Pro isn't activated on this computer, so no clip was made.")
            return None
        t0 = time.time()
        s, e = d["start"], d["end"]
        now = datetime.datetime.now()
        title = d.get("title", "Clip")
        safe = clean_name(title)
        out = CLIPS / clean_name(f"{now:%Y-%m-%d %H%M} {self.meta['channel']} - {title}")
        out.mkdir(parents=True, exist_ok=True)
        d["_folder"] = str(out)   # removed again if the render fails, so no half-made clip is left
        cut = out / "_src.mp4"
        run(["ffmpeg", "-y", "-v", "error", "-ss", f"{off + (s - a):.3f}", "-i", str(media), "-t", f"{e - s:.3f}",
             "-c:v", "libx264", "-preset", "ultrafast", "-crf", "14", "-c:a", "aac", "-b:a", "256k", str(cut)])
        meta = dict(self.meta, stamp=self.stamp(s))
        try:
            th = float(d.get("thumb_t", e - (e - s) * 0.3)) - s
        except Exception:
            th = (e - s) * 0.7
        d["thumb_rel"] = min(max(0.5, th), e - s - 0.3)
        edit.render(cut, meta, d, out, self.cfg)
        names = {"vertical.mp4": f"{safe} - Vertical.mp4", "wide.mp4": f"{safe} - Wide.mp4",
                 "cover_vertical.png": f"{safe} - Vertical - Thumbnail.png",
                 "thumb_wide.jpg": f"{safe} - Wide - Thumbnail.jpg"}
        for k, v in names.items():
            if (out / k).exists():
                (out / k).rename(out / v)
        d["files"] = {k.split(".")[0]: v for k, v in names.items() if (out / v).exists()}
        caption = edit.write_meta(out, meta, d)
        cut.unlink(missing_ok=True)
        d["meta_channel"] = self.meta["channel"]
        phone.send_clip_async(out, dict(d), caption)
        self.stats["clips"] += 1
        dashboard.build()
        log("clip", f"READY in {time.time() - t0:.0f}s -> {out}")
        notify(f"MontClipper: {self.meta['channel']} ({d['score']})", title)

    def timeline_start(self):
        return 0.0

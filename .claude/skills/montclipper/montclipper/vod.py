"""After-stream mode: clip a finished stream (Twitch VOD or YouTube VOD) from chat replay + audio + transcript."""
import json, os, threading, time, datetime, statistics, concurrent.futures as cf
from pathlib import Path
from .common import log, load_config, CACHE, run, fmt_t, parse_source
from .chat import youtube_vod_chat, bucketize, chat_spikes
from .media import to_wav, loudness, transcribe_words, words_to_lines
from .pipeline import Producer
from . import judge as J

FMT = "bv*[height<=1080]+ba/b[height<=1080]/best"

class VodSession(Producer):
    def __init__(self, url, cfg, t_from=0, t_to=None, max_clips=12):
        info = json.loads(run(["yt-dlp", "-J", "--no-warnings", url], timeout=120).stdout)
        platform, ident, norm = parse_source(url)
        if platform == "twitch_vod":
            name = (info.get("uploader_id") or info.get("uploader") or "twitch").lower()
            link, credit = f"https://twitch.tv/{name}", f"twitch.tv/{name}"
            plat = "twitch"
        else:
            name = info.get("channel") or info.get("uploader") or "youtube"
            link, credit = info.get("webpage_url", url), f"youtube: {name}"
            plat = "youtube"
        meta = {"channel": name, "platform": plat, "link": link, "credit": credit,
                "title": info.get("title", ""), "game": (info.get("categories") or [""])[0] if plat == "twitch" else ""}
        self.url, self.plat, self.info = url, plat, info
        self.duration = float(info.get("duration") or 0)
        self.t_from, self.t_to = t_from, (t_to or self.duration)
        self.max_clips = max_clips
        wd = CACHE / "vod" / f"{name}_{info.get('id','x')}"
        wd.mkdir(parents=True, exist_ok=True)
        super().__init__(meta, cfg, wd)
        self.chat = []
        self.wav = None
        self.words_cache = {}
        log("vod", f"{name}: '{meta['title'][:70]}' ({fmt_t(self.duration)}) -> {wd}")

    # ---------------------------------------------------------------- inputs
    def load_chat(self):
        out = self.dir / "chat.jsonl"
        if not out.exists() or out.stat().st_size == 0:
            log("vod", "downloading chat replay ...")
            try:
                if self.plat == "twitch":
                    log("vod", "finished Twitch streams are clipped from the sound, the words and Claude "
                               "(their old chat isn't read)")
                    n = 0
                else:
                    n = youtube_vod_chat(self.url, self.dir, out)
            except Exception as e:
                log("vod", "chat replay unavailable:", e); n = 0
            log("vod", f"chat replay: {n} messages")
        for ln in open(out) if out.exists() else []:
            m = json.loads(ln); m["t"] = m.pop("off"); self.chat.append(m)

    def load_audio(self):
        wav = self.dir / "audio.wav"
        if not wav.exists():
            log("vod", "downloading audio track ...")
            for f in list(self.dir.glob("audio_src.*")):
                f.unlink()
            part = []
            if self.t_from > 0 or self.t_to < self.duration - 1:
                part = ["--download-sections", f"*{self.t_from:.0f}-{self.t_to:.0f}"]
            run(["yt-dlp", "-q", "--no-warnings", "-N", "8", "-f", "bestaudio/Audio_Only/audio_only/worst", *part,
                 "-o", str(self.dir / "audio_src.%(ext)s"), self.url], timeout=7200)
            src = next(self.dir.glob("audio_src.*"))
            to_wav(src, wav)
            src.unlink()
        self.wav = wav
        self.aoff = self.t_from if (self.t_from > 0 or self.t_to < self.duration - 1) else 0.0
        self.db = [-90.0] * int(self.aoff * 2) + loudness(wav)
        log("vod", f"audio ready ({fmt_t(len(self.db) / 2)})")

    # ---------------------------------------------------------------- detectors
    def chat_candidates(self):
        if not self.chat:
            return []
        b = bucketize(self.chat, 0, self.duration)
        spikes = chat_spikes(b, 0, ratio=self.cfg["chat_ratio"], min_unique=max(3, self.cfg["chat_min_unique"] // 2),
                             skip_until=self.cfg["warmup_seconds"])
        return [(t, min(s, 6), "chat", f"chat {mood} x{s:.1f}: " + " / ".join(sm[:5])) for t, s, mood, sm in spikes]

    def audio_candidates(self, top=15):
        out, db = [], self.db
        win = 240
        for i in range(win, len(db) - 2, 2):
            v = db[i]
            if v < -24:
                continue
            med = statistics.median(db[i - win:i:4])
            if v > med + self.cfg["audio_jump_db"] and db[i + 1] > med + self.cfg["audio_jump_db"] - 2:
                out.append((i / 2 + 3, (v - med) / 4, "audio", f"loudness +{v - med:.0f}dB"))
        out.sort(key=lambda x: -x[1])
        picked = []
        for c in out:
            if all(abs(c[0] - p[0]) > 60 for p in picked):
                picked.append(c)
            if len(picked) >= top:
                break
        return picked

    def sweep_all(self, chunk=600):
        """Transcribe in 10-minute chunks and let Claude find moments (runs in background)."""
        t = self.t_from
        while t < self.t_to:
            b = min(self.t_to, t + chunk)
            lines = self.window_lines(t, b)
            if lines:
                ms = J.sweep(self.meta, lines, self.window_chat(t, b), self.cfg["sweep_model"])
                for m in ms:
                    try:
                        tt = float(m["t"])
                    except Exception:
                        continue
                    if t - 5 <= tt <= b + 5:
                        self.cands.add(tt, float(m.get("strength", 6)) / 2, "claude-sweep", m.get("why", ""))
                        log("detect", f"claude sweep {fmt_t(tt)} s{m.get('strength')} {m.get('why','')[:70]}")
            t = b

    # ---------------------------------------------------------------- Producer access
    def window_lines(self, a, b, media=None):
        a, b = max(0, a), min(self.duration, b)
        key = (int(a), int(b))
        if key not in self.words_cache:
            tmp = self.dir / f"w_{key[0]}_{key[1]}.wav"
            to_wav(self.wav, tmp, start=max(0, a - self.aoff), dur=b - a)
            ws = transcribe_words(tmp)
            tmp.unlink(missing_ok=True)
            self.words_cache[key] = [{"w": w["w"], "s": a + w["s"], "e": a + w["e"]} for w in ws]
        return words_to_lines(self.words_cache[key])

    def window_chat(self, a, b):
        t0 = (int(max(0, a)) // 10) * 10
        bk = bucketize([m for m in self.chat if t0 <= m["t"] <= b], t0, b)
        for i, x in enumerate(bk):
            x["t"] = t0 + i * 10
        return bk

    def window_media(self, a, b):
        out = self.dir / "judge" / f"sec_{int(a)}_{int(b)}.mp4"
        for attempt in range(3):
            if out.exists():
                break
            for f in out.parent.glob(out.stem + "*"):
                f.unlink()
            extra = ["--force-keyframes-at-cuts"] if attempt < 2 else []   # last try: keyframe cut
            run(["yt-dlp", "-q", "--no-warnings", "-N", "8", "-f", FMT, "--download-sections", f"*{a:.0f}-{b:.0f}",
                 *extra, "--merge-output-format", "mp4", "-o", str(out), self.url], check=False, timeout=900)
            if not out.exists():
                log("vod", f"section {fmt_t(a)} download failed (try {attempt + 1}/3)")
                time.sleep(3)
        if not out.exists():
            cands = list(out.parent.glob(out.stem + "*"))
            if not cands:
                return None, 0
            out = cands[0]
        return str(out), 0.0

    # ---------------------------------------------------------------- main
    def run(self):
        t0 = time.time()
        with cf.ThreadPoolExecutor(2) as ex:
            fc, fa = ex.submit(self.load_chat), ex.submit(self.load_audio)
            fc.result(); fa.result()
        for c in self.chat_candidates() + self.audio_candidates():
            if self.t_from <= c[0] <= self.t_to:
                self.cands.add(*c)
        log("vod", f"{len(self.cands.items)} chat/audio candidates; starting Claude sweep + judging")
        sw = None
        if self.cfg.get("use_claude", True):
            sw = threading.Thread(target=self.sweep_all, daemon=True); sw.start()
        budget = self.max_clips * 4
        lock = threading.Lock()
        counter = {"judged": 0}
        def worker():
            while True:
                with lock:
                    if counter["judged"] >= budget or len(self.made) >= self.max_clips:
                        return
                c = self.cands.take(self.duration + 1)
                if not c:
                    if sw and sw.is_alive():
                        time.sleep(3); continue
                    return
                with lock:
                    counter["judged"] += 1
                try:
                    self.process(c)
                except Exception as e:
                    log("judge", f"#{c['id']} failed: {e}"); c["state"] = "done"
        workers = [threading.Thread(target=worker) for _ in range(3)]
        for w in workers:
            w.start()
        for w in workers:
            w.join()
        judged = counter["judged"]
        for p in (self.dir / "judge").glob("sec_*"):
            p.unlink(missing_ok=True)
        log("vod", f"done in {fmt_t(time.time() - t0)}: {self.stats['clips']} clips from {judged} judged")
        from .common import get_phone
        phone = get_phone()
        phone.wait_pending()
        phone.message(f"✅ Finished clipping {self.meta['channel']}: {self.stats['clips']} clips made.")
        return self.stats

def clip_vod(url, cfg=None, t_from=0, t_to=None, max_clips=12):
    import shutil, signal
    def _bye(*_):
        raise KeyboardInterrupt
    for sig in [getattr(signal, n) for n in ("SIGTERM", "SIGHUP") if hasattr(signal, n)]:
        signal.signal(sig, _bye)
    for old in (CACHE / "vod").glob("*"):          # leftovers from a crashed run
        if old.is_dir() and time.time() - old.stat().st_mtime > 1800:
            shutil.rmtree(old, ignore_errors=True)
    v = VodSession(url, cfg or load_config(), t_from, t_to, max_clips)
    try:
        return v.run()
    finally:
        shutil.rmtree(v.dir, ignore_errors=True)   # downloaded audio/sections are temporary
        log("vod", "temporary files deleted - clips are in 'Upload to Socials'")

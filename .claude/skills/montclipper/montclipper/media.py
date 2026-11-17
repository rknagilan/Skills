"""Audio extraction, loudness, Whisper word transcription, frame sheets."""
import json, subprocess, tempfile, os
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from .common import run, WHISPER_MODEL, WHISPER_LOCK, FONT_BOLD

def to_wav(src, dst, start=None, dur=None):
    cmd = ["ffmpeg", "-y", "-v", "error"]
    if start is not None:
        cmd += ["-ss", f"{start:.3f}"]
    cmd += ["-i", str(src)]
    if dur is not None:
        cmd += ["-t", f"{dur:.3f}"]
    cmd += ["-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(dst)]
    run(cmd)
    return dst

def loudness(wav, step=0.5):
    """Return list of dBFS values, one per `step` seconds."""
    import wave
    with wave.open(str(wav)) as w:
        sr = w.getframerate()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    n = int(sr * step)
    if len(data) < n:
        return []
    k = len(data) // n
    blocks = data[: k * n].reshape(k, n)
    rms = np.sqrt((blocks ** 2).mean(axis=1) + 1e-12)
    return [round(float(20 * np.log10(r)), 1) for r in rms]

def transcribe_words(wav, prompt=None):
    """Whisper word list [{w, s, e}] in seconds relative to the wav start."""
    with tempfile.TemporaryDirectory() as td:
        base = os.path.join(td, "out")
        cmd = ["whisper-cli", "-m", str(WHISPER_MODEL), "-f", str(wav), "-ojf", "-of", base,
               "-np", "-l", "en", "-t", "6"]
        if prompt:
            cmd += ["--prompt", prompt[:200]]
        with WHISPER_LOCK:
            run(cmd, timeout=1800)
        d = json.load(open(base + ".json"))
    words = []
    for seg in d.get("transcription", []):
        for t in seg.get("tokens", []):
            txt = t.get("text", "")
            if txt.startswith("[_") or txt.startswith("<|"):
                continue
            s, e = t["offsets"]["from"] / 1000, t["offsets"]["to"] / 1000
            if txt.startswith(" ") or not words:
                if txt.strip():
                    words.append({"w": txt.strip(), "s": s, "e": e})
            else:
                words[-1]["w"] += txt
                words[-1]["e"] = e
    # drop whisper hallucination loops on silence
    clean = []
    for w in words:
        if len(clean) >= 4 and all(c["w"].lower() == w["w"].lower() for c in clean[-4:]):
            continue
        clean.append(w)
    return clean

def words_to_lines(words, gap=1.2, max_len=16):
    """Group words into short transcript lines [{s, e, text}]."""
    lines, cur = [], []
    for w in words:
        if cur and (w["s"] - cur[-1]["e"] > gap or len(cur) >= max_len or cur[-1]["w"][-1:] in ".?!"):
            lines.append({"s": cur[0]["s"], "e": cur[-1]["e"], "text": " ".join(x["w"] for x in cur)})
            cur = []
        cur.append(w)
    if cur:
        lines.append({"s": cur[0]["s"], "e": cur[-1]["e"], "text": " ".join(x["w"] for x in cur)})
    return lines

def grab_frame(src, t, dst, width=640):
    run(["ffmpeg", "-y", "-v", "error", "-ss", f"{max(0,t):.3f}", "-i", str(src), "-frames:v", "1",
         "-vf", f"scale={width}:-2", "-q:v", "4", str(dst)], check=False)
    return Path(dst).exists()

def contact_sheet(frames, labels, dst, cols=3):
    """frames: list of image paths. Writes one labelled grid image."""
    ims = [Image.open(f).convert("RGB") for f in frames if Path(f).exists()]
    if not ims:
        return None
    w, h = ims[0].size
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w, rows * h), "black")
    font = ImageFont.truetype(FONT_BOLD, max(16, w // 22))
    d = ImageDraw.Draw(sheet)
    for i, im in enumerate(ims):
        x, y = (i % cols) * w, (i // cols) * h
        sheet.paste(im.resize((w, h)), (x, y))
        d.rectangle([x, y, x + w // 3, y + w // 15], fill=(0, 0, 0))
        d.text((x + 6, y + 2), labels[i], fill=(255, 255, 0), font=font)
    sheet.save(dst, quality=85)
    return dst

def probe_duration(src):
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(src)], check=False)
    try:
        return float(r.stdout.strip())
    except Exception:
        return 0.0

def probe_video(src):
    r = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=width,height,r_frame_rate", "-of", "json", str(src)], check=False)
    try:
        s = json.loads(r.stdout)["streams"][0]
        num, den = s["r_frame_rate"].split("/")
        return int(s["width"]), int(s["height"]), float(num) / float(den)
    except Exception:
        return 1920, 1080, 30.0

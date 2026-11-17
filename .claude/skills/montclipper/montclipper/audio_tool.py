"""Music detection (and optional removal). Runs inside the tools-audio environment (torch, panns; demucs only for music: remove).

  tools-audio/bin/python audio_tool.py <in.wav (44.1k stereo)> <out_voice.wav> <words.json> <threshold>

Prints JSON: {"music_frac": 0..1, "cleaned": bool, "residual_frac": 0..1}
- music_frac: share of 3-second windows where the sound tagger hears music (on the original audio).
- If music_frac >= threshold: Demucs splits voice from music; the voice track is kept. Windows where
  music is still heard AND nobody is talking are muted. residual_frac = music left after cleaning.
"""
import json, sys, warnings
from pathlib import Path
warnings.filterwarnings("ignore")
import numpy as np

import os
_R = Path(__file__).resolve().parent.parent
_H = Path(os.environ["MONTCLIPPER_HOME"]).expanduser() if os.environ.get("MONTCLIPPER_HOME") else \
     (_R if (_R / "Upload to Socials").exists() else Path.home() / "MontClipper")
PANNS = _H / "models" / "panns" / "Cnn14_mAP=0.431.pth"

SONG_LABELS = ["Song", "Singing", "Rapping", "Vocal music", "Pop music", "Hip hop music", "Rock music",
               "Rhythm and blues", "Soul music", "Reggae", "Country", "Music of Africa"]

def tagger():
    import contextlib, io
    with contextlib.redirect_stdout(io.StringIO()):
        from panns_inference import AudioTagging, labels
        m = AudioTagging(checkpoint_path=str(PANNS), device="cpu")
    return m, labels.index("Music")

def song_score(m, y32, win=3.0):
    """How much it sounds like a real song (singing, rap, pop/hip hop...) rather than an instrumental game score."""
    from panns_inference import labels
    idx = [labels.index(k) for k in SONG_LABELS if k in labels]
    w = int(32000 * win)
    if len(y32) < w:
        y32 = np.pad(y32, (0, w - len(y32)))
    chunks = np.stack([y32[i:i + w] for i in range(0, max(1, len(y32) - w + 1), w)])
    import contextlib, io
    with contextlib.redirect_stdout(io.StringIO()):
        out, _ = m.inference(chunks)
    return float(out[:, idx].max())

def music_probs(m, mi, y32, win=3.0):
    w = int(32000 * win)
    if len(y32) < w:
        y32 = np.pad(y32, (0, w - len(y32)))
    chunks = np.stack([y32[i:i + w] for i in range(0, max(1, len(y32) - w + 1), w)])
    import contextlib, io
    with contextlib.redirect_stdout(io.StringIO()):
        out, _ = m.inference(chunks)
    return out[:, mi]

def clean_voice(voice, sr, words):
    """After separation, music can survive inside the voice stem (held melody notes, a sung hook).
    1) Held-note filter: speech pitch moves all the time, held music notes stay flat, so energy that is
       constant for half a second at one frequency is taken out.
    2) Gap gate: between words, anything much quieter than the talking is turned down 20 dB
       (laughs and screams are loud, so they stay)."""
    import librosa
    from scipy.ndimage import median_filter
    hop = 512
    kt = int(0.5 * sr / hop) | 1
    out = []
    for c in range(voice.shape[1]):
        S = librosa.stft(voice[:, c], n_fft=4096, hop_length=hop)
        mag = np.abs(S)
        held = median_filter(mag, size=(1, kt))
        mask = np.maximum(np.clip((mag - 0.9 * held) / (mag + 1e-9), 0, 1), 0.12)
        out.append(librosa.istft(S * mask, hop_length=hop, length=len(voice)))
    v = np.stack(out, 1)
    fr = int(0.05 * sr)
    n = len(v) // fr + 1
    lvl = np.array([20 * np.log10(np.sqrt(np.mean(v[i * fr:(i + 1) * fr] ** 2)) + 1e-9) for i in range(n)])
    talk = np.zeros(n, bool)
    for w in words:
        talk[max(0, int((w["s"] - 0.15) / 0.05)):int((w["e"] + 0.25) / 0.05) + 1] = True
    sp = np.median(lvl[talk]) if talk.any() else lvl.max()
    g = np.where(talk | (lvl > sp - 10), 1.0, 0.1)
    g = np.repeat(g, fr)[:len(v)]
    k = int(0.06 * sr)
    g = np.convolve(g, np.ones(k) / k, mode="same")
    return v * g[:, None]

def main(inp, outp, words_path, threshold):
    import librosa, soundfile as sf, torch
    words = json.loads(Path(words_path).read_text()) if Path(words_path).exists() else []
    m, mi = tagger()
    y32, _ = librosa.load(inp, sr=32000, mono=True)
    mp = music_probs(m, mi, y32)
    frac = float((mp >= 0.5).mean())
    res = {"music_frac": round(frac, 2), "cleaned": False, "residual_frac": round(frac, 2),
           "song": round(song_score(m, y32), 2) if frac > 0 else 0.0}
    if frac < threshold:
        print(json.dumps(res)); return
    from demucs.pretrained import get_model
    from demucs.apply import apply_model
    model = get_model("htdemucs")
    model.eval()
    wav, sr = sf.read(inp, always_2d=True)
    dev = "mps" if torch.backends.mps.is_available() else "cpu"
    vi = model.sources.index("vocals")
    def separate(t):
        r = t.mean(0)
        z = (t - r.mean()) / (r.std() + 1e-8)
        with torch.no_grad():
            out = apply_model(model, z[None], device=dev, split=True, overlap=0.25, progress=False)[0]
        return out[vi] * (r.std() + 1e-8) + r.mean()
    v = separate(torch.tensor(wav.T, dtype=torch.float32).repeat(2 // max(1, wav.shape[1]), 1))
    v = separate(v)                       # second pass removes most of what the first one leaves
    voice = v.cpu().numpy().T             # (n, 2)
    voice = clean_voice(voice, sr, words)
    sf.write(outp, voice, sr)
    v32 = librosa.resample(voice.mean(1), orig_sr=sr, target_sr=32000)
    left = music_probs(m, mi, v32)
    # strict: any window that still sounds like music, or a high average, means "not fully removed"
    res.update(cleaned=True, residual_frac=round(float((left >= 0.35).mean()), 2),
               residual_max=round(float(left.max()), 2), residual_mean=round(float(left.mean()), 2))
    print(json.dumps(res))

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4]) if len(sys.argv) > 4 else 0.5)

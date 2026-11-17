#!/usr/bin/env python3
"""visual-clipper — caption builder.

Takes the ingest manifest's transcript, slices it to a clip's [start,end],
rebases timestamps to clip-local (0-based), and writes a punchy short-form SRT:
short UPPERCASE word-chunks that pop on screen (TikTok/Reels/Shorts style).

Usage:
  python make_srt.py --manifest <manifest.json> --start 73.2 --end 91.6 \
      --out clip_01.srt [--words-per-chunk 2] [--no-upper]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _fmt(t: float) -> str:
    if t < 0:
        t = 0.0
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    ms = int(round((t - int(t)) * 1000))
    if ms == 1000:
        s += 1
        ms = 0
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _chunk(words: list[str], n: int) -> list[list[str]]:
    return [words[i:i + n] for i in range(0, len(words), n)]


def _norm(w: str) -> str:
    """Comparison key for a word: lowercased alphanumerics only."""
    return "".join(ch for ch in w.lower() if ch.isalnum())


def _dedup_rolling(transcript: list[dict], start: float, end: float
                   ) -> list[tuple[str, float, float]]:
    """Collapse YouTube-style ROLLING auto-captions into a clean word timeline.

    Rolling captions repeat the boundary words between consecutive cues
    ("here's your monthly" -> "here's your monthly reminder ..."), which makes a
    naive chunker emit the same words twice. For each segment we find the largest
    overlap between the words already emitted and this segment's leading words,
    and keep only the NEW tail — so every word appears exactly once, in order.

    Returns (display_word, word_start, word_end) in SOURCE seconds.
    """
    emitted_norm: list[str] = []
    timeline: list[tuple[str, float, float]] = []
    for seg in sorted(transcript, key=lambda s: float(s.get("start", 0))):
        s, e = float(seg["start"]), float(seg["end"])
        if e < start - 1.0 or s > end + 1.0:          # a little slack at edges
            continue
        words = (seg.get("text") or "").split()
        if not words:
            continue
        norm = [_norm(w) for w in words]
        # largest k where the tail of what we've emitted == the head of this seg
        maxk = min(len(words), len(emitted_norm), 16)
        k = 0
        for cand in range(maxk, 0, -1):
            if emitted_norm[-cand:] == norm[:cand]:
                k = cand
                break
        new_words = words[k:]
        if not new_words:
            continue
        dur = max(0.01, e - s)
        per = dur / len(new_words)            # spread the new tail across the seg
        for i, w in enumerate(new_words):
            timeline.append((w, s + i * per, s + (i + 1) * per))
        emitted_norm.extend(norm[k:])
    # keep only words that actually fall in the clip window
    return [(w, ws, we) for (w, ws, we) in timeline if we > start and ws < end]


def build(transcript: list[dict], start: float, end: float,
          words_per_chunk: int, upper: bool, lead: float = 0.0) -> list[tuple[float, float, str]]:
    # 1) de-duplicated, de-rolled word timeline in source time
    timeline = _dedup_rolling(transcript, start, end)
    if not timeline:
        return []

    # 2) group consecutive words into short on-screen chunks, clip-local time
    cues: list[tuple[float, float, str]] = []
    for grp in _chunk(timeline, max(1, words_per_chunk)):
        cs = max(0.0, (grp[0][1] - start) - lead)
        ce = max(cs + 0.2, (grp[-1][2] - start) - lead)
        text = " ".join(w for (w, _, _) in grp)
        cues.append((cs, ce, text.upper() if upper else text))

    # 3) guarantee no two captions are ever on screen at once: clamp each cue's
    #    end to just before the next cue's start.
    cues.sort(key=lambda c: c[0])
    cleaned: list[tuple[float, float, str]] = []
    for i, (cs, ce, text) in enumerate(cues):
        if i + 1 < len(cues):
            ce = min(ce, cues[i + 1][0])
        if ce <= cs:                      # degenerate (cues at same instant)
            ce = cs + 0.04
            if i + 1 < len(cues):
                ce = min(ce, cues[i + 1][0])
        if ce > cs:
            cleaned.append((cs, ce, text))
    return cleaned


def main() -> None:
    ap = argparse.ArgumentParser(description="visual-clipper caption builder")
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--start", type=float, required=True)
    ap.add_argument("--end", type=float, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--words-per-chunk", type=int, default=2)
    ap.add_argument("--no-upper", action="store_true")
    ap.add_argument("--lead", type=float, default=0.3,
                    help="advance captions earlier by N seconds to counter auto-caption lag (default 0.3)")
    args = ap.parse_args()

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    transcript = manifest.get("transcript", [])
    cues = build(transcript, args.start, args.end, args.words_per_chunk, not args.no_upper, args.lead)

    out = Path(args.out)
    if not cues:
        out.write_text("", encoding="utf-8")
        print(json.dumps({"out": str(out), "cues": 0,
                          "note": "no transcript overlap — clip will have no burned captions"}))
        return

    lines = []
    for i, (cs, ce, text) in enumerate(cues, 1):
        lines.append(str(i))
        lines.append(f"{_fmt(cs)} --> {_fmt(ce)}")
        lines.append(text)
        lines.append("")
    out.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"out": str(out), "cues": len(cues)}))


if __name__ == "__main__":
    main()

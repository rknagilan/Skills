#!/usr/bin/env python3
"""visual-clipper — CAPTION LINT (deterministic quality gate).

Scans a finished SRT for the failure modes that make burned captions look broken
— the ones we actually hit: overlapping cues (two captions on screen at once) and
ROLLING DUPLICATES (the same words repeated across consecutive cues, the YouTube
auto-caption artifact). Also flags empty cues, too-fast reading speed, and absurd
durations.

This is the cheap, exact guard that runs before the LLM caption-judge ever looks
at pixels: timing and duplication are math, so we check them with math and fail
loudly. Exit code 0 = clean, 1 = problems found (report on stdout as JSON).

Usage:
  python caption_lint.py --srt clip_01.srt [--max-cps 24] [--max-dur 7] [--json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_TS = re.compile(r"(\d\d):(\d\d):(\d\d),(\d{3})")


def _parse_ts(s: str) -> float:
    m = _TS.search(s)
    if not m:
        return -1.0
    h, mi, se, ms = (int(x) for x in m.groups())
    return h * 3600 + mi * 60 + se + ms / 1000.0


def parse_srt(text: str) -> list[dict]:
    cues: list[dict] = []
    blocks = re.split(r"\n\s*\n", text.strip())
    for b in blocks:
        lines = [ln for ln in b.splitlines() if ln.strip() != ""]
        if len(lines) < 2:
            continue
        # find the timing line (the one with -->)
        ti = next((i for i, ln in enumerate(lines) if "-->" in ln), None)
        if ti is None:
            continue
        a, _, c = lines[ti].partition("-->")
        start, end = _parse_ts(a), _parse_ts(c)
        body = " ".join(lines[ti + 1:]).strip()
        cues.append({"start": start, "end": end, "text": body})
    return cues


def _norm_words(text: str) -> list[str]:
    return ["".join(ch for ch in w.lower() if ch.isalnum()) for w in text.split()]


def lint(cues: list[dict], max_cps: float, max_dur: float, min_dur: float) -> list[dict]:
    problems: list[dict] = []
    if not cues:
        return [{"cue": 0, "kind": "empty_file", "detail": "no cues parsed"}]

    for i, c in enumerate(cues, 1):
        s, e, txt = c["start"], c["end"], c["text"]

        if s < 0 or e < 0:
            problems.append({"cue": i, "kind": "bad_timestamp", "detail": "unparseable time"})
            continue
        if not txt:
            problems.append({"cue": i, "kind": "empty_text", "detail": "cue has no text"})
        if e <= s:
            problems.append({"cue": i, "kind": "nonpositive_duration",
                             "detail": f"{s:.3f}->{e:.3f}"})
        dur = e - s
        nwords = len(txt.split())
        if dur > max_dur:
            problems.append({"cue": i, "kind": "too_long",
                             "detail": f"{dur:.2f}s on screen (>{max_dur}s) — stuck caption"})
        # too_brief: a chunk flashing below the perception floor (sub-frame blink).
        # Short word-pop chunks are meant to flash, so we only flag truly imperceptible.
        if 0 < dur < min_dur:
            problems.append({"cue": i, "kind": "too_brief",
                             "detail": f"{dur*1000:.0f}ms on screen (<{min_dur*1000:.0f}ms) — blinks"})
        # reading speed (cps) is only meaningful for LONG cues — a full sentence shown
        # too fast. Micro word-pop chunks are read cumulatively, so they're exempt.
        nchars = len(txt)
        if nwords >= 6 and dur > 0.05 and nchars / dur > max_cps:
            problems.append({"cue": i, "kind": "too_fast",
                             "detail": f"{nchars/dur:.0f} chars/s over {nwords} words (>{max_cps})"})

        if i < len(cues):
            nxt = cues[i]  # 0-based next
            # OVERLAP: two captions visible at once
            if e > nxt["start"] + 0.001:
                problems.append({"cue": i, "kind": "overlap",
                                 "detail": f"ends {e:.3f} after next starts {nxt['start']:.3f}"})
            # EXACT DUPLICATE consecutive text
            if _norm_words(txt) and _norm_words(txt) == _norm_words(nxt["text"]):
                problems.append({"cue": i, "kind": "duplicate_text",
                                 "detail": f"same text as cue {i+1}: {txt!r}"})
            # ROLLING DUPLICATE: this cue's words reappear as the head/tail of next
            a, bwords = _norm_words(txt), _norm_words(nxt["text"])
            if a and bwords:
                # next cue starts by repeating the tail of this cue
                overlap = 0
                for k in range(1, min(len(a), len(bwords)) + 1):
                    if a[-k:] == bwords[:k]:
                        overlap = k
                if overlap >= 2:
                    problems.append({"cue": i, "kind": "rolling_repeat",
                                     "detail": f"{overlap} words repeat into cue {i+1} "
                                               f"({' '.join(a[-overlap:])})"})
    return problems


def main() -> None:
    ap = argparse.ArgumentParser(description="visual-clipper caption linter")
    ap.add_argument("--srt", required=True)
    ap.add_argument("--max-cps", type=float, default=24.0,
                    help="max characters-per-second reading speed (default 24)")
    ap.add_argument("--max-dur", type=float, default=7.0,
                    help="max seconds a single cue may stay on screen (default 7)")
    ap.add_argument("--min-dur", type=float, default=0.10,
                    help="min seconds a cue must stay on screen before it's an imperceptible blink (default 0.10)")
    ap.add_argument("--json", action="store_true", help="emit full JSON report")
    args = ap.parse_args()

    path = Path(args.srt)
    if not path.exists() or path.stat().st_size == 0:
        print(json.dumps({"srt": str(path), "ok": True, "cues": 0,
                          "note": "no/empty SRT — nothing to burn"}))
        return

    cues = parse_srt(path.read_text(encoding="utf-8"))
    problems = lint(cues, args.max_cps, args.max_dur, args.min_dur)
    report = {
        "srt": str(path),
        "cues": len(cues),
        "ok": len(problems) == 0,
        "problem_count": len(problems),
        "problems": problems,
    }
    if args.json or problems:
        print(json.dumps(report, indent=2))
    else:
        print(json.dumps({"srt": str(path), "cues": len(cues), "ok": True}))

    if problems:
        kinds = sorted({p["kind"] for p in problems})
        sys.stderr.write(f"[caption_lint] FAIL: {len(problems)} problem(s): {', '.join(kinds)}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()

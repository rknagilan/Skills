#!/usr/bin/env python3
"""visual-clipper — DETECT stage (content-aware framing).

Watches a clip with OpenCV and reports WHERE the important content is, so the
camera/reframe stage stops guessing crop centers by eye. Two jobs:

1. Face track  — find the speaker's face across the clip and emit a per-sample
   (t, cx, cy) center track + a median center. Crop-fill reframing can follow
   this instead of a hand-typed cx/cy (the "framings are a little off" fix).

2. Layout sense — decide whether this clip is a SCREEN-SHARE + WEBCAM PIP (one
   face living in a stable corner box that's a minority of the frame) vs a plain
   talking-head / full-frame shot. For screencasts it emits a `speaker_box`
   (the webcam region) and a `screen_box` (the whole frame) so the renderer can
   build a stacked split layout — screen on top, speaker enlarged on the bottom —
   instead of wasting 40% of a 9:16 frame on blurred bars.

This mirrors how AutoFlip / Opus-style reframers work: detect salient content
(faces), pick a layout, then crop — rather than a fixed center.

Output: JSON to stdout (and --out if given). Deterministic: fixed sample grid,
no randomness, no network.

Usage:
  python detect.py --source SRC.mp4 --start 8.5 --end 26.7 [--samples 24] [--out det.json]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np


def _probe_dims(src: str) -> tuple[int, int]:
    proc = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", src],
        capture_output=True, text=True,
    )
    data = json.loads(proc.stdout or "{}")
    vs = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
    return int(vs["width"]), int(vs["height"])


def _grab(src: str, t: float, W: int, H: int) -> "np.ndarray | None":
    """Grab one BGR frame at source time t via ffmpeg pipe (robust seek)."""
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{t:.3f}",
         "-i", src, "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
        capture_output=True,
    )
    if proc.returncode != 0 or not proc.stdout:
        return None
    buf = np.frombuffer(proc.stdout, dtype=np.uint8)
    if buf.size < W * H * 3:
        return None
    return buf[: W * H * 3].reshape(H, W, 3)


def _load_cascades() -> list:
    base = cv2.data.haarcascades
    names = ["haarcascade_frontalface_default.xml", "haarcascade_frontalface_alt2.xml"]
    out = []
    for n in names:
        c = cv2.CascadeClassifier(base + n)
        if not c.empty():
            out.append(c)
    return out


def _detect_faces(gray, cascades, min_frac: float) -> list[tuple[int, int, int, int]]:
    H, W = gray.shape[:2]
    minsz = max(24, int(min(W, H) * min_frac))
    faces: list[tuple[int, int, int, int]] = []
    for c in cascades:
        found = c.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=6,
                                   minSize=(minsz, minsz))
        for (x, y, w, h) in found:
            faces.append((int(x), int(y), int(w), int(h)))
        if faces:
            break
    return faces


def main() -> None:
    ap = argparse.ArgumentParser(description="visual-clipper content detector")
    ap.add_argument("--source", required=True)
    ap.add_argument("--start", type=float, required=True)
    ap.add_argument("--end", type=float, required=True)
    ap.add_argument("--samples", type=int, default=24)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    W, H = _probe_dims(args.source)
    cascades = _load_cascades()
    if not cascades:
        raise SystemExit("[detect] no haar cascades found in opencv data dir")

    dur = max(0.1, args.end - args.start)
    n = max(6, args.samples)
    times = [args.start + dur * (i + 0.5) / n for i in range(n)]

    centers = []          # (t_local, cx, cy, area_frac) largest face per frame
    all_boxes = []        # normalized boxes of the largest face per frame
    for t in times:
        frame = _grab(args.source, t, W, H)
        if frame is None:
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        faces = _detect_faces(gray, cascades, min_frac=0.04)
        if not faces:
            continue
        # largest face = the speaker
        x, y, w, h = max(faces, key=lambda b: b[2] * b[3])
        cx = (x + w / 2.0) / W
        cy = (y + h / 2.0) / H
        centers.append({"t": round(t - args.start, 3), "cx": round(cx, 4),
                        "cy": round(cy, 4)})
        all_boxes.append((x / W, y / H, w / W, h / H))

    result: dict = {
        "source_dims": f"{W}x{H}",
        "clip_start": args.start,
        "clip_end": args.end,
        "samples": n,
        "faces_found": len(all_boxes),
        "face_centers": centers,
    }

    if all_boxes:
        arr = np.array(all_boxes)            # cols: x,y,w,h (normalized)
        med = np.median(arr, axis=0)
        fcx = float(med[0] + med[2] / 2.0)
        fcy = float(med[1] + med[3] / 2.0)
        result["face_center_median"] = {"cx": round(fcx, 4), "cy": round(fcy, 4)}

        # --- webcam-pip heuristic --------------------------------------------
        # A webcam pip = a face that (a) is consistently present, (b) lives in a
        # stable spot (low spread), and (c) sits off-center in a corner/side,
        # i.e. the face center is biased away from the middle. If so, the talking
        # head is a small inset over a screen-share -> recommend split layout.
        spread = float(np.mean(np.std(arr[:, :2], axis=0)))   # positional jitter
        off_center = (abs(fcx - 0.5) ** 2 + abs(fcy - 0.5) ** 2) ** 0.5
        face_w = float(med[2])
        present = len(all_boxes) / n
        is_pip = (present >= 0.5 and spread < 0.06 and off_center > 0.18
                  and face_w < 0.22)
        result["webcam_pip"] = is_pip
        result["pip_signals"] = {
            "present_frac": round(present, 2), "pos_spread": round(spread, 4),
            "off_center": round(off_center, 3), "face_w": round(face_w, 4),
        }

        if is_pip:
            # Build the speaker (webcam) box around the face: head + shoulders,
            # clamped to the frame. Pad generously below for shoulders.
            x0, y0, w0, h0 = med
            sx = max(0.0, x0 - 0.9 * w0)
            sy = max(0.0, y0 - 0.7 * h0)
            ex = min(1.0, x0 + w0 + 0.9 * w0)
            ey = min(1.0, y0 + h0 + 1.8 * h0)
            result["speaker_box"] = {"x": round(sx, 4), "y": round(sy, 4),
                                     "w": round(ex - sx, 4), "h": round(ey - sy, 4)}
            result["screen_box"] = {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0}
            result["recommend_fill"] = "split"
        else:
            result["recommend_fill"] = "crop"   # plain face -> face-aware crop
    else:
        # no faces at all -> probably a pure screen/slide: show it whole
        result["recommend_fill"] = "blur"

    txt = json.dumps(result, indent=2)
    if args.out:
        Path(args.out).write_text(txt, encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

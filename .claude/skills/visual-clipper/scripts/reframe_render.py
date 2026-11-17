#!/usr/bin/env python3
"""visual-clipper — CAMERA stage renderer.

Turns a reframe PLAN (crop/zoom keyframes that Claude wrote after watching the
clip's frames) into a finished 9:16 vertical short. This is the piece that lets
the "camera" move: follow the speaker, punch in on the emphasis line, pull back
for the reveal — instead of one static crop for the whole clip.

How it works
------------
A 9:16 crop window slides over the landscape source. Each keyframe gives the
window's CENTER (cx,cy as 0..1 of the source frame) and a ZOOM (1.0 = widest
9:16 crop that fits; >1 = tighter punch-in). Between consecutive keyframes the
window moves linearly, so the result reads as a smooth camera move. We render
one short segment per keyframe interval (simple 2-point lerp expressions), concat
them, then do a final pass that muxes the original clip audio and burns captions.

If the plan has <2 keyframes, or --mode static is passed, it renders one stable
crop from the first keyframe (the safe fallback the framing-judge collapses to).

Usage:
  python reframe_render.py --source SRC.mp4 --start 73.2 --end 91.6 \
      --plan plan.json --out clip_01.mp4 [--srt clip_01.srt] \
      [--mode plan|static] [--target 1080x1920] [--crf 18] [--fps 30]

Plan JSON: see ../templates/reframe-plan.schema.json
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(f"[reframe] ffmpeg failed:\n{' '.join(cmd)}\n{proc.stderr.strip()}")


def _probe_dims(src: str) -> tuple[int, int]:
    proc = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", src],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise SystemExit(f"[reframe] ffprobe failed: {proc.stderr.strip()}")
    data = json.loads(proc.stdout or "{}")
    vs = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
    return int(vs["width"]), int(vs["height"])


def _even(x: float) -> int:
    return int(round(x / 2.0)) * 2


def _window(cx: float, cy: float, zoom: float, W: int, H: int,
            ar_w: int, ar_h: int) -> tuple[int, int, int, int]:
    """Compute an integer (w,h,x,y) crop window of aspect ar_w:ar_h at the given
    center and zoom, clamped inside the source frame."""
    zoom = max(1.0, float(zoom))
    # widest window of the target aspect that fits the source
    if W * ar_h >= H * ar_w:          # source wider than target aspect -> height-bound
        h0 = H
        w0 = H * ar_w / ar_h
    else:                              # source taller -> width-bound
        w0 = W
        h0 = W * ar_h / ar_w
    w = _even(min(W, w0 / zoom))
    h = _even(min(H, h0 / zoom))
    # keep exact aspect after rounding by deriving h from w
    h = _even(min(H, w * ar_h / ar_w))
    x = cx * W - w / 2.0
    y = cy * H - h / 2.0
    x = _even(max(0, min(W - w, x)))
    y = _even(max(0, min(H - h, y)))
    return w, h, x, y


def _seg_filter(a, b, target_w, target_h) -> str:
    """Linear-interp crop expression for one segment, t local to the segment."""
    (w0, h0, x0, y0, d) = a
    (w1, h1, x1, y1, _) = b
    d = max(d, 0.04)

    def lerp(v0, v1):
        if v0 == v1:
            return f"{v0}"
        return f"({v0}+({v1 - v0})*min(t/{d:.4f},1))"

    return (
        f"crop=w='{lerp(w0, w1)}':h='{lerp(h0, h1)}':"
        f"x='{lerp(x0, x1)}':y='{lerp(y0, y1)}',"
        f"scale={target_w}:{target_h}:flags=bicubic,setsar=1,format=yuv420p"
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="visual-clipper camera renderer")
    ap.add_argument("--source", required=True)
    ap.add_argument("--start", type=float, required=True)
    ap.add_argument("--end", type=float, required=True)
    ap.add_argument("--plan", required=True, help="reframe plan JSON")
    ap.add_argument("--out", required=True)
    ap.add_argument("--srt", default=None, help="optional SRT to burn (clip-local timing)")
    ap.add_argument("--mode", choices=["plan", "static"], default="plan")
    ap.add_argument("--fill", choices=["crop", "blur", "split"], default="crop",
                    help="crop = full-bleed 9:16 with moving camera (tight); "
                         "blur = show the WHOLE frame fit-to-width with blurred bars (zoomed out); "
                         "split = stacked screencast layout — screen on top, the webcam "
                         "speaker enlarged on the bottom (no dead bars)")
    ap.add_argument("--speaker-box", default=None,
                    help="[split] webcam region as normalized 'x,y,w,h' (0..1). "
                         "Get it from detect.py's speaker_box.")
    ap.add_argument("--screen-box", default="0,0,1,1",
                    help="[split] screen region as normalized 'x,y,w,h' (default whole frame)")
    ap.add_argument("--split-ratio", type=float, default=0.0,
                    help="[split] top-zone (screen) fraction of height. 0 = auto: fit the "
                         "screen to width with NO crop and give the rest to the speaker.")
    ap.add_argument("--blur-zoom", type=float, default=1.3,
                    help="[blur fill] enlarge the content by this factor so the blurred "
                         "bars are smaller (1.0 = pure fit-to-width; 1.3 trims sides slightly)")
    ap.add_argument("--zoom-out", type=float, default=0.08,
                    help="[crop fill] pull the framing back by this fraction, filling the "
                         "thin margin with blur (0 = full-bleed; 0.08 = a touch looser)")
    ap.add_argument("--target", default="1080x1920")
    ap.add_argument("--crf", type=int, default=18)
    ap.add_argument("--fps", type=int, default=30)
    args = ap.parse_args()

    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise SystemExit("[reframe] ffmpeg/ffprobe not found on PATH.")

    target_w, target_h = (int(v) for v in args.target.lower().split("x"))
    ar_w, ar_h = target_w, target_h
    clip_dur = max(0.1, args.end - args.start)
    W, H = _probe_dims(args.source)

    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    kfs = sorted(plan.get("keyframes", []), key=lambda k: float(k.get("t", 0)))
    if not kfs:
        kfs = [{"t": 0.0, "cx": 0.5, "cy": 0.5, "zoom": 1.0}]

    # clamp keyframe times into the clip, ensure first at 0 / last at clip_dur
    for k in kfs:
        k["t"] = max(0.0, min(clip_dur, float(k.get("t", 0.0))))
    if kfs[0]["t"] > 0:
        kfs.insert(0, {**kfs[0], "t": 0.0})
    if kfs[-1]["t"] < clip_dur:
        kfs.append({**kfs[-1], "t": clip_dur})

    static = args.mode == "static" or len(kfs) < 2
    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="reframe_") as td:
        tmp = Path(td)

        # ---- 1. render cropped (silent) video ----------------------------------
        if args.fill == "split":
            # Stacked screencast layout (Opus-style "screenshare mode"):
            #   TOP  = the screen, fit to full width (tweets/code stay readable)
            #   BOT  = the webcam speaker box, enlarged to fill the rest
            # Fills the whole 9:16 frame with real content instead of blurred bars.
            def _box(s):
                v = [float(x) for x in s.split(",")]
                return v[0], v[1], v[2], v[3]

            if not args.speaker_box:
                raise SystemExit("[reframe] --fill split needs --speaker-box "
                                 "(run detect.py and pass its speaker_box).")
            sbx, sby, sbw, sbh = _box(args.speaker_box)
            scx, scy, scw, sch = _box(args.screen_box)

            screen_px_w = max(2, W * scw)
            screen_px_h = max(2, H * sch)
            if args.split_ratio and args.split_ratio > 0:
                top_h = _even(target_h * min(0.85, max(0.3, args.split_ratio)))
            else:
                # auto: top height = screen fit-to-width height (no crop)
                top_h = _even(target_w * screen_px_h / screen_px_w)
            top_h = max(2, min(target_h - 2, top_h))
            bot_h = target_h - top_h

            # screen: fit to width if auto (no crop); cover if a ratio was forced
            if args.split_ratio and args.split_ratio > 0:
                top_chain = (
                    f"crop={_even(W*scw)}:{_even(H*sch)}:{_even(W*scx)}:{_even(H*scy)},"
                    f"scale={target_w}:{top_h}:force_original_aspect_ratio=increase,"
                    f"crop={target_w}:{top_h}")
            else:
                top_chain = (
                    f"crop={_even(W*scw)}:{_even(H*sch)}:{_even(W*scx)}:{_even(H*scy)},"
                    f"scale={target_w}:{top_h}")
            # speaker: cover-fill the bottom zone, light sharpen to fight upscale soft
            bot_chain = (
                f"crop={_even(W*sbw)}:{_even(H*sbh)}:{_even(W*sbx)}:{_even(H*sby)},"
                f"scale={target_w}:{bot_h}:force_original_aspect_ratio=increase,"
                f"crop={target_w}:{bot_h},unsharp=5:5:0.6:5:5:0.0")
            vf = (f"[0:v]{top_chain},setsar=1[top];"
                  f"[0:v]{bot_chain},setsar=1[bot];"
                  f"[top][bot]vstack=inputs=2,format=yuv420p")
            video_only = tmp / "video.mp4"
            _run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-ss", f"{args.start:.3f}", "-t", f"{clip_dur:.3f}", "-i", args.source,
                "-filter_complex", vf, "-r", str(args.fps), "-an",
                "-c:v", "libx264", "-preset", "fast", "-crf", str(args.crf),
                str(video_only),
            ])
        elif args.fill == "blur":
            # Zoomed-out style: fit the WHOLE landscape frame to the target width and
            # fill the top/bottom with a blurred, scaled copy. Nothing is cropped, so
            # the camera keyframes don't apply — this is the "show everything" look.
            # foreground enlarged by --blur-zoom (then center-cropped back to width)
            # so the blurred bars shrink. 1.0 = pure fit-to-width (biggest bars).
            fg_w = _even(target_w * max(1.0, args.blur_zoom))
            vf = (
                "split=2[bg][fg];"
                f"[bg]scale={target_w}:{target_h}:force_original_aspect_ratio=increase,"
                f"crop={target_w}:{target_h},boxblur=40:1,eq=brightness=-0.08[bg];"
                f"[fg]scale={fg_w}:-2,crop={target_w}:ih:(iw-{target_w})/2:0[fg];"
                "[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1,format=yuv420p"
            )
            video_only = tmp / "video.mp4"
            _run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-ss", f"{args.start:.3f}", "-t", f"{clip_dur:.3f}", "-i", args.source,
                "-filter_complex", vf, "-r", str(args.fps), "-an",
                "-c:v", "libx264", "-preset", "fast", "-crf", str(args.crf),
                str(video_only),
            ])
        elif static:
            k = kfs[0]
            w, h, x, y = _window(k["cx"], k["cy"], k.get("zoom", 1.0), W, H, ar_w, ar_h)
            vf = (f"crop={w}:{h}:{x}:{y},scale={target_w}:{target_h}:flags=bicubic,"
                  f"setsar=1,format=yuv420p")
            video_only = tmp / "video.mp4"
            _run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-ss", f"{args.start:.3f}", "-t", f"{clip_dur:.3f}", "-i", args.source,
                "-vf", vf, "-r", str(args.fps), "-an",
                "-c:v", "libx264", "-preset", "fast", "-crf", str(args.crf),
                str(video_only),
            ])
        else:
            seg_files = []
            for i in range(len(kfs) - 1):
                ka, kb = kfs[i], kfs[i + 1]
                t0, t1 = ka["t"], kb["t"]
                if t1 - t0 < 0.04:
                    continue
                wa = _window(ka["cx"], ka["cy"], ka.get("zoom", 1.0), W, H, ar_w, ar_h)
                wb = _window(kb["cx"], kb["cy"], kb.get("zoom", 1.0), W, H, ar_w, ar_h)
                a = (*wa, t1 - t0)
                b = (*wb, t1 - t0)
                vf = _seg_filter(a, b, target_w, target_h)
                seg = tmp / f"seg_{i:03d}.mp4"
                _run([
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-ss", f"{args.start + t0:.3f}", "-t", f"{t1 - t0:.3f}", "-i", args.source,
                    "-vf", vf, "-r", str(args.fps), "-an",
                    "-c:v", "libx264", "-preset", "fast", "-crf", str(args.crf),
                    "-video_track_timescale", "90000",
                    str(seg),
                ])
                seg_files.append(seg)
            if not seg_files:
                raise SystemExit("[reframe] no renderable segments from plan.")
            concat_list = tmp / "concat.txt"
            concat_list.write_text(
                "".join(f"file '{p.as_posix()}'\n" for p in seg_files), encoding="utf-8")
            video_only = tmp / "video.mp4"
            _run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "concat", "-safe", "0", "-i", str(concat_list),
                "-c", "copy", str(video_only),
            ])

        # ---- 1b. crop zoom-out: pull the full-bleed frame back a touch ---------
        # Only for crop/static (blur already shows everything). Scales the 1080x1920
        # content down by --zoom-out and fills the thin margin with a blurred copy.
        if args.fill == "crop" and args.zoom_out and args.zoom_out > 0:
            zo = max(0.5, 1.0 - float(args.zoom_out))
            inner_w = _even(target_w * zo)
            inner_h = _even(target_h * zo)
            padded = tmp / "video_padded.mp4"
            _run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(video_only),
                "-filter_complex",
                ("split=2[bg][fg];"
                 f"[bg]boxblur=40:1,eq=brightness=-0.08[bg];"
                 f"[fg]scale={inner_w}:{inner_h}[fg];"
                 "[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1,format=yuv420p"),
                "-r", str(args.fps), "-an",
                "-c:v", "libx264", "-preset", "fast", "-crf", str(args.crf),
                str(padded),
            ])
            video_only = padded

        # ---- 2. extract clip audio --------------------------------------------
        audio = tmp / "audio.m4a"
        has_audio = True
        ap_proc = subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-ss", f"{args.start:.3f}", "-t", f"{clip_dur:.3f}", "-i", args.source,
            "-vn", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", str(audio),
        ], capture_output=True, text=True)
        if ap_proc.returncode != 0 or not audio.exists():
            has_audio = False

        # ---- 3. final pass: mux audio (+ burn captions if provided) -----------
        final_cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(video_only)]
        if has_audio:
            final_cmd += ["-i", str(audio)]

        burn = args.srt and Path(args.srt).exists() and Path(args.srt).stat().st_size > 0
        if burn:
            # run with cwd at the SRT's dir and pass bare filename to dodge the
            # Windows drive-colon escaping problem in the subtitles filter.
            srt_path = Path(args.srt).resolve()
            cwd = str(srt_path.parent)
            # NOTE: when burning an SRT, libass assumes a 384x288 script canvas and
            # scales FontSize/MarginV to the real frame (here ~6.7x for 1920 tall).
            # So these are script-space units: FontSize ~9 -> ~60px, MarginV ~60 ->
            # ~400px up from the bottom (TikTok/Reels lower-third safe zone).
            style = ("FontName=Arial,FontSize=9,Bold=1,PrimaryColour=&H00FFFFFF,"
                     "OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=0,"
                     "Alignment=2,MarginV=60")
            final_cmd += ["-vf", f"subtitles={srt_path.name}:force_style='{style}'",
                          "-c:v", "libx264", "-preset", "fast", "-crf", str(args.crf)]
        else:
            cwd = None
            final_cmd += ["-c:v", "copy"]

        if has_audio:
            final_cmd += ["-map", "0:v:0", "-map", "1:a:0", "-c:a", "aac", "-b:a", "192k", "-shortest"]
        else:
            final_cmd += ["-map", "0:v:0", "-an"]
        final_cmd += ["-movflags", "+faststart", str(out)]

        proc = subprocess.run(final_cmd, capture_output=True, text=True, cwd=cwd)
        if proc.returncode != 0:
            raise SystemExit(f"[reframe] final mux failed:\n{' '.join(final_cmd)}\n{proc.stderr.strip()}")

    print(json.dumps({
        "out": str(out),
        "mode": "static" if static else "plan",
        "keyframes": len(kfs),
        "source_dims": f"{W}x{H}",
        "target_dims": f"{target_w}x{target_h}",
        "duration": round(clip_dur, 2),
        "captions_burned": bool(burn),
        "audio": has_audio,
    }, indent=2))


if __name__ == "__main__":
    main()

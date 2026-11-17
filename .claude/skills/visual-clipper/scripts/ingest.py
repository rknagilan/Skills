#!/usr/bin/env python3
"""visual-clipper — INGEST stage.

Wraps the `watch` skill's download/frames/transcribe machinery to produce a
single manifest.json that the SCOUT stage (Claude vision) reads:

  - downloads the source (yt-dlp) or resolves a local file
  - probes dimensions/duration
  - extracts timestamped frames at an auto-scaled fps (so Claude can SEE it)
  - parses native captions to a timestamped transcript (Whisper fallback)

Outputs everything under <project-root>/<slug>/ and prints a compact summary
plus the manifest path. Nothing here calls a model — it just builds artifacts.

Usage:
  python ingest.py "<url-or-path>" --slug <slug> \
      [--project-root DIR] [--resolution 768] [--max-frames 120] \
      [--start T] [--end T] [--no-whisper]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path


def _load_watch_scripts():
    """Import download.py / frames.py / transcribe.py from the installed watch skill."""
    watch_dir = Path.home() / ".claude" / "skills" / "watch" / "scripts"
    if not watch_dir.exists():
        raise SystemExit(
            f"[visual-clipper] watch skill scripts not found at {watch_dir}. "
            "Install the /watch skill first."
        )
    mods = {}
    for name in ("download", "frames", "transcribe"):
        spec = importlib.util.spec_from_file_location(f"watch_{name}", watch_dir / f"{name}.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        mods[name] = mod
    return watch_dir, mods


def _download(source: str, dl_dir: Path, download_mod) -> dict:
    """Download a URL with the YouTube remote challenge solver enabled, or resolve
    a local file. Mirrors watch's download_url but adds --remote-components, which
    YouTube now requires (the n-challenge solver) or the video reads as 'unavailable'."""
    if not download_mod.is_url(source):
        return download_mod.download(source, dl_dir)

    import shutil as _sh
    if _sh.which("yt-dlp") is None:
        raise SystemExit("yt-dlp is not installed.")
    dl_dir.mkdir(parents=True, exist_ok=True)
    out_template = str(dl_dir / "video.%(ext)s")
    cmd = [
        "yt-dlp",
        "--remote-components", "ejs:github",   # enable JS/n-challenge solver
        "--no-update",
        "-N", "8",
        "-f", "bv*[height<=720]+ba/b[height<=720]/bv+ba/b",
        "--merge-output-format", "mp4",
        "--write-info-json", "--write-subs", "--write-auto-subs",
        "--sub-langs", "en,en-US,en-GB,en-orig",
        "--sub-format", "vtt", "--convert-subs", "vtt",
        "--no-playlist", "--ignore-errors",
        "-o", out_template, "--", source,
    ]
    result = subprocess.run(cmd, stdout=sys.stderr, stderr=sys.stderr)
    video = download_mod._pick_video(dl_dir)
    if video is None:
        raise SystemExit(
            f"yt-dlp did not produce a video file in {dl_dir} (exit {result.returncode}). "
            "If this is an n-challenge error, ensure a JS runtime (node) is installed."
        )
    subtitle = download_mod._pick_subtitle(dl_dir)
    info_path = dl_dir / "video.info.json"
    info: dict = {"url": source}
    if info_path.exists():
        try:
            raw = json.loads(info_path.read_text(encoding="utf-8"))
            info = {
                "title": raw.get("title"),
                "uploader": raw.get("uploader") or raw.get("channel"),
                "duration": raw.get("duration"),
                "url": raw.get("webpage_url") or source,
            }
        except Exception:  # noqa: BLE001
            pass
    return {
        "video_path": str(video),
        "subtitle_path": str(subtitle) if subtitle else None,
        "info": info,
        "downloaded": True,
    }


def _whisper_fallback(watch_dir: Path, video_path: str, work: Path) -> list[dict]:
    """Run watch's whisper.py and adapt its segments to {start,end,text}."""
    audio_out = work / "audio.mp3"
    proc = subprocess.run(
        [sys.executable, str(watch_dir / "whisper.py"), video_path, str(audio_out)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        print(f"[visual-clipper] whisper fallback failed: {proc.stderr.strip()}", file=sys.stderr)
        return []
    try:
        data = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return []
    segs = []
    for s in data.get("segments", []):
        segs.append({
            "start": round(float(s.get("start", 0.0)), 2),
            "end": round(float(s.get("end", 0.0)), 2),
            "text": (s.get("text") or "").strip(),
        })
    return [s for s in segs if s["text"]]


def main() -> None:
    ap = argparse.ArgumentParser(description="visual-clipper ingest")
    ap.add_argument("source", help="video URL or local file path")
    ap.add_argument("--slug", required=True, help="project slug")
    ap.add_argument(
        "--project-root",
        default=str(Path(__file__).resolve().parents[4] / "tiktok-manager" / "projects"),
        help="where <slug>/ projects live (default: tiktok-manager/projects)",
    )
    ap.add_argument("--resolution", type=int, default=768,
                    help="frame width for scouting (default 768 — readable text/faces)")
    ap.add_argument("--max-frames", type=int, default=120)
    ap.add_argument("--start", default=None, help="optional ingest window start (SS / MM:SS / HH:MM:SS)")
    ap.add_argument("--end", default=None, help="optional ingest window end")
    ap.add_argument("--no-whisper", action="store_true", help="skip Whisper fallback if no captions")
    args = ap.parse_args()

    watch_dir, m = _load_watch_scripts()
    download, frames, transcribe = m["download"], m["frames"], m["transcribe"]

    proj = Path(args.project_root).resolve() / args.slug
    ingest = proj / "ingest"
    frames_dir = ingest / "frames"
    dl_dir = ingest / "download"
    for d in (proj, ingest, frames_dir, dl_dir):
        d.mkdir(parents=True, exist_ok=True)

    # 1. Download / resolve source ------------------------------------------------
    print("[visual-clipper] downloading / resolving source ...", file=sys.stderr)
    dl = _download(args.source, dl_dir, download)
    video_path = dl["video_path"]

    # Keep a stable source.mp4 in the project root (run_clipper-compatible layout).
    source = proj / "source.mp4"
    if Path(video_path).resolve() != source.resolve():
        try:
            shutil.copy2(video_path, source)
        except Exception as exc:  # noqa: BLE001
            print(f"[visual-clipper] could not copy source ({exc}); referencing in place", file=sys.stderr)
            source = Path(video_path)

    # 2. Probe + extract frames ---------------------------------------------------
    print("[visual-clipper] probing + extracting frames ...", file=sys.stderr)
    meta = frames.get_metadata(str(source))
    duration = meta["duration_seconds"]
    start_sec = frames.parse_time(args.start)
    end_sec = frames.parse_time(args.end)
    eff_start = start_sec if start_sec is not None else 0.0
    eff_end = end_sec if end_sec is not None else duration
    eff_dur = max(0.0, eff_end - eff_start)
    focused = start_sec is not None or end_sec is not None
    fps, target = (frames.auto_fps_focus if focused else frames.auto_fps)(eff_dur, max_frames=args.max_frames)
    frame_list = frames.extract(
        str(source), frames_dir, fps=fps, resolution=args.resolution,
        max_frames=args.max_frames, start_seconds=start_sec, end_seconds=end_sec,
    )

    # 3. Transcript ---------------------------------------------------------------
    print("[visual-clipper] building transcript ...", file=sys.stderr)
    transcript: list[dict] = []
    sub = dl.get("subtitle_path")
    if sub and Path(sub).exists():
        transcript = transcribe.parse_vtt(sub)
    elif not args.no_whisper:
        transcript = _whisper_fallback(watch_dir, str(source), ingest)
    if not transcript:
        print("[visual-clipper] WARNING: no transcript (no captions and Whisper unavailable). "
              "SCOUT will rely on frames only.", file=sys.stderr)

    # 4. Manifest -----------------------------------------------------------------
    manifest = {
        "slug": args.slug,
        "source": str(source),
        "info": dl.get("info", {}),
        "width": meta.get("width"),
        "height": meta.get("height"),
        "duration_seconds": duration,
        "has_audio": meta.get("has_audio"),
        "frame_fps": fps,
        "frame_resolution": args.resolution,
        "ingest_window": {"start": eff_start, "end": eff_end} if focused else None,
        "frames": [
            {"index": f["index"], "t": f["timestamp_seconds"], "path": f["path"]}
            for f in frame_list
        ],
        "transcript": transcript,
    }
    manifest_path = ingest / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # 5. Summary ------------------------------------------------------------------
    title = (dl.get("info") or {}).get("title") or Path(source).name
    print(json.dumps({
        "manifest": str(manifest_path),
        "project_dir": str(proj),
        "source": str(source),
        "title": title,
        "dimensions": f'{meta.get("width")}x{meta.get("height")}',
        "duration_seconds": round(duration, 1),
        "frame_count": len(frame_list),
        "frame_fps": round(fps, 3),
        "transcript_segments": len(transcript),
        "frames_dir": str(frames_dir),
    }, indent=2))


if __name__ == "__main__":
    main()

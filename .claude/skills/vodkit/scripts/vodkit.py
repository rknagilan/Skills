#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["yt-dlp"]
# ///
"""vodkit: get audio, metadata and frame-accurate clips out of Twitch VODs.

Run it with `uv run vodkit.py`, which brings its own yt-dlp, or with python3 3.10+ and
yt-dlp installed. Either way, ffmpeg (with ffprobe) must be on PATH. No Twitch API keys.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Fast-seek this far before a cut, then decode the rest of the way for an exact start.
SEEK_PREROLL = 5.0
# Allowed difference between the requested and the encoded clip length.
DURATION_TOLERANCE = 0.25
# Without an edit list the first video frame sits at 0:00. With ffmpeg's default one,
# the video starts ~33 ms after the audio, and QuickTime's still view shows black.
MP4_OUTPUT = ("-movflags", "+faststart", "-use_editlist", "0")


class VodkitError(Exception):
    """Something went wrong in a way the user can act on; the message says what."""


class MissingTool(VodkitError):
    """yt-dlp, ffmpeg or ffprobe isn't installed."""


def log(message: str) -> None:
    print(f"[vodkit] {message}", file=sys.stderr, flush=True)


INSTALL_HINTS = {
    "yt-dlp": "run vodkit with `uv run`, or install yt-dlp (`brew install yt-dlp` or `pipx install yt-dlp`)",
    "ffmpeg": "install ffmpeg (`brew install ffmpeg`, `apt install ffmpeg` or ffmpeg.org)",
    "ffprobe": "install ffmpeg, which includes ffprobe (`brew install ffmpeg`, `apt install ffmpeg` or ffmpeg.org)",
}


def run(*args: str) -> str:
    try:
        result = subprocess.run(args, capture_output=True, text=True)
    except FileNotFoundError:
        raise MissingTool(f"{args[0]} isn't installed: {INSTALL_HINTS.get(args[0], 'install it and try again')}") from None
    if result.returncode != 0:
        raise VodkitError(f"{args[0]} failed: {result.stderr.strip()[-400:]}")
    return result.stdout


def yt_dlp(*args: str) -> str:
    # Under `uv run`, yt-dlp is a package of this script's environment, not a command on PATH.
    if importlib.util.find_spec("yt_dlp"):
        try:
            return run(sys.executable, "-m", "yt_dlp", *args)
        except VodkitError as error:
            raise VodkitError(str(error).replace(sys.executable, "yt-dlp", 1)) from None
    return run("yt-dlp", *args)


def data_dir() -> Path:
    return Path(os.environ.get("VODKIT_DATA", "vodkit-data"))


# ---------------------------------------------------------------- VODs and times

def parse_vod_id(vod: str) -> str:
    """The VOD id from a URL or a bare id: the first run of 6 or more digits."""
    match = re.search(r"(\d{6,})", vod)
    if not match:
        raise VodkitError(f"can't find a VOD id in {vod!r}")
    return match.group(1)


def latest_vod_id(channel: str) -> str:
    url = f"https://www.twitch.tv/{channel}/videos?filter=archives&sort=time"
    lines = yt_dlp("--flat-playlist", "--playlist-end", "1", "-j", url).splitlines()
    if not lines:
        raise VodkitError(f"{channel} has no past broadcasts")
    return json.loads(lines[0])["id"].removeprefix("v")


def resolve_vod_id(vod: str, channel: str | None) -> str:
    if vod != "latest":
        return parse_vod_id(vod)
    if not channel:
        raise VodkitError("'latest' needs a channel: pass --channel or set VODKIT_CHANNEL")
    return latest_vod_id(channel)


def parse_time(text: str) -> float:
    """Seconds from '754.5', '12:34.5' or '1:02:03'."""
    parts = text.split(":")
    if len(parts) > 3 or not all(re.fullmatch(r"\d+(\.\d+)?", p) for p in parts):
        raise VodkitError(f"can't read {text!r} as a time (use seconds, m:ss or h:mm:ss)")
    seconds = 0.0
    for part in parts:
        seconds = seconds * 60 + float(part)
    return seconds


def deep_link(vod_id: str, seconds: float) -> str:
    """A link that opens the VOD at `seconds`, for checking a moment by hand."""
    total = int(seconds)
    h, m, s = total // 3600, total % 3600 // 60, total % 60
    return f"https://www.twitch.tv/videos/{vod_id}?t={h}h{m}m{s}s"


def chapter_at(metadata: dict, seconds: float) -> str | None:
    """The game (Twitch category) being played at `seconds` into the VOD."""
    for chapter in metadata.get("chapters", []):
        if chapter["start_time"] <= seconds < chapter["end_time"]:
            return chapter["title"]
    return metadata.get("game")


def load_metadata(vod_id: str) -> dict:
    """Title, start time, length and chapters, cached in <data>/vods/<id>.json."""
    path = data_dir() / "vods" / f"{vod_id}.json"
    if path.exists():
        return json.loads(path.read_text())

    log(f"fetching metadata for {vod_id}")
    try:
        info = json.loads(yt_dlp("-j", f"https://www.twitch.tv/videos/{vod_id}"))
    except MissingTool:
        raise
    except VodkitError as error:
        raise VodkitError(f"VOD {vod_id} unavailable (expired, deleted or subscriber-only?): {error}") from None
    if info.get("is_live"):
        raise VodkitError("that broadcast is still live; try again after the stream ends")
    chapters = info.get("chapters") or []
    metadata = {
        "vod_id": vod_id,
        "vod_url": f"https://www.twitch.tv/videos/{vod_id}",
        "title": info["title"],
        "channel": info.get("uploader_id"),
        "game": chapters[0]["title"] if chapters else None,
        "chapters": chapters,
        "created_at": datetime.fromtimestamp(info["timestamp"], timezone.utc).isoformat(),
        "duration": info["duration"],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(metadata, indent=2))
    return metadata


# ------------------------------------------------------------------------ audio

def media_seconds(path: Path) -> float:
    return float(run("ffprobe", "-v", "error", "-show_entries", "format=duration",
                     "-of", "csv=p=0", str(path)))


def download_audio(vod_id: str) -> Path:
    """The VOD's audio-only track, downloaded once to <data>/audio/<id>.<ext>."""
    audio_dir = data_dir() / "audio"
    existing = [p for p in audio_dir.glob(f"{vod_id}.*") if ".partial." not in p.name]
    if existing:
        return existing[0]
    audio_dir.mkdir(parents=True, exist_ok=True)

    # Download under a .partial name and keep it only if it covers the whole VOD.
    # When Twitch drops a fragment, yt-dlp can still write a file that's a few seconds
    # short, and every timestamp after the hole would be off.
    for leftover in audio_dir.glob(f"{vod_id}.partial.*"):
        leftover.unlink()
    expected = load_metadata(vod_id)["duration"]
    log(f"downloading the audio track ({expected / 3600:.1f} h of stream)")
    yt_dlp("-q", "--no-progress", "-N", "8", "-f", "Audio_Only",
        "--fragment-retries", "30", "--abort-on-unavailable-fragments",
        "-o", str(audio_dir / f"{vod_id}.partial.%(ext)s"),
        f"https://www.twitch.tv/videos/{vod_id}")
    partial = next(audio_dir.glob(f"{vod_id}.partial.*"))

    got = media_seconds(partial)
    if abs(got - expected) > 2:
        partial.unlink()
        raise VodkitError(f"the audio came out {got:.0f}s long but the VOD is {expected:.0f}s "
                          "(Twitch dropped part of it); try again later")
    final = partial.with_name(partial.name.replace(".partial", ""))
    partial.rename(final)
    return final


# ------------------------------------------------------------------------- cuts

def stream_url(vod_id: str, quality: str) -> str:
    """The signed HLS playlist URL. It expires, so fetch a fresh one for each run."""
    try:
        return yt_dlp("-g", "-f", quality, f"https://www.twitch.tv/videos/{vod_id}").strip()
    except MissingTool:
        raise
    except VodkitError as error:
        raise VodkitError(f"source video unavailable (VOD expired or deleted?): {error}") from None


def cut(vod_id: str, start: float, end: float, *, quality: str, crf: int, preset: str,
        fade: float, out: Path | None) -> Path:
    """A frame-accurate clip of [start, end), encoded straight from Twitch.

    Cached in <data>/vods/<id>/<start>-<end>.mp4 unless `out` is given. Every clip uses
    the same encode settings for a given crf/preset, so clips can be joined without
    another encode.
    """
    if end <= start:
        raise VodkitError(f"the end ({end:.2f}s) must be after the start ({start:.2f}s)")
    path = out or data_dir() / "vods" / vod_id / f"{start:.2f}-{end:.2f}.mp4"
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)

    duration = end - start
    # Two-stage seek: a fast seek alone (-ss before -i) can land past the requested time
    # on Twitch's HLS stream, so fast-seek a few seconds early and decode the rest.
    coarse = max(0.0, start - SEEK_PREROLL)
    exact = start - coarse
    # Filters see the stream from the coarse seek point, before the exact seek trims it,
    # so the fades are offset by the preroll.
    fades = (f"afade=t=in:st={exact:.3f}:d={fade},"
             f"afade=t=out:st={exact + duration - fade:.3f}:d={fade}")
    partial = path.with_suffix(".partial.mp4")
    log(f"cutting {duration:.1f}s from {start:.2f}s")
    run("ffmpeg", "-nostdin", "-loglevel", "error", "-y",
        "-ss", f"{coarse:.3f}", "-i", stream_url(vod_id, quality),
        "-ss", f"{exact:.3f}", "-t", f"{duration:.3f}",
        "-af", fades,
        "-c:v", "libx264", "-crf", str(crf), "-preset", preset, "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        *MP4_OUTPUT, str(partial))
    # Check before keeping it, so a bad cut can't be reused by later runs.
    try:
        verify(partial, duration)
    except VodkitError:
        partial.unlink(missing_ok=True)
        raise
    partial.rename(path)
    return path


def join(clips: list[Path], out: Path) -> Path:
    """Joins clips made with the same settings, with hard cuts and no re-encode."""
    out.parent.mkdir(parents=True, exist_ok=True)
    concat_list = out.with_name(f".{out.stem}-clips.txt")
    concat_list.write_text("".join(f"file '{clip.resolve()}'\n" for clip in clips))
    try:
        run("ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
            "-i", str(concat_list), "-c", "copy", *MP4_OUTPUT, str(out))
    finally:
        concat_list.unlink()
    return out


def verify(path: Path, expected_seconds: float) -> None:
    """Fails loudly on anything that makes a clip unusable."""
    if not path.exists() or path.stat().st_size == 0:
        raise VodkitError(f"{path.name} was not created")
    info = json.loads(run("ffprobe", "-v", "error", "-show_streams", "-show_format",
                          "-of", "json", str(path)))
    kinds = {stream["codec_type"] for stream in info["streams"]}
    if kinds != {"video", "audio"}:
        raise VodkitError(f"{path.name} has streams {sorted(kinds)}, expected video and audio")

    duration = float(info["format"]["duration"])
    if abs(duration - expected_seconds) > DURATION_TOLERANCE:
        raise VodkitError(f"{path.name} is {duration:.2f}s, expected {expected_seconds:.2f}s")

    video = next(s for s in info["streams"] if s["codec_type"] == "video")
    # A late first frame means the seek skipped footage, even when the length looks right.
    if float(video.get("start_time", 0)) > 0.1:
        raise VodkitError(f"{path.name} video starts {float(video['start_time']):.2f}s late")

    # Stream audio always has a noise floor, so a stretch of digital silence means audio
    # was lost (a misplaced fade or a muted section), not that the streamer paused.
    silence = subprocess.run(["ffmpeg", "-nostdin", "-i", str(path), "-vn",
                              "-af", "silencedetect=noise=-80dB:d=0.4", "-f", "null", "-"],
                             capture_output=True, text=True).stderr
    if "silence_start" in silence:
        at = silence[silence.index("silence_start"):][:60]
        raise VodkitError(f"{path.name} has dead audio ({at}); if the VOD is muted there, "
                          "that part of the stream has no sound on Twitch either")


# -------------------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vodkit", description=__doc__.splitlines()[0])
    parser.add_argument("--channel", default=os.environ.get("VODKIT_CHANNEL"),
                        help="Twitch channel for 'latest' (default: $VODKIT_CHANNEL)")
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    info = commands.add_parser("info", help="print a VOD's title, date, length and chapters as JSON")
    info.add_argument("vod", help="VOD URL, id, or 'latest'")

    audio = commands.add_parser("audio", help="download the audio-only track; prints its path")
    audio.add_argument("vod")

    clip = commands.add_parser("cut", help="encode a frame-accurate clip; prints its path")
    clip.add_argument("vod")
    clip.add_argument("start", help="seconds, m:ss or h:mm:ss")
    clip.add_argument("end", help="seconds, m:ss or h:mm:ss")
    clip.add_argument("-o", "--out", type=Path, help="output file (default: cached under the data folder)")
    clip.add_argument("--quality", default="best", help="yt-dlp format, e.g. 1080p60 or 720p60 (default: best)")
    clip.add_argument("--crf", type=int, default=18, help="x264 quality, lower is better (default: 18)")
    clip.add_argument("--preset", default="medium", help="x264 preset (default: medium)")
    clip.add_argument("--fade", type=float, default=0.03, help="audio fade at each edge in seconds (default: 0.03)")

    joined = commands.add_parser("join", help="join clips made with the same settings, without re-encoding")
    joined.add_argument("out", type=Path)
    joined.add_argument("clips", type=Path, nargs="+")

    check = commands.add_parser("verify", help="check a clip's streams, length, start and audio")
    check.add_argument("file", type=Path)
    check.add_argument("seconds", type=parse_time, help="expected length")

    link = commands.add_parser("link", help="a link that opens the VOD at a time, and the game being played")
    link.add_argument("vod")
    link.add_argument("time", help="seconds, m:ss or h:mm:ss")

    args = parser.parse_args(argv)
    try:
        if args.command == "info":
            print(json.dumps(load_metadata(resolve_vod_id(args.vod, args.channel)), indent=2))
        elif args.command == "audio":
            print(download_audio(resolve_vod_id(args.vod, args.channel)))
        elif args.command == "cut":
            vod_id = resolve_vod_id(args.vod, args.channel)
            print(cut(vod_id, parse_time(args.start), parse_time(args.end), quality=args.quality,
                      crf=args.crf, preset=args.preset, fade=args.fade, out=args.out))
        elif args.command == "join":
            print(join(args.clips, args.out))
        elif args.command == "verify":
            verify(args.file, args.seconds)
            print(f"{args.file}: ok")
        elif args.command == "link":
            vod_id = resolve_vod_id(args.vod, args.channel)
            seconds = parse_time(args.time)
            print(deep_link(vod_id, seconds))
            game = chapter_at(load_metadata(vod_id), seconds)
            if game:
                print(f"game: {game}")
    except VodkitError as error:
        print(f"vodkit: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

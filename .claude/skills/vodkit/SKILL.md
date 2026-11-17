---
name: vodkit
description: Work with Twitch VODs (past broadcasts and highlights) without downloading whole streams, using yt-dlp and ffmpeg and no Twitch API keys. Covers finding a VOD from a URL, an id or "latest", reading its metadata and chapters (which game was played when), downloading only the audio for transcription or loudness analysis, cutting frame-accurate clips straight from Twitch's stream, joining clips without re-encoding, checking clips before using them, and timestamped deep links. Use whenever a task involves a Twitch VOD, a past broadcast, stream highlights, clipping a stream, or transcribing a stream.
---

# vodkit: Twitch VODs without the whole download

Everything here uses `yt-dlp` and `ffmpeg` (with `ffprobe`). No Twitch API credentials are needed.

`scripts/vodkit.py`, in this skill's folder, does each step below and has the gotchas built in. Use it rather than writing new yt-dlp or ffmpeg commands; if a task needs something it doesn't do, follow the rules in this file.

```bash
uv run scripts/vodkit.py info <vod>                # metadata as JSON (title, date, length, chapters)
uv run scripts/vodkit.py audio <vod>               # audio-only download; prints the file path
uv run scripts/vodkit.py cut <vod> 1:02:03 1:02:41 # frame-accurate clip; prints the file path
uv run scripts/vodkit.py join out.mp4 a.mp4 b.mp4  # join clips with no re-encode
uv run scripts/vodkit.py verify clip.mp4 38        # check a clip against its expected length
uv run scripts/vodkit.py link <vod> 1:02:03        # deep link + the game being played then
```

- `uv run` brings its own yt-dlp. Without uv, `python3 scripts/vodkit.py` works when yt-dlp is installed. Either way ffmpeg (with ffprobe) must be on PATH; if a tool is missing, the error says how to install it.

- `<vod>` is a VOD URL, a bare id, or `latest` (with `--channel NAME` before the command, or `VODKIT_CHANNEL` set).
- Times can be seconds (`3723.5`), `m:ss` or `h:mm:ss`.
- Metadata, audio and clips are cached under `./vodkit-data/`, or wherever `VODKIT_DATA` points. Reruns reuse them.
- Errors go to stderr with exit code 1, and the message says what to do.

---

# Finding a VOD

- **Id from a URL:** the first run of 6 or more digits (`twitch.tv/videos/2894251896` gives `2894251896`).
- **Latest:** `yt-dlp --flat-playlist --playlist-end 1 -j "https://www.twitch.tv/<channel>/videos?filter=archives&sort=time"`. The `id` comes back with a `v` in front; strip it.
- **Metadata:** `yt-dlp -j https://www.twitch.tv/videos/<id>` gives `title`, `timestamp` (UTC epoch), `duration`, `chapters` and `is_live`.
  - If `is_live` is true, the broadcast is still running and the VOD is incomplete. Stop and try again after the stream ends.
  - Cache the metadata and read it from there afterwards, rather than asking Twitch again.

## Chapters tell you which game

Each chapter is a Twitch category with `start_time` and `end_time` in VOD seconds. Streams often switch games partway through, so:

- The VOD's overall game is just the first chapter.
- For a moment at time `t`, the game is the chapter where `start_time <= t < end_time`. Fall back to the first chapter if none matches.

## Deep links

`https://www.twitch.tv/videos/<id>?t=<h>h<m>m<s>s` opens the VOD at a timestamp. Put these in any report about moments in a stream, so a person can check each one by hand.

---

# Audio only

For transcription (Whisper and the like) or loudness analysis, download only the audio track:

```bash
yt-dlp -q --no-progress -N 8 -f Audio_Only --fragment-retries 30 --abort-on-unavailable-fragments \
  -o "<id>.partial.%(ext)s" https://www.twitch.tv/videos/<id>
```

- `-N 8` fetches fragments in parallel. An 8-hour VOD's audio takes a few minutes; tell the user roughly how long to expect.
- **Check the length before keeping it.** Twitch occasionally fails a fragment, and yt-dlp can still write a file a few seconds short. Every timestamp after the hole would then be off. Download under a `.partial` name, compare its `ffprobe` duration to the VOD's `duration`, and keep it only if they're within 2 seconds.
- Decode it once to 16 kHz mono (`ffmpeg -i <file> -ac 1 -ar 16000 -f s16le -`) and use that one decode for both transcription and loudness.
- Don't download again if the file is already there.

---

# Cutting clips

Never download the whole VOD to cut a clip. Encode just the spans you need, straight from Twitch's stream.

1. **Get the signed stream URL:** `yt-dlp -g -f <quality> https://www.twitch.tv/videos/<id>` (`best`, `1080p60`, `720p60`, ...). The URL expires, so fetch a fresh one each run and never store it.
2. **Seek in two stages:** `ffmpeg -ss <start - 5> -i <url> -ss 5 -t <duration> ...`.
   - A fast seek alone (`-ss` only before `-i`) can land past the requested time on Twitch's stream, silently dropping the first fraction of a second.
   - The second `-ss` decodes the rest of the way, so the cut is frame-accurate.
3. **Offset filter times by the preroll.** Filters see the stream from the coarse seek point, before the exact seek trims it. A fade placed at `duration - 0.03` without the 5 s offset lands 5 s early and silences the end of the clip.
4. **Use identical encode settings for every clip** (libx264 at one CRF and preset, `yuv420p`, AAC). Then clips can be joined with `-f concat -c copy`, with no second encode.
5. **Fade the audio for about 0.03 s at each edge** so the cuts don't click.
6. **Check before keeping.** Encode to a `.partial.mp4`, verify it (below), then rename it. That way a bad cut can't be reused by later runs.
7. **Cache clips by VOD and time range** (`<id>/<start>-<end>.mp4`) and reuse them on reruns. When a clip's boundaries change, delete the old file.

## What to check in every clip

- It has exactly one video and one audio stream.
- Its length is within 0.25 s of what was asked for.
- The video's first frame starts no more than 0.1 s in. A late start means the seek skipped footage, even when the length looks right.
- No digital silence (below -80 dB for 0.4 s or more). Stream audio always has a noise floor, so true silence means audio was lost. The exception is a section Twitch muted for copyrighted music: that part has no sound on Twitch either.

## MP4 output

Write every finished mp4 with `-movflags +faststart -use_editlist 0`. By default ffmpeg adds an edit list that starts the video about 33 ms after the audio. QuickTime's still view before play shows exactly 0:00, where there's no picture yet, so the clip looks like a black screen until it's played.

---

# When a VOD disappears

Twitch past broadcasts expire (after 7 to 60 days, depending on the channel), and streamers delete them.

- When `yt-dlp` fails for a VOD that used to work, treat it as gone. Report "source video unavailable (VOD expired or deleted?)", fail that item, and move on. Don't retry forever.
- Subscriber-only VODs fail the same way without a signed-in account; say that's a possible cause.
- Keep cached clips and audio after a VOD is gone, since they may be the only copy left.
- Highlights don't expire. If a stream matters, suggest the streamer highlight it or download it while it's still up.

---

# Twitch's own clip APIs

Checked in October 2026; confirm against Twitch's current docs before relying on them.

- **Create Clip From VOD** makes an official Twitch Clip, but only from one continuous span of 5 to 60 seconds, and it needs an authorized app. It can't make a clip with dead air cut out.
- **There is no video upload API.** Uploads existed only in the v5 (Kraken) API, which shut down in 2022. Streamers upload to Twitch by hand.
- Keep the VOD id and source timestamps with every clip, so an official clip can still be made from the same moment later.

---
name: montclipper
description: MontClipper Lite clips finished streams (Twitch or YouTube videos), up to 5 clips each. The AI (Claude Code or Codex) finds the best moments (chat spikes, streamer reactions, a transcript read every 2 minutes) and makes ready-to-post clips in ~/MontClipper/Upload to Socials - 9:16 and 16:9 videos with captions, a cover/thumbnail for each, and upload notes. Use when the user says MontClipper, "clip this stream", "watch <streamer>", "clip the VOD", "show me my clips", or wants stream clips for Shorts, TikTok or Reels.
---

# MontClipper

The engine is this skill folder. Run it with the launcher `<this folder>/mc` (it uses MontClipper's own
Python; on Windows run it in Git Bash, or use `<this folder>/mc.cmd`). The user's clips, recordings and settings are in `~/MontClipper` (or `$MONTCLIPPER_HOME`).
The plain-language guide is `<this folder>/USER-GUIDE.md` (a copy is in `~/MontClipper/User guide.md`).

Works in **Claude Code and Codex**. The engine judges clips with the AI it was started from (`codex exec` under
Codex, `claude -p` under Claude Code, else whichever is installed); `"agent": "codex"` or `"claude"` in
`~/MontClipper/config.json` forces one. In Codex, run `setup.sh` and every `mc` command **outside the sandbox** (request escalated
permissions / full access, and ask the user to approve): inside it, speech-to-text can't use the graphics chip, downloads
fail and the clip judge (`codex exec`) can't start. `mc` refuses to run in the sandbox and says so. Never work around
this (no stand-in scripts, no judging clips yourself): ask for the permission.

Assume the user is **not technical**: do everything for them, and reply in short, plain words
(no flags, no paths unless asked, no jargon).

## First use
If `~/MontClipper/tools-audio` doesn't exist, set it up. Mac: check for Homebrew, then (asking first)
`brew install ffmpeg streamlink yt-dlp whisper-cpp uv`. Windows: (asking first) `winget install` Git.Git,
Gyan.FFmpeg, Streamlink.Streamlink, yt-dlp.yt-dlp, astral-sh.uv (Windows may show a "make changes" prompt: tell the user to click Yes; new tools may not be on PATH until a
new shell, so look in `%LOCALAPPDATA%/Microsoft/WinGet/Links` or ask the user to restart Claude Code, then carry on), then use Git Bash. Then `bash <this folder>/setup.sh`. It downloads about
2.5 GB once (speech model, music checker). Finish with `<this folder>/mc check`. If a step fails on this computer,
read the error and fix it yourself, including in this skill's files, rather than handing it to the user.

## What the user says, and what you do
- "watch <name>" or anything live: explain in one line that live clipping (clips minutes after the moment,
  sent to the phone) is in MontClipper Pro in Chris Ife Studio Premium (https://dub.sh/chrisifestudio), and offer to
  clip a finished stream instead.
- "clip this stream <link>": run `<this folder>/mc vod "<link>"` in the background (add `--max-clips N`,
  `--from H:MM:SS --to H:MM:SS` if they asked). Report the clip titles when done. Lite makes at most 5 clips per stream.- "show me my clips": `<this folder>/mc open` (opens Finder and the All clips page in their browser).
- "status": `<this folder>/mc status`, then summarise in one or two lines.
- Pickiness and look: edit `~/MontClipper/config.json` (create it with only the changed keys). `min_score` up
  = fewer, better clips; `chat_ratio` down = more chat moments; `vertical`/`wide`; `brand` = their channel name
  shown on the vertical video. Changes apply to the next run.
- Setup problems: `<this folder>/mc check`, then fix what's missing.

## Outputs
`~/MontClipper/Upload to Socials/<date time> <streamer> - <title>/` holds `<title> - Vertical.mp4`,
`<title> - Vertical - Thumbnail.png` (1080x1920 cover), `<title> - Wide.mp4`, `<title> - Wide - Thumbnail.jpg`,
`Upload notes.txt` (title, caption, description with credit, hashtags, warnings), plus a hidden .meta.json.
Posted folders go in `Upload to Socials/Done`. `Upload to Socials/All clips.html` plays every clip: tell users to
double-click it in Finder.

## Rules (keep them)
- Credit the streamer on every clip (the engine does it). Never post or upload for the user.
- Music: every clip is checked by a sound tagger. A real song gets "A song is playing. Remove the music before
  posting (CapCut: Audio > Isolate voice)"; instrumental game music gets "Background game music (no singing).
  Lower risk". The clip keeps its sound: don't promise automatic music removal.
- Skipped automatically: GTA 6 story spoilers. Violent openings are avoided (YouTube ads rule).
- Recordings are temporary, in `~/MontClipper/Recordings (auto-deleted)`. They're deleted when a stream ends,
  when watching stops, and after each finished-stream job. Leftovers from a crash are cleaned at the next start.
- Recommend a separate clips channel, never the user's own channel with their own videos (reused-content risk).
- If YouTube says "Sign in to confirm you're not a bot", set `"youtube_browser": "chrome"` (or safari) in config.json.

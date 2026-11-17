# MontClipper: how to use it

MontClipper Lite turns a stream that has ended into clips that are ready to post, up to 5 per stream.
(MontClipper Pro also clips streams **while they are still live** and sends every clip to your phone.
It's in Chris Ife Studio Premium: https://dub.sh/chrisifestudio)

You don't need to know anything technical. You talk to Claude, and Claude does the rest. (Using Codex instead? It works the same way: wherever this guide
says Claude, talk to Codex.)

---


- If the streamer isn't live yet, MontClipper **waits** and starts by itself when they go live.
  You can set it up and go to sleep.
- A clip is usually ready 1 to 3 minutes after the moment. Your Mac makes a sound each time.
- To stop, type: **MontClipper, stop watching**
<!--/PRO-->

## Clip a stream that has ended

Paste the link of the finished stream (a Twitch video or a YouTube video):

> **MontClipper, clip this stream: https://www.youtube.com/watch?v=...**

You get up to 5 clips. You can also clip only part of the stream ("only the first hour").

## Find your clips

Everything ready to post is in the **Upload to Socials** folder inside the **MontClipper** folder
in your home folder. Ask Claude: **MontClipper, show me my clips**

Each clip has its own folder, named with the date, the streamer and the clip title. Inside:

| File | What it's for |
|---|---|
| `... - Vertical.mp4` | The tall video for YouTube Shorts, TikTok and Instagram Reels |
| `... - Vertical - Thumbnail.png` | The cover for the tall video |
| `... - Wide.mp4` | The normal wide video for YouTube or X |
| `... - Wide - Thumbnail.jpg` | The thumbnail for the wide video |
| `Upload notes.txt` | Title, caption, description and hashtags to copy and paste, plus any warning (like music) |

After you post a clip, move its folder into **Done** so you know what's posted.

To watch all clips in one place, double-click **All clips.html** in the Upload to Socials
folder. It opens in your browser, and you can play every clip there.

---

## How MontClipper picks moments

It watches the stream in several ways, and Claude decides on every clip:

1. **Chat goes crazy.** Lots of different viewers react at the same time (laughing, "CLIP IT", "NO WAY").
   (For finished streams this works on YouTube, where the old chat is saved.)
2. **The streamer gets loud.** Screaming or laughing much louder than normal.
3. **Claude listens.** Claude reads everything the streamer said and spots funny or
   big moments that chat missed.

For each moment, Claude watches it, then decides whether it's good enough, where the clip should
start and end, and writes the title. Weak moments are thrown away, so a quiet stream gives few clips.

## Built-in safety rules

- **Music is checked on every clip.** There are two kinds of warning:
  - **"A song is playing. Remove the music before posting"**: a real song (singing or rap, like a car
    radio in a game). Songs get copyright claims that take your earnings. In CapCut: tap the clip, then
    **Audio → Isolate voice**, and listen once. If you can still hear the song, don't post that clip.
  - **"Background game music (no singing)"**: the game's own soundtrack. Lower risk, and most clippers post these
    as they are. If a platform ever shows a copyright claim, mute the music in CapCut.
- **No GTA 6 story spoilers.** Clips of story scenes or endings are never made. Rockstar takes them down.
- **No violent openings.** YouTube shows fewer ads when violence is in the first 7 seconds, so clips avoid that.
- **Credit on every clip.** The streamer's name is on screen and in the description.

## Disk space

While it works, MontClipper keeps temporary files in the **Recordings (auto-deleted)** folder.
 These recordings are deleted
**automatically** when the stream ends, when you stop watching, or when a finished-stream job is done.
You never need to clean up. If you see files there while nothing is running, it's safe to delete them.

## Change how picky it is

Just tell Claude in plain words, for example:
- "MontClipper, make fewer but better clips"
- "MontClipper, I'm missing good moments, be less strict"
- "MontClipper, only make vertical videos"
- "MontClipper, put my channel name ClipOga on the clips"

## How to make money with clips

1. **Join the streamer's clipping program.** Many big streamers pay clippers per 1,000 views
   (through Whop, Vyro or their Discord). It also means you have permission to post their clips.
2. **Post fast.** Being first is MontClipper's advantage. Post the vertical video as soon as it's ready.
3. **One clip, one account.** Don't post the same clip to many accounts; platforms punish duplicates.
4. **Use a separate clips channel.** Don't mix stream clips into a channel with your own videos:
   YouTube can stop ads on the **whole** channel for "reused content".

---

<details>
<summary>For advanced users: commands you can type in Terminal yourself</summary>

MontClipper's launcher is `~/.claude/skills/montclipper/mc` (on Windows, in Git Bash; or `mc.cmd` in
Terminal or PowerShell).

- `mc vod "<link>" --max-clips 5 --from 1:00:00 --to 2:00:00`
- `mc open`: opens Upload to Socials and the clips page
- `mc status`: what is being watched
- `mc check`: check that everything is installed
- Ctrl+C stops watching.

Settings live in `~/MontClipper/config.json` (create it with only what you want to change), e.g. `{"min_score": 70}`.
Main ones: `min_score` (62; higher means fewer, better clips), `chat_ratio` (2.6; lower catches more
chat moments), `vertical` / `wide` (true), `brand` (your channel name on the vertical video, "none" for none),
`music` ("label" flags songs; "keep" turns the check off), `buffer_minutes` (40),
`youtube_browser` ("chrome" or "safari": use that browser's YouTube login if YouTube asks you to sign in).
</details>

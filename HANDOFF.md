# Handoff: continue this work on the user's Windows PC

Read this first. You are now running ON the user's Windows PC (user: rknag), so run every
command yourself; do not ask the user to type commands. The user is a beginner and prefers
**Tamil** replies when they write in Tamil. Give one step at a time.

## Goal
GTA 6 releases Nov 19. The user wants: when chosen streamers go live, automatically make viral
vertical clips and post them to the user's Instagram, with only one phone tap to approve.
Legal route: Whop / Content Rewards clipping campaigns (streamers pay per view, #ad disclosure required).

## Already done
- Repo cloned at `C:\Users\rknag\AutoClip` (branch `ccr-21cbc605-g8n41d`).
- 95 skills installed in `C:\Users\rknag\.claude\skills` (ig-reel, montclipper, vodkit,
  shorts-clipper, video-to-shorts-skill, ai-clipping-skill, social-publish, upload-post, twitch-clips, ...).
- Docker Desktop present. Python 3.14 at `C:\Users\rknag\AppData\Local\Python\pythoncore-3.14-64\python.exe`
  (3.15 also installed; avoid it for ML packages). Codex CLI installed and logged in with ChatGPT.
- SupoClip cloned to `C:\Users\rknag\ClippingApps\supoclip` (needs .env keys, not started).
- Cutawan installed but buggy: fixed `av==16.0.1` in its venv; then hit missing `cublas64_12.dll`
  (NVIDIA GPU, no CUDA libs). User set `CUDA_VISIBLE_DEVICES=-1` (User env) to force CPU; untested.
  **The user is frustrated with Cutawan. Drop it unless they ask.**
- Clips Kitty: download page opened; install status unknown.

## Next steps (one at a time, do them yourself)
1. Install/verify tools: ffmpeg, yt-dlp (winget), check `py -3.14`.
2. Test clipping with a skill (montclipper or shorts-clipper) on a short GTA YouTube video the user gives;
   produce 2 vertical 9:16 clips with captions. Fix errors yourself.
3. Set up AutoClip (`autoclip\GUIDE-TAMIL.md`): run `autoclip\install-windows.ps1`, ntfy topic on phone,
   fill `autoclip\config.json` + `autoclip\streamers.json`, `py -3.14 autoclip\autoclip.py --check`,
   then `autoclip\register-autostart.ps1`. Note: autoclip.py's live recording / ntfy / posting
   were never tested on a real stream; test with a live channel before Nov 19.
4. Things only the user can do: join Whop/Content Rewards GTA campaigns (paste brief into
   `autoclip\campaigns\*\brief.txt`), connect Instagram (Creator account) to WoopSocial, install ntfy app.

## Rules
- Never post without the user's approval; keep #ad on campaign clips; credit streamers.
- Don't post clips of streamers without a campaign or permission.

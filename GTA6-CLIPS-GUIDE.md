# GTA 6 stream → viral Instagram Reels (skills guide)

## The pipeline
| Step | What | Installed skill |
|---|---|---|
| 1 | Find which streamers / moments are trending | `last30days`, `ig-viral` |
| 2 | Get the stream VOD (Twitch / YouTube / Kick) | `vodkit` (Twitch, no full download), `montclipper` |
| 3 | Find the best / funniest moments | `shorts-clipper`, `clipper-find`, `visual-clipper`, `openshorts` |
| 4 | Cut to vertical 9:16 with captions | `montclipper`, `video-to-shorts-skill`, `clipper-clip`, `visual-clipper` |
| 5 | Edit: zooms, effects, montage on the beat | `editing-gameplay-montages`, `editar-reel`, `highlight-reel`, `trial-reels`, `ranking-list` |
| 6 | Sound + music | `sonido-reel` |
| 7 | Hook, caption, hashtags | `ig-reel`, `ig-caption`, `ig-human` |
| 8 | Post to Instagram / TikTok / Shorts | `social-publish`, `video-to-shorts-skill`, `ai-clipping-skill` (clipping campaigns) |

## ⚠️ Copyright: read this first
Clips of other streamers belong to them. To stay safe and keep your account:
1. **Use streamers who allow clipping**: many run "clip programs" or campaigns (Whop, Content Rewards) and pay you per view. `ai-clipping-skill` is built for this.
2. **Or ask for permission**, and always credit the streamer (@name) in the video and caption.
3. **Add your own value**: commentary, ranking lists, reactions, edits. Pure re-uploads get copyright strikes.
4. GTA 6 game footage is owned by Rockstar Games. Normal gameplay clips are usually fine, but don't post leaks.

## Not installed (no license file), install yourself if you want
- `NikitaPPP017/twitch-clips` (Twitch VOD → 9:16, Russian): copy `.claude/skills/twitch-clips`
- `Upload-Post/upload-post-skill` (post Reels to Instagram): `npx skills add Upload-Post/upload-post-skill`

## Tools you need on your computer
`ffmpeg`, `yt-dlp`, Python 3, and for some skills Node.js (Remotion/HyperFrames). A GPU helps but is not required.

## Desktop clipping apps (not skills): from the Threads post "GTA 6 open-source clipping tools"
| App | Type | Needs | Install |
|---|---|---|---|
| OpenShorts | web app + skill | Docker, 8GB RAM, Gemini key | `openshorts` skill already installed |
| Cutawan | desktop app (MIT) | optional AI key; local captions free | `install-clipping-apps-windows.ps1` |
| SupoClip | web app (AGPL-3.0) | Docker, AssemblyAI key, one LLM key | `install-clipping-apps-windows.ps1` |
| Clips Kitty | desktop app (Windows) | none (local) | download page opened by the script |

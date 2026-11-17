---
name: visual-clipper
description: Turn a long video into short-form vertical clips by WATCHING it, not just reading the transcript. Use when the user wants to clip a video (URL or local file) for TikTok/Reels/Shorts/Whop — especially when they want the clips reframed/zoomed well for vertical, or clip selection grounded in what's actually on screen. Multi-agent. Claude scouts candidates from frames plus transcript, three LLM-as-judge gates vet clip selection, framing, and captions, OpenCV picks the layout (crop, split, or blur), then ffmpeg renders 9:16 with clean burned captions.
license: MIT
metadata:
  version: 1.0.0
  author: Zach Ongeri
  homepage: https://github.com/zackseal89/Claudeclipping-skill
  tags: [video, clipping, tiktok, shorts, reels, ffmpeg, opencv, captions, reframe, multi-agent]
  requires: [yt-dlp, ffmpeg, ffprobe, python3, opencv-python, numpy]
---

# visual-clipper

Clip a long video into vertical shorts **by watching and understanding it**, not by
reading the transcript blind. Claude sees the frames, so clip selection, layout, and
camera framing are all grounded in what's on screen — and three judge gates keep it honest.

## Pipeline — 9 stages, 3 quality gates

```
1 INGEST → 2 SCOUT → 3 JUDGE①(clips) → 4 DETECT → 5 CAMERA → 6 JUDGE②(framing)
        → 7 CUT → 8 JUDGE③(captions) → 9 PACKAGE
```

You orchestrate. The three gates are LLM-as-judge subagents (clip / framing / caption);
each has a rubric in `references/`. Never skip a gate — they are the difference between
"looks fine to me" and "actually ships well."

## Conventions (read once)

- All paths are **relative to the workspace root**. Scripts live in this skill's
  `scripts/`, rubrics in `references/`, the plan schema in `templates/`.
- One project per job at `tiktok-manager/projects/<slug>/` (kebab-case slug from the title).
  Clips, plans, SRTs, and metadata all live in `projects/<slug>/clips/`.
- **Whop clips are client work** — match the *client's* tone in captions/metadata, not Zach's.
  Read `tiktok-manager/config/accounts.json` for the target account's niche + tag style.
- Determinism: no `Date.now()`, no unseeded randomness in any render. Same input → same clip.

---

## The one decision that drives framing: pick the LAYOUT

Every clip uses exactly one of three layout techniques. **DETECT (stage 4) recommends it
for you**; this table is why. Get this right and the framing is right.

| Footage | Technique | Render flag | Plan |
|---|---|---|---|
| **Single talking head**, 1080p+ source | **crop + camera** — full-bleed 9:16 that follows the face and punches in on emphasis | `--fill crop` (default) | 3–5 keyframes, `cx,cy` seeded from DETECT's face track |
| **Screen-share + webcam pip** (reactions, tweet/code reading, demos) | **split** — screen on top, the webcam speaker enlarged on the bottom; fills the whole frame, no dead bars | `--fill split --speaker-box "x,y,w,h"` | 1 static keyframe (the layout frames it, not a camera move) |
| **Wide / multi-subject / scenic / pure slides** | **blur** — show the whole frame fit-to-width with a blurred background fill; nothing cropped | `--fill blur` | 1 centered keyframe |

Rule of thumb: **crop only earns its keep on a single face on a high-res source.** When a
full crop would slice the action out, use split (if there's a webcam to stack) or blur.

---

## Stage 1 — INGEST (download + see + transcribe)

```bash
python ".claude/skills/visual-clipper/scripts/ingest.py" "<url-or-path>" --slug <slug>
```

Downloads the source to `projects/<slug>/source.mp4`, extracts timestamped frames
(auto-fps, 768px) + a timestamped transcript, and writes `projects/<slug>/ingest/manifest.json`
(prints dims, duration, frame count, transcript segments). If it warns there's no transcript,
SCOUT proceeds on frames alone.

## Stage 2 — SCOUT (you watch, you propose)

Read `references/scout-rubric.md`. Then **read the manifest and actually look at the frames** —
Read a spread of the `frames[].path` JPEGs, transcript alongside. Propose **6–10 candidates**
in the rubric's format, citing frame timestamps as visual evidence. Looking at frames is the
whole point — do not clip from text alone.

## Stage 3 — JUDGE ① (clip selection)

Spawn the **clip-judge** subagent with the `manifest.json` path + your full candidate list.
It scores each on hook / payoff / self-contained / visual / share, kills weak and duplicate
clips, and returns a ranked render order.

```
Agent(subagent_type="clip-judge", prompt: "<manifest path> + the candidate list ...")
```

Fallback: if `clip-judge` isn't registered, spawn `general-purpose` and tell it to follow
`references/clip-judge-rubric.md` exactly. Show the user the ranked table, confirm which clips
to render (default: all PASS), and apply any REVISE timestamp fixes.

## Stage 4 — DETECT (content-aware framing — don't guess)

Before eyeballing a crop, let OpenCV say where the content is and which layout to use:

```bash
python ".claude/skills/visual-clipper/scripts/detect.py" \
  "tiktok-manager/projects/<slug>/source.mp4" --start <clip_start> --end <clip_end> \
  --out "tiktok-manager/projects/<slug>/clips/clip_<NN>_detect.json"
```

It returns a face-center track, a median face center, and **`recommend_fill`** — which maps
straight onto the decision table above:

- **`"crop"`** → talking head. Seed your keyframe `cx,cy` from `face_center_median` (stop guessing).
- **`"split"`** → screen-share + webcam pip. It also emits `speaker_box` + `screen_box`; pass
  `speaker_box` to the renderer's `--speaker-box` in stage 7.
- **`"blur"`** → no face (pure slides/screen). Show the whole frame.

## Stage 5 — CAMERA (write the reframe plan) — per chosen clip

Extract dense frames of just that clip so you can see the motion:

```bash
python "$HOME/.claude/skills/watch/scripts/frames.py" \
  "tiktok-manager/projects/<slug>/source.mp4" \
  "tiktok-manager/projects/<slug>/clips/clip_<NN>_frames" \
  --start <clip_start> --end <clip_end> --resolution 768
```

Read those frames + `references/camera-grammar.md`. Write a plan to
`projects/<slug>/clips/clip_<NN>_plan.json` per `templates/reframe-plan.schema.json`.

- **crop layout** → 3–5 keyframes (`cx,cy,zoom` over clip-local `t`) that follow the subject
  and punch in on emphasis. Seed `cx,cy` from DETECT's face track. Default to stillness.
- **split / blur layout** → a single centered keyframe. The layout frames the shot, not a
  camera move; the plan just needs to exist for the renderer.

## Stage 6 — JUDGE ② (framing)

Spawn the **framing-judge** with the plan path, source dims (WxH), and the clip frame paths.
It verifies the crop keeps the subject framed and the motion is sane.

```
Agent(subagent_type="framing-judge", prompt: "<plan path>, dims WxH, clip frame paths ...")
```

Fallback: `general-purpose` + `references/framing-judge-rubric.md`.

- **APPROVE** → render.
- **REVISE** → apply its numeric fixes, re-judge **once**.
- **FALLBACK** (or a 2nd failed REVISE) → single-keyframe plan at the judge's `fallback_center`,
  render with `--mode static`.

(For split/blur layouts the plan is already a static keyframe; the framing-judge mainly
confirms the layout choice fits the footage — see how it's used in `references/framing-judge-rubric.md`.)

## Stage 7 — CUT (captions → lint → render → verify)

Do these **in order**. The caption lint is a hard gate that runs *before* you burn anything.

```bash
# 1) build captions (auto de-dupes rolling YouTube captions; UPPERCASE word-pop chunks)
python ".claude/skills/visual-clipper/scripts/make_srt.py" \
  --manifest "tiktok-manager/projects/<slug>/ingest/manifest.json" \
  --start <clip_start> --end <clip_end> \
  --out "tiktok-manager/projects/<slug>/clips/clip_<NN>.srt"

# 2) LINT the SRT — must exit 0 before you render
python ".claude/skills/visual-clipper/scripts/caption_lint.py" \
  --srt "tiktok-manager/projects/<slug>/clips/clip_<NN>.srt"

# 3) render 9:16 — pick ONE fill per the decision table / DETECT
python ".claude/skills/visual-clipper/scripts/reframe_render.py" \
  --source "tiktok-manager/projects/<slug>/source.mp4" \
  --start <clip_start> --end <clip_end> \
  --plan "tiktok-manager/projects/<slug>/clips/clip_<NN>_plan.json" \
  --out  "tiktok-manager/projects/<slug>/clips/clip_<NN>.mp4" \
  --srt  "tiktok-manager/projects/<slug>/clips/clip_<NN>.srt" \
  [--fill crop|split|blur]  [--speaker-box "x,y,w,h"]  [--mode static]
```

- **Lint gate (step 2):** exit 0 = clean; exit 1 = it found `overlap`, `rolling_repeat`
  (duplicated words — the YouTube rolling-caption artifact), `duplicate_text`, `too_brief`,
  `too_long`, or `empty_text`. **Do not render broken captions.** `make_srt.py` already
  de-dupes and guarantees non-overlap, so a failure means a hand-edit went wrong — re-run
  `make_srt.py`, don't patch the SRT by hand.
- **Fill flag (step 3):** `crop` (default), `split` (needs `--speaker-box` from DETECT;
  optional `--screen-box`, default whole frame; `--split-ratio 0` = fit screen to width and
  give the rest to the speaker), or `blur`. Add `--mode static` for the framing FALLBACK.
  Omit `--srt` to skip burned captions.
- **Verify:** re-extract a couple of frames from the **OUTPUT** clip and look — subject framed,
  captions in the safe zone. If framing is off, it's a plan/box bug; fix and re-render. Never
  claim it's good without looking.

## Stage 8 — JUDGE ③ (captions) — observe the burned-in pixels

Lint proved the timing/duplication is clean (that's math). Now a judge looks at the rendered
captions for what math can't see — legibility, safe-zone placement, sync, not covering the
payload. Reuse your verify frames from the OUTPUT clip:

```
Agent(subagent_type="caption-judge",
      prompt: "OUTPUT-clip frames: <dir>. caption_lint report: <json>. SRT: <path>.")
```

Fallback: if `caption-judge` isn't registered, spawn `general-purpose` and tell it to follow
`references/caption-judge-rubric.md`. APPROVE → ship. REVISE → fix (usually re-run
`make_srt.py`, re-lint), re-judge once. FAIL → a hard defect slipped past the linter: fix it
**and** tighten `caption_lint.py`.

## Stage 9 — PACKAGE (metadata for the channel)

Write `projects/<slug>/clips/clip_<NN>_meta.json`: clip start/end/duration, chosen account,
fill mode, plus social metadata (title, caption, hashtags, 3s hook) in the account's
niche/tag style from `tiktok-manager/config/accounts.json`. Match the client's voice for Whop
accounts. Finish by listing each rendered clip with its path, hook, and one-line why-this-works.

---

## Tuned defaults — don't regress

| Knob | Default | Why |
|---|---|---|
| `make_srt.py --lead` | `0.3` | captions fire 0.3s early to beat auto-caption lag |
| `make_srt.py --words-per-chunk` | `2` | short word-pop chunks; bump to 3 for slower VO |
| rolling de-dup | always on | collapses YouTube's repeated rolling lines — no doubled captions |
| burned font | `FontSize=9, Shadow=0`, `MarginV=60` (libass script-space) | ~60px on 1920, crisp outline, lower-third safe zone. >10 looks oversized |
| `reframe_render --blur-zoom` | `1.3` | blur fill: enlarge content so blurred bars stay small (1.0 = biggest bars) |
| `reframe_render --zoom-out` | `0.08` | crop fill: thin blurred border so it's not maxed-out tight (0 = full-bleed) |
| `reframe_render --split-ratio` | `0` | split: fit screen to width (no crop), rest to the speaker |
| `caption_lint --max-cps / --max-dur / --min-dur` | `24 / 7 / 0.10` | reading speed (long cues only), stuck-caption, and blink floors |

## Notes

- Requires `yt-dlp` + `ffmpeg`/`ffprobe` (same as /watch). Whisper fallback (videos without
  captions) needs `GROQ_API_KEY`/`OPENAI_API_KEY` in `~/.config/watch/.env`.
- Face-aware framing is built in via `detect.py` (OpenCV). *Legacy option:* if Cloudinary
  creds exist in `tiktok-manager/.env`, `tiktok-manager/scripts/run_clipper.py reframe
  --gravity faces` does a cloud face-aware static crop — but prefer `detect.py` + `--fill`,
  which needs no external service.
- Temp render files go to the OS temp dir; the renderer cleans up after itself.

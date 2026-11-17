# CAMERA grammar — writing a reframe plan

After a clip is chosen, you re-watch **only that clip's frames** (extracted dense,
so you can see the motion) and write a `reframe-plan.json` that tells
`reframe_render.py` how to move a 9:16 crop window over the landscape source.

You are the camera operator. The landscape frame is your stage; the 9:16 window
is your viewfinder. Your job: keep the subject well-placed and use motion to
serve the story — not to show off.

## The coordinate system
- `cx`, `cy` ∈ [0,1] = the **center** of the crop window, as a fraction of the
  SOURCE frame. `cx=0` is the left edge, `cx=1` the right; `cy=0` top, `cy=1` bottom.
- `zoom` ≥ 1.0. `1.0` = the widest 9:16 crop that fits the source height.
  `1.3`–`1.5` = a comfortable punch-in. Above ~1.8 you risk softness on 1080p sources.
- `t` = **clip-local** seconds (0 = start of the clip).

## How to read the frames into a plan
1. **Locate the subject** in each frame. Where is the face / the action? That's
   where `cx,cy` should point. A talking head camera-left → `cx≈0.35`. Centered → `cx≈0.5`.
2. **Keep eyes in the upper third.** For a face, aim `cy≈0.40–0.45` so the eyeline
   sits high in the vertical frame (not dead center — that looks like a mugshot).
3. **Follow, don't jump.** If the subject moves across the frame, move `cx` with
   them across keyframes. The render interpolates linearly = a smooth pan.
4. **Hold by repeating.** Two keyframes with the same values = a static hold.
5. **Punch in on emphasis.** On the key line / the reveal, raise `zoom` to 1.3–1.5.
   Pull back to 1.0 for wide reactions or to reveal a screen/product.

## Grammar of good moves
- **Default to stillness.** A locked, well-composed frame beats constant drifting.
  Most clips need 3–5 keyframes, not 15.
- **One idea per move.** Either follow the subject OR punch in — rarely both at once.
- **Motion takes time.** Give a pan/zoom ≥0.8s between its start and end keyframes,
  or it snaps and looks jittery.
- **Land moves before the line they serve.** Finish a punch-in *as* the emphasis
  word hits, not after.
- **Respect headroom.** Never crop the top of the head off. If the subject is tall
  in frame, pull `zoom` toward 1.0 rather than slicing the forehead.

## When NOT to crop at all — pick split or blur instead
A full-bleed 9:16 crop of a 16:9 source magnifies ~2.7x (worse on 720p), so for
anything that isn't a single high-res talking head, the crop+camera path loses the
action. DETECT (stage 4) tells you which alternative to use; the two are:

- **`--fill split`** — when there's a **screen-share with a webcam pip** (reactions,
  tweet/code reading, demos). Stacks the screen on top and the enlarged webcam speaker
  on the bottom, filling the whole frame with real content. Pass DETECT's `speaker_box`.
  This beats blur whenever there's a webcam to stack — no dead bars.
- **`--fill blur`** — when there's **no webcam to stack**: wide/multi-subject scenes,
  scenic or comedy footage, or pure slides. Shows the whole frame fit-to-width with a
  blurred background fill, nothing cropped.

For **both** split and blur the camera keyframes don't apply — just write a single
centered keyframe so the plan validates. Reserve the crop+camera path (punch-ins,
follows) for single-subject talking heads on a high-res source, where it earns its keep.

## Safety / fallback
If the source is busy, multiple speakers cut fast, or you genuinely can't tell
where to look, write a **single stable keyframe** (one entry, `zoom` 1.0–1.15,
centered on the dominant subject). The renderer treats that as static mode — a
clean center-ish crop is always better than a confused camera. The orchestrator
can also run `--mode static` to force this.

## Output
Write strictly to the schema in `../templates/reframe-plan.schema.json`. Keyframes
ordered by `t`, first at or near 0, last at or near clip duration. Include short
`note`s so the framing-judge can check your intent against the frames.

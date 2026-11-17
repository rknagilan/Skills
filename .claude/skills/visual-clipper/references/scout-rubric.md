# SCOUT rubric — finding clip candidates

You are scouting a long video for short-form clips. You have two signals and you
**must use both**: the **frames** (what the video looks like, moment to moment)
and the **transcript** (what is said, with timestamps). The whole point of this
skill is that you are not clipping blind from text — you are *watching*.

## What makes a clip
A great short is a **self-contained payoff**. Someone scrolling should get a
complete little arc in 15–60s: a hook, tension, and a resolution — without needing
the rest of the video.

Look for candidates where the visual signal AND the verbal signal agree:

- **Hook moments** — a surprising claim, a bold opener, a question that demands an answer. In frames: a lean-in, direct-to-camera, a sharp expression.
- **Payoff / reveal** — the "oh" moment, a result shown, a before/after. In frames: a screen reveal, a product shown, a reaction.
- **Energy peaks** — laughter, emphasis, raised hands, fast cuts. The transcript alone hides these; the frames show them.
- **Demonstrations** — something is *shown*, not just described. These clip well because they're inherently visual.
- **Quotable lines** — a crisp, standalone sentence that works as an on-screen caption.

## Avoid
- Clips that depend on earlier context to make sense ("as I said before…").
- Mid-thought starts or ends — cut on clean sentence boundaries.
- Long dead air, filler, "um"-heavy stretches, throat-clearing intros.
- Anything where the frames show nothing is happening (static slide, no speaker presence) unless the audio truly carries it.

## Boundaries
- Start ~0.3–0.8s **before** the first word so it doesn't feel clipped.
- End on the beat after the payoff lands — don't trail into the next topic.
- Target 15–60s. If a moment is great but 90s, note a tighter inner cut.

## Output
Propose **6–10 candidates**, ranked by your own gut. For each:

```
- clip: <n>
  start: <source seconds>   end: <source seconds>   (~<dur>s)
  hook: "<the first spoken line, verbatim>"
  arc: <one line: setup → payoff>
  visual: <what the FRAMES show that makes this work — cite frame timestamps>
  why: <one line: why someone stops scrolling>
```

Cite frame timestamps (e.g. "speaker leans in at 0:74, screen reveal at 0:81")
so the judge and camera stages can trust you actually watched.

# Skills Catalog — Instagram, YouTube, Reverse Engineering, Audio, Animation

This is a list of Claude skills and plugins that I found for each topic (November 2026).
Most of them are community plugins. Read a skill's SKILL.md before you use it.

## How to install

**Option A: Claude app plugin directory (easiest)**
1. Open the Claude app, then go to **Settings → Plugins** (or Customize → Plugins).
2. Search for the plugin name from the tables below.
3. Click **Install** or **Enable**.

**Option B: Command line (skills from GitHub)**
```bash
npx skills add <owner>/<repo> --skill <skill-name> --agent claude-code
```

**Option C: Copy it by hand**
Put the skill folder (the folder that has `SKILL.md` in it) in one of these places:
- `~/.claude/skills/<skill-name>/` (works in every project)
- `<your-project>/.claude/skills/<skill-name>/` (works in this project only)

---

## 1. Instagram

| Plugin / Skill | What it does |
|---|---|
| **Social Media Skills** → `instagram-growth`, `instagram-reels-publishing`, `instagram-seo`, `reels-script`, `carousel-writer`, `caption-writer`, `hashtag-strategy`, `story-writer`, `profile-optimization` | Grow an account, write Reels scripts, captions, carousels and hashtags |
| **instagram** plugin | Read and reply to comments and DMs through the official Instagram Graph API |
| **IT Reelsmaker** | Edit talking-head clips into Reels with subtitles and motion graphics |
| **Posty / Ayrshare / Social media studio** | Schedule and publish posts to Instagram and other networks |

## 2. YouTube

| Plugin / Skill | What it does |
|---|---|
| **TubeAlfred YouTube** (15 skills) | Transcripts, comments, channel audit, SEO audit, keyword ideas, competitors, Shorts |
| **YouTube Transcriber** | Free captions/transcripts for videos and playlists |
| **Social Media Skills** → `youtube-long-form`, `youtube-shorts`, `youtube-publishing-and-metadata`, `thumbnail-design`, `viral-reverse-engineering` | Video scripts, titles, descriptions, thumbnails |
| **watch-video** | Claude "watches" a video: keyframes + Whisper transcription |
| **video-to-code-skill** | Turn screen recordings into keyframes + transcript |

## 3. Reverse Engineering

> Use these only on software you own, or for CTFs, malware research or authorized security work.

| Plugin / Skill | What it does |
|---|---|
| **Reverse Engineering** plugin (Anthropic directory) | General binary reverse engineering skill |
| `sickn33/antigravity-awesome-skills` → `reverse-engineer` | IDA Pro, Ghidra, radare2, x64dbg, pwntools, angr, capstone |
| `popey/claude-code-skills` → `reverse-engineer` | Disassembly, decompiling, IDAPython / Ghidra scripts |
| `mukul975/Anthropic-Cybersecurity-Skills` → `reverse-engineering-malware-with-ghidra` | Malware analysis with Ghidra |
| `a5c-ai/babysitter` → Ghidra/IDA skill | Headless Ghidra automation |
| MCP servers: `LaurieWired/GhidraMCP`, `mrexodia/ida-pro-mcp` | Connect Claude straight to Ghidra or IDA |

Install example:
```bash
npx -y skills add sickn33/antigravity-awesome-skills --skill reverse-engineer --agent claude-code
```

## 4. Sound and Audio

| Plugin / Skill | What it does |
|---|---|
| **AudioPod** | Transcribe, split songs into stems, remove noise, audio → MIDI |
| **Audiorective** | Build synths, sequencers and audio visualizers with Web Audio |
| **Video Cleanup** | Clean speech audio (noise, loudness) in videos |
| **Abracadabrax** (3 plugins) | AI background music, songs, podcast jingles (uses paid credits) |
| **Social Media Skills** → `ai-music-and-sound`, `ai-voiceover`, `suno`, `podcast-and-audiograms` | Prompts and workflows for AI music and voice |
| **Twilio** `twilio-call-recordings`, `twilio-voice-conversation-relay` (already enabled) | Record calls and build voice AI |

## 5. Animation and Motion

| Plugin / Skill | What it does |
|---|---|
| **Remotion** (official, 12 skills) | Videos and animations with React: captions, audio, 3D, render |
| **animation-studio** | Hand-drawn animated short films with code-made music |
| **Motion Reel** | Motion graphics videos with music and sound effects |
| **Tweenkit** | Animated PPTX, kinetic videos, animated HTML pages |
| **Sticklore** | Stick-figure explainer animations |
| **Skills for React/React Native** → `gsap-*`, `reanimated-*`, `css-animations`, `ui-motion` | GSAP and Reanimated animation for apps and websites |
| **audit-suite** → `web-animation-design` | Rules for good web animation |
| **Very Good AI Flutter** → `animations` | Flutter animations |
| Built-in: `anthropic-skills:algorithmic-art`, `anthropic-skills:slack-gif-creator`, `anthropic-skills:canvas-design` | Generative art, animated GIFs, posters |

Remotion install:
```bash
npx skills add remotion-dev/skills
```

---

## Big skill collections (for more)

- [VoltAgent/awesome-agent-skills](https://github.com/VoltAgent/awesome-agent-skills) — 1000+ skills
- [mouadja02/skills](https://github.com/mouadja02/skills)
- [karanb192/awesome-claude-skills](https://github.com/karanb192/awesome-claude-skills)
- [abubakarsiddik31/claude-skills-collection](https://github.com/abubakarsiddik31/claude-skills-collection)
- [glebis/claude-skills](https://github.com/glebis/claude-skills)
- [lyndonkl/claude](https://github.com/lyndonkl/claude)
- [Remotion skills docs](https://www.remotion.dev/skills)

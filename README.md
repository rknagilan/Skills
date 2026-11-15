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

---

## 6. Skills from the Instagram creator @igao.ia (Reels analysis)

Instagram cannot be opened from the cloud session, so this list comes from the 9 video covers
(the titles are in Portuguese) plus a web search for each tool. ✅ = confirmed tool, 🔶 = best guess.

| # | Video title (Portuguese → English) | Views | Skill / tool | How to get it |
|---|---|---|---|---|
| 1 | "Essa config ultrapassou o próprio Claude Code" → *This config beat Claude Code itself* | 40.6K | ✅ **Everything Claude Code (ECC)** — the yellow "E" logo. Big pack of agents, skills, hooks, rules | `/plugin marketplace add affaan-m/everything-claude-code` |
| 2 | "Por que seus Reels não viralizam — o Claude te mostra" → *Why your Reels don't go viral* | 11.8K | 🔶 Reel analysis: Claude watches your Reel and checks hook (gancho), retention and the second where people leave | `watch-video` plugin + Social Media Skills `viral-reverse-engineering`, `content-audit` |
| 3 | "Claude copia qualquer vídeo cena por cena" → *Claude copies any video scene by scene* | 59.5K | 🔶 Video → storyboard → remake. Claude breaks a video into scenes, then rebuilds it | `watch-video` / `video-to-code-skill` + **Remotion** |
| 4 | "Por que ninguém assiste seus vídeos?" → *Why does nobody watch your videos?* ("3 iguais", "Modelo 07") | 12K | 🔶 Hook / template tester: makes many hook versions and picks the best one | Social Media Skills `hook-writer`, `experimentation-and-ab-testing` |
| 5 | "Crie o seu clone virtual com IA, de graça" → *Make your AI virtual clone for free* | 24.6K | ✅ **LongCat-Video-Avatar 1.5** (Meituan, open source). A talking avatar from 1 photo + audio | github.com/meituan-longcat/LongCat-Video (needs a strong GPU) |
| 6 | "Meu Claude edita à meia-noite enquanto eu durmo" → *My Claude edits at midnight while I sleep* | 9.1K | 🔶 "Máquina de Reels" (Reels Machine): a scheduled Claude Code job. It finds viral Reels → writes script → narration → edit → review | Claude Code scheduled tasks / `/loop` + the skills below |
| 7 | "A skill que descobre o próximo viral no Claude, grátis" → *The skill that finds the next viral trend* ("Últimos 30 dias", ⭐66.3K) | 18.3K | ✅ **last30days-skill** by mvanhorn. Searches Reddit, X, YouTube, TikTok, Instagram and the web from the last 30 days | `/plugin marketplace add mvanhorn/last30days-skill` |
| 8 | "Um Google Meu Negócio dentro do ChatGPT" → *Google My Business inside ChatGPT* | 16.1K | 🔶 A Google Business Profile connector/app for ChatGPT (it is not a Claude skill) | — |
| 9 | "O Claude transforma sua ideia em um Reels" → *Claude turns your idea into a Reel* | 21.2K | 🔶 The same "máquina-de-reels" project: idea → script → voice → video | **IT Reelsmaker**, **Remotion**, **Motion Reel**, Social Media Skills `reels-script` |

### Build your own "Reels Machine" (step by step)
1. **Find a trend** → `last30days-skill`
2. **Study viral videos** → `watch-video` + `viral-reverse-engineering`
3. **Write the script** → `reels-script`, `hook-writer`
4. **Voice** → `ai-voiceover` (or ElevenLabs)
5. **Make the video** → **Remotion** / **IT Reelsmaker** / **Motion Reel**
6. **Avatar (optional)** → LongCat-Video-Avatar
7. **Post** → Posty / Ayrshare
8. **Run every night** → a Claude Code scheduled task

### About the creator
- @igao.ia is **Igor Henrique** (Brazil, Portuguese content).
- His paid product: **Máquina de Reels**: https://maquina.igorhenrique.com/ (a plug-and-play file for Claude Code / Codex that edits Reels: cuts, captions, animations).
- Free projects with a similar idea on GitHub (not his):
  - [Fabio-araujo-silva/maquina-de-reels](https://github.com/Fabio-araujo-silva/maquina-de-reels): prompt → vertical reel (script, voice, 3D, render)
  - [gt-moraes/entusiasta-motion](https://github.com/gt-moraes/entusiasta-motion): Claude Code skill that edits full Reels with Remotion
  - [Jakeschincariol/instagram-agent-skill](https://github.com/Jakeschincariol/instagram-agent-skill): 13 free Instagram skills (hooks, viral research, captions)
  - [masterpz/skill-edicao-reels](https://github.com/masterpz/skill-edicao-reels), [Felpborges/skill-reel](https://github.com/Felpborges/skill-reel), [lucalves3/skill-de-roteiro-reels](https://github.com/lucalves3/skill-de-roteiro-reels)

### Igor Henrique's website (igorhenrique.com): what it offers
Found through search results (the site itself is blocked from the cloud session).

| Page | What it is | Price |
|---|---|---|
| igorhenrique.com | Link page: IA Academy, Octuz AI, free prompt group, YouTube lessons | free |
| **maquina.igorhenrique.com**: *Máquina de Reels Automáticos* | Plug-and-play file for **Claude Code or Codex** that edits Reels from a Portuguese prompt (cuts, captions, animations) + 7 short lessons. Bonuses: **cover factory** (capas) and **animation library** | R$ 97 |
| ia.igorhenrique.com / club.igorhenrique.com: *IA Academy* | Course: AI apps, virtual influencers, AI automation | R$ 97 – 197 |
| mentoria.igorhenrique.com | Marketing funnel course with AI | paid |

The site does **not** publish a public list of the skills inside the Máquina de Reels. It is a paid zip file.

### Free alternatives that do the same job (open source)
- [emersonsvale/reels-em-codigo](https://github.com/emersonsvale/reels-em-codigo): script → animated Reel with voice, karaoke captions, end card
- [javiggil/reels-con-ia](https://github.com/javiggil/reels-con-ia): cut silences, 4K captions and animations
- [clabza16/skills-edicion](https://github.com/clabza16/skills-edicion): zooms, karaoke subtitles, titles, motion effects, sound
- [gouveaero/claude-skills-content](https://github.com/gouveaero/claude-skills-content): carousels, Remotion video, weekly plan, trend research
- [augustollgarcia-max reels-automatico PR](https://github.com/augustollgarcia-max/ui-ux-pro-max-skill/pull/76): FFmpeg + Whisper + Remotion reels machine
- [Artem Novitckii: 6 editing skills](https://novitckii.com/resources/editing-skills/) · [6 animation skills](https://novitckii.com/resources/animation-skills/)

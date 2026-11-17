#!/usr/bin/env bash
# Installs 2 extra skills that have no license file (so they are not stored in this repo).
# Run from the repo root:  bash scripts/install-extra-skills.sh
set -euo pipefail
cd "$(dirname "$0")/.."

# 1. upload-post: post Reels/videos to Instagram, TikTok, YouTube... (needs an upload-post.com API key)
npx -y skills add Upload-Post/upload-post-skill --agent claude-code -y

# 2. twitch-clips: Twitch VOD -> 9:16 clips (macOS Apple Silicon only, Russian instructions)
tmp="$(mktemp -d)"
git clone -q --depth 1 https://github.com/NikitaPPP017/twitch-clips.git "$tmp/twitch-clips"
mkdir -p .claude/skills
cp -R "$tmp/twitch-clips/.claude/skills/twitch-clips" .claude/skills/
echo "Done: upload-post and twitch-clips installed in .claude/skills/"

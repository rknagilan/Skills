#!/usr/bin/env bash
# MontClipper setup. Safe to run again: it only adds what is missing.
# Engine: the folder this script is in. Your clips, recordings and settings: $MONTCLIPPER_HOME, else ~/MontClipper.
set -e
SKILL="$(cd "$(dirname "$0")" && pwd)"
case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) WIN=1 ;; *) WIN=0 ;; esac
H="${MONTCLIPPER_HOME:-$HOME/MontClipper}"
echo "MontClipper setup"
echo "  engine: $SKILL"
echo "  your clips folder: $H"

missing=""
TOOLS="ffmpeg ffprobe streamlink yt-dlp uv curl"
[ "$WIN" = 1 ] || TOOLS="$TOOLS whisper-cli"      # on Windows, setup downloads whisper.cpp itself
for t in $TOOLS; do
  command -v "$t" >/dev/null 2>&1 || missing="$missing $t"
done
command -v claude >/dev/null 2>&1 || command -v codex >/dev/null 2>&1 || missing="$missing claude-or-codex"
if [ -n "$missing" ]; then
  echo ""
  echo "Missing:$missing"
  if [ "$WIN" = 1 ]; then
    echo "Install on Windows (Terminal from the Start menu, one line at a time), then reopen Terminal:"
    echo "  winget install Gyan.FFmpeg"
    echo "  winget install Streamlink.Streamlink"
    echo "  winget install yt-dlp.yt-dlp"
    echo "  winget install astral-sh.uv"
  else
    echo "Install on a Mac with Homebrew (https://brew.sh):"
    echo "  brew install ffmpeg streamlink yt-dlp whisper-cpp uv"
  fi
  echo "AI agent: Claude Code (https://claude.com/claude-code) or Codex (https://chatgpt.com/codex)"
  echo "Then run this setup again."
  exit 1
fi

mkdir -p "$H/Upload to Socials/Done" "$H/Recordings (auto-deleted)" "$H/channels" "$H/models/panns"

# Speech-to-text model (whisper.cpp large-v3-turbo, about 570 MB)
W="$H/models/ggml-large-v3-turbo-q5_0.bin"
if [ ! -s "$W" ]; then
  echo "Downloading the speech model (about 570 MB) ..."
  curl -L --fail --retry 3 -o "$W.part" "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo-q5_0.bin"
  mv "$W.part" "$W"
fi

# MontClipper's own Python (numpy, Pillow) with the music checker: PANNs sound tagger (about 1.5 GB with PyTorch)
A="$H/tools-audio"
PY="$A/bin/python"; [ "$WIN" = 1 ] && PY="$A/Scripts/python.exe"
if [ ! -x "$PY" ]; then
  echo "Setting up the music checker ..."
  uv venv --python 3.12 "$A"
fi
"$PY" -c "import torch, panns_inference, librosa, soundfile, PIL" 2>/dev/null || \
  uv pip install --python "$PY" torch panns-inference librosa soundfile numpy pillow
# Windows: whisper.cpp speech-to-text program (CPU build)
if [ "$WIN" = 1 ] && ! command -v whisper-cli >/dev/null 2>&1 && [ ! -f "$H/bin/whisper/Release/whisper-cli.exe" ]; then
  echo "Downloading whisper.cpp ..."
  mkdir -p "$H/bin/whisper"
  curl -L --fail --retry 3 -o "$H/bin/whisper.zip" "https://github.com/ggml-org/whisper.cpp/releases/download/b5454/whisper-bin-x64.zip"
  "$PY" -m zipfile -e "$H/bin/whisper.zip" "$H/bin/whisper" && rm -f "$H/bin/whisper.zip"
fi

P="$H/models/panns/Cnn14_mAP=0.431.pth"
if [ ! -s "$P" ]; then
  echo "Downloading the music checker model (about 330 MB) ..."
  curl -L --fail --retry 3 -o "$P.part" "https://zenodo.org/record/3987831/files/Cnn14_mAP%3D0.431.pth?download=1"
  mv "$P.part" "$P"
fi
L="$HOME/panns_data/class_labels_indices.csv"
if [ ! -s "$L" ]; then
  mkdir -p "$HOME/panns_data"
  curl -L --fail --retry 3 -o "$L" "http://storage.googleapis.com/us_audioset/youtube_corpus/v1/csv/class_labels_indices.csv"
fi

chmod +x "$SKILL/mc"
[ -f "$H/User guide.md" ] || cp "$SKILL/USER-GUIDE.md" "$H/User guide.md"
echo ""
MONTCLIPPER_HOME="$H" "$SKILL/mc" check

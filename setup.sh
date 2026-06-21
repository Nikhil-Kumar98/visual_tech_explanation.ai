#!/usr/bin/env bash
# ============================================================
# visual_tech_explanation.ai — one-shot setup
# Installs system deps, creates a venv, installs Python packages,
# and pulls a local LLM for free offline script writing.
# Safe to re-run.
# ============================================================
set -euo pipefail

cd "$(dirname "$0")"

echo "==> Checking Homebrew"
if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew not found. Install it from https://brew.sh first." >&2
  exit 1
fi

echo "==> Installing system dependencies (ffmpeg, ollama)"
brew list ffmpeg >/dev/null 2>&1 || brew install ffmpeg
brew list ollama >/dev/null 2>&1 || brew install ollama

echo "==> Creating Python virtual environment (.venv)"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> Installing Python packages"
pip install --upgrade pip >/dev/null
pip install -r requirements.txt

echo "==> Starting Ollama service"
brew services start ollama >/dev/null 2>&1 || true
sleep 2

MODEL="$(python3 -c "import yaml;print(yaml.safe_load(open('config/config.yaml'))['script']['model'])")"
echo "==> Pulling local LLM: ${MODEL} (one-time download)"
ollama pull "${MODEL}" || echo "WARN: could not pull ${MODEL}; pull it manually later."

echo "==> Creating asset folders"
mkdir -p assets/broll assets/output assets/work assets/branding assets/voice

cat <<'DONE'

============================================================
Setup complete.

Next steps:
  1. Add B-roll clips to assets/broll/  (see data/kling_broll_prompts.md)
  2. Activate the env:   source .venv/bin/activate
  3. Make one video:     python -m src.orchestrator --topic "how LLMs work"
  4. Or run the queue:   python -m src.orchestrator --batch

Everything runs locally for $0. Edit config/config.yaml to tune it.
============================================================
DONE

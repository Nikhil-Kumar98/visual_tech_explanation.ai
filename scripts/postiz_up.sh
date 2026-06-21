#!/usr/bin/env bash
# ============================================================
# Self-host Postiz (free, open-source) to auto-post to
# YouTube / Instagram / TikTok from this pipeline.
#
# Postiz's services/env-vars change between releases, so we clone the
# OFFICIAL compose repo (recommended by their docs) rather than vendoring it.
# ============================================================
set -euo pipefail
cd "$(dirname "$0")/.."

POSTIZ_DIR="postiz"

echo "==> Checking Docker"
if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed."
  echo "Install Docker Desktop, then re-run this script:"
  echo "    brew install --cask docker"
  echo "    open -a Docker        # start it once, finish onboarding"
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo "Docker is installed but not running. Start Docker Desktop (open -a Docker) and re-run." >&2
  exit 1
fi

echo "==> Fetching the official Postiz docker-compose"
if [ ! -d "${POSTIZ_DIR}/.git" ]; then
  git clone https://github.com/gitroomhq/postiz-docker-compose "${POSTIZ_DIR}"
else
  git -C "${POSTIZ_DIR}" pull --ff-only || true
fi

echo "==> Starting Postiz (this pulls images on first run)"
( cd "${POSTIZ_DIR}" && docker compose up -d )

cat <<'DONE'

============================================================
Postiz is starting. Next steps:

  1. Open the UI:        https://localhost:4007
     (accept the self-signed cert warning; create your admin user)
  2. Settings -> Channels: connect YouTube, Instagram, TikTok
     (each platform walks you through OAuth)
  3. Settings -> API:      generate an API key, then export it:
        export POSTIZ_API_KEY="paste-key-here"
  4. In config/config.yaml set:
        posting.backend: postiz
        posting.postiz_url: http://localhost:4007   # match the UI port
     Keep auto_publish: false at first -> posts land as DRAFTS to review.
  5. Produce + push a video:
        python -m src.orchestrator --topic "how LLMs work"

Stop Postiz:   ( cd postiz && docker compose down )
Logs:          ( cd postiz && docker compose logs -f )
============================================================
DONE

# visual_tech_explanation.ai

Automated, **$0/month** pipeline that turns a tech topic into a finished
vertical explainer video — script, voice-over, captions, B-roll, and a
ready-to-post file — then queues it for publishing. Built to run locally on a
Mac (Apple Silicon).

```
topic ─► local LLM writes script + scenes + B-roll tags
      ─► local TTS voices each scene
      ─► picks matching clips from your reusable Kling B-roll library
      ─► ffmpeg stitches video + captions (9:16) + optional music/intro/outro
      ─► stages the video + caption for review (or posts via Postiz)
```

## Why a B-roll *library* (the honest design choice)
Kling's free daily credits only work through their website — there is **no free
API**, and scripting their UI breaks constantly and violates their TOS. So
instead of generating new video every day, you generate a small library of
reusable, generic tech clips **once** (neural nets, servers, code, particles…)
and the automation reuses them forever. Result: fully automated *and* free.

## The 100% free stack
| Step | Tool | Cost |
|---|---|---|
| Script writing | Local LLM via **Ollama** (offline) | free |
| Voice-over | macOS **`say`** (default) → upgradeable to local **XTTS** voice clone, or paid **ElevenLabs** | free |
| B-roll | **Kling** free credits → reused library | free |
| Editing / captions | **ffmpeg** | free |
| Posting | **Postiz** (self-host) or a safe local review queue | free |
| Orchestration | **Python** | free |

Every backend is swappable from `config/config.yaml` — no code changes.

## Quick start
```bash
./setup.sh                       # installs deps, venv, pulls the local LLM
source .venv/bin/activate

# 1) Build your B-roll library (one time):
#    Use the prompts in data/kling_broll_prompts.md on Kling (free),
#    download the clips, and drop them in assets/broll/

# 2) Make a single video:
python -m src.orchestrator --topic "how LLMs work"

# 3) Or produce the next batch from the topic queue:
python -m src.orchestrator --batch
```
Finished videos land in `assets/output/`; review copies + captions go to
`assets/output/queue/`.

## Auto-posting with Postiz (YouTube / Instagram / TikTok)
Postiz is free + open-source and posts to all platforms from one place.

```bash
# 1) Stand up Postiz locally (clones the official compose, needs Docker):
./scripts/postiz_up.sh
#    If Docker isn't installed:  brew install --cask docker && open -a Docker

# 2) In the Postiz UI (https://localhost:4007):
#    - create your admin user
#    - Settings -> Channels: connect YouTube, Instagram, TikTok (OAuth)
#    - Settings -> API: generate an API key

# 3) Point the pipeline at Postiz:
export POSTIZ_API_KEY="your-key"
#    config/config.yaml -> posting.backend: postiz   (keep auto_publish: false)

# 4) Produce + push (lands as DRAFTS for you to approve in Postiz):
python -m src.orchestrator --topic "how LLMs work"
```
Until you set `posting.auto_publish: true`, posts are staged as drafts (YouTube
`private`, TikTok `SELF_ONLY`) so nothing goes live without your OK. Per-platform
options live under `posting.platform_settings` in the config.

## Daily automation (2 videos/day)
```bash
python scripts/run_daily.py --at 09:00     # leave running
# or hands-off via cron/launchd:
#   cd /path/to/repo && .venv/bin/python -m src.orchestrator --batch
```
Topics are read top-down from `data/topics.txt`; finished ones are recorded in
`data/topics_done.txt` so they aren't repeated.

## Your phased plan
- **Phase 1 (now):** B-roll loop + AI voice + clean captions. Grow the audience.
- **Phase 2 (later):** introduce your face/voice clone — flip `voice.backend`
  to `xtts` (free, clones your voice from a short sample) or `elevenlabs`.

## Project layout
```
config/config.yaml          all settings (backends, sizes, posting…)
data/topics.txt             topic queue
data/kling_broll_prompts.md prompts to build your B-roll library
src/
  config.py                 config loader
  script_generator.py       topic -> script + scenes + B-roll tags (Ollama/Gemini)
  voice.py                  TTS: say | xtts | elevenlabs (swappable)
  broll_library.py          tag-matching clip picker
  captions.py               SRT generation
  assembler.py              ffmpeg stitch + captions + music (9:16)
  poster.py                 publish: queue | postiz
  orchestrator.py           end-to-end pipeline + topic queue
scripts/run_daily.py        daily scheduler
scripts/postiz_up.sh        self-host Postiz for auto-posting
assets/broll/               your reusable Kling clips
assets/output/              finished videos (+ /queue for review)
assets/branding/            optional intro.mp4 / outro.mp4 / music.mp3
```

## Configuration highlights (`config/config.yaml`)
- `voice.backend`: `say` (free, default) → `xtts` (free clone) → `elevenlabs` (paid)
- `script.model`: any Ollama model (default `llama3.1:8b`)
- `video.captions`, `caption_font_size`, `music_volume`, dimensions/fps
- `posting.backend`: `queue` (safe review) or `postiz`; `auto_publish` gate

## Notes
- First `say`/ffmpeg run needs no model download; XTTS downloads weights on first use.
- Nothing is auto-published unless you set `posting.auto_publish: true`.

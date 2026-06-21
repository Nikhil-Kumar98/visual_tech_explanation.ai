"""Publish finished videos. Default backend is a safe local queue.

Backends (config posting.backend):
  - "queue"  : write video + caption + metadata to assets/output/queue/ for you
               to review and upload. Zero risk. DEFAULT.
  - "postiz" : push to a self-hosted Postiz instance which fans out to
               YouTube / Instagram / TikTok. Free + open source.

Nothing is auto-published unless posting.auto_publish is true.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from .config import Config, load_config
from .models import VideoScript
from .utils import get_logger, slugify

log = get_logger(__name__)


def build_caption(script: VideoScript) -> str:
    tags = " ".join(script.caption_hashtags)
    return f"{script.title}\n\n{script.hook}\n\n{tags}".strip()


class QueuePoster:
    def __init__(self, cfg: Config):
        self.queue_dir = cfg.path("paths.output") / "queue"
        self.queue_dir.mkdir(parents=True, exist_ok=True)

    def publish(self, video: Path, script: VideoScript) -> dict:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        base = f"{stamp}-{slugify(script.title)}"
        dst = self.queue_dir / f"{base}.mp4"
        shutil.copy2(video, dst)
        caption = build_caption(script)
        (self.queue_dir / f"{base}.txt").write_text(caption, encoding="utf-8")
        meta = {
            "video": str(dst),
            "title": script.title,
            "topic": script.topic,
            "caption": caption,
            "status": "staged",
            "created": stamp,
        }
        (self.queue_dir / f"{base}.json").write_text(
            json.dumps(meta, indent=2), encoding="utf-8"
        )
        log.info("Staged for review: %s", dst)
        return meta


class PostizPoster:
    """Publish via a (self-hosted) Postiz instance using its public API.

    Flow per the Postiz public API:
      1. GET  /public/v1/integrations          -> map platform -> integration id
      2. POST /public/v1/upload (multipart)    -> {id, path} for the video
      3. POST /public/v1/posts                 -> one entry per integration,
                                                  each with platform settings
    Defaults to type="draft" (auto_publish: false) so you approve in the Postiz
    UI before anything goes live.
    """

    def __init__(self, cfg: Config):
        import os
        url = cfg.get("posting.postiz_url", "http://localhost:4007").rstrip("/")
        self.api_base = f"{url}/api/public/v1"
        self.platforms = [p.lower() for p in cfg.get("posting.platforms", [])]
        self.auto = cfg.get("posting.auto_publish", False)
        self.settings_cfg = cfg.get("posting.platform_settings", {}) or {}
        self.api_key = os.environ.get("POSTIZ_API_KEY", "")

    def _headers(self) -> dict:
        return {"Authorization": self.api_key}

    def _integrations(self):
        import requests
        resp = requests.get(
            f"{self.api_base}/integrations", headers=self._headers(), timeout=60
        )
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else data.get("integrations", [])

    def _upload(self, video: Path) -> dict:
        import requests
        with open(video, "rb") as fh:
            resp = requests.post(
                f"{self.api_base}/upload", headers=self._headers(),
                files={"file": (video.name, fh, "video/mp4")}, timeout=600,
            )
        resp.raise_for_status()
        media = resp.json()
        return {"id": media["id"], "path": media["path"]}

    def _settings_for(self, identifier: str, script: VideoScript) -> dict:
        """Per-platform required settings, with config overrides."""
        title = script.title[:95]
        tags = [{"value": h.lstrip("#"), "label": h.lstrip("#")}
                for h in script.caption_hashtags[:8]]
        defaults = {
            "youtube": {
                "__type": "youtube",
                "title": title,
                "type": "public" if self.auto else "private",
                "selfDeclaredMadeForKids": "no",
                "tags": tags,
            },
            "instagram": {
                "__type": "instagram",
                "post_type": "post",
                "is_trial_reel": False,
                "collaborators": [],
            },
            "instagram-standalone": {
                "__type": "instagram-standalone",
                "post_type": "post",
                "is_trial_reel": False,
                "collaborators": [],
            },
            "tiktok": {
                "__type": "tiktok",
                "privacy_level": "PUBLIC_TO_EVERYONE" if self.auto else "SELF_ONLY",
                "duet": True,
                "stitch": True,
                "comment": True,
                "autoAddMusic": "no",
                "brand_content_toggle": False,
                "brand_organic_toggle": False,
                "video_made_with_ai": True,
                "content_posting_method": "UPLOAD",
            },
        }
        base = defaults.get(identifier, {"__type": identifier})
        base.update(self.settings_cfg.get(identifier, {}))
        return base

    def publish(self, video: Path, script: VideoScript) -> dict:
        import requests
        from datetime import datetime, timezone
        if not self.api_key:
            raise RuntimeError("POSTIZ_API_KEY not set for postiz backend.")

        integrations = self._integrations()
        wanted = [
            ig for ig in integrations
            if str(ig.get("identifier", ig.get("name", ""))).lower() in self.platforms
        ]
        if not wanted:
            raise RuntimeError(
                f"No Postiz channels match {self.platforms}. Connect them in the "
                "Postiz UI first. Available: "
                f"{[ig.get('identifier') or ig.get('name') for ig in integrations]}"
            )

        media = self._upload(video)
        caption = build_caption(script)

        posts = []
        for ig in wanted:
            identifier = str(ig.get("identifier", ig.get("name", ""))).lower()
            posts.append({
                "integration": {"id": ig["id"]},
                "value": [{"content": caption, "image": [media]}],
                "settings": self._settings_for(identifier, script),
            })

        payload = {
            "type": "now" if self.auto else "draft",
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "shortLink": False,
            "tags": [],
            "posts": posts,
        }
        resp = requests.post(
            f"{self.api_base}/posts", headers=self._headers(),
            json=payload, timeout=180,
        )
        resp.raise_for_status()
        kind = "published" if self.auto else "draft"
        log.info("Postiz %s across %s: %s",
                 kind, [p.lower() for p in self.platforms], script.title)
        return {"status": kind, "postiz": resp.json()}


_BACKENDS = {"queue": QueuePoster, "postiz": PostizPoster}


class Poster:
    def __init__(self, config: Config | None = None):
        self.cfg = config or load_config()
        name = self.cfg.get("posting.backend", "queue")
        if name not in _BACKENDS:
            raise ValueError(f"Unknown posting backend: {name}")
        log.info("Posting backend: %s", name)
        self.backend = _BACKENDS[name](self.cfg)

    def publish(self, video: Path, script: VideoScript) -> dict:
        return self.backend.publish(video, script)

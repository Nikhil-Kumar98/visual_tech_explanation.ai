"""Pick reusable B-roll clips from your local Kling library by matching tags.

The library is just a folder of video files (assets/broll/). Tags come from
two places, merged:
  1. assets/broll/manifest.json  -> {"neural_net_01.mp4": ["neural network","ai"]}
  2. the filename itself (words split on -, _, spaces)

The picker scores each clip by tag overlap with the scene and avoids reusing
the same clip twice in one video when alternatives exist.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from .config import Config, load_config
from .models import VideoScript
from .utils import get_logger

log = get_logger(__name__)

VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}


class BrollLibrary:
    def __init__(self, config: Config | None = None):
        self.cfg = config or load_config()
        self.dir = self.cfg.path("paths.broll_library")
        self.index: dict[Path, set[str]] = {}
        self._load()

    def _load(self) -> None:
        if not self.dir.exists():
            log.warning("B-roll library dir missing: %s", self.dir)
            return
        manifest = self._read_manifest()
        for clip in sorted(self.dir.iterdir()):
            if clip.suffix.lower() not in VIDEO_EXTS:
                continue
            tags = set(self._filename_tags(clip.stem))
            tags |= {t.lower().strip() for t in manifest.get(clip.name, [])}
            self.index[clip] = tags
        log.info("Loaded %d B-roll clips from %s", len(self.index), self.dir)

    def _read_manifest(self) -> dict[str, list[str]]:
        mpath = self.dir / "manifest.json"
        if mpath.exists():
            try:
                return json.loads(mpath.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                log.warning("manifest.json is invalid JSON; ignoring it.")
        return {}

    @staticmethod
    def _filename_tags(stem: str) -> list[str]:
        cleaned = stem.lower().replace("-", " ").replace("_", " ")
        return [w for w in cleaned.split() if not w.isdigit()]

    # ---- scoring ----------------------------------------------------
    def _score(self, clip_tags: set[str], scene_tags: list[str]) -> int:
        score = 0
        for tag in scene_tags:
            words = set(tag.lower().split())
            if words & clip_tags:
                score += 2          # word overlap
            elif any(tag in ct or ct in tag for ct in clip_tags):
                score += 1          # substring match
        return score

    def pick(self, scene_tags: list[str], used: set[Path]) -> Path | None:
        if not self.index:
            return None
        scored = [
            (self._score(tags, scene_tags), clip)
            for clip, tags in self.index.items()
        ]
        scored.sort(key=lambda x: x[1] in used)  # prefer unused, stable
        best = max((s for s, _ in scored), default=0)

        if best == 0:
            # No tag match at all — fall back to any unused clip (then any clip).
            unused = [c for c in self.index if c not in used]
            return random.choice(unused or list(self.index))

        top = [clip for score, clip in scored if score == best]
        unused_top = [c for c in top if c not in used]
        return random.choice(unused_top or top)

    def assign(self, script: VideoScript) -> VideoScript:
        """Attach a broll_clip path to every scene in the script."""
        used: set[Path] = set()
        for scene in script.scenes:
            clip = self.pick(scene.broll_tags, used)
            if clip is None:
                raise RuntimeError(
                    f"No B-roll available in {self.dir}. Add clips first "
                    "(see data/kling_broll_prompts.md)."
                )
            used.add(clip)
            scene.broll_clip = str(clip)
            log.info("Scene %r -> %s", scene.broll_tags, clip.name)
        return script


if __name__ == "__main__":
    lib = BrollLibrary()
    for clip, tags in lib.index.items():
        print(f"{clip.name}: {sorted(tags)}")

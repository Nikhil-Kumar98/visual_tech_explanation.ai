"""Shared dataclasses passed between pipeline stages."""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict


@dataclass
class Scene:
    """One beat of the video: a line of narration + which B-roll to show."""
    narration: str
    broll_tags: list[str] = field(default_factory=list)
    # Filled in later by the b-roll picker / assembler:
    broll_clip: str | None = None
    audio_clip: str | None = None
    duration: float | None = None


@dataclass
class VideoScript:
    topic: str
    title: str
    hook: str
    scenes: list[Scene]
    caption_hashtags: list[str] = field(default_factory=list)

    @property
    def full_narration(self) -> str:
        return " ".join(s.narration for s in self.scenes)

    def to_dict(self) -> dict:
        return asdict(self)

    def save(self, path) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2, ensure_ascii=False)

    @classmethod
    def from_dict(cls, d: dict) -> "VideoScript":
        scenes = [Scene(**s) for s in d.get("scenes", [])]
        return cls(
            topic=d["topic"],
            title=d["title"],
            hook=d.get("hook", ""),
            scenes=scenes,
            caption_hashtags=d.get("caption_hashtags", []),
        )

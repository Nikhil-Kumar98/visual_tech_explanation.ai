"""End-to-end pipeline: topic -> script -> voice + B-roll -> video -> publish.

Run a single topic:
    python -m src.orchestrator --topic "how LLMs work"

Run the next N queued topics (defaults to config videos_per_day):
    python -m src.orchestrator --batch
"""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from .assembler import Assembler
from .broll_library import BrollLibrary
from .config import Config, load_config
from .models import VideoScript
from .poster import Poster
from .script_generator import ScriptGenerator
from .utils import get_logger, slugify
from .voice import Voice

log = get_logger(__name__)


class TopicQueue:
    """File-backed FIFO queue of topics with a 'done' ledger."""

    def __init__(self, cfg: Config):
        self.topics_file = cfg.root / "data" / "topics.txt"
        self.done_file = cfg.root / "data" / "topics_done.txt"

    def _read(self, path: Path) -> list[str]:
        if not path.exists():
            return []
        out = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                out.append(line)
        return out

    def pending(self) -> list[str]:
        done = set(self._read(self.done_file))
        return [t for t in self._read(self.topics_file) if t not in done]

    def mark_done(self, topic: str) -> None:
        with open(self.done_file, "a", encoding="utf-8") as fh:
            fh.write(topic + "\n")


class Pipeline:
    def __init__(self, config: Config | None = None):
        self.cfg = config or load_config()
        self.cfg.ensure_dirs()
        self.scripter = ScriptGenerator(self.cfg)
        self.library = BrollLibrary(self.cfg)
        self.voice = Voice(self.cfg)
        self.assembler = Assembler(self.cfg)
        self.poster = Poster(self.cfg)

    def produce(self, topic: str) -> Path:
        log.info("=== Producing video for: %s ===", topic)
        script = self.scripter.generate(topic)
        self.library.assign(script)

        out_dir = self.cfg.path("paths.output")
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        video_path = out_dir / f"{stamp}-{slugify(script.title)}.mp4"

        # Persist the script next to the video for traceability.
        script.save(out_dir / f"{stamp}-{slugify(script.title)}.json")

        self.assembler.assemble(script, self.voice, video_path)
        self.poster.publish(video_path, script)
        log.info("=== Done: %s ===", video_path)
        return video_path

    def run_batch(self, n: int | None = None) -> list[Path]:
        n = n or self.cfg.get("project.videos_per_day", 2)
        queue = TopicQueue(self.cfg)
        pending = queue.pending()
        if not pending:
            log.warning("No pending topics left in data/topics.txt.")
            return []
        produced = []
        for topic in pending[:n]:
            try:
                produced.append(self.produce(topic))
                queue.mark_done(topic)
            except Exception:
                log.exception("Failed to produce topic %r; leaving it in queue.", topic)
        return produced


def main() -> None:
    ap = argparse.ArgumentParser(description="visual_tech_explanation.ai pipeline")
    ap.add_argument("--topic", help="Produce a single video for this topic.")
    ap.add_argument("--batch", action="store_true", help="Produce the next N queued topics.")
    ap.add_argument("--count", type=int, default=None, help="Override how many in --batch.")
    args = ap.parse_args()

    pipe = Pipeline()
    if args.topic:
        pipe.produce(args.topic)
    elif args.batch:
        pipe.run_batch(args.count)
    else:
        ap.error("Pass --topic '<topic>' or --batch")


if __name__ == "__main__":
    main()

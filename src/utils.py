"""Small shared helpers: logging, slugs, ffprobe duration, shell runner."""
from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


log = get_logger(__name__)


def require_binary(name: str) -> str:
    """Return the path to a required CLI binary or raise a helpful error."""
    found = shutil.which(name)
    if not found:
        raise RuntimeError(
            f"'{name}' is not installed or not on PATH. Run ./setup.sh first."
        )
    return found


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a command, logging it, and raising (with stderr) on failure."""
    log.debug("exec: %s", " ".join(str(c) for c in cmd))
    try:
        return subprocess.run(cmd, check=True, **kwargs)
    except subprocess.CalledProcessError as exc:
        if exc.stderr:
            tail = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else exc.stderr
            log.error("Command failed (%s):\n%s", cmd[0], tail[-2000:])
        raise


def slugify(text: str, max_len: int = 60) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:max_len] or "untitled"


def media_duration(path: str | Path) -> float:
    """Return the duration of an audio/video file in seconds via ffprobe."""
    ffprobe = require_binary("ffprobe")
    out = subprocess.run(
        [
            ffprobe, "-v", "error", "-show_entries", "format=duration",
            "-of", "json", str(path),
        ],
        check=True, capture_output=True, text=True,
    )
    return float(json.loads(out.stdout)["format"]["duration"])

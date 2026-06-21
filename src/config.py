"""Load and access the YAML configuration.

Everything in the pipeline reads its settings from config/config.yaml so the
user never has to touch code to tune behaviour.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

# Repo root = parent of the src/ directory.
ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = ROOT / "config" / "config.yaml"


class Config:
    """Thin wrapper over the parsed YAML with dotted-key access and path helpers."""

    def __init__(self, data: dict[str, Any], config_path: Path):
        self._data = data
        self.config_path = config_path

    def get(self, dotted_key: str, default: Any = None) -> Any:
        """Fetch a nested value, e.g. config.get('voice.backend')."""
        node: Any = self._data
        for part in dotted_key.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def path(self, dotted_key: str) -> Path:
        """Resolve a configured path relative to the repo root."""
        raw = self.get(dotted_key)
        if raw is None:
            raise KeyError(f"No path configured for '{dotted_key}'")
        p = Path(raw)
        return p if p.is_absolute() else (ROOT / p)

    def ensure_dirs(self) -> None:
        """Create the working/output/library dirs if they don't exist yet."""
        for key in ("paths.broll_library", "paths.output", "paths.work"):
            self.path(key).mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        return ROOT


@lru_cache(maxsize=1)
def load_config(config_path: str | os.PathLike | None = None) -> Config:
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return Config(data, path)

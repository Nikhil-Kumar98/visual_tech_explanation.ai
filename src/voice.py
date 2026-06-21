"""Text-to-speech with swappable backends.

Backends (selected via config voice.backend):
  - "say"        : macOS built-in `say` — free, zero install, reliable. DEFAULT.
  - "xtts"       : Coqui XTTS local voice cloning — free, clones YOUR voice.
  - "elevenlabs" : ElevenLabs cloud — paid, highest quality.

Each backend implements synth(text, out_wav) -> Path. Swapping later means
changing one line in config.yaml; no other code changes.
"""
from __future__ import annotations

import os
from pathlib import Path

from .config import Config, load_config
from .utils import get_logger, require_binary, run

log = get_logger(__name__)


class VoiceBackend:
    def synth(self, text: str, out_wav: Path) -> Path:  # pragma: no cover
        raise NotImplementedError


class SayBackend(VoiceBackend):
    """macOS `say` -> AIFF, converted to wav via ffmpeg. Free, no setup."""

    def __init__(self, cfg: Config):
        self.voice = cfg.get("voice.say_voice", "Samantha")
        self.rate = cfg.get("voice.say_rate", 180)

    def synth(self, text: str, out_wav: Path) -> Path:
        say = require_binary("say")
        ffmpeg = require_binary("ffmpeg")
        aiff = out_wav.with_suffix(".aiff")
        run([say, "-v", self.voice, "-r", str(self.rate), "-o", str(aiff), text])
        run([ffmpeg, "-y", "-i", str(aiff), "-ar", "44100", "-ac", "1", str(out_wav)],
            capture_output=True)
        aiff.unlink(missing_ok=True)
        return out_wav


class XTTSBackend(VoiceBackend):
    """Coqui XTTS v2 local voice cloning. Free. `pip install TTS` required."""

    def __init__(self, cfg: Config):
        self.speaker_wav = cfg.path("voice.xtts_speaker_wav")
        self.language = cfg.get("voice.xtts_language", "en")
        self._tts = None

    def _load(self):
        if self._tts is None:
            try:
                from TTS.api import TTS  # type: ignore
            except ImportError as exc:
                raise RuntimeError(
                    "XTTS backend needs Coqui TTS. Install with `pip install TTS`."
                ) from exc
            log.info("Loading XTTS model (first run downloads weights)...")
            self._tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
        return self._tts

    def synth(self, text: str, out_wav: Path) -> Path:
        if not self.speaker_wav.exists():
            raise FileNotFoundError(
                f"XTTS needs a voice sample at {self.speaker_wav} "
                "(10-30s of clean speech of your voice)."
            )
        tts = self._load()
        tts.tts_to_file(
            text=text,
            speaker_wav=str(self.speaker_wav),
            language=self.language,
            file_path=str(out_wav),
        )
        return out_wav


class ElevenLabsBackend(VoiceBackend):
    """ElevenLabs cloud TTS. Paid. Needs ELEVENLABS_API_KEY + voice id in config."""

    def __init__(self, cfg: Config):
        self.voice_id = cfg.get("voice.elevenlabs_voice_id", "")
        self.api_key = os.environ.get("ELEVENLABS_API_KEY", "")

    def synth(self, text: str, out_wav: Path) -> Path:
        import requests
        if not self.api_key or not self.voice_id:
            raise RuntimeError("ElevenLabs needs ELEVENLABS_API_KEY and voice id.")
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}"
        resp = requests.post(
            url,
            headers={"xi-api-key": self.api_key, "accept": "audio/mpeg"},
            json={"text": text, "model_id": "eleven_multilingual_v2"},
            timeout=120,
        )
        resp.raise_for_status()
        mp3 = out_wav.with_suffix(".mp3")
        mp3.write_bytes(resp.content)
        ffmpeg = require_binary("ffmpeg")
        run([ffmpeg, "-y", "-i", str(mp3), "-ar", "44100", "-ac", "1", str(out_wav)],
            capture_output=True)
        mp3.unlink(missing_ok=True)
        return out_wav


_BACKENDS = {
    "say": SayBackend,
    "xtts": XTTSBackend,
    "elevenlabs": ElevenLabsBackend,
}


class Voice:
    def __init__(self, config: Config | None = None):
        self.cfg = config or load_config()
        name = self.cfg.get("voice.backend", "say")
        if name not in _BACKENDS:
            raise ValueError(f"Unknown voice backend: {name}")
        log.info("Voice backend: %s", name)
        self.backend = _BACKENDS[name](self.cfg)

    def synth(self, text: str, out_wav: Path) -> Path:
        out_wav.parent.mkdir(parents=True, exist_ok=True)
        return self.backend.synth(text, out_wav)


if __name__ == "__main__":
    import sys
    text = sys.argv[1] if len(sys.argv) > 1 else "Hello, this is a test of the voice module."
    out = Path("assets/work/voice_test.wav")
    Voice().synth(text, out)
    print(f"Wrote {out}")

"""Turn a topic string into a structured VideoScript using a free local LLM.

Default backend is Ollama (runs offline on your Mac, no API key). A Gemini
free-tier backend is included as a swappable alternative.

The LLM is asked to return strict JSON so we can parse scenes + B-roll tags.
"""
from __future__ import annotations

import json
import re

import requests

from .config import Config, load_config
from .models import Scene, VideoScript
from .utils import get_logger

log = get_logger(__name__)

SYSTEM_PROMPT = """You are a scriptwriter for short-form vertical tech explainer videos
(YouTube Shorts / Reels / TikTok). You write punchy, accurate, beginner-friendly scripts.

Return ONLY valid minified JSON (no markdown, no commentary) with this exact shape:
{
  "title": "string, <=70 chars, catchy",
  "hook": "string, the first spoken line, must grab attention in <3s",
  "scenes": [
    {
      "narration": "one or two spoken sentences for this scene",
      "broll_tags": ["2-4 lowercase keywords describing the ideal background visual"]
    }
  ],
  "caption_hashtags": ["#tech", "#..."]
}
broll_tags must be generic, reusable visual concepts (e.g. "neural network",
"data stream", "server room", "code", "robot", "brain", "cloud", "chip").
"""


class ScriptGenerator:
    def __init__(self, config: Config | None = None):
        self.cfg = config or load_config()

    # ---- public API -------------------------------------------------
    def generate(self, topic: str) -> VideoScript:
        backend = self.cfg.get("script.backend", "ollama")
        log.info("Generating script for topic %r via %s", topic, backend)
        raw = self._call_backend(backend, self._build_user_prompt(topic))
        data = self._parse_json(raw)
        return self._to_script(topic, data)

    # ---- prompt -----------------------------------------------------
    def _build_user_prompt(self, topic: str) -> str:
        n = self.cfg.get("script.scenes", 4)
        secs = self.cfg.get("script.target_seconds", 45)
        tone = self.cfg.get("script.tone", "energetic, clear, beginner-friendly")
        return (
            f"Topic: {topic}\n"
            f"Tone: {tone}\n"
            f"Total spoken length: about {secs} seconds.\n"
            f"Break it into exactly {n} scenes.\n"
            f"Make the hook surprising or curiosity-driven. End with a one-line takeaway."
        )

    # ---- backends ---------------------------------------------------
    def _call_backend(self, backend: str, user_prompt: str) -> str:
        if backend == "ollama":
            return self._call_ollama(user_prompt)
        if backend == "gemini":
            return self._call_gemini(user_prompt)
        raise ValueError(f"Unknown script backend: {backend}")

    def _call_ollama(self, user_prompt: str) -> str:
        host = self.cfg.get("script.ollama_host", "http://localhost:11434")
        model = self.cfg.get("script.model", "llama3.1:8b")
        try:
            resp = requests.post(
                f"{host}/api/chat",
                json={
                    "model": model,
                    "format": "json",
                    "stream": False,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                },
                timeout=300,
            )
            resp.raise_for_status()
        except requests.exceptions.ConnectionError as exc:
            raise RuntimeError(
                "Could not reach Ollama. Start it with `ollama serve` and "
                f"ensure the model is pulled: `ollama pull {model}`."
            ) from exc
        return resp.json()["message"]["content"]

    def _call_gemini(self, user_prompt: str) -> str:
        import os
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY not set for gemini backend.")
        model = self.cfg.get("script.model", "gemini-1.5-flash")
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={key}"
        )
        resp = requests.post(
            url,
            json={
                "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                "contents": [{"parts": [{"text": user_prompt}]}],
                "generationConfig": {"response_mime_type": "application/json"},
            },
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"]

    # ---- parsing ----------------------------------------------------
    @staticmethod
    def _parse_json(raw: str) -> dict:
        raw = raw.strip()
        # Strip markdown fences if the model added them anyway.
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?|```$", "", raw, flags=re.MULTILINE).strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if not match:
                raise ValueError(f"LLM did not return JSON:\n{raw[:500]}")
            return json.loads(match.group(0))

    @staticmethod
    def _to_script(topic: str, data: dict) -> VideoScript:
        scenes = [
            Scene(
                narration=s.get("narration", "").strip(),
                broll_tags=[t.lower().strip() for t in s.get("broll_tags", [])],
            )
            for s in data.get("scenes", [])
            if s.get("narration", "").strip()
        ]
        if not scenes:
            raise ValueError("LLM returned no usable scenes.")
        return VideoScript(
            topic=topic,
            title=data.get("title", topic).strip(),
            hook=data.get("hook", "").strip(),
            scenes=scenes,
            caption_hashtags=data.get("caption_hashtags", []),
        )


if __name__ == "__main__":
    import sys
    topic = sys.argv[1] if len(sys.argv) > 1 else "how LLMs work"
    script = ScriptGenerator().generate(topic)
    print(json.dumps(script.to_dict(), indent=2))

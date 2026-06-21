"""Assemble the final vertical video with ffmpeg.

Per scene: synth voice -> measure duration -> loop+crop B-roll to 9:16 for that
duration -> embed the scene audio -> optionally burn captions. Then concat all
scenes (plus optional intro/outro) and mix optional background music.
"""
from __future__ import annotations

from pathlib import Path

from .captions import render_scene_captions, write_scene_srt
from .config import Config, load_config
from .models import VideoScript
from .utils import get_logger, media_duration, require_binary, run

log = get_logger(__name__)


class Assembler:
    def __init__(self, config: Config | None = None):
        self.cfg = config or load_config()
        self.ffmpeg = require_binary("ffmpeg")
        self.w = self.cfg.get("video.width", 1080)
        self.h = self.cfg.get("video.height", 1920)
        self.fps = self.cfg.get("video.fps", 30)
        self.work = self.cfg.path("paths.work")
        self.work.mkdir(parents=True, exist_ok=True)

    # ---- per-scene segment -----------------------------------------
    def build_scene(self, idx: int, narration: str, broll: Path,
                    audio: Path) -> Path:
        dur = media_duration(audio)
        seg = self.work / f"segment_{idx:02d}.mp4"
        base_vf = (
            f"scale={self.w}:{self.h}:force_original_aspect_ratio=increase,"
            f"crop={self.w}:{self.h},fps={self.fps},setsar=1"
        )

        # Inputs: 0 = looping B-roll, 1 = scene audio, 2.. = caption PNGs.
        inputs = [
            "-stream_loop", "-1", "-i", str(broll),
            "-i", str(audio),
        ]

        caption_clips = []
        if self.cfg.get("video.captions", True):
            # Also emit an SRT alongside (useful for platform caption upload).
            write_scene_srt(narration, dur, self.work / f"scene_{idx:02d}.srt")
            caption_clips = render_scene_captions(
                narration, dur, self.work, idx, self.w, self.h,
                font_size=self.cfg.get("video.caption_font_size", 64),
                box=self.cfg.get("video.caption_box", True),
                color=self.cfg.get("video.caption_color", "white"),
            )

        for clip in caption_clips:
            inputs += ["-i", str(clip.png)]

        # Build the filter graph: base video then chained timed overlays.
        steps = [f"[0:v]{base_vf}[v0]"]
        prev = "v0"
        for n, clip in enumerate(caption_clips):
            in_idx = 2 + n
            out = f"v{n + 1}"
            steps.append(
                f"[{prev}][{in_idx}:v]"
                f"overlay=0:0:enable='between(t\\,{clip.start:.3f}\\,{clip.end:.3f})'"
                f"[{out}]"
            )
            prev = out

        cmd = [
            self.ffmpeg, "-y", *inputs,
            "-t", f"{dur:.3f}",
            "-filter_complex", ";".join(steps),
            "-map", f"[{prev}]", "-map", "1:a",
            "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-ar", "44100", "-ac", "2",
            "-shortest", str(seg),
        ]
        run(cmd, capture_output=True)
        return seg

    # ---- normalize intro/outro to match segment params -------------
    def _normalize(self, src: Path, idx: str) -> Path:
        out = self.work / f"branding_{idx}.mp4"
        vf = (
            f"scale={self.w}:{self.h}:force_original_aspect_ratio=increase,"
            f"crop={self.w}:{self.h},fps={self.fps},setsar=1"
        )
        cmd = [self.ffmpeg, "-y", "-i", str(src)]
        if self._has_audio(src):
            cmd += [
                "-filter_complex", f"[0:v]{vf}[v]",
                "-map", "[v]", "-map", "0:a",
            ]
        else:
            # Synthesize silent stereo audio so concat streams stay uniform.
            cmd += [
                "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                "-filter_complex", f"[0:v]{vf}[v]",
                "-map", "[v]", "-map", "1:a", "-shortest",
            ]
        cmd += [
            "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-ar", "44100", "-ac", "2", str(out),
        ]
        run(cmd, capture_output=True)
        return out

    def _has_audio(self, src: Path) -> bool:
        ffprobe = require_binary("ffprobe")
        import subprocess
        out = subprocess.run(
            [ffprobe, "-v", "error", "-select_streams", "a",
             "-show_entries", "stream=index", "-of", "csv=p=0", str(src)],
            capture_output=True, text=True,
        )
        return bool(out.stdout.strip())

    # ---- concat + music --------------------------------------------
    def _concat(self, segments: list[Path], out: Path) -> Path:
        listfile = self.work / "concat.txt"
        listfile.write_text(
            "".join(f"file '{s.resolve()}'\n" for s in segments), encoding="utf-8"
        )
        run([
            self.ffmpeg, "-y", "-f", "concat", "-safe", "0",
            "-i", str(listfile), "-c", "copy", str(out),
        ], capture_output=True)
        return out

    def _add_music(self, video: Path, music: Path, out: Path) -> Path:
        vol = self.cfg.get("video.music_volume", 0.08)
        run([
            self.ffmpeg, "-y", "-i", str(video),
            "-stream_loop", "-1", "-i", str(music),
            "-filter_complex",
            f"[1:a]volume={vol}[bg];[0:a][bg]amix=inputs=2:duration=first:dropout_transition=2[a]",
            "-map", "0:v", "-map", "[a]",
            "-c:v", "copy", "-c:a", "aac", "-shortest", str(out),
        ], capture_output=True)
        return out

    # ---- public API -------------------------------------------------
    def assemble(self, script: VideoScript, voice, out_path: Path) -> Path:
        """voice: an object with .synth(text, out_wav). Returns final video path."""
        segments: list[Path] = []

        intro = self.cfg.path("paths.intro")
        if intro.exists():
            segments.append(self._normalize(intro, "intro"))

        for i, scene in enumerate(script.scenes):
            if not scene.broll_clip:
                raise RuntimeError("Scene has no B-roll assigned; run BrollLibrary.assign first.")
            audio = self.work / f"scene_{i:02d}.wav"
            voice.synth(scene.narration, audio)
            scene.audio_clip = str(audio)
            seg = self.build_scene(i, scene.narration, Path(scene.broll_clip), audio)
            scene.duration = media_duration(seg)
            segments.append(seg)

        outro = self.cfg.path("paths.outro")
        if outro.exists():
            segments.append(self._normalize(outro, "outro"))

        out_path.parent.mkdir(parents=True, exist_ok=True)
        concatenated = self.work / "concat_out.mp4"
        self._concat(segments, concatenated)

        music = self.cfg.path("paths.music")
        if music.exists():
            self._add_music(concatenated, music, out_path)
        else:
            run([self.ffmpeg, "-y", "-i", str(concatenated), "-c", "copy", str(out_path)],
                capture_output=True)

        log.info("Final video: %s", out_path)
        return out_path

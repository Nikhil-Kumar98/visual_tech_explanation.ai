"""Caption generation.

Two outputs are supported:
  - write_scene_srt(): a plain SRT file (handy for uploading captions to YouTube).
  - render_scene_captions(): full-frame transparent PNGs with the caption baked
    in, plus timing. The assembler overlays these, so we never depend on
    ffmpeg being built with libass/drawtext (Homebrew's ffmpeg isn't).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# macOS font candidates, first that exists wins.
_FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "/System/Library/Fonts/Helvetica.ttc",
    "/Library/Fonts/Arial.ttf",
]


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default(size)


def _fmt_ts(seconds: float) -> str:
    seconds = max(seconds, 0)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    if ms == 1000:
        s, ms = s + 1, 0
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _chunk_words(text: str, words_per_line: int = 5) -> list[str]:
    words = text.split()
    return [
        " ".join(words[i : i + words_per_line])
        for i in range(0, len(words), words_per_line)
    ] or [text]


def write_scene_srt(narration: str, duration: float, out_srt: Path,
                    words_per_line: int = 5) -> Path:
    lines = _chunk_words(narration, words_per_line)
    per = duration / len(lines)
    out_srt.parent.mkdir(parents=True, exist_ok=True)
    with open(out_srt, "w", encoding="utf-8") as fh:
        for i, line in enumerate(lines):
            fh.write(
                f"{i + 1}\n{_fmt_ts(i * per)} --> {_fmt_ts((i + 1) * per)}\n{line}\n\n"
            )
    return out_srt


@dataclass
class CaptionClip:
    png: Path
    start: float
    end: float


def _wrap_to_width(draw, text, font, max_width) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if draw.textlength(trial, font=font) <= max_width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def render_scene_captions(
    narration: str,
    duration: float,
    work_dir: Path,
    idx: int,
    width: int,
    height: int,
    font_size: int = 64,
    box: bool = True,
    margin_v: int = 240,
    color: str = "white",
    words_per_line: int = 5,
) -> list[CaptionClip]:
    """Render one transparent full-frame PNG per caption chunk with timing."""
    work_dir.mkdir(parents=True, exist_ok=True)
    font = _load_font(font_size)
    chunks = _chunk_words(narration, words_per_line)
    per = duration / len(chunks)
    max_text_width = int(width * 0.86)
    line_gap = int(font_size * 0.30)

    clips: list[CaptionClip] = []
    scratch = Image.new("RGBA", (width, height))
    measure = ImageDraw.Draw(scratch)

    for i, chunk in enumerate(chunks):
        lines = _wrap_to_width(measure, chunk, font, max_text_width)
        ascent, descent = font.getmetrics()
        line_h = ascent + descent
        block_h = line_h * len(lines) + line_gap * (len(lines) - 1)

        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        y0 = height - margin_v - block_h

        if box:
            widths = [draw.textlength(ln, font=font) for ln in lines]
            box_w = int(max(widths)) + 56
            box_h = block_h + 40
            bx0 = (width - box_w) // 2
            by0 = y0 - 20
            draw.rounded_rectangle(
                [bx0, by0, bx0 + box_w, by0 + box_h],
                radius=24, fill=(0, 0, 0, 150),
            )

        y = y0
        for ln in lines:
            tw = draw.textlength(ln, font=font)
            x = (width - tw) / 2
            draw.text((x, y), ln, font=font, fill=color,
                      stroke_width=3, stroke_fill=(0, 0, 0, 255))
            y += line_h + line_gap

        png = work_dir / f"cap_{idx:02d}_{i:02d}.png"
        img.save(png)
        clips.append(CaptionClip(png=png, start=i * per, end=(i + 1) * per))

    return clips

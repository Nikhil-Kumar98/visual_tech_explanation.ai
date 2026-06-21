# Kling B-roll Prompt Library

Generate these **once** with Kling free credits, then drop the clips into
`assets/broll/`. The automation reuses them forever, so you never need fresh
video per upload. Aim for ~20-30 clips. Each prompt is tuned for a clean,
loopable, vertical (9:16) tech background.

> Tip: name files with the tag so the picker matches them automatically, e.g.
> `neural-network-01.mp4`, `data-stream-02.mp4`. Or maintain
> `assets/broll/manifest.json` (see bottom).

## Shared style suffix (append to every prompt)
> vertical 9:16, slow seamless loop, dark background, subtle motion, cinematic,
> high detail, no text, no watermark, 5 seconds

## Core clips
| Filename | Prompt |
|---|---|
| `neural-network-01.mp4` | Glowing blue neural network, nodes pulsing and connecting, data flowing along edges |
| `neural-network-02.mp4` | 3D animated artificial neural network rotating slowly, glowing synapses firing |
| `data-stream-01.mp4` | Streams of binary code and light particles flowing through a dark tunnel |
| `data-stream-02.mp4` | Abstract flowing data packets, neon lines moving across a dark grid |
| `server-room-01.mp4` | Futuristic server room, rows of blinking server racks, blue ambient light, slow dolly |
| `cloud-01.mp4` | Glowing digital cloud icon made of particles, data uploading and downloading |
| `code-01.mp4` | Close-up of colorful source code scrolling on a dark screen, soft bokeh |
| `chip-01.mp4` | Macro shot of a glowing computer chip / CPU, electric pulses across circuits |
| `gpu-01.mp4` | High-end GPU with glowing fans, electricity arcing, dark moody lighting |
| `brain-01.mp4` | Digital human brain made of light and circuits, neurons firing, slow rotation |
| `robot-01.mp4` | Friendly humanoid AI robot head, glowing eyes, subtle idle motion, dark studio |
| `chatbot-ui-01.mp4` | Abstract chat interface, message bubbles appearing, soft glow, minimal |
| `network-globe-01.mp4` | Earth from space with glowing connection lines linking cities, internet network |
| `lock-encryption-01.mp4` | Glowing padlock made of digital particles, encryption keys swirling around it |
| `database-01.mp4` | Stacked glowing database cylinders, data flowing between them, dark background |
| `api-01.mp4` | Abstract puzzle pieces / connectors snapping together with light, data exchange |
| `search-01.mp4` | Magnifying glass over a sea of glowing documents, results highlighting |
| `wifi-signal-01.mp4` | Glowing wifi waves radiating from a router, signal particles in the air |
| `gps-satellite-01.mp4` | Satellite orbiting Earth beaming signals to a glowing map pin below |
| `container-docker-01.mp4` | Stacked glowing shipping containers as a metaphor for software containers, isometric |
| `particles-abstract-01.mp4` | Soft floating tech particles and light streaks, generic calm background |
| `circuit-board-01.mp4` | Top-down glowing circuit board, electric current tracing the paths |

## manifest.json (optional, for richer tagging)
If you don't want to encode tags in filenames, create `assets/broll/manifest.json`:

```json
{
  "clip_001.mp4": ["neural network", "ai", "brain"],
  "clip_002.mp4": ["data stream", "code", "binary"],
  "clip_003.mp4": ["server room", "cloud", "data center"]
}
```

The picker merges these tags with words from the filename.

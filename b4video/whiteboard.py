"""Whiteboard scene renderer — progressive SVG diagram drawing synced to narration.

Diagrams are defined as YAML files with timed drawing steps. Each step
references narration words and specifies SVG elements to reveal. The
renderer produces a video of the diagram drawing itself on a dark background.

Diagram format (YAML):
    canvas:
      width: 1920
      height: 1080
      background: "#2f495e"

    elements:
      - id: box-forge
        type: rect
        x: 200
        y: 300
        width: 250
        height: 120
        fill: "#4a6d8c"
        stroke: "#c0d5e7"
        stroke_width: 2
        label: "Forge"
        label_color: "#c0d5e7"

      - id: box-atlas
        type: rect
        x: 600
        y: 300
        width: 250
        height: 120
        fill: "#4a6d8c"
        stroke: "#c9a84c"
        stroke_width: 2
        label: "Atlas"
        label_color: "#c9a84c"

      - id: arrow-forge-atlas
        type: arrow
        x1: 450
        y1: 360
        x2: 600
        y2: 360
        stroke: "#c0d5e7"
        stroke_width: 2
        label: "PR review"
        label_color: "#7ca7cb"

    steps:
      - at_word: "Forge"           # reveal when narrator says this word
        reveal: ["box-forge"]
        effect: fade               # fade | draw | instant

      - at_word: "Atlas"
        reveal: ["box-atlas"]
        effect: fade

      - at_word: "review"
        reveal: ["arrow-forge-atlas"]
        effect: draw
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

import yaml

# Brand colors
BG_COLOR = "#2f495e"
FADE_DURATION = 0.5  # seconds for fade-in effect
DRAW_DURATION = 0.8  # seconds for draw effect


def render_whiteboard(
    diagram_path: Path,
    timing_path: Path,
    scene_key: str,
    output_path: Path,
    *,
    width: int = 1920,
    height: int = 1080,
    fps: int = 30,
) -> None:
    """Render a whiteboard diagram video synced to narration timing.

    Args:
        diagram_path: YAML file defining the diagram elements and steps
        timing_path: timing.json from ElevenLabs with word timestamps
        scene_key: key in timing.json (e.g., "scene-01")
        output_path: where to write the output MP4
        width/height/fps: video dimensions
    """
    diagram = yaml.safe_load(diagram_path.read_text())
    timing = json.loads(timing_path.read_text())

    scene_timing = timing.get(scene_key, {})
    characters = scene_timing.get("characters", [])
    start_times = scene_timing.get("start_times", [])

    # Build word list with timestamps from character-level data
    words = _chars_to_words(characters, start_times)

    # Resolve step timing — map "at_word" to actual timestamps
    elements = {e["id"]: e for e in diagram.get("elements", [])}
    steps = _resolve_steps(diagram.get("steps", []), words)

    canvas = diagram.get("canvas", {})
    bg = canvas.get("background", BG_COLOR)
    total_duration = max(start_times) + 2.0 if start_times else 10.0

    # Render frames
    with tempfile.TemporaryDirectory(prefix="b4video-wb-") as tmpdir:
        frame_dir = Path(tmpdir) / "frames"
        frame_dir.mkdir()

        total_frames = int(total_duration * fps)
        for frame_idx in range(total_frames):
            t = frame_idx / fps
            svg = _build_svg(elements, steps, t, width, height, bg)
            _svg_to_png(svg, frame_dir / f"frame-{frame_idx:05d}.png", width, height)

        # Assemble frames into video
        _frames_to_video(frame_dir, output_path, fps, width, height)


def _chars_to_words(characters: list[str], start_times: list[float]) -> list[tuple[str, float]]:
    """Convert character-level timestamps to word-level (word, start_time) pairs."""
    words = []
    current_word = ""
    word_start = 0.0

    for i, ch in enumerate(characters):
        if ch == " ":
            if current_word.strip():
                words.append((current_word.strip(), word_start))
            current_word = ""
            if i + 1 < len(start_times):
                word_start = start_times[i + 1]
        else:
            if not current_word:
                word_start = start_times[i] if i < len(start_times) else 0.0
            current_word += ch

    if current_word.strip():
        words.append((current_word.strip(), word_start))

    return words


def _resolve_steps(steps: list[dict], words: list[tuple[str, float]]) -> list[dict]:
    """Resolve at_word references to actual timestamps."""
    resolved = []
    for step in steps:
        target_word = step.get("at_word", "").lower().rstrip(".,!?;:")
        # Find the first word matching the target
        timestamp = 0.0
        for word, t in words:
            if word.lower().rstrip(".,!?;:") == target_word:
                timestamp = t
                break

        resolved.append({
            "time": timestamp,
            "reveal": step.get("reveal", []),
            "effect": step.get("effect", "fade"),
        })

    return resolved


def _build_svg(
    elements: dict[str, dict],
    steps: list[dict],
    t: float,
    width: int,
    height: int,
    bg: str,
) -> str:
    """Build an SVG string for the given timestamp."""
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        f'<rect width="{width}" height="{height}" fill="{bg}"/>',
    ]

    # Determine which elements are visible and their opacity
    visible: dict[str, float] = {}  # element_id -> opacity
    for step in steps:
        step_time = step["time"]
        effect = step["effect"]

        for elem_id in step["reveal"]:
            if t < step_time:
                continue  # not yet revealed

            if effect == "instant":
                visible[elem_id] = 1.0
            elif effect == "fade":
                progress = min((t - step_time) / FADE_DURATION, 1.0)
                visible[elem_id] = max(visible.get(elem_id, 0), progress)
            elif effect == "draw":
                progress = min((t - step_time) / DRAW_DURATION, 1.0)
                visible[elem_id] = max(visible.get(elem_id, 0), progress)

    # Render visible elements
    for elem_id, opacity in visible.items():
        elem = elements.get(elem_id)
        if not elem:
            continue
        parts.append(_render_element(elem, opacity))

    parts.append("</svg>")
    return "\n".join(parts)


def _render_element(elem: dict, opacity: float) -> str:
    """Render a single element as SVG with given opacity."""
    etype = elem.get("type", "rect")
    op = f'opacity="{opacity:.2f}"'

    if etype == "rect":
        x, y = elem.get("x", 0), elem.get("y", 0)
        w, h = elem.get("width", 100), elem.get("height", 60)
        fill = elem.get("fill", "#4a6d8c")
        stroke = elem.get("stroke", "#c0d5e7")
        sw = elem.get("stroke_width", 2)
        rx = elem.get("rx", 8)

        svg = (
            f'<g {op}>'
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" '
            f'rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'
        )

        label = elem.get("label")
        if label:
            lc = elem.get("label_color", "#c0d5e7")
            cx, cy = x + w // 2, y + h // 2
            svg += (
                f'<text x="{cx}" y="{cy}" text-anchor="middle" '
                f'dominant-baseline="central" fill="{lc}" '
                f'font-family="sans-serif" font-size="24" font-weight="bold">'
                f'{label}</text>'
            )

        svg += "</g>"
        return svg

    elif etype == "circle":
        cx = elem.get("cx", 100)
        cy = elem.get("cy", 100)
        r = elem.get("r", 50)
        fill = elem.get("fill", "#4a6d8c")
        stroke = elem.get("stroke", "#c0d5e7")
        sw = elem.get("stroke_width", 2)

        svg = (
            f'<g {op}>'
            f'<circle cx="{cx}" cy="{cy}" r="{r}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'
        )
        label = elem.get("label")
        if label:
            lc = elem.get("label_color", "#c0d5e7")
            svg += (
                f'<text x="{cx}" y="{cy}" text-anchor="middle" '
                f'dominant-baseline="central" fill="{lc}" '
                f'font-family="sans-serif" font-size="20">'
                f'{label}</text>'
            )
        svg += "</g>"
        return svg

    elif etype == "arrow":
        x1, y1 = elem.get("x1", 0), elem.get("y1", 0)
        x2, y2 = elem.get("x2", 100), elem.get("y2", 0)
        stroke = elem.get("stroke", "#c0d5e7")
        sw = elem.get("stroke_width", 2)

        # For draw effect, we animate the line length via dashoffset
        svg = (
            f'<g {op}>'
            f'<defs><marker id="ah-{id(elem)}" markerWidth="10" markerHeight="7" '
            f'refX="9" refY="3.5" orient="auto">'
            f'<polygon points="0 0, 10 3.5, 0 7" fill="{stroke}"/>'
            f'</marker></defs>'
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            f'stroke="{stroke}" stroke-width="{sw}" '
            f'marker-end="url(#ah-{id(elem)})"/>'
        )

        label = elem.get("label")
        if label:
            lc = elem.get("label_color", "#7ca7cb")
            mx, my = (x1 + x2) // 2, (y1 + y2) // 2 - 15
            svg += (
                f'<text x="{mx}" y="{my}" text-anchor="middle" '
                f'fill="{lc}" font-family="sans-serif" font-size="18">'
                f'{label}</text>'
            )

        svg += "</g>"
        return svg

    elif etype == "text":
        x, y = elem.get("x", 0), elem.get("y", 0)
        text = elem.get("text", "")
        color = elem.get("color", "#c0d5e7")
        size = elem.get("font_size", 28)
        anchor = elem.get("anchor", "middle")

        return (
            f'<text x="{x}" y="{y}" text-anchor="{anchor}" '
            f'fill="{color}" font-family="sans-serif" font-size="{size}" '
            f'{op}>{text}</text>'
        )

    return ""


def _svg_to_png(svg_content: str, output: Path, width: int, height: int) -> None:
    """Convert SVG string to PNG."""
    import cairosvg
    cairosvg.svg2png(
        bytestring=svg_content.encode(),
        write_to=str(output),
        output_width=width,
        output_height=height,
    )


def _frames_to_video(frame_dir: Path, output: Path, fps: int, width: int, height: int) -> None:
    """Assemble PNG frames into an MP4 video."""
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(fps),
        "-i", str(frame_dir / "frame-%05d.png"),
        "-c:v", "libopenh264",
        "-pix_fmt", "yuv420p",
        str(output),
    ]

    # Auto-detect better encoder
    probe = subprocess.run(["ffmpeg", "-encoders"], capture_output=True, text=True)
    if "libx264" in probe.stdout:
        cmd = [
            "ffmpeg", "-y",
            "-framerate", str(fps),
            "-i", str(frame_dir / "frame-%05d.png"),
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p",
            str(output),
        ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg frame assembly failed:\n{result.stderr}")

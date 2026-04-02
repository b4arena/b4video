"""Stage 4: Compose individual scenes — PiP overlay, transitions."""

from __future__ import annotations

import subprocess
from pathlib import Path

from b4video.manifest import Manifest
from b4video.parser import Scene, SceneMeta

# PiP settings
PIP_SIZE = 240
PIP_MARGIN = 20


def compose_scenes(
    meta: SceneMeta,
    scenes: list[Scene],
    build_dir: Path,
    manifest: Manifest,
    *,
    force: bool = False,
) -> None:
    """Compose each scene into a final per-scene video."""
    composed_dir = build_dir / "composed"
    composed_dir.mkdir(parents=True, exist_ok=True)
    video_dir = build_dir / "video"
    audio_dir = build_dir / "audio"

    width, height = meta.resolution.split("x")

    for scene in scenes:
        key = f"composed-scene-{scene.index:02d}"
        output = composed_dir / f"scene-{scene.index:02d}.mp4"

        if not force and manifest.is_complete(key) and output.exists():
            continue

        art = manifest.get_or_create(key, str(output))

        try:
            if scene.scene_type == "presenter":
                _compose_presenter(scene, video_dir, audio_dir, output, width, height, meta.fps)
            elif scene.scene_type == "demo":
                _compose_overlay(scene, video_dir, audio_dir, output, width, height, meta.fps,
                                 bg_suffix="screen", bg_ext="webm")
            elif scene.scene_type == "whiteboard":
                _compose_overlay(scene, video_dir, audio_dir, output, width, height, meta.fps,
                                 bg_suffix="whiteboard", bg_ext="mp4")

            art.mark_complete()
        except Exception as e:
            art.mark_failed(str(e))

        manifest.save(build_dir)


def _compose_presenter(
    scene: Scene,
    video_dir: Path,
    audio_dir: Path,
    output: Path,
    width: str,
    height: str,
    fps: int,
) -> None:
    """Scale presenter avatar to target resolution with audio."""
    avatar_path = video_dir / f"scene-{scene.index:02d}-avatar.mp4"
    audio_path = audio_dir / f"scene-{scene.index:02d}.mp3"

    if not avatar_path.exists():
        raise FileNotFoundError(f"Avatar video not found: {avatar_path}")

    cmd = [
        "ffmpeg", "-y",
        "-i", str(avatar_path),
        "-i", str(audio_path),
        "-filter_complex",
        f"[0:v]fps={fps},scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2[v]",
        "-map", "[v]",
        "-map", "1:a",
        "-c:v", "libopenh264",
        "-c:a", "aac", "-b:a", "192k",
        "-r", str(fps),
        str(output),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed (presenter):\n{result.stderr}")


def _pip_filter(input_index: int, pip_x: int, pip_y: int) -> list[str]:
    """Build FFmpeg filter chain for PiP avatar overlay.

    Scales the avatar to PiP size with a thin border.
    Uses a clean rectangular crop — no circle masking to avoid
    compatibility issues with geq/chromakey across FFmpeg versions.
    """
    border = 3
    inner = PIP_SIZE - (border * 2)
    return [
        # Match framerate, scale to fill square (by height), crop center, add border
        f"[{input_index}:v]fps=30,scale=-1:{inner},crop={inner}:{inner},"
        f"pad={PIP_SIZE}:{PIP_SIZE}:{border}:{border}:color=0x4a6d8c"
        f"[pip]",
    ]


def _compose_overlay(
    scene: Scene,
    video_dir: Path,
    audio_dir: Path,
    output: Path,
    width: str,
    height: str,
    fps: int,
    *,
    bg_suffix: str,
    bg_ext: str,
) -> None:
    """Overlay PiP avatar on a background video (screen recording or whiteboard)."""
    bg_path = video_dir / f"scene-{scene.index:02d}-{bg_suffix}.{bg_ext}"
    avatar_path = video_dir / f"scene-{scene.index:02d}-avatar.mp4"
    audio_path = audio_dir / f"scene-{scene.index:02d}.mp3"

    if not bg_path.exists():
        raise FileNotFoundError(f"Background video not found: {bg_path}")

    w, h = int(width), int(height)
    pip_x = w - PIP_SIZE - PIP_MARGIN
    pip_y = h - PIP_SIZE - PIP_MARGIN

    filter_parts = [
        f"[0:v]fps={fps},scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2[bg]",
    ]

    inputs = ["-i", str(bg_path)]
    map_video = "[bg]"

    if avatar_path.exists():
        inputs.extend(["-i", str(avatar_path)])
        filter_parts.extend(_pip_filter(1, pip_x, pip_y))
        filter_parts.append(f"[bg][pip]overlay={pip_x}:{pip_y}[out]")
        map_video = "[out]"

    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-i", str(audio_path),
        "-filter_complex", ";".join(filter_parts),
        "-map", map_video,
        "-map", f"{len(inputs)//2}:a",
        "-c:v", "libopenh264",
        "-c:a", "aac", "-b:a", "192k",
        "-r", str(fps),
        str(output),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed ({bg_suffix}):\n{result.stderr}")

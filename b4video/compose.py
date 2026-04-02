"""Stage 4: Compose individual scenes — PiP overlay, transitions."""

from __future__ import annotations

import subprocess
from pathlib import Path

from b4video.manifest import Manifest
from b4video.parser import Scene, SceneMeta

# PiP settings
PIP_SIZE = 240
PIP_MARGIN = 20
PIP_POSITION = "bottom-right"


def compose_scenes(
    meta: SceneMeta,
    scenes: list[Scene],
    build_dir: Path,
    manifest: Manifest,
    *,
    force: bool = False,
) -> None:
    """Compose each scene into a final per-scene video.

    Presenter: scale avatar to target resolution.
    Demo: overlay PiP avatar on screen recording.
    """
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
                _compose_demo(scene, video_dir, audio_dir, output, width, height, meta.fps)
            elif scene.scene_type == "whiteboard":
                _compose_whiteboard(scene, video_dir, audio_dir, output, width, height, meta.fps)

            art.mark_complete()
        except Exception as e:
            art.mark_failed(str(e))
            # Continue with other scenes — fail per-scene, not per-video

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
        f"[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
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
        raise RuntimeError(f"FFmpeg failed:\n{result.stderr}")


def _compose_demo(
    scene: Scene,
    video_dir: Path,
    audio_dir: Path,
    output: Path,
    width: str,
    height: str,
    fps: int,
) -> None:
    """Overlay PiP avatar on screen recording with narration audio."""
    screen_path = video_dir / f"scene-{scene.index:02d}-screen.webm"
    avatar_path = video_dir / f"scene-{scene.index:02d}-avatar.mp4"
    audio_path = audio_dir / f"scene-{scene.index:02d}.mp3"

    if not screen_path.exists():
        raise FileNotFoundError(f"Screen recording not found: {screen_path}")

    # Build filter: scale screen, overlay PiP circle-cropped avatar
    w, h = int(width), int(height)
    pip_x = w - PIP_SIZE - PIP_MARGIN
    pip_y = h - PIP_SIZE - PIP_MARGIN

    filter_parts = [
        f"[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2[bg]",
    ]

    inputs = ["-i", str(screen_path)]
    map_video = "[bg]"

    # Add PiP if avatar exists
    if avatar_path.exists():
        inputs.extend(["-i", str(avatar_path)])
        filter_parts.append(
            f"[1:v]scale={PIP_SIZE}:{PIP_SIZE},"
            f"format=yuva420p,"
            f"geq=lum='lum(X,Y)':a='if(gt(abs(X-{PIP_SIZE//2})*abs(X-{PIP_SIZE//2})"
            f"+abs(Y-{PIP_SIZE//2})*abs(Y-{PIP_SIZE//2}),{(PIP_SIZE//2)**2}),0,255)'[pip]"
        )
        filter_parts.append(f"[bg][pip]overlay={pip_x}:{pip_y}[out]")
        map_video = "[out]"

    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-i", str(audio_path),
        "-filter_complex", ";".join(filter_parts),
        "-map", map_video,
        "-map", f"{len(inputs)//2}:a",  # audio input index
        "-c:v", "libopenh264",
        "-c:a", "aac", "-b:a", "192k",
        "-r", str(fps),
        str(output),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed (demo):\n{result.stderr}")


def _compose_whiteboard(
    scene: Scene,
    video_dir: Path,
    audio_dir: Path,
    output: Path,
    width: str,
    height: str,
    fps: int,
) -> None:
    """Overlay PiP avatar on whiteboard diagram with narration audio."""
    wb_path = video_dir / f"scene-{scene.index:02d}-whiteboard.mp4"
    avatar_path = video_dir / f"scene-{scene.index:02d}-avatar.mp4"
    audio_path = audio_dir / f"scene-{scene.index:02d}.mp3"

    if not wb_path.exists():
        raise FileNotFoundError(f"Whiteboard video not found: {wb_path}")

    w, h = int(width), int(height)
    pip_x = w - PIP_SIZE - PIP_MARGIN
    pip_y = h - PIP_SIZE - PIP_MARGIN

    filter_parts = [
        f"[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2[bg]",
    ]

    inputs = ["-i", str(wb_path)]
    map_video = "[bg]"

    if avatar_path.exists():
        inputs.extend(["-i", str(avatar_path)])
        filter_parts.append(
            f"[1:v]scale={PIP_SIZE}:{PIP_SIZE},"
            f"format=yuva420p,"
            f"geq=lum='lum(X,Y)':a='if(gt(abs(X-{PIP_SIZE//2})*abs(X-{PIP_SIZE//2})"
            f"+abs(Y-{PIP_SIZE//2})*abs(Y-{PIP_SIZE//2}),{(PIP_SIZE//2)**2}),0,255)'[pip]"
        )
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
        raise RuntimeError(f"FFmpeg failed (whiteboard):\n{result.stderr}")

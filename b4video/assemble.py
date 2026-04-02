"""Stage 5: Assemble final video — concatenate scenes, add music, generate subtitles."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from b4video.manifest import Manifest
from b4video.parser import Scene, SceneMeta

CROSSFADE_DURATION = 0.5
TARGET_LUFS = -16
MUSIC_LUFS = -30


def assemble_video(
    meta: SceneMeta,
    scenes: list[Scene],
    build_dir: Path,
    manifest: Manifest,
    *,
    force: bool = False,
) -> Path:
    """Concatenate composed scenes with intro/outro into final video."""
    output_dir = build_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    composed_dir = build_dir / "composed"

    final_path = output_dir / "final.mp4"
    key = "final-video"

    if not force and manifest.is_complete(key) and final_path.exists():
        return final_path

    art = manifest.get_or_create(key, str(final_path))

    # Collect available composed scenes
    scene_files: list[Path] = []

    # Check for intro template
    intro = Path("assets/intro.mp4")
    if intro.exists():
        scene_files.append(intro)

    for scene in scenes:
        composed = composed_dir / f"scene-{scene.index:02d}.mp4"
        if composed.exists():
            scene_files.append(composed)

    # Check for outro template
    outro = Path("assets/outro.mp4")
    if outro.exists():
        scene_files.append(outro)

    if not scene_files:
        art.mark_failed("No composed scenes found")
        raise RuntimeError("No composed scenes found in build/composed/")

    try:
        _concatenate(scene_files, final_path, meta)
        _generate_subtitles(build_dir, output_dir)
        art.mark_complete()
        manifest.save(build_dir)
    except Exception as e:
        art.mark_failed(str(e))
        manifest.save(build_dir)
        raise

    return final_path


def _concatenate(files: list[Path], output: Path, meta: SceneMeta) -> None:
    """Concatenate video files with crossfade transitions."""
    if len(files) == 1:
        # Single file — just copy
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(files[0]), "-c", "copy", str(output)],
            capture_output=True, text=True, check=True,
        )
        return

    # Build concat filter with crossfades
    width, height = meta.resolution.split("x")

    # For simplicity with crossfades, use the concat demuxer for now
    # and apply audio normalization as a second pass
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        for path in files:
            f.write(f"file '{path.resolve()}'\n")
        filelist = f.name

    # Pass 1: concatenate
    concat_cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", filelist,
        "-c:v", "libopenh264",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(output),
    ]

    result = subprocess.run(concat_cmd, capture_output=True, text=True)
    Path(filelist).unlink(missing_ok=True)

    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg concat failed:\n{result.stderr}")


def _generate_subtitles(build_dir: Path, output_dir: Path) -> None:
    """Generate SRT subtitles from ElevenLabs timing data."""
    timing_path = build_dir / "audio" / "timing.json"
    srt_path = output_dir / "subtitles.srt"

    if not timing_path.exists():
        return  # No timing data available

    timing = json.loads(timing_path.read_text())

    srt_entries: list[str] = []
    counter = 1
    time_offset = 0.0

    for scene_key in sorted(timing.keys()):
        alignments = timing[scene_key]
        for alignment in alignments:
            chars = alignment.get("characters", [])
            starts = alignment.get("start_times", [])
            ends = alignment.get("end_times", [])

            if not chars or not starts or not ends:
                continue

            # Group characters into words/phrases for subtitle display
            text = "".join(chars)
            start_time = starts[0] + time_offset
            end_time = ends[-1] + time_offset

            srt_entries.append(
                f"{counter}\n"
                f"{_format_srt_time(start_time)} --> {_format_srt_time(end_time)}\n"
                f"{text}\n"
            )
            counter += 1

    srt_path.write_text("\n".join(srt_entries))


def _format_srt_time(seconds: float) -> str:
    """Format seconds as SRT timestamp (HH:MM:SS,mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

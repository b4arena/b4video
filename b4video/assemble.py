"""Stage 5: Assemble final video — crossfade scenes, add music, generate subtitles."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from b4video.manifest import Manifest
from b4video.parser import Scene, SceneMeta

CROSSFADE_DURATION = 0.5  # seconds


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

    intro = Path("assets/intro.mp4")
    if intro.exists():
        scene_files.append(intro)

    for scene in scenes:
        composed = composed_dir / f"scene-{scene.index:02d}.mp4"
        if composed.exists():
            scene_files.append(composed)

    outro = Path("assets/outro.mp4")
    if outro.exists():
        scene_files.append(outro)

    if not scene_files:
        art.mark_failed("No composed scenes found")
        raise RuntimeError("No composed scenes found in build/composed/")

    try:
        _assemble_with_crossfades(scene_files, final_path, meta)
        _generate_subtitles(build_dir, output_dir)
        art.mark_complete()
        manifest.save(build_dir)
    except Exception as e:
        art.mark_failed(str(e))
        manifest.save(build_dir)
        raise

    return final_path


def _get_duration(path: Path) -> float:
    """Get video duration in seconds via ffprobe."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    return float(result.stdout.strip())


def _assemble_with_crossfades(files: list[Path], output: Path, meta: SceneMeta) -> None:
    """Assemble video files with xfade crossfade transitions between scenes."""
    if len(files) == 1:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(files[0]), "-c", "copy", str(output)],
            capture_output=True, text=True, check=True,
        )
        return

    if len(files) == 2:
        # Simple two-file crossfade
        dur0 = _get_duration(files[0])
        offset = dur0 - CROSSFADE_DURATION

        cmd = [
            "ffmpeg", "-y",
            "-i", str(files[0]),
            "-i", str(files[1]),
            "-filter_complex",
            f"[0:v][1:v]xfade=transition=fade:duration={CROSSFADE_DURATION}:offset={offset}[v];"
            f"[0:a][1:a]acrossfade=d={CROSSFADE_DURATION}[a]",
            "-map", "[v]", "-map", "[a]",
            "-c:v", "libopenh264",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            str(output),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg xfade failed:\n{result.stderr}")
        return

    # Multiple files: chain xfade filters
    # Get durations for offset calculation
    durations = [_get_duration(f) for f in files]

    # Build input args
    inputs = []
    for f in files:
        inputs.extend(["-i", str(f)])

    # Build chained xfade filter
    # Each xfade takes two streams and produces one, consuming CROSSFADE_DURATION
    # from the end of the first and start of the second
    video_filters = []
    audio_filters = []

    # Calculate offsets: each offset is cumulative duration minus crossfade overlaps
    cumulative = 0.0
    offsets = []
    for i, dur in enumerate(durations[:-1]):
        cumulative += dur - CROSSFADE_DURATION
        offsets.append(cumulative)

    # Chain video xfade: [0:v][1:v]xfade -> [v01]; [v01][2:v]xfade -> [v012]; etc
    n = len(files)
    prev_label = "0:v"
    for i in range(1, n):
        out_label = f"v{i}"
        offset = offsets[i - 1]
        # Use cumulative offset from start, not from previous
        actual_offset = sum(durations[:i]) - (CROSSFADE_DURATION * i)
        video_filters.append(
            f"[{prev_label}][{i}:v]xfade=transition=fade:"
            f"duration={CROSSFADE_DURATION}:offset={actual_offset:.3f}[{out_label}]"
        )
        prev_label = out_label

    # Chain audio acrossfade similarly
    prev_alabel = "0:a"
    for i in range(1, n):
        out_alabel = f"a{i}"
        audio_filters.append(
            f"[{prev_alabel}][{i}:a]acrossfade=d={CROSSFADE_DURATION}[{out_alabel}]"
        )
        prev_alabel = out_alabel

    filter_complex = ";".join(video_filters + audio_filters)

    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", f"[{prev_label}]",
        "-map", f"[{prev_alabel}]",
        "-c:v", "libopenh264",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(output),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg xfade chain failed:\n{result.stderr}")


def _generate_subtitles(build_dir: Path, output_dir: Path) -> None:
    """Generate SRT subtitles from ElevenLabs timing data."""
    timing_path = build_dir / "audio" / "timing.json"
    srt_path = output_dir / "subtitles.srt"

    if not timing_path.exists():
        return

    timing = json.loads(timing_path.read_text())

    srt_entries: list[str] = []
    counter = 1
    time_offset = 0.0

    for scene_key in sorted(timing.keys()):
        alignment = timing[scene_key]
        chars = alignment.get("characters", [])
        starts = alignment.get("start_times", [])
        ends = alignment.get("end_times", [])

        if not chars or not starts or not ends:
            continue

        # Group characters into words for subtitle display
        word = ""
        word_start = 0.0
        for i, ch in enumerate(chars):
            if ch == " " and word.strip():
                srt_entries.append(
                    f"{counter}\n"
                    f"{_format_srt_time(word_start + time_offset)} --> "
                    f"{_format_srt_time(ends[i - 1] + time_offset)}\n"
                    f"{word.strip()}\n"
                )
                counter += 1
                word = ""
                word_start = starts[i + 1] if i + 1 < len(starts) else starts[i]
            else:
                if not word:
                    word_start = starts[i]
                word += ch

        # Last word
        if word.strip():
            srt_entries.append(
                f"{counter}\n"
                f"{_format_srt_time(word_start + time_offset)} --> "
                f"{_format_srt_time(ends[-1] + time_offset)}\n"
                f"{word.strip()}\n"
            )
            counter += 1

        time_offset += ends[-1]

    srt_path.write_text("\n".join(srt_entries))


def _format_srt_time(seconds: float) -> str:
    """Format seconds as SRT timestamp (HH:MM:SS,mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

"""Generate intro/outro template videos from logo + brand colors."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

# b4arena brand colors (from tabula/src/css/custom.css)
BG_COLOR = "0x2f495e"       # primary-darkest (dark steel blue) — FFmpeg hex format
TEXT_COLOR = "0xc0d5e7"     # primary-lightest (pale blue)
ACCENT_COLOR = "0xc9a84c"  # gold accent
SUBTITLE_COLOR = "0x7ca7cb"  # primary (medium blue)

INTRO_DURATION = 4.0  # seconds
OUTRO_DURATION = 4.0  # seconds

FONT = "Noto Sans"


def _find_encoder() -> list[str]:
    """Find the best available H.264 encoder."""
    result = subprocess.run(
        ["ffmpeg", "-encoders"], capture_output=True, text=True
    )
    if "libx264" in result.stdout:
        return ["-c:v", "libx264", "-preset", "medium", "-crf", "18"]
    return ["-c:v", "libopenh264", "-b:v", "2M"]


def generate_intro(
    output: Path,
    logo: Path,
    *,
    title: str = "b4arena",
    subtitle: str = "",
    width: int = 1920,
    height: int = 1080,
    fps: int = 30,
) -> None:
    """Generate an intro template video.

    Timeline:
      0.0 - 0.5s: fade in from black
      0.5 - 1.5s: logo appears
      1.5 - 3.5s: title + subtitle fade in below logo
      3.5 - 4.0s: hold (crossfade to first scene handled by compose stage)
    """
    if not logo.exists():
        raise FileNotFoundError(f"Logo not found: {logo}")

    logo_y = height // 3
    title_esc = _escape_drawtext(title)
    subtitle_esc = _escape_drawtext(subtitle)
    encoder = _find_encoder()

    filter_complex = ";".join([
        # Background color
        f"color=c={BG_COLOR}:s={width}x{height}:d={INTRO_DURATION}:r={fps},format=yuv420p[bg]",
        # Logo: scale to 480px wide, fade in
        f"[1:v]scale=480:-1,format=yuva420p,"
        f"fade=t=in:st=0.3:d=0.7:alpha=1[logo]",
        # Overlay logo centered
        f"[bg][logo]overlay=(W-w)/2:{logo_y - 120}:eof_action=pass[v1]",
        # Title text
        f"[v1]drawtext="
        f"text='{title_esc}':"
        f"fontsize=72:fontcolor={TEXT_COLOR}:"
        f"x=(w-text_w)/2:y={logo_y + 130}:"
        f"alpha='if(lt(t\\,1.5)\\,0\\,min((t-1.5)/0.5\\,1))':"
        f"font='{FONT}'[v2]",
        # Subtitle text
        f"[v2]drawtext="
        f"text='{subtitle_esc}':"
        f"fontsize=36:fontcolor={SUBTITLE_COLOR}:"
        f"x=(w-text_w)/2:y={logo_y + 220}:"
        f"alpha='if(lt(t\\,2.0)\\,0\\,min((t-2.0)/0.5\\,1))':"
        f"font='{FONT}'[v3]",
        # Fade in from black
        f"[v3]fade=t=in:st=0:d=0.5[vout]",
    ])

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c={BG_COLOR}:s={width}x{height}:d={INTRO_DURATION}:r={fps}",
        "-loop", "1", "-t", str(INTRO_DURATION), "-i", str(logo),
        "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo",
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-map", "2:a",
        *encoder,
        "-c:a", "aac", "-b:a", "192k",
        "-t", str(INTRO_DURATION),
        "-pix_fmt", "yuv420p",
        str(output),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg intro generation failed:\n{result.stderr}")

    _verify_output(output, INTRO_DURATION, fps)


def generate_outro(
    output: Path,
    logo: Path,
    *,
    website: str = "b4arena.com",
    cta: str = "Subscribe for more",
    width: int = 1920,
    height: int = 1080,
    fps: int = 30,
) -> None:
    """Generate an outro template video.

    Timeline:
      0.0 - 0.5s: fade in
      0.5 - 2.5s: logo + website URL
      2.5 - 3.5s: CTA text fades in
      3.5 - 4.0s: fade to black
    """
    if not logo.exists():
        raise FileNotFoundError(f"Logo not found: {logo}")

    logo_y = height // 3
    website_esc = _escape_drawtext(website)
    cta_esc = _escape_drawtext(cta)
    encoder = _find_encoder()

    filter_complex = ";".join([
        # Background
        f"color=c={BG_COLOR}:s={width}x{height}:d={OUTRO_DURATION}:r={fps},format=yuv420p[bg]",
        # Logo: 360px wide
        f"[1:v]scale=360:-1,format=yuva420p[logo]",
        f"[bg][logo]overlay=(W-w)/2:{logo_y - 80}:eof_action=pass[v1]",
        # Website URL
        f"[v1]drawtext="
        f"text='{website_esc}':"
        f"fontsize=42:fontcolor={ACCENT_COLOR}:"
        f"x=(w-text_w)/2:y={logo_y + 100}:"
        f"font='{FONT}'[v2]",
        # CTA — fades in
        f"[v2]drawtext="
        f"text='{cta_esc}':"
        f"fontsize=32:fontcolor={TEXT_COLOR}:"
        f"x=(w-text_w)/2:y={logo_y + 160}:"
        f"alpha='if(lt(t\\,2.5)\\,0\\,min((t-2.5)/0.5\\,1))':"
        f"font='{FONT}'[v3]",
        # Fade to black at end
        f"[v3]fade=t=out:st=3.5:d=0.5[vout]",
    ])

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c={BG_COLOR}:s={width}x{height}:d={OUTRO_DURATION}:r={fps}",
        "-loop", "1", "-t", str(OUTRO_DURATION), "-i", str(logo),
        "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo",
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-map", "2:a",
        *encoder,
        "-c:a", "aac", "-b:a", "192k",
        "-t", str(OUTRO_DURATION),
        "-pix_fmt", "yuv420p",
        str(output),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg outro generation failed:\n{result.stderr}")

    _verify_output(output, OUTRO_DURATION, fps)


def _escape_drawtext(text: str) -> str:
    """Escape special characters for FFmpeg drawtext filter."""
    # Escape characters that have special meaning in drawtext
    text = text.replace("\\", "\\\\")
    text = text.replace("'", "'\\''")
    text = text.replace(":", "\\:")
    text = text.replace("%", "%%")
    return text


def _verify_output(path: Path, expected_duration: float, expected_fps: int) -> None:
    """Verify the output video has the expected frame count."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=nb_frames",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        try:
            nb_frames = int(result.stdout.strip())
            expected = int(expected_duration * expected_fps)
            if nb_frames < expected // 2:
                raise RuntimeError(
                    f"Output has only {nb_frames} frames (expected ~{expected}). "
                    f"This usually means the encoder dropped frames. "
                    f"Try installing libx264: the video file at {path} may be broken."
                )
        except ValueError:
            pass  # Can't parse frame count — skip verification

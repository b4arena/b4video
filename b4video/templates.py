"""Generate intro/outro template videos from logo + brand colors."""

from __future__ import annotations

import subprocess
from pathlib import Path

# b4arena brand colors (from tabula/src/css/custom.css)
BG_COLOR = "#2f495e"         # primary-darkest (dark steel blue)
TEXT_COLOR = "#c0d5e7"       # primary-lightest (pale blue)
ACCENT_COLOR = "#c9a84c"    # gold accent
SUBTITLE_COLOR = "#7ca7cb"  # primary (medium blue)

INTRO_DURATION = 4.0  # seconds
OUTRO_DURATION = 4.0  # seconds


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
      0.5 - 1.5s: logo appears (scale up)
      1.5 - 3.5s: title + subtitle fade in below logo
      3.5 - 4.0s: hold (crossfade to first scene handled by compose stage)
    """
    if not logo.exists():
        raise FileNotFoundError(f"Logo not found: {logo}")

    # Logo positioning: centered, upper third
    logo_y = height // 3

    filter_complex = (
        # Background
        f"color=c={BG_COLOR}:s={width}x{height}:d={INTRO_DURATION}:r={fps}[bg];"
        # Logo: scale to 300px wide, fade in
        f"[1:v]scale=300:-1,format=rgba,"
        f"fade=t=in:st=0.3:d=0.7:alpha=1[logo];"
        # Overlay logo centered
        f"[bg][logo]overlay=(W-w)/2:{logo_y - 75}:shortest=1[with_logo];"
        # Draw title text
        f"[with_logo]drawtext="
        f"text='{_escape_ffmpeg_text(title)}':"
        f"fontsize=64:fontcolor={TEXT_COLOR}:"
        f"x=(w-text_w)/2:y={logo_y + 100}:"
        f"alpha='if(lt(t,1.5),0,min((t-1.5)/0.5,1))':"
        f"font='Noto Sans'"
        f"[with_title];"
        # Draw subtitle if provided
        f"[with_title]drawtext="
        f"text='{_escape_ffmpeg_text(subtitle)}':"
        f"fontsize=32:fontcolor={SUBTITLE_COLOR}:"
        f"x=(w-text_w)/2:y={logo_y + 180}:"
        f"alpha='if(lt(t,2.0),0,min((t-2.0)/0.5,1))':"
        f"font='Noto Sans'"
        f"[with_sub];"
        # Global fade in from black
        f"[with_sub]fade=t=in:st=0:d=0.5[out]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c={BG_COLOR}:s={width}x{height}:d={INTRO_DURATION}:r={fps}",
        "-i", str(logo),
        "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo:d={INTRO_DURATION}",
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-map", "2:a",
        "-c:v", "libopenh264",
        "-c:a", "aac", "-b:a", "192k",
        "-t", str(INTRO_DURATION),
        "-pix_fmt", "yuv420p",
        str(output),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg intro generation failed:\n{result.stderr}")


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
      0.0 - 0.5s: crossfade in (from last scene, handled by compose stage)
      0.5 - 2.5s: logo + website URL
      2.5 - 3.5s: CTA text fades in
      3.5 - 4.0s: fade to black
    """
    if not logo.exists():
        raise FileNotFoundError(f"Logo not found: {logo}")

    logo_y = height // 3

    filter_complex = (
        # Background
        f"color=c={BG_COLOR}:s={width}x{height}:d={OUTRO_DURATION}:r={fps}[bg];"
        # Logo
        f"[1:v]scale=200:-1,format=rgba[logo];"
        f"[bg][logo]overlay=(W-w)/2:{logo_y - 50}:shortest=1[with_logo];"
        # Website URL
        f"[with_logo]drawtext="
        f"text='{_escape_ffmpeg_text(website)}':"
        f"fontsize=36:fontcolor={ACCENT_COLOR}:"
        f"x=(w-text_w)/2:y={logo_y + 80}:"
        f"font='Noto Sans'"
        f"[with_url];"
        # CTA
        f"[with_url]drawtext="
        f"text='{_escape_ffmpeg_text(cta)}':"
        f"fontsize=28:fontcolor={TEXT_COLOR}:"
        f"x=(w-text_w)/2:y={logo_y + 140}:"
        f"alpha='if(lt(t,2.5),0,min((t-2.5)/0.5,1))':"
        f"font='Noto Sans'"
        f"[with_cta];"
        # Fade to black at end
        f"[with_cta]fade=t=out:st=3.5:d=0.5[out]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c={BG_COLOR}:s={width}x{height}:d={OUTRO_DURATION}:r={fps}",
        "-i", str(logo),
        "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo:d={OUTRO_DURATION}",
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-map", "2:a",
        "-c:v", "libopenh264",
        "-c:a", "aac", "-b:a", "192k",
        "-t", str(OUTRO_DURATION),
        "-pix_fmt", "yuv420p",
        str(output),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg outro generation failed:\n{result.stderr}")


def _escape_ffmpeg_text(text: str) -> str:
    """Escape special characters for FFmpeg drawtext filter."""
    return text.replace("'", "'\\''").replace(":", "\\:").replace("%", "%%")

"""Stage 3: Generate visual assets — HeyGen avatars + Showboat screen recordings."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

import httpx

from b4video.config import Config
from b4video.manifest import Manifest
from b4video.parser import Scene, SceneMeta

HEYGEN_API_BASE = "https://api.heygen.com"
HEYGEN_POLL_INTERVAL = 10  # seconds
HEYGEN_TIMEOUT = 600  # 10 minutes


def generate_visuals(
    meta: SceneMeta,
    scenes: list[Scene],
    build_dir: Path,
    manifest: Manifest,
    config: Config,
    *,
    force: bool = False,
) -> None:
    """Generate visual assets for all scenes.

    Presenter scenes: submit audio to HeyGen, get avatar video.
    Demo scenes: run Showboat script, capture screen recording.
    """
    video_dir = build_dir / "video"
    video_dir.mkdir(parents=True, exist_ok=True)
    audio_dir = build_dir / "audio"

    avatar_id = config.avatars.get(meta.avatar, meta.avatar)

    for scene in scenes:
        if scene.scene_type == "presenter":
            _generate_avatar(scene, audio_dir, video_dir, manifest, config, avatar_id, force=force)
        elif scene.scene_type == "demo":
            _run_showboat(scene, video_dir, manifest, force=force)

        manifest.save(build_dir)


def _generate_avatar(
    scene: Scene,
    audio_dir: Path,
    video_dir: Path,
    manifest: Manifest,
    config: Config,
    avatar_id: str,
    *,
    force: bool = False,
) -> None:
    """Submit audio to HeyGen and poll for avatar video."""
    key = f"video-scene-{scene.index:02d}-avatar"
    video_path = video_dir / f"scene-{scene.index:02d}-avatar.mp4"

    if not force and manifest.is_complete(key) and video_path.exists():
        return

    art = manifest.get_or_create(key, str(video_path))
    audio_path = audio_dir / f"scene-{scene.index:02d}.mp3"

    if not audio_path.exists():
        art.mark_failed(f"Audio not found: {audio_path}")
        return

    if not config.heygen_api_key:
        art.mark_failed("HEYGEN_API_KEY not configured")
        raise RuntimeError("HEYGEN_API_KEY not configured")

    headers = {"X-Api-Key": config.heygen_api_key}

    try:
        # Upload audio
        with httpx.Client(timeout=60) as client:
            upload_resp = client.post(
                f"{HEYGEN_API_BASE}/v1/asset",
                headers=headers,
                files={"file": ("audio.mp3", audio_path.read_bytes(), "audio/mpeg")},
            )
            upload_resp.raise_for_status()
            audio_asset_id = upload_resp.json()["data"]["asset_id"]

            # Create video generation task
            create_resp = client.post(
                f"{HEYGEN_API_BASE}/v2/video/generate",
                headers={**headers, "Content-Type": "application/json"},
                json={
                    "video_inputs": [{
                        "character": {
                            "type": "avatar",
                            "avatar_id": avatar_id,
                        },
                        "voice": {
                            "type": "audio",
                            "audio_asset_id": audio_asset_id,
                        },
                    }],
                    "dimension": {"width": 1920, "height": 1080},
                },
            )
            create_resp.raise_for_status()
            video_id = create_resp.json()["data"]["video_id"]

            # Poll for completion
            elapsed = 0
            while elapsed < HEYGEN_TIMEOUT:
                time.sleep(HEYGEN_POLL_INTERVAL)
                elapsed += HEYGEN_POLL_INTERVAL

                status_resp = client.get(
                    f"{HEYGEN_API_BASE}/v1/video_status.get",
                    headers=headers,
                    params={"video_id": video_id},
                )
                status_resp.raise_for_status()
                status = status_resp.json()["data"]["status"]

                if status == "completed":
                    video_url = status_resp.json()["data"]["video_url"]
                    # Download the video
                    dl_resp = client.get(video_url)
                    dl_resp.raise_for_status()
                    video_path.write_bytes(dl_resp.content)
                    art.mark_complete()
                    return
                elif status == "failed":
                    error = status_resp.json()["data"].get("error", "Unknown error")
                    art.mark_failed(f"HeyGen generation failed: {error}")
                    return

            art.mark_failed(f"HeyGen timeout after {HEYGEN_TIMEOUT}s")

    except Exception as e:
        art.mark_failed(str(e))
        raise


def _run_showboat(
    scene: Scene,
    video_dir: Path,
    manifest: Manifest,
    *,
    force: bool = False,
) -> None:
    """Run a Showboat script and capture screen recording."""
    key = f"video-scene-{scene.index:02d}-screen"
    video_path = video_dir / f"scene-{scene.index:02d}-screen.webm"

    if not force and manifest.is_complete(key) and video_path.exists():
        return

    art = manifest.get_or_create(key, str(video_path))

    if not scene.showboat_script:
        art.mark_failed("No showboat script specified")
        return

    script_path = Path(scene.showboat_script)
    if not script_path.exists():
        art.mark_failed(f"Showboat script not found: {script_path}")
        return

    try:
        result = subprocess.run(
            ["showboat", "record", str(script_path), "--output", str(video_path)],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            art.mark_failed(f"Showboat failed:\n{result.stderr}")
            return

        art.mark_complete()

    except subprocess.TimeoutExpired:
        art.mark_failed("Showboat script timed out (300s)")
    except FileNotFoundError:
        art.mark_failed("'showboat' command not found — is it installed?")
    except Exception as e:
        art.mark_failed(str(e))
        raise

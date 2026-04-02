"""Stage 2: Generate voice narration via ElevenLabs."""

from __future__ import annotations

from pathlib import Path

from b4video.config import Config
from b4video.manifest import Manifest
from b4video.parser import Scene, SceneMeta


def generate_voice(
    meta: SceneMeta,
    scenes: list[Scene],
    build_dir: Path,
    manifest: Manifest,
    config: Config,
    *,
    force: bool = False,
) -> None:
    """Generate audio for all scenes via ElevenLabs.

    Produces build/audio/scene-NN.mp3 and build/audio/timing.json.
    Skips scenes that already have completed audio (idempotent).
    """
    from elevenlabs.client import ElevenLabs

    audio_dir = build_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    if not config.elevenlabs_api_key:
        raise RuntimeError("ELEVENLABS_API_KEY not configured")

    client = ElevenLabs(api_key=config.elevenlabs_api_key)

    # Resolve voice alias to ID
    voice_id = config.voices.get(meta.voice, meta.voice)

    timing_data: dict[str, list] = {}

    for scene in scenes:
        key = f"audio-scene-{scene.index:02d}"
        audio_path = audio_dir / f"scene-{scene.index:02d}.mp3"

        if not force and manifest.is_complete(key) and audio_path.exists():
            continue

        art = manifest.get_or_create(key, str(audio_path))

        try:
            response = client.text_to_speech.convert_with_timestamps(
                text=scene.narration,
                voice_id=voice_id,
                model_id="eleven_multilingual_v2",
                output_format="mp3_44100_128",
            )

            # Write audio
            audio_bytes = b""
            word_timestamps = []
            for chunk in response:
                if hasattr(chunk, "audio_base64") and chunk.audio_base64:
                    import base64
                    audio_bytes += base64.b64decode(chunk.audio_base64)
                if hasattr(chunk, "alignment") and chunk.alignment:
                    word_timestamps.append({
                        "characters": chunk.alignment.characters,
                        "start_times": chunk.alignment.character_start_times_seconds,
                        "end_times": chunk.alignment.character_end_times_seconds,
                    })

            audio_path.write_bytes(audio_bytes)
            timing_data[f"scene-{scene.index:02d}"] = word_timestamps
            art.mark_complete()

        except Exception as e:
            art.mark_failed(str(e))
            raise

        manifest.save(build_dir)

    # Write timing data
    import json
    timing_path = audio_dir / "timing.json"
    timing_path.write_text(json.dumps(timing_data, indent=2))

"""Configuration management for b4video."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


# Brand defaults — override via config file or env vars
BUILTIN_VOICES = {
    "b4arena-default": "IKne3meq5aSn9XLyUdCD",  # Charlie — Deep, Confident, Energetic
}
BUILTIN_AVATARS = {
    "presenter-01": "August_Hoodies_Front_public",  # August in hoodie, front-facing
}


@dataclass
class Config:
    """b4video configuration."""

    elevenlabs_api_key: str = ""
    heygen_api_key: str = ""
    default_voice: str = "b4arena-default"
    default_avatar: str = "presenter-01"
    voices: dict[str, str] = field(default_factory=lambda: dict(BUILTIN_VOICES))
    avatars: dict[str, str] = field(default_factory=lambda: dict(BUILTIN_AVATARS))


def load_config() -> Config:
    """Load configuration from environment, .env, and config file."""
    config = Config()

    # Environment variables take precedence
    config.elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY", "")
    config.heygen_api_key = os.getenv("HEYGEN_API_KEY", "")
    config.default_voice = os.getenv("B4VIDEO_DEFAULT_VOICE", "b4arena-default")
    config.default_avatar = os.getenv("B4VIDEO_DEFAULT_AVATAR", "presenter-01")

    # Load TOML/YAML config file if it exists
    config_path = Path.home() / ".config" / "b4video" / "config.yaml"
    if config_path.exists():
        with open(config_path) as f:
            data = yaml.safe_load(f) or {}
        config.voices = data.get("voices", {})
        config.avatars = data.get("avatars", {})
        if not config.elevenlabs_api_key:
            config.elevenlabs_api_key = data.get("elevenlabs", {}).get("api_key", "")
        if not config.heygen_api_key:
            config.heygen_api_key = data.get("heygen", {}).get("api_key", "")

    return config

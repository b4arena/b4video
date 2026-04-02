"""Stage 1: Parse Markdown script into scene list."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml


@dataclass
class SceneMeta:
    """Frontmatter metadata for the video."""

    title: str
    voice: str = "b4arena-default"
    avatar: str = "presenter-01"
    resolution: str = "1920x1080"
    fps: int = 30
    music: str | None = None


@dataclass
class Scene:
    """A single scene parsed from the script."""

    index: int
    heading: str
    scene_type: str  # "presenter" or "demo"
    narration: str
    showboat_script: str | None = None


def parse_script(script_path: str | Path) -> tuple[SceneMeta, list[Scene]]:
    """Parse a Markdown video script into metadata and scenes.

    Returns (metadata, scenes) or raises ValueError on validation errors.
    """
    path = Path(script_path)
    if not path.exists():
        raise ValueError(f"Script not found: {path}")

    content = path.read_text()

    # Split frontmatter
    meta, body = _split_frontmatter(content)

    # Parse scenes from body
    scenes = _parse_scenes(body)

    # Validate
    _validate(meta, scenes, path.parent)

    return meta, scenes


def _split_frontmatter(content: str) -> tuple[SceneMeta, str]:
    """Extract YAML frontmatter and return (meta, body)."""
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
    if not match:
        raise ValueError("Script must start with YAML frontmatter (--- ... ---)")

    raw = yaml.safe_load(match.group(1)) or {}
    if "title" not in raw:
        raise ValueError("Frontmatter must include 'title'")

    meta = SceneMeta(
        title=raw["title"],
        voice=raw.get("voice", "b4arena-default"),
        avatar=raw.get("avatar", "presenter-01"),
        resolution=raw.get("resolution", "1920x1080"),
        fps=raw.get("fps", 30),
        music=raw.get("music"),
    )
    return meta, match.group(2)


def _parse_scenes(body: str) -> list[Scene]:
    """Parse ## headings into Scene objects."""
    # Split on ## headings
    parts = re.split(r"^## (.+)$", body, flags=re.MULTILINE)

    scenes: list[Scene] = []
    # parts[0] is text before first heading (ignored)
    # then alternating: heading, content, heading, content, ...
    for i in range(1, len(parts), 2):
        heading = parts[i].strip()
        content = parts[i + 1] if i + 1 < len(parts) else ""

        scene_type = _extract_comment(content, "type") or "presenter"
        if scene_type == "pip":
            scene_type = "demo"

        showboat = _extract_comment(content, "showboat")

        # Narration is the content minus HTML comments
        narration = re.sub(r"<!--.*?-->", "", content, flags=re.DOTALL).strip()

        scenes.append(Scene(
            index=len(scenes),
            heading=heading,
            scene_type=scene_type,
            narration=narration,
            showboat_script=showboat,
        ))

    return scenes


def _extract_comment(content: str, key: str) -> str | None:
    """Extract a value from <!-- key: value --> comment."""
    match = re.search(rf"<!--\s*{key}:\s*(.+?)\s*-->", content)
    return match.group(1).strip() if match else None


def _validate(meta: SceneMeta, scenes: list[Scene], script_dir: Path) -> None:
    """Validate parsed script."""
    if not scenes:
        raise ValueError("Script must contain at least one ## section")

    valid_types = {"presenter", "demo"}
    for scene in scenes:
        if scene.scene_type not in valid_types:
            raise ValueError(
                f"Scene '{scene.heading}': unknown type '{scene.scene_type}' "
                f"(expected: {valid_types})"
            )
        if scene.scene_type == "demo" and not scene.showboat_script:
            raise ValueError(
                f"Scene '{scene.heading}': demo scenes require a "
                f"<!-- showboat: path/to/script.sh --> comment"
            )
        if not scene.narration:
            raise ValueError(f"Scene '{scene.heading}': no narration text found")

    # Validate resolution format
    if not re.match(r"^\d+x\d+$", meta.resolution):
        raise ValueError(f"Invalid resolution format: '{meta.resolution}' (expected WxH)")


def write_scenes_json(meta: SceneMeta, scenes: list[Scene], build_dir: Path) -> Path:
    """Write parsed scenes to build/scenes.json."""
    build_dir.mkdir(parents=True, exist_ok=True)
    output = build_dir / "scenes.json"
    data = {
        "meta": asdict(meta),
        "scenes": [asdict(s) for s in scenes],
    }
    output.write_text(json.dumps(data, indent=2))
    return output

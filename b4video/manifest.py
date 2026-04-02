"""Build manifest — tracks per-artifact status for idempotent re-runs."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class ArtifactStatus:
    """Status of a single build artifact."""

    path: str
    status: str = "pending"  # pending | complete | failed
    updated_at: str = ""
    error: str | None = None

    def mark_complete(self) -> None:
        self.status = "complete"
        self.updated_at = datetime.now(timezone.utc).isoformat()
        self.error = None

    def mark_failed(self, error: str) -> None:
        self.status = "failed"
        self.updated_at = datetime.now(timezone.utc).isoformat()
        self.error = error


@dataclass
class Manifest:
    """Build manifest tracking all artifacts."""

    artifacts: dict[str, ArtifactStatus] = field(default_factory=dict)

    def get_or_create(self, key: str, path: str) -> ArtifactStatus:
        if key not in self.artifacts:
            self.artifacts[key] = ArtifactStatus(path=path)
        return self.artifacts[key]

    def is_complete(self, key: str) -> bool:
        art = self.artifacts.get(key)
        return art is not None and art.status == "complete"

    def save(self, build_dir: Path) -> None:
        path = build_dir / "manifest.json"
        data = {k: asdict(v) for k, v in self.artifacts.items()}
        path.write_text(json.dumps(data, indent=2))

    @classmethod
    def load(cls, build_dir: Path) -> Manifest:
        path = build_dir / "manifest.json"
        if not path.exists():
            return cls()
        data = json.loads(path.read_text())
        artifacts = {k: ArtifactStatus(**v) for k, v in data.items()}
        return cls(artifacts=artifacts)

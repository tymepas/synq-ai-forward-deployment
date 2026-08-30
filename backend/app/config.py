from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """All filesystem locations used by the local CLI."""

    root: Path

    @property
    def corpus_dir(self) -> Path:
        local_bundle = self.root / "candidate_bundle"
        return local_bundle if local_bundle.exists() else self.root.parent / "candidate_bundle"

    @property
    def database_path(self) -> Path:
        return self.root / "data" / "meridian.db"

    @property
    def outputs_dir(self) -> Path:
        return self.root / "outputs"

    @property
    def audit_dir(self) -> Path:
        return self.root / "audit"


def default_settings() -> Settings:
    return Settings(root=Path(__file__).resolve().parents[1])

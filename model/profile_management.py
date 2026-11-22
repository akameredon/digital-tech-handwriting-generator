"""Teacher correction and reusable handwriting-profile management."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import os
import tempfile
from typing import Any, Dict, List, Optional

from renderer.stroke_handwriting import Stroke, WriterProfile


@dataclass(frozen=True)
class CorrectionEvent:
    timestamp: str
    character: str
    old_label: Optional[str]
    new_label: str
    reason: str


@dataclass
class ManagedWriterProfile:
    profile: WriterProfile
    version: int = 1
    corrections: List[CorrectionEvent] = field(default_factory=list)
    approved: bool = False

    def public_dict(self) -> Dict[str, Any]:
        return {
            "name": self.profile.name,
            "version": self.version,
            "approved": self.approved,
            "coverage": sorted(self.profile.strokes.keys()),
            "correction_count": len(self.corrections),
            "last_updated": self.corrections[-1].timestamp if self.corrections else None,
        }


class WriterProfileStore:
    """Persist teacher profiles safely and keep every correction auditable."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, name: str) -> Path:
        safe = "".join(char if char.isalnum() or char in "-_" else "_" for char in name).strip("_")
        if not safe:
            raise ValueError("Profile name must contain at least one letter or number.")
        return self.root / f"{safe}.json"

    @staticmethod
    def _serialize(managed: ManagedWriterProfile) -> Dict[str, Any]:
        profile = {key: value for key, value in managed.profile.__dict__.items() if key != "strokes"}
        profile["ink"] = list(managed.profile.ink)
        profile["strokes"] = managed.profile.strokes
        return {
            "profile": profile,
            "version": managed.version,
            "approved": managed.approved,
            "corrections": [asdict(event) for event in managed.corrections],
        }

    @staticmethod
    def _deserialize(data: Dict[str, Any]) -> ManagedWriterProfile:
        profile_data = data["profile"]
        profile = WriterProfile(
            **{key: value for key, value in profile_data.items() if key in WriterProfile.__dataclass_fields__}
        )
        profile.ink = tuple(profile.ink)
        profile.strokes = {
            label: [[tuple(point) for point in stroke] for stroke in strokes]
            for label, strokes in profile.strokes.items()
        }
        corrections = [CorrectionEvent(**item) for item in data.get("corrections", [])]
        return ManagedWriterProfile(profile, int(data.get("version", 1)), corrections, bool(data.get("approved", False)))

    def save(self, managed: ManagedWriterProfile) -> Path:
        destination = self._path(managed.profile.name)
        payload = json.dumps(self._serialize(managed), indent=2)
        fd, temporary = tempfile.mkstemp(prefix=destination.name, dir=self.root)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, destination)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return destination

    def load(self, name: str) -> ManagedWriterProfile:
        path = self._path(name)
        if not path.exists():
            raise FileNotFoundError(f"No handwriting profile named {name!r}.")
        return self._deserialize(json.loads(path.read_text(encoding="utf-8")))

    def list_profiles(self) -> List[Dict[str, Any]]:
        result = []
        for path in sorted(self.root.glob("*.json")):
            try:
                result.append(self._deserialize(json.loads(path.read_text(encoding="utf-8"))).public_dict())
            except (OSError, ValueError, KeyError, TypeError):
                continue
        return result

    def correct_label(self, managed: ManagedWriterProfile, character: str, new_label: str, reason: str = "teacher correction") -> ManagedWriterProfile:
        if len(character) != 1 or len(new_label) != 1:
            raise ValueError("Corrections must use one character for the old and new labels.")
        if character not in managed.profile.strokes:
            raise KeyError(f"Profile has no trajectory for {character!r}.")
        old_label = character
        trajectory = managed.profile.strokes.pop(character)
        managed.profile.strokes[new_label] = trajectory
        managed.version += 1
        managed.approved = False
        managed.corrections.append(CorrectionEvent(datetime.now(timezone.utc).isoformat(), character, old_label, new_label, reason))
        return managed

    def approve(self, managed: ManagedWriterProfile) -> ManagedWriterProfile:
        if not managed.profile.strokes:
            raise ValueError("Cannot approve a profile with no handwriting trajectories.")
        managed.approved = True
        managed.version += 1
        return managed

"""Data models for DevPulse."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class ItemType(StrEnum):
    """Type of item being tracked."""

    PYPI = "pypi"
    GITHUB = "github"
    TOPIC = "topic"


@dataclass
class TrackedItem:
    """An item the user wants to track (package, repo, or topic)."""

    name: str
    item_type: ItemType
    source_url: str | None = None
    current_version: str | None = None
    added_at: datetime = field(default_factory=datetime.now)
    last_checked: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to a JSON-serializable dict."""
        data = asdict(self)
        data["item_type"] = self.item_type.value
        data["added_at"] = self.added_at.isoformat()
        data["last_checked"] = self.last_checked.isoformat() if self.last_checked else None
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TrackedItem:
        """Create from a dict (e.g. loaded from JSON)."""
        return cls(
            name=data["name"],
            item_type=ItemType(data["item_type"]),
            source_url=data.get("source_url"),
            current_version=data.get("current_version"),
            added_at=datetime.fromisoformat(data["added_at"]),
            last_checked=datetime.fromisoformat(data["last_checked"]) if data.get("last_checked") else None,
        )

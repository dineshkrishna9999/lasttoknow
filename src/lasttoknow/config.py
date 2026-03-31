"""Configuration management for LastToKnow.

Stores tracked items and settings in ~/.lasttoknow/ as JSON files.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from lasttoknow.models import ItemType, TrackedItem

logger = logging.getLogger(__name__)

DEFAULT_DIR = Path.home() / ".lasttoknow"


class LastToKnowConfig:
    """Manages tracked items and settings.

    Everything is saved as JSON in ~/.lasttoknow/.
    """

    def __init__(self, config_dir: Path | None = None) -> None:
        self._dir = config_dir or DEFAULT_DIR
        self._settings: dict[str, Any] = {}
        self._tracked: list[TrackedItem] = []
        self._loaded = False

    @property
    def config_dir(self) -> Path:
        return self._dir

    @property
    def config_file(self) -> Path:
        return self._dir / "config.json"

    @property
    def tracked_file(self) -> Path:
        return self._dir / "tracked.json"

    # ── Settings ──────────────────────────────────

    @property
    def model(self) -> str | None:
        """LLM model to use (e.g. 'azure/gpt-4.1')."""
        self._ensure_loaded()
        value = self._settings.get("model")
        if value is None or isinstance(value, str):
            return value
        return str(value)

    @model.setter
    def model(self, value: str | None) -> None:
        self._ensure_loaded()
        self._settings["model"] = value

    @property
    def sources(self) -> list[str]:
        """Enabled data sources."""
        self._ensure_loaded()
        value = self._settings.get("sources")
        if isinstance(value, list):
            return [str(s) for s in value]
        return ["pypi", "github", "hackernews", "reddit"]

    @property
    def default_days(self) -> int:
        """How many days to look back in briefings."""
        self._ensure_loaded()
        value = self._settings.get("default_days")
        if isinstance(value, int):
            return value
        return 7

    # ── Tracked Items ─────────────────────────────

    @property
    def tracked_items(self) -> list[TrackedItem]:
        self._ensure_loaded()
        return list(self._tracked)

    def add_item(
        self,
        name: str,
        item_type: ItemType,
        *,
        source_url: str | None = None,
        current_version: str | None = None,
    ) -> TrackedItem:
        """Add an item to track. Raises ValueError if duplicate."""
        self._ensure_loaded()
        for existing in self._tracked:
            if existing.name == name and existing.item_type == item_type:
                msg = f"Already tracking '{name}' as {item_type.value}"
                raise ValueError(msg)

        item = TrackedItem(
            name=name,
            item_type=item_type,
            source_url=source_url,
            current_version=current_version,
        )
        self._tracked.append(item)
        self._save_tracked()
        return item

    def remove_item(self, name: str) -> bool:
        """Remove a tracked item by name. Returns True if found."""
        self._ensure_loaded()
        before = len(self._tracked)
        self._tracked = [i for i in self._tracked if i.name != name]
        if len(self._tracked) < before:
            self._save_tracked()
            return True
        return False

    def get_item(self, name: str) -> TrackedItem | None:
        """Get a tracked item by name."""
        self._ensure_loaded()
        for item in self._tracked:
            if item.name == name:
                return item
        return None

    def update_last_checked(self, name: str) -> None:
        """Mark an item as just checked."""
        self._ensure_loaded()
        for item in self._tracked:
            if item.name == name:
                item.last_checked = datetime.now()
                self._save_tracked()
                return

    def clear_all(self) -> int:
        """Remove all tracked items. Returns count removed."""
        self._ensure_loaded()
        count = len(self._tracked)
        self._tracked = []
        self._save_tracked()
        return count

    # ── Persistence ───────────────────────────────

    def load(self) -> None:
        """Load settings and tracked items from disk."""
        self._dir.mkdir(parents=True, exist_ok=True)
        self._load_settings()
        self._load_tracked()
        self._loaded = True

    def save_settings(self) -> None:
        """Save settings to disk."""
        self._dir.mkdir(parents=True, exist_ok=True)
        self.config_file.write_text(json.dumps(self._settings, indent=2))

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self.load()

    def _load_settings(self) -> None:
        if self.config_file.exists():
            try:
                self._settings = json.loads(self.config_file.read_text())
            except (json.JSONDecodeError, OSError):
                self._settings = {}
        else:
            self._settings = {}

    def _load_tracked(self) -> None:
        if self.tracked_file.exists():
            try:
                data = json.loads(self.tracked_file.read_text())
                self._tracked = [TrackedItem.from_dict(item) for item in data]
            except (json.JSONDecodeError, OSError, KeyError):
                self._tracked = []
        else:
            self._tracked = []

    def _save_tracked(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        data = [item.to_dict() for item in self._tracked]
        self.tracked_file.write_text(json.dumps(data, indent=2))

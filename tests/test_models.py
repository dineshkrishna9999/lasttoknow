"""Tests for devpulse data models."""

from datetime import datetime

from devpulse.models import ItemType, TrackedItem


class TestTrackedItem:
    """Tests for TrackedItem dataclass."""

    def test_create_pypi_item(self) -> None:
        item = TrackedItem(name="litellm", item_type=ItemType.PYPI, current_version="1.40.0")
        assert item.name == "litellm"
        assert item.item_type == ItemType.PYPI
        assert item.current_version == "1.40.0"
        assert item.source_url is None
        assert item.last_checked is None

    def test_create_github_item(self) -> None:
        item = TrackedItem(
            name="BerriAI/litellm",
            item_type=ItemType.GITHUB,
            source_url="https://github.com/BerriAI/litellm",
        )
        assert item.item_type == ItemType.GITHUB
        assert item.source_url == "https://github.com/BerriAI/litellm"

    def test_create_topic_item(self) -> None:
        item = TrackedItem(name="AI agents", item_type=ItemType.TOPIC)
        assert item.item_type == ItemType.TOPIC

    def test_to_dict(self) -> None:
        now = datetime(2026, 3, 29, 12, 0, 0)
        item = TrackedItem(
            name="litellm",
            item_type=ItemType.PYPI,
            current_version="1.40.0",
            added_at=now,
        )
        data = item.to_dict()
        assert data["name"] == "litellm"
        assert data["item_type"] == "pypi"
        assert data["added_at"] == "2026-03-29T12:00:00"
        assert data["last_checked"] is None

    def test_from_dict_roundtrip(self) -> None:
        now = datetime(2026, 3, 29, 12, 0, 0)
        original = TrackedItem(
            name="litellm",
            item_type=ItemType.PYPI,
            current_version="1.40.0",
            added_at=now,
        )
        data = original.to_dict()
        restored = TrackedItem.from_dict(data)
        assert restored.name == original.name
        assert restored.item_type == original.item_type
        assert restored.current_version == original.current_version
        assert restored.added_at == original.added_at

    def test_from_dict_with_last_checked(self) -> None:
        data = {
            "name": "click",
            "item_type": "pypi",
            "current_version": "8.1.0",
            "added_at": "2026-03-29T10:00:00",
            "last_checked": "2026-03-29T12:00:00",
        }
        item = TrackedItem.from_dict(data)
        assert item.last_checked == datetime(2026, 3, 29, 12, 0, 0)


class TestItemType:
    """Tests for ItemType enum."""

    def test_values(self) -> None:
        assert ItemType.PYPI.value == "pypi"
        assert ItemType.GITHUB.value == "github"
        assert ItemType.TOPIC.value == "topic"

    def test_from_string(self) -> None:
        assert ItemType("pypi") == ItemType.PYPI
        assert ItemType("github") == ItemType.GITHUB

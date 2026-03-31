"""Tests for lasttoknow config management."""

import json
from pathlib import Path

import pytest

from lasttoknow.config import LastToKnowConfig
from lasttoknow.models import ItemType


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    """Provide a temporary config directory."""
    return tmp_path / "lasttoknow"


@pytest.fixture
def config(config_dir: Path) -> LastToKnowConfig:
    """Provide a LastToKnowConfig with a temp directory."""
    return LastToKnowConfig(config_dir=config_dir)


class TestConfigDirs:
    """Tests for config directory setup."""

    def test_creates_directory_on_load(self, config: LastToKnowConfig, config_dir: Path) -> None:
        config.load()
        assert config_dir.exists()

    def test_config_file_paths(self, config: LastToKnowConfig, config_dir: Path) -> None:
        assert config.config_file == config_dir / "config.json"
        assert config.tracked_file == config_dir / "tracked.json"


class TestSettings:
    """Tests for settings management."""

    def test_default_model_is_none(self, config: LastToKnowConfig) -> None:
        assert config.model is None

    def test_set_model(self, config: LastToKnowConfig) -> None:
        config.model = "azure/gpt-4.1"
        assert config.model == "azure/gpt-4.1"

    def test_default_sources(self, config: LastToKnowConfig) -> None:
        assert "pypi" in config.sources
        assert "github" in config.sources
        assert "hackernews" in config.sources

    def test_default_days(self, config: LastToKnowConfig) -> None:
        assert config.default_days == 7

    def test_save_and_reload_settings(self, config_dir: Path) -> None:
        # Save settings
        config1 = LastToKnowConfig(config_dir=config_dir)
        config1.model = "gpt-4o"
        config1.save_settings()

        # Reload in a new instance
        config2 = LastToKnowConfig(config_dir=config_dir)
        config2.load()
        assert config2.model == "gpt-4o"

    def test_corrupted_config_uses_defaults(self, config_dir: Path) -> None:
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "config.json").write_text("not valid json{{{")
        config = LastToKnowConfig(config_dir=config_dir)
        config.load()
        # Should fall back to defaults
        assert config.model is None
        assert "pypi" in config.sources


class TestTrackedItems:
    """Tests for tracked item management."""

    def test_empty_by_default(self, config: LastToKnowConfig) -> None:
        assert config.tracked_items == []

    def test_add_pypi_item(self, config: LastToKnowConfig) -> None:
        item = config.add_item("litellm", ItemType.PYPI, current_version="1.40.0")
        assert item.name == "litellm"
        assert item.item_type == ItemType.PYPI
        assert item.current_version == "1.40.0"
        assert len(config.tracked_items) == 1

    def test_add_github_item(self, config: LastToKnowConfig) -> None:
        item = config.add_item(
            "BerriAI/litellm",
            ItemType.GITHUB,
            source_url="https://github.com/BerriAI/litellm",
        )
        assert item.item_type == ItemType.GITHUB
        assert item.source_url == "https://github.com/BerriAI/litellm"

    def test_add_topic(self, config: LastToKnowConfig) -> None:
        item = config.add_item("AI agents", ItemType.TOPIC)
        assert item.item_type == ItemType.TOPIC

    def test_add_duplicate_raises(self, config: LastToKnowConfig) -> None:
        config.add_item("litellm", ItemType.PYPI)
        with pytest.raises(ValueError, match="Already tracking"):
            config.add_item("litellm", ItemType.PYPI)

    def test_same_name_different_type_allowed(self, config: LastToKnowConfig) -> None:
        config.add_item("litellm", ItemType.PYPI)
        config.add_item("litellm", ItemType.TOPIC)
        assert len(config.tracked_items) == 2

    def test_remove_item(self, config: LastToKnowConfig) -> None:
        config.add_item("litellm", ItemType.PYPI)
        config.add_item("click", ItemType.PYPI)
        assert config.remove_item("litellm") is True
        assert len(config.tracked_items) == 1
        assert config.tracked_items[0].name == "click"

    def test_remove_nonexistent_returns_false(self, config: LastToKnowConfig) -> None:
        assert config.remove_item("doesnt-exist") is False

    def test_get_item(self, config: LastToKnowConfig) -> None:
        config.add_item("litellm", ItemType.PYPI)
        item = config.get_item("litellm")
        assert item is not None
        assert item.name == "litellm"

    def test_get_item_not_found(self, config: LastToKnowConfig) -> None:
        assert config.get_item("nope") is None

    def test_update_last_checked(self, config: LastToKnowConfig) -> None:
        config.add_item("litellm", ItemType.PYPI)
        assert config.get_item("litellm") is not None
        assert config.get_item("litellm").last_checked is None  # type: ignore[union-attr]
        config.update_last_checked("litellm")
        assert config.get_item("litellm").last_checked is not None  # type: ignore[union-attr]

    def test_clear_all(self, config: LastToKnowConfig) -> None:
        config.add_item("litellm", ItemType.PYPI)
        config.add_item("click", ItemType.PYPI)
        count = config.clear_all()
        assert count == 2
        assert config.tracked_items == []

    def test_tracked_items_returns_copy(self, config: LastToKnowConfig) -> None:
        """Ensure the returned list is a copy, not a reference."""
        config.add_item("litellm", ItemType.PYPI)
        items = config.tracked_items
        items.clear()  # Modify the copy
        assert len(config.tracked_items) == 1  # Original unchanged


class TestPersistence:
    """Tests for save/load cycle."""

    def test_tracked_items_persist_across_instances(self, config_dir: Path) -> None:
        # Add items with first instance
        config1 = LastToKnowConfig(config_dir=config_dir)
        config1.add_item("litellm", ItemType.PYPI, current_version="1.40.0")
        config1.add_item("AI agents", ItemType.TOPIC)

        # Load with second instance
        config2 = LastToKnowConfig(config_dir=config_dir)
        config2.load()
        assert len(config2.tracked_items) == 2
        assert config2.tracked_items[0].name == "litellm"
        assert config2.tracked_items[0].current_version == "1.40.0"
        assert config2.tracked_items[1].name == "AI agents"

    def test_corrupted_tracked_file_starts_fresh(self, config_dir: Path) -> None:
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "tracked.json").write_text("[{broken json")
        config = LastToKnowConfig(config_dir=config_dir)
        config.load()
        assert config.tracked_items == []

    def test_tracked_file_is_valid_json(self, config: LastToKnowConfig) -> None:
        config.add_item("litellm", ItemType.PYPI)
        data = json.loads(config.tracked_file.read_text())
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["name"] == "litellm"
        assert data[0]["item_type"] == "pypi"

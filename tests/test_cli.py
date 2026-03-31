"""Tests for the FirstToKnow CLI commands."""

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from firsttoknow.cli import app
from firsttoknow.config import FirstToKnowConfig

runner = CliRunner()


def _make_config(tmp_path: Path) -> FirstToKnowConfig:
    """Create a config that uses a temp directory."""
    return FirstToKnowConfig(config_dir=tmp_path / "firsttoknow")


class TestTrack:
    """Tests for the track command."""

    def test_track_pypi_package(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        with patch("firsttoknow.cli._config", config):
            result = runner.invoke(app, ["track", "litellm"])
        assert result.exit_code == 0
        assert "litellm" in result.output
        assert "pypi" in result.output

    def test_track_github_repo(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        with patch("firsttoknow.cli._config", config):
            result = runner.invoke(app, ["track", "--github", "BerriAI/litellm"])
        assert result.exit_code == 0
        assert "BerriAI/litellm" in result.output
        assert "github" in result.output

    def test_track_topic(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        with patch("firsttoknow.cli._config", config):
            result = runner.invoke(app, ["track", "--topic", "AI agents"])
        assert result.exit_code == 0
        assert "AI agents" in result.output
        assert "topic" in result.output

    def test_track_duplicate(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        with patch("firsttoknow.cli._config", config):
            runner.invoke(app, ["track", "litellm"])
            result = runner.invoke(app, ["track", "litellm"])
        assert result.exit_code == 0
        assert "Already tracking" in result.output

    def test_track_with_version(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        with patch("firsttoknow.cli._config", config):
            result = runner.invoke(app, ["track", "litellm", "--version", "1.40.0"])
        assert result.exit_code == 0
        assert config.get_item("litellm") is not None
        item = config.get_item("litellm")
        assert item is not None
        assert item.current_version == "1.40.0"

    def test_track_npm_package(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        with patch("firsttoknow.cli._config", config):
            result = runner.invoke(app, ["track", "--npm", "express"])
        assert result.exit_code == 0
        assert "express" in result.output
        assert "npm" in result.output


class TestUntrack:
    """Tests for the untrack command."""

    def test_untrack_existing(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        with patch("firsttoknow.cli._config", config):
            runner.invoke(app, ["track", "litellm"])
            result = runner.invoke(app, ["untrack", "litellm"])
        assert result.exit_code == 0
        assert "Stopped tracking" in result.output

    def test_untrack_nonexistent(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        with patch("firsttoknow.cli._config", config):
            result = runner.invoke(app, ["untrack", "doesnt-exist"])
        assert result.exit_code == 0
        assert "Not tracking" in result.output


class TestList:
    """Tests for the list command."""

    def test_list_empty(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        with patch("firsttoknow.cli._config", config):
            result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "No items tracked" in result.output

    def test_list_with_items(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        with patch("firsttoknow.cli._config", config):
            runner.invoke(app, ["track", "litellm"])
            runner.invoke(app, ["track", "--topic", "AI agents"])
            result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "litellm" in result.output
        assert "AI agents" in result.output


class TestConfig:
    """Tests for config subcommands."""

    def test_config_model_set(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        with patch("firsttoknow.cli._config", config):
            result = runner.invoke(app, ["config", "model", "gpt-4o"])
        assert result.exit_code == 0
        assert "gpt-4o" in result.output
        assert config.model == "gpt-4o"

    def test_config_show(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        with patch("firsttoknow.cli._config", config):
            result = runner.invoke(app, ["config", "show"])
        assert result.exit_code == 0
        assert "FirstToKnow" in result.output
        assert "(not set)" in result.output

    def test_config_show_with_model(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        with patch("firsttoknow.cli._config", config):
            runner.invoke(app, ["config", "model", "azure/gpt-4.1"])
            result = runner.invoke(app, ["config", "show"])
        assert result.exit_code == 0
        assert "azure/gpt-4.1" in result.output


class TestStatus:
    """Tests for the status command."""

    def test_status_empty(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        with patch("firsttoknow.cli._config", config):
            result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "FirstToKnow" in result.output
        assert "No items tracked" in result.output


class TestBrief:
    """Tests for the brief command."""

    def test_brief_no_model(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        with patch("firsttoknow.cli._config", config), patch.dict("os.environ", {}, clear=True):
            result = runner.invoke(app, ["brief"])
        assert result.exit_code == 1
        assert "No model configured" in result.output

    def test_brief_with_model_flag(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        with (
            patch("firsttoknow.cli._config", config),
            patch("firsttoknow.agents.agent.run_agent", return_value="Test briefing response"),
        ):
            result = runner.invoke(app, ["brief", "--model", "gpt-4o"])
        assert result.exit_code == 0
        assert "Test briefing response" in result.output


class TestScan:
    """Tests for the scan command."""

    def test_scan_pyproject(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        project = tmp_path / "project"
        project.mkdir()
        toml = project / "pyproject.toml"
        toml.write_text('[project]\ndependencies = [\n    "litellm>=1.40.0",\n    "rich>=13.0.0",\n]\n')
        with patch("firsttoknow.cli._config", config):
            result = runner.invoke(app, ["scan", str(project)])
        assert result.exit_code == 0
        assert "litellm" in result.output
        assert "rich" in result.output
        assert config.get_item("litellm") is not None
        assert config.get_item("rich") is not None

    def test_scan_requirements(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        project = tmp_path / "project"
        project.mkdir()
        req = project / "requirements.txt"
        req.write_text("httpx>=0.27.0\nclick>=8.0\n")
        with patch("firsttoknow.cli._config", config):
            result = runner.invoke(app, ["scan", str(project)])
        assert result.exit_code == 0
        assert "httpx" in result.output
        assert "click" in result.output

    def test_scan_skips_duplicates(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        project = tmp_path / "project"
        project.mkdir()
        toml = project / "pyproject.toml"
        toml.write_text('[project]\ndependencies = ["litellm>=1.40.0"]\n')
        with patch("firsttoknow.cli._config", config):
            # Track first, then scan
            runner.invoke(app, ["track", "litellm"])
            result = runner.invoke(app, ["scan", str(project)])
        assert result.exit_code == 0
        assert "already tracked" in result.output

    def test_scan_empty_dir(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        project = tmp_path / "empty"
        project.mkdir()
        with patch("firsttoknow.cli._config", config):
            result = runner.invoke(app, ["scan", str(project)])
        assert result.exit_code == 0
        assert "No dependencies found" in result.output

    def test_scan_records_version(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        project = tmp_path / "project"
        project.mkdir()
        toml = project / "pyproject.toml"
        toml.write_text('[project]\ndependencies = ["litellm>=1.40.0"]\n')
        with patch("firsttoknow.cli._config", config):
            runner.invoke(app, ["scan", str(project)])
        item = config.get_item("litellm")
        assert item is not None
        assert item.current_version == "1.40.0"

    def test_scan_package_json(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        project = tmp_path / "project"
        project.mkdir()
        pkg = project / "package.json"
        pkg.write_text('{"dependencies": {"express": "^4.18.2", "react": "^18.2.0"}}')
        with patch("firsttoknow.cli._config", config):
            result = runner.invoke(app, ["scan", str(project)])
        assert result.exit_code == 0
        assert "express" in result.output
        assert "react" in result.output
        item = config.get_item("express")
        assert item is not None
        assert item.item_type.value == "npm"
        assert item.current_version == "4.18.2"

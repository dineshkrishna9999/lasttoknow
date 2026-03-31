"""Tests for the FirstToKnow renderer."""

from __future__ import annotations

from io import StringIO
from unittest.mock import MagicMock, patch

from rich.console import Console

from firsttoknow.renderer import _TOOL_STATUS, render_banner, render_briefing, render_briefing_spinner


class TestRenderBriefing:
    """Tests for the briefing renderer with markdown support."""

    def test_renders_markdown_headings(self) -> None:
        """Markdown headings should be rendered (not shown as raw ##)."""
        buf = StringIO()
        test_console = Console(file=buf, force_terminal=True, width=80)
        with patch("firsttoknow.renderer.console", test_console):
            render_briefing("## Package Updates\n\nSome content here.", model="gpt-4o")
        output = buf.getvalue()
        # Raw ## should not appear — Rich Markdown renders headings as styled text
        assert "##" not in output
        assert "Package Updates" in output

    def test_renders_bold_text(self) -> None:
        """Bold markdown should render without raw ** markers."""
        buf = StringIO()
        test_console = Console(file=buf, force_terminal=True, width=80)
        with patch("firsttoknow.renderer.console", test_console):
            render_briefing("**litellm 1.41.0** — New release", model="gpt-4o")
        output = buf.getvalue()
        assert "**" not in output
        assert "litellm 1.41.0" in output

    def test_renders_bullet_lists(self) -> None:
        """Bullet lists should render as proper bullets."""
        buf = StringIO()
        test_console = Console(file=buf, force_terminal=True, width=80)
        with patch("firsttoknow.renderer.console", test_console):
            render_briefing("- Item one\n- Item two\n- Item three", model="gpt-4o")
        output = buf.getvalue()
        # Rich renders bullets as • instead of -
        assert "Item one" in output
        assert "Item two" in output

    def test_panel_has_title_and_subtitle(self) -> None:
        """The briefing panel should have the correct title and model subtitle."""
        buf = StringIO()
        test_console = Console(file=buf, force_terminal=True, width=80)
        with patch("firsttoknow.renderer.console", test_console):
            render_briefing("Hello world", model="azure/gpt-4.1")
        output = buf.getvalue()
        assert "FirstToKnow Briefing" in output
        assert "azure/gpt-4.1" in output

    def test_falls_back_on_markdown_error(self) -> None:
        """If Markdown rendering fails, should fall back to raw text."""
        buf = StringIO()
        test_console = Console(file=buf, force_terminal=True, width=80)
        with (
            patch("firsttoknow.renderer.console", test_console),
            patch("firsttoknow.renderer.Markdown", side_effect=Exception("unicode error")),
        ):
            render_briefing("## Hello\n\nFallback content", model="gpt-4o")
        output = buf.getvalue()
        # Should still render the content (as raw text) without crashing
        assert "Fallback content" in output
        assert "FirstToKnow Briefing" in output


class TestRenderBanner:
    """Tests for the ASCII logo banner."""

    def test_banner_shows_version(self) -> None:
        """Banner should display the version string."""
        buf = StringIO()
        test_console = Console(file=buf, force_terminal=True, width=80, highlight=False)
        with patch("firsttoknow.renderer.console", test_console):
            render_banner("0.4.0")
        output = buf.getvalue()
        assert "0.4.0" in output

    def test_banner_shows_tagline(self) -> None:
        """Banner should display the tagline."""
        buf = StringIO()
        test_console = Console(file=buf, force_terminal=True, width=80)
        with patch("firsttoknow.renderer.console", test_console):
            render_banner("0.4.0")
        output = buf.getvalue()
        assert "Never miss what matters" in output

    def test_banner_contains_ascii_art(self) -> None:
        """Banner should contain the ASCII art logo."""
        buf = StringIO()
        test_console = Console(file=buf, force_terminal=True, width=80)
        with patch("firsttoknow.renderer.console", test_console):
            render_banner("0.4.0")
        output = buf.getvalue()
        # Box-drawing characters from the banner
        assert "╔" in output


class TestRenderBriefingSpinner:
    """Tests for the briefing spinner context manager."""

    def test_yields_callable(self) -> None:
        """The context manager should yield a callable."""
        with patch("firsttoknow.renderer.console") as mock_console:
            mock_console.status.return_value.__enter__ = MagicMock()
            mock_console.status.return_value.__exit__ = MagicMock(return_value=False)
            with render_briefing_spinner() as on_tool_call:
                assert callable(on_tool_call)

    def test_callback_updates_status(self) -> None:
        """Calling the callback should update the spinner status text."""
        mock_status = MagicMock()
        with patch("firsttoknow.renderer.console") as mock_console:
            mock_console.status.return_value.__enter__ = MagicMock(return_value=mock_status)
            mock_console.status.return_value.__exit__ = MagicMock(return_value=False)
            with render_briefing_spinner() as on_tool_call:
                on_tool_call("fetch_pypi_releases")
                mock_status.update.assert_called_with("[bold green]Checking PyPI...")

    def test_callback_handles_unknown_tool(self) -> None:
        """Unknown tool names should show a generic message."""
        mock_status = MagicMock()
        with patch("firsttoknow.renderer.console") as mock_console:
            mock_console.status.return_value.__enter__ = MagicMock(return_value=mock_status)
            mock_console.status.return_value.__exit__ = MagicMock(return_value=False)
            with render_briefing_spinner() as on_tool_call:
                on_tool_call("some_unknown_tool")
                mock_status.update.assert_called_with("[bold green]Running some_unknown_tool...")

    def test_all_tools_have_status_labels(self) -> None:
        """Every known tool should have a human-friendly status label."""
        expected_tools = {
            "fetch_pypi_releases",
            "fetch_npm_releases",
            "check_vulnerabilities",
            "check_license_change",
            "fetch_github_trending",
            "fetch_hackernews_top",
            "fetch_devto_articles",
            "fetch_reddit_posts",
        }
        assert set(_TOOL_STATUS.keys()) == expected_tools

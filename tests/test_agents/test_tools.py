"""Tests for the DevPulse agent tool functions.

Each tool calls an external API. We mock httpx.get so tests are
fast, offline, and deterministic.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from devpulse.agents._tools import DevPulseTools


def _mock_response(data: dict | list) -> MagicMock:  # type: ignore[type-arg]
    """Create a mock httpx.Response with JSON data."""
    mock = MagicMock()
    mock.json.return_value = data
    mock.raise_for_status.return_value = None
    return mock


class TestFetchPypiReleases:
    """Tests for the PyPI release fetcher."""

    def setup_method(self) -> None:
        self.tools = DevPulseTools()

    def test_successful_fetch(self) -> None:
        mock_data = {
            "info": {
                "version": "1.41.0",
                "summary": "Call 100+ LLM APIs",
                "home_page": "https://github.com/BerriAI/litellm",
                "project_urls": {"Homepage": "https://github.com/BerriAI/litellm"},
                "requires_python": ">=3.8",
            },
            "releases": {"1.41.0": [], "1.40.0": [], "1.39.0": []},
        }
        with patch("devpulse.agents._tools.httpx.get", return_value=_mock_response(mock_data)):
            result = json.loads(self.tools.fetch_pypi_releases("litellm"))

        assert result["package"] == "litellm"
        assert result["latest_version"] == "1.41.0"
        assert result["summary"] == "Call 100+ LLM APIs"
        assert "1.41.0" in result["recent_versions"]

    def test_returns_error_on_failure(self) -> None:
        with patch("devpulse.agents._tools.httpx.get", side_effect=Exception("Connection failed")):
            result = json.loads(self.tools.fetch_pypi_releases("nonexistent-pkg"))

        assert "error" in result
        assert "Connection failed" in result["error"]

    def test_limits_recent_versions(self) -> None:
        releases = {f"1.{i}.0": [] for i in range(20)}
        mock_data = {
            "info": {
                "version": "1.19.0",
                "summary": "test",
                "home_page": "",
                "project_urls": {},
                "requires_python": "",
            },
            "releases": releases,
        }
        with patch("devpulse.agents._tools.httpx.get", return_value=_mock_response(mock_data)):
            result = json.loads(self.tools.fetch_pypi_releases("test-pkg"))

        assert len(result["recent_versions"]) == 5


class TestFetchGithubTrending:
    """Tests for the GitHub trending fetcher."""

    def setup_method(self) -> None:
        self.tools = DevPulseTools()

    def test_successful_fetch(self) -> None:
        mock_data = {
            "items": [
                {
                    "full_name": "cool/repo",
                    "description": "A cool repo",
                    "stargazers_count": 1500,
                    "html_url": "https://github.com/cool/repo",
                    "language": "Python",
                },
            ],
        }
        with patch("devpulse.agents._tools.httpx.get", return_value=_mock_response(mock_data)):
            result = json.loads(self.tools.fetch_github_trending("python", "weekly"))

        assert result["language"] == "python"
        assert result["since"] == "weekly"
        assert len(result["trending"]) == 1
        assert result["trending"][0]["name"] == "cool/repo"
        assert result["trending"][0]["stars"] == 1500

    def test_daily_since(self) -> None:
        mock_data = {"items": []}
        with patch("devpulse.agents._tools.httpx.get", return_value=_mock_response(mock_data)) as mock_get:
            self.tools.fetch_github_trending("python", "daily")

        call_kwargs = mock_get.call_args
        query = call_kwargs.kwargs.get("params", call_kwargs[1].get("params", {}))
        assert "created:>" in query["q"]

    def test_monthly_since(self) -> None:
        mock_data = {"items": []}
        with patch("devpulse.agents._tools.httpx.get", return_value=_mock_response(mock_data)) as mock_get:
            self.tools.fetch_github_trending("javascript", "monthly")

        call_kwargs = mock_get.call_args
        query = call_kwargs.kwargs.get("params", call_kwargs[1].get("params", {}))
        assert "javascript" in query["q"]

    def test_returns_error_on_failure(self) -> None:
        with patch("devpulse.agents._tools.httpx.get", side_effect=Exception("Rate limited")):
            result = json.loads(self.tools.fetch_github_trending())

        assert "error" in result

    def test_limits_to_ten_repos(self) -> None:
        items = [
            {
                "full_name": f"user/repo-{i}",
                "description": f"Repo {i}",
                "stargazers_count": 100 - i,
                "html_url": f"https://github.com/user/repo-{i}",
                "language": "Python",
            }
            for i in range(15)
        ]
        mock_data = {"items": items}
        with patch("devpulse.agents._tools.httpx.get", return_value=_mock_response(mock_data)):
            result = json.loads(self.tools.fetch_github_trending())

        assert len(result["trending"]) == 10


class TestFetchHackernewsTop:
    """Tests for the Hacker News fetcher."""

    def setup_method(self) -> None:
        self.tools = DevPulseTools()

    def test_successful_fetch(self) -> None:
        mock_data = {
            "hits": [
                {
                    "title": "Show HN: Cool AI Tool",
                    "url": "https://example.com",
                    "points": 342,
                    "num_comments": 128,
                    "objectID": "12345",
                },
            ],
        }
        with patch("devpulse.agents._tools.httpx.get", return_value=_mock_response(mock_data)):
            result = json.loads(self.tools.fetch_hackernews_top("AI"))

        assert result["query"] == "AI"
        assert len(result["stories"]) == 1
        assert result["stories"][0]["title"] == "Show HN: Cool AI Tool"
        assert result["stories"][0]["points"] == 342

    def test_missing_url_uses_hn_link(self) -> None:
        mock_data = {
            "hits": [
                {
                    "title": "Ask HN: Best AI tools?",
                    "points": 50,
                    "num_comments": 30,
                    "objectID": "99999",
                },
            ],
        }
        with patch("devpulse.agents._tools.httpx.get", return_value=_mock_response(mock_data)):
            result = json.loads(self.tools.fetch_hackernews_top("AI"))

        assert "news.ycombinator.com" in result["stories"][0]["url"]
        assert "99999" in result["stories"][0]["url"]

    def test_custom_limit(self) -> None:
        mock_data = {"hits": []}
        with patch("devpulse.agents._tools.httpx.get", return_value=_mock_response(mock_data)) as mock_get:
            self.tools.fetch_hackernews_top("python", limit=5)

        call_kwargs = mock_get.call_args
        params = call_kwargs.kwargs.get("params", call_kwargs[1].get("params", {}))
        assert params["hitsPerPage"] == 5

    def test_returns_error_on_failure(self) -> None:
        with patch("devpulse.agents._tools.httpx.get", side_effect=Exception("Timeout")):
            result = json.loads(self.tools.fetch_hackernews_top())

        assert "error" in result
        assert "Timeout" in result["error"]


class TestGetTools:
    """Tests for the get_tools method."""

    def test_returns_three_tools(self) -> None:
        tools = DevPulseTools()
        function_tools = tools.get_tools()
        assert len(function_tools) == 3

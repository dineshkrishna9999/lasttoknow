"""Tool functions for the FirstToKnow agent.

Each method fetches data from an external API and returns a JSON string.
The agent reads the JSON, reasons about it, and builds its response.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta

import httpx
from google.adk.tools.function_tool import FunctionTool

logger = logging.getLogger(__name__)

_TIMEOUT = 10


class FirstToKnowTools:
    """Tools the FirstToKnow agent can call to fetch real-time data."""

    def fetch_pypi_releases(self, package_name: str) -> str:
        """Fetch the latest release info for a PyPI package.

        Args:
            package_name: Name of the package on PyPI (e.g. "litellm", "google-adk").

        Returns:
            JSON string with version, summary, and recent versions.
        """
        url = f"https://pypi.org/pypi/{package_name}/json"
        try:
            resp = httpx.get(url, timeout=_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            info = data["info"]
            recent_versions = sorted(data["releases"].keys(), reverse=True)[:5]
            return json.dumps(
                {
                    "package": package_name,
                    "latest_version": info["version"],
                    "summary": info["summary"],
                    "home_page": info.get("home_page") or info.get("project_url", ""),
                    "project_urls": info.get("project_urls", {}),
                    "requires_python": info.get("requires_python", ""),
                    "recent_versions": recent_versions,
                }
            )
        except Exception as exc:
            logger.warning("PyPI fetch failed for %s: %s", package_name, exc)
            return json.dumps({"error": f"Failed to fetch {package_name}: {exc}"})

    def fetch_npm_releases(self, package_name: str) -> str:
        """Fetch the latest release info for an npm package.

        Args:
            package_name: Name of the package on npm (e.g. "express", "react", "@babel/core").

        Returns:
            JSON string with version, summary, and recent versions.
        """
        url = f"https://registry.npmjs.org/{package_name}"
        try:
            resp = httpx.get(url, timeout=_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            dist_tags = data.get("dist-tags", {})
            latest = dist_tags.get("latest", "")
            versions = data.get("versions", {})
            recent_versions = sorted(versions.keys(), reverse=True)[:5]
            latest_info = versions.get(latest, {}) if latest else {}
            repo = latest_info.get("repository", {})
            repo_url = ""
            if isinstance(repo, dict):
                repo_url = repo.get("url", "")
            elif isinstance(repo, str):
                repo_url = repo
            return json.dumps(
                {
                    "package": package_name,
                    "latest_version": latest,
                    "summary": latest_info.get("description", ""),
                    "home_page": latest_info.get("homepage", "") or repo_url,
                    "project_urls": {"repository": repo_url} if repo_url else {},
                    "recent_versions": recent_versions,
                }
            )
        except Exception as exc:
            logger.warning("npm fetch failed for %s: %s", package_name, exc)
            return json.dumps({"error": f"Failed to fetch {package_name}: {exc}"})

    def fetch_github_trending(self, language: str = "python", since: str = "weekly") -> str:
        """Fetch trending repositories from GitHub.

        Args:
            language: Programming language to filter by (e.g. "python", "javascript").
            since: Time range — "daily", "weekly", or "monthly".

        Returns:
            JSON string with a list of trending repos (name, description, stars, url).
        """
        today = datetime.now()
        if since == "daily":
            date_str = today.strftime("%Y-%m-%d")
        elif since == "monthly":
            date_str = f"{today.year}-{today.month:02d}-01"
        else:
            week_ago = today - timedelta(days=7)
            date_str = week_ago.strftime("%Y-%m-%d")

        params: dict[str, str | int] = {
            "q": f"language:{language} created:>{date_str}",
            "sort": "stars",
            "order": "desc",
            "per_page": 10,
        }
        try:
            resp = httpx.get("https://api.github.com/search/repositories", params=params, timeout=_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            repos = [
                {
                    "name": repo["full_name"],
                    "description": repo.get("description", ""),
                    "stars": repo["stargazers_count"],
                    "url": repo["html_url"],
                    "language": repo.get("language", ""),
                }
                for repo in data.get("items", [])[:10]
            ]
            return json.dumps({"trending": repos, "language": language, "since": since})
        except Exception as exc:
            logger.warning("GitHub trending fetch failed: %s", exc)
            return json.dumps({"error": f"Failed to fetch trending: {exc}"})

    def fetch_hackernews_top(self, query: str = "AI", limit: int = 10) -> str:
        """Fetch top Hacker News stories matching a query.

        Args:
            query: Search term to filter stories (e.g. "AI", "python", "LLM").
            limit: Maximum number of stories to return (default 10).

        Returns:
            JSON string with a list of stories (title, url, points, comments).
        """
        params: dict[str, str | int] = {
            "query": query,
            "tags": "story",
            "hitsPerPage": limit,
        }
        try:
            resp = httpx.get("https://hn.algolia.com/api/v1/search", params=params, timeout=_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            stories = [
                {
                    "title": hit["title"],
                    "url": hit.get("url", f"https://news.ycombinator.com/item?id={hit['objectID']}"),
                    "points": hit.get("points", 0),
                    "comments": hit.get("num_comments", 0),
                }
                for hit in data.get("hits", [])
            ]
            return json.dumps({"stories": stories, "query": query})
        except Exception as exc:
            logger.warning("HN fetch failed for query '%s': %s", query, exc)
            return json.dumps({"error": f"Failed to fetch HN: {exc}"})

    def fetch_devto_articles(self, tag: str = "python", limit: int = 10) -> str:
        """Fetch recent popular articles from Dev.to by tag.

        Args:
            tag: Tag to filter by (e.g. "python", "ai", "machinelearning", "javascript").
            limit: Maximum number of articles to return (default 10).

        Returns:
            JSON string with a list of articles (title, url, reactions, comments, published).
        """
        params: dict[str, str | int] = {
            "tag": tag,
            "top": 7,
            "per_page": limit,
        }
        try:
            resp = httpx.get("https://dev.to/api/articles", params=params, timeout=_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            articles = [
                {
                    "title": a["title"],
                    "url": a["url"],
                    "reactions": a.get("positive_reactions_count", 0),
                    "comments": a.get("comments_count", 0),
                    "published": a.get("readable_publish_date", ""),
                    "author": a.get("user", {}).get("username", ""),
                }
                for a in data[:limit]
            ]
            return json.dumps({"articles": articles, "tag": tag})
        except Exception as exc:
            logger.warning("Dev.to fetch failed for tag '%s': %s", tag, exc)
            return json.dumps({"error": f"Failed to fetch Dev.to: {exc}"})

    def fetch_reddit_posts(self, subreddit: str = "programming", limit: int = 10) -> str:
        """Fetch top posts from a subreddit.

        Args:
            subreddit: Subreddit name (e.g. "programming", "Python", "MachineLearning").
            limit: Maximum number of posts to return (default 10).

        Returns:
            JSON string with a list of posts (title, url, score, comments).
        """
        url = f"https://www.reddit.com/r/{subreddit}/hot.json"
        headers = {"User-Agent": "FirstToKnow/0.1"}
        try:
            resp = httpx.get(url, headers=headers, params={"limit": limit}, timeout=_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            posts = [
                {
                    "title": p["data"]["title"],
                    "url": p["data"].get("url", ""),
                    "score": p["data"].get("score", 0),
                    "comments": p["data"].get("num_comments", 0),
                    "permalink": f"https://reddit.com{p['data']['permalink']}",
                }
                for p in data.get("data", {}).get("children", [])
                if not p["data"].get("stickied", False)
            ]
            return json.dumps({"posts": posts[:limit], "subreddit": subreddit})
        except Exception as exc:
            logger.warning("Reddit fetch failed for r/%s: %s", subreddit, exc)
            return json.dumps({"error": f"Failed to fetch Reddit: {exc}"})

    def get_tools(self) -> list[FunctionTool]:
        """Return all tools as FunctionTool instances for ADK."""
        return [
            FunctionTool(self.fetch_pypi_releases),
            FunctionTool(self.fetch_npm_releases),
            FunctionTool(self.fetch_github_trending),
            FunctionTool(self.fetch_hackernews_top),
            FunctionTool(self.fetch_devto_articles),
            FunctionTool(self.fetch_reddit_posts),
        ]

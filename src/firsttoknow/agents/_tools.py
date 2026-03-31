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


def _error_response(context: str, exc: Exception) -> str:
    """Build a standard JSON error response and log the failure."""
    logger.warning("%s: %s", context, exc)
    return json.dumps({"error": f"{context}: {exc}"})


def _extract_pypi_license(info: dict[str, object]) -> str:
    """Extract the best license string from PyPI package info.

    Tries license_expression (SPDX), then license, then classifiers.
    """
    # Prefer license_expression (newest, SPDX-formatted)
    expr = info.get("license_expression")
    if expr and isinstance(expr, str) and expr.strip():
        return expr.strip()

    # Fall back to license field
    raw = info.get("license")
    if raw and isinstance(raw, str) and raw.strip():
        return raw.strip()

    # Fall back to classifiers
    classifiers = info.get("classifiers", [])
    if isinstance(classifiers, list):
        for c in classifiers:
            if isinstance(c, str) and c.startswith("License ::"):
                # e.g. "License :: OSI Approved :: MIT License" → "MIT License"
                parts = c.split(" :: ")
                return parts[-1] if len(parts) >= 2 else c

    return "UNKNOWN"


def _extract_npm_license(version_data: dict[str, object]) -> str:
    """Extract the license string from an npm version's metadata.

    Handles both string and {"type": "MIT"} formats.
    """
    raw = version_data.get("license")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    if isinstance(raw, dict):
        license_type = raw.get("type")
        if isinstance(license_type, str) and license_type.strip():
            return license_type.strip()

    # Legacy: some old packages use "licenses" array
    licenses = version_data.get("licenses")
    if isinstance(licenses, list) and licenses:
        first = licenses[0]
        if isinstance(first, dict):
            license_type = first.get("type")
            if isinstance(license_type, str):
                return license_type.strip()
        if isinstance(first, str):
            return first.strip()

    return "UNKNOWN"


def _get_previous_version(versions: list[str], latest: str) -> str | None:
    """Find the version immediately before the latest in a sorted version list.

    Args:
        versions: List of version strings (sorted descending).
        latest: The current latest version string.

    Returns:
        The previous version string, or None if there's only one version.
    """
    try:
        idx = versions.index(latest)
        if idx + 1 < len(versions):
            return versions[idx + 1]
    except ValueError:
        # latest not in list; return second item if available
        if len(versions) >= 2:
            return versions[1]
    return None


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
            return _error_response(f"PyPI fetch failed for {package_name}", exc)

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
            return _error_response(f"npm fetch failed for {package_name}", exc)

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
            return _error_response("GitHub trending fetch failed", exc)

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
            return _error_response(f"HN fetch failed for query '{query}'", exc)

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
            return _error_response(f"Dev.to fetch failed for tag '{tag}'", exc)

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
            return _error_response(f"Reddit fetch failed for r/{subreddit}", exc)

    def check_vulnerabilities(self, package_name: str, ecosystem: str = "pypi") -> str:
        """Check a package for known security vulnerabilities via OSV.dev.

        Args:
            package_name: Name of the package (e.g. "litellm", "express").
            ecosystem: Package ecosystem — "pypi" or "npm".

        Returns:
            JSON string with vulnerability count and details, or an error.
        """
        # OSV expects exact ecosystem strings
        ecosystem_map = {"pypi": "PyPI", "npm": "npm"}
        osv_ecosystem = ecosystem_map.get(ecosystem.lower(), ecosystem)

        try:
            resp = httpx.post(
                "https://api.osv.dev/v1/query",
                json={"package": {"name": package_name, "ecosystem": osv_ecosystem}},
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            raw_vulns = data.get("vulns", [])

            vulns = []
            for v in raw_vulns:
                # Extract best ID: prefer CVE alias, fall back to OSV id
                vuln_id = v.get("id", "")
                aliases = v.get("aliases", [])
                cve_id = next((a for a in aliases if a.startswith("CVE-")), None)
                display_id = cve_id or vuln_id

                # Extract severity from CVSS score
                severity_list = v.get("severity", [])
                score = ""
                severity_label = "UNKNOWN"
                if severity_list:
                    score = severity_list[0].get("score", "")
                    try:
                        score_float = float(score)
                        if score_float >= 9.0:
                            severity_label = "CRITICAL"
                        elif score_float >= 7.0:
                            severity_label = "HIGH"
                        elif score_float >= 4.0:
                            severity_label = "MEDIUM"
                        else:
                            severity_label = "LOW"
                    except (ValueError, TypeError):
                        pass

                # Extract reference URL
                refs = v.get("references", [])
                url = f"https://osv.dev/vulnerability/{vuln_id}"
                for ref in refs:
                    if ref.get("type") == "ADVISORY":
                        url = ref.get("url", url)
                        break

                vulns.append(
                    {
                        "id": display_id,
                        "summary": v.get("summary", ""),
                        "severity": severity_label,
                        "score": score,
                        "url": url,
                    }
                )

            return json.dumps(
                {
                    "package": package_name,
                    "ecosystem": osv_ecosystem,
                    "vulnerability_count": len(vulns),
                    "vulnerabilities": vulns,
                }
            )
        except Exception as exc:
            return _error_response(f"OSV fetch failed for {package_name} ({ecosystem})", exc)

    def check_license_change(self, package_name: str, ecosystem: str = "pypi") -> str:
        """Check if a package's license has changed between its latest and previous version.

        Args:
            package_name: Name of the package (e.g. "redis", "express").
            ecosystem: Package ecosystem — "pypi" or "npm".

        Returns:
            JSON string with license info for latest and previous versions,
            and whether the license changed.
        """
        ecosystem_lower = ecosystem.lower()
        try:
            if ecosystem_lower == "npm":
                return self._check_npm_license(package_name)
            return self._check_pypi_license(package_name)
        except Exception as exc:
            return _error_response(f"License check failed for {package_name} ({ecosystem})", exc)

    def _check_pypi_license(self, package_name: str) -> str:
        """Check license change for a PyPI package."""
        # Get version list
        resp = httpx.get(f"https://pypi.org/pypi/{package_name}/json", timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        versions = sorted(data.get("releases", {}).keys(), reverse=True)
        latest = data["info"]["version"]
        previous = _get_previous_version(versions, latest)

        latest_license = _extract_pypi_license(data["info"])

        if not previous:
            return json.dumps(
                {
                    "package": package_name,
                    "ecosystem": "PyPI",
                    "latest_version": latest,
                    "latest_license": latest_license,
                    "previous_version": None,
                    "previous_license": None,
                    "license_changed": False,
                }
            )

        # Fetch previous version metadata
        prev_resp = httpx.get(f"https://pypi.org/pypi/{package_name}/{previous}/json", timeout=_TIMEOUT)
        prev_resp.raise_for_status()
        prev_data = prev_resp.json()
        previous_license = _extract_pypi_license(prev_data["info"])

        changed = (
            latest_license.lower() != previous_license.lower()
            and latest_license != "UNKNOWN"
            and previous_license != "UNKNOWN"
        )

        return json.dumps(
            {
                "package": package_name,
                "ecosystem": "PyPI",
                "latest_version": latest,
                "latest_license": latest_license,
                "previous_version": previous,
                "previous_license": previous_license,
                "license_changed": changed,
            }
        )

    def _check_npm_license(self, package_name: str) -> str:
        """Check license change for an npm package."""
        resp = httpx.get(f"https://registry.npmjs.org/{package_name}", timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        dist_tags = data.get("dist-tags", {})
        latest = dist_tags.get("latest", "")
        versions_data = data.get("versions", {})
        versions = sorted(versions_data.keys(), reverse=True)
        previous = _get_previous_version(versions, latest)

        latest_license = _extract_npm_license(versions_data.get(latest, {}))

        if not previous:
            return json.dumps(
                {
                    "package": package_name,
                    "ecosystem": "npm",
                    "latest_version": latest,
                    "latest_license": latest_license,
                    "previous_version": None,
                    "previous_license": None,
                    "license_changed": False,
                }
            )

        previous_license = _extract_npm_license(versions_data.get(previous, {}))

        changed = (
            latest_license.lower() != previous_license.lower()
            and latest_license != "UNKNOWN"
            and previous_license != "UNKNOWN"
        )

        return json.dumps(
            {
                "package": package_name,
                "ecosystem": "npm",
                "latest_version": latest,
                "latest_license": latest_license,
                "previous_version": previous,
                "previous_license": previous_license,
                "license_changed": changed,
            }
        )

    def get_tools(self) -> list[FunctionTool]:
        """Return all tools as FunctionTool instances for ADK."""
        return [
            FunctionTool(self.fetch_pypi_releases),
            FunctionTool(self.fetch_npm_releases),
            FunctionTool(self.check_vulnerabilities),
            FunctionTool(self.check_license_change),
            FunctionTool(self.fetch_github_trending),
            FunctionTool(self.fetch_hackernews_top),
            FunctionTool(self.fetch_devto_articles),
            FunctionTool(self.fetch_reddit_posts),
        ]

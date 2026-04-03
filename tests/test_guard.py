"""Tests for the guard module.

Testing strategy:
────────────────
We mock ALL external calls (git subprocess, HTTP to OSV/PyPI/npm).
Why? Because:
1. Tests must be fast (no network = instant)
2. Tests must be reliable (no "OSV is down" flaking)
3. Tests must be deterministic (same input = same output, always)

We test the LOGIC: "given these deps changed and OSV returns these CVEs,
does the guard produce the right findings?"
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

if TYPE_CHECKING:
    from pathlib import Path

from firsttoknow.guard import (
    _extract_fix_version,
    check_license_change,
    check_vulnerabilities,
    find_new_deps,
    get_changed_dep_files,
    run_guard,
)
from firsttoknow.models import GuardFinding, GuardReport, Severity
from firsttoknow.scanner import ScannedDep

# ──────────────────────────────────────────────
# Model tests
# ──────────────────────────────────────────────


class TestGuardReport:
    """Test the GuardReport data model."""

    def test_empty_report_passes(self) -> None:
        """An empty report (no findings) should pass."""
        report = GuardReport()
        assert report.passed is True
        assert report.critical_count == 0
        assert report.warning_count == 0
        assert report.info_count == 0

    def test_info_only_passes(self) -> None:
        """A report with only INFO findings should pass."""
        report = GuardReport(
            findings=[
                GuardFinding(package="requests", ecosystem="pypi", severity=Severity.INFO, title="clean"),
            ]
        )
        assert report.passed is True
        assert report.info_count == 1

    def test_warning_only_passes(self) -> None:
        """Warnings alone don't fail the guard — they're advisory."""
        report = GuardReport(
            findings=[
                GuardFinding(package="requests", ecosystem="pypi", severity=Severity.WARNING, title="heads up"),
            ]
        )
        assert report.passed is True
        assert report.warning_count == 1

    def test_critical_fails(self) -> None:
        """Any CRITICAL finding should fail the guard."""
        report = GuardReport(
            findings=[
                GuardFinding(package="requests", ecosystem="pypi", severity=Severity.CRITICAL, title="CVE found"),
            ]
        )
        assert report.passed is False
        assert report.critical_count == 1

    def test_mixed_findings(self) -> None:
        """A mix of severities — one critical means failure."""
        report = GuardReport(
            findings=[
                GuardFinding(package="a", ecosystem="pypi", severity=Severity.INFO, title="ok"),
                GuardFinding(package="b", ecosystem="pypi", severity=Severity.WARNING, title="hmm"),
                GuardFinding(package="c", ecosystem="pypi", severity=Severity.CRITICAL, title="bad"),
                GuardFinding(package="d", ecosystem="pypi", severity=Severity.INFO, title="ok"),
            ]
        )
        assert report.passed is False
        assert report.critical_count == 1
        assert report.warning_count == 1
        assert report.info_count == 2


# ──────────────────────────────────────────────
# Git diff parsing tests
# ──────────────────────────────────────────────


class TestGetChangedDepFiles:
    """Test detection of changed dependency files."""

    @patch("firsttoknow.guard.subprocess.run")
    def test_detects_pyproject_change(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Should detect when pyproject.toml is in the diff."""
        # First call: git diff --name-only HEAD
        # Second call: git diff --name-only --cached
        mock_run.side_effect = [
            MagicMock(stdout="src/main.py\npyproject.toml\nREADME.md\n", returncode=0),
            MagicMock(stdout="", returncode=0),
        ]
        result = get_changed_dep_files(tmp_path)
        assert "pyproject.toml" in result

    @patch("firsttoknow.guard.subprocess.run")
    def test_detects_package_json_in_staged(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Should detect package.json in staged changes."""
        mock_run.side_effect = [
            MagicMock(stdout="", returncode=0),  # unstaged
            MagicMock(stdout="package.json\n", returncode=0),  # staged
        ]
        result = get_changed_dep_files(tmp_path)
        assert "package.json" in result

    @patch("firsttoknow.guard.subprocess.run")
    def test_no_dep_files_changed(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """If only source files changed, no dep files should be returned."""
        mock_run.side_effect = [
            MagicMock(stdout="src/main.py\nsrc/utils.py\n", returncode=0),
            MagicMock(stdout="", returncode=0),
        ]
        result = get_changed_dep_files(tmp_path)
        assert result == []

    @patch("firsttoknow.guard.subprocess.run")
    def test_deduplicates(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Same file in both staged and unstaged should appear once."""
        mock_run.side_effect = [
            MagicMock(stdout="pyproject.toml\n", returncode=0),
            MagicMock(stdout="pyproject.toml\n", returncode=0),
        ]
        result = get_changed_dep_files(tmp_path)
        assert result == ["pyproject.toml"]

    def test_fallback_when_not_git_repo(self, tmp_path: Path) -> None:
        """If not a git repo, fall back to checking which dep files exist."""
        # Create a pyproject.toml in the temp dir
        (tmp_path / "pyproject.toml").write_text("[project]\nname='test'\n")
        # No git — subprocess will fail
        with patch("firsttoknow.guard.subprocess.run", side_effect=FileNotFoundError):
            result = get_changed_dep_files(tmp_path)
        assert "pyproject.toml" in result


# ──────────────────────────────────────────────
# Dependency diffing tests
# ──────────────────────────────────────────────


class TestFindNewDeps:
    """Test the core logic: finding deps that are NEW since last commit."""

    @patch("firsttoknow.guard.scan_committed_deps")
    @patch("firsttoknow.guard.scan_current_deps")
    def test_finds_new_dep(self, mock_current: MagicMock, mock_committed: MagicMock, tmp_path: Path) -> None:
        """A dep that exists now but not in the last commit is NEW."""
        mock_current.return_value = {
            "requests": ScannedDep("requests", "2.31.0"),
            "flask": ScannedDep("flask", "3.0.0"),
        }
        mock_committed.return_value = {
            "requests": ScannedDep("requests", "2.31.0"),
        }
        new = find_new_deps(tmp_path)
        assert len(new) == 1
        assert new[0].name == "flask"

    @patch("firsttoknow.guard.scan_committed_deps")
    @patch("firsttoknow.guard.scan_current_deps")
    def test_no_new_deps(self, mock_current: MagicMock, mock_committed: MagicMock, tmp_path: Path) -> None:
        """If deps haven't changed, nothing is new."""
        mock_current.return_value = {"requests": ScannedDep("requests", "2.31.0")}
        mock_committed.return_value = {"requests": ScannedDep("requests", "2.28.0")}
        new = find_new_deps(tmp_path)
        assert len(new) == 0

    @patch("firsttoknow.guard.scan_committed_deps")
    @patch("firsttoknow.guard.scan_current_deps")
    def test_all_new_in_fresh_project(
        self, mock_current: MagicMock, mock_committed: MagicMock, tmp_path: Path
    ) -> None:
        """In a brand new project (no previous commit), everything is new."""
        mock_current.return_value = {
            "requests": ScannedDep("requests", "2.31.0"),
            "flask": ScannedDep("flask", "3.0.0"),
        }
        mock_committed.return_value = {}
        new = find_new_deps(tmp_path)
        assert len(new) == 2


# ──────────────────────────────────────────────
# Vulnerability check tests
# ──────────────────────────────────────────────


class TestCheckVulnerabilities:
    """Test the OSV vulnerability checker."""

    @patch("firsttoknow.guard.httpx.post")
    def test_clean_package(self, mock_post: MagicMock) -> None:
        """A package with no CVEs should return an INFO finding."""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"vulns": []}),
        )
        mock_post.return_value.raise_for_status = MagicMock()

        findings = check_vulnerabilities("requests", "pypi")
        assert len(findings) == 1
        assert findings[0].severity == Severity.INFO
        assert "No known vulnerabilities" in findings[0].title

    @patch("firsttoknow.guard.httpx.post")
    def test_vulnerable_package(self, mock_post: MagicMock) -> None:
        """A package with CVEs should return CRITICAL findings."""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(
                return_value={
                    "vulns": [
                        {
                            "id": "GHSA-1234",
                            "aliases": ["CVE-2024-1234"],
                            "summary": "Remote code execution vulnerability",
                            "severity": [{"score": "9.8"}],
                            "references": [{"type": "ADVISORY", "url": "https://example.com/advisory"}],
                        }
                    ]
                }
            ),
        )
        mock_post.return_value.raise_for_status = MagicMock()

        findings = check_vulnerabilities("bad-package", "pypi")
        assert len(findings) == 1
        assert findings[0].severity == Severity.CRITICAL
        assert "Remote code execution" in findings[0].title
        assert "CVE-2024-1234" in findings[0].details
        assert findings[0].url == "https://example.com/advisory"

    @patch("firsttoknow.guard.httpx.post")
    def test_multiple_vulns(self, mock_post: MagicMock) -> None:
        """Multiple CVEs should produce multiple findings."""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(
                return_value={
                    "vulns": [
                        {"id": "GHSA-1", "aliases": ["CVE-2024-001"], "summary": "bug 1", "severity": [], "references": []},
                        {"id": "GHSA-2", "aliases": ["CVE-2024-002"], "summary": "bug 2", "severity": [], "references": []},
                    ]
                }
            ),
        )
        mock_post.return_value.raise_for_status = MagicMock()

        findings = check_vulnerabilities("risky-pkg", "pypi")
        assert len(findings) == 2
        assert all(f.severity == Severity.CRITICAL for f in findings)

    @patch("firsttoknow.guard.httpx.post")
    def test_api_failure_returns_warning(self, mock_post: MagicMock) -> None:
        """If OSV API is down, return a WARNING (not a crash)."""
        mock_post.side_effect = Exception("Connection refused")

        findings = check_vulnerabilities("some-pkg", "pypi")
        assert len(findings) == 1
        assert findings[0].severity == Severity.WARNING
        assert "Could not check" in findings[0].title

    @patch("firsttoknow.guard.httpx.post")
    def test_deduplicates_same_cve(self, mock_post: MagicMock) -> None:
        """Same CVE under different OSV IDs should appear only once.

        Real scenario: OSV returns GHSA-xxx and PYSEC-yyy both
        referencing CVE-2021-29510. We should show it once.
        """
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(
                return_value={
                    "vulns": [
                        {
                            "id": "GHSA-5jqp-qgf6-3pvh",
                            "aliases": ["CVE-2021-29510"],
                            "summary": "Infinite loop via 'infinity' input",
                            "severity": [],
                            "references": [],
                        },
                        {
                            "id": "PYSEC-2021-141",
                            "aliases": ["CVE-2021-29510"],
                            "summary": "Same bug, different DB entry",
                            "severity": [],
                            "references": [],
                        },
                    ]
                }
            ),
        )
        mock_post.return_value.raise_for_status = MagicMock()

        findings = check_vulnerabilities("pydantic", "pypi")
        assert len(findings) == 1  # NOT 2
        assert "CVE-2021-29510" in findings[0].details

    @patch("firsttoknow.guard.httpx.post")
    def test_version_aware_query(self, mock_post: MagicMock) -> None:
        """When version is provided, OSV query should include it."""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"vulns": []}),
        )
        mock_post.return_value.raise_for_status = MagicMock()

        check_vulnerabilities("pydantic", "pypi", version="2.7.0")

        # Verify the request included the version
        call_kwargs = mock_post.call_args
        request_body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert request_body["version"] == "2.7.0"

    @patch("firsttoknow.guard.httpx.post")
    def test_no_version_omits_field(self, mock_post: MagicMock) -> None:
        """Without a version, the query should NOT include version field."""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"vulns": []}),
        )
        mock_post.return_value.raise_for_status = MagicMock()

        check_vulnerabilities("requests", "pypi")

        call_kwargs = mock_post.call_args
        request_body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert "version" not in request_body


# ──────────────────────────────────────────────
# Fix version extraction tests
# ──────────────────────────────────────────────


class TestExtractFixVersion:
    """Test the _extract_fix_version helper.

    Why test a 'private' function?
    ──────────────────────────────
    Even though it starts with _, this function has complex parsing logic
    (nested dicts, multiple ranges, multiple events). If it breaks, the
    user gets wrong "upgrade to" advice — that's worse than no advice.
    Testing the private function directly is simpler and more precise
    than testing it through check_vulnerabilities() which requires
    mocking the entire HTTP layer.

    Rule of thumb: test private functions when their logic is complex
    enough to break independently.
    """

    def test_extracts_fix_version(self) -> None:
        """Standard OSV structure with a fix version."""
        affected = [
            {
                "package": {"name": "pydantic", "ecosystem": "PyPI"},
                "ranges": [
                    {
                        "type": "ECOSYSTEM",
                        "events": [
                            {"introduced": "2.0.0"},
                            {"fixed": "2.4.0"},
                        ],
                    }
                ],
            }
        ]
        assert _extract_fix_version(affected, "pydantic") == "2.4.0"

    def test_no_fix_available(self) -> None:
        """Some vulnerabilities don't have a fix yet (only 'introduced', no 'fixed')."""
        affected = [
            {
                "package": {"name": "bad-pkg", "ecosystem": "PyPI"},
                "ranges": [
                    {
                        "type": "ECOSYSTEM",
                        "events": [
                            {"introduced": "0"},
                        ],
                    }
                ],
            }
        ]
        assert _extract_fix_version(affected, "bad-pkg") is None

    def test_wrong_package_name_skipped(self) -> None:
        """If the affected entry is for a DIFFERENT package, skip it.

        Real scenario: some OSV entries list multiple affected packages.
        We only want the fix version for OUR package.
        """
        affected = [
            {
                "package": {"name": "other-pkg", "ecosystem": "PyPI"},
                "ranges": [
                    {
                        "type": "ECOSYSTEM",
                        "events": [
                            {"introduced": "1.0"},
                            {"fixed": "1.5"},
                        ],
                    }
                ],
            }
        ]
        assert _extract_fix_version(affected, "my-pkg") is None

    def test_case_insensitive_match(self) -> None:
        """Package name matching should be case-insensitive.

        PyPI treats 'Flask' and 'flask' as the same package.
        OSV might use either casing.
        """
        affected = [
            {
                "package": {"name": "Flask", "ecosystem": "PyPI"},
                "ranges": [
                    {
                        "type": "ECOSYSTEM",
                        "events": [
                            {"introduced": "0"},
                            {"fixed": "2.3.2"},
                        ],
                    }
                ],
            }
        ]
        assert _extract_fix_version(affected, "flask") == "2.3.2"

    def test_empty_affected_list(self) -> None:
        """Empty affected list → no fix version."""
        assert _extract_fix_version([], "anything") is None

    def test_multiple_ranges_returns_first_fix(self) -> None:
        """If there are multiple ranges with fixes, return the first one.

        Real scenario: some OSV entries have both ECOSYSTEM and SEMVER ranges.
        """
        affected = [
            {
                "package": {"name": "requests", "ecosystem": "PyPI"},
                "ranges": [
                    {
                        "type": "ECOSYSTEM",
                        "events": [
                            {"introduced": "2.0"},
                            {"fixed": "2.31.0"},
                        ],
                    },
                    {
                        "type": "SEMVER",
                        "events": [
                            {"introduced": "2.0.0"},
                            {"fixed": "2.31.0"},
                        ],
                    },
                ],
            }
        ]
        assert _extract_fix_version(affected, "requests") == "2.31.0"


class TestActionableDetails:
    """Test that vulnerability findings include actionable upgrade guidance."""

    @patch("firsttoknow.guard.httpx.post")
    def test_details_include_fix_version(self, mock_post: MagicMock) -> None:
        """When OSV provides a fix version, details should say 'upgrade to >= X'."""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(
                return_value={
                    "vulns": [
                        {
                            "id": "GHSA-test",
                            "aliases": ["CVE-2024-0001"],
                            "summary": "Some vulnerability",
                            "references": [],
                            "affected": [
                                {
                                    "package": {"name": "pydantic", "ecosystem": "PyPI"},
                                    "ranges": [
                                        {
                                            "type": "ECOSYSTEM",
                                            "events": [
                                                {"introduced": "2.0"},
                                                {"fixed": "2.4.0"},
                                            ],
                                        }
                                    ],
                                }
                            ],
                        }
                    ]
                }
            ),
        )
        mock_post.return_value.raise_for_status = MagicMock()

        findings = check_vulnerabilities("pydantic", "pypi", version="2.0.0")
        assert len(findings) == 1
        details = findings[0].details
        # Should contain ALL three pieces: CVE ID, user's version, fix version
        assert "CVE-2024-0001" in details
        assert "your version: 2.0.0" in details
        assert "fix: upgrade to >= 2.4.0" in details

    @patch("firsttoknow.guard.httpx.post")
    def test_details_show_no_fix_when_unavailable(self, mock_post: MagicMock) -> None:
        """When no fix version exists, details should say 'no fix available yet'."""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(
                return_value={
                    "vulns": [
                        {
                            "id": "GHSA-nofix",
                            "aliases": ["CVE-2024-9999"],
                            "summary": "Unfixed vulnerability",
                            "references": [],
                            "affected": [
                                {
                                    "package": {"name": "risky-pkg", "ecosystem": "PyPI"},
                                    "ranges": [
                                        {
                                            "type": "ECOSYSTEM",
                                            "events": [
                                                {"introduced": "0"},
                                            ],
                                        }
                                    ],
                                }
                            ],
                        }
                    ]
                }
            ),
        )
        mock_post.return_value.raise_for_status = MagicMock()

        findings = check_vulnerabilities("risky-pkg", "pypi", version="1.0.0")
        assert len(findings) == 1
        assert "no fix available yet" in findings[0].details

    @patch("firsttoknow.guard.httpx.post")
    def test_details_without_version(self, mock_post: MagicMock) -> None:
        """When no version is provided, details should NOT include 'your version'."""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(
                return_value={
                    "vulns": [
                        {
                            "id": "GHSA-test2",
                            "aliases": ["CVE-2024-0002"],
                            "summary": "Another vuln",
                            "references": [],
                        }
                    ]
                }
            ),
        )
        mock_post.return_value.raise_for_status = MagicMock()

        findings = check_vulnerabilities("some-pkg", "pypi")
        assert len(findings) == 1
        assert "your version" not in findings[0].details
        assert "CVE-2024-0002" in findings[0].details


# ──────────────────────────────────────────────
# License check tests
# ──────────────────────────────────────────────


class TestCheckLicenseChange:
    """Test the license change checker."""

    @patch("firsttoknow.agents._tools.FirstToKnowTools.check_license_change")
    def test_no_change(self, mock_check: MagicMock) -> None:
        """If license didn't change, return empty list."""
        mock_check.return_value = json.dumps({
            "package": "requests",
            "license_changed": False,
            "latest_license": "Apache-2.0",
            "previous_license": "Apache-2.0",
        })

        findings = check_license_change("requests", "pypi")
        assert findings == []

    @patch("firsttoknow.agents._tools.FirstToKnowTools.check_license_change")
    def test_license_changed(self, mock_check: MagicMock) -> None:
        """If license changed, return a CRITICAL finding."""
        mock_check.return_value = json.dumps({
            "package": "redis",
            "license_changed": True,
            "latest_version": "5.0",
            "latest_license": "SSPL",
            "previous_version": "4.0",
            "previous_license": "BSD-3-Clause",
        })

        findings = check_license_change("redis", "pypi")
        assert len(findings) == 1
        assert findings[0].severity == Severity.CRITICAL
        assert "License changed" in findings[0].title
        assert "BSD-3-Clause" in findings[0].title
        assert "SSPL" in findings[0].title


# ──────────────────────────────────────────────
# Full guard run tests
# ──────────────────────────────────────────────


class TestRunGuard:
    """Test the full guard pipeline end-to-end."""

    @patch("firsttoknow.guard.check_license_change")
    @patch("firsttoknow.guard.check_vulnerabilities")
    @patch("firsttoknow.guard.find_new_deps")
    def test_no_new_deps(
        self, mock_find: MagicMock, mock_vulns: MagicMock, mock_license: MagicMock, tmp_path: Path
    ) -> None:
        """No new deps → report passes with info message."""
        mock_find.return_value = []

        report = run_guard(tmp_path)
        assert report.passed is True
        assert len(report.findings) == 1
        assert "No new dependencies" in report.findings[0].title

    @patch("firsttoknow.guard.check_license_change")
    @patch("firsttoknow.guard.check_vulnerabilities")
    @patch("firsttoknow.guard.find_new_deps")
    def test_clean_new_dep(
        self, mock_find: MagicMock, mock_vulns: MagicMock, mock_license: MagicMock, tmp_path: Path
    ) -> None:
        """New dep with no issues → report passes."""
        mock_find.return_value = [ScannedDep("flask", "3.0.0")]
        mock_vulns.return_value = [
            GuardFinding(package="flask", ecosystem="pypi", severity=Severity.INFO, title="flask: no known vulnerabilities")
        ]
        mock_license.return_value = []

        report = run_guard(tmp_path)
        assert report.passed is True

    @patch("firsttoknow.guard.check_license_change")
    @patch("firsttoknow.guard.check_vulnerabilities")
    @patch("firsttoknow.guard.find_new_deps")
    def test_vulnerable_new_dep(
        self, mock_find: MagicMock, mock_vulns: MagicMock, mock_license: MagicMock, tmp_path: Path
    ) -> None:
        """New dep with CVE → report fails."""
        mock_find.return_value = [ScannedDep("bad-pkg", "1.0.0")]
        mock_vulns.return_value = [
            GuardFinding(
                package="bad-pkg", ecosystem="pypi", severity=Severity.CRITICAL,
                title="bad-pkg: CVE-2024-9999", details="Remote code execution",
            )
        ]
        mock_license.return_value = []

        report = run_guard(tmp_path)
        assert report.passed is False
        assert report.critical_count == 1

    @patch("firsttoknow.guard.check_license_change")
    @patch("firsttoknow.guard.check_vulnerabilities")
    @patch("firsttoknow.guard.find_new_deps")
    def test_npm_package_detection(
        self, mock_find: MagicMock, mock_vulns: MagicMock, mock_license: MagicMock, tmp_path: Path
    ) -> None:
        """Scoped npm packages (@scope/name) should be detected as npm."""
        mock_find.return_value = [ScannedDep("@babel/core", "7.0.0")]
        mock_vulns.return_value = [
            GuardFinding(package="@babel/core", ecosystem="npm", severity=Severity.INFO, title="clean")
        ]
        mock_license.return_value = []

        run_guard(tmp_path)

        # Should have been called with ecosystem="npm" and the version
        mock_vulns.assert_called_once_with("@babel/core", "npm", version="7.0.0")
        mock_license.assert_called_once_with("@babel/core", "npm")

"""Tests for the AI-powered code review feature.

Testing strategy:
────────────────
We mock litellm.completion — we never call a real LLM in tests.
Why? Because:
1. Tests must be free (no API costs)
2. Tests must be deterministic (LLM responses vary)
3. Tests must be fast (no network round-trip)

We test the LOGIC: "given this diff and this LLM response,
does review_diff produce the right findings?"

We also test _parse_review_response separately because LLMs
are unpredictable in their output format — we need to handle
markdown fences, extra text, malformed JSON, etc.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from firsttoknow.guard import _parse_review_response, review_diff
from firsttoknow.models import Severity

if TYPE_CHECKING:
    from pathlib import Path


# ──────────────────────────────────────────────
# _parse_review_response tests
# ──────────────────────────────────────────────


class TestParseReviewResponse:
    """Test JSON parsing of LLM responses.

    LLMs are messy — they add markdown fences, extra text, wrong formats.
    These tests ensure we handle all the common quirks.
    """

    def test_clean_json_array(self) -> None:
        """Perfect JSON array — the happy path."""
        response = json.dumps([
            {"title": "Hardcoded API key", "details": "Use env vars", "package": "config.py"},
        ])
        findings = _parse_review_response(response)
        assert len(findings) == 1
        assert findings[0].title == "Hardcoded API key"
        assert findings[0].severity == Severity.WARNING

    def test_empty_array(self) -> None:
        """Empty array means clean diff — no findings."""
        findings = _parse_review_response("[]")
        assert findings == []

    def test_markdown_fenced_json(self) -> None:
        """LLMs love wrapping JSON in ```json ... ``` even when told not to."""
        response = '```json\n[{"title": "SSL disabled", "details": "verify=False", "package": "client.py"}]\n```'
        findings = _parse_review_response(response)
        assert len(findings) == 1
        assert "SSL disabled" in findings[0].title

    def test_json_with_extra_text(self) -> None:
        """LLM adds explanatory text before the JSON array."""
        response = 'Here are the findings:\n[{"title": "Secret leaked", "details": "Remove it", "package": "app.py"}]'
        findings = _parse_review_response(response)
        assert len(findings) == 1

    def test_single_object_instead_of_array(self) -> None:
        """LLM returns a single {} instead of [{}]."""
        response = '{"title": "Path traversal risk", "details": "Sanitize input", "package": "views.py"}'
        findings = _parse_review_response(response)
        assert len(findings) == 1

    def test_malformed_json(self) -> None:
        """Totally broken JSON — should return empty, not crash."""
        findings = _parse_review_response("this is not json at all")
        assert findings == []

    def test_empty_response(self) -> None:
        """Empty string from LLM — no findings."""
        findings = _parse_review_response("")
        assert findings == []

    def test_findings_are_warning_severity(self) -> None:
        """All AI findings should be WARNING (advisory), never CRITICAL.

        Why? Because LLMs can hallucinate. If we made AI findings CRITICAL,
        a hallucinated issue would BLOCK the push. That's unacceptable.
        Only deterministic checks (CVEs from OSV) should block pushes.
        """
        response = json.dumps([
            {"title": "Issue 1", "details": "Details 1", "package": "a.py"},
            {"title": "Issue 2", "details": "Details 2", "package": "b.py"},
        ])
        findings = _parse_review_response(response)
        assert all(f.severity == Severity.WARNING for f in findings)

    def test_ecosystem_is_ai_review(self) -> None:
        """AI findings should be tagged with ecosystem='AI review' for clarity."""
        response = json.dumps([{"title": "Test", "details": "Test", "package": "test.py"}])
        findings = _parse_review_response(response)
        assert findings[0].ecosystem == "AI review"

    def test_truncates_long_titles_and_details(self) -> None:
        """Guard against LLM returning extremely long text."""
        response = json.dumps([{
            "title": "x" * 500,
            "details": "y" * 500,
            "package": "test.py",
        }])
        findings = _parse_review_response(response)
        assert len(findings[0].title) <= 120
        assert len(findings[0].details) <= 300


# ──────────────────────────────────────────────
# review_diff tests
# ──────────────────────────────────────────────


class TestReviewDiff:
    """Test the full review_diff function."""

    @patch("firsttoknow.guard.get_git_diff")
    @patch("firsttoknow.guard.litellm")
    def test_clean_diff(self, mock_litellm: MagicMock, mock_diff: MagicMock, tmp_path: Path) -> None:
        """LLM says diff is clean → no findings."""
        mock_diff.return_value = "diff --git a/main.py\n+print('hello')\n"

        # Build a mock response matching litellm's structure
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "[]"
        mock_litellm.completion.return_value = mock_response

        findings = review_diff(tmp_path, "gpt-4o")
        assert findings == []

    @patch("firsttoknow.guard.get_git_diff")
    @patch("firsttoknow.guard.litellm")
    def test_risky_diff(self, mock_litellm: MagicMock, mock_diff: MagicMock, tmp_path: Path) -> None:
        """LLM finds a security issue → WARNING finding."""
        mock_diff.return_value = "diff --git a/config.py\n+API_KEY = 'sk-1234567890'\n"

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps([
            {"title": "Hardcoded API key", "details": "Use environment variables", "package": "config.py"},
        ])
        mock_litellm.completion.return_value = mock_response

        findings = review_diff(tmp_path, "gpt-4o")
        assert len(findings) == 1
        assert findings[0].severity == Severity.WARNING
        assert "API key" in findings[0].title

    @patch("firsttoknow.guard.get_git_diff")
    def test_empty_diff_skips_llm(self, mock_diff: MagicMock, tmp_path: Path) -> None:
        """No changes → skip LLM call entirely (save money + time)."""
        mock_diff.return_value = ""
        findings = review_diff(tmp_path, "gpt-4o")
        assert findings == []

    @patch("firsttoknow.guard.get_git_diff")
    @patch("firsttoknow.guard.litellm")
    def test_llm_failure_returns_warning(self, mock_litellm: MagicMock, mock_diff: MagicMock, tmp_path: Path) -> None:
        """If the LLM call fails (no API key, network error), return a warning."""
        mock_diff.return_value = "diff --git a/main.py\n+import os\n"
        mock_litellm.completion.side_effect = Exception("API key not set")

        findings = review_diff(tmp_path, "gpt-4o")
        assert len(findings) == 1
        assert findings[0].severity == Severity.WARNING
        assert "Could not run AI code review" in findings[0].title

    @patch("firsttoknow.guard.get_git_diff")
    @patch("firsttoknow.guard.litellm")
    def test_large_diff_truncated(self, mock_litellm: MagicMock, mock_diff: MagicMock, tmp_path: Path) -> None:
        """Large diffs should be truncated before sending to the LLM."""
        # Create a diff larger than _MAX_DIFF_CHARS
        mock_diff.return_value = "x" * 20000

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "[]"
        mock_litellm.completion.return_value = mock_response

        review_diff(tmp_path, "gpt-4o")

        # Verify the message sent to the LLM was truncated
        call_args = mock_litellm.completion.call_args
        user_message = call_args.kwargs["messages"][1]["content"]
        assert "truncated" in user_message
        # Should be around _MAX_DIFF_CHARS + some overhead, not 20000
        assert len(user_message) < 10000

    @patch("firsttoknow.guard.get_git_diff")
    @patch("firsttoknow.guard.litellm")
    def test_uses_temperature_zero(self, mock_litellm: MagicMock, mock_diff: MagicMock, tmp_path: Path) -> None:
        """Review should use temperature=0 for consistent, deterministic analysis."""
        mock_diff.return_value = "diff --git a/main.py\n+x = 1\n"

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "[]"
        mock_litellm.completion.return_value = mock_response

        review_diff(tmp_path, "gpt-4o")

        call_args = mock_litellm.completion.call_args
        assert call_args.kwargs["temperature"] == 0.0

"""Guard module — scans git changes for dependency risks before you push.

Architecture decision: WHY is this separate from the agent?
─────────────────────────────────────────────────────────────
The `brief` command uses an LLM agent (ADK + LiteLLM) because it needs
to reason, summarize, and prioritize across many sources.

The `guard` command does NOT need an LLM for its core job:
  - "Does this package have CVEs?" → YES/NO from OSV database
  - "Did the license change?" → string comparison

Using an LLM here would be:
  1. Slower (network round-trip to an LLM API)
  2. Less reliable (LLMs can hallucinate CVE numbers)
  3. More expensive (token costs for every git push)
  4. Requires API keys (guard should work offline with local checks)

We DO reuse the same HTTP functions from _tools.py — just call them
directly instead of routing through an agent.

─────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

import httpx

from firsttoknow.models import GuardFinding, GuardReport, Severity
from firsttoknow.scanner import (
    ScannedDep,
    scan_package_json,
    scan_pyproject,
    scan_requirements,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Git diff parsing
# ──────────────────────────────────────────────


def get_git_diff(path: Path, staged: bool = False) -> str:
    """Run `git diff` and return the output as a string.

    Why subprocess and not a git library (like GitPython)?
    ──────────────────────────────────────────────────────
    - GitPython is a 10MB dependency for one command
    - subprocess.run is stdlib — zero dependencies
    - We only need the text output of `git diff`, nothing fancy
    - Rule of thumb: don't add a library for something a one-liner can do

    Args:
        path: Path to the git repo root.
        staged: If True, show only staged changes (--cached).
                If False, show ALL uncommitted changes.

    Returns:
        The raw diff text, or empty string if no changes / not a git repo.
    """
    cmd = ["git", "diff"]
    if staged:
        cmd.append("--cached")

    # We also want to see what's in commits not yet pushed.
    # For Step 1, we'll keep it simple: diff uncommitted changes.
    # In Step 2 (git hook), we'll compare against the remote.

    try:
        result = subprocess.run(  # noqa: S603
            cmd,
            cwd=path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        logger.warning("git diff failed: %s", exc)
        return ""


def get_changed_dep_files(path: Path) -> list[str]:
    """Find which dependency files have been modified in git.

    Why check specific filenames instead of parsing all diffs?
    ──────────────────────────────────────────────────────────
    A git diff can contain thousands of lines across hundreds of files.
    We only care about dependency files (pyproject.toml, requirements.txt,
    package.json). Checking filenames first is O(1) vs parsing everything.

    Returns:
        List of changed dependency file basenames (e.g. ["pyproject.toml"]).
    """
    cmd = ["git", "diff", "--name-only", "HEAD"]
    try:
        result = subprocess.run(  # noqa: S603
            cmd,
            cwd=path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        changed = result.stdout.strip().splitlines()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        # Not a git repo or git not installed — fall back to scanning everything
        return _detect_dep_files(path)

    # Also check staged files
    cmd_staged = ["git", "diff", "--name-only", "--cached"]
    try:
        result_staged = subprocess.run(  # noqa: S603
            cmd_staged,
            cwd=path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        changed.extend(result_staged.stdout.strip().splitlines())
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    dep_files = {"pyproject.toml", "requirements.txt", "package.json"}
    found = []
    for f in changed:
        basename = Path(f).name
        if basename in dep_files:
            found.append(basename)

    # Deduplicate while preserving order
    return list(dict.fromkeys(found))


def _detect_dep_files(path: Path) -> list[str]:
    """Fallback: check which dep files exist (when not in a git repo)."""
    found = []
    for name in ("pyproject.toml", "requirements.txt", "package.json"):
        if (path / name).exists():
            found.append(name)
    return found


# ──────────────────────────────────────────────
# Dependency diffing
# ──────────────────────────────────────────────


def scan_current_deps(path: Path) -> dict[str, ScannedDep]:
    """Scan the CURRENT state of dependency files.

    Returns:
        Dict mapping normalized package name → ScannedDep.
    """
    deps: dict[str, ScannedDep] = {}

    for dep in scan_pyproject(path):
        deps[dep.name.lower()] = dep
    for dep in scan_requirements(path):
        deps.setdefault(dep.name.lower(), dep)
    for dep in scan_package_json(path):
        deps[dep.name.lower()] = dep

    return deps


def scan_committed_deps(path: Path) -> dict[str, ScannedDep]:
    """Scan the LAST COMMITTED state of dependency files.

    How this works (concept: git show):
    ─────────────────────────────────────
    `git show HEAD:pyproject.toml` outputs the file contents as they
    were in the last commit — WITHOUT modifying your working directory.
    This lets us compare "what was" vs "what is now" to find NEW deps.

    Returns:
        Dict mapping normalized package name → ScannedDep.
    """
    deps: dict[str, ScannedDep] = {}
    import tempfile

    for filename, scanner in [
        ("pyproject.toml", scan_pyproject),
        ("requirements.txt", scan_requirements),
        ("package.json", scan_package_json),
    ]:
        try:
            result = subprocess.run(  # noqa: S603
                ["git", "show", f"HEAD:{filename}"],  # noqa: S607
                cwd=path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                continue  # File doesn't exist in last commit

            # Write to temp file so our existing scanners can read it
            # Why? Our scanners expect file paths, not strings.
            # We COULD refactor them to accept strings, but that's a
            # bigger change. For now, temp file is simple and works.
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=filename, delete=False
            ) as tmp:
                tmp.write(result.stdout)
                tmp_path = Path(tmp.name)

            try:
                for dep in scanner(tmp_path):
                    deps.setdefault(dep.name.lower(), dep)
            finally:
                tmp_path.unlink(missing_ok=True)

        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            continue

    return deps


def find_new_deps(path: Path) -> list[ScannedDep]:
    """Find dependencies that exist NOW but didn't exist in the last commit.

    This is the core of the guard: "what NEW packages are you about to push?"

    Returns:
        List of newly added dependencies.
    """
    current = scan_current_deps(path)
    committed = scan_committed_deps(path)

    new_deps: list[ScannedDep] = []
    for name, dep in current.items():
        if name not in committed:
            new_deps.append(dep)

    return new_deps


# ──────────────────────────────────────────────
# Vulnerability & license checking
# ──────────────────────────────────────────────

# We reuse the HTTP logic from _tools.py. But instead of going through
# the agent (which wraps everything in JSON strings for the LLM),
# we call the underlying functions and parse the results ourselves.
#
# Why not import FirstToKnowTools directly?
# Because those methods return JSON STRINGS (designed for LLM consumption).
# We'd have to json.loads() every response — wasteful. Instead, we
# make the same HTTP calls but return structured Python objects.


def check_vulnerabilities(
    package_name: str, ecosystem: str = "pypi", version: str | None = None
) -> list[GuardFinding]:
    """Check a single package for known CVEs via OSV.dev.

    Key improvement over a naive approach:
    ──────────────────────────────────────
    1. VERSION-AWARE QUERIES: If we know the version being installed,
       we ask OSV "is pydantic 2.7.0 vulnerable?" instead of
       "is pydantic vulnerable?". The difference is huge:
       - Without version: returns ALL historic CVEs (noisy, scary, misleading)
       - With version: returns only CVEs that affect YOUR version (accurate, useful)

    2. DEDUPLICATION: OSV often returns the same vulnerability under
       multiple IDs (e.g., GHSA-xxx AND CVE-xxx for the same bug).
       We deduplicate by CVE ID so each issue appears only once.

    Args:
        package_name: Package name (e.g., "pydantic").
        ecosystem: "pypi" or "npm".
        version: If provided, only return vulns affecting this version.
    """
    ecosystem_map = {"pypi": "PyPI", "npm": "npm"}
    osv_ecosystem = ecosystem_map.get(ecosystem.lower(), ecosystem)

    # Build the query — include version if we have it
    query_pkg: dict[str, str] = {"name": package_name, "ecosystem": osv_ecosystem}
    query: dict[str, object] = {"package": query_pkg}
    if version:
        query["version"] = version

    try:
        resp = httpx.post(
            "https://api.osv.dev/v1/query",
            json=query,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning("OSV check failed for %s: %s", package_name, exc)
        return [
            GuardFinding(
                package=package_name,
                ecosystem=ecosystem,
                severity=Severity.WARNING,
                title=f"Could not check vulnerabilities for {package_name}",
                details=str(exc),
            )
        ]

    raw_vulns = data.get("vulns", [])
    if not raw_vulns:
        return [
            GuardFinding(
                package=package_name,
                ecosystem=ecosystem,
                severity=Severity.INFO,
                title="No known vulnerabilities",
            )
        ]

    # Deduplicate: multiple OSV entries can refer to the same CVE.
    # We use the CVE ID as the dedup key. If no CVE alias exists,
    # use the OSV ID (which is unique per entry).
    #
    # Why a dict and not a set?
    # Because we want to keep the FIRST (usually best-described) entry
    # for each CVE, not just track "seen" IDs.
    seen_ids: dict[str, GuardFinding] = {}

    for v in raw_vulns:
        vuln_id = v.get("id", "")
        aliases = v.get("aliases", [])
        cve_id = next((a for a in aliases if a.startswith("CVE-")), None)
        display_id = cve_id or vuln_id

        # Skip if we've already seen this CVE
        if display_id in seen_ids:
            continue

        summary = v.get("summary", "No description available")

        # Build URL — prefer the NVD advisory link
        url = f"https://osv.dev/vulnerability/{vuln_id}"
        for ref in v.get("references", []):
            if ref.get("type") == "ADVISORY":
                url = ref.get("url", url)
                break

        # Extract fix version from the `affected` ranges
        # OSV structure: affected[].ranges[].events[] = [{"introduced":"X"}, {"fixed":"Y"}]
        # The "fixed" event tells us which version patched this vulnerability.
        fixed_version = _extract_fix_version(v.get("affected", []), package_name)

        # Build a human-readable detail string that answers:
        # 1. What CVE is this?
        # 2. What version are YOU installing?
        # 3. What should you DO?
        detail_parts = [display_id]
        if version:
            detail_parts.append(f"your version: {version}")
        if fixed_version:
            detail_parts.append(f"fix: upgrade to >= {fixed_version}")
        else:
            detail_parts.append("no fix available yet")

        finding = GuardFinding(
            package=package_name,
            ecosystem=ecosystem,
            severity=Severity.CRITICAL,
            title=summary if summary != "No description available" else display_id,
            details=" · ".join(detail_parts),
            url=url,
        )
        seen_ids[display_id] = finding

    return list(seen_ids.values())


def _extract_fix_version(affected: list[dict[str, object]], package_name: str) -> str | None:
    """Extract the fix version from OSV affected data.

    OSV structure example:
        "affected": [{
            "package": {"name": "pydantic", "ecosystem": "PyPI"},
            "ranges": [{
                "type": "ECOSYSTEM",
                "events": [
                    {"introduced": "2.0.0"},
                    {"fixed": "2.4.0"}        ← this is what we want
                ]
            }]
        }]

    Why extract this?
    ─────────────────
    Without this, the guard says "pydantic has CVE-2024-3772" — scary but useless.
    With this, the guard says "fix: upgrade to >= 2.4.0" — actionable.
    That's the difference between a tool that creates anxiety and one that
    solves problems.

    Returns:
        The fix version string (e.g. "2.4.0"), or None if no fix exists.
    """
    for entry in affected:
        # Make sure we're looking at the right package
        pkg = entry.get("package", {})
        if isinstance(pkg, dict) and pkg.get("name", "").lower() != package_name.lower():
            continue

        ranges = entry.get("ranges", [])
        if not isinstance(ranges, list):
            continue

        for r in ranges:
            if not isinstance(r, dict):
                continue
            events = r.get("events", [])
            if not isinstance(events, list):
                continue

            # Walk events looking for "fixed"
            for event in events:
                if isinstance(event, dict) and "fixed" in event:
                    fixed = event["fixed"]
                    if isinstance(fixed, str):
                        return fixed

    return None


def check_license_change(package_name: str, ecosystem: str = "pypi") -> list[GuardFinding]:
    """Check if a package's license changed between its latest two versions."""
    from firsttoknow.agents._tools import FirstToKnowTools

    tools = FirstToKnowTools()

    try:
        # Reuse the existing tool — it returns a JSON string
        result_json = tools.check_license_change(package_name, ecosystem)
        result = json.loads(result_json)
    except Exception as exc:
        logger.warning("License check failed for %s: %s", package_name, exc)
        return []

    if result.get("error"):
        return []

    if result.get("license_changed"):
        prev_license = result.get("previous_license", "?")
        new_license = result.get("latest_license", "?")
        return [
            GuardFinding(
                package=package_name,
                ecosystem=ecosystem,
                severity=Severity.CRITICAL,
                title=f"License changed: {prev_license} → {new_license}",
                details=(
                    f"v{result.get('previous_version', '?')} was {prev_license}, "
                    f"v{result.get('latest_version', '?')} is {new_license}"
                ),
            )
        ]

    return []


# ──────────────────────────────────────────────
# Main guard runner
# ──────────────────────────────────────────────


def run_guard(path: Path) -> GuardReport:
    """Run the full guard check on a project directory.

    This is the main entry point. It:
    1. Finds new dependencies (comparing current vs last commit)
    2. Checks each one for vulnerabilities (OSV)
    3. Checks each one for license changes
    4. Returns a structured report

    Args:
        path: Path to the project root (must be a git repo).

    Returns:
        GuardReport with all findings.
    """
    report = GuardReport()

    # Step 1: Find new deps
    new_deps = find_new_deps(path)

    if not new_deps:
        report.findings.append(
            GuardFinding(
                package="dependencies",
                ecosystem="—",
                severity=Severity.INFO,
                title="No new dependencies detected",
                details="Nothing changed since your last commit.",
            )
        )
        return report

    # Step 2: Check each new dep
    for dep in new_deps:
        # Determine ecosystem from context
        # Simple heuristic: if the name has @ or /, it's npm. Otherwise pypi.
        # This works for 99% of cases. We can make it smarter later.
        ecosystem = "npm" if dep.name.startswith("@") or "/" in dep.name else "pypi"

        # Check vulnerabilities — pass version for accurate results
        # Without version: "is pydantic vulnerable?" → ALL historic CVEs (scary, misleading)
        # With version: "is pydantic 2.7.0 vulnerable?" → only relevant CVEs (useful)
        vuln_findings = check_vulnerabilities(dep.name, ecosystem, version=dep.version)
        report.findings.extend(vuln_findings)

        # Check license changes
        license_findings = check_license_change(dep.name, ecosystem)
        report.findings.extend(license_findings)

    return report

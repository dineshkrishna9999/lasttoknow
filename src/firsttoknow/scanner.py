"""Dependency scanner for FirstToKnow.

Reads pyproject.toml, requirements.txt, or package.json from a project directory
and extracts package names + pinned versions.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path  # noqa: TC003 — used at runtime, not just type hints

logger = logging.getLogger(__name__)

# Packages that aren't useful to track (build tools, dev-only, etc.)
_SKIP = frozenset(
    {
        "pip",
        "setuptools",
        "wheel",
        "hatchling",
        "flit-core",
        "flit_core",
        "poetry-core",
        "poetry_core",
    }
)


@dataclass
class ScannedDep:
    """A dependency found by the scanner."""

    name: str
    version: str | None = None


def _normalize(name: str) -> str:
    """Normalize a package name (PEP 503)."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _parse_version_spec(spec: str) -> str | None:
    """Extract a pinned or minimum version from a spec string.

    Examples:
        ">=1.40.0"       → "1.40.0"
        ">=1.40.0,<2.0"  → "1.40.0"
        "==3.11.0"       → "3.11.0"
        "<=1.70.0"       → None  (upper bound only, no current version)
        ""               → None
    """
    if not spec:
        return None
    # Look for ==, >=, or ~= first (these indicate a known version)
    match = re.search(r"(?:==|>=|~=)\s*([0-9][0-9a-zA-Z.*]*)", spec)
    if match:
        return match.group(1)
    return None


def scan_pyproject(path: Path) -> list[ScannedDep]:
    """Scan a pyproject.toml for dependencies.

    Args:
        path: Path to the project directory (not the file itself).

    Returns:
        List of dependencies found.
    """
    toml_path = path / "pyproject.toml" if path.is_dir() else path

    if not toml_path.exists():
        return []

    try:
        # Use tomllib (stdlib in 3.11+)
        import tomllib

        with toml_path.open("rb") as f:
            data = tomllib.load(f)
    except Exception:
        logger.warning("Failed to parse %s", toml_path)
        return []

    deps: list[ScannedDep] = []

    # [project.dependencies]
    for dep_str in data.get("project", {}).get("dependencies", []):
        parsed = _parse_dep_string(dep_str)
        if parsed and _normalize(parsed.name) not in _SKIP:
            deps.append(parsed)

    return deps


def scan_requirements(path: Path) -> list[ScannedDep]:
    """Scan a requirements.txt for dependencies.

    Args:
        path: Path to the project directory or to the file itself.

    Returns:
        List of dependencies found.
    """
    req_path = path / "requirements.txt" if path.is_dir() else path

    if not req_path.exists():
        return []

    deps: list[ScannedDep] = []
    try:
        for line in req_path.read_text().splitlines():
            line = line.strip()
            # Skip comments, empty lines, and -r/-e flags
            if not line or line.startswith(("#", "-r", "-e", "--")):
                continue
            parsed = _parse_dep_string(line)
            if parsed and _normalize(parsed.name) not in _SKIP:
                deps.append(parsed)
    except OSError:
        logger.warning("Failed to read %s", req_path)

    return deps


def _parse_dep_string(dep_str: str) -> ScannedDep | None:
    """Parse a PEP 508 dependency string into name + version.

    Examples:
        "litellm>=1.40.0"      → ScannedDep("litellm", "1.40.0")
        "rich>=13.0.0"         → ScannedDep("rich", "13.0.0")
        "httpx[http2]>=0.27.0" → ScannedDep("httpx", "0.27.0")
        "litellm<=1.70.0"      → ScannedDep("litellm", None)
    """
    # Remove extras: "httpx[http2]>=0.27" → "httpx>=0.27"
    dep_str = re.sub(r"\[.*?\]", "", dep_str).strip()

    if not dep_str:
        return None

    # Split on first version operator
    match = re.match(r"([a-zA-Z0-9_.-]+)\s*(.*)", dep_str)
    if not match:
        return None

    name = match.group(1).strip()
    version_spec = match.group(2).strip()

    if not name:
        return None

    version = _parse_version_spec(version_spec)
    return ScannedDep(name=name, version=version)


def _parse_npm_version(spec: str) -> str | None:
    """Extract a version number from an npm semver spec.

    Examples:
        "^1.2.3"  → "1.2.3"
        "~4.17.1" → "4.17.1"
        ">=2.0.0" → "2.0.0"
        "1.2.3"   → "1.2.3"
        "*"       → None
        "latest"  → None
    """
    if not spec:
        return None
    match = re.match(r"^\s*[\^~>=<]*\s*([0-9][0-9a-zA-Z.*+-]*)", spec)
    return match.group(1) if match else None


def scan_package_json(path: Path) -> list[ScannedDep]:
    """Scan a package.json for dependencies.

    Only reads the ``dependencies`` field (not ``devDependencies``).

    Args:
        path: Path to the project directory (not the file itself).

    Returns:
        List of dependencies found.
    """
    pkg_path = path / "package.json" if path.is_dir() else path

    if not pkg_path.exists():
        return []

    try:
        data = json.loads(pkg_path.read_text())
    except Exception:
        logger.warning("Failed to parse %s", pkg_path)
        return []

    deps: list[ScannedDep] = []
    for name, version_spec in data.get("dependencies", {}).items():
        version = _parse_npm_version(version_spec)
        deps.append(ScannedDep(name=name, version=version))

    return deps


def scan_project(path: Path) -> list[ScannedDep]:
    """Scan a project directory for dependencies.

    Tries pyproject.toml first, then requirements.txt, then package.json.

    Args:
        path: Path to the project directory.

    Returns:
        List of dependencies found.
    """
    deps = scan_pyproject(path)
    if deps:
        return deps

    deps = scan_requirements(path)
    if deps:
        return deps

    return scan_package_json(path)

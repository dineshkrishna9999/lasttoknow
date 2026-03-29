"""Tests for the dependency scanner."""

from __future__ import annotations

from typing import TYPE_CHECKING

from devpulse.scanner import ScannedDep, scan_project, scan_pyproject, scan_requirements

if TYPE_CHECKING:
    from pathlib import Path


class TestScanPyproject:
    """Tests for scanning pyproject.toml."""

    def test_scans_dependencies(self, tmp_path: Path) -> None:
        toml = tmp_path / "pyproject.toml"
        toml.write_text(
            '[project]\ndependencies = [\n    "litellm>=1.40.0",\n    "rich>=13.0.0",\n    "httpx>=0.27.0",\n]\n'
        )
        deps = scan_pyproject(tmp_path)
        assert len(deps) == 3
        names = [d.name for d in deps]
        assert "litellm" in names
        assert "rich" in names
        assert "httpx" in names

    def test_extracts_versions(self, tmp_path: Path) -> None:
        toml = tmp_path / "pyproject.toml"
        toml.write_text('[project]\ndependencies = [\n    "litellm>=1.40.0",\n    "rich==13.7.0",\n    "click",\n]\n')
        deps = scan_pyproject(tmp_path)
        by_name = {d.name: d for d in deps}
        assert by_name["litellm"].version == "1.40.0"
        assert by_name["rich"].version == "13.7.0"
        assert by_name["click"].version is None

    def test_skips_build_tools(self, tmp_path: Path) -> None:
        toml = tmp_path / "pyproject.toml"
        toml.write_text('[project]\ndependencies = [\n    "setuptools>=68.0",\n    "wheel",\n    "rich>=13.0.0",\n]\n')
        deps = scan_pyproject(tmp_path)
        names = [d.name for d in deps]
        assert "setuptools" not in names
        assert "wheel" not in names
        assert "rich" in names

    def test_handles_extras(self, tmp_path: Path) -> None:
        toml = tmp_path / "pyproject.toml"
        toml.write_text('[project]\ndependencies = [\n    "httpx[http2]>=0.27.0",\n]\n')
        deps = scan_pyproject(tmp_path)
        assert len(deps) == 1
        assert deps[0].name == "httpx"
        assert deps[0].version == "0.27.0"

    def test_returns_empty_for_missing_file(self, tmp_path: Path) -> None:
        deps = scan_pyproject(tmp_path)
        assert deps == []

    def test_returns_empty_for_no_deps_section(self, tmp_path: Path) -> None:
        toml = tmp_path / "pyproject.toml"
        toml.write_text("[project]\nname = 'test'\n")
        deps = scan_pyproject(tmp_path)
        assert deps == []

    def test_upper_bound_only_has_no_version(self, tmp_path: Path) -> None:
        toml = tmp_path / "pyproject.toml"
        toml.write_text('[project]\ndependencies = [\n    "litellm<=1.70.0",\n]\n')
        deps = scan_pyproject(tmp_path)
        assert len(deps) == 1
        assert deps[0].name == "litellm"
        assert deps[0].version is None


class TestScanRequirements:
    """Tests for scanning requirements.txt."""

    def test_scans_requirements(self, tmp_path: Path) -> None:
        req = tmp_path / "requirements.txt"
        req.write_text("litellm>=1.40.0\nrich>=13.0.0\nhttpx\n")
        deps = scan_requirements(tmp_path)
        assert len(deps) == 3

    def test_skips_comments_and_flags(self, tmp_path: Path) -> None:
        req = tmp_path / "requirements.txt"
        req.write_text("# A comment\n-r other.txt\n--index-url http://x\nlitellm>=1.40.0\n")
        deps = scan_requirements(tmp_path)
        assert len(deps) == 1
        assert deps[0].name == "litellm"

    def test_extracts_pinned_version(self, tmp_path: Path) -> None:
        req = tmp_path / "requirements.txt"
        req.write_text("litellm==1.41.0\nrich~=13.7.0\n")
        deps = scan_requirements(tmp_path)
        by_name = {d.name: d for d in deps}
        assert by_name["litellm"].version == "1.41.0"
        assert by_name["rich"].version == "13.7.0"

    def test_returns_empty_for_missing_file(self, tmp_path: Path) -> None:
        deps = scan_requirements(tmp_path)
        assert deps == []


class TestScanProject:
    """Tests for the unified scan_project function."""

    def test_prefers_pyproject(self, tmp_path: Path) -> None:
        toml = tmp_path / "pyproject.toml"
        toml.write_text('[project]\ndependencies = ["litellm>=1.40.0"]\n')
        req = tmp_path / "requirements.txt"
        req.write_text("rich>=13.0.0\n")
        deps = scan_project(tmp_path)
        # Should use pyproject.toml, not requirements.txt
        assert len(deps) == 1
        assert deps[0].name == "litellm"

    def test_falls_back_to_requirements(self, tmp_path: Path) -> None:
        req = tmp_path / "requirements.txt"
        req.write_text("rich>=13.0.0\nhttpx>=0.27.0\n")
        deps = scan_project(tmp_path)
        assert len(deps) == 2

    def test_returns_empty_for_empty_dir(self, tmp_path: Path) -> None:
        deps = scan_project(tmp_path)
        assert deps == []


class TestScannedDep:
    """Tests for the ScannedDep dataclass."""

    def test_defaults(self) -> None:
        dep = ScannedDep(name="litellm")
        assert dep.name == "litellm"
        assert dep.version is None

    def test_with_version(self) -> None:
        dep = ScannedDep(name="litellm", version="1.40.0")
        assert dep.version == "1.40.0"

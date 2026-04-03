"""FirstToKnow CLI — your AI-powered tech radar from the terminal.

Built with Typer — function arguments become CLI arguments automatically.
Type hints drive the parsing, no decorators needed.

Commands:
    firsttoknow track litellm              Track a PyPI package
    firsttoknow track --github BerriAI/x   Track a GitHub repo
    firsttoknow track --topic "AI agents"  Track a topic
    firsttoknow track --npm express        Track an npm package
    firsttoknow untrack litellm            Stop tracking
    firsttoknow list                       Show tracked items
    firsttoknow brief                      Get your AI briefing
    firsttoknow guard                      Check deps before pushing
    firsttoknow config model gpt-4o        Set default model
    firsttoknow config show                Show settings
"""

from __future__ import annotations

import os
import subprocess
from typing import Annotated

import typer
from dotenv import load_dotenv

from firsttoknow import __version__
from firsttoknow.config import FirstToKnowConfig
from firsttoknow.models import GuardFinding, ItemType, Severity
from firsttoknow.renderer import (
    render_banner,
    render_briefing,
    render_briefing_spinner,
    render_error,
    render_guard_report,
    render_scan_results,
    render_status,
    render_success,
    render_tracked_items,
    render_warning,
)

# ──────────────────────────────────────────────
# App setup
# ──────────────────────────────────────────────

# Load .env file if present (API keys, FIRSTTOKNOW_MODEL, etc.)
load_dotenv()

app = typer.Typer(
    name="firsttoknow",
    help="🔔 FirstToKnow — Never miss what matters in tech.\n\nTrack packages, releases, and trends. Get briefed like a CTO.",
    no_args_is_help=True,
)

# Sub-app for "firsttoknow config ..."
config_app = typer.Typer(help="Manage FirstToKnow settings.")
app.add_typer(config_app, name="config")

# Shared config instance.
_config = FirstToKnowConfig()


def _version_callback(value: bool) -> None:
    if value:
        render_banner(__version__)
        raise typer.Exit


@app.callback()
def _main(
    version: Annotated[
        bool, typer.Option("--version", "-v", help="Show version and exit.", callback=_version_callback)
    ] = False,
) -> None:
    """🔔 FirstToKnow — Never miss what matters in tech."""


def _resolve_model(model_override: str | None) -> str:
    """Figure out which LLM model to use (flag → env var → config → error)."""
    model = model_override or os.environ.get("FIRSTTOKNOW_MODEL") or _config.model
    if not model:
        render_error(
            "No model configured. Set one with:\n"
            "  firsttoknow config model azure/gpt-4.1\n"
            "  or set FIRSTTOKNOW_MODEL env var\n"
            "  or pass --model flag"
        )
        raise typer.Exit(1)
    return model


# ──────────────────────────────────────────────
# track / untrack / list
# ──────────────────────────────────────────────


@app.command()
def track(
    name: Annotated[str, typer.Argument(help="Package name, repo (owner/repo), or topic to track.")],
    github: Annotated[bool, typer.Option("--github", help="Track as a GitHub repo.")] = False,
    topic: Annotated[bool, typer.Option("--topic", help="Track as a topic.")] = False,
    npm: Annotated[bool, typer.Option("--npm", help="Track as an npm package.")] = False,
    version: Annotated[str | None, typer.Option("--version", "-V", help="Current version you're using.")] = None,
) -> None:
    """Track a package, repo, or topic."""
    if github:
        item_type = ItemType.GITHUB
        source_url = f"https://github.com/{name}"
    elif topic:
        item_type = ItemType.TOPIC
        source_url = None
    elif npm:
        item_type = ItemType.NPM
        source_url = f"https://www.npmjs.com/package/{name}"
    else:
        item_type = ItemType.PYPI
        source_url = f"https://pypi.org/project/{name}/"

    try:
        item = _config.add_item(name, item_type, source_url=source_url, current_version=version)
        render_success(f"Now tracking [bold]{item.name}[/bold] ({item.item_type.value})")
    except ValueError as exc:
        render_warning(str(exc))


@app.command()
def untrack(
    name: Annotated[str, typer.Argument(help="Name of the item to stop tracking.")],
) -> None:
    """Stop tracking a package, repo, or topic."""
    if _config.remove_item(name):
        render_success(f"Stopped tracking [bold]{name}[/bold]")
    else:
        render_warning(f"Not tracking '{name}'")


@app.command()
def scan(
    path: Annotated[str, typer.Argument(help="Path to project directory (default: current dir).")] = ".",
) -> None:
    """Auto-detect and track dependencies from pyproject.toml, requirements.txt, or package.json."""
    from pathlib import Path

    from firsttoknow.scanner import scan_project

    project_path = Path(path).resolve()
    deps, source = scan_project(project_path)

    if not deps:
        render_warning(f"No dependencies found in {project_path}")
        return

    is_npm = source == "package.json"

    added = 0
    skipped = 0
    for dep in deps:
        try:
            if is_npm:
                _config.add_item(
                    dep.name,
                    ItemType.NPM,
                    source_url=f"https://www.npmjs.com/package/{dep.name}",
                    current_version=dep.version,
                )
            else:
                _config.add_item(
                    dep.name,
                    ItemType.PYPI,
                    source_url=f"https://pypi.org/project/{dep.name}/",
                    current_version=dep.version,
                )
            render_success(f"Tracking [bold]{dep.name}[/bold]" + (f" (v{dep.version})" if dep.version else ""))
            added += 1
        except ValueError:
            skipped += 1

    render_scan_results(found=len(deps), added=added, skipped=skipped, source=source)


@app.command(name="list")
def list_items() -> None:
    """Show all tracked items."""
    render_tracked_items(_config.tracked_items)


# ──────────────────────────────────────────────
# brief
# ──────────────────────────────────────────────


@app.command()
def brief(
    model: Annotated[str | None, typer.Option("--model", "-m", help="LLM model to use.")] = None,
    raw: Annotated[bool, typer.Option("--raw", help="Print raw response without formatting.")] = False,
) -> None:
    """Get your AI-powered tech briefing.

    The agent checks your tracked packages, finds trending repos,
    and synthesizes everything into a prioritized briefing.
    """
    resolved_model = _resolve_model(model)
    items = _config.tracked_items
    packages = [i.name for i in items if i.item_type == ItemType.PYPI]
    npm_packages = [i.name for i in items if i.item_type == ItemType.NPM]
    github_repos = [i.name for i in items if i.item_type == ItemType.GITHUB]
    topics = [i.name for i in items if i.item_type == ItemType.TOPIC]

    # Build the message for the agent
    parts = ["Give me a tech briefing."]
    if packages:
        parts.append(f"Check these PyPI packages for updates: {', '.join(packages)}.")
    if npm_packages:
        parts.append(f"Check these npm packages for updates: {', '.join(npm_packages)}.")
    if github_repos:
        parts.append(f"Check these GitHub repos for new releases: {', '.join(github_repos)}.")
    if topics:
        parts.append(f"Also search for news about: {', '.join(topics)}.")
    if not packages and not npm_packages and not github_repos and not topics:
        parts.append("I'm not tracking anything specific yet — give me general Python/AI trends.")
    if packages or npm_packages:
        parts.append("Also check all tracked packages for known security vulnerabilities.")
        parts.append("Also check all tracked packages for license changes between versions.")

    message = " ".join(parts)

    # Import here to avoid loading ADK/LiteLLM on every CLI invocation
    from firsttoknow.agents.agent import run_agent

    try:
        with render_briefing_spinner() as on_tool_call:
            response = run_agent(model=resolved_model, message=message, on_tool_call=on_tool_call)
    except Exception as exc:
        render_error(str(exc))
        raise typer.Exit(1) from exc

    if raw:
        typer.echo(response)
    else:
        render_briefing(response, model=resolved_model)

    # Update last_checked for all tracked items
    for item in items:
        _config.update_last_checked(item.name)


# ──────────────────────────────────────────────
# guard
# ──────────────────────────────────────────────


@app.command()
def guard(
    path: Annotated[str, typer.Argument(help="Path to project directory (default: current dir).")] = ".",
    init: Annotated[bool, typer.Option("--init", help="Install guard as a pre-push git hook.")] = False,
    review: Annotated[bool, typer.Option("--review", help="Run AI-powered code review of the diff.")] = False,
    model: Annotated[str | None, typer.Option("--model", "-m", help="LLM model for AI review.")] = None,
) -> None:
    """Scan your uncommitted changes for dependency risks before pushing.

    Compares your current dependency files against the last git commit,
    finds NEW dependencies, and checks each one for:
    - Known security vulnerabilities (CVEs via OSV.dev)
    - License changes between versions

    Use --review to also get an AI-powered code review of the diff.
    Use --init to install as an automatic pre-push hook.
    Exit code 0 = all clear, exit code 1 = critical issues found.
    """
    if init:
        _install_guard_hook(path)
        return

    from pathlib import Path

    from firsttoknow.guard import run_guard

    project_path = Path(path).resolve()

    # Import here (like brief does) to keep CLI startup fast
    try:
        report = run_guard(project_path)
    except Exception as exc:
        render_error(f"Guard scan failed: {exc}")
        raise typer.Exit(1) from exc

    # Optional: AI-powered code review
    if review:
        resolved_model = _resolve_model(model)
        from firsttoknow.guard import review_diff

        try:
            ai_findings = review_diff(project_path, resolved_model)
            if ai_findings:
                report.findings.extend(ai_findings)
            else:
                # Show the user that AI review ran and found nothing
                report.findings.append(
                    GuardFinding(
                        package="AI review",
                        ecosystem="—",
                        severity=Severity.INFO,
                        title="AI code review: no security issues found in diff",
                        details=f"Reviewed by {resolved_model}",
                    )
                )
        except Exception as exc:
            render_warning(f"AI review failed: {exc}")

    render_guard_report(report)

    # Exit code matters! When used as a git hook, exit code 1
    # tells git to ABORT the push. This is how we block bad code.
    if not report.passed:
        raise typer.Exit(1)


def _install_guard_hook(path: str) -> None:
    """Install FirstToKnow Guard as a pre-push hook via pre-commit.

    Why pre-commit instead of writing .git/hooks/pre-push directly?
    ───────────────────────────────────────────────────────────────
    1. Coexistence: raw .git/hooks/ only allows ONE script per hook.
       pre-commit lets multiple hooks share the same stage.
    2. Cross-platform: shell scripts don't work on Windows.
       pre-commit handles Windows/macOS/Linux.
    3. Idempotent: pre-commit won't break if you run init twice.
    4. Standard: it's what the ecosystem uses (ruff, mypy, black).

    The trade-off? Requires pre-commit to be installed. But if you're
    using firsttoknow, you're a developer who likely has it already.
    """
    from pathlib import Path

    project_path = Path(path).resolve()
    config_file = project_path / ".pre-commit-config.yaml"

    # ── Step 1: Check if .pre-commit-config.yaml exists ──────────
    if not config_file.exists():
        render_warning(
            "No .pre-commit-config.yaml found.\n"
            "  Create one first, or run: pre-commit sample-config > .pre-commit-config.yaml"
        )
        raise typer.Exit(1)

    # ── Step 2: Check if guard hook is already configured ────────
    config_text = config_file.read_text()
    if "firsttoknow-guard" in config_text:
        render_success("Guard hook is already configured in .pre-commit-config.yaml")
    else:
        # Append the local hook config
        hook_config = (
            "\n"
            "  # FirstToKnow Guard — checks new dependencies for CVEs and license changes\n"
            "  - repo: local\n"
            "    hooks:\n"
            "      - id: firsttoknow-guard\n"
            "        name: FirstToKnow Guard (dependency security)\n"
            "        entry: firsttoknow-guard\n"
            "        language: system\n"
            "        stages: [pre-push]\n"
            "        pass_filenames: false\n"
            "        always_run: true\n"
        )
        config_file.write_text(config_text + hook_config)
        render_success("Added guard hook to .pre-commit-config.yaml")

    # ── Step 3: Install the pre-push hook ────────────────────────
    try:
        result = subprocess.run(
            ["pre-commit", "install", "--hook-type", "pre-push"],  # noqa: S607
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            render_success("Pre-push hook installed")
        else:
            render_warning(f"pre-commit install failed: {result.stderr.strip()}")
            render_warning("You can install manually: pre-commit install --hook-type pre-push")
    except FileNotFoundError:
        render_warning(
            "pre-commit not found. Install it first:\n"
            "  pip install pre-commit\n"
            "Then run: pre-commit install --hook-type pre-push"
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        render_warning(f"Could not run pre-commit: {exc}")

    render_success(
        "\n  Guard will now run automatically before every [bold]git push[/bold].\n"
        "  To bypass (emergency): git push --no-verify"
    )


# ──────────────────────────────────────────────
# config model / config show
# ──────────────────────────────────────────────


@config_app.command(name="model")
def config_model(
    model_name: Annotated[str, typer.Argument(help="LLM model string (e.g. azure/gpt-4.1, gpt-4o).")],
) -> None:
    """Set the default LLM model."""
    _config.model = model_name
    _config.save_settings()
    render_success(f"Default model set to [bold]{model_name}[/bold]")


@config_app.command(name="show")
def config_show() -> None:
    """Show current configuration."""
    render_status(
        config_dir=str(_config.config_dir),
        model=_config.model,
        sources=_config.sources,
        default_days=_config.default_days,
        tracked_count=len(_config.tracked_items),
    )


# ──────────────────────────────────────────────
# status
# ──────────────────────────────────────────────


@app.command()
def status() -> None:
    """Show FirstToKnow status and tracked items."""
    render_banner(__version__)
    config_show()
    render_tracked_items(_config.tracked_items)

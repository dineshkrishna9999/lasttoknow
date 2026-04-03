"""Rich terminal renderer for FirstToKnow output.

Handles all the pretty-printing: briefing panels, tracked item tables,
status displays. Uses the Rich library for colors, tables, and panels.

Why a separate renderer? Keeps display logic out of the CLI and agent code.
The CLI calls the renderer, the renderer calls Rich.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from firsttoknow import __version__

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

    from firsttoknow.models import GuardReport, TrackedItem

console = Console()


def render_tracked_items(items: list[TrackedItem]) -> None:
    """Display tracked items in a rich table."""
    if not items:
        console.print("[yellow]No items tracked yet.[/yellow] Run [bold]firsttoknow track <package>[/bold] to start.")
        return

    table = Table(title=f"🔔 FirstToKnow — Tracking {len(items)} items")
    table.add_column("Name", style="bold")
    table.add_column("Type", style="cyan")
    table.add_column("Version", style="green")
    table.add_column("Last Checked", style="dim")

    for item in items:
        last_checked = item.last_checked.strftime("%Y-%m-%d %H:%M") if item.last_checked else "never"
        table.add_row(
            item.name,
            item.item_type.value,
            item.current_version or "—",
            last_checked,
        )

    console.print(table)


def render_briefing(response: str, model: str) -> None:
    """Display an agent briefing response in a rich panel with markdown rendering.

    Falls back to raw text if Markdown rendering fails (e.g. Rich unicode
    data issue on some Python/platform combinations).
    """
    try:
        content: Markdown | str = Markdown(response, hyperlinks=True)
        panel = Panel(
            content,
            title="🔔 FirstToKnow Briefing",
            subtitle=f"model: {model}",
            border_style="green",
            padding=(1, 2),
        )
        console.print(panel)
    except Exception:
        # Fallback: render as plain text if Markdown rendering fails
        panel = Panel(
            response,
            title="🔔 FirstToKnow Briefing",
            subtitle=f"model: {model}",
            border_style="green",
            padding=(1, 2),
        )
        console.print(panel)


def render_status(
    config_dir: str,
    model: str | None,
    sources: list[str],
    default_days: int,
    tracked_count: int,
) -> None:
    """Display the current FirstToKnow configuration."""
    info = Text()
    info.append(f"  Config dir:    {config_dir}\n", style="dim")
    info.append("  Model:         ")
    info.append(f"{model or '(not set)'}\n", style="cyan")
    info.append(f"  Sources:       {', '.join(sources)}\n")
    info.append(f"  Default days:  {default_days}\n")
    info.append(f"  Tracked items: {tracked_count}")

    panel = Panel(
        info,
        title=f"🔔 FirstToKnow v{__version__}",
        border_style="blue",
    )
    console.print(panel)


def render_success(message: str) -> None:
    """Display a success message."""
    console.print(f"[green]✓[/green] {message}")


def render_warning(message: str) -> None:
    """Display a warning message."""
    console.print(f"[yellow]{message}[/yellow]")


def render_scan_results(found: int, added: int, skipped: int, source: str) -> None:
    """Display scan results summary."""
    console.print(f"\n[bold]📦 Scanned:[/bold] {source}")
    console.print(
        f"   Found [bold]{found}[/bold] dependencies, added [bold]{added}[/bold] new, {skipped} already tracked.\n"
    )


def render_error(message: str) -> None:
    """Display an error message."""
    console.print(f"[red]{message}[/red]")


# ──────────────────────────────────────────────
# ASCII banner
# ──────────────────────────────────────────────

_BANNER = """\
[bold green]
  ╔═╗╦╦═╗╔═╗╔╦╗╔╦╗╔═╗╦╔═╔╗╔╔═╗╦ ╦
  ╠╣ ║╠╦╝╚═╗ ║  ║ ║ ║╠╩╗║║║║ ║║║║
  ╚  ╩╩╚═╚═╝ ╩  ╩ ╚═╝╩ ╩╝╚╝╚═╝╚╩╝[/bold green]"""


def render_banner(version: str) -> None:
    """Display the FirstToKnow ASCII banner with version."""
    console.print(_BANNER)
    console.print(f"  [dim]v{version} — Never miss what matters in tech.[/dim]\n")


# ──────────────────────────────────────────────
# Briefing spinner
# ──────────────────────────────────────────────

_TOOL_STATUS: dict[str, str] = {
    "fetch_pypi_releases": "Checking PyPI",
    "fetch_npm_releases": "Checking npm",
    "check_vulnerabilities": "Scanning for vulnerabilities",
    "fetch_github_trending": "Fetching GitHub trending repos",
    "fetch_github_releases": "Fetching GitHub releases",
    "fetch_hackernews_top": "Searching Hacker News",
    "fetch_devto_articles": "Browsing Dev.to articles",
    "fetch_reddit_posts": "Checking Reddit",
    "check_license_change": "Checking license changes",
}


# ──────────────────────────────────────────────
# Guard report
# ──────────────────────────────────────────────


def render_guard_report(report: GuardReport) -> None:
    """Display the guard scan results as a clear, scannable report.

    Design decision: stacked items, not a table
    ────────────────────────────────────────────
    v1 used a table — but findings have variable-length details and URLs.
    Tables truncate that or look cramped. Instead, each finding gets its
    own lines, like how `npm audit` or `cargo audit` display results.
    Scannable, no truncation, room to breathe.
    """
    from firsttoknow.models import Severity

    console.print()  # breathing room

    # ── Grade + Header ────────────────────────────
    grade = report.grade
    grade_styles = {
        "Blockbuster": ("bold green", "OG — clean code, power push 🚀"),
        "Superhit": ("green", "Almost perfect, minor notes"),
        "Hit": ("yellow", "One fix away from greatness"),
        "Average": ("red", "Needs attention before shipping"),
        "Flop": ("red", "Several issues — hold the release"),
        "Disaster": ("bold red", "Do not ship — fix immediately"),
    }
    color, label = grade_styles.get(grade, ("white", "Unknown"))
    console.print(f"  [{color}]🎬  GUARD  {grade}[/{color}]  [dim]— {label}[/dim]")

    console.print()

    # ── Each finding as its own block ─────────
    severity_styles = {
        Severity.CRITICAL: ("🚨", "red", "CRITICAL"),
        Severity.WARNING: ("⚠️ ", "yellow", "WARNING"),
        Severity.INFO: ("✅", "green", "OK"),
    }

    for finding in report.findings:
        icon, color, label = severity_styles.get(finding.severity, ("❓", "white", "UNKNOWN"))

        # Line 1: icon + package + severity label
        console.print(f"  {icon} [bold]{finding.package}[/bold]  [{color}]{label}[/{color}]")

        # Line 2: what was found (the human-readable title)
        console.print(f"     {finding.title}")

        # Line 3: details (if any)
        if finding.details:
            console.print(f"     [dim]{finding.details}[/dim]")

        # Line 4: link (if any) — full URL, not truncated
        if finding.url:
            console.print(f"     [dim blue]{finding.url}[/dim blue]")

        console.print()  # gap between findings

    # ── Summary bar ───────────────────────────
    parts = []
    if report.critical_count:
        parts.append(f"[bold red]{report.critical_count} critical[/bold red]")
    if report.warning_count:
        parts.append(
            f"[bold yellow]{report.warning_count} warning{'s' if report.warning_count != 1 else ''}[/bold yellow]"
        )
    if report.info_count:
        parts.append(f"[bold green]{report.info_count} passed[/bold green]")

    summary = "  " + " · ".join(parts)
    console.print(f"  {'─' * 50}")
    console.print(summary)
    console.print()

    # ── Actionable hint ───────────────────────
    if not report.passed:
        console.print("  [dim]Fix the critical issues above, then push again.[/dim]")
        console.print()


@contextmanager
def render_briefing_spinner() -> Generator[Callable[[str], None]]:
    """Show a live spinner during briefing that updates with each tool call.

    Yields a callback that the agent calls with the tool name whenever
    a tool is invoked. The spinner text updates to show what's happening.

    Usage::

        with render_briefing_spinner() as on_tool_call:
            response = run_agent(model, message, on_tool_call=on_tool_call)
    """
    with console.status("[bold green]Preparing briefing...", spinner="dots") as status:

        def _on_tool_call(tool_name: str) -> None:
            label = _TOOL_STATUS.get(tool_name, f"Running {tool_name}")
            status.update(f"[bold green]{label}...")

        yield _on_tool_call

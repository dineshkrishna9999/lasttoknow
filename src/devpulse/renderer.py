"""Rich terminal renderer for DevPulse output.

Handles all the pretty-printing: briefing panels, tracked item tables,
status displays. Uses the Rich library for colors, tables, and panels.

Why a separate renderer? Keeps display logic out of the CLI and agent code.
The CLI calls the renderer, the renderer calls Rich.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from devpulse import __version__

if TYPE_CHECKING:
    from devpulse.models import TrackedItem

console = Console()


def render_tracked_items(items: list[TrackedItem]) -> None:
    """Display tracked items in a rich table."""
    if not items:
        console.print("[yellow]No items tracked yet.[/yellow] Run [bold]devpulse track <package>[/bold] to start.")
        return

    table = Table(title=f"📡 DevPulse — Tracking {len(items)} items")
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
    """Display an agent briefing response in a rich panel."""
    panel = Panel(
        response,
        title="📡 DevPulse Briefing",
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
    """Display the current DevPulse configuration."""
    info = Text()
    info.append(f"  Config dir:    {config_dir}\n", style="dim")
    info.append("  Model:         ")
    info.append(f"{model or '(not set)'}\n", style="cyan")
    info.append(f"  Sources:       {', '.join(sources)}\n")
    info.append(f"  Default days:  {default_days}\n")
    info.append(f"  Tracked items: {tracked_count}")

    panel = Panel(
        info,
        title=f"📡 DevPulse v{__version__}",
        border_style="blue",
    )
    console.print(panel)


def render_success(message: str) -> None:
    """Display a success message."""
    console.print(f"[green]✓[/green] {message}")


def render_warning(message: str) -> None:
    """Display a warning message."""
    console.print(f"[yellow]{message}[/yellow]")


def render_error(message: str) -> None:
    """Display an error message."""
    console.print(f"[red]{message}[/red]")

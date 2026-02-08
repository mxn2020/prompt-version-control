"""pv - prompt version control CLI."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table
from sqlalchemy.orm import Session

from pv import __version__
from pv.config import default_db_path
from pv.database import get_session_factory, init_db, reset_engine
from pv.services.prompt_service import PromptService


def _version_callback(value: bool) -> None:
    if value:
        print(f"pv {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="pv",
    help="prompt-version-control: version your prompts locally.",
    add_completion=False,
    no_args_is_help=True,
)


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            help="Show version and exit.",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = False,
) -> None:
    """prompt-version-control: version your prompts locally."""


console = Console()

DbOption = Annotated[
    Path | None,
    typer.Option("--db", envvar="PV_DB", help="Override path to SQLite database."),
]


def _db_path(db: Path | None) -> Path:
    return db if db is not None else default_db_path()


def _get_service(db: Path | None) -> tuple[PromptService, Session]:
    """Return (service, session) after ensuring the database exists."""
    path = _db_path(db)
    reset_engine()
    init_db(path)
    factory = get_session_factory(path)
    session = factory()
    return PromptService(session), session


# ------------------------------------------------------------------
# init
# ------------------------------------------------------------------


@app.command()
def init(db: DbOption = None) -> None:
    """Initialize the pv database."""
    path = _db_path(db)
    reset_engine()
    init_db(path)
    rprint(f"[green]✓[/green] Database initialized at [bold]{path}[/bold]")


# ------------------------------------------------------------------
# add
# ------------------------------------------------------------------


@app.command()
def add(
    name: Annotated[str, typer.Argument(help="Prompt name")],
    content: Annotated[
        str | None,
        typer.Option("--content", "-c", help="Prompt content. Use - to read from stdin."),
    ] = None,
    file: Annotated[
        Path | None,
        typer.Option("--file", "-f", help="Read prompt content from a file."),
    ] = None,
    tag: Annotated[
        list[str] | None,
        typer.Option("--tag", "-t", help="Tags for this version (repeatable)."),
    ] = None,
    note: Annotated[
        str | None,
        typer.Option("--note", "-n", help="Optional note for this version."),
    ] = None,
    db: DbOption = None,
) -> None:
    """Add a new version of a prompt."""
    if content and file:
        rprint("[red]Error:[/red] Provide --content or --file, not both.")
        raise typer.Exit(1) from None
    if file:
        if not file.exists():
            rprint(f"[red]Error:[/red] File not found: {file}")
            raise typer.Exit(1) from None
        content = file.read_text(encoding="utf-8")
    elif content == "-":
        content = sys.stdin.read()
    elif content is None:
        rprint("[red]Error:[/red] Provide prompt content via --content or --file.")
        raise typer.Exit(1) from None

    service, session = _get_service(db)
    try:
        version = service.add_version(name, content, tags=tag or [], note=note)
        session.commit()
        rprint(
            f"[green]✓[/green] Added [bold]{name}[/bold] v{version.version_number}"
            f" (hash: {version.content_hash[:12]}…)"
        )
    except Exception as exc:
        session.rollback()
        rprint(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from None
    finally:
        session.close()
        reset_engine()


# ------------------------------------------------------------------
# list (ls)
# ------------------------------------------------------------------


@app.command("list")
def list_prompts(
    db: DbOption = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
) -> None:
    """List all prompts."""
    import json

    service, session = _get_service(db)
    try:
        prompts = service.list_prompts()
        if not prompts:
            rprint("[dim]No prompts found.[/dim]")
            return

        if json_output:
            data = []
            for p in prompts:
                versions = service.list_versions(p.name)
                data.append(
                    {
                        "name": p.name,
                        "versions": len(versions),
                        "latest": versions[-1].version_number if versions else None,
                        "created_at": p.created_at.isoformat() if p.created_at else None,
                    }
                )
            rprint(json.dumps(data, indent=2))
        else:
            table = Table(title="Prompts")
            table.add_column("Name", style="cyan")
            table.add_column("Versions", justify="right")
            table.add_column("Latest", justify="right")
            table.add_column("Created", style="dim")
            for p in prompts:
                versions = service.list_versions(p.name)
                latest = str(versions[-1].version_number) if versions else "-"
                table.add_row(
                    p.name,
                    str(len(versions)),
                    latest,
                    str(p.created_at.strftime("%Y-%m-%d %H:%M")) if p.created_at else "",
                )
            console.print(table)
    finally:
        session.close()
        reset_engine()


# ------------------------------------------------------------------
# log
# ------------------------------------------------------------------


@app.command()
def log(
    name: Annotated[str, typer.Argument(help="Prompt name")],
    db: DbOption = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
) -> None:
    """Show version history for a prompt."""
    import json

    service, session = _get_service(db)
    try:
        versions = service.list_versions(name)
        if not versions:
            rprint(f"[dim]No versions for '{name}'.[/dim]")
            return

        if json_output:
            data = [
                {
                    "version": v.version_number,
                    "hash": v.content_hash[:12],
                    "note": v.note,
                    "tags": [t.name for t in v.tags],
                    "created_at": v.created_at.isoformat() if v.created_at else None,
                }
                for v in versions
            ]
            rprint(json.dumps(data, indent=2))
        else:
            table = Table(title=f"Versions of '{name}'")
            table.add_column("Version", justify="right", style="cyan")
            table.add_column("Hash", style="dim")
            table.add_column("Tags")
            table.add_column("Note")
            table.add_column("Created", style="dim")
            for v in versions:
                table.add_row(
                    str(v.version_number),
                    v.content_hash[:12],
                    ", ".join(t.name for t in v.tags) or "-",
                    v.note or "-",
                    v.created_at.strftime("%Y-%m-%d %H:%M") if v.created_at else "",
                )
            console.print(table)
    except ValueError as exc:
        rprint(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from None
    finally:
        session.close()
        reset_engine()


# ------------------------------------------------------------------
# show
# ------------------------------------------------------------------


@app.command()
def show(
    name: Annotated[str, typer.Argument(help="Prompt name")],
    version: Annotated[
        int | None,
        typer.Option("--version", "-v", help="Version number (default: latest)."),
    ] = None,
    db: DbOption = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
) -> None:
    """Show the content of a prompt version."""
    import json

    service, session = _get_service(db)
    try:
        if version is not None:
            ver = service.get_version(name, version)
        else:
            ver = service.get_latest_version(name)

        if json_output:
            data = {
                "name": name,
                "version": ver.version_number,
                "content": ver.content,
                "hash": ver.content_hash,
                "note": ver.note,
                "tags": [t.name for t in ver.tags],
                "created_at": ver.created_at.isoformat() if ver.created_at else None,
            }
            rprint(json.dumps(data, indent=2))
        else:
            rprint(f"[bold cyan]{name}[/bold cyan] v{ver.version_number}")
            rprint(
                f"[dim]Hash: {ver.content_hash[:12]} | "
                f"Tags: {', '.join(t.name for t in ver.tags) or 'none'} | "
                f"Note: {ver.note or 'none'}[/dim]"
            )
            rprint()
            rprint(ver.content)
    except ValueError as exc:
        rprint(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from None
    finally:
        session.close()
        reset_engine()


# ------------------------------------------------------------------
# diff
# ------------------------------------------------------------------


@app.command()
def diff(
    name: Annotated[str, typer.Argument(help="Prompt name")],
    v1: Annotated[int, typer.Argument(help="First version number")],
    v2: Annotated[int, typer.Argument(help="Second version number")],
    db: DbOption = None,
) -> None:
    """Show a unified diff between two versions of a prompt."""
    service, session = _get_service(db)
    try:
        result = service.diff_versions(name, v1, v2)
        if not result:
            rprint("[dim]No differences.[/dim]")
        else:
            # Colorize diff output
            for line in result.splitlines():
                if line.startswith("+++") or line.startswith("---"):
                    rprint(f"[bold]{line}[/bold]")
                elif line.startswith("+"):
                    rprint(f"[green]{line}[/green]")
                elif line.startswith("-"):
                    rprint(f"[red]{line}[/red]")
                elif line.startswith("@@"):
                    rprint(f"[cyan]{line}[/cyan]")
                else:
                    rprint(line)
    except ValueError as exc:
        rprint(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from None
    finally:
        session.close()
        reset_engine()


# ------------------------------------------------------------------
# rollback
# ------------------------------------------------------------------


@app.command()
def rollback(
    name: Annotated[str, typer.Argument(help="Prompt name")],
    version: Annotated[int, typer.Argument(help="Version number to rollback to")],
    db: DbOption = None,
) -> None:
    """Rollback a prompt to a previous version (creates a new version)."""
    service, session = _get_service(db)
    try:
        new_ver = service.rollback(name, version)
        session.commit()
        rprint(
            f"[green]✓[/green] Rolled back [bold]{name}[/bold] to v{version} → "
            f"new v{new_ver.version_number}"
        )
    except ValueError as exc:
        session.rollback()
        rprint(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from None
    finally:
        session.close()
        reset_engine()


# ------------------------------------------------------------------
# tag
# ------------------------------------------------------------------


@app.command()
def tag(
    name: Annotated[str, typer.Argument(help="Prompt name")],
    version: Annotated[int, typer.Argument(help="Version number")],
    add_tags: Annotated[
        list[str] | None,
        typer.Option("--add", "-a", help="Tags to add (repeatable)."),
    ] = None,
    remove_tags: Annotated[
        list[str] | None,
        typer.Option("--remove", "-r", help="Tags to remove (repeatable)."),
    ] = None,
    db: DbOption = None,
) -> None:
    """Add or remove tags on a prompt version."""
    if not add_tags and not remove_tags:
        rprint("[red]Error:[/red] Provide --add and/or --remove.")
        raise typer.Exit(1) from None

    service, session = _get_service(db)
    try:
        for t in add_tags or []:
            service.add_tag(name, version, t)
        for t in remove_tags or []:
            service.remove_tag(name, version, t)
        session.commit()
        rprint(f"[green]✓[/green] Updated tags on [bold]{name}[/bold] v{version}")
    except ValueError as exc:
        session.rollback()
        rprint(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from None
    finally:
        session.close()
        reset_engine()


# ------------------------------------------------------------------
# export
# ------------------------------------------------------------------


@app.command()
def export(
    name: Annotated[str, typer.Argument(help="Prompt name")],
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Write to file instead of stdout."),
    ] = None,
    db: DbOption = None,
) -> None:
    """Export all versions of a prompt as JSON."""
    service, session = _get_service(db)
    try:
        if output:
            service.export_to_file(name, output)
            rprint(f"[green]✓[/green] Exported [bold]{name}[/bold] to {output}")
        else:
            rprint(service.export_prompt(name))
    except ValueError as exc:
        rprint(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from None
    finally:
        session.close()
        reset_engine()


# ------------------------------------------------------------------
# delete
# ------------------------------------------------------------------


@app.command()
def delete(
    name: Annotated[str, typer.Argument(help="Prompt name")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation.")] = False,
    db: DbOption = None,
) -> None:
    """Delete a prompt and all its versions."""
    if not yes:
        confirm = typer.confirm(f"Delete prompt '{name}' and all its versions?")
        if not confirm:
            rprint("[dim]Aborted.[/dim]")
            raise typer.Exit(0)

    service, session = _get_service(db)
    try:
        service.delete_prompt(name)
        session.commit()
        rprint(f"[green]✓[/green] Deleted [bold]{name}[/bold]")
    except ValueError as exc:
        session.rollback()
        rprint(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from None
    finally:
        session.close()
        reset_engine()

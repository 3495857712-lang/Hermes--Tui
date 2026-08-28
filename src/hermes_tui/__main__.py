"""Command-line interface for Hermes TUI.

Provides the ``chat``, ``config``, ``doctor``, ``skills``, ``memory``,
and ``version`` commands via Click.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import click

from . import __version__
from .config import DEFAULT_CONFIG_PATH, Config, get_config_dir
from .database import DatabaseManager
from .memory import MemoryManager
from .skills import SkillLoader


def _setup_logging(verbose: bool = False) -> None:
    """Configure root logging for CLI usage."""
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def _load_config() -> Config:
    """Load configuration, creating a default file if needed."""
    config, _ = Config.ensure_default()
    return config


@click.group(invoke_without_command=True)
@click.option("-v", "--verbose", is_flag=True, help="Enable debug logging.")
@click.version_option(version=__version__, prog_name="hermes-tui")
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    """Hermes TUI - A self-improving terminal AI agent."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    _setup_logging(verbose)
    if ctx.invoked_subcommand is None:
        ctx.invoke(chat)


@cli.command()
@click.option("--model", default=None, help="Override the model name.")
@click.option(
    "--theme",
    default=None,
    type=click.Choice(["dark", "light"]),
    help="Override the UI theme.",
)
def chat(model: str | None, theme: str | None) -> None:
    """Launch the interactive TUI chat application."""
    try:
        from .bootstrap import create_app
    except ImportError as exc:
        click.echo(f"Error: failed to load Hermes TUI: {exc}", err=True)
        click.echo('Install dependencies with: pip install -e ".[dev]"', err=True)
        sys.exit(1)
    config = _load_config()
    if model:
        config.llm.model = model
    if theme:
        config.ui.theme = theme
    try:
        app = create_app(config=config)
    except Exception as exc:
        click.echo(f"Error: failed to initialise Hermes TUI: {exc}", err=True)
        logger = logging.getLogger(__name__)
        logger.exception("Bootstrap failed")
        sys.exit(1)
    app.run()


@cli.group()
def config() -> None:
    """Manage configuration."""


@config.command("init")
def config_init() -> None:
    """Generate a default configuration file."""
    _, created = Config.ensure_default()
    if created:
        click.echo(f"Default configuration written to {DEFAULT_CONFIG_PATH}")
    else:
        click.echo(f"Configuration already exists at {DEFAULT_CONFIG_PATH}")


@config.command("path")
def config_path() -> None:
    """Show the path to the configuration file."""
    click.echo(str(DEFAULT_CONFIG_PATH))


@config.command("show")
def config_show() -> None:
    """Display the current configuration."""
    cfg = _load_config()
    click.echo(cfg.model_dump_json(indent=2))


@cli.command()
def doctor() -> None:
    """Run diagnostics and report the environment status."""
    click.echo("Hermes TUI — Environment Check")
    click.echo("=" * 40)

    # Version
    click.echo(f"  Version:      {__version__}")
    click.echo(f"  Python:       {sys.version.split()[0]}")
    click.echo(f"  Config dir:   {get_config_dir()}")
    click.echo(
        f"  Config file:  {DEFAULT_CONFIG_PATH} "
        f"{'(exists)' if DEFAULT_CONFIG_PATH.exists() else '(not found)'}"
    )

    # Config
    try:
        cfg = _load_config()
        click.echo(f"  LLM provider: {cfg.llm.provider}")
        click.echo(f"  LLM model:    {cfg.llm.model}")
        click.echo(f"  LLM base URL: {cfg.llm.base_url}")
    except Exception as exc:
        click.echo(f"  Config error: {exc}", err=True)

    # Database
    try:
        db_path = Path(cfg.memory.db_path).expanduser()
        if db_path.exists():
            db = DatabaseManager(db_path)
            n_memories = db.count_memories()
            n_sessions = len(db.list_sessions())
            db.close()
            click.echo(f"  Database:     {db_path}")
            click.echo(f"    Memories:   {n_memories}")
            click.echo(f"    Sessions:   {n_sessions}")
        else:
            click.echo(f"  Database:     {db_path} (will be created on first run)")
    except Exception as exc:
        click.echo(f"  Database error: {exc}", err=True)

    # Skills
    try:
        skills_dir = Path(cfg.skills.skills_dir).expanduser()
        if skills_dir.is_dir():
            loader = SkillLoader(skills_dir)
            skills = loader.discover()
            click.echo(f"  Skills:       {len(skills)} in {skills_dir}")
        else:
            click.echo(f"  Skills dir:   {skills_dir} (not found)")
    except Exception as exc:
        click.echo(f"  Skills error: {exc}", err=True)

    # Optional dependencies
    for mod, label in [
        ("textual", "TUI framework"),
        ("httpx", "HTTP client"),
        ("yaml", "YAML config"),
        ("pydantic", "Data validation"),
    ]:
        try:
            __import__(mod)
            click.echo(f"  [{label}: OK]")
        except ImportError:
            click.echo(f"  [{label}: MISSING]")

    click.echo("\nAll checks complete.")


@cli.command()
def skills() -> None:
    """List all discovered skills."""
    cfg = _load_config()
    skills_dir = Path(cfg.skills.skills_dir).expanduser()
    loader = SkillLoader(skills_dir)
    discovered = loader.discover()
    if not discovered:
        click.echo("No skills found.")
        click.echo(f"Skills directory: {skills_dir}")
        return
    click.echo(f"Found {len(discovered)} skill(s) in {skills_dir}:\n")
    for s in discovered:
        tags = f" [{', '.join(s.tags)}]" if s.tags else ""
        click.echo(f"  - {s.name} v{s.version}{tags}")
        click.echo(f"    {s.description}")


@cli.group()
def memory() -> None:
    """Manage stored memories."""


def _open_memory(cfg: Config) -> tuple[DatabaseManager, MemoryManager]:
    db_path = Path(cfg.memory.db_path).expanduser()
    db = DatabaseManager(db_path)
    mgr = MemoryManager(db)
    return db, mgr


@memory.command("search")
@click.argument("query")
@click.option(
    "--layer",
    type=click.Choice(["working", "episodic", "procedural"]),
    default=None,
    help="Restrict search to a memory layer.",
)
@click.option("--limit", default=10, show_default=True, help="Max results.")
def memory_search(query: str, layer: str | None, limit: int) -> None:
    """Search memories by keyword."""
    cfg = _load_config()
    db, mgr = _open_memory(cfg)
    try:
        results = mgr.search(query, layer=layer, limit=limit)
        if not results:
            click.echo("No matching memories found.")
            return
        for entry in results:
            tags = f" [{', '.join(entry.tags)}]" if entry.tags else ""
            click.echo(f"  ({entry.layer}) {entry.key}{tags}")
            click.echo(f"    {entry.content[:200]}")
            click.echo()
    finally:
        db.close()


@memory.command("list")
@click.option(
    "--layer",
    type=click.Choice(["working", "episodic", "procedural"]),
    default=None,
    help="Filter by layer.",
)
@click.option("--limit", default=20, show_default=True, help="Max entries.")
def memory_list(layer: str | None, limit: int) -> None:
    """List recent memories."""
    cfg = _load_config()
    db, mgr = _open_memory(cfg)
    try:
        entries = mgr.get_recent(layer=layer, limit=limit)
        if not entries:
            click.echo("No memories stored.")
            return
        for entry in entries:
            tags = f" [{', '.join(entry.tags)}]" if entry.tags else ""
            click.echo(
                f"  #{entry.id} ({entry.layer}) {entry.key}{tags}  accessed={entry.access_count}"
            )
            click.echo(f"    {entry.content[:150]}")
            click.echo()
    finally:
        db.close()


@memory.command("clear")
@click.option(
    "--layer",
    type=click.Choice(["working", "episodic", "procedural"]),
    default=None,
    help="Layer to clear (default: all).",
)
@click.confirmation_option(prompt="Are you sure you want to clear memories?")
def memory_clear(layer: str | None) -> None:
    """Clear stored memories."""
    cfg = _load_config()
    db, mgr = _open_memory(cfg)
    try:
        mgr.clear(layer=layer)
        if layer:
            click.echo(f"Cleared '{layer}' memory layer.")
        else:
            click.echo("Cleared all memories.")
    finally:
        db.close()


@cli.command()
def version() -> None:
    """Show the Hermes TUI version."""
    click.echo(f"hermes-tui {__version__}")


def main() -> None:
    """Console-script entry point."""
    cli(obj={})


if __name__ == "__main__":
    main()

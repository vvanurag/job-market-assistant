"""Command-line entry point: ``jobmarket <command>``."""

from __future__ import annotations

from datetime import UTC

import typer

from jobmarket import __version__
from jobmarket.checks import Status, run_all
from jobmarket.settings import get_settings

app = typer.Typer(help="Job Market Assistant command-line tools.", no_args_is_help=True)

_COLOURS = {
    Status.PASS: typer.colors.GREEN,
    Status.WARN: typer.colors.YELLOW,
    Status.FAIL: typer.colors.RED,
    Status.SKIP: typer.colors.BRIGHT_BLACK,
}


@app.callback()
def main() -> None:
    """Job Market Assistant command-line tools."""


@app.command()
def doctor(
    deep: bool = typer.Option(False, "--deep", help="Also call each model and API to prove it works."),
) -> None:
    """Check that the local environment meets the Phase 0 exit criteria."""
    results = run_all(get_settings(), deep=deep)
    width = max(len(r.name) for r in results)
    for r in results:
        badge = typer.style(f"{r.status.value:<4}", fg=_COLOURS[r.status], bold=True)
        typer.echo(f"  {badge}  {r.name:<{width}}  {r.detail}")

    failed = [r for r in results if r.status is Status.FAIL]
    warned = [r for r in results if r.status is Status.WARN]
    typer.echo(f"\n{len(results) - len(failed) - len(warned)} passed, {len(warned)} warnings, {len(failed)} failed")
    if failed:
        raise typer.Exit(code=1)


@app.command()
def version() -> None:
    """Print the package version."""
    typer.echo(__version__)


bronze_app = typer.Typer(help="Bronze layer: load and inspect raw records.", no_args_is_help=True)
app.add_typer(bronze_app, name="bronze")


@bronze_app.command("load")
def bronze_load(
    source: str = typer.Option(None, help="Only load this source."),
    batch: str = typer.Option(None, help="Only load this batch."),
) -> None:
    """Load raw posting files into bronze.raw_postings (safe to re-run)."""
    from jobmarket.bronze.loader import load_all

    settings = get_settings()
    results = load_all(settings.duckdb_path, settings.bronze_root, source, batch)
    if not results:
        typer.echo(f"No batches found under {settings.bronze_root}")
        raise typer.Exit(code=1)

    header = f"{'source':<20} {'batch':<12} {'files':>6} {'new':>6} {'same':>6} {'changed':>8} {'invalid':>8}"
    typer.echo(f"{header}  status")
    for r in results:
        colour = {"succeeded": typer.colors.GREEN, "failed": typer.colors.RED}.get(r.status, typer.colors.YELLOW)
        typer.echo(
            f"{r.source_id:<20} {r.batch_id:<12} {r.files_seen:>6} {r.rows_inserted:>6} {r.rows_unchanged:>6} "
            f"{r.rows_conflicting:>8} {r.rows_invalid:>8}  " + typer.style(r.status, fg=colour)
        )
        if r.error:
            typer.echo(f"  error: {r.error}")
    if any(r.status == "failed" for r in results):
        raise typer.Exit(code=1)


@bronze_app.command("status")
def bronze_status() -> None:
    """Show how many postings Bronze holds per source and batch."""
    from jobmarket.bronze.loader import bronze_summary

    rows = bronze_summary(get_settings().duckdb_path)
    if not rows:
        typer.echo("Bronze is empty. Run: jobmarket bronze load")
        return
    typer.echo(f"{'source':<20} {'batch':<12} {'postings':>9}  last loaded (UTC)")
    for source_id, batch_id, postings, last_loaded in rows:
        typer.echo(f"{source_id:<20} {batch_id:<12} {postings:>9}  {last_loaded.astimezone(UTC):%Y-%m-%d %H:%M:%S}")
    typer.echo(f"{'total':<33} {sum(r[2] for r in rows):>9}")


if __name__ == "__main__":
    app()

"""Command-line entry point: ``jobmarket <command>``."""

from __future__ import annotations

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


if __name__ == "__main__":
    app()
